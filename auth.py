"""
Authentication routes for user registration, login, and account management.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.urls import url_parse
from models.user import User
import os
from utils.email_service import send_email

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    """Register a new user."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Validate form data
        if not email or not password:
            flash('Email and password are required', 'danger')
            return render_template('auth/register.html')
        
        # Check if user exists
        if User.get_by_email(email):
            flash('Email already registered', 'danger')
            return render_template('auth/register.html')
        
        # Create user
        user = User.create_user(email, password)
        
        # Generate confirmation token and send email
        token = User.generate_confirmation_token(email)
        confirmation_url = url_for('auth.confirm_email', token=token, _external=True)
        
        # Send confirmation email
        subject = 'Please confirm your email'
        html_content = f'''
        <p>Welcome to the Spotify Playlist Generator!</p>
        <p>Please confirm your email by <a href="{confirmation_url}">clicking here</a>.</p>
        <p>If you did not register for this account, please ignore this email.</p>
        '''
        send_email(email, subject, html_content)
        
        flash('A confirmation email has been sent to your email address.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@auth.route('/confirm/<token>')
def confirm_email(token):
    """Confirm email address."""
    if current_user.is_authenticated and current_user.is_active:
        return redirect(url_for('main.index'))
    
    email = User.verify_confirmation_token(token)
    if not email:
        flash('The confirmation link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.login'))
    
    user = User.get_by_email(email)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.login'))
    
    user.is_active = True
    flash('Your email has been confirmed. You can now log in.', 'success')
    return redirect(url_for('auth.login'))

@auth.route('/login', methods=['GET', 'POST'])
def login():
    """Log in a user."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember', False) == 'on'
        
        user = User.get_by_email(email)
        
        if not user or not user.check_password(password):
            flash('Invalid email or password', 'danger')
            return render_template('auth/login.html')
        
        if not user.is_active:
            flash('Please confirm your email before logging in.', 'warning')
            return render_template('auth/login.html')
        
        login_user(user, remember=remember)
        
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('main.dashboard')
        
        return redirect(next_page)
    
    return render_template('auth/login.html')

@auth.route('/logout')
@login_required
def logout():
    """Log out a user."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))

@auth.route('/profile')
@login_required
def profile():
    """Show user profile."""
    return render_template('auth/profile.html')

@auth.route('/reset-password-request', methods=['GET', 'POST'])
def reset_password_request():
    """Request password reset."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.get_by_email(email)
        
        if user:
            token = User.generate_confirmation_token(email)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            subject = 'Password Reset Request'
            html_content = f'''
            <p>To reset your password, <a href="{reset_url}">click here</a>.</p>
            <p>If you did not make this request, please ignore this email.</p>
            '''
            send_email(email, subject, html_content)
        
        flash('If your email is registered, you will receive password reset instructions.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password_request.html')

@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    email = User.verify_confirmation_token(token)
    if not email:
        flash('The reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.login'))
    
    user = User.get_by_email(email)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        
        if not password:
            flash('Password is required', 'danger')
            return render_template('auth/reset_password.html')
        
        user.set_password(password)
        flash('Your password has been reset.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html')