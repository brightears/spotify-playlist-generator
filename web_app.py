"""
Spotify Playlist Generator web application.
"""
import os
import json
from flask import Flask, render_template, redirect, url_for, request, session, jsonify, flash, Response
from flask_wtf import FlaskForm
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from wtforms import StringField, BooleanField, SelectField, IntegerField
from wtforms.validators import DataRequired, Optional, NumberRange
import secrets
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import uuid
import threading

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()  # This loads the variables from .env

from playlist_generator import generate_playlist
from models.user import User
from utils.spotify_oauth import SpotifyOAuth
from utils.payment_service import create_checkout_session, handle_webhook_event
from auth import auth

# Verify that critical environment variables are set
youtube_api_key = os.environ.get('YOUTUBE_API_KEY')
spotify_client_id = os.environ.get('SPOTIFY_CLIENT_ID')
spotify_client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')

if not youtube_api_key:
    print("WARNING: YOUTUBE_API_KEY not set. YouTube source may not work properly.")
if not spotify_client_id or not spotify_client_secret:
    print("WARNING: Spotify credentials not set. Spotify authentication may fail.")

# Optional validator
class OptionalValidator:
    def __call__(self, form, field):
        pass

# Form class
class PlaylistForm(FlaskForm):
    name = StringField('Playlist Name', validators=[DataRequired()])
    description = StringField('Description', validators=[OptionalValidator()])
    genre = SelectField('Genre', choices=[
        ('acoustic', 'Acoustic'),
        ('afrobeat', 'Afrobeat'),
        ('alt-rock', 'Alternative Rock'),
        ('alternative', 'Alternative'),
        ('ambient', 'Ambient'),
        ('blues', 'Blues'),
        ('chill', 'Chill'),
        ('classical', 'Classical'),
        ('club', 'Club'),
        ('country', 'Country'),
        ('dance', 'Dance'),
        ('deep-house', 'Deep House'),
        ('disco', 'Disco'),
        ('drum-and-bass', 'Drum and Bass'),
        ('dubstep', 'Dubstep'),
        ('edm', 'EDM'),
        ('electro', 'Electro'),
        ('electronic', 'Electronic'),
        ('folk', 'Folk'),
        ('funk', 'Funk'),
        ('groove', 'Groove'),
        ('grunge', 'Grunge'),
        ('guitar', 'Guitar'),
        ('happy', 'Happy'),
        ('hard-rock', 'Hard Rock'),
        ('heavy-metal', 'Heavy Metal'),
        ('hip-hop', 'Hip Hop'),
        ('house', 'House'),
        ('indie', 'Indie'),
        ('indie-pop', 'Indie Pop'),
        ('jazz', 'Jazz'),
        ('k-pop', 'K-Pop'),
        ('latin', 'Latin'),
        ('metal', 'Metal'),
        ('new-release', 'New Release'),
        ('opera', 'Opera'),
        ('party', 'Party'),
        ('piano', 'Piano'),
        ('pop', 'Pop'),
        ('r-n-b', 'R&B'),
        ('reggae', 'Reggae'),
        ('reggaeton', 'Reggaeton'),
        ('rock', 'Rock'),
        ('rock-n-roll', 'Rock n Roll'),
        ('romance', 'Romance'),
        ('sad', 'Sad'),
        ('salsa', 'Salsa'),
        ('samba', 'Samba'),
        ('ska', 'Ska'),
        ('sleep', 'Sleep'),
        ('soul', 'Soul'),
        ('study', 'Study'),
        ('summer', 'Summer'),
        ('synth-pop', 'Synth Pop'),
        ('techno', 'Techno'),
        ('trance', 'Trance'),
        ('trip-hop', 'Trip Hop'),
        ('world-music', 'World Music')
    ], validators=[DataRequired()])
    days = IntegerField('Days to Look Back', validators=[DataRequired(), NumberRange(min=1, max=90)], default=14)
    public = BooleanField('Public Playlist', default=True)

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(16))
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Register blueprints
app.register_blueprint(auth, url_prefix='/auth')

# Tasks storage (memory-based for demonstration)
tasks = {}

# Setup Spotify OAuth
spotify_oauth = SpotifyOAuth()

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID."""
    return User.get_by_id(user_id)

# Landing page route
@app.route('/')
def index():
    """Landing page for the application."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

# Dashboard route (requires login)
@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard after login."""
    # Check if user has active subscription
    if not current_user.has_active_subscription():
        return redirect(url_for('subscription'))
    
    # Check if user has connected Spotify
    spotify_connected = bool(current_user.spotify_tokens.get('access_token'))
    
    # Get user's created playlists
    playlists = current_user.created_playlists
    
    return render_template('dashboard.html', 
                          spotify_connected=spotify_connected,
                          playlists=playlists)

# Subscription page route
@app.route('/subscription')
@login_required
def subscription():
    """Subscription page for payment."""
    # Check if user already has active subscription
    if current_user.has_active_subscription():
        return redirect(url_for('dashboard'))
    
    return render_template('subscription.html', 
                          price='$3.00',
                          period='month')

# Create checkout session route
@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout():
    """Create Stripe checkout session."""
    success_url = url_for('subscription_success', _external=True)
    cancel_url = url_for('subscription', _external=True)
    
    session_id = create_checkout_session(
        current_user.email, 
        success_url, 
        cancel_url
    )
    
    if not session_id:
        flash('An error occurred while creating the checkout session.', 'danger')
        return redirect(url_for('subscription'))
    
    return jsonify({'id': session_id})

# Subscription success route
@app.route('/subscription/success')
@login_required
def subscription_success():
    """Handle successful subscription."""
    session_id = request.args.get('session_id')
    
    if session_id:
        # In a real application, verify the session with Stripe
        # and update the user's subscription status
        
        # For demonstration, we'll just activate the subscription
        current_user.activate_subscription()
        
        flash('Your subscription was successful! You now have full access.', 'success')
    
    return redirect(url_for('dashboard'))

# Stripe webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Stripe webhook events."""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    
    event_data = handle_webhook_event(payload, sig_header)
    
    if not event_data or not event_data.get('success'):
        return jsonify({'status': 'error'}), 400
    
    # Handle subscription events
    if event_data.get('type') == 'subscription_created':
        # Find user by email and update subscription
        user = User.get_by_email(event_data.get('customer_email'))
        if user:
            user.activate_subscription()
    
    elif event_data.get('type') == 'subscription_cancelled':
        # Find user by subscription ID and deactivate
        # This is just a placeholder - implement based on your database structure
        pass
    
    return jsonify({'status': 'success'})

# Connect to Spotify route
@app.route('/connect-spotify')
@login_required
def connect_spotify():
    """Connect user's Spotify account."""
    # Check if user has active subscription
    if not current_user.has_active_subscription():
        flash('Please subscribe to access this feature.', 'warning')
        return redirect(url_for('subscription'))
    
    # Generate a state value for CSRF protection
    state = secrets.token_hex(16)
    session['spotify_auth_state'] = state
    
    # Get Spotify auth URL
    auth_url = spotify_oauth.get_auth_url(state)
    
    return redirect(auth_url)

# Spotify callback route
@app.route('/callback')
@login_required
def spotify_callback():
    """Handle Spotify OAuth callback."""
    error = request.args.get('error')
    code = request.args.get('code')
    state = request.args.get('state')
    
    # Check state for CSRF protection
    if state != session.get('spotify_auth_state'):
        flash('State mismatch. Please try again.', 'danger')
        return redirect(url_for('dashboard'))
    
    if error:
        flash(f'Spotify authentication error: {error}', 'danger')
        return redirect(url_for('dashboard'))
    
    # Exchange code for tokens
    token_info = spotify_oauth.get_token(code)
    
    if not token_info:
        flash('Failed to get Spotify tokens.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Save tokens to user record
    current_user.add_spotify_tokens(
        token_info['access_token'],
        token_info['refresh_token'],
        token_info['expires_at']
    )
    
    flash('Successfully connected to Spotify!', 'success')
    return redirect(url_for('dashboard'))

# Playlist creation form route
@app.route('/create-playlist', methods=['GET', 'POST'])
@login_required
def create_playlist():
    """Create playlist form."""
    # Check if user has active subscription
    if not current_user.has_active_subscription():
        flash('Please subscribe to access this feature.', 'warning')
        return redirect(url_for('subscription'))
    
    # Check if user has connected Spotify
    if not current_user.spotify_tokens.get('access_token'):
        flash('Please connect your Spotify account first.', 'warning')
        return redirect(url_for('dashboard'))
    
    form = PlaylistForm()
    
    if form.validate_on_submit():
        # Create unique task ID
        task_id = str(uuid.uuid4())
        
        # Initialize task
        tasks[task_id] = {
            'status': 'pending',
            'logs': [],
            'matched': [],
            'unmatched': [],
            'playlist_url': None,
            'start_time': datetime.now(),
            'user_id': current_user.id,
            'result': {}
        }
        
        # Get form data
        playlist_data = {
            'name': form.name.data,
            'description': form.description.data,
            'genre': form.genre.data,
            'days': form.days.data,
            'public': form.public.data,
            'user_id': current_user.id,
            'task_id': task_id,
            'spotify_tokens': current_user.spotify_tokens,
        }
        
        # Start playlist generation in a background thread
        thread = threading.Thread(target=run_playlist_task, args=(task_id, playlist_data))
        thread.daemon = True
        thread.start()
        
        return redirect(url_for('status', task_id=task_id))
    
    return render_template('create_playlist.html', form=form)

def run_playlist_task(task_id, playlist_data):
    """Run playlist generation task."""
    task = tasks.get(task_id)
    if not task:
        return
    
    try:
        task['status'] = 'running'
        
        # Extract Spotify tokens
        spotify_tokens = playlist_data.pop('spotify_tokens')
        
        # Log function for the task
        def log_message(message):
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            task['logs'].append({'timestamp': timestamp, 'message': message})
        
        # Generate playlist with the logged messages
        result = generate_playlist(
            playlist_data['name'],
            playlist_data['description'],
            playlist_data['genre'],
            playlist_data['days'],
            limit=50,  # Set a reasonable limit
            public=playlist_data['public'],
            log_message=log_message,
            spotify_tokens=spotify_tokens
        )
        
        # Update task with results
        task['matched'] = result['matched']
        task['unmatched'] = result['unmatched']
        task['playlist_url'] = result['playlist_url']
        task['result'] = result
        task['status'] = 'completed'
        
        # Save playlist to user history
        user = User.get_by_id(playlist_data['user_id'])
        if user:
            user.add_created_playlist({
                'name': playlist_data['name'],
                'description': playlist_data['description'],
                'created_at': datetime.now().isoformat(),
                'track_count': len(result['matched']),
                'playlist_url': result['playlist_url']
            })
    except Exception as e:
        task['status'] = 'failed'
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        task['logs'].append({
            'timestamp': timestamp,
            'message': f'Error: {str(e)}'
        })

# Status page route
@app.route('/status/<task_id>')
@login_required
def status(task_id):
    """Show task status."""
    task = tasks.get(task_id)
    
    if not task:
        flash('Task not found.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check if this task belongs to the current user
    if task.get('user_id') != current_user.id:
        flash('You do not have access to this task.', 'danger')
        return redirect(url_for('dashboard'))
    
    return render_template('status.html', task_id=task_id, task=task)

# Download CSV route
@app.route('/download-csv/<task_id>')
@login_required
def download_csv(task_id):
    """Download tracks as CSV."""
    task = tasks.get(task_id)
    
    if not task:
        flash('Task not found.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check if this task belongs to the current user
    if task.get('user_id') != current_user.id:
        flash('You do not have access to this task.', 'danger')
        return redirect(url_for('dashboard'))
    
    if not task.get('result') or not task.get('result').get('csv_data'):
        flash('No CSV data available for this task.', 'warning')
        return redirect(url_for('status', task_id=task_id))
    
    # Create a response with the CSV data
    response = Response(
        task['result']['csv_data'],
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=playlist_tracks_{task_id}.csv"}
    )
    
    return response

# API endpoint for task status
@app.route('/api/status/<task_id>')
@login_required
def api_status(task_id):
    """Get task status via API."""
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