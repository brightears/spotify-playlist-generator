#!/usr/bin/env bash
# Build script for Render deployment

echo "Starting build process..."

# Install dependencies
pip install -r requirements.txt

# Initialize database
echo "Initializing database..."
python db_init.py

# Run any migrations
if [ -f "migrate_db.py" ]; then
    echo "Running database migrations..."
    python migrate_db.py
fi

# Run PostgreSQL migrations if DATABASE_URL is set
if [ ! -z "$DATABASE_URL" ] && [ -f "migrate_postgres.py" ]; then
    echo "Running PostgreSQL migrations..."
    python migrate_postgres.py
fi

echo "Build complete!"