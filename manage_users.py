#!/usr/bin/env python3
"""
User management script for production database.
Run this with appropriate DATABASE_URL to manage users.
"""

import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

def get_db_connection():
    """Get database connection."""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Usage: DATABASE_URL=postgresql://... python manage_users.py [command]")
        sys.exit(1)
    
    # Handle Render's postgres:// URLs
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    return create_engine(database_url)

def list_users():
    """List all users in the database."""
    engine = get_db_connection()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, email, name, subscription_status, subscription_plan, 
                   subscription_current_period_end, created_at
            FROM users
            ORDER BY created_at DESC
        """))
        
        users = result.fetchall()
        
        if not users:
            print("No users found in database")
            return
        
        print(f"\nFound {len(users)} users:")
        print("-" * 100)
        
        for user in users:
            print(f"ID: {user[0]}")
            print(f"Email: {user[1]}")
            print(f"Name: {user[2] or 'Not set'}")
            print(f"Subscription: {user[3] or 'None'} ({user[4] or 'N/A'})")
            if user[5]:
                print(f"Expires: {user[5]}")
            print(f"Created: {user[6]}")
            print("-" * 100)

def grant_subscription(email, days=30):
    """Grant a test subscription to a user."""
    engine = get_db_connection()
    
    with engine.connect() as conn:
        # Check if user exists
        result = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email})
        user = result.fetchone()
        
        if not user:
            print(f"User with email {email} not found!")
            return
        
        # Grant subscription
        end_date = datetime.utcnow() + timedelta(days=days)
        
        conn.execute(text("""
            UPDATE users 
            SET subscription_status = 'active',
                subscription_plan = 'monthly',
                subscription_current_period_end = :end_date
            WHERE email = :email
        """), {"email": email, "end_date": end_date})
        
        conn.commit()
        print(f"✓ Granted {days}-day subscription to {email}")
        print(f"  Valid until: {end_date}")

def remove_subscription(email):
    """Remove subscription from a user."""
    engine = get_db_connection()
    
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE users 
            SET subscription_status = NULL,
                subscription_plan = NULL,
                subscription_current_period_end = NULL
            WHERE email = :email
        """), {"email": email})
        
        conn.commit()
        print(f"✓ Removed subscription from {email}")

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python manage_users.py [command] [args]")
        print("\nCommands:")
        print("  list                     - List all users")
        print("  grant <email> [days]     - Grant subscription (default 30 days)")
        print("  remove <email>           - Remove subscription")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "list":
        list_users()
    elif command == "grant":
        if len(sys.argv) < 3:
            print("Error: Email required")
            sys.exit(1)
        email = sys.argv[2]
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        grant_subscription(email, days)
    elif command == "remove":
        if len(sys.argv) < 3:
            print("Error: Email required")
            sys.exit(1)
        remove_subscription(sys.argv[2])
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()