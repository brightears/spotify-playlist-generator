#!/usr/bin/env python
"""Spotify Token Exchange Script

This script exchanges an authorization code for access and refresh tokens
and saves them to a file for future use. It also provides functions to get
valid authentication data for API calls."""
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
AUTH_FILE_PATH = Path.home() / ".spotify_auth.json"
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
TOKEN_URL = "https://accounts.spotify.com/api/token"


def exchange_code_for_tokens(code):
    """Exchange the authorization code for access and refresh tokens.
    
    Args:
        code: The authorization code from Spotify
        
    Returns:
        Dict with token data or None if exchange failed
    """
    auth_header = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    ).decode()
    
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    
    response = requests.post(TOKEN_URL, headers=headers, data=data)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")
        return None


def refresh_access_token(refresh_token):
    """Refresh the access token using the refresh token.
    
    Args:
        refresh_token: The refresh token from Spotify
        
    Returns:
        Dict with new token data or None if refresh failed
    """
    auth_header = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    ).decode()
    
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    
    response = requests.post(TOKEN_URL, headers=headers, data=data)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Error refreshing token: {response.status_code} - {response.text}")
        return None


def save_auth_data(auth_data):
    """Save authentication data to a file.
    
    Args:
        auth_data: Dict with token data
    """
    # Add timestamp to know when the tokens were acquired
    auth_data["timestamp"] = int(time.time())
    
    # Save to file
    try:
        with open(AUTH_FILE_PATH, "w") as f:
            json.dump(auth_data, f, indent=2)
        print(f"✅ Saved authentication data to {AUTH_FILE_PATH}")
    except Exception as e:
        print(f"❌ Error saving authentication data: {e}")


def load_auth_data():
    """Load authentication data from file.
    
    Returns:
        Dict with token data or None if file doesn't exist or is invalid
    """
    try:
        if not AUTH_FILE_PATH.exists():
            print(f"❌ Authentication file not found: {AUTH_FILE_PATH}")
            return None
        
        with open(AUTH_FILE_PATH, "r") as f:
            auth_data = json.load(f)
        
        return auth_data
    except Exception as e:
        print(f"❌ Error loading authentication data: {e}")
        return None


def get_valid_auth_data():
    """Get valid authentication data, refreshing if necessary.
    
    Returns:
        Dict with valid token data or None if not available
    """
    auth_data = load_auth_data()
    
    if not auth_data:
        print("❌ No authentication data available")
        print("Please run 'python token_exchange.py YOUR_AUTH_CODE' to authenticate")
        return None
    
    # Check if the access token has expired (tokens last 1 hour)
    timestamp = auth_data.get("timestamp", 0)
    expires_in = auth_data.get("expires_in", 3600)
    current_time = int(time.time())
    
    # Refresh if token is expired or about to expire (within 5 minutes)
    if current_time >= timestamp + expires_in - 300:
        print("Token expired, refreshing...")
        
        refresh_token = auth_data.get("refresh_token")
        if not refresh_token:
            print("❌ No refresh token available")
            return None
        
        new_auth_data = refresh_access_token(refresh_token)
        
        if not new_auth_data:
            print("❌ Failed to refresh token")
            return None
        
        # Preserve the refresh token if it's not included in the response
        if "refresh_token" not in new_auth_data:
            new_auth_data["refresh_token"] = refresh_token
        
        # Update the timestamp
        new_auth_data["timestamp"] = current_time
        
        # Save the updated auth data
        save_auth_data(new_auth_data)
        
        return new_auth_data
    
    return auth_data


def test_api_connection(auth_data):
    """Test the Spotify API connection with the provided tokens.
    
    Args:
        auth_data: Dict with token data
        
    Returns:
        True if connection is successful, False otherwise
    """
    access_token = auth_data.get("access_token")
    
    if not access_token:
        print("❌ No access token available")
        return False
    
    headers = {
        "Authorization": f"Bearer {access_token}",
    }
    
    response = requests.get("https://api.spotify.com/v1/me", headers=headers)
    
    if response.status_code == 200:
        user_data = response.json()
        print(f"✅ Connected to Spotify API as {user_data.get('display_name')} ({user_data.get('id')})")
        return True
    else:
        print(f"❌ API connection test failed: {response.status_code} - {response.text}")
        return False


def main():
    """Main function."""
    # Check for Spotify credentials
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("❌ Error: Missing Spotify API credentials")
        print("Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your .env file")
        return 1
    
    # Get authorization code from command line argument
    if len(sys.argv) < 2:
        print("❌ Error: No authorization code provided")
        print("Usage: python token_exchange.py YOUR_AUTH_CODE")
        return 1
    
    authorization_code = sys.argv[1].strip()
    
    if not authorization_code:
        print("❌ Error: Empty authorization code")
        return 1
    
    # Exchange the code for tokens
    print("Exchanging authorization code for tokens...")
    auth_data = exchange_code_for_tokens(authorization_code)
    
    if not auth_data:
        print("❌ Failed to exchange code for tokens")
        return 1
    
    # Save the authentication data
    save_auth_data(auth_data)
    
    # Test the API connection
    if test_api_connection(auth_data):
        print("\n🎉 Authentication completed successfully! 🎉")
        print("\nYou can now run the playlist creation script:")
        print("python create_spotify_playlist.py --limit 25")
        print("or")
        print("python web_app.py")
        return 0
    else:
        print("\n❌ Authentication failed - API connection test unsuccessful")
        return 1


if __name__ == "__main__":
    sys.exit(main())