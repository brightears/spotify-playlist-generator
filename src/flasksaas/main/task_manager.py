"""
Task manager for handling playlist creation tasks.
"""
import time
import asyncio
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
import uuid
import logging

# Import the real playlist generation functionality
from utils.sources.youtube import YouTubeSource
from utils.destinations.spotify import SpotifyDestination
from playlist_generator import create_playlist
from src.flasksaas.models import User, UserSource

# Configure logging
logger = logging.getLogger(__name__)

# In-memory task storage (in production, use Redis or database)
tasks: Dict[str, Dict[str, Any]] = {}

class TaskManager:
    def __init__(self):
        self.youtube_source = YouTubeSource()
    
    async def create_playlist_task(self, genre: str, track_count: int, progress_callback=None) -> Dict:
        """Create a playlist by fetching real tracks from YouTube."""
        try:
            logger.info(f"Starting playlist creation task for genre: {genre}, track count: {track_count}")
            
            # Check if API keys are available
            import os
            youtube_api_key = os.environ.get("YOUTUBE_API_KEY")
            spotify_client_id = os.environ.get("SPOTIFY_CLIENT_ID")
            
            if not youtube_api_key or not spotify_client_id:
                return await self._create_demo_playlist(genre, track_count, progress_callback)
            
            # Update progress
            if progress_callback:
                progress_callback({
                    'status': 'running',
                    'progress': 10,
                    'message': 'Connecting to YouTube API...'
                })
            
            # Fetch real tracks from YouTube
            logger.info(f"Fetching {track_count} tracks from YouTube for genre: {genre}")
            tracks = await self.youtube_source.get_tracks(
                days_to_look_back=30,  # Look back 30 days for fresh content
                genre=genre,
                limit=track_count
            )
            
            if progress_callback:
                progress_callback({
                    'status': 'running',
                    'progress': 50,
                    'message': f'Found {len(tracks)} tracks from YouTube sources...'
                })
            
            # Convert Track objects to dict format for compatibility
            track_dicts = []
            for track in tracks:
                track_dict = {
                    'title': track.title,
                    'artist': track.artist,
                    'remix': track.remix,
                    'source': track.source,
                    'source_url': track.source_url,
                    'duration': "3:30",  # Default duration since YouTube API doesn't provide this easily
                    'youtube_id': track.source_url.split('v=')[-1] if 'v=' in track.source_url else None
                }
                track_dicts.append(track_dict)
            
            if progress_callback:
                progress_callback({
                    'status': 'running',
                    'progress': 80,
                    'message': 'Processing track metadata...'
                })
            
            # Get source information
            sources = self._get_genre_sources(genre)
            
            result = {
                'status': 'completed',
                'tracks': track_dicts,
                'sources': sources,
                'total_tracks': len(track_dicts),
                'genre': genre
            }
            
            if progress_callback:
                progress_callback({
                    'status': 'completed',
                    'progress': 100,
                    'message': f'Successfully fetched {len(track_dicts)} real tracks from YouTube!',
                    'result': result
                })
            
            logger.info(f"Playlist creation completed. Found {len(track_dicts)} tracks.")
            return result
            
        except Exception as e:
            logger.error(f"Error in playlist creation task: {e}", exc_info=True)
            error_result = {
                'status': 'error',
                'error': str(e),
                'tracks': [],
                'sources': [],
                'total_tracks': 0,
                'genre': genre
            }
            
            if progress_callback:
                progress_callback({
                    'status': 'error',
                    'progress': 0,
                    'message': f'Error fetching tracks: {str(e)}',
                    'result': error_result
                })
            
            return error_result

    def _get_genre_sources(self, genre: str) -> List[Dict]:
        """Get the YouTube sources for a given genre (instance method)."""
        return get_genre_sources(genre)

def get_genre_sources(genre: str, user_id: Optional[int] = None, include_predefined: bool = True, include_custom: bool = True) -> List[Dict]:
    """Get the YouTube sources for a given genre, optionally including user custom sources."""
    sources = []
    
    # Add predefined sources if requested
    if include_predefined:
        youtube_source = YouTubeSource()
        genre_channels = youtube_source.GENRE_CHANNELS.get(genre, youtube_source.GENRE_CHANNELS.get("all", []))
        
        for channel in genre_channels:
            sources.append({
                'id': channel['id'],
                'name': channel['name'],
                'type': channel['type'],
                'custom': False
            })
    
    # Add user custom sources if requested and user has subscription
    if include_custom and user_id:
        try:
            user = User.query.get(user_id)
            if user and user.has_active_subscription:
                custom_sources = UserSource.query.filter_by(
                    user_id=user_id, 
                    is_active=True
                ).all()
                
                for custom_source in custom_sources:
                    # Parse the URL to extract the ID
                    source_id = extract_youtube_id(custom_source.source_url)
                    if source_id:
                        sources.append({
                            'id': source_id,
                            'name': custom_source.name,
                            'type': custom_source.source_type,
                            'custom': True,
                            'url': custom_source.source_url
                        })
        except Exception as e:
            logger.error(f"Error fetching custom sources for user {user_id}: {e}")
    
    return sources


def extract_youtube_id(url: str) -> Optional[str]:
    """Extract YouTube channel or playlist ID from URL."""
    try:
        # Playlist patterns
        playlist_patterns = [
            r'(?:youtube\.com/playlist\?list=|youtu\.be/playlist\?list=)([a-zA-Z0-9_-]+)',
        ]
        
        # Channel patterns
        channel_patterns = [
            r'youtube\.com/channel/([a-zA-Z0-9_-]+)',
            r'youtube\.com/c/([a-zA-Z0-9_-]+)',
            r'youtube\.com/@([a-zA-Z0-9_-]+)',
            r'youtube\.com/user/([a-zA-Z0-9_-]+)',
        ]
        
        # Check playlist patterns first
        for pattern in playlist_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # Check channel patterns
        for pattern in channel_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    except Exception as e:
        logger.error(f"Error extracting YouTube ID from URL {url}: {e}")
        return None

def create_new_task(user_id: int, playlist_name: str, description: str, genre: str, days: int, public: bool, source_selection: str = 'both') -> str:
    """Create a new playlist generation task."""
    task_id = str(uuid.uuid4())
    
    task = {
        'id': task_id,
        'user_id': user_id,
        'status': 'processing',
        'progress': 0,
        'message': 'Initializing playlist creation...',
        'step': 0,
        'created_at': datetime.now(),
        'last_updated': datetime.now(),
        'result': None,
        'error': None,
        # Store playlist parameters
        'playlist_name': playlist_name,
        'description': description,
        'genre': genre,
        'days': days,
        'public': public,
        'source_selection': source_selection
    }
    
    tasks[task_id] = task
    print(f"Created new task {task_id} for user {user_id}")
    return task_id

def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Get a task by ID."""
    return tasks.get(task_id)

def get_user_tasks(user_id: int) -> list:
    """Get all tasks for a user."""
    return [task for task in tasks.values() if task['user_id'] == user_id]

async def process_task_step(task_id: str) -> bool:
    """Process one step of the task. Returns True if task was updated."""
    task = tasks.get(task_id)
    if not task:
        return False
    
    # Allow both 'processing' and 'running' status
    if task['status'] not in ['processing', 'running']:
        return False
    
    # Change status to running when we start processing
    if task['status'] == 'processing':
        task['status'] = 'running'
    
    current_step = task.get('step', 0)
    
    try:
        if current_step == 0:
            # Initialize task
            print(f"Task {task_id}: Starting initialization (step 0)")
            task['message'] = 'Initializing playlist creation...'
            task['progress'] = 10
            # Get source selection preference
            source_selection = task.get('source_selection', 'both')
            include_predefined = source_selection in ['both', 'predefined']
            include_custom = source_selection in ['both', 'custom']
            
            task['sources'] = get_genre_sources(
                task['genre'], 
                user_id=task.get('user_id'),
                include_predefined=include_predefined,
                include_custom=include_custom
            )
            task['step'] = 1
            print(f"Task {task_id}: Initialization complete, moving to step 1. Found {len(task['sources'])} sources for genre {task['genre']}")
            
        elif current_step == 1:
            # Fetch tracks from YouTube
            genre = task['genre']
            days = task['days']
            task['message'] = f'Fetching tracks from YouTube for genre: {genre}...'
            task['progress'] = 30
            print(f"Task {task_id}: Starting YouTube track fetching for genre {genre}")
            
            try:
                # Initialize YouTube source
                youtube_source = YouTubeSource()
                
                # Get sources based on user's selection
                user_id = task.get('user_id')
                source_selection = task.get('source_selection', 'both')
                include_predefined = source_selection in ['both', 'predefined']
                include_custom = source_selection in ['both', 'custom']
                
                custom_sources = get_genre_sources(
                    genre, 
                    user_id=user_id, 
                    include_predefined=include_predefined, 
                    include_custom=include_custom
                )
                
                # Fetch tracks from YouTube using both predefined and custom sources
                tracks = await youtube_source.get_tracks_from_sources(
                    sources=custom_sources,
                    days_to_look_back=days,
                    limit=50  # Get 50 tracks instead of just 3
                )
                
                # Convert Track objects to dictionaries for JSON serialization
                track_dicts = []
                for track in tracks:
                    track_dict = {
                        'title': track.title,
                        'artist': track.artist,
                        'duration': getattr(track, 'duration', 'Unknown'),
                        'source': getattr(track, 'source', 'YouTube'),
                        'genre': genre,
                        'url': getattr(track, 'url', None),
                        'remix': getattr(track, 'remix', None)
                    }
                    track_dicts.append(track_dict)
                
                task['tracks'] = track_dicts
                task['step'] = 2
                task['progress'] = 50
                task['message'] = f'Fetched {len(track_dicts)} tracks from YouTube for genre {genre}'
                print(f"Task {task_id}: Successfully fetched {len(track_dicts)} tracks")
                
            except Exception as e:
                print(f"Task {task_id}: Error in step 1: {e}")
                import traceback
                traceback.print_exc()
                task['status'] = 'error'
                task['message'] = f'Failed to fetch tracks from YouTube: {str(e)}'
                raise e
            
        elif current_step == 2:
            # Complete the task - don't automatically create Spotify playlist
            tracks = task.get('tracks', [])
            task['status'] = 'complete'
            task['progress'] = 100
            task['message'] = f'Successfully fetched {len(tracks)} tracks from YouTube!'
            
            # Generate CSV data for download
            import csv
            import io
            csv_buffer = io.StringIO()
            csv_writer = csv.writer(csv_buffer)
            csv_writer.writerow(['Title', 'Artist', 'Remix', 'Source', 'URL'])
            
            for track in tracks:
                csv_writer.writerow([
                    track.get('title', ''),
                    track.get('artist', ''),
                    track.get('remix', ''),
                    track.get('source', ''),
                    track.get('url', track.get('source_url', ''))
                ])
            
            task['csv_data'] = csv_buffer.getvalue()
            
            # Create result without Spotify info
            task['result'] = {
                'playlist_name': task['playlist_name'],
                'playlist_url': None,
                'spotify_created': False,
                'track_count': len(tracks),
                'matched_tracks': 0,
                'unmatched_tracks': 0,
                'tracks': tracks[:10],  # Show first 10 tracks
                'sources_used': [source['name'] for source in task.get('sources', [])],
                'genre': task['genre'],
                'days_searched': task['days']
            }
            task['step'] = 3  # Mark as complete
            
        elif current_step == 3:
            # Connect to Spotify  
            task['message'] = 'Connecting to Spotify API...'
            task['progress'] = 80
            
            try:
                # Get user's Spotify authentication from session
                user_id = task.get('user_id')
                user = User.query.get(user_id)
                if not user:
                    raise ValueError(f"User {user_id} not found")
                
                # Check if user has Spotify tokens
                if not user.spotify_access_token:
                    raise ValueError("User has not connected Spotify account")
                
                # Prepare auth data for Spotify destination
                auth_data = {
                    'access_token': user.spotify_access_token,
                    'refresh_token': user.spotify_refresh_token,
                    'expires_at': user.spotify_token_expires,
                    'user_id': user.spotify_user_id
                }
                
                # Initialize Spotify destination
                spotify_destination = SpotifyDestination()
                
                # Authenticate with user's tokens
                auth_success = await spotify_destination.authenticate(auth_data)
                if not auth_success:
                    raise ValueError("Failed to authenticate with Spotify")
                
                # If tokens were refreshed, update the database
                if spotify_destination.auth_data != auth_data:
                    print(f"Task {task_id}: Tokens were refreshed, updating database...")
                    user.spotify_access_token = spotify_destination.auth_data.get('access_token')
                    user.spotify_refresh_token = spotify_destination.auth_data.get('refresh_token')
                    user.spotify_token_expires = spotify_destination.auth_data.get('expires_at')
                    from src.flasksaas.models import db
                    db.session.commit()
                    print(f"Task {task_id}: Database updated with new tokens")
                
                task['spotify_destination'] = spotify_destination
                task['step'] = 4
                print(f"Task {task_id}: Spotify destination initialized")
                
            except Exception as e:
                print(f"Task {task_id}: Error in step 3: {e}")
                task['status'] = 'error'
                task['message'] = f'Failed to connect to Spotify: {str(e)}'
                raise e
            
        elif current_step == 4:
            # Create Spotify playlist
            task['message'] = f'Creating Spotify playlist "{task["playlist_name"]}"...'
            task['progress'] = 90
            
            try:
                spotify_destination = task.get('spotify_destination')
                if not spotify_destination:
                    raise ValueError("Spotify destination not initialized")
                
                # Convert track dictionaries back to Track objects
                tracks = task.get('tracks', [])
                track_objects = []
                for track_dict in tracks:
                    from utils.sources.base import Track
                    track_obj = Track(
                        title=track_dict['title'],
                        artist=track_dict['artist'],
                        remix=track_dict.get('remix'),
                        source=track_dict.get('source', 'YouTube'),
                        source_url=track_dict.get('url')
                    )
                    track_objects.append(track_obj)
                
                # Create the playlist on Spotify
                playlist_result = await spotify_destination.create_playlist(
                    name=task['playlist_name'],
                    tracks=track_objects,
                    description=f"Playlist created from YouTube sources - Genre: {task['genre']}",
                    public=task.get('public', False),
                    min_match_score=0.7,
                    progress_callback=None  # Don't use callback for now to avoid await issues
                )
                
                if playlist_result.success:
                    task['spotify_playlist_url'] = playlist_result.playlist_url
                    task['matched_tracks'] = len(playlist_result.added_tracks)
                    task['unmatched_tracks'] = len(playlist_result.unmatched_tracks)
                    task['csv_data'] = playlist_result.csv_data
                    task['step'] = 5
                    print(f"Task {task_id}: Spotify playlist created successfully")
                    print(f"Task {task_id}: Matched {len(playlist_result.added_tracks)} tracks, {len(playlist_result.unmatched_tracks)} unmatched")
                    
                    # Log some match details for debugging
                    for i, match in enumerate(playlist_result.added_tracks[:5]):  # First 5 matches
                        print(f"Task {task_id}: Match {i+1}: '{match.track.title}' by '{match.track.artist}' -> '{match.match_name}' by '{match.match_artist}' (score: {match.score:.2f})")
                    
                    if playlist_result.unmatched_tracks:
                        print(f"Task {task_id}: Unmatched tracks:")
                        for i, match in enumerate(playlist_result.unmatched_tracks[:3]):  # First 3 unmatched
                            print(f"Task {task_id}: Unmatched {i+1}: '{match.track.title}' by '{match.track.artist}' (best score: {match.score:.2f})")
                else:
                    raise ValueError(f"Failed to create Spotify playlist: {playlist_result.message}")
                
            except Exception as e:
                print(f"Task {task_id}: Error in step 4: {e}")
                task['status'] = 'error'
                task['message'] = f'Failed to create Spotify playlist: {str(e)}'
                raise e
            
        elif current_step == 5:
            # Finalize and complete
            task['message'] = 'Finalizing playlist...'
            task['progress'] = 95
            task['step'] = 6
            
        elif current_step == 6:
            # Complete the task
            tracks = task.get('tracks', [])
            task['status'] = 'complete'
            task['progress'] = 100
            task['message'] = 'Playlist created successfully!'
            
            # Create realistic result
            task['result'] = {
                'playlist_name': task['playlist_name'],
                'playlist_url': task.get('spotify_playlist_url'),
                'spotify_created': bool(task.get('spotify_playlist_url')),
                'track_count': len(tracks),
                'matched_tracks': task.get('matched_tracks', 0),
                'unmatched_tracks': task.get('unmatched_tracks', 0),
                'tracks': tracks[:10],  # Show first 10 tracks
                'sources_used': [source['name'] for source in task.get('sources', [])],
                'genre': task['genre'],
                'days_searched': task['days']
            }
            
        else:
            # Unknown step, reset to beginning
            print(f"Unknown step {current_step} for task {task_id}, resetting to step 0")
            task['step'] = 0
            return False
            
        task['last_updated'] = datetime.now()
        print(f"Task {task_id} updated: step {task['step']}, progress {task['progress']}%, message: {task['message']}")
        return True
        
    except Exception as e:
        print(f"Error processing task {task_id}: {e}")
        task['status'] = 'error'
        task['message'] = f'Error: {str(e)}'
        task['error'] = str(e)
        task['last_updated'] = datetime.now()
        return True

def cleanup_old_tasks():
    """Remove tasks older than 1 hour."""
    cutoff = datetime.now() - timedelta(hours=1)
    to_remove = [task_id for task_id, task in tasks.items() 
                 if task['created_at'] < cutoff]
    
    for task_id in to_remove:
        del tasks[task_id]
        print(f"Cleaned up old task {task_id}")
