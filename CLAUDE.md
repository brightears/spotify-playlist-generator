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

# Migration for playlist history (nullable Spotify fields)
python migrate_playlist_history_fix.py
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
- **`utils/`** - Plugin architecture for music sources
  - **`sources/`** - Abstract `MusicSource` base with YouTube, Beatport, etc. implementations
  - **`destinations/`** - (Removed - no longer creating playlists)

### Key Patterns
- **Task Management**: Async playlist generation with database storage (PlaylistTask model)
- **Real-time Updates**: AJAX polling for playlist creation progress at `/api/status/<task_id>`
- **Plugin Architecture**: Extensible source system with abstract base classes
- **Authentication Flow**: Flask-Login + Google OAuth for user authentication
- **Music Discovery**: Focus on finding tracks, not creating playlists directly
- **Playlist History**: GeneratedPlaylist model stores compressed CSV data for Pro users
- **Export System**: Multiple formats with gzip compression for efficient storage

### Entry Points
- **`web_app.py`** - Main Flask application with blueprint registration
- **Database**: SQLite at `spotify_playlists.db` (configurable via `DATABASE_URL`)

## Environment Configuration

Required `.env` file:
```
# Core settings
YOUTUBE_API_KEY=your_api_key
FLASK_SECRET_KEY=your_secret_key
DATABASE_URL=sqlite:///spotify_playlists.db  # PostgreSQL in production

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
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_DEFAULT_SENDER=support@brightears.io

# Legacy Spotify credentials (no longer used, kept for compatibility)
SPOTIFY_CLIENT_ID=not_used
SPOTIFY_CLIENT_SECRET=not_used
```

## Current Branch Context

On `auth-rebuild` branch - Fully functional music discovery platform:
- User authentication via Google OAuth
- Stripe subscription system (Pro Monthly: $3/mo, Pro Yearly: $24/yr)
- Complete pivot from Spotify integration to discovery tool
- Playlist history feature for Pro users
- Multi-format exports with compression
- Professional dark theme UI throughout

## Testing & Quality

- No linting/formatting tools configured (no Black, flake8, etc.)
- Basic pytest setup but tests currently broken due to import issues
- No Flask-Migrate despite being in requirements - uses manual migration scripts
- CSRF protection enabled in production, disabled in development (`WTF_CSRF_ENABLED = IS_PRODUCTION`)

## Development Notes

- Application uses SQLite for development, easily configurable for production databases
- Task system now stores playlist generation status in database (with in-memory cache for performance)
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

### Production Readiness Improvements (Dec 28, 2024)
- **Database Storage**: Playlist tasks now stored in database (PlaylistTask and GeneratedPlaylist models)
- **Enhanced Webhooks**: Added handlers for subscription.created, invoice.payment_failed, invoice.payment_succeeded
- **Rate Limiting**: Implemented Flask-Limiter with sensible defaults:
  - Playlist creation: 10/hour, 3/minute
  - API endpoints: 300/hour, 60/minute
  - Auth endpoints: 20/hour (login), 10/hour (register)
  - Stripe webhooks exempted from limits
- **CSRF Protection**: Re-enabled in production (`WTF_CSRF_ENABLED = IS_PRODUCTION`)

### Recent Changes (Dec 29, 2024 - Part 1)

#### Spotify API Limitations Discovery
- Discovered Spotify requires 250k MAUs for extended API access
- Development mode limited to 25 manually added users
- No paid API tier available for small developers

#### Pivot to Music Discovery Platform
- **Removed Spotify Integration**: Complete removal of OAuth and playlist creation
- **Added Multi-Platform Search**: One-click search links for each track:
  - Spotify, Tidal, YouTube Music, Beatport, Traxsource
- **Multiple Export Formats**: CSV, M3U, JSON
- **Focus Change**: From playlist creation to music discovery
- **No API Limits**: Scalable to unlimited users

### Recent Changes (Dec 29, 2024 - Part 2)

#### Playlist History Feature (Pro Only)
- Implemented GeneratedPlaylist model to store all discovered playlists
- CSV data compressed with gzip and base64 encoded for efficient storage
- Historical playlists viewable and re-downloadable anytime
- Fixed "task not found" error by handling 'history_' prefixed task IDs
- Added migration to make spotify_url and spotify_id nullable

#### UI/UX Improvements
- Changed processing status color from yellow to brand blue (#00CFFF)
- Removed duplicate "Playlist History" link from dashboard
- Updated platform search button colors:
  - Tidal: Black/white theme
  - YouTube: Softer red
  - Beatport: Green styling
  - Traxsource: Blue theme
- Removed redundant flash messages during playlist creation
- Fixed dashboard grid layout (3 columns for Pro users)

#### Bug Fixes
- Fixed status mismatch ('complete' vs 'completed') causing stuck playlists
- Fixed connection errors when viewing historical playlists
- Added is_history flag to prevent polling on historical playlists
- Fixed download functionality for historical playlists

#### Documentation Updates
- Landing page: Complete rewrite removing all Spotify references
- Terms of Service: Updated to reflect music discovery platform
- Privacy Policy: Removed Spotify token collection, clarified data usage
- Added comprehensive FAQ section explaining the platform

### Deployment
- Application deployed on Render.com
- Custom domain: brightears.io
- GitHub integration for automatic deployments
- PostgreSQL database in production
- Environment variables managed in Render dashboard