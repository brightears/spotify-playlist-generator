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
        token_data = response.json()
        # Add expiration time
        token_data["expires_at"] = int(time.time()) + token_data["expires_in"]
        return token_data
    else:
        print(f"Error exchanging code for tokens: {response.status_code}")
        print(response.text)
        return None


def save_auth_data(auth_data):
    """Save authentication data to a file.
    
    Args:
        auth_data: Dict with token data
    """
    with open(AUTH_FILE_PATH, "w") as f:
        json.dump(auth_data, f)
    print(f"Authentication data saved to {AUTH_FILE_PATH}")


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
        token_data = response.json()
        # Add expiration time
        token_data["expires_at"] = int(time.time()) + token_data["expires_in"]
        # Keep the refresh token if not provided in the response
        if "refresh_token" not in token_data:
            token_data["refresh_token"] = refresh_token
        return token_data
    else:
        print(f"Error refreshing access token: {response.status_code}")
        print(response.text)
        return None


def get_valid_auth_data():
    """Get valid authentication data, refreshing the access token if necessary.
    
    Returns:
        Dict with valid token data or None if not available/refreshable
    """
    # Check if auth file exists
    if not AUTH_FILE_PATH.exists():
        print(f"Authentication file not found: {AUTH_FILE_PATH}")
        print("Please run the token exchange script first.")
        return None
    
    # Load auth data
    try:
        with open(AUTH_FILE_PATH, "r") as f:
            auth_data = json.load(f)
    except Exception as e:
        print(f"Error loading authentication data: {e}")
        return None
    
    # Check if access token is expired
    current_time = int(time.time())
    expires_at = auth_data.get("expires_at", 0)
    
    # If token expires in less than 60 seconds, refresh it
    if expires_at - current_time < 60:
        print("Access token expired or about to expire, refreshing...")
        refresh_token = auth_data.get("refresh_token")
        
        if not refresh_token:
            print("No refresh token found")
            return None
        
        # Refresh the token
        new_auth_data = refresh_access_token(refresh_token)
        
        if not new_auth_data:
            print("Failed to refresh access token")
            return None
        
        # Save the new auth data
        save_auth_data(new_auth_data)
        return new_auth_data
    
    return auth_data


def test_api_connection(auth_data):
    """Test the Spotify API connection with a simple request.
    
    Args:
        auth_data: Dict with token data
        
    Returns:
        True if connection successful, False otherwise
    """
    if not auth_data or "access_token" not in auth_data:
        return False
    
    headers = {
        "Authorization": f"Bearer {auth_data['access_token']}",
    }
    
    response = requests.get("https://api.spotify.com/v1/me", headers=headers)
    
    if response.status_code == 200:
        user_data = response.json()
        print(f"✅ Connected to Spotify as: {user_data['display_name']} ({user_data['id']})")
        return True
    else:
        print(f"❌ API connection failed: {response.status_code}")
        print(response.text)
        return False


def main():
    """Main function to exchange the code for tokens."""
    print("\n===== Spotify Token Exchange =====\n")
    
    # Check if credentials are set
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("❌ Error: Spotify credentials not found in .env file")
        print("Make sure SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET are set")
        return 1
    
    # Get the authorization code from command line argument
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
        print("python spotify_playlist.py --limit 25")
        return 0
    else:
        print("\n❌ Authentication failed - API connection test unsuccessful")
        return 1


if __name__ == "__main__":
    sys.exit(main())