"""Main application entry point for the Spotify Playlist Generator app."""

import os
import sys
import time
import json
import asyncio
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from threading import Thread
from queue import Queue

# Load configuration and API keys from environment variables
# This is done first to ensure they're available for imports

youtube_api_key = os.environ.get('YOUTUBE_API_KEY')
spotify_client_id = os.environ.get('SPOTIFY_CLIENT_ID')
spotify_client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')

import logging

logger = logging.getLogger(__name__)

if not youtube_api_key:
    logger.warning("YOUTUBE_API_KEY not set. YouTube source may not work properly.")
if not spotify_client_id or not spotify_client_secret:
    logger.warning("Spotify credentials not set. Spotify authentication may fail.")

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SelectMultipleField, BooleanField, IntegerField
from wtforms.validators import DataRequired, NumberRange, Optional as OptionalValidator

from utils.sources.base import MusicSource, Track
from utils.destinations.base import PlaylistDestination, PlaylistResult
from utils.sources.traxsource_new import TraxsourceSource
from utils.sources.beatport import BeatportSource
from utils.sources.youtube import YouTubeSource
from utils.destinations.spotify import SpotifyDestination

from models import db, User
from auth import auth_bp
from subscription import subscription_bp

# -------------- Flask application setup --------------- #

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'development-key')

# Set the SQLite database path to an absolute path
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 
    f'sqlite:///{os.path.join(base_dir, "spotify_playlists.db")}'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Temporarily disable CSRF for development; enable for production
app.config['WTF_CSRF_ENABLED'] = False

# Initialize database
db.init_app(app)

# Set up Flask-Login
from flask_login import LoginManager, login_required, current_user

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(subscription_bp)

# -------------- Helper Functions --------------------- #

def subscription_required(f):
    """Decorator to check if user has an active subscription."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.has_active_subscription:
            return redirect(url_for('subscription.subscription'))
        return f(*args, **kwargs)
    return decorated_function

# Task management for playlist creation
tasks = {}

# -------------- Form Definition --------------------- #

class PlaylistForm(FlaskForm):
    """Form for creating a new playlist."""
    name = StringField('Playlist Name', validators=[DataRequired()])
    description = StringField('Description')
    genre = SelectField('Genre', choices=[
        ('', 'All Genres'),
        ('electronic', 'Electronic'),
        ('house', 'House'),
        ('techno', 'Techno'),
        ('ambient', 'Ambient'),
        ('pop', 'Pop'),
        ('rock', 'Rock'),
        ('indie', 'Indie'),
        ('hip-hop', 'Hip Hop'),
        ('rap', 'Rap'),
        ('r-n-b', 'R&B'),
        ('jazz', 'Jazz'),
        ('classical', 'Classical'),
        ('country', 'Country'),
        ('folk', 'Folk'),
        ('metal', 'Metal')
    ])
    days = IntegerField('Days to Look Back', default=7, validators=[NumberRange(min=1, max=90)])
    public = BooleanField('Public Playlist', default=True)

# -------------- Route Definitions ------------------ #

@app.route('/', methods=['GET', 'POST'])
def index():
    """Home page with playlist creation form."""
    form = PlaylistForm()
    errors = {}
    
    if request.method == 'POST':
        if form.validate():
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
                
            if not current_user.has_active_subscription:
                return redirect(url_for('subscription.subscription'))
                
            # Set up task ID and initial status
            task_id = str(int(time.time()))
            tasks[task_id] = {
                'status': 'initializing',
                'progress': 0,
                'message': 'Starting playlist generation...',
                'result': None,
                'user_id': current_user.id,
                'form_data': {
                    'name': form.name.data,
                    'description': form.description.data,
                    'genre': form.genre.data,
                    'days': form.days.data,
                    'public': form.public.data
                }
            }
            
            # Start playlist creation task in background
            thread = Thread(target=create_playlist_task, args=(task_id,))
            thread.daemon = True
            thread.start()
            
            return redirect(url_for('status', task_id=task_id))
        else:
            errors = form.errors
    
    return render_template('index.html', form=form, errors=errors)


@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard showing playlist history and stats."""
    # In a real implementation, this would load playlists from the database
    # For now, we'll just show a simple dashboard
    return render_template('dashboard.html')


@app.route('/create')
@login_required
@subscription_required
def create_playlist_page():
    """Display form to create a new playlist."""
    # Check if there's a previous task to retry
    task_id = request.args.get('retry')
    form = PlaylistForm()
    
    if task_id and task_id in tasks and tasks[task_id]['user_id'] == current_user.id:
        # Pre-fill the form with previous task data
        task_data = tasks[task_id]['form_data']
        form.name.data = task_data.get('name')
        form.description.data = task_data.get('description')
        form.genre.data = task_data.get('genre')
        form.days.data = task_data.get('days')
        form.public.data = task_data.get('public', True)
    
    return render_template('index.html', form=form)


@app.route('/status/<task_id>')
def status(task_id):
    """Show status of a playlist creation task."""
    if task_id not in tasks:
        return redirect(url_for('index'))
        
    # Only allow the user who created the task to view it
    if current_user.is_authenticated and tasks[task_id]['user_id'] == current_user.id:
        return render_template('status.html', task_id=task_id)
    
    return redirect(url_for('index'))


@app.route('/api/status/<task_id>')
def api_status(task_id):
    """API endpoint to get task status."""
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
        
    # Only allow the user who created the task to view it
    if not current_user.is_authenticated or tasks[task_id]['user_id'] != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify({
        'status': tasks[task_id]['status'],
        'progress': tasks[task_id]['progress'],
        'message': tasks[task_id]['message'],
        'result': tasks[task_id]['result']
    })


# -------------- Async Task Function ---------------- #

def create_playlist_task(task_id):
    """Background task to create a playlist."""
    task = tasks[task_id]
    
    try:
        task['status'] = 'processing'
        task['message'] = 'Getting tracks from source...'
        task['progress'] = 10
        
        # Get form data
        form_data = task['form_data']
        
        # Initialize source
        source = YouTubeSource(api_key=youtube_api_key)
        
        # Get the genre
        genre = form_data['genre']
        
        # Calculate the date range
        days_ago = form_data['days']
        start_date = datetime.utcnow() - timedelta(days=days_ago)
        
        # Update status
        task['message'] = f'Searching YouTube for {genre if genre else "all"} tracks from the last {days_ago} days...'
        task['progress'] = 20
        
        # Get tracks from the source
        # In a real implementation, this would be an async call
        # For now, we'll simulate with a delay
        time.sleep(2)  # Simulate API call
        
        tracks = []
        # Simulate finding tracks
        for i in range(15):
            tracks.append(Track(
                id=f'track{i}',
                title=f'Sample Track {i+1}',
                artist=f'Artist {i % 5 + 1}',
                album=f'Album {i % 3 + 1}',
                release_date=datetime.utcnow() - timedelta(days=i % days_ago),
                genre=genre if genre else 'Various',
                source='youtube',
                url=f'https://youtube.com/watch?v=sample{i}'
            ))
        
        # Update status
        task['message'] = f'Found {len(tracks)} tracks. Creating Spotify playlist...'
        task['progress'] = 50
        
        # Here we would normally connect to Spotify and create the playlist
        # For this prototype, we'll simulate success
        time.sleep(3)  # Simulate Spotify API operations
        
        # Format the date in the playlist name if needed
        playlist_name = form_data['name'].replace('{date}', datetime.utcnow().strftime('%Y-%m-%d'))
        
        # Update with final result
        task['status'] = 'complete'
        task['message'] = 'Playlist created successfully!'
        task['progress'] = 100
        task['result'] = {
            'playlist_name': playlist_name,
            'playlist_url': 'https://open.spotify.com/playlist/sample',
            'track_count': len(tracks),
            'tracks': [{'title': t.title, 'artist': t.artist} for t in tracks[:5]]  # Just show first 5
        }
        
    except Exception as e:
        task['status'] = 'error'
        task['message'] = f'Error creating playlist: {str(e)}'
        task['progress'] = 0


# -------------- Application Entry Point -------------- #

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

# explainer: Added Flask application setup with blueprint registration, playlist creation form, async task processing, and route handlers for the main functionality. This serves as the central entry point for the web application. -->
