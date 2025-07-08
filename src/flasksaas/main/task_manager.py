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
from src.flasksaas.models import User, UserSource, PlaylistTask, GeneratedPlaylist
from src.flasksaas import db
import gzip
import base64

# Configure logging
logger = logging.getLogger(__name__)

# In-memory task storage (in production, use Redis or database)
tasks: Dict[str, Dict[str, Any]] = {}

def update_task_status(task_id: str, status: str = None, progress: int = None, message: str = None, **kwargs):
    """Update task status in both memory and database."""
    # Update in-memory
    if task_id in tasks:
        task = tasks[task_id]
        if status is not None:
            task['status'] = status
        if progress is not None:
            task['progress'] = progress
        if message is not None:
            task['message'] = message
        task['last_updated'] = datetime.now()
        
        # Update any additional fields
        for key, value in kwargs.items():
            task[key] = value
    
    # Update in database
    db_task = PlaylistTask.query.get(task_id)
    if db_task:
        if status is not None:
            db_task.status = status
        if progress is not None:
            db_task.progress = progress
        if status in ['completed', 'complete']:
            db_task.completed_at = datetime.utcnow()
        elif status == 'failed' and 'error' in kwargs:
            db_task.error_message = str(kwargs['error'])
        
        # Update results if provided
        if 'spotify_playlist_url' in kwargs:
            db_task.spotify_playlist_url = kwargs['spotify_playlist_url']
        if 'spotify_playlist_id' in kwargs:
            db_task.spotify_playlist_id = kwargs['spotify_playlist_id']
        if 'tracks_found' in kwargs:
            db_task.tracks_found = kwargs['tracks_found']
        if 'tracks_matched' in kwargs:
            db_task.tracks_matched = kwargs['tracks_matched']
            
        db.session.commit()

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


def get_selected_sources(genre: str, user_id: int, selected_source_ids: List[str]) -> List[Dict]:
    """Get sources based on Pro user's checkbox selections."""
    sources = []
    
    try:
        # Process each selected source
        for source_id in selected_source_ids:
            if source_id.startswith('preset_'):
                # Handle preset sources
                playlist_id = source_id.replace('preset_', '')
                youtube_source = YouTubeSource()
                
                # Check all available sources across all genres
                found = False
                # First check the "all" genre
                all_channels = youtube_source.GENRE_CHANNELS.get("all", [])
                for channel in all_channels:
                    if channel['id'] == playlist_id:
                        sources.append({
                            'id': channel['id'],
                            'name': channel['name'],
                            'type': channel['type'],
                            'custom': False
                        })
                        found = True
                        break
                
                # If not found in "all", check all other genres
                if not found:
                    for genre_key, genre_channels in youtube_source.GENRE_CHANNELS.items():
                        for channel in genre_channels:
                            if channel['id'] == playlist_id:
                                sources.append({
                                    'id': channel['id'],
                                    'name': channel['name'],
                                    'type': channel['type'],
                                    'custom': False
                                })
                                found = True
                                break
                        if found:
                            break
                
                # Log if we couldn't find the preset source
                if not found:
                    logger.warning(f"Preset source with ID '{playlist_id}' not found in any genre")
                        
            elif source_id.startswith('custom_'):
                # Handle custom sources
                custom_id = int(source_id.replace('custom_', ''))
                custom_source = UserSource.query.filter_by(
                    id=custom_id,
                    user_id=user_id,
                    is_active=True
                ).first()
                
                if custom_source:
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
        logger.error(f"Error processing selected sources: {e}", exc_info=True)
        # Continue processing other sources even if one fails
    
    # Log summary
    logger.info(f"Processed {len(selected_source_ids)} selected sources, found {len(sources)} valid sources")
    
    return sources


def extract_youtube_id(url: str) -> Optional[str]:
    """Extract YouTube channel or playlist ID from URL."""
    try:
        # For @username format, extract just the username
        if '@' in url:
            # Extract username from various URL formats
            # e.g., youtube.com/@MrRevillz/videos?view=0 -> MrRevillz
            match = re.search(r'@([^/?\s]+)', url)
            if match:
                return f"@{match.group(1)}"  # Return @username format
            return url  # Fallback to full URL
        
        # Playlist patterns
        playlist_patterns = [
            r'(?:youtube\.com/playlist\?list=|youtu\.be/playlist\?list=)([a-zA-Z0-9_-]+)',
        ]
        
        # Channel patterns
        channel_patterns = [
            r'youtube\.com/channel/([a-zA-Z0-9_-]+)',
            r'youtube\.com/c/([a-zA-Z0-9_-]+)',
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
        
        return url  # Return the full URL as fallback
    except Exception as e:
        logger.error(f"Error extracting YouTube ID from URL {url}: {e}")
        return None

def create_new_task(user_id: int, playlist_name: str, description: str, genre: str, days: int, public: bool, source_selection: str = 'both') -> str:
    """Create a new playlist generation task."""
    task_id = str(uuid.uuid4())
    
    try:
        # Create database entry
        db_task = PlaylistTask(
            id=task_id,
            user_id=user_id,
            status='processing',
            progress=0,
            playlist_name=playlist_name,
            description=description,
            genre=genre,
            days=days,
            is_public=public,
            source_selection=source_selection
        )
        db.session.add(db_task)
        db.session.commit()
    except Exception as e:
        logger.error(f"Error creating task in database: {e}")
        db.session.rollback()
        # Try again with a fresh session
        try:
            db.session.add(db_task)
            db.session.commit()
        except Exception as e2:
            logger.error(f"Second attempt failed: {e2}")
            raise
    
    # Also maintain in-memory for backward compatibility
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
    """Get a task by ID, checking both memory and database."""
    # First check in-memory cache
    if task_id in tasks:
        return tasks[task_id]
    
    # If not in memory, check database
    db_task = PlaylistTask.query.get(task_id)
    if db_task:
        # Reconstruct task dict from database
        task = {
            'id': db_task.id,
            'user_id': db_task.user_id,
            'status': db_task.status,
            'progress': db_task.progress or 0,
            'message': f'Task status: {db_task.status}',
            'step': 0,  # Default step value
            'created_at': db_task.created_at,
            'last_updated': db_task.created_at,
            'result': None,
            'error': db_task.error_message,
            'playlist_name': db_task.playlist_name,
            'description': db_task.description,
            'genre': db_task.genre,
            'days': db_task.days,
            'public': db_task.is_public,
            'source_selection': db_task.source_selection or 'both'
        }
        
        # If task is completed, try to get the result
        if db_task.status == 'completed' and db_task.tracks_found:
            task['result'] = {
                'tracks_found': db_task.tracks_found,
                'playlist_url': db_task.spotify_playlist_url
            }
        
        # Cache it in memory for future requests
        tasks[task_id] = task
        return task
    
    return None

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
            
            # Check if source_selection is a list (Pro user with checkboxes)
            if isinstance(source_selection, list):
                # Pro user with selected sources
                task['sources'] = get_selected_sources(
                    task['genre'], 
                    user_id=task.get('user_id'),
                    selected_source_ids=source_selection
                )
            else:
                # Regular user or old format
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
                
                # Check if source_selection is a list (Pro user with checkboxes)
                if isinstance(source_selection, list):
                    # Pro user with selected sources
                    custom_sources = get_selected_sources(
                        genre, 
                        user_id=user_id,
                        selected_source_ids=source_selection
                    )
                else:
                    # Regular user or old format
                    include_predefined = source_selection in ['both', 'predefined']
                    include_custom = source_selection in ['both', 'custom']
                    
                    custom_sources = get_genre_sources(
                        genre, 
                        user_id=user_id, 
                        include_predefined=include_predefined, 
                        include_custom=include_custom
                    )
                
                # Fetch tracks from YouTube sources in parallel batches for speed
                tracks = []
                total_sources = len(custom_sources)
                
                # Dynamic batch size: more sources = larger batches
                if total_sources <= 3:
                    batch_size = total_sources  # Process all at once if few sources
                elif total_sources <= 10:
                    batch_size = 3  # Process 3 at a time for medium counts
                else:
                    batch_size = 5  # Process 5 at a time for many sources
                
                # Process sources in parallel batches
                for batch_start in range(0, total_sources, batch_size):
                    batch_end = min(batch_start + batch_size, total_sources)
                    batch = custom_sources[batch_start:batch_end]
                    
                    # Update progress with source names
                    progress_percent = 30 + int((batch_start / total_sources) * 40)  # 30-70% range
                    source_names = [s['name'] for s in batch]
                    if len(source_names) > 1:
                        task['message'] = f'Processing {", ".join(source_names[:2])}... ({batch_end}/{total_sources} sources)'
                    else:
                        task['message'] = f'Processing {source_names[0]}... ({batch_end}/{total_sources} sources)'
                    task['progress'] = progress_percent
                    update_task_status(task_id, progress=progress_percent, message=task['message'])
                    
                    # Create tasks for parallel execution
                    batch_tasks = []
                    for source in batch:
                        # Same limit for all sources
                        tracks_per_source = 100
                        
                        # Create coroutine for this source
                        source_task = youtube_source.get_tracks_from_sources(
                            sources=[source],
                            days_to_look_back=days,
                            limit=tracks_per_source,
                            progress_callback=lambda info: print(f"Progress: {info}")
                        )
                        batch_tasks.append((source, source_task))
                    
                    # Execute batch in parallel
                    print(f"Task {task_id}: Processing batch {batch_start + 1}-{batch_end} in parallel...")
                    batch_results = await asyncio.gather(
                        *[task for _, task in batch_tasks],
                        return_exceptions=True
                    )
                    
                    # Process results
                    for (source, _), result in zip(batch_tasks, batch_results):
                        if isinstance(result, Exception):
                            print(f"Task {task_id}: Error fetching from {source['name']}: {result}")
                            logger.error(f"Error fetching from {source['name']}: {result}")
                            continue
                        elif result:
                            tracks.extend(result)
                            print(f"Task {task_id}: Fetched {len(result)} tracks from {source['name']}")
                            logger.info(f"Fetched {len(result)} tracks from {source['name']}")
                        else:
                            print(f"Task {task_id}: No tracks found from {source['name']}")
                            logger.info(f"No tracks found from {source['name']}")
                    
                    # Small delay between batches to prevent rate limiting
                    if batch_end < total_sources:
                        await asyncio.sleep(0.5)
                
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
                task['progress'] = 70
                task['message'] = f'Fetched {len(track_dicts)} tracks from YouTube for genre {genre}'
                print(f"Task {task_id}: Successfully fetched {len(track_dicts)} tracks")
                
                # Update database immediately after fetching
                update_task_status(task_id, progress=70, message=task['message'])
                
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
            task['status'] = 'completed'
            task['progress'] = 100
            task['message'] = f'Successfully fetched {len(tracks)} tracks from YouTube!'
            
            # Generate CSV data for download
            import csv
            import io
            csv_buffer = io.StringIO()
            csv_writer = csv.writer(csv_buffer)
            csv_writer.writerow(['Title', 'Artist', 'Remix', 'Source'])
            
            for track in tracks:
                csv_writer.writerow([
                    track.get('title', ''),
                    track.get('artist', ''),
                    track.get('remix', ''),
                    track.get('source', '')
                ])
            
            task['csv_data'] = csv_buffer.getvalue()
            
            # Create result
            task['result'] = {
                'playlist_name': task['playlist_name'],
                'track_count': len(tracks),
                'tracks': tracks,  # Include all tracks for export
                'sources_used': [source['name'] for source in task.get('sources', [])],
                'genre': task['genre'],
                'days_searched': task['days']
            }
            
            # Save playlist to history for Pro users
            try:
                db_task = PlaylistTask.query.get(task_id)
                if db_task and db_task.user:
                    # Check if user has active subscription
                    if db_task.user.has_active_subscription:
                        # Compress CSV data
                        csv_compressed = base64.b64encode(
                            gzip.compress(task['csv_data'].encode('utf-8'))
                        ).decode('utf-8')
                        
                        # Create GeneratedPlaylist entry
                        generated_playlist = GeneratedPlaylist(
                            user_id=db_task.user_id,
                            task_id=task_id,
                            name=task['playlist_name'],
                            description=task.get('description', ''),
                            spotify_url='',  # No longer using Spotify
                            spotify_id=f'brightears_{task_id}',  # Use task ID as unique identifier
                            track_count=len(tracks),
                            source_channel=task['genre'],
                            days_analyzed=task['days'],
                            csv_data=csv_compressed
                        )
                        db.session.add(generated_playlist)
                        db.session.commit()
                        print(f"Saved playlist to history for Pro user {db_task.user_id}")
            except Exception as e:
                print(f"Error saving playlist to history: {e}")
                # Don't fail the task if history save fails
            
            # Update task status in database
            update_task_status(task_id, 
                             status='completed',
                             progress=100,
                             tracks_found=len(tracks))
            
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
