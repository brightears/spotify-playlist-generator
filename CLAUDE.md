# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Development Commands

### Setup & Environment
```bash
# Quick development setup
./run.sh

# Manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running the Application
```bash
# Development server (main entry point)
python web_app.py
# Serves on http://127.0.0.1:8080
```

### Database Operations
```bash
# Initialize database schema
python db_init.py

# Run database migrations
python migrate_db.py
```

### Testing
```bash
# Run tests (currently has import issues that need fixing)
pytest test_app.py -v

# Quick syntax check
python -c "from web_app import app; print('App loads successfully')"
```

## Architecture Overview

### Blueprint Structure
- **`src/flasksaas/`** - Main SaaS application package using factory pattern
  - **`auth/`** - Authentication (login/register/logout) with Flask-Login + bcrypt
  - **`billing/`** - Stripe subscription management
  - **`main/`** - Core playlist generation functionality 
  - **`models.py`** - SQLAlchemy User model with subscription fields
- **`utils/`** - Plugin architecture for music sources and playlist destinations
  - **`sources/`** - Abstract `MusicSource` base with YouTube, Beatport, etc. implementations
  - **`destinations/`** - Abstract `PlaylistDestination` base with Spotify implementation

### Key Patterns
- **Task Management**: Async playlist generation with in-memory task storage (needs Redis/DB for production)
- **Real-time Updates**: AJAX polling for playlist creation progress at `/api/status/<task_id>`
- **Plugin Architecture**: Extensible source/destination system with abstract base classes
- **Authentication Flow**: Flask-Login + OAuth integration for Spotify API access

### Entry Points
- **`web_app.py`** - Main Flask application with blueprint registration
- **Database**: SQLite at `spotify_playlists.db` (configurable via `DATABASE_URL`)

## Environment Configuration

Required `.env` file:
```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
YOUTUBE_API_KEY=your_api_key
FLASK_SECRET_KEY=your_secret_key
DATABASE_URL=sqlite:///spotify_playlists.db

# Google OAuth (optional - for Gmail login)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
```

## Current Branch Context

On `auth-rebuild` branch - migrating from simple Flask app to full SaaS architecture:
- User authentication and subscription system being implemented
- Blueprint modularization in progress
- Many untracked files from the restructuring

## Testing & Quality

- No linting/formatting tools configured (no Black, flake8, etc.)
- Basic pytest setup but tests currently broken due to import issues
- No Flask-Migrate despite being in requirements - uses manual migration scripts
- CSRF protection temporarily disabled for development (`WTF_CSRF_ENABLED = False`)

## Development Notes

- Application uses SQLite for development, easily configurable for production databases
- Task system stores playlist generation status in memory - should be moved to persistent storage
- Real-time progress tracking implemented via background threads and AJAX polling
- Multiple template directories due to blueprint restructuring - consolidation may be needed