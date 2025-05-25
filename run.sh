#!/bin/bash
# Simple script to run the Spotify Playlist Generator web app

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install or update dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists, create from example if not
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo "⚠️ Please edit .env file to add your API credentials! ⚠️"
fi

# Run the application
echo "Starting web application..."
python web_app.py

# Deactivate virtual environment on exit
deactivate