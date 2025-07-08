#!/usr/bin/env python3
"""
Migration to increase source_selection field size for Pro users.
Pro users can select multiple sources which requires more storage space.
"""

import os
import sys
from sqlalchemy import create_engine, text

# Add the parent directory to the path to import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config

def migrate():
    """Increase source_selection field size from VARCHAR(20) to TEXT."""
    # Get database URL from config
    database_url = Config.DATABASE_URL
    
    # Create engine
    engine = create_engine(database_url)
    
    print("Starting migration to increase source_selection field size...")
    
    try:
        with engine.connect() as conn:
            # PostgreSQL syntax for altering column type
            conn.execute(text("""
                ALTER TABLE playlist_tasks 
                ALTER COLUMN source_selection TYPE TEXT
            """))
            conn.commit()
            
        print("Migration completed successfully!")
        print("source_selection field changed from VARCHAR(20) to TEXT")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        engine.dispose()

if __name__ == "__main__":
    migrate()