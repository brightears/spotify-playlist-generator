# Multi-Source Playlist Generator

## Project Repository

This project is now available on GitHub at: https://github.com/brightears/spotify-playlist-generator

To clone the repository:
```bash
git clone https://github.com/brightears/spotify-playlist-generator.git
```

Automates playlist creation by fetching tracks from multiple sources (Traxsource, Beatport, YouTube) and creating playlists on various platforms (Spotify, YouTube). Features both command-line and web interfaces for easy configuration.

## Supported Platforms

### Sources
- **Traxsource**: Scrapes top charts and new releases
- **Beatport**: Fetches charts via API
- **YouTube**: Extracts tracks from channels and playlists

### Destinations
- **Spotify**: Creates playlists via Web API
- **YouTube**: Creates playlists via Data API

## Quick Start

### Setup
1. `python -m venv venv && source venv/bin/activate`
2. `pip install -r requirements.txt`
3. Set up authentication for your chosen platforms (see below)

### Spotify Setup
1. `cp .env.spotify.sample .env.spotify` → add your **SPOTIFY_CLIENT_ID** & **SPOTIFY_CLIENT_SECRET**
2. Set up a Spotify Developer App at [developer.spotify.com](https://developer.spotify.com/dashboard)
3. Add `http://127.0.0.1:8888/callback` as a Redirect URI
4. Run `python token_exchange.py` to authenticate

### YouTube Setup
1. Follow the [YouTube Setup Guide](docs/youtube_setup.md) to create OAuth credentials
2. Save credentials as `~/.youtube_credentials.json`
3. Add your YouTube API key to `.env`: `YOUTUBE_API_KEY=your_api_key_here`
4. **Important**: Run `python create_youtube_playlist_cli.py` once to complete OAuth authentication
5. After successful authentication, you can use the web interface

**Note**: The web interface requires you to authenticate via the CLI tool first due to OAuth flow limitations.

## Usage

### Command Line Interface
```bash
# Create a Spotify playlist from Traxsource
python create_playlist.py -s traxsource -d spotify -n "House Music {date}"

# Create a YouTube playlist from multiple sources
python create_playlist.py -s traxsource beatport -d youtube --public

# Filter by genre and time period
python create_playlist.py -s traxsource -d spotify -g "Progressive House" --days 7
```

### Web Interface
1. Run `python web_app.py`
2. Open [http://localhost:8080](http://localhost:8080) in your browser
3. Configure your playlist options and click "Generate Playlist"

## Configuration

### Environment Variables
Set these in `.env` or as environment variables:

```
# Required for Spotify
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret

# Required for YouTube
YOUTUBE_API_KEY=your_api_key

# Optional
BEATPORT_CLIENT_ID=your_beatport_client_id
BEATPORT_CLIENT_SECRET=your_beatport_client_secret
```

## Available Music Sources

### Traxsource
Genres: house, deep-house, soulful-house, afro-house, tech-house

### Beatport
Genres: house, techno, tech-house, deep-house, melodic-house-techno

### YouTube
Channels & Playlists:
- Selected Base (House)
- MrRevillz (Deep House)
- Glitterbox (Nu Disco)
- Defected Music (House)

## Key Features

- Multi-source track collection
- Genre filtering
- Date range filtering
- Customizable playlist names
- Public/private playlist options
- Progress tracking
- Web and CLI interfaces

## Contributing

Contributions welcome! Add new sources or destinations by implementing the appropriate interface classes.