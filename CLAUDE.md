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

# Google OAuth (required for login)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Stripe (required for subscriptions)
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=your_stripe_publishable_key
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret
STRIPE_MONTHLY_PRICE_ID=your_monthly_price_id
STRIPE_YEARLY_PRICE_ID=your_yearly_price_id

# Email configuration (for contact form)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USE_SSL=False
MAIL_USERNAME=platzer.norbert@gmail.com  # Your Gmail account
MAIL_PASSWORD=your_app_password           # Gmail app-specific password
MAIL_DEFAULT_SENDER=support@brightears.io # Your custom domain email
```

## Current Branch Context

On `auth-rebuild` branch - SaaS architecture with subscription system:
- User authentication fully implemented with Google OAuth
- Stripe subscription system integrated (Pro Monthly: $3/mo, Pro Yearly: $24/yr)
- Blueprint modularization complete
- Subscription UI improvements implemented (Dec 22, 2024)

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

## Recent Changes (Dec 22, 2024)

### Subscription UI Improvements
- Fixed subscription page routing (now uses `/billing/subscription`)
- Removed CSRF token display bug on subscription page
- Implemented proper cancellation flow with confirmation page
- Updated cancelled subscription display to show "Active until [date]"
- Replaced jarring color alerts with subtle dark theme styling
- Added custom sources feature instead of "priority support"
- Profile page now correctly shows cancelled subscription status

### Design System Updates
- Flash messages redesigned with dark theme colors and icons
- Removed yellow/green warning boxes in favor of subtle grays
- Cancel subscription button uses collapsible "Subscription Settings"
- Consistent use of brand color (#00CFFF) for CTAs

### Deployment
- Application deployed on Render.com
- GitHub integration for automatic deployments
- Backup checkpoint created: `v1.0-subscription-ui-complete`