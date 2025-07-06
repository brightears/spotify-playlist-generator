"""Auth blueprint – email/password registration + login."""
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_user, logout_user, current_user, login_required
from google.auth.transport import requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from .. import db
from ..models import User
from ..forms import LoginForm, RegisterForm, ResetPasswordRequestForm, ResetPasswordForm
from flask_mail import Message
from flask import current_app

auth_bp = Blueprint("auth", __name__, template_folder="templates")

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

# Configure OAuth flow
def get_google_oauth_flow():
    """Create and configure Google OAuth flow."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return None
    
    # For Render deployment, we need to ensure HTTPS is used
    # Get the base URL from environment or construct it
    if os.environ.get('RENDER'):
        # On Render, force HTTPS
        scheme = 'https'
        # Use the Render service URL or construct from request
        if request:
            redirect_uri = url_for('auth.google_callback', _external=True, _scheme=scheme)
        else:
            # Fallback for when request context is not available
            app_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://spotify-playlist-generator-rcva.onrender.com')
            redirect_uri = f"{app_url}/auth/google-callback"
    else:
        # Local development
        redirect_uri = url_for('auth.google_callback', _external=True)
    
    print(f"DEBUG: Google OAuth redirect URI: {redirect_uri}")
    
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        },
        scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile"
        ]
    )
    flow.redirect_uri = redirect_uri
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
                
                # No flash message needed - being on dashboard is enough confirmation
                
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
        print(f"Registration form validated for email: {form.email.data}")
        
        if User.query.filter_by(email=form.email.data.lower()).first():
            print("Email already registered")
            flash("Email already registered", "warning")
        else:
            try:
                print("Creating new user...")
                user = User(email=form.email.data.lower())
                print("Setting password...")
                user.set_password(form.password.data)
                print("Adding to database session...")
                db.session.add(user)
                print("Committing to database...")
                db.session.commit()
                print("User created successfully!")
                
                # Automatically log in the new user
                print("Logging in new user...")
                login_user(user, remember=True)
                print("User logged in successfully!")
                flash("Registration successful! Let's get you started with a subscription.", "success")
                return redirect(url_for("billing.subscription"))
            except Exception as e:
                print(f"Error during registration: {str(e)}")
                db.session.rollback()
                flash("Registration failed. Please try again.", "error")
    else:
        if request.method == "POST":
            print(f"Form validation failed: {form.errors}")
    
    return render_template("auth/register.html", form=form)


# Direct login endpoint removed for security
# This was a development-only feature that bypassed security controls


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
        include_granted_scopes='true',
        prompt='consent'  # Force consent to avoid scope mismatch
    )
    
    session['oauth_state'] = state
    return redirect(authorization_url)


@auth_bp.route("/google-callback")
def google_callback():
    """Handle Google OAuth callback."""
    print(f"Google callback received with args: {dict(request.args)}")
    
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    
    # Check for errors from Google
    error = request.args.get('error')
    if error:
        print(f"Google OAuth error: {error}")
        error_desc = request.args.get('error_description', 'Unknown error')
        flash(f"Google login failed: {error_desc}", "error")
        return redirect(url_for("auth.login"))
    
    # Verify state parameter
    state = request.args.get('state')
    stored_state = session.get('oauth_state')
    print(f"State verification - received: {state}, stored: {stored_state}")
    
    if not stored_state or state != stored_state:
        flash("Invalid OAuth state. Please try again.", "error")
        return redirect(url_for("auth.login"))
    
    flow = get_google_oauth_flow()
    if not flow:
        flash("Google OAuth is not configured.", "error")
        return redirect(url_for("auth.login"))
    
    try:
        print("Fetching token from Google...")
        # Fetch token - handle scope mismatch by catching and retrying
        try:
            flow.fetch_token(authorization_response=request.url)
        except Exception as e:
            error_msg = str(e)
            print(f"Token fetch error: {error_msg}")
            if "Scope has changed" in error_msg:
                # This is a known issue with google-auth library
                # The scopes are equivalent, just in different format
                # Try to fetch token without scope verification
                import urllib.parse
                parsed_url = urllib.parse.urlparse(request.url)
                params = urllib.parse.parse_qs(parsed_url.query)
                code = params.get('code', [None])[0]
                
                if code:
                    # Manually exchange the code for tokens
                    token_url = "https://oauth2.googleapis.com/token"
                    token_data = {
                        'code': code,
                        'client_id': GOOGLE_CLIENT_ID,
                        'client_secret': GOOGLE_CLIENT_SECRET,
                        'redirect_uri': flow.redirect_uri,
                        'grant_type': 'authorization_code'
                    }
                    
                    import requests as req
                    response = req.post(token_url, data=token_data)
                    if response.status_code == 200:
                        token_info = response.json()
                        flow.credentials._token = token_info.get('access_token')
                        flow.credentials._id_token = token_info.get('id_token')
                        flow.credentials._refresh_token = token_info.get('refresh_token')
                        flow.credentials._expiry = None
                        print("Token obtained via manual exchange")
                    else:
                        raise Exception(f"Manual token exchange failed: {response.text}")
                else:
                    raise Exception("No authorization code found")
            else:
                raise
        
        print("Token fetched successfully, getting user info...")
        # Get user info from Google
        credentials = flow.credentials
        request_session = requests.Request()
        id_info = id_token.verify_oauth2_token(
            credentials.id_token, request_session, GOOGLE_CLIENT_ID
        )
        print(f"User info retrieved: email={id_info.get('email')}, name={id_info.get('name')}")
        
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
            # No flash message needed - being on dashboard is enough confirmation
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


@auth_bp.route("/reset-password-request", methods=["GET", "POST"])
def reset_password_request():
    """Request a password reset."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    
    form = ResetPasswordRequestForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            send_password_reset_email(user)
        # Always show success message to prevent email enumeration
        flash("Check your email for instructions to reset your password.", "info")
        return redirect(url_for("auth.login"))
    
    return render_template("auth/reset_password_request.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Reset password with token."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    
    user = User.verify_reset_password_token(token)
    if not user:
        flash("Invalid or expired reset link.", "error")
        return redirect(url_for("auth.login"))
    
    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been reset.", "success")
        return redirect(url_for("auth.login"))
    
    return render_template("auth/reset_password.html", form=form)


def send_password_reset_email(user):
    """Send password reset email to user."""
    token = user.get_reset_password_token()
    
    # Get mail instance from app extensions
    mail = current_app.extensions.get('mail')
    
    if mail and current_app.config.get('MAIL_USERNAME'):
        msg = Message(
            subject="[Bright Ears] Reset Your Password",
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'support@brightears.io'),
            recipients=[user.email]
        )
        
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        
        msg.body = f"""Dear Bright Ears user,

You have requested a password reset. Click the link below to reset your password:

{reset_url}

This link will expire in 10 minutes for security reasons.

If you did not request this reset, please ignore this email.

Best regards,
The Bright Ears Team
"""
        
        msg.html = f"""
<p>Dear Bright Ears user,</p>

<p>You have requested a password reset. Click the link below to reset your password:</p>

<p><a href="{reset_url}" style="display: inline-block; padding: 12px 24px; background-color: #00CFFF; color: #121212; text-decoration: none; border-radius: 24px; font-weight: bold;">Reset Password</a></p>

<p>Or copy this link: {reset_url}</p>

<p>This link will expire in 10 minutes for security reasons.</p>

<p>If you did not request this reset, please ignore this email.</p>

<p>Best regards,<br>
The Bright Ears Team</p>
"""
        
        try:
            mail.send(msg)
            current_app.logger.info(f"Password reset email sent to {user.email}")
        except Exception as e:
            current_app.logger.error(f"Failed to send password reset email: {str(e)}")
    else:
        # If mail not configured, log the reset link (development only)
        current_app.logger.warning(f"Mail not configured. Reset link for {user.email}: {url_for('auth.reset_password', token=token, _external=True)}")
