"""Authentication blueprint for the Spotify Playlist Generator app."""

from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from models import db, User

auth_bp = Blueprint('auth', __name__, template_folder='templates')

# ---------------------- helpers ---------------------- #

def _validate_password(password: str) -> bool:
    """Basic password policy: at least 8 characters."""
    return len(password) >= 8

# ---------------------- routes ----------------------- #

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        # Support either field name (password_confirm preferred in templates)
        confirm = request.form.get('password_confirm', request.form.get('confirm_password', ''))
        
        # Debug output to help with form troubleshooting
        print(f"Form data received - Email: {email}, Password length: {len(password)}, Confirm length: {len(confirm)}")
        print(f"Form fields: {list(request.form.keys())}")

        if not email or not password:
            flash('Email and password are required.', 'danger')
            return render_template('auth/register.html')

        if password != confirm:
            flash(f'Passwords do not match. Please try again.', 'danger')
            return render_template('auth/register.html')

        if not _validate_password(password):
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('This email is already registered.', 'danger')
            return render_template('auth/register.html')

        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])

def login():
    """User login."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=bool(request.form.get('remember')))
            user.last_login = datetime.utcnow()
            db.session.commit()
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))

        flash('Invalid email or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html')


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_pwd = request.form.get('current_password', '')
    new_pwd = request.form.get('new_password', '')
    # Support either field name (password_confirm preferred in templates)
    confirm = request.form.get('password_confirm', request.form.get('confirm_password', ''))

    if not current_user.check_password(current_pwd):
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('auth.profile'))

    if new_pwd != confirm:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('auth.profile'))

    if not _validate_password(new_pwd):
        flash('Password must be at least 8 characters.', 'danger')
        return redirect(url_for('auth.profile'))

    current_user.set_password(new_pwd)
    db.session.commit()
    flash('Password updated successfully.', 'success')
    return redirect(url_for('auth.profile'))


@auth_bp.route('/update-account', methods=['POST'])
@login_required
def update_account():
    """Update user account details."""
    # Get form data
    email = request.form.get('email', '').strip().lower()
    
    # Validate email
    if not email:
        flash('Email is required.', 'danger')
        return redirect(url_for('auth.profile'))
    
    # Check if email is already taken by another user
    existing_user = User.query.filter_by(email=email).first()
    if existing_user and existing_user.id != current_user.id:
        flash('This email is already associated with another account.', 'danger')
        return redirect(url_for('auth.profile'))
    
    # Update the user's email
    current_user.email = email
    db.session.commit()
    
    flash('Account information updated successfully.', 'success')
    return redirect(url_for('auth.profile'))


@auth_bp.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    """Delete user account and all associated data."""
    # Confirm with password for security
    password = request.form.get('password', '')
    
    if not current_user.check_password(password):
        flash('Incorrect password. Account deletion canceled.', 'danger')
        return redirect(url_for('auth.profile'))
    
    # Cancel any active subscriptions
    if current_user.has_active_subscription and current_user.stripe_subscription_id:
        try:
            import stripe
            stripe.Subscription.delete(current_user.stripe_subscription_id)
        except Exception as e:
            # Log the error but continue with account deletion
            print(f"Error canceling Stripe subscription: {e}")
    
    # Store the user ID for deletion
    user_id = current_user.id
    
    # Log the user out first
    logout_user()
    
    # Delete the user
    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        flash('Your account has been permanently deleted.', 'success')
    
    return redirect(url_for('index'))


# ---------------------- helpers end ------------------ #

# explainer: Introduced an `auth` Blueprint with routes for register, login, logout, profile, password change, account update, and account deletion. Uses Flask-Login for authentication and SQLAlchemy for user persistence. Passwords hashed securely and basic flash messaging added. -->
