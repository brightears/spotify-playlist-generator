# Bright Ears - Professional Music Discovery Platform

## Project Repository

This project is available on GitHub at: https://github.com/brightears/tidal-fresh

To clone the repository:
```bash
git clone https://github.com/brightears/tidal-fresh.git
```

## Overview

Bright Ears is a professional music research and discovery tool built by DJs, for DJs. It automates the process of finding fresh releases from YouTube channels and provides comprehensive export options for your workflow. Instead of creating playlists directly (which has platform limitations), it focuses on discovery with one-click search across all major music platforms.

## Key Features

- **YouTube Track Discovery**: Scans curated YouTube channels for the latest music (1-90 days)
- **Multi-Platform Search**: One-click search on Spotify, Tidal, YouTube Music, Beatport, and Traxsource
- **Multiple Export Formats**: Download track lists as CSV, M3U, or JSON
- **Custom Sources**: Pro users can add and save their own YouTube channels/playlists
- **Playlist History**: Pro users can access and re-download all past discoveries
- **No API Limits**: Works for unlimited users without platform restrictions
- **Professional Workflow**: CSV exports perfect for record shopping on Beatport, Juno, etc.
- **Secure Authentication**: Google OAuth with password reset functionality

## Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL (for production) or SQLite (for development)
- Stripe account (for subscriptions)
- Google OAuth credentials
- YouTube API key

### Setup

1. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Create a `.env` file with your credentials:
   ```env
   # Core Settings
   FLASK_SECRET_KEY=your_secret_key
   DATABASE_URL=sqlite:///spotify_playlists.db
   
   # Google OAuth
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   
   # YouTube API
   YOUTUBE_API_KEY=your_youtube_api_key
   
   # Stripe (for subscriptions)
   STRIPE_SECRET_KEY=your_stripe_secret_key
   STRIPE_PUBLISHABLE_KEY=your_stripe_publishable_key
   STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret
   STRIPE_MONTHLY_PRICE_ID=your_monthly_price_id
   STRIPE_YEARLY_PRICE_ID=your_yearly_price_id
   
   # Email (for contact form and password reset)
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=True
   MAIL_USERNAME=your_email@gmail.com
   MAIL_PASSWORD=your_app_password
   MAIL_DEFAULT_SENDER=support@brightears.io
   ```

3. Initialize the database:
   ```bash
   python db_init.py
   python migrate_playlists.py
   ```

4. Run the application:
   ```bash
   python web_app.py
   ```

5. Visit `http://127.0.0.1:8080`

## Usage

### For Users

1. **Sign Up/Login**: Use Google OAuth to create an account
2. **Create Playlist**: 
   - Choose a genre or YouTube channel
   - Select how many days back to search
   - Click "Create Playlist"
3. **Discover Music**:
   - View found tracks with one-click search links
   - Click platform buttons to search for each track
   - Export the full list in your preferred format

### For Pro Users ($3/month or $24/year)

- Add unlimited custom YouTube channels/playlists as sources
- Access all export formats (CSV, M3U, JSON)
- Playlist history - view and re-download all past discoveries
- Custom sources saved permanently for one-click discovery
- Early access to new features

## Architecture

### Tech Stack
- **Backend**: Flask, SQLAlchemy, Flask-Login, Flask-Mail
- **Frontend**: Jinja2 templates, Tailwind CSS, jQuery
- **Database**: PostgreSQL (production) / SQLite (development)
- **Authentication**: Google OAuth 2.0 + Password-based with reset
- **Payments**: Stripe subscriptions
- **Security**: Flask-Limiter, bcrypt, CSRF protection
- **Task Queue**: In-memory with database persistence
- **Deployment**: Render.com with custom domain

### Key Components

```
src/flasksaas/
├── auth/              # Authentication (Google OAuth)
├── billing/           # Stripe subscription management  
├── main/              # Core functionality
│   ├── routes.py      # Main application routes
│   └── task_manager.py # Async task processing with DB persistence
├── models.py          # Database models (User, GeneratedPlaylist, PlaylistTask)
└── forms.py           # WTForms for playlist creation

utils/
├── sources/           # Music source plugins
│   ├── base.py        # Abstract base class
│   └── youtube.py     # YouTube channel/playlist scanner
└── destinations/      # (Removed - no longer creating playlists)

templates/             # Jinja2 templates with dark theme
static/               # CSS, JavaScript, images
```

## Why Music Discovery Instead of Playlist Creation?

We discovered that Spotify's API requires 250,000 monthly active users for production access. Their development mode only allows 25 manually added users. Rather than limit our platform, we pivoted to a professional music discovery model that:

- Works for unlimited users without restrictions
- Requires no playlist API access or tokens
- Lets DJs use their preferred platform and workflow
- Provides multiple export formats for maximum flexibility
- Focuses on what DJs need most: finding fresh tracks efficiently

## Deployment

The application is deployed on Render.com:

1. Connect your GitHub repository to Render
2. Set all environment variables (see `.env` example above)
3. Use the build command: `pip install -r requirements.txt`
4. Use the start command: `gunicorn web_app:app`
5. Add a PostgreSQL database
6. Set up your custom domain
7. Run migrations after deployment:
   ```bash
   python db_init.py
   python migrate_playlists.py
   python migrate_playlist_history_fix.py  # For nullable Spotify fields
   ```

## Recent Changes (July 2025)

### Password Reset Feature
- Added secure password reset functionality
- Email-based reset with 10-minute token expiration
- Complete dark theme UI integration
- Secure token generation using itsdangerous
- HTML and plain text email support

## Recent Changes (June 2025)

### Major Platform Pivot
- Removed Spotify OAuth integration due to 250k MAU requirement
- Transformed into professional music discovery platform
- Added one-click search links for multiple platforms

### New Features
- **Playlist History**: Pro users can access all past discoveries
- **Persistent Tasks**: Database storage for reliable task handling  
- **Custom Sources**: Add and save your own YouTube channels
- **Export Formats**: CSV (with compression), M3U, and JSON
- **Professional UI**: Dark theme optimized for DJ workflows

### Technical Improvements
- Enhanced rate limiting for production stability
- Migrated to PostgreSQL with proper migrations
- Added gzip compression for playlist storage
- Improved error handling and user feedback
- Fixed task status synchronization issues

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.