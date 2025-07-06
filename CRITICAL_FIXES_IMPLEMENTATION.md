# Critical Security Fixes - Implementation Guide

This guide provides copy-paste ready code to fix the most critical security vulnerabilities identified in the audit.

## 1. Remove Direct Login Endpoint

**File:** `src/flasksaas/auth/routes.py`

Replace lines 164-188 with:

```python
# Direct login endpoint removed for security
# This was a development-only feature that bypassed security controls
```

## 2. Fix SQL Injection in Migration Scripts

**File:** `migrate_db.py`

Replace the vulnerable code with:

```python
# Define allowed columns and their types
SUBSCRIPTION_COLUMNS = {
    'stripe_customer_id': 'VARCHAR(255)',
    'subscription_id': 'VARCHAR(255)', 
    'subscription_status': 'VARCHAR(50)',
    'subscription_plan': 'VARCHAR(50)',
    'subscription_current_period_end': 'DATETIME'
}

OAUTH_COLUMNS = {
    'name': 'VARCHAR(100)',
    'google_id': 'VARCHAR(50)'
}

# Add missing subscription columns
for column, column_type in SUBSCRIPTION_COLUMNS.items():
    if column not in columns:
        print(f"Adding column: {column}")
        # Use parameterized query structure
        cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {column_type}")

# Add missing OAuth columns  
for column, column_type in OAUTH_COLUMNS.items():
    if column not in columns:
        print(f"Adding column: {column}")
        cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {column_type}")
```

## 3. Remove Hardcoded Test Users

**File:** `src/flasksaas/models.py`

Replace the `has_active_subscription` property (lines 66-86) with:

```python
@property
def has_active_subscription(self):
    """Check if the user has an active subscription."""
    from datetime import datetime
    
    if not self.subscription_status:
        return False
        
    # Check if subscription is active and not expired
    active_statuses = ['active', 'trialing', 'canceled']
    if self.subscription_status in active_statuses:
        # Check if subscription hasn't expired
        if self.subscription_current_period_end:
            return datetime.utcnow() < self.subscription_current_period_end
        return True
        
    return False
```

Also update the cancel method in `src/flasksaas/billing/routes.py` (lines 96-104):

```python
@billing_bp.route('/cancel', methods=['POST'])
@login_required
def cancel():
    """Cancel the user's active Stripe subscription."""
    if not current_user.subscription_id:
        flash('No active subscription found.', 'warning')
        return redirect(url_for('billing.subscription'))
    
    # ... rest of the method stays the same
```

## 4. Protect Debug Endpoints

**File:** `web_app.py`

Add this decorator after imports:

```python
from functools import wraps
from flask import abort

def development_only(f):
    """Decorator to restrict endpoints to development environment only."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if IS_PRODUCTION:
            abort(404)  # Return 404 in production as if endpoint doesn't exist
        return f(*args, **kwargs)
    return decorated_function
```

Then update the debug endpoint (line 189):

```python
@app.route('/debug/create-tables')
@development_only
def debug_create_tables():
    """Debug endpoint to manually create database tables."""
    # ... rest of the function stays the same
```

## 5. Fix Stripe Webhook Validation

**File:** `src/flasksaas/billing/routes.py`

Update the webhook handler (lines 126-145):

```python
@billing_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks to keep subscription status in sync."""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    
    # Fail closed if webhook secret not configured
    if not webhook_secret:
        current_app.logger.error('Stripe webhook secret not configured - rejecting webhook')
        return jsonify(success=False, error='Webhook not configured'), 500
    
    # Verify webhook came from Stripe
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        current_app.logger.warning('Invalid Stripe webhook signature')
        return jsonify(success=False, error='Invalid signature'), 400
    except Exception as e:
        current_app.logger.error(f'Stripe webhook error: {str(e)}')
        return jsonify(success=False, error=str(e)), 400
```

## 6. Enable CSRF Protection Always

**File:** `web_app.py`

Change line 102 from:
```python
app.config['WTF_CSRF_ENABLED'] = IS_PRODUCTION
```

To:
```python
app.config['WTF_CSRF_ENABLED'] = True  # Always enable CSRF protection
```

## 7. Add Authentication to API Endpoints

**File:** `src/flasksaas/main/routes.py`

Update the api_status endpoint (lines 120-182):

```python
@main_bp.route('/api/status/<task_id>')
@login_required  # Add this decorator
def api_status(task_id):
    """API endpoint to get task status."""
    # Get task using the task manager
    task = get_task(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # Verify user owns this task
    if task['user_id'] != current_user.id:
        current_app.logger.warning(f'User {current_user.id} attempted to access task {task_id} owned by user {task["user_id"]}')
        return jsonify({'error': 'Access denied'}), 403
    
    # ... rest of the function stays the same
```

## 8. Add Security Headers

**File:** `web_app.py`

Add after the route definitions:

```python
@app.after_request
def set_security_headers(response):
    """Set security headers on all responses."""
    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'DENY'
    
    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # Enable XSS filter in browsers
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Force HTTPS in production
    if IS_PRODUCTION:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    # Basic CSP to prevent XSS
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://js.stripe.com; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self' data:; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://api.stripe.com"
    )
    
    return response
```

## 9. Improve Password Validation

**File:** `src/flasksaas/forms.py`

Add a custom validator and update the RegisterForm:

```python
import re
from wtforms.validators import ValidationError

def password_complexity(form, field):
    """Validate password meets complexity requirements."""
    password = field.data
    
    if len(password) < 8:
        raise ValidationError('Password must be at least 8 characters long')
    
    if not re.search(r'[A-Z]', password):
        raise ValidationError('Password must contain at least one uppercase letter')
    
    if not re.search(r'[a-z]', password):
        raise ValidationError('Password must contain at least one lowercase letter')
    
    if not re.search(r'\d', password):
        raise ValidationError('Password must contain at least one number')
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValidationError('Password must contain at least one special character')

class RegisterForm(FlaskForm):
    """Form for user registration."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        password_complexity
    ])
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Create Account')
```

## 10. Add Input Sanitization

Create a new file `src/flasksaas/utils/sanitize.py`:

```python
import html
import re
from urllib.parse import urlparse

def sanitize_html(text):
    """Escape HTML to prevent XSS."""
    if not text:
        return ''
    return html.escape(str(text))

def sanitize_url(url):
    """Validate and sanitize URLs."""
    if not url:
        return ''
    
    # Parse URL
    try:
        parsed = urlparse(url)
        
        # Only allow http/https
        if parsed.scheme not in ['http', 'https']:
            return ''
        
        # Ensure it's a valid YouTube URL for source URLs
        allowed_domains = ['youtube.com', 'youtu.be', 'www.youtube.com']
        if parsed.netloc not in allowed_domains:
            return ''
        
        return url
    except:
        return ''

def sanitize_filename(filename):
    """Sanitize filename to prevent directory traversal."""
    # Remove any path components
    filename = filename.replace('..', '').replace('/', '').replace('\\', '')
    
    # Only allow alphanumeric, dash, underscore, and dot
    filename = re.sub(r'[^a-zA-Z0-9._-]', '', filename)
    
    return filename[:255]  # Limit length
```

Then use these functions throughout the application when handling user input.

## 11. Implement Rate Limiting Configuration

**File:** `web_app.py`

Update the rate limiter configuration (lines 122-139):

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import redis

def get_user_identifier():
    """Get identifier for rate limiting - authenticated users get higher limits."""
    if current_user and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        return f"user:{current_user.id}"
    return get_remote_address()

# Configure Redis for production rate limiting
if IS_PRODUCTION:
    # Use Redis in production for distributed rate limiting
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    storage_uri = redis_url
else:
    # Use memory storage in development
    storage_uri = "memory://"

limiter = Limiter(
    app=app,
    key_func=get_user_identifier,
    default_limits=["1000 per hour", "100 per minute"] if IS_PRODUCTION else [],
    storage_uri=storage_uri,
    headers_enabled=True,
    swallow_errors=True,  # Don't break the app if Redis is down
)

# Specific endpoint limits
auth_limits = "5 per minute" if IS_PRODUCTION else None
api_limits = "60 per minute" if IS_PRODUCTION else None
payment_limits = "10 per hour" if IS_PRODUCTION else None
```

## 12. Add Failed Login Tracking

Create a new model in `src/flasksaas/models.py`:

```python
class LoginAttempt(db.Model):
    """Track failed login attempts for security."""
    __tablename__ = "login_attempts"
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=False)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)
    success = db.Column(db.Boolean, default=False)
    
    @classmethod
    def is_locked_out(cls, email, lockout_duration=900):  # 15 minutes
        """Check if email is locked out due to failed attempts."""
        cutoff = datetime.utcnow() - timedelta(seconds=lockout_duration)
        
        # Count failed attempts in the last 15 minutes
        failed_attempts = cls.query.filter_by(
            email=email.lower(),
            success=False
        ).filter(
            cls.attempted_at > cutoff
        ).count()
        
        return failed_attempts >= 5  # Lock after 5 failed attempts
```

Then update the login route in `src/flasksaas/auth/routes.py`:

```python
from flask import request
from ..models import LoginAttempt

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        
        # Check if account is locked
        if LoginAttempt.is_locked_out(email):
            flash("Account temporarily locked due to too many failed attempts. Please try again later.", "danger")
            return render_template("auth/login.html", form=form)
        
        user = User.query.filter_by(email=email).first()
        
        # Track login attempt
        attempt = LoginAttempt(
            email=email,
            ip_address=request.remote_addr or 'unknown'
        )
        
        if user and user.check_password(form.password.data):
            attempt.success = True
            db.session.add(attempt)
            db.session.commit()
            
            login_user(user, remember=form.remember.data)
            next_page = request.args.get("next") or url_for("main.dashboard")
            return redirect(next_page)
        else:
            attempt.success = False
            db.session.add(attempt)
            db.session.commit()
            
            flash("Invalid credentials", "danger")
    
    return render_template("auth/login.html", form=form)
```

Remember to create a migration for the new LoginAttempt table.

## Testing the Fixes

After implementing these fixes:

1. Run the application in development mode and verify all features work
2. Try to access debug endpoints - they should return 404
3. Test login with weak passwords - should be rejected
4. Try rapid login attempts - should be rate limited
5. Verify CSRF tokens are required on all forms
6. Check browser developer tools for security headers
7. Test Stripe webhooks with invalid signatures - should be rejected

These fixes address the most critical security vulnerabilities. Implement them immediately before going to production.