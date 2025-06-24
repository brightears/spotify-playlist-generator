"""
Spotify OAuth and playlist creation routes.
"""
import os
import secrets
import asyncio
from flask import Blueprint, request, redirect, url_for, session, flash, jsonify, current_app
from flask_login import login_required, current_user
from utils.spotify_oauth import SpotifyOAuth
from utils.destinations.spotify import SpotifyDestination
from utils.sources.base import Track
from src.flasksaas.models import User, db
from src.flasksaas.main.task_manager import get_task

spotify_bp = Blueprint('spotify', __name__, url_prefix='/spotify')

def get_spotify_oauth():
    """Get configured SpotifyOAuth instance."""
    # Use environment variable for redirect URI, fallback to local development
    redirect_uri = os.environ.get('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:5000/spotify/callback')
    
    return SpotifyOAuth(
        client_id=os.environ.get('SPOTIFY_CLIENT_ID'),
        client_secret=os.environ.get('SPOTIFY_CLIENT_SECRET'),
        redirect_uri=redirect_uri,
        scope='playlist-modify-public playlist-modify-private user-read-private'
    )

@spotify_bp.route('/connect')
@login_required
def connect_account():
    """Initiate Spotify OAuth to connect user's account."""
    # Store state in session for after OAuth
    session['spotify_state'] = secrets.token_urlsafe(32)
    session['spotify_connect_only'] = True  # Flag to indicate this is just for connection
    
    # Get Spotify OAuth URL
    spotify_oauth = get_spotify_oauth()
    auth_url = spotify_oauth.get_auth_url(state=session['spotify_state'])
    
    # Debug logging
    print(f"DEBUG: Spotify OAuth Configuration (Account Connect):")
    print(f"  Client ID: {spotify_oauth.client_id[:10]}...{spotify_oauth.client_id[-10:] if len(spotify_oauth.client_id) > 20 else spotify_oauth.client_id}")
    print(f"  Redirect URI: {spotify_oauth.redirect_uri}")
    print(f"  Auth URL: {auth_url[:100]}...")
    
    return redirect(auth_url)

@spotify_bp.route('/connect/<task_id>')
@login_required
def connect(task_id):
    """Initiate Spotify OAuth for creating a playlist."""
    # Verify the task belongs to the current user
    task = get_task(task_id)
    if not task or task['user_id'] != current_user.id:
        flash('Task not found or unauthorized.', 'error')
        return redirect(url_for('main.dashboard'))
    
    if task['status'] != 'complete':
        flash('Playlist must be generated first.', 'error')
        return redirect(url_for('main.status', task_id=task_id))
    
    # Store task_id in session for after OAuth
    session['spotify_task_id'] = task_id
    session['spotify_state'] = secrets.token_urlsafe(32)
    
    # Get Spotify OAuth URL
    spotify_oauth = get_spotify_oauth()
    auth_url = spotify_oauth.get_auth_url(state=session['spotify_state'])
    
    # Debug logging
    print(f"DEBUG: Spotify OAuth Configuration:")
    print(f"  Client ID: {spotify_oauth.client_id[:10]}...{spotify_oauth.client_id[-10:] if len(spotify_oauth.client_id) > 20 else spotify_oauth.client_id}")
    print(f"  Redirect URI: {spotify_oauth.redirect_uri}")
    print(f"  Auth URL: {auth_url[:100]}...")
    
    return redirect(auth_url)

@spotify_bp.route('/callback')
@login_required
def callback():
    """Handle Spotify OAuth callback."""
    print(f"DEBUG: Spotify callback called")
    print(f"DEBUG: Request args: {dict(request.args)}")
    print(f"DEBUG: Session spotify_state: {session.get('spotify_state')}")
    
    # Verify state parameter
    state = request.args.get('state')
    if not state or state != session.get('spotify_state'):
        print(f"DEBUG: State mismatch - received: {state}, expected: {session.get('spotify_state')}")
        flash('Invalid OAuth state. Please try again.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Get authorization code
    code = request.args.get('code')
    error = request.args.get('error')
    
    print(f"DEBUG: Authorization code: {code[:10] + '...' if code else None}")
    print(f"DEBUG: Error: {error}")
    
    if error:
        flash(f'Spotify authorization failed: {error}', 'error')
        return redirect(url_for('main.dashboard'))
    
    if not code:
        flash('No authorization code received.', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        print("DEBUG: Exchanging code for tokens...")
        # Exchange code for tokens
        spotify_oauth = get_spotify_oauth()
        token_data = spotify_oauth.get_token(code)
        
        print(f"DEBUG: Token exchange successful")
        # Store tokens in user record
        current_user.spotify_access_token = token_data['access_token']
        current_user.spotify_refresh_token = token_data.get('refresh_token')
        current_user.spotify_token_expires = token_data.get('expires_in')
        db.session.commit()
        
        # Check if this was just a connection request or playlist creation
        if session.get('spotify_connect_only'):
            # Clean up session
            session.pop('spotify_connect_only', None)
            # Removed success flash - connection status is shown in dashboard
            return redirect(url_for('main.dashboard'))
        
        # Get the task to create playlist for
        task_id = session.get('spotify_task_id')
        print(f"DEBUG: Task ID from session: {task_id}")
        if task_id:
            return redirect(url_for('spotify.create_playlist', task_id=task_id))
        else:
            # Removed success flash - connection status is shown in dashboard
            return redirect(url_for('main.dashboard'))
            
    except Exception as e:
        print(f"Spotify OAuth error: {e}")
        flash('Failed to connect to Spotify. Please try again.', 'error')
        return redirect(url_for('main.dashboard'))

@spotify_bp.route('/create-playlist/<task_id>')
@login_required
def create_playlist(task_id):
    """Create the actual Spotify playlist."""
    # Verify task and user
    task = get_task(task_id)
    if not task or task['user_id'] != current_user.id:
        flash('Task not found or unauthorized.', 'error')
        return redirect(url_for('main.dashboard'))
    
    if not current_user.spotify_access_token:
        flash('Please connect to Spotify first.', 'error')
        return redirect(url_for('spotify.connect', task_id=task_id))
    
    async def create_spotify_playlist():
        """Async function to create the Spotify playlist."""
        try:
            print(f"DEBUG: Starting Spotify playlist creation for task {task_id}")
            
            # Create Spotify destination and authenticate
            spotify = SpotifyDestination()
            auth_success = await spotify.authenticate({
                'access_token': current_user.spotify_access_token,
                'refresh_token': current_user.spotify_refresh_token
            })
            
            print(f"DEBUG: Spotify authentication result: {auth_success}")
            
            if not auth_success:
                return None, 'Failed to authenticate with Spotify. Please reconnect.'
            
            # Create playlist
            tracks = task.get('tracks', [])
            playlist_name = task.get('playlist_name', 'Generated Playlist')
            description = f"Generated playlist with {len(tracks)} tracks from {task.get('genre', 'various')} genre"
            
            print(f"DEBUG: Creating playlist '{playlist_name}' with {len(tracks)} tracks")
            
            # Convert tracks to Track objects
            spotify_tracks = []
            for i, track in enumerate(tracks):
                track_obj = Track(
                    title=track['title'],
                    artist=track['artist'],
                    source=track.get('source', 'Generated'),
                    source_url=track.get('source_url', ''),
                    additional_info={
                        'album': track.get('album', ''),
                        'duration': track.get('duration', 0),
                        'genre': track.get('genre', '')
                    }
                )
                spotify_tracks.append(track_obj)
                
                # Debug first 3 tracks
                if i < 3:
                    print(f"DEBUG: Track {i+1}: '{track_obj.title}' by '{track_obj.artist}'")
            
            print(f"DEBUG: Converted {len(spotify_tracks)} tracks to Track objects")
            
            # Create the playlist
            result = await spotify.create_playlist(
                name=playlist_name,
                tracks=spotify_tracks,
                description=description,
                public=task.get('public', False)
            )
            
            print(f"DEBUG: Spotify playlist creation result: {result}")
            print(f"DEBUG: Result type: {type(result)}")
            if hasattr(result, 'success'):
                print(f"DEBUG: Success: {result.success}")
                print(f"DEBUG: Message: {getattr(result, 'message', 'No message')}")
                if hasattr(result, 'added_tracks'):
                    print(f"DEBUG: Added tracks: {len(result.added_tracks) if result.added_tracks else 0}")
                if hasattr(result, 'unmatched_tracks'):
                    print(f"DEBUG: Unmatched tracks: {len(result.unmatched_tracks) if result.unmatched_tracks else 0}")
            
            return result, None
            
        except Exception as e:
            print(f"DEBUG: Exception during Spotify playlist creation: {str(e)}")
            print(f"DEBUG: Exception type: {type(e).__name__}")
            import traceback
            print(f"DEBUG: Traceback: {traceback.format_exc()}")
            return None, str(e)
    
    try:
        # Run the async operation with timeout
        result, error = asyncio.run(asyncio.wait_for(create_spotify_playlist(), timeout=60.0))
        
        if error:
            flash(f'Failed to create Spotify playlist: {error}', 'error')
            return redirect(url_for('main.status', task_id=task_id))
        
        if result and result.success:
            # Update task with real Spotify URL
            task['result']['playlist_url'] = result.playlist_url
            task['result']['spotify_created'] = True
            task['result']['spotify_playlist_id'] = getattr(result, 'playlist_id', None)
            
            # Stay on our page with success message and link
            flash(f'Playlist "{task.get("playlist_name")}" created successfully on Spotify!', 'success')
            # Store the Spotify URL in session for the status page to show
            session['spotify_playlist_url'] = result.playlist_url
            return redirect(url_for('main.status', task_id=task_id))
        else:
            error_msg = getattr(result, 'message', 'Unknown error') if result else 'Unknown error'
            flash(f'Failed to create Spotify playlist: {error_msg}', 'error')
            return redirect(url_for('main.status', task_id=task_id))
            
    except asyncio.TimeoutError:
        print("DEBUG: Spotify playlist creation timed out after 60 seconds")
        flash('Spotify playlist creation timed out. Please try again.', 'error')
        return redirect(url_for('main.status', task_id=task_id))
    except Exception as e:
        print(f"Playlist creation error: {e}")
        flash('Failed to create Spotify playlist. Please try again.', 'error')
        return redirect(url_for('main.status', task_id=task_id))

@spotify_bp.route('/disconnect')
@login_required
def disconnect():
    """Disconnect user's Spotify account."""
    current_user.spotify_access_token = None
    current_user.spotify_refresh_token = None
    current_user.spotify_token_expires = None
    db.session.commit()
    
    flash('Spotify account disconnected.', 'success')
    return redirect(url_for('main.dashboard'))
