#!/bin/bash
# Setup script for Spotify Playlist Generator

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create instance directory if it doesn't exist
if [ ! -d "instance" ]; then
    echo "Creating instance directory..."
    mkdir -p instance
fi

# Initialize the database if it doesn't exist
if [ ! -f "instance/app.db" ]; then
    echo "Initializing database..."
    FLASK_APP=app.py python -c "from app import create_app; from models import db; app = create_app(); app.app_context().push(); db.create_all()"
fi

echo "Setup complete! You can now run the application with:"
echo "flask run --host=127.0.0.1 --port=8080"