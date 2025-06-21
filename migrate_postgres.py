#!/usr/bin/env python3
"""
PostgreSQL migration script to create all necessary tables.
This script is compatible with both SQLite and PostgreSQL.
"""

import os
from datetime import datetime
from sqlalchemy import create_engine, text
from pathlib import Path

# Get database URL from environment or use SQLite as fallback
DATABASE_URL = os.environ.get('DATABASE_URL')

# Handle Render's postgres:// URLs (convert to postgresql://)
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Default to SQLite if no DATABASE_URL is set
if not DATABASE_URL:
    ROOT_DIR = Path(__file__).resolve().parent
    DATABASE_URL = f"sqlite:///{ROOT_DIR}/spotify_playlists.db"

def create_tables():
    """Create all necessary tables for the application."""
    
    print(f"Connecting to database...")
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Create users table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(120) UNIQUE NOT NULL,
                name VARCHAR(100),
                password VARCHAR(128) NOT NULL,
                google_id VARCHAR(50) UNIQUE,
                is_active BOOLEAN DEFAULT TRUE,
                is_confirmed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                spotify_access_token TEXT,
                spotify_refresh_token TEXT,
                spotify_token_expires INTEGER,
                spotify_user_id VARCHAR(50),
                stripe_customer_id VARCHAR(255),
                subscription_id VARCHAR(255),
                subscription_status VARCHAR(50),
                subscription_plan VARCHAR(50),
                subscription_current_period_end TIMESTAMP
            )
        """))
        conn.commit()
        print("✓ Created users table")
        
        # Create user_sources table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_sources (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(200) NOT NULL,
                source_url TEXT NOT NULL,
                source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('channel', 'playlist')),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
        print("✓ Created user_sources table")
        
        # Create indexes for better performance
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sources_user_id ON user_sources(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sources_active ON user_sources(is_active)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)"))
        conn.commit()
        print("✓ Created indexes")
        
    print("Database migration completed successfully!")

if __name__ == "__main__":
    create_tables()