"""
Spotify OAuth utilities for multi-user authentication.
"""
import os
import base64
import json
import time
import requests
from flask import url_for, current_app, session
from urllib.parse import urlencode

class SpotifyOAuth:
    """
    Spotify OAuth for multi-user authentication.
    
    Instead of storing a single user's auth in a file, this handles
    OAuth for multiple users by storing tokens in the user database.
    """
    
    def __init__(self, client_id=None, client_secret=None, redirect_uri=None, scope=None):
        """Initialize SpotifyOAuth with credentials."""
        self.client_id = client_id or os.environ.get('SPOTIFY_CLIENT_ID')
        self.client_secret = client_secret or os.environ.get('SPOTIFY_CLIENT_SECRET')
        self.redirect_uri = redirect_uri or os.environ.get('SPOTIFY_REDIRECT_URI')
        self.scope = scope or 'playlist-modify-public playlist-modify-private'
        self.auth_url = 'https://accounts.spotify.com/authorize'
        self.token_url = 'https://accounts.spotify.com/api/token'
    
    def get_auth_url(self, state=None):
        """Get the authorization URL for user login."""
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'scope': self.scope,
            'show_dialog': True
        }
        
        if state:
            params['state'] = state
            
        auth_url = f"{self.auth_url}?{urlencode(params)}"
        return auth_url
    
    def get_auth_header(self):
        """Get the Basic Auth header for token requests."""
        auth_header = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        return {"Authorization": f"Basic {auth_header}"}
    
    def get_token(self, code):
        """Exchange authorization code for access and refresh tokens."""
        payload = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri
        }
        
        headers = self.get_auth_header()
        
        try:
            response = requests.post(self.token_url, data=payload, headers=headers)
            response.raise_for_status()
            token_info = response.json()
            
            # Add expiration time
            token_info['expires_at'] = int(time.time()) + token_info['expires_in']
            
            return token_info
        except requests.exceptions.HTTPError as e:
            current_app.logger.error(f"Error getting token: {e}")
            current_app.logger.error(f"Response: {response.text}")
            current_app.logger.error(f"Client ID: {self.client_id}")
            current_app.logger.error(f"Redirect URI: {self.redirect_uri}")
            raise e
        except Exception as e:
            current_app.logger.error(f"Unexpected error: {e}")
            return None
    
    def refresh_token(self, refresh_token):
        """Refresh an expired access token."""
        payload = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        
        headers = self.get_auth_header()
        
        try:
            response = requests.post(self.token_url, data=payload, headers=headers)
            response.raise_for_status()
            token_info = response.json()
            
            # Add expiration time
            token_info['expires_at'] = int(time.time()) + token_info['expires_in']
            
            # Add refresh token if not returned (Spotify doesn't always return it)
            if 'refresh_token' not in token_info:
                token_info['refresh_token'] = refresh_token
                
            return token_info
        except requests.exceptions.HTTPError as e:
            current_app.logger.error(f"Error refreshing token: {e}")
            current_app.logger.error(f"Response: {response.text}")
            return None
        except Exception as e:
            current_app.logger.error(f"Unexpected error: {e}")
            return None
    
    def get_authorized_headers(self, access_token):
        """Get headers with Bearer token for API requests."""
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }