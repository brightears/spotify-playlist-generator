"""Auth blueprint – email/password registration + login."""
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_user, logout_user, current_user, login_required
from google.auth.transport import requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from .. import db
from ..models import User
from ..forms import LoginForm, RegisterForm

auth_bp = Blueprint("auth", __name__, template_folder="templates")

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

# Configure OAuth flow
def get_google_oauth_flow():
    """Create and configure Google OAuth flow."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return None
    
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [url_for('auth.google_callback', _external=True)]
            }
        },
        scopes=["openid", "email", "profile"]
    )
    flow.redirect_uri = url_for('auth.google_callback', _external=True)
    return flow

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Debug authentication state
    print(f"Login route - current_user.is_authenticated: {current_user.is_authenticated}")
    
    if current_user.is_authenticated:
        print("User is already authenticated, redirecting to dashboard")
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        print(f"Form validated - Email: {form.email.data}")
        user = User.query.filter_by(email=form.email.data.lower()).first()
        
        if user:
            print(f"User found: {user.email}")
            valid_password = user.check_password(form.password.data)
            print(f"Password valid: {valid_password}")
            
            if valid_password:
                login_user(user, remember=form.remember.data)
                print(f"User logged in successfully. Remember me: {form.remember.data}")
                print(f"Current user authenticated after login: {current_user.is_authenticated}")
                
                flash("Logged in successfully!", "success")
                
                # Check if the request prefers JSON (for AJAX requests from browser preview)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': True,
                        'message': 'Logged in successfully!',
                        'redirect': url_for('main.dashboard')
                    })
                
                next_page = request.args.get("next") or url_for("main.dashboard")
                print(f"Redirecting to: {next_page}")
                return redirect(next_page)
        
        print("Login failed - Invalid credentials")
        flash("Invalid credentials", "danger")
        
        # Return JSON error for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': 'Invalid credentials'
            }), 401
    elif request.method == "POST":
        print(f"Form validation failed: {form.errors}")
        
        # Return JSON validation errors for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': 'Form validation failed',
                'errors': form.errors
            }), 400
    
    return render_template("auth/login.html", form=form)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower()).first():
            flash("Email already registered", "warning")
        else:
            user = User(email=form.email.data.lower())
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            
            # Automatically log in the new user
            login_user(user, remember=True)
            flash("Registration successful! Let's get you started with a subscription.", "success")
            return redirect(url_for("billing.subscription"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/direct-login/<email>/<password>")
def direct_login(email, password):
    """Direct login endpoint for testing in browser preview environments.
    WARNING: This endpoint should be disabled in production!
    """
    # For development use only - this bypasses the form
    user = User.query.filter_by(email=email.lower()).first()
    
    if user and user.check_password(password):
        login_user(user, remember=True)
        return jsonify({
            'success': True,
            'message': 'Logged in successfully via direct login!',
            'user': {
                'email': user.email,
                'is_authenticated': current_user.is_authenticated
            },
            'next': url_for('main.dashboard')
        })
    
    return jsonify({
        'success': False,
        'message': 'Invalid credentials for direct login'
    }), 401


@auth_bp.route("/google-login")
def google_login():
    """Initiate Google OAuth login."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    
    flow = get_google_oauth_flow()
    if not flow:
        flash("Google OAuth is not configured.", "error")
        return redirect(url_for("auth.login"))
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    
    session['oauth_state'] = state
    return redirect(authorization_url)


@auth_bp.route("/google-callback")
def google_callback():
    """Handle Google OAuth callback."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    
    # Verify state parameter
    if 'oauth_state' not in session or request.args.get('state') != session['oauth_state']:
        flash("Invalid OAuth state. Please try again.", "error")
        return redirect(url_for("auth.login"))
    
    flow = get_google_oauth_flow()
    if not flow:
        flash("Google OAuth is not configured.", "error")
        return redirect(url_for("auth.login"))
    
    try:
        # Fetch token
        flow.fetch_token(authorization_response=request.url)
        
        # Get user info from Google
        credentials = flow.credentials
        request_session = requests.Request()
        id_info = id_token.verify_oauth2_token(
            credentials.id_token, request_session, GOOGLE_CLIENT_ID
        )
        
        # Extract user information
        email = id_info.get('email', '').lower()
        name = id_info.get('name', '')
        
        if not email:
            flash("Unable to get email from Google account.", "error")
            return redirect(url_for("auth.login"))
        
        # Check if user exists
        user = User.query.filter_by(email=email).first()
        
        if not user:
            # Create new user for Google OAuth
            user = User(email=email, name=name if name else email.split('@')[0])
            # Set a random password since they'll use OAuth
            user.set_password(os.urandom(24).hex())
            user.google_id = id_info.get('sub')  # Store Google ID if User model supports it
            db.session.add(user)
            db.session.commit()
            
            login_user(user, remember=True)
            flash(f"Welcome {name or email}! Account created successfully.", "success")
            return redirect(url_for("billing.subscription"))
        else:
            # Log in existing user
            login_user(user, remember=True)
            flash(f"Welcome back {user.name or user.email}!", "success")
            return redirect(url_for("main.dashboard"))
            
    except Exception as e:
        print(f"Google OAuth error: {str(e)}")
        flash("Authentication failed. Please try again.", "error")
        return redirect(url_for("auth.login"))
    finally:
        # Clean up session
        session.pop('oauth_state', None)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile")
@login_required
def profile():
    """User profile page."""
    return render_template("auth/profile.html")
