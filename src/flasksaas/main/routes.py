"""Main blueprint for core application routes."""
import time
import asyncio
import csv
import io
import json
import uuid
import gzip
import base64
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app, session, send_file, make_response
from flask_login import login_required, current_user
from flask_wtf.csrf import generate_csrf
from flask_mail import Message, Mail

# Import the PlaylistForm from the correct location
from src.flasksaas.forms import PlaylistForm
from src.flasksaas.main.task_manager import create_new_task, process_task_step, get_task, get_user_tasks, tasks, TaskManager
from ..models import User, UserSource, GeneratedPlaylist
from .. import db

def populate_suggested_sources(user_id):
    """Pre-populate suggested playlist sources for new Pro users."""
    # Check if user already has sources
    existing_sources = UserSource.query.filter_by(user_id=user_id).count()
    if existing_sources > 0:
        return  # User already has sources, don't add suggestions
    
    # Our suggested playlists
    suggested_sources = [
        {"name": "Selected Base", "url": "https://www.youtube.com/playlist?list=PLSr_oFUba1jtP9x5ZFs5Y0GJkb8fmC161"},
        {"name": "Defected Music", "url": "https://www.youtube.com/playlist?list=PLoRGBexfBL8dbhIs6-GqWapmosx-0gqa7"},
        {"name": "Glitterbox Ibiza", "url": "https://www.youtube.com/playlist?list=PLIxQjHO1yTm99RG32st06TnxZHMgCbT4H"},
        {"name": "Anjunadeep", "url": "https://www.youtube.com/playlist?list=PLp0LvzekmDePVdSozfdcux2Lm-zw25Iie"},
        {"name": "Toolroom Records", "url": "https://www.youtube.com/playlist?list=PLGdqhGdToks3HVLQqYbkp1pkyyuZUkJ8U"},
        {"name": "Spinnin' Records", "url": "https://www.youtube.com/playlist?list=PL53244BC75ACF40D0"},
        {"name": "Stay True Sounds", "url": "https://www.youtube.com/playlist?list=PLOH68idrufmjnBkoJLchYzyRN_uFcH628"}
    ]
    
    try:
        for source in suggested_sources:
            new_source = UserSource(
                user_id=user_id,
                name=source["name"],
                source_url=source["url"],
                source_type="playlist",
                is_active=True
            )
            db.session.add(new_source)
        
        db.session.commit()
        current_app.logger.info(f"Added {len(suggested_sources)} suggested sources for user {user_id}")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding suggested sources: {e}")

main_bp = Blueprint('main', __name__, template_folder="templates")
task_manager = TaskManager()

@main_bp.route("/")
def index():
    """Home page."""
    # Show landing page for non-authenticated users, dashboard for authenticated
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template("landing.html")

@main_bp.route("/dashboard")
@login_required
def dashboard():
    """User dashboard."""
    # Simply render the dashboard template
    return render_template("dashboard.html")

@main_bp.route("/guide")
def guide():
    """Music discovery guide."""
    return render_template("guide.html")

@main_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    """Create a new playlist."""
    try:
        form = PlaylistForm()
        
        # For Pro users, populate the sources dynamically
        if current_user.has_active_subscription:
            # Pre-populate suggested sources if user has none
            populate_suggested_sources(current_user.id)
            
            # Build choices for the form - only custom sources
            choices = []
            
            # Get all custom sources (including pre-populated suggestions)
            custom_sources = UserSource.query.filter_by(
                user_id=current_user.id,
                is_active=True
            ).all()
            
            for source in custom_sources:
                choice_id = f"custom_{source.id}"
                choices.append((choice_id, source.name))
            
            form.selected_sources.choices = choices
            
            # Pre-select all sources by default on GET request
            if request.method == 'GET':
                form.selected_sources.data = [choice[0] for choice in choices]
        
        if form.validate_on_submit():
            # Process selected sources for Pro users
            selected_sources = None
            if current_user.has_active_subscription and hasattr(form, 'selected_sources'):
                selected_sources = form.selected_sources.data
                # Validate that at least one source is selected
                if not selected_sources:
                    flash("Please select at least one source.", "error")
                    return render_template('create.html', form=form)
            
            # Create a new task with the form data
            task_id = create_new_task(
                user_id=current_user.id,
                playlist_name=form.name.data,
                description=form.description.data,
                genre=form.genre.data if not current_user.has_active_subscription else 'all',
                days=form.days.data,
                public=True,  # Default to True since we removed the form field
                source_selection='both' if not selected_sources else selected_sources
            )
            
            # No flash message needed - the status page will show the progress
            return redirect(url_for('main.status', task_id=task_id))
        
        # Log form errors if any
        if request.method == 'POST' and not form.validate():
            current_app.logger.error(f"Form validation errors: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"{field}: {error}", "error")
        
        return render_template('create.html', form=form)
        
    except Exception as e:
        current_app.logger.error(f"Error in create route: {e}", exc_info=True)
        flash("An error occurred. Please try again.", "error")
        # Create a fresh form instance
        form = PlaylistForm()
        return render_template('create.html', form=form)

@main_bp.route("/test-session")
def test_session():
    """Test session functionality."""
    session['count'] = session.get('count', 0) + 1
    return jsonify({
        'count': session['count'], 
        'session_keys': list(session.keys()),
        'session_id': session.get('_id', 'No session ID')
    })

@main_bp.route('/status/<task_id>')
@login_required
def status(task_id):
    """Show the status of a playlist creation task."""
    print(f"Status route accessed for task {task_id} by user {current_user.id}")
    
    # Get task using the task manager
    task = get_task(task_id)
    if not task:
        flash("Task not found.", "error")
        return redirect(url_for('main.dashboard'))
    
    # Check if user owns this task
    if task['user_id'] != current_user.id:
        flash("Access denied.", "error")
        return redirect(url_for('main.dashboard'))
    
    print(f"Task data: {task}")
    
    return render_template('status.html', task_id=task_id, task=task)

@main_bp.route('/debug/status/<task_id>')
@login_required
def debug_status(task_id):
    """Debug version of the status page with direct API polling."""
    # Get task using the task manager
    task = get_task(task_id)
    if not task:
        return f"Task {task_id} not found"
    
    # Check if user owns this task
    if task['user_id'] != current_user.id:
        return f"Access denied. Task belongs to user {task['user_id']}, current user is {current_user.id}"
    
    return render_template('debug_status.html', 
                         task_id=task_id, 
                         task=task,
                         user_id=current_user.id,
                         session_id=session.get('_id', 'No session ID'),
                         csrf_token=generate_csrf())


@main_bp.route('/api/status/<task_id>')
def api_status(task_id):
    """API endpoint to get task status."""
    print(f"API status called for task {task_id}")
    print(f"Session ID: {session.get('_id', 'No session ID')}")
    print(f"Session keys: {list(session.keys())}")
    print(f"Current user: {getattr(current_user, 'id', 'Not authenticated')}")
    
    # Get task using the task manager
    task = get_task(task_id)
    if not task:
        print(f"Task {task_id} not found")
        return jsonify({'error': 'Task not found'}), 404
    
    # Require authentication and ownership check
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    if task['user_id'] != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    print(f"Task found: user_id={task['user_id']}, status={task['status']}, step={task['step']}")
    
    # Store pre-processing state for debugging
    pre_status = task['status']
    pre_step = task['step']
    pre_progress = task['progress']
    
    print(f"API status: Task {task_id} before processing - status: {pre_status}, step: {pre_step}, progress: {pre_progress}%")
    
    # If the task is still in progress, advance it by one step
    was_updated = False
    if task['status'] not in ['completed', 'error']:
        # This will update the task state if needed
        was_updated = asyncio.run(process_task_step(task_id))
        task = get_task(task_id)  # Get updated task
        print(f"API status: Task {task_id} after processing - status: {task['status']}, step: {task['step']}, progress: {task['progress']}%, updated: {was_updated}")
    
    # Return the current task status
    response_data = {
        'status': task['status'],
        'progress': task['progress'],
        'message': task['message'],
        'step': task['step'],
        'authenticated': True,
        'was_updated': was_updated,
        'pre_status': pre_status,
        'pre_step': pre_step,
        'pre_progress': pre_progress
    }
    
    # Add task results if complete
    if task['status'] == 'completed':
        response_data.update({
            'tracks': task.get('tracks', []),
            'sources': task.get('sources', []),
            'total_tracks': len(task.get('tracks', [])),
            'result': task.get('result'),  # Include the result object for the frontend
            'csv_data': task.get('csv_data'),  # Include CSV data for download button
            'matched_tracks': task.get('matched_tracks'),
            'unmatched_tracks': task.get('unmatched_tracks'),
            'spotify_playlist_url': task.get('spotify_playlist_url')
        })
    elif task['status'] == 'error':
        response_data['error'] = task.get('message', 'Unknown error')
    
    print(f"API response: {response_data}")
    return jsonify(response_data)

@main_bp.route('/test-api/<task_id>')
@login_required
def test_api(task_id):
    """Test route to debug API issues."""
    # Get task using the task manager
    task = get_task(task_id)
    if not task:
        return f"Task {task_id} not found"
    
    # Check if user owns this task
    if task['user_id'] != current_user.id:
        return f"Task belongs to user {task['user_id']}, current user is {current_user.id}"
    
    # Try to process the task
    was_updated = asyncio.run(process_task_step(task_id))
    task = get_task(task_id)
    
    return f"""
    <h2>Task {task_id} Debug Info</h2>
    <p><strong>User ID:</strong> {current_user.id}</p>
    <p><strong>Task User ID:</strong> {task['user_id']}</p>
    <p><strong>Status:</strong> {task['status']}</p>
    <p><strong>Step:</strong> {task['step']}</p>
    <p><strong>Progress:</strong> {task['progress']}%</p>
    <p><strong>Message:</strong> {task['message']}</p>
    <p><strong>Was Updated:</strong> {was_updated}</p>
    <p><strong>Session ID:</strong> {session.get('_id', 'No session ID')}</p>
    <p><strong>CSRF Token:</strong> {generate_csrf()}</p>
    <p><strong>Last Updated:</strong> {task['last_updated']}</p>
    <br>
    <a href="{url_for('main.api_status', task_id=task_id)}">API Status Endpoint</a>
    """

@main_bp.route('/simple/status/<task_id>')
@login_required
def simple_status(task_id):
    """Simple status page that passes task data directly to template."""
    # Get task using the task manager
    task = get_task(task_id)
    if not task:
        flash("Task not found.", "error")
        return redirect(url_for('main.dashboard'))
    
    # Check if user owns this task
    if task['user_id'] != current_user.id:
        flash("Access denied.", "error")
        return redirect(url_for('main.dashboard'))
    
    # Process the task if it's not complete
    if task['status'] not in ['completed', 'error']:
        asyncio.run(process_task_step(task_id))
        task = get_task(task_id)  # Get updated task
    
    return render_template('simple_status.html', task_id=task_id, task=task)

@main_bp.route('/download/<task_id>')
@login_required
def download(task_id):
    """Download playlist results in various formats."""
    # Check if this is a historical playlist
    if task_id.startswith('history_'):
        playlist_id = int(task_id.replace('history_', ''))
        
        # Get the historical playlist
        playlist = GeneratedPlaylist.query.filter_by(
            id=playlist_id,
            user_id=current_user.id
        ).first()
        
        if not playlist:
            flash("Playlist not found.", "error")
            return redirect(url_for('main.history'))
        
        # Decompress the CSV data to get tracks
        try:
            csv_data = gzip.decompress(
                base64.b64decode(playlist.csv_data.encode('utf-8'))
            ).decode('utf-8')
            
            # Parse CSV to get tracks
            csv_reader = csv.DictReader(io.StringIO(csv_data))
            tracks = []
            for row in csv_reader:
                tracks.append({
                    'title': row.get('Title', ''),
                    'artist': row.get('Artist', ''),
                    'remix': row.get('Remix', ''),
                    'source': row.get('Source', ''),
                    'url': row.get('URL', '')
                })
            
            # Create a task-like object for the download logic
            task = {
                'status': 'completed',
                'result': {
                    'tracks': tracks,
                    'playlist_name': playlist.name
                },
                'csv_data': csv_data
            }
            result = task['result']
            playlist_name = playlist.name
            
        except Exception as e:
            current_app.logger.error(f"Error loading historical playlist: {e}")
            flash("Error loading playlist data.", "error")
            return redirect(url_for('main.history'))
    else:
        # Get live task using the task manager
        task = get_task(task_id)
        if not task:
            flash("Task not found.", "error")
            return redirect(url_for('main.dashboard'))
        
        # Check if user owns this task
        if task['user_id'] != current_user.id:
            flash("Access denied.", "error")
            return redirect(url_for('main.dashboard'))
        
        # Check if task is complete
        if task['status'] not in ['completed', 'complete']:
            flash("Task is not complete.", "error")
            return redirect(url_for('main.status', task_id=task_id))
        
        result = task.get('result', {})
        tracks = result.get('tracks', [])
        playlist_name = result.get('playlist_name', f'playlist_{task_id}')
    
    # Get format from query string
    format_type = request.args.get('format', 'csv').lower()
    tracks = result.get('tracks', [])
    
    # Debug logging
    current_app.logger.info(f"Download request for task {task_id}: format={format_type}, tracks count={len(tracks)}")
    
    if format_type == 'csv':
        # Generate CSV - check if we have cached data
        if task.get('csv_data'):
            csv_data = task['csv_data']
        else:
            # Generate CSV from tracks
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
            
            csv_data = csv_buffer.getvalue()
        
        response = make_response(csv_data)
        response.headers['Content-Disposition'] = f'attachment; filename={playlist_name}.csv'
        response.headers['Content-Type'] = 'text/csv'
        
    elif format_type == 'm3u':
        # Generate M3U playlist
        m3u_content = "#EXTM3U\n"
        m3u_content += f"#PLAYLIST:{playlist_name}\n\n"
        
        for track in tracks:
            # M3U format: #EXTINF:duration,Artist - Title
            artist = track.get('artist', 'Unknown Artist')
            title = track.get('title', 'Unknown Title')
            remix = track.get('remix', '')
            full_title = f"{title} ({remix})" if remix else title
            
            m3u_content += f"#EXTINF:-1,{artist} - {full_title}\n"
            # For YouTube tracks, we can include the URL
            if track.get('url'):
                m3u_content += f"{track['url']}\n\n"
            else:
                m3u_content += f"# Search: {artist} {full_title}\n\n"
        
        response = make_response(m3u_content)
        response.headers['Content-Disposition'] = f'attachment; filename={playlist_name}.m3u8'
        response.headers['Content-Type'] = 'audio/x-mpegurl'
        
    elif format_type == 'json':
        # Generate JSON export
        json_data = {
            'playlist_name': playlist_name,
            'created_at': datetime.now().isoformat(),
            'track_count': len(tracks),
            'genre': result.get('genre', ''),
            'days_searched': result.get('days_searched', 0),
            'sources': result.get('sources_used', []),
            'tracks': tracks
        }
        
        response = make_response(json.dumps(json_data, indent=2))
        response.headers['Content-Disposition'] = f'attachment; filename={playlist_name}.json'
        response.headers['Content-Type'] = 'application/json'
        
    else:
        # Default to CSV for unknown formats
        return redirect(url_for('main.download', task_id=task_id, format='csv'))
    
    return response


@main_bp.route("/sources")
@login_required
def sources():
    """Manage custom YouTube sources (paid users only)."""
    if not current_user.has_active_subscription:
        flash("Custom sources are available for Pro subscribers only.", "warning")
        return redirect(url_for('main.dashboard'))
    
    # Pre-populate suggested sources for new Pro users
    populate_suggested_sources(current_user.id)
    
    user_sources = UserSource.query.filter_by(user_id=current_user.id).order_by(UserSource.created_at.desc()).all()
    max_sources = 20
    
    return render_template("sources.html", 
                         sources=user_sources, 
                         current_count=len(user_sources),
                         max_sources=max_sources)


@main_bp.route("/sources/add", methods=["GET", "POST"])
@login_required
def add_source():
    """Add a new custom YouTube source."""
    if not current_user.has_active_subscription:
        flash("Custom sources are available for Pro subscribers only.", "warning")
        return redirect(url_for('main.dashboard'))
    
    # Check current source count
    current_source_count = UserSource.query.filter_by(user_id=current_user.id).count()
    max_sources = 20
    
    if request.method == "POST":
        # Check if user has reached the limit
        if current_source_count >= max_sources:
            flash(f"You've reached the maximum of {max_sources} custom sources. Please remove some before adding new ones.", "error")
            return redirect(url_for('main.sources'))
        
        name = request.form.get("name", "").strip()
        source_url = request.form.get("source_url", "").strip()
        source_type = request.form.get("source_type", "").strip()
        
        if not name or not source_url or not source_type:
            flash("All fields are required.", "error")
            return render_template("add_source.html", 
                                 current_count=current_source_count, 
                                 max_sources=max_sources)
        
        try:
            # Create new source
            new_source = UserSource(
                user_id=current_user.id,
                name=name,
                source_url=source_url,
                source_type=source_type
            )
            db.session.add(new_source)
            db.session.commit()
            
            flash(f"Successfully added '{name}' to your custom sources!", "success")
            return redirect(url_for('main.sources'))
            
        except ValueError as e:
            flash(str(e), "error")
            return render_template("add_source.html", 
                                 current_count=current_source_count, 
                                 max_sources=max_sources)
        except Exception as e:
            flash("An error occurred while adding the source. Please try again.", "error")
            current_app.logger.error(f"Error adding source: {e}")
            return render_template("add_source.html", 
                                 current_count=current_source_count, 
                                 max_sources=max_sources)
    
    return render_template("add_source.html", 
                         current_count=current_source_count, 
                         max_sources=max_sources)


@main_bp.route("/sources/<int:source_id>/delete", methods=["POST"])
@login_required
def delete_source(source_id):
    """Delete a custom YouTube source."""
    if not current_user.has_active_subscription:
        flash("Access denied.", "error")
        return redirect(url_for('main.dashboard'))
    
    source = UserSource.query.filter_by(id=source_id, user_id=current_user.id).first()
    if not source:
        flash("Source not found.", "error")
        return redirect(url_for('main.sources'))
    
    try:
        db.session.delete(source)
        db.session.commit()
        flash(f"Successfully deleted '{source.name}'.", "success")
    except Exception as e:
        flash("An error occurred while deleting the source.", "error")
        current_app.logger.error(f"Error deleting source: {e}")
    
    return redirect(url_for('main.sources'))


@main_bp.route("/sources/<int:source_id>/toggle", methods=["POST"])
@login_required
def toggle_source(source_id):
    """Toggle a custom YouTube source active/inactive."""
    if not current_user.has_active_subscription:
        flash("Access denied.", "error")
        return redirect(url_for('main.dashboard'))
    
    source = UserSource.query.filter_by(id=source_id, user_id=current_user.id).first()
    if not source:
        flash("Source not found.", "error")
        return redirect(url_for('main.sources'))
    
    try:
        source.is_active = not source.is_active
        db.session.commit()
    except Exception as e:
        flash("An error occurred while updating the source.", "error")
        current_app.logger.error(f"Error toggling source: {e}")
    
    return redirect(url_for('main.sources'))


@main_bp.route("/terms")
def terms():
    """Terms of Service page."""
    return render_template("legal/terms.html")


@main_bp.route("/privacy")
def privacy():
    """Privacy Policy page."""
    return render_template("legal/privacy.html")


@main_bp.route("/history")
@login_required
def history():
    """View playlist generation history (Pro users only)."""
    if not current_user.has_active_subscription:
        flash("Playlist history is available for Pro subscribers only.", "warning")
        return redirect(url_for('main.dashboard'))
    
    # Get user's generated playlists, ordered by most recent first
    playlists = GeneratedPlaylist.query.filter_by(
        user_id=current_user.id
    ).order_by(GeneratedPlaylist.created_at.desc()).all()
    
    return render_template("history.html", playlists=playlists)


@main_bp.route("/history/<int:playlist_id>")
@login_required
def view_history(playlist_id):
    """View a specific playlist from history."""
    if not current_user.has_active_subscription:
        flash("Playlist history is available for Pro subscribers only.", "warning")
        return redirect(url_for('main.dashboard'))
    
    # Get the playlist
    playlist = GeneratedPlaylist.query.filter_by(
        id=playlist_id,
        user_id=current_user.id
    ).first()
    
    if not playlist:
        flash("Playlist not found.", "error")
        return redirect(url_for('main.history'))
    
    # Decompress the CSV data to get tracks
    try:
        if not playlist.csv_data:
            # Handle old playlists that don't have CSV data
            current_app.logger.warning(f"Playlist {playlist_id} has no CSV data")
            flash("This playlist was created before history tracking was enabled.", "info")
            return redirect(url_for('main.history'))
            
        csv_data = gzip.decompress(
            base64.b64decode(playlist.csv_data.encode('utf-8'))
        ).decode('utf-8')
        
        # Parse CSV to get tracks
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        tracks = []
        for row in csv_reader:
            tracks.append({
                'title': row.get('Title', ''),
                'artist': row.get('Artist', ''),
                'remix': row.get('Remix', ''),
                'source': row.get('Source', ''),
                'url': row.get('URL', '')
            })
        
        # Create a mock task object for the status template
        task = {
            'id': f'history_{playlist_id}',
            'status': 'completed',
            'progress': 100,
            'playlist_name': playlist.name,
            'description': playlist.description,
            'genre': playlist.source_channel,
            'days': playlist.days_analyzed,
            'result': {
                'playlist_name': playlist.name,
                'track_count': playlist.track_count,
                'tracks': tracks,
                'sources_used': [playlist.source_channel],
                'genre': playlist.source_channel,
                'days_searched': playlist.days_analyzed
            },
            'csv_data': csv_data
        }
        
        return render_template('status.html', task_id=task['id'], task=task, is_history=True)
        
    except Exception as e:
        current_app.logger.error(f"Error decompressing playlist data: {e}")
        flash("Error loading playlist data.", "error")
        return redirect(url_for('main.history'))


@main_bp.route("/debug/playlist/<playlist_id>")
@login_required
def debug_playlist(playlist_id):
    """Debug endpoint to test individual YouTube playlists."""
    import os
    from googleapiclient.discovery import build
    
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return jsonify({"error": "No YouTube API key configured"}), 500
    
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        
        # Get playlist info
        playlist_request = youtube.playlists().list(
            part="snippet,contentDetails",
            id=playlist_id
        )
        playlist_response = playlist_request.execute()
        
        if not playlist_response.get("items"):
            return jsonify({"error": "Playlist not found", "playlist_id": playlist_id}), 404
        
        playlist_info = playlist_response["items"][0]
        
        # Get first 20 videos from playlist to see more
        playlist_items_request = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=20
        )
        items_response = playlist_items_request.execute()
        
        videos = []
        for item in items_response.get("items", []):
            videos.append({
                "title": item["snippet"]["title"],
                "published": item["snippet"]["publishedAt"],
                "video_id": item["contentDetails"]["videoId"]
            })
        
        return jsonify({
            "playlist_id": playlist_id,
            "playlist_title": playlist_info["snippet"]["title"],
            "channel": playlist_info["snippet"]["channelTitle"],
            "item_count": playlist_info["contentDetails"]["itemCount"],
            "recent_videos": videos
        })
        
    except Exception as e:
        return jsonify({"error": str(e), "playlist_id": playlist_id}), 500


@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    """Contact form page."""
    from src.flasksaas.forms import ContactForm
    form = ContactForm()
    
    if form.validate_on_submit():
        try:
            # Log the attempt
            current_app.logger.info(f"Contact form submission attempt from {form.email.data}")
            
            # Get mail instance from app extensions
            mail = current_app.extensions.get('mail')
            
            # Log mail configuration (without password)
            current_app.logger.info(f"Mail configured: {mail is not None}")
            if mail:
                current_app.logger.info(f"Mail server: {current_app.config.get('MAIL_SERVER')}")
                current_app.logger.info(f"Mail port: {current_app.config.get('MAIL_PORT')}")
                current_app.logger.info(f"Mail username: {current_app.config.get('MAIL_USERNAME')}")
                current_app.logger.info(f"Mail default sender: {current_app.config.get('MAIL_DEFAULT_SENDER')}")
                current_app.logger.info(f"Mail use TLS: {current_app.config.get('MAIL_USE_TLS')}")
            
            if mail and current_app.config.get('MAIL_USERNAME') and current_app.config.get('MAIL_PASSWORD'):
                # Create email message
                msg = Message(
                    subject=f"[Bright Ears Support] {form.subject.data}",
                    sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'support@brightears.io'),
                    recipients=['support@brightears.io'],
                    reply_to=form.email.data
                )
                
                # Format the email body
                msg.body = f"""
New support message from Bright Ears contact form:

Name: {form.name.data}
Email: {form.email.data}
Subject: {form.subject.data}

Message:
{form.message.data}

---
This message was sent from the Bright Ears contact form.
                """
                
                # Log before sending
                current_app.logger.info(f"Attempting to send email to {msg.recipients} from {msg.sender}")
                
                # Send the email
                mail.send(msg)
                current_app.logger.info(f"Contact form email successfully sent: {form.email.data} - {form.subject.data}")
            else:
                # Fallback: just log if mail is not configured
                missing_config = []
                if not mail:
                    missing_config.append("Mail extension not initialized")
                if not current_app.config.get('MAIL_USERNAME'):
                    missing_config.append("MAIL_USERNAME not set")
                if not current_app.config.get('MAIL_PASSWORD'):
                    missing_config.append("MAIL_PASSWORD not set")
                    
                current_app.logger.warning(f"Mail not fully configured. Missing: {', '.join(missing_config)}")
                current_app.logger.info(f"Contact form submission (not emailed): {form.email.data} - {form.subject.data}")
            
            flash("Thank you for contacting us! We'll get back to you within 24 hours.", "success")
            return redirect(url_for('main.contact'))
            
        except Exception as e:
            current_app.logger.error(f"Failed to send contact form email: {str(e)}")
            current_app.logger.error(f"Error type: {type(e).__name__}")
            import traceback
            current_app.logger.error(f"Traceback: {traceback.format_exc()}")
            flash("Sorry, there was an error sending your message. Please try again later.", "error")
    
    return render_template("contact.html", form=form)
