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

echo "Build complete!"