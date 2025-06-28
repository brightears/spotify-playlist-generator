#!/usr/bin/env python
"""Database migration to add playlist tracking tables."""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

from web_app import app, db
from src.flasksaas.models import PlaylistTask, GeneratedPlaylist

def create_playlist_tables():
    """Create the new playlist tracking tables."""
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        print("Successfully created playlist tracking tables:")
        print("- playlist_tasks")
        print("- generated_playlists")
        
        # Verify tables exist
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'playlist_tasks' in tables:
            print("✓ playlist_tasks table created successfully")
        else:
            print("✗ Failed to create playlist_tasks table")
            
        if 'generated_playlists' in tables:
            print("✓ generated_playlists table created successfully")
        else:
            print("✗ Failed to create generated_playlists table")

if __name__ == "__main__":
    print("Creating playlist tracking tables...")
    create_playlist_tables()
    print("Migration complete!")