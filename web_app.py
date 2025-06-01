"""
Spotify Playlist Generator web application.
"""
import os
import json
from flask import Flask, render_template, redirect, url_for, request, session, jsonify, flash, Response
from flask_login import LoginManager, current_user, login_required
from datetime import datetime, timedelta
import uuid
import threading

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()  # This loads the variables from .env

from models import db, User
from auth import auth_bp
from subscription import subscription_bp

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-key-for-local-only')
app.config['DEBUG'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.abspath("instance/app.db")}')
# Debug output of database path
print(f"Using database at: {os.path.abspath('instance/app.db')}")
print(f"Database path exists: {os.path.exists(os.path.abspath('instance/app.db'))}")
print(f"Database directory exists: {os.path.exists(os.path.dirname(os.path.abspath('instance/app.db')))}")
print(f"SQLALCHEMY_DATABASE_URI: {os.environ.get('DATABASE_URL', f'sqlite:///{os.path.abspath('instance/app.db')}')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_ENABLED'] = False

# Upload folder settings
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

# Initialize extensions
db.init_app(app)

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database tables if they don't exist
with app.app_context():
    db.create_all()

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(subscription_bp)

# Dictionary to store background tasks
tasks = {}

# Routes
@app.route('/')
def index():
    """Home page."""
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard."""
    playlists = []  # TODO: Get user's playlists
    return render_template('dashboard.html', user=current_user, playlists=playlists)

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new playlist."""
    if request.method == 'POST':
        # Process the playlist creation form
        source_url = request.form.get('source_url')
        playlist_name = request.form.get('playlist_name')
        
        if not source_url or not playlist_name:
            flash('Please provide both a source URL and playlist name.', 'danger')
            return render_template('create.html')
        
        # Generate a unique ID for this task
        task_id = str(uuid.uuid4())
        
        # Start the playlist generation task in a background thread
        task = {
            'id': task_id,
            'user_id': current_user.id,
            'status': 'processing',
            'start_time': datetime.now(),
            'logs': [],
            'source_url': source_url,
            'playlist_name': playlist_name
        }
        tasks[task_id] = task
        
        # Redirect to status page
        return redirect(url_for('status', task_id=task_id))
    
    return render_template('create.html')

@app.route('/status/<task_id>')
@login_required
def status(task_id):
    """Show status of a playlist generation task."""
    task = tasks.get(task_id)
    if not task:
        flash('Task not found.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check if this task belongs to the current user
    if task.get('user_id') != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('dashboard'))
    
    return render_template('status.html', task_id=task_id)

@app.route('/api/status/<task_id>')
@login_required
def api_status(task_id):
    """API endpoint to get task status."""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # Check if this task belongs to the current user
    if task.get('user_id') != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify({
        'status': task.get('status'),
        'logs': task.get('logs', []),
        'matched': task.get('matched', []),
        'unmatched': task.get('unmatched', []),
        'playlist_url': task.get('playlist_url')
    })

# Clean up tasks older than 24 hours
@app.before_request
def clean_old_tasks():
    """Clean up old tasks."""
    cutoff = datetime.now() - timedelta(hours=24)
    
    for task_id in list(tasks.keys()):
        task = tasks.get(task_id)
        if task and task.get('start_time') and task.get('start_time') < cutoff:
            del tasks[task_id]

if __name__ == '__main__':
    # Create upload folder if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Use environment variables for port or default to 8080
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(debug=debug, host='0.0.0.0', port=port, threaded=True)

# <!-- explainer: This file sets up the Flask application with database, authentication, and subscription integration. Key features include:
# 1. SQLAlchemy database initialization with proper path handling
# 2. Flask-Login for user authentication
# 3. Registration of auth and subscription blueprints
# 4. Protected dashboard route requiring login
# 5. Task management for playlist generation
# 6. Debug configuration for easier development
# -->