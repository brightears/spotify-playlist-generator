"""
Flask web application for creating Spotify playlists from various sources.
"""
import os
import sys
import logging
import json
import asyncio
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SelectMultipleField, BooleanField, IntegerField
from wtforms.validators import DataRequired, NumberRange, Optional as OptionalValidator

from utils.sources.base import MusicSource, Track
from utils.destinations.base import PlaylistDestination, PlaylistResult
from utils.sources.traxsource_new import TraxsourceSource
from playlist_generator import create_playlist

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-key-for-local-only')
app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF protection for development

# Global variables to store task state
tasks = {}

class PlaylistForm(FlaskForm):
    """Form for configuring playlist creation."""
    name = StringField('Playlist Name', validators=[DataRequired()])
    description = StringField('Playlist Description', validators=[DataRequired()])
    
    sources = SelectMultipleField('Sources', choices=[
        ('traxsource', 'Traxsource'),
        ('beatport', 'Beatport'),
        ('youtube', 'YouTube'),
        ('juno', 'Juno Download'),
    ], validators=[DataRequired()])
    
    destination = SelectField('Destination', choices=[
        ('spotify', 'Spotify'),
        ('youtube', 'YouTube'),
    ], validators=[DataRequired()])
    
    genre = SelectField('Genre', choices=[
        ('all', 'All Genres'),
        ('house', 'House'),
        ('deep-house', 'Deep House'),
        ('tech-house', 'Tech House'),
        ('soulful-house', 'Soulful House'),
        ('afro-house', 'Afro House'),
        ('nu-disco', 'Nu Disco'),
    ], validators=[DataRequired()])
    
    days_to_look_back = IntegerField('Days to Look Back', 
                                      validators=[NumberRange(min=1, max=30), DataRequired()],
                                      default=14)
    
    public = BooleanField('Public Playlist', default=True)
    
    limit = IntegerField('Track Limit', 
                         validators=[NumberRange(min=10, max=100), DataRequired()],
                         default=50)
    
    min_match_score = StringField('Minimum Match Score (0.0-1.0)', 
                                 default="0.5")

def log_message(message: str, task_id: str = None):
    """Log a message to the console and to the task log if task_id is provided."""
    logger.info(message)
    if task_id and task_id in tasks:
        tasks[task_id]['messages'].append({
            'text': message,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        })

async def update_progress(task_id: str, current: int, total: int, message: Optional[str] = None):
    """Update the progress of a task."""
    if task_id in tasks:
        progress = int((current / total) * 100) if total > 0 else 0
        tasks[task_id]['progress'] = progress
        if message:
            log_message(message, task_id)

@app.route('/')
def index():
    """Render the main page with the playlist creation form."""
    form = PlaylistForm()
    return render_template('index.html', form=form)

@app.route('/create-playlist', methods=['POST'])
def create_playlist_route():
    """Handle form submission to create a playlist."""
    form = PlaylistForm()
    
    if not form.validate_on_submit():
        return render_template('index.html', form=form, errors=form.errors)
    
    # Create a unique task ID
    task_id = str(uuid.uuid4())
    
    # Initialize task state
    tasks[task_id] = {
        'id': task_id,
        'status': 'starting',
        'progress': 0,
        'messages': [],
        'result': None,
        'error': None
    }
    
    # Log initial message
    log_message(f"Starting playlist creation task with ID: {task_id}", task_id)
    
    # Get form data
    playlist_name = form.name.data
    playlist_desc = form.description.data
    source_ids = form.sources.data
    destination_id = form.destination.data
    genre = form.genre.data
    days = form.days_to_look_back.data
    public = form.public.data
    limit = form.limit.data
    
    try:
        min_match_score = float(form.min_match_score.data)
        if not (0.0 <= min_match_score <= 1.0):
            min_match_score = 0.5  # Default if out of range
    except ValueError:
        min_match_score = 0.5  # Default if not a valid float
    
    # Set specific source thresholds
    source_match_thresholds = {
        'traxsource': 0.5,  # More lenient for Traxsource
        'youtube': 0.7,
        'beatport': 0.7,
        'juno': 0.6
    }
    
    # Store task parameters
    tasks[task_id]['params'] = {
        'name': playlist_name,
        'description': playlist_desc,
        'sources': source_ids,
        'destination': destination_id,
        'genre': genre,
        'days': days,
        'public': public,
        'limit': limit,
        'min_match_score': min_match_score
    }
    
    # Start the background task
    asyncio.run(run_playlist_creation_task(task_id))
    
    # Redirect to the status page
    return redirect(url_for('task_status', task_id=task_id))

async def run_playlist_creation_task(task_id: str):
    """Run the playlist creation task in the background."""
    if task_id not in tasks:
        return
    
    task = tasks[task_id]
    task['status'] = 'running'
    
    try:
        # Get task parameters
        params = task['params']
        playlist_name = params['name']
        playlist_desc = params['description']
        source_ids = params['sources']
        destination_id = params['destination']
        genre = params['genre']
        days = params['days']
        public = params['public']
        limit = params['limit']
        min_match_score = params['min_match_score']
        
        # Initialize sources
        sources = []
        
        # Log information about the task
        log_message(f"Creating playlist '{playlist_name}' with the following parameters:", task_id)
        log_message(f"- Sources: {', '.join(source_ids)}", task_id)
        log_message(f"- Destination: {destination_id}", task_id)
        log_message(f"- Genre: {genre}", task_id)
        log_message(f"- Days to look back: {days}", task_id)
        log_message(f"- Public: {public}", task_id)
        log_message(f"- Track limit: {limit}", task_id)
        log_message(f"- Minimum match score: {min_match_score}", task_id)
        
        # Add sources based on selected source IDs
        for source_id in source_ids:
            if source_id == 'traxsource':
                # Add Traxsource source for electronic music charts
                from utils.sources.traxsource_new import TraxsourceSource
                sources.append(TraxsourceSource())
                log_message("Added Traxsource source for electronic music charts", task_id)
            
            elif source_id == 'beatport':
                # Try to use Beatport API first, fall back to RSS if needed
                try:
                    from utils.sources.beatport_api import BeatportAPISource
                    sources.append(BeatportAPISource())
                    log_message("Added Beatport API source for electronic music charts", task_id)
                except Exception as e:
                    log_message(f"Could not initialize Beatport API: {e}", task_id)
                    log_message("Falling back to Beatport RSS feed", task_id)
                    from utils.sources.beatport_rss import BeatportRSSSource
                    sources.append(BeatportRSSSource())
                    log_message("Added Beatport RSS source for electronic music charts", task_id)
            
            elif source_id == 'youtube':
                # Add YouTube source for music from channels and playlists
                from utils.sources.youtube import YouTubeSource
                sources.append(YouTubeSource())
                log_message("Added YouTube source for music from channels and playlists", task_id)
            
            elif source_id == 'juno':
                # Add Juno Download source for electronic music charts
                from utils.sources.juno_download import JunoDownloadSource
                sources.append(JunoDownloadSource())
                log_message("Added Juno Download source for electronic music charts", task_id)
        
        if not sources:
            raise ValueError("No valid sources selected")
        
        # Initialize destination
        destination = None
        
        if destination_id == 'spotify':
            # Initialize Spotify destination
            from utils.destinations.spotify import SpotifyDestination
            destination = SpotifyDestination()
            log_message("Added Spotify as playlist destination", task_id)
        
        elif destination_id == 'youtube':
            # Initialize YouTube destination
            from utils.destinations.youtube import YouTubeDestination
            destination = YouTubeDestination()
            log_message("Added YouTube as playlist destination", task_id)
        
        if not destination:
            raise ValueError("No valid destination selected")
        
        # Authenticate with the destination
        log_message(f"Authenticating with {destination.name}...", task_id)
        authenticated = await destination.authenticate()
        
        if not authenticated:
            raise ValueError(f"Failed to authenticate with {destination.name}")
        
        log_message(f"Successfully authenticated with {destination.name}", task_id)
        
        # Define the progress callback
        async def progress_callback(current, total, message=None):
            await update_progress(task_id, current, total, message)
        
        # Create the playlist
        log_message(f"Creating playlist on {destination.name}...", task_id)
        
        # Fetch tracks from sources
        all_tracks = []
        for i, source in enumerate(sources):
            log_message(f"Fetching tracks from {source.name} ({i+1}/{len(sources)})...", task_id)
            
            # Set source-specific match threshold if available
            source_threshold = min_match_score
            if source.name in source_match_thresholds:
                source_threshold = source_match_thresholds[source.name]
                log_message(f"Using match threshold of {source_threshold} for {source.name}", task_id)
            
            try:
                tracks = await source.get_tracks(
                    days_to_look_back=days,
                    genre=genre,
                    limit=limit // len(sources)  # Distribute tracks evenly
                )
                
                # Add source information to each track
                for track in tracks:
                    track.source = source.name
                
                log_message(f"Found {len(tracks)} tracks from {source.name}", task_id)
                all_tracks.extend(tracks)
            except Exception as e:
                log_message(f"Error fetching tracks from {source.name}: {e}", task_id)
        
        if not all_tracks:
            raise ValueError("No tracks found from any source")
        
        log_message(f"Found {len(all_tracks)} total tracks from all sources", task_id)
        
        # Create the playlist
        result = await destination.create_playlist(
            name=playlist_name,
            description=playlist_desc,
            tracks=all_tracks,
            public=public,
            min_match_score=min_match_score,
            progress_callback=progress_callback
        )
        
        # Log results
        log_message("Playlist creation complete!", task_id)
        log_message(f"Playlist URL: {result.playlist_url}", task_id)
        log_message(f"Added {result.tracks_added} tracks out of {len(all_tracks)} total tracks", task_id)
        
        # Update task status
        task['status'] = 'completed'
        task['result'] = {
            'playlist_url': result.playlist_url,
            'tracks_added': result.tracks_added,
            'total_tracks': len(all_tracks)
        }
        task['progress'] = 100
        
    except Exception as e:
        logger.exception("Error in playlist creation task")
        task['status'] = 'failed'
        task['error'] = str(e)
        log_message(f"Error: {str(e)}", task_id)

@app.route('/status/<task_id>')
def task_status(task_id):
    """Render the status page for a task."""
    if task_id not in tasks:
        return render_template('status.html', error="Task not found")
    
    return render_template('status.html', task=tasks[task_id])

@app.route('/api/status/<task_id>')
def api_task_status(task_id):
    """API endpoint to get the status of a task."""
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    return jsonify(tasks[task_id])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)