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

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()  # This loads the variables from .env

# Verify that critical environment variables are set
youtube_api_key = os.environ.get('YOUTUBE_API_KEY')
spotify_client_id = os.environ.get('SPOTIFY_CLIENT_ID')
spotify_client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')

if not youtube_api_key:
    print("WARNING: YOUTUBE_API_KEY not set. YouTube source may not work properly.")
if not spotify_client_id or not spotify_client_secret:
    print("WARNING: Spotify credentials not set. Spotify authentication may fail.")

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SelectMultipleField, BooleanField, IntegerField
from wtforms.validators import DataRequired, NumberRange, Optional as OptionalValidator

from utils.sources.base import MusicSource, Track
from utils.destinations.base import PlaylistDestination, PlaylistResult
from utils.sources.youtube import YouTubeSource
from utils.destinations.spotify import SpotifyDestination

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-key-for-local-only')
app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF protection for simplicity

# In-memory storage for tasks
tasks = {}

class PlaylistForm(FlaskForm):
    """Form for playlist creation."""
    name = StringField('Playlist Name', validators=[DataRequired()])
    description = StringField('Description', validators=[DataRequired()])
    genre = SelectField('Genre', choices=[
        ('all', 'All Genres'),
        ('house', 'House'),
        ('deep-house', 'Deep House'),
        ('nu-disco', 'Nu Disco')
    ], validators=[DataRequired()])
    days = IntegerField('Days to Look Back', default=14, validators=[
        DataRequired(),
        NumberRange(min=1, max=365)
    ])
    public = BooleanField('Public Playlist', default=True)


@app.route('/', methods=['GET', 'POST'])
def index():
    """Render the index page."""
    form = PlaylistForm()
    
    if form.validate_on_submit():
        # Create task ID
        task_id = str(uuid.uuid4())
        
        # Initialize task
        tasks[task_id] = {
            'id': task_id,
            'status': 'pending',
            'progress': 0,
            'logs': [],
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Run task in background
        run_async_task(
            task_id=task_id,
            name=form.name.data,
            description=form.description.data,
            genre=form.genre.data,
            days=form.days.data,
            limit=200,  # Default to a high limit for maximum track results
            public=form.public.data,
            export_csv=True
        )
        
        # Redirect to status page
        return redirect(url_for('task_status', task_id=task_id))
    
    return render_template('index.html', form=form)


def run_async_task(task_id, name, description, genre, days, limit, public, export_csv):
    """Run a task asynchronously."""
    def run_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(create_playlist_task(
                task_id=task_id,
                name=name,
                description=description,
                genre=genre,
                days=days,
                limit=limit,
                public=public,
                export_csv=export_csv
            ))
        except Exception as e:
            logger.exception(f"Error in background task: {e}")
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = str(e)
        finally:
            loop.close()
    
    thread = threading.Thread(target=run_task)
    thread.daemon = True
    thread.start()


def log_message(message, task_id):
    """Add a log message to a task."""
    if task_id in tasks:
        timestamp = datetime.now().isoformat()
        tasks[task_id]['logs'].append({
            'timestamp': timestamp,
            'message': message
        })
        tasks[task_id]['updated_at'] = timestamp
        logger.info(f"Task {task_id}: {message}")


async def progress_callback(current, total, message=None, task_id=None):
    """Callback for tracking progress."""
    if task_id is None or task_id not in tasks:
        return
    
    if total > 0:
        tasks[task_id]['progress'] = int((current / total) * 100)
    if message:
        log_message(message, task_id)


async def create_playlist_task(task_id, name, description, genre, days, limit, public, export_csv):
    """Background task for creating a playlist."""
    task = tasks[task_id]
    task['status'] = 'running'
    
    log_message(f"Starting playlist creation task", task_id)
    log_message(f"Source: YouTube", task_id)
    log_message(f"Genre: {genre}", task_id)
    log_message(f"Days to look back: {days}", task_id)
    
    try:
        # Initialize YouTube source
        source = YouTubeSource()
        log_message("Using YouTube as source", task_id)
        
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
        # Fetch tracks from YouTube
        log_message(f"Fetching tracks from YouTube...", task_id)
        
        try:
            tracks = await source.get_tracks(
                days_to_look_back=days,
                genre=genre,
                limit=limit * 3  # Fetch 3x the limit to account for tracks that won't match on Spotify
            )
            log_message(f"Found {len(tracks)} tracks", task_id)
        except Exception as e:
            log_message(f"Error fetching tracks: {str(e)}", task_id)
            raise
        
        # Create the playlist
        # Pass the tracks directly to the destination to create the playlist
        log_message(f"Creating playlist with Spotify...", task_id)
        result = await destination.create_playlist(
            name=name,
            description=description,
            tracks=tracks,
            public=public,
            progress_callback=task_progress_callback,
            export_unmatched=export_csv
        )
        
        log_message(f"Playlist created with {result.tracks_added} tracks", task_id)
        
        # Get the matched and unmatched tracks from the result
        matched_tracks = result.added_tracks if hasattr(result, 'added_tracks') and result.added_tracks else []
        unmatched_tracks = result.unmatched_tracks if hasattr(result, 'unmatched_tracks') and result.unmatched_tracks else []
        
        # Get CSV data directly from the result
        csv_data = result.csv_data if hasattr(result, 'csv_data') else None
        
        log_message(f"Matched tracks: {len(matched_tracks)}", task_id)
        log_message(f"Unmatched tracks: {len(unmatched_tracks)}", task_id)
        if csv_data:
            log_message(f"CSV data generated for export", task_id)
        
        # Update task status
        task['status'] = 'completed'
        task['result'] = {
            'playlist_url': result.playlist_url,
            'playlist_id': result.playlist_id,
            'tracks_added': result.tracks_added,
            'tracks_total': len(tracks),
            'matched_tracks': matched_tracks,
            'unmatched_tracks': unmatched_tracks,
            'csv_data': csv_data
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
        return render_template('error.html', message="Task not found"), 404
        
    return render_template('status.html', task_id=task_id, task=tasks[task_id])


@app.route('/download-csv/<task_id>')
def download_csv(task_id):
    """Download tracks as CSV."""
    if task_id not in tasks or 'result' not in tasks[task_id] or 'csv_data' not in tasks[task_id]['result']:
        return "No data available", 404
    
    # Get the CSV data from the task result
    csv_data = tasks[task_id]['result']['csv_data']
    if not csv_data:
        return "No data available", 404
    
    # Create a response with the CSV data
    response = Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=playlist_tracks_{task_id}.csv"}
    )
    
    return response

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