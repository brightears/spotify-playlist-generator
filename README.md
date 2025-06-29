# Bright Ears - Music Discovery Platform

## Project Repository

This project is available on GitHub at: https://github.com/brightears/spotify-playlist-generator

To clone the repository:
```bash
git clone https://github.com/brightears/spotify-playlist-generator.git
```

## Overview

Bright Ears is a music discovery platform that helps DJs and music enthusiasts find fresh tracks from YouTube channels. Instead of creating playlists directly (which has API limitations), it provides one-click search links to find tracks on your preferred music platform.

## Key Features

- **YouTube Track Discovery**: Scans curated YouTube channels for the latest music
- **Multi-Platform Search**: One-click search on Spotify, Tidal, YouTube Music, Beatport, and Traxsource
- **Multiple Export Formats**: Download playlists as CSV, M3U, or JSON
- **Custom Sources**: Pro users can add their own YouTube channels/playlists
- **No API Limits**: Works for unlimited users without platform restrictions
- **SaaS Architecture**: User accounts, subscriptions, and custom sources

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
   
   # Email (for contact form)
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
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

### For Pro Users

- Add custom YouTube channels/playlists as sources
- Access all export formats
- Priority support

## Architecture

### Tech Stack
- **Backend**: Flask, SQLAlchemy, Flask-Login
- **Frontend**: Jinja2 templates, Tailwind CSS, jQuery
- **Database**: PostgreSQL (production) / SQLite (development)
- **Authentication**: Google OAuth 2.0
- **Payments**: Stripe subscriptions
- **Task Queue**: In-memory with database persistence
- **Deployment**: Render.com with custom domain

### Key Components

```
src/flasksaas/
├── auth/          # Authentication (Google OAuth)
├── billing/       # Stripe subscription management
├── main/          # Core functionality
│   └── task_manager.py  # Async task processing
├── models.py      # Database models
└── forms.py       # WTForms

utils/
├── sources/       # Music source plugins
│   └── youtube.py # YouTube channel scanner
└── destinations/  # (Removed - no longer needed)

templates/         # Jinja2 templates
static/           # CSS, JavaScript, images
```

## Why No Direct Playlist Creation?

We discovered that Spotify's API requires 250,000 monthly active users for extended access. Their development mode only allows 25 manually added users. Rather than limit our platform, we pivoted to a music discovery model that:

- Works for unlimited users
- Requires no playlist API access
- Lets users choose their preferred platform
- Provides multiple export formats

## Deployment

The application is deployed on Render.com:

1. Connect your GitHub repository to Render
2. Set all environment variables
3. Use the build command: `pip install -r requirements.txt`
4. Use the start command: `gunicorn web_app:app`
5. Add a PostgreSQL database
6. Set up your custom domain

## Recent Changes (December 2024)

- Removed Spotify OAuth integration due to API limitations
- Added multi-platform search links for each track
- Implemented multiple export formats (CSV, M3U, JSON)
- Enhanced rate limiting for production
- Added database storage for tasks
- Improved error handling and user feedback

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.