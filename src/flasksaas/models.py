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
    _password = db.Column("password", db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_confirmed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
