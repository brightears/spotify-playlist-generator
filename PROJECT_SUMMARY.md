# PROJECT SUMMARY - Bright Ears (Tidal Fresh)

## Project Overview

**Name**: Bright Ears (formerly MusicMixr/Tidal Fresh)  
**Purpose**: Automated music discovery platform that scans YouTube channels and other music sources to create fresh Spotify playlists  
**Target Users**: DJs, music producers, playlist curators, and music enthusiasts who want to stay current with new releases

### Core Value Proposition
- Discovers fresh music from YouTube channels, Beatport, Traxsource, and other sources
- Automatically matches tracks to Spotify and creates playlists
- Saves hours of manual music discovery work
- Never miss a new release from favorite channels/labels

## Tech Stack

### Backend
- **Python 3.x** - Core language
- **Flask 2.x** - Web framework
- **SQLAlchemy** - ORM for database operations
- **Flask-Login** - User authentication
- **bcrypt** - Password hashing
- **Stripe API** - Payment processing
- **Google OAuth 2.0** - Gmail authentication
- **Spotify Web API** - Playlist creation
- **YouTube Data API v3** - Music discovery
- **aiohttp** - Async HTTP requests

### Frontend
- **Tailwind CSS** - Styling (via CDN)
- **Inter font** - Primary typography
- **Vanilla JavaScript** - Client-side functionality
- **AJAX** - Real-time status updates

### Database
- **SQLite** - Development database
- **PostgreSQL** - Production ready

### Key Dependencies (requirements.txt)
```
Flask==2.3.2
Flask-Login==0.6.2
Flask-WTF==1.1.1
SQLAlchemy==2.0.19
bcrypt==4.0.1
stripe==5.5.0
google-auth==2.22.0
spotipy==2.23.0
google-api-python-client==2.95.0
aiohttp==3.8.5
python-dotenv==1.0.0
```

## Architecture

### Application Structure
```
tidal_fresh/
├── web_app.py              # Main Flask application entry point
├── src/flasksaas/          # Core application package
│   ├── __init__.py         # Flask app factory
│   ├── auth/               # Authentication blueprint
│   │   ├── routes.py       # Login/register/logout + Google OAuth
│   │   └── forms.py        # WTForms for auth
│   ├── billing/            # Stripe payment blueprint
│   │   └── routes.py       # Subscription management
│   ├── main/               # Core functionality blueprint
│   │   ├── routes.py       # Playlist generation endpoints
│   │   └── task_manager.py # Async task handling
│   ├── spotify_routes.py   # Spotify OAuth and playlist creation
│   └── models.py           # SQLAlchemy User model
├── utils/                  # Plugin architecture
│   ├── sources/            # Music source plugins
│   │   ├── base.py         # Abstract MusicSource class
│   │   ├── youtube.py      # YouTube channel scanner
│   │   ├── beatport_rss.py # Beatport RSS feed parser
│   │   └── traxsource_new.py # Traxsource scraper
│   └── destinations/       # Playlist destination plugins
│       ├── base.py         # Abstract PlaylistDestination
│       └── spotify.py      # Spotify playlist creator
└── templates/              # Jinja2 templates
    ├── base.html           # Base template with header/footer
    ├── landing.html        # Marketing landing page
    ├── dashboard.html      # User dashboard
    └── create_playlist.html # Playlist creation form
```

### Data Flow
1. **User Authentication** → Flask-Login + bcrypt/Google OAuth
2. **Source Selection** → User chooses YouTube channels/genres
3. **Music Discovery** → Background task scans sources
4. **Track Matching** → Searches Spotify for discovered tracks
5. **Playlist Creation** → Spotify API creates/updates playlist
6. **Progress Updates** → AJAX polls `/api/status/<task_id>`

### Database Schema
```sql
User:
- id (Integer, Primary Key)
- email (String, Unique)
- password_hash (String)
- created_at (DateTime)
- is_active (Boolean)
- subscription_status (String)
- subscription_id (String)
- subscription_end_date (DateTime)
- spotify_access_token (String)
- spotify_refresh_token (String)
- google_id (String)
```

## Recent Progress (Latest Session - June 15, 2025)

### Authentication System
- Implemented Flask-Login based authentication
- Added User model with bcrypt password hashing
- Created login and registration forms with WTForms
- Built responsive auth templates with Tailwind CSS
- Added session management and user persistence
- **Successfully implemented Google OAuth login**
  - Fixed scope mismatch issues with Google Auth library
  - Added manual token exchange fallback
  - Configured for Render deployment with proper HTTPS redirect URIs

### Deployment & Production
- Fixed jQuery UI dependency issues on status page
- Added CSV download functionality for fetched tracks
- Debugged and fixed Spotify OAuth integration (was using wrong Client ID)
- Successfully deployed to Render at https://spotify-playlist-generator-rcva.onrender.com
- All core features working: YouTube fetch → CSV download → Spotify playlist creation

### Project Structure
- Migrated to Flask factory pattern with blueprints
- Created modular structure: auth, billing, main blueprints
- Set up proper extension initialization
- Maintained compatibility with existing functionality

## Current Status

### Working Features
- ✅ YouTube playlist/video URL parsing and track extraction
- ✅ Track search using YouTube Data API
- ✅ Background task processing with progress tracking
- ✅ User authentication (login/register/logout)
- ✅ Session persistence with "Remember Me"
- ✅ Blueprint-based modular architecture
- ✅ **Google OAuth login integration**
- ✅ **Spotify OAuth integration and playlist creation**
- ✅ **CSV export of fetched tracks**
- ✅ **Full production deployment on Render**

### In Progress
- 🔄 Stripe billing integration (routes created, implementation pending)
- 🔄 User dashboard with playlist history
- 🔄 Email confirmation system

## Next Steps

1. **Implement Billing System**
   - Set up Stripe webhook handlers
   - Create subscription plans (Basic/Pro/Premium)
   - Add payment method management
   - Integrate billing with user dashboard

2. **Enhance User Experience**
   - Add email verification for new accounts
   - Create user profile management page
   - Implement playlist history and management
   - Add ability to edit/delete saved playlists
   - Add social sharing features

3. **Production Improvements**
   - Move task storage from in-memory to Redis/database
   - Add proper error tracking (Sentry)
   - Implement rate limiting
   - Add comprehensive logging
   - Set up automated backups

## Technical Debt

- Move task storage from in-memory to persistent storage (Redis/DB)
- Add comprehensive error handling and logging
- Implement proper CSRF protection (currently disabled)
- Add rate limiting for API endpoints
- Create automated tests (pytest setup exists but tests need fixing)
- Set up CI/CD pipeline
- Configure Flask-Migrate for database migrations (currently using manual scripts)
- Add production-grade session storage (Redis)
- Implement proper secrets management

## Environment Variables (Required for Deployment)

### Render Environment Variables
- `DATABASE_URL`: PostgreSQL connection string (or uses SQLite fallback)
- `SPOTIFY_CLIENT_ID`: Spotify OAuth client ID
- `SPOTIFY_CLIENT_SECRET`: Spotify OAuth client secret
- `SPOTIFY_REDIRECT_URI`: https://your-app.onrender.com/spotify/callback
- `GOOGLE_CLIENT_ID`: Google OAuth client ID (e.g., 240581931156-xxx.apps.googleusercontent.com)
- `GOOGLE_CLIENT_SECRET`: Google OAuth client secret
- `RENDER`: Set to `true` for Render deployment
- `RENDER_EXTERNAL_URL`: Full app URL (e.g., https://spotify-playlist-generator-rcva.onrender.com)
- `YOUTUBE_API_KEY`: YouTube Data API key
- `FLASK_SECRET_KEY`: Secret key for sessions
- `STRIPE_SECRET_KEY`: (When implementing billing)
- `STRIPE_PUBLISHABLE_KEY`: (When implementing billing)
- `STRIPE_WEBHOOK_SECRET`: (When implementing billing)

## Key Files

### Entry Points
- `web_app.py` - Main Flask application, blueprint registration
- `src/flasksaas/__init__.py` - Flask app factory, extension setup

### Core Functionality
- `src/flasksaas/main/routes.py` - Playlist generation endpoints
- `src/flasksaas/auth/routes.py` - Authentication + Google OAuth
- `src/flasksaas/spotify_routes.py` - Spotify OAuth and playlist creation
- `utils/sources/youtube.py` - YouTube channel scanning logic
- `utils/destinations/spotify.py` - Spotify playlist creation

### UI/Templates
- `templates/base.html` - Base template with header/nav
- `templates/landing.html` - Marketing homepage
- `templates/dashboard.html` - User dashboard
- `templates/status.html` - Playlist generation progress page
- `static/css/style.css` - Custom styles (if any)

### Configuration
- `.env` - Environment variables (not in git)
- `requirements.txt` - Python dependencies
- `CLAUDE.md` - AI assistant instructions
- `docs/google_oauth_setup.md` - Google OAuth configuration guide

## Setup Instructions

### Prerequisites
- Python 3.8+
- Spotify Developer Account
- YouTube Data API key
- Stripe Account (for payments)
- Google OAuth credentials (optional)

### Environment Setup
```bash
# Clone repository
git clone [repository-url]
cd tidal_fresh

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
YOUTUBE_API_KEY=your_youtube_api_key
FLASK_SECRET_KEY=your_secret_key
DATABASE_URL=sqlite:///spotify_playlists.db
STRIPE_SECRET_KEY=your_stripe_key
STRIPE_PUBLISHABLE_KEY=your_stripe_pub_key
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
EOF

# Initialize database
python db_init.py

# Run development server
python web_app.py
# Server runs on http://127.0.0.1:8080
```

### Quick Start Script
```bash
./run.sh  # Automated setup and run
```

## Context for Future Sessions

### Current Branch Status
- On `auth-rebuild` branch
- Last commit: "fix: handle Google OAuth scope mismatch error"
- All major features working in production

### What Was Accomplished Today
1. **Fixed playlist creation flow** - Was stuck at "Initializing task..."
2. **Debugged Spotify OAuth** - Wrong Client ID in Render environment
3. **Implemented Google OAuth** - Full setup with Google Cloud Console
4. **Fixed scope mismatch error** - Added fallback token exchange
5. **Added CSV export** - Users can download fetched tracks
6. **Fixed jQuery UI errors** - Replaced with vanilla JavaScript

### Production URLs
- App: https://spotify-playlist-generator-rcva.onrender.com
- Google OAuth Callback: https://spotify-playlist-generator-rcva.onrender.com/auth/google-callback
- Spotify OAuth Callback: https://spotify-playlist-generator-rcva.onrender.com/spotify/callback

### Next Session Should Focus On
1. **Stripe Integration** - Complete billing system
2. **User Dashboard** - Show playlist history
3. **Email Verification** - Add email confirmation flow
4. **Profile Management** - Let users update their info
5. **Redis Integration** - Move tasks to persistent storage

### Important Context
- Google OAuth Client ID: 240581931156-mue123egr4tgo46290heq56c00mnc1n5.apps.googleusercontent.com
- All OAuth integrations working (Google + Spotify)
- Production deployment stable on Render
- Database auto-creates tables on startup
- Task system uses in-memory storage (needs Redis for production scale)

This project is now a fully functional SaaS application with working authentication, OAuth integrations, and playlist generation. The next phase is monetization through Stripe and enhanced user features.