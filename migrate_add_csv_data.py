#!/usr/bin/env python3
"""Migration to add csv_data column to playlist_tasks table."""

import os
from dotenv import load_dotenv
load_dotenv()

from web_app import app, db
from sqlalchemy import text

def add_csv_data_column():
    """Add csv_data column to playlist_tasks table."""
    with app.app_context():
        try:
            # Check if column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='playlist_tasks' 
                AND column_name='csv_data'
            """))
            
            if result.rowcount > 0:
                print("Column csv_data already exists in playlist_tasks table")
                return
            
            # Add the column
            db.session.execute(text("""
                ALTER TABLE playlist_tasks 
                ADD COLUMN csv_data TEXT
            """))
            
            db.session.commit()
            print("Successfully added csv_data column to playlist_tasks table")
            
        except Exception as e:
            print(f"Error adding csv_data column: {e}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    add_csv_data_column()