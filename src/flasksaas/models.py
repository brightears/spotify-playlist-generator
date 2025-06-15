"""Database models for the FlaskSaaS skeleton.
Only the User model is defined for now – sufficient for email / password auth.
"""
from datetime import datetime
from flask_bcrypt import Bcrypt
from flask_login import UserMixin
from sqlalchemy.orm import validates

from . import db

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
