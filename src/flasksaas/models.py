"""Database models for the FlaskSaaS skeleton.
Only the User model is defined for now – sufficient for email / password auth.
"""
from datetime import datetime
from flask_bcrypt import Bcrypt
from flask_login import UserMixin
from sqlalchemy.orm import validates

from . import db

# Bcrypt instance will be initialized in the main app
bcrypt = Bcrypt()

class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=True)  # Display name from Google or manual entry
    _password = db.Column("password", db.String(128), nullable=False)
    google_id = db.Column(db.String(50), unique=True, nullable=True)  # Google OAuth subject ID
    is_active = db.Column(db.Boolean, default=True)
    is_confirmed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Spotify integration fields
    spotify_access_token = db.Column(db.Text, nullable=True)
    spotify_refresh_token = db.Column(db.Text, nullable=True)
    spotify_token_expires = db.Column(db.Integer, nullable=True)
    spotify_user_id = db.Column(db.String(50), nullable=True)

    # Subscription fields
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    subscription_id = db.Column(db.String(255), nullable=True)
    subscription_status = db.Column(db.String(50), nullable=True)  # active, past_due, canceled, etc.
    subscription_plan = db.Column(db.String(50), nullable=True)    # monthly, yearly
    subscription_current_period_end = db.Column(db.DateTime, nullable=True)

    # ------------------------------------------------------------------
    # Password helpers
    # ------------------------------------------------------------------
    def set_password(self, raw_password: str) -> None:
        self._password = bcrypt.generate_password_hash(raw_password).decode("utf-8")

    def check_password(self, raw_password: str) -> bool:
        return bcrypt.check_password_hash(self._password, raw_password)

    # ------------------------------------------------------------------
    # Flask-Login requirements
    # ------------------------------------------------------------------
    def get_id(self):
        return str(self.id)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @validates("email")
    def _validate_email(self, key, address: str):
        assert "@" in address, "Provided email is invalid"
        return address.lower()
        
    # ------------------------------------------------------------------
    # Subscription helpers
    # ------------------------------------------------------------------
    @property
    def has_active_subscription(self):
        """Check if the user has an active subscription."""
        from datetime import datetime
        
        if not self.subscription_status:
            return False
            
        # Check if subscription is active and not expired
        active_statuses = ['active', 'trialing']
        if self.subscription_status in active_statuses:
            # Check if subscription hasn't expired
            if self.subscription_current_period_end:
                return datetime.utcnow() < self.subscription_current_period_end
            return True
            
        return False
    
    @property 
    def subscription_display_name(self):
        """Get user-friendly subscription name."""
        if not self.has_active_subscription:
            return "Free"
        
        plan_names = {
            'monthly': 'Pro Monthly ($3/month)',
            'yearly': 'Pro Yearly ($24/year)'
        }
        return plan_names.get(self.subscription_plan, 'Pro')


class UserSource(db.Model):
    """User's custom YouTube sources for music discovery."""
    __tablename__ = "user_sources"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)  # User-friendly name for the source
    source_url = db.Column(db.Text, nullable=False)  # YouTube channel/playlist URL
    source_type = db.Column(db.String(20), nullable=False)  # 'channel' or 'playlist'
    is_active = db.Column(db.Boolean, default=True)  # Whether to include in discovery
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = db.relationship('User', backref=db.backref('custom_sources', lazy=True))
    
    @validates("source_url")
    def _validate_source_url(self, key, url: str):
        """Validate that the URL is a YouTube channel or playlist."""
        if not url:
            raise ValueError("Source URL is required")
        
        url = url.strip()
        youtube_patterns = [
            'youtube.com/channel/',
            'youtube.com/c/',
            'youtube.com/@',
            'youtube.com/user/',
            'youtube.com/playlist?list=',
            'youtu.be/playlist?list='
        ]
        
        if not any(pattern in url.lower() for pattern in youtube_patterns):
            raise ValueError("URL must be a valid YouTube channel or playlist")
        
        return url
    
    @validates("source_type")
    def _validate_source_type(self, key, source_type: str):
        """Validate source type is either 'channel' or 'playlist'."""
        valid_types = ['channel', 'playlist']
        if source_type not in valid_types:
            raise ValueError(f"Source type must be one of: {valid_types}")
        return source_type
    
    def __repr__(self):
        return f'<UserSource {self.name} ({self.source_type})>'
