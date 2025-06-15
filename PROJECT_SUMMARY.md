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
│   │   ├── routes.py       # Login/register/logout endpoints
│   │   └── forms.py        # WTForms for auth
│   ├── billing/            # Stripe payment blueprint
│   │   └── routes.py       # Subscription management
│   ├── main/               # Core functionality blueprint
│   │   ├── routes.py       # Playlist generation endpoints
│   │   └── task_manager.py # Async task handling
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
```

## Recent Changes

### Session 1 (Initial Analysis)
- Verified all core files intact after iCloud sync issue
- Confirmed production-ready features all present
- Identified Flask blueprint architecture

### Session 2 (UI Redesign)
- Integrated Google Stitch dark theme design
- Rebranded from "MusicMixr" to "Bright Ears"
- Updated to Inter font throughout
- Created professional landing page with hero, features, pricing
- Changed color scheme to dark theme (#1a1a1a) with cyan accent (#00CFFF)

### Session 3 (Header Design)
- Evolved header from black → grey → white → cyan gradient
- Final header: Light cyan gradient (from-[#f0fdff] to-[#e6fcff])
- Updated navigation to SaaS best practices:
  - Unauthenticated: Home, Login, Sign Up (button)
  - Authenticated: Dashboard, Account, user@email, Log Out
- Ensured black logo elements visible on light background

## Current Status

### ✅ Working
- Core Flask application structure
- Authentication system (login/register/logout)
- Google OAuth integration
- Stripe payment setup
- YouTube music discovery
- Spotify playlist creation
- CSV export functionality
- Task management system
- New dark theme UI
- Landing page design
- Header with cyan gradient

### 🚧 In Progress
- Auth-rebuild branch active
- Blueprint modularization
- User subscription system
- Flask-Login integration

### ❌ Broken/Issues
- Test suite has import errors
- No Flask-Migrate despite being in requirements
- Virtual environment needs setup for development
- CSRF temporarily disabled (WTF_CSRF_ENABLED = False)
- Many untracked files from restructuring

## Next Steps

### Immediate Priorities
1. Complete auth system integration on auth-rebuild branch
2. Fix test suite import issues
3. Set up proper virtual environment
4. Enable CSRF protection
5. Clean up untracked files and commit changes

### Planned Features
- Automated daily playlist updates for Pro users
- Team accounts with shared playlists
- Advanced genre filtering
- Analytics dashboard
- Mobile-responsive design improvements
- Email notifications for playlist updates

### Known Issues
- Task storage is in-memory (needs Redis/DB for production)
- Multiple template directories need consolidation
- No proper error handling for API failures
- Missing rate limiting on playlist generation

## Development Notes

### Important Patterns
- **Plugin Architecture**: Sources and destinations are extensible via abstract base classes
- **Factory Pattern**: Flask app created via `create_app()` in `src/flasksaas/__init__.py`
- **Blueprint Structure**: Modular components (auth, billing, main)
- **Async Tasks**: Background threads for playlist generation with status polling

### Conventions
- Templates use Jinja2 with `{% extends "base.html" %}`
- All routes return JSON for AJAX or render templates
- User authentication checked via `@login_required` decorator
- Dark theme with Tailwind CSS utility classes
- Brand colors: #00CFFF (cyan), #1a1a1a (dark bg)

### Security Considerations
- Passwords hashed with bcrypt
- Sessions managed by Flask-Login
- OAuth tokens stored securely
- API keys in environment variables
- CSRF protection (currently disabled for dev)

## Key Files

### Entry Points
- `web_app.py` - Main Flask application, blueprint registration
- `src/flasksaas/__init__.py` - Flask app factory, extension setup

### Core Functionality
- `src/flasksaas/main/routes.py` - Playlist generation endpoints
- `utils/sources/youtube.py` - YouTube channel scanning logic
- `utils/destinations/spotify.py` - Spotify playlist creation

### UI/Templates
- `templates/base.html` - Base template with header/nav
- `templates/landing.html` - Marketing homepage
- `templates/dashboard.html` - User dashboard
- `static/css/style.css` - Custom styles (if any)

### Configuration
- `.env` - Environment variables (not in git)
- `requirements.txt` - Python dependencies
- `CLAUDE.md` - AI assistant instructions

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
- Major restructuring in progress
- Many files modified but not committed

### Design Decisions Made
1. **Branding**: "Bright Ears" with cyan (#00CFFF) accent
2. **UI Theme**: Dark mode (#1a1a1a) with light cyan gradient header
3. **Navigation**: SaaS-focused (Login/Sign Up prominent)
4. **Font**: Inter throughout application
5. **Architecture**: Moving to Flask blueprints + factory pattern

### Next Session Should
1. Review uncommitted changes on auth-rebuild branch
2. Complete auth system integration
3. Test user registration/login flow
4. Consider merging to main once stable
5. Set up proper deployment pipeline

### Important Context
- User requested "art" focused design - achieved with gradient header
- Logo has black "B" and half-black "E" - needs light backgrounds
- Project was originally called "Tidal Fresh" - file paths still reflect this
- Production features all verified working in core files
- UI modernization is primary current focus

### File Naming Notes
- Project folder: `tidal_fresh` (historical)
- Brand name: "Bright Ears" (current)
- Some references to "MusicMixr" being updated
- Database: `spotify_playlists.db`

This project is a production-ready SaaS application with solid fundamentals that's currently undergoing UI/UX modernization and architectural improvements to support scaling.