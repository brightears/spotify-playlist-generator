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

    def get_reset_password_token(self, expires_in=600):
        """Generate a password reset token that expires in 10 minutes."""
        from itsdangerous import URLSafeTimedSerializer
        from flask import current_app
        
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps({'reset_password': self.id}, salt='password-reset-salt')
    
    @staticmethod
    def verify_reset_password_token(token, max_age=600):
        """Verify the password reset token and return the user."""
        from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
        from flask import current_app
        
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, salt='password-reset-salt', max_age=max_age)
            user_id = data.get('reset_password')
            if user_id:
                return User.query.get(user_id)
        except (SignatureExpired, BadSignature):
            return None
        return None

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
        active_statuses = ['active', 'trialing', 'canceled']
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
    
    @validates("name")
    def _validate_name(self, key, name: str):
        """Validate and sanitize the source name."""
        from markupsafe import escape
        
        if not name:
            raise ValueError("Source name is required")
        
        # Sanitize to prevent XSS
        name = str(escape(name.strip()))[:200]
        
        if not name:
            raise ValueError("Source name cannot be empty")
            
        return name
    
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


class PlaylistTask(db.Model):
    """Stores playlist generation tasks."""
    __tablename__ = "playlist_tasks"
    
    id = db.Column(db.String(36), primary_key=True)  # UUID
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, processing, completed, failed
    progress = db.Column(db.Integer, default=0)  # 0-100
    
    # Task parameters
    playlist_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    genre = db.Column(db.String(50))
    days = db.Column(db.Integer, default=7)
    is_public = db.Column(db.Boolean, default=True)
    source_selection = db.Column(db.Text, default='both')  # Changed to Text to support Pro users' multiple selections
    
    # Results
    spotify_playlist_url = db.Column(db.Text)
    spotify_playlist_id = db.Column(db.String(100))
    tracks_found = db.Column(db.Integer, default=0)
    tracks_matched = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('playlist_tasks', lazy=True))
    

class GeneratedPlaylist(db.Model):
    """Stores successfully generated playlists for history."""
    __tablename__ = "generated_playlists"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    task_id = db.Column(db.String(36), db.ForeignKey('playlist_tasks.id'))
    
    # Playlist details
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    spotify_url = db.Column(db.Text)  # No longer used, made nullable
    spotify_id = db.Column(db.String(100))  # No longer used, made nullable
    
    # Stats
    track_count = db.Column(db.Integer, default=0)
    source_channel = db.Column(db.String(100))  # Which YouTube channel/source was used
    days_analyzed = db.Column(db.Integer)
    
    # CSV data (compressed)
    csv_data = db.Column(db.Text)  # Store base64 encoded compressed CSV
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('playlists', lazy=True))
    task = db.relationship('PlaylistTask', backref=db.backref('playlist', uselist=False))
    
    @validates("source_type")
    def _validate_source_type(self, key, source_type: str):
        """Validate source type is either 'channel' or 'playlist'."""
        valid_types = ['channel', 'playlist']
        if source_type not in valid_types:
            raise ValueError(f"Source type must be one of: {valid_types}")
        return source_type
    
    def __repr__(self):
        return f'<UserSource {self.name} ({self.source_type})>'
