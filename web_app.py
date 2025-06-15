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

# Load environment variables first
from dotenv import load_dotenv
load_dotenv()

# Ensure 'src' and root directory are importable
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

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
from flask_wtf import FlaskForm, CSRFProtect

from utils.sources.base import MusicSource, Track
from utils.destinations.base import PlaylistDestination, PlaylistResult
from utils.sources.youtube import YouTubeSource
from utils.destinations.spotify import SpotifyDestination

# Import the new FlaskSaaS auth & billing blueprints
from src.flasksaas import db
from src.flasksaas.models import User
from src.flasksaas.auth.routes import auth_bp
from src.flasksaas.billing.routes import billing_bp
from src.flasksaas.main import main_bp
from src.flasksaas.spotify_routes import spotify_bp
from src.flasksaas.forms import PlaylistForm

# -------------- Flask application setup --------------- #

app = Flask(__name__, template_folder="templates")

# Check if we're in production (Render sets RENDER environment variable)
IS_PRODUCTION = os.environ.get('RENDER') is not None

# Use a stable SECRET_KEY that doesn't change between restarts
# This is the most important setting for session stability
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'development-key-not-for-prod')
app.config['TESTING'] = not IS_PRODUCTION
app.config['DEBUG'] = not IS_PRODUCTION

# Session configuration for development - ensures cookies work properly
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=5)

# Configure session cookies based on environment
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_NAME'] = 'spotify_session'

# Make sessions permanent by default to improve persistence
@app.before_request
def make_session_permanent():
    session.permanent = True

# Set the SQLite database path to an absolute path
base_dir = os.path.abspath(os.path.dirname(__file__))

# Handle database URL - Render uses 'postgres://' but SQLAlchemy needs 'postgresql://'
database_url = os.environ.get('DATABASE_URL')
print(f"Raw DATABASE_URL: {database_url}")

if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
    print(f"Converted DATABASE_URL: {database_url}")

final_db_url = database_url or f'sqlite:///{os.path.join(base_dir, "spotify_playlists.db")}'
print(f"Final database URL: {final_db_url}")

app.config['SQLALCHEMY_DATABASE_URI'] = final_db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Enable CSRF protection in production
app.config['WTF_CSRF_ENABLED'] = IS_PRODUCTION

# Initialize CSRFProtect but don't enforce it for now
csrf = CSRFProtect()
csrf.init_app(app)

# Add a comment explaining this is for development only
# TODO: Re-enable CSRF protection before deploying to production
# This is temporarily disabled to troubleshoot authentication flow

# Initialize database
db.init_app(app)

# Initialize bcrypt for password hashing
from src.flasksaas.models import bcrypt
bcrypt.init_app(app)

# Set up Flask-Login
from flask_login import LoginManager, login_required, current_user

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Initialize database tables on first run
# Move this after all imports and blueprints are registered
def init_db():
    with app.app_context():
        try:
            print("Checking if database tables exist...")
            # Try to query the User table
            User.query.first()
            print("Database tables already exist.")
        except Exception as e:
            print(f"Database check error: {e}")
            print("Creating database tables...")
            db.create_all()
            print("Database tables created successfully!")

# Debug endpoint to manually create tables
@app.route('/debug/create-tables')
def debug_create_tables():
    """Debug endpoint to manually create database tables."""
    try:
        print("Creating database tables...")
        db.create_all()
        
        # Verify tables were created
        tables = db.engine.table_names()
        return f"""
        <h2>Database Setup Debug</h2>
        <p><strong>Database URL:</strong> {app.config['SQLALCHEMY_DATABASE_URI']}</p>
        <p><strong>Created tables:</strong> {tables}</p>
        <p><strong>Status:</strong> Tables created successfully!</p>
        <a href="/auth/register">Try Registration Now</a>
        """
    except Exception as e:
        return f"""
        <h2>Database Setup Error</h2>
        <p><strong>Database URL:</strong> {app.config['SQLALCHEMY_DATABASE_URI']}</p>
        <p><strong>Error:</strong> {str(e)}</p>
        """

# Register blueprints (new auth + billing + main)
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(billing_bp, url_prefix='/billing')
app.register_blueprint(main_bp)  # No prefix for main blueprint to match existing URLs
app.register_blueprint(spotify_bp, url_prefix='/spotify')  # Register the Spotify blueprint

# Initialize database after everything is set up
init_db()

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


# Dashboard route moved to main blueprint


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


# Auth status route for direct testing of authentication without redirects

@app.route('/auth-status')
def auth_status():
    """Display current authentication status without redirects."""
    user_data = {
        'is_authenticated': current_user.is_authenticated,
        'session_active': bool(session),
        'session_keys': list(session.keys())
    }
    
    if current_user.is_authenticated:
        user_data.update({
            'user_id': current_user.id,
            'user_email': current_user.email
        })
    
    return jsonify(user_data)

@app.route('/direct-login-helper')
def direct_login_helper():
    """Helper page for testing authentication in browser preview environments."""
    return render_template('direct_login.html')

@app.route('/test-session')
def test_session():
    """Test route to verify session persistence with browser-based test."""
    # Increment session counter
    session['count'] = session.get('count', 0) + 1
    session_keys = list(session.keys())
    
    from flask_wtf.csrf import generate_csrf
    csrf_token = generate_csrf()
    
    # Render template showing session info
    return render_template('test_session.html',
                           session_count=session.get('count', 0),
                           session_keys=session_keys,
                           csrf_token=csrf_token,
                           is_authenticated=current_user.is_authenticated,
                           user_email=current_user.email if current_user.is_authenticated else None)

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
