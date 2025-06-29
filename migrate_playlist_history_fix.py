#!/usr/bin/env python
"""Migration to fix GeneratedPlaylist table - make spotify fields nullable."""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

from web_app import app, db
from sqlalchemy import text

def fix_generated_playlist_columns():
    """Make spotify_url and spotify_id nullable in generated_playlists table."""
    with app.app_context():
        # Check if we're using PostgreSQL or SQLite
        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        is_postgres = 'postgresql' in db_url
        
        if is_postgres:
            # PostgreSQL syntax
            print("Updating GeneratedPlaylist columns in PostgreSQL database...")
            try:
                # Make columns nullable
                db.session.execute(text('ALTER TABLE generated_playlists ALTER COLUMN spotify_url DROP NOT NULL'))
                db.session.execute(text('ALTER TABLE generated_playlists ALTER COLUMN spotify_id DROP NOT NULL'))
                db.session.commit()
                print("✓ Updated spotify_url and spotify_id to be nullable")
                
            except Exception as e:
                print(f"Migration error: {e}")
                db.session.rollback()
        else:
            # SQLite doesn't support ALTER COLUMN easily
            print("SQLite detected. Cannot easily modify column constraints.")
            print("For development, you may need to recreate the table.")
            print("In production (PostgreSQL), run this migration.")

if __name__ == "__main__":
    print("Fixing GeneratedPlaylist table schema...")
    fix_generated_playlist_columns()
    print("Migration complete!")