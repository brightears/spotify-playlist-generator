"""
Flask web application for creating Spotify playlists from various sources.
"""
import os
import sys
import logging
import json
import asyncio
import uuid
import threading
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
from utils.sources.youtube import YouTubeSource
from utils.sources.beatport_rss import BeatportRSSSource
from utils.sources.juno_download import JunoDownloadSource
from utils.destinations.spotify import SpotifyDestination
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
    description = StringField('Description', validators=[OptionalValidator()])
    
    sources = SelectMultipleField('Sources', choices=[
        ('youtube', 'YouTube'),
        ('traxsource', 'Traxsource'),
        ('beatport', 'Beatport'),
        ('juno', 'Juno Download'),
    ], validators=[DataRequired()])
    
    genre = SelectField('Genre', choices=[
        ('all', 'All Genres'),
        ('house', 'House'),
        ('deep-house', 'Deep House'),
        ('tech-house', 'Tech House'),
        ('melodic-house', 'Melodic House'),
        ('afro-house', 'Afro House'),
    ], validators=[DataRequired()])
    
    days = IntegerField('Days to Look Back', 
                       validators=[DataRequired(), NumberRange(min=1, max=90)],
                       default=14)
    
    limit = IntegerField('Maximum Tracks', 
                        validators=[DataRequired(), NumberRange(min=1, max=200)],
                        default=50)
    
    min_score = IntegerField('Minimum Match Score (%)', 
                            validators=[DataRequired(), NumberRange(min=1, max=100)],
                            default=70)
    
    public = BooleanField('Public Playlist', default=True)


@app.route('/', methods=['GET', 'POST'])
def index():
    """Render the index page with the playlist configuration form."""
    form = PlaylistForm()
    
    if form.validate_on_submit():
        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        
        # Convert form data
        min_score = form.min_score.data / 100.0  # Convert percentage to 0-1 scale
        
        # Initialize task state
        tasks[task_id] = {
            'id': task_id,
            'status': 'initializing',
            'progress': 0,
            'messages': [],
            'result': None,
            'error': None,
            'created_at': datetime.now().isoformat(),
        }
        
        # Start background task
        run_async_task(
            task_id=task_id,
            sources=form.sources.data,
            name=form.name.data,
            description=form.description.data,
            genre=form.genre.data,
            days=form.days.data,
            limit=form.limit.data,
            public=form.public.data,
            min_score=min_score
        )
        
        # Redirect to status page
        return redirect(url_for('task_status', task_id=task_id))
    
    return render_template('index.html', form=form)


def run_async_task(task_id, sources, name, description, genre, days, limit, public, min_score):
    """Run an asynchronous task in a separate thread."""
    def wrapper():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                create_playlist_task(task_id, sources, name, description, genre, days, limit, public, min_score)
            )
        finally:
            loop.close()
    
    thread = threading.Thread(target=wrapper)
    thread.daemon = True
    thread.start()
    return thread


def log_message(message, task_id):
    """Add a message to the task log."""
    if task_id in tasks:
        if 'messages' not in tasks[task_id]:
            tasks[task_id]['messages'] = []
        tasks[task_id]['messages'].append(message)
        logger.info(f"Task {task_id}: {message}")


async def progress_callback(current, total, message, task_id):
    """Callback function for tracking progress."""
    if task_id in tasks:
        if total > 0:
            tasks[task_id]['progress'] = int((current / total) * 100)
        if message:
            log_message(message, task_id)


async def create_playlist_task(task_id, sources, name, description, genre, days, limit, public, min_score):
    """Background task for creating a playlist."""
    task = tasks[task_id]
    task['status'] = 'running'
    
    log_message(f"Starting playlist creation task", task_id)
    log_message(f"Sources: {', '.join(sources)}", task_id)
    log_message(f"Genre: {genre}", task_id)
    log_message(f"Days to look back: {days}", task_id)
    
    try:
        # Initialize sources
        source_instances = []
        for source_name in sources:
            if source_name == 'youtube':
                source_instances.append(YouTubeSource())
                log_message("Added YouTube source", task_id)
            elif source_name == 'traxsource':
                source_instances.append(TraxsourceSource())
                log_message("Added Traxsource source", task_id)
            elif source_name == 'beatport':
                source_instances.append(BeatportRSSSource())
                log_message("Added Beatport source", task_id)
            elif source_name == 'juno':
                source_instances.append(JunoDownloadSource())
                log_message("Added Juno Download source", task_id)
        
        if not source_instances:
            raise ValueError("No valid sources selected")
        
        # Initialize destination
        destination = SpotifyDestination()
        log_message("Using Spotify as destination", task_id)
        
        # Authenticate with Spotify
        log_message("Authenticating with Spotify...", task_id)
        authenticated = await destination.authenticate()
        
        if not authenticated:
            raise ValueError("Failed to authenticate with Spotify. Check credentials and try again.")
        
        log_message("Successfully authenticated with Spotify", task_id)
        
        # Create a custom progress callback that includes the task ID
        async def task_progress_callback(current, total, message=None):
            await progress_callback(current, total, message, task_id)
        
        # Create the playlist
        log_message(f"Creating playlist '{name}'...", task_id)
        
        # Fetch tracks from all sources first
        all_tracks = []
        for source in source_instances:
            source_limit = limit // len(source_instances)
            log_message(f"Fetching tracks from {source.name}...", task_id)
            
            try:
                tracks = await source.get_tracks(
                    days_to_look_back=days,
                    genre=genre,
                    limit=source_limit
                )
                log_message(f"Found {len(tracks)} tracks from {source.name}", task_id)
                all_tracks.extend(tracks)
            except Exception as e:
                log_message(f"Error fetching tracks from {source.name}: {str(e)}", task_id)
        
        log_message(f"Found {len(all_tracks)} total tracks", task_id)
        
        # Create the playlist
        result = await create_playlist(
            sources=source_instances,
            destination=destination,
            name=name,
            description=description,
            genre=genre,
            days_to_look_back=days,
            limit=limit,
            public=public,
            min_match_score=min_score,
            progress_callback=task_progress_callback
        )
        
        log_message(f"Playlist created with {result.tracks_added} of {len(all_tracks)} total tracks", task_id)
        
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
    # Use environment variables for port or default to 8080
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(debug=debug, host='0.0.0.0', port=port, threaded=True)