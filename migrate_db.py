#!/usr/bin/env python3
"""
Database migration script to add subscription fields to existing users table.
"""

import sqlite3
import os
from pathlib import Path

# Get the database path
ROOT_DIR = Path(__file__).resolve().parent
DB_PATH = ROOT_DIR / "spotify_playlists.db"

def migrate_database():
    """Add subscription and OAuth columns to users table if they don't exist."""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if subscription columns already exist
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    
    subscription_columns = [
        'stripe_customer_id',
        'subscription_id', 
        'subscription_status',
        'subscription_plan',
        'subscription_current_period_end'
    ]
    
    oauth_columns = [
        'name',
        'google_id'
    ]
    
    # Add missing subscription columns
    for column in subscription_columns:
        if column not in columns:
            print(f"Adding column: {column}")
            if column == 'subscription_current_period_end':
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column} DATETIME")
            else:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column} VARCHAR(255)")
    
    # Add missing OAuth columns
    for column in oauth_columns:
        if column not in columns:
            print(f"Adding column: {column}")
            if column == 'name':
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column} VARCHAR(100)")
            elif column == 'google_id':
                # Add without UNIQUE constraint first, then add index separately
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column} VARCHAR(50)")
                cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users({column})")
    
    conn.commit()
    conn.close()
    print("Database migration completed successfully!")

if __name__ == "__main__":
    migrate_database()
