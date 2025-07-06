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
    
    # Define allowed columns and their types
    SUBSCRIPTION_COLUMNS = {
        'stripe_customer_id': 'VARCHAR(255)',
        'subscription_id': 'VARCHAR(255)', 
        'subscription_status': 'VARCHAR(50)',
        'subscription_plan': 'VARCHAR(50)',
        'subscription_current_period_end': 'DATETIME'
    }
    
    OAUTH_COLUMNS = {
        'name': 'VARCHAR(100)',
        'google_id': 'VARCHAR(50)'
    }
    
    # Add missing subscription columns
    for column, column_type in SUBSCRIPTION_COLUMNS.items():
        if column not in columns:
            print(f"Adding column: {column}")
            # Whitelist approach - column names are hardcoded, only types are dynamic
            sql = f"ALTER TABLE users ADD COLUMN {column} {column_type}"
            cursor.execute(sql)
    
    # Add missing OAuth columns  
    for column, column_type in OAUTH_COLUMNS.items():
        if column not in columns:
            print(f"Adding column: {column}")
            sql = f"ALTER TABLE users ADD COLUMN {column} {column_type}"
            cursor.execute(sql)
            if column == 'google_id':
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)")
    
    # Create user_sources table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name VARCHAR(200) NOT NULL,
            source_url TEXT NOT NULL,
            source_type VARCHAR(20) NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    print("Created user_sources table")
    
    # Create index for better performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_sources_user_id ON user_sources(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_sources_active ON user_sources(is_active)")
    
    conn.commit()
    conn.close()
    print("Database migration completed successfully!")

if __name__ == "__main__":
    migrate_database()
