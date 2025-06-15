#!/usr/bin/env python3
"""
Initialize the FlaskSaaS database tables
"""
from src.flasksaas import db
from web_app import app

if __name__ == "__main__":
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("Database tables created successfully.")
