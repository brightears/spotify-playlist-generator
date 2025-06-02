#!/bin/bash
# Setup script for Spotify Playlist Generator

# Install dependencies directly (for Codex environment)
echo "Installing dependencies directly..."
pip install flask flask-login flask-wtf flask-sqlalchemy flask-migrate flask-dance blinker sqlalchemy-utils pytest

# If requirements.txt exists, install from it as well
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
fi

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

echo "Setup complete!"