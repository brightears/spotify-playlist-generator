#!/usr/bin/env python
"""Migration to remove Spotify-related columns from the database."""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

from web_app import app, db
from sqlalchemy import text

def remove_spotify_columns():
    """Remove Spotify-related columns from the users table."""
    with app.app_context():
        # Check if we're using PostgreSQL or SQLite
        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        is_postgres = 'postgresql' in db_url
        
        if is_postgres:
            # PostgreSQL syntax
            print("Removing Spotify columns from PostgreSQL database...")
            try:
                # Drop columns one by one to avoid errors if they don't exist
                columns_to_drop = [
                    'spotify_access_token',
                    'spotify_refresh_token',
                    'spotify_token_expires',
                    'spotify_user_id'
                ]
                
                for column in columns_to_drop:
                    try:
                        db.session.execute(text(f'ALTER TABLE users DROP COLUMN IF EXISTS {column}'))
                        print(f"✓ Dropped column: {column}")
                    except Exception as e:
                        print(f"✗ Error dropping column {column}: {e}")
                
                db.session.commit()
                print("PostgreSQL migration complete!")
                
            except Exception as e:
                print(f"Migration error: {e}")
                db.session.rollback()
        else:
            # SQLite doesn't support dropping columns easily
            print("SQLite detected. Column removal not supported.")
            print("The Spotify columns will remain but won't be used by the application.")
            print("This is harmless and won't affect functionality.")

if __name__ == "__main__":
    print("Removing Spotify integration columns...")
    remove_spotify_columns()
    print("Migration complete!")