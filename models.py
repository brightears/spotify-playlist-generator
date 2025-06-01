"""Database models for the Spotify Playlist Generator app."""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# SQLAlchemy instance will be initialised by the main app
# (see web_app.py where db.init_app(app) is called)

db = SQLAlchemy()

class User(db.Model, UserMixin):
    """Application user."""

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Subscription information
    subscription_status = db.Column(db.String(32), default='none')  # none | active | canceled
    subscription_end_date = db.Column(db.DateTime, nullable=True)

    # Stripe
    stripe_customer_id = db.Column(db.String(64))
    stripe_subscription_id = db.Column(db.String(64))

    def set_password(self, password: str) -> None:
        """Hash and store the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a plaintext password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def has_active_subscription(self) -> bool:
        """Return True if the user has an active subscription."""
        if self.subscription_status != 'active':
            return False
        if self.subscription_end_date and self.subscription_end_date < datetime.utcnow():
            return False
        return True