"""
User model for authentication and subscription management.
"""
import os
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer, SignatureExpired

# This would typically connect to your database
# For a real implementation, use SQLAlchemy or another ORM
# This is a simplified in-memory implementation for demonstration
users_db = {}

class User(UserMixin):
    """User model for authentication and subscription management."""
    
    def __init__(self, id, email, password_hash=None, is_active=False, 
                 subscription_active=False, subscription_end=None, 
                 spotify_tokens=None, created_playlists=None):
        self.id = id
        self.email = email
        self.password_hash = password_hash
        self.is_active = is_active  # Email verified
        self.subscription_active = subscription_active
        self.subscription_end = subscription_end
        self.spotify_tokens = spotify_tokens or {}
        self.created_playlists = created_playlists or []
    
    def set_password(self, password):
        """Set the password hash for the user."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if the password is correct."""
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        """Return the user ID as a string, required for Flask-Login."""
        return str(self.id)
    
    def has_active_subscription(self):
        """Check if the user has an active subscription."""
        if not self.subscription_active:
            return False
        if not self.subscription_end:
            return False
        return datetime.datetime.now() < self.subscription_end
    
    def activate_subscription(self, months=1):
        """Activate the user's subscription for a number of months."""
        self.subscription_active = True
        if self.subscription_end and self.subscription_end > datetime.datetime.now():
            # Extend existing subscription
            self.subscription_end = self.subscription_end + datetime.timedelta(days=30*months)
        else:
            # New subscription
            self.subscription_end = datetime.datetime.now() + datetime.timedelta(days=30*months)
    
    def deactivate_subscription(self):
        """Deactivate the user's subscription."""
        self.subscription_active = False
    
    def add_spotify_tokens(self, access_token, refresh_token, expires_at):
        """Add Spotify tokens for the user."""
        self.spotify_tokens = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at
        }
    
    def add_created_playlist(self, playlist_data):
        """Add a created playlist to the user's history."""
        self.created_playlists.append(playlist_data)
    
    @staticmethod
    def get_by_email(email):
        """Get a user by email."""
        for user_id, user in users_db.items():
            if user.email == email:
                return user
        return None
    
    @staticmethod
    def get_by_id(id):
        """Get a user by ID."""
        return users_db.get(str(id))
    
    @staticmethod
    def create_user(email, password):
        """Create a new user."""
        # Check if user exists
        if User.get_by_email(email):
            return None
        
        # Create new user
        user_id = str(len(users_db) + 1)  # Simple ID generation
        user = User(user_id, email)
        user.set_password(password)
        users_db[user_id] = user
        return user
    
    @staticmethod
    def generate_confirmation_token(email):
        """Generate a confirmation token for email verification."""
        serializer = URLSafeTimedSerializer(os.environ.get('FLASK_SECRET_KEY'))
        return serializer.dumps(email, salt='email-confirmation')
    
    @staticmethod
    def verify_confirmation_token(token, expiration=3600):
        """Verify a confirmation token and return the email."""
        serializer = URLSafeTimedSerializer(os.environ.get('FLASK_SECRET_KEY'))
        try:
            email = serializer.loads(
                token,
                salt='email-confirmation',
                max_age=expiration
            )
            return email
        except SignatureExpired:
            return None