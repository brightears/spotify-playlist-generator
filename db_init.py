#!/usr/bin/env python3
"""
Initialize the FlaskSaaS database tables
"""
import os
from src.flasksaas import db
from src.flasksaas.models import User  # Import models to ensure they're registered
from web_app import app

if __name__ == "__main__":
    with app.app_context():
        print(f"Database URL: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print("Creating database tables...")
        
        # Drop existing tables if they exist (for clean deployment)
        if os.environ.get('RENDER'):
            print("On Render - creating fresh tables...")
            db.drop_all()
        
        db.create_all()
        print("Database tables created successfully.")
        
        # Verify tables were created
        tables = db.engine.table_names()
        print(f"Created tables: {tables}")
