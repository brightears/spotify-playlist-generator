"""Main blueprint for core application routes."""
import time
import asyncio
import csv
import io
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app, session, send_file, make_response
from flask_login import login_required, current_user
from flask_wtf.csrf import generate_csrf

# Import the PlaylistForm from the correct location
from src.flasksaas.forms import PlaylistForm
from src.flasksaas.main.task_manager import create_new_task, process_task_step, get_task, get_user_tasks, tasks, TaskManager
from ..models import User, UserSource
from .. import db

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

@main_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    """Create a new playlist."""
    form = PlaylistForm()
    
    if form.validate_on_submit():
        # Create a new task with the form data
        task_id = create_new_task(
            user_id=current_user.id,
            playlist_name=form.name.data,
            description=form.description.data,
            genre=form.genre.data,
            days=form.days.data,
            public=form.public.data,
            source_selection=form.source_selection.data
        )
        
        flash("Playlist creation started! You'll be redirected to track progress.", "success")
        return redirect(url_for('main.status', task_id=task_id))
    
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
    
    # For now, don't require authentication on the API endpoint for debugging
    print(f"Task found: user_id={task['user_id']}, status={task['status']}, step={task['step']}")
    
    # Store pre-processing state for debugging
    pre_status = task['status']
    pre_step = task['step']
    pre_progress = task['progress']
    
    print(f"API status: Task {task_id} before processing - status: {pre_status}, step: {pre_step}, progress: {pre_progress}%")
    
    # If the task is still in progress, advance it by one step
    was_updated = False
    if task['status'] not in ['complete', 'error']:
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
    if task['status'] == 'complete':
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
    if task['status'] not in ['complete', 'error']:
        asyncio.run(process_task_step(task_id))
        task = get_task(task_id)  # Get updated task
    
    return render_template('simple_status.html', task_id=task_id, task=task)

@main_bp.route('/download/<task_id>')
@login_required
def download(task_id):
    """Download playlist results as CSV."""
    # Get task using the task manager
    task = get_task(task_id)
    if not task:
        flash("Task not found.", "error")
        return redirect(url_for('main.dashboard'))
    
    # Check if user owns this task
    if task['user_id'] != current_user.id:
        flash("Access denied.", "error")
        return redirect(url_for('main.dashboard'))
    
    # Check if task is complete
    if task['status'] != 'complete':
        flash("Task is not complete.", "error")
        return redirect(url_for('main.status', task_id=task_id))
    
    # Check if CSV data exists
    if 'csv_data' not in task or not task['csv_data']:
        flash("No CSV data available for this task.", "error")
        return redirect(url_for('main.status', task_id=task_id))
    
    # Create response with CSV data
    response = make_response(task['csv_data'])
    response.headers['Content-Disposition'] = f'attachment; filename=playlist_{task_id}.csv'
    response.headers['Content-Type'] = 'text/csv'
    
    return response


@main_bp.route("/sources")
@login_required
def sources():
    """Manage custom YouTube sources (paid users only)."""
    if not current_user.has_active_subscription:
        flash("Custom sources are available for Pro subscribers only.", "warning")
        return redirect(url_for('main.dashboard'))
    
    user_sources = UserSource.query.filter_by(user_id=current_user.id).order_by(UserSource.created_at.desc()).all()
    return render_template("sources.html", sources=user_sources)


@main_bp.route("/sources/add", methods=["GET", "POST"])
@login_required
def add_source():
    """Add a new custom YouTube source."""
    if not current_user.has_active_subscription:
        flash("Custom sources are available for Pro subscribers only.", "warning")
        return redirect(url_for('main.dashboard'))
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        source_url = request.form.get("source_url", "").strip()
        source_type = request.form.get("source_type", "").strip()
        
        if not name or not source_url or not source_type:
            flash("All fields are required.", "error")
            return render_template("add_source.html")
        
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
            return render_template("add_source.html")
        except Exception as e:
            flash("An error occurred while adding the source. Please try again.", "error")
            current_app.logger.error(f"Error adding source: {e}")
            return render_template("add_source.html")
    
    return render_template("add_source.html")


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
        status = "enabled" if source.is_active else "disabled"
        flash(f"Successfully {status} '{source.name}'.", "success")
    except Exception as e:
        flash("An error occurred while updating the source.", "error")
        current_app.logger.error(f"Error toggling source: {e}")
    
    return redirect(url_for('main.sources'))
