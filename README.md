# Multi-Source Playlist Generator

## Project Repository

This project is now available on GitHub at: https://github.com/brightears/spotify-playlist-generator

To clone the repository:
```bash
git clone https://github.com/brightears/spotify-playlist-generator.git
```

Automates playlist creation by fetching tracks from multiple sources (Traxsource, Beatport, YouTube, Juno Download) and creating playlists on various platforms (Spotify, YouTube). Features both command-line and web interfaces for easy configuration.

## Supported Platforms

### Sources
- **YouTube**: Extracts tracks from channels and playlists
- **Traxsource**: Scrapes top charts and new releases
- **Beatport**: Fetches charts via RSS feeds
- **Juno Download**: Scrapes bestseller charts and new releases

### Destinations
- **Spotify**: Creates playlists via Web API

## Quick Start

### Setup
1. `python -m venv venv && source venv/bin/activate`
2. `pip install -r requirements.txt`
3. `cp .env.example .env` → edit to add your API credentials
4. Set up authentication for your chosen platforms (see below)

### Spotify Setup
1. Set up a Spotify Developer App at [developer.spotify.com](https://developer.spotify.com/dashboard)
2. Add `http://127.0.0.1:8888/callback` as a Redirect URI
3. Add your credentials to the `.env` file:
   ```
   SPOTIFY_CLIENT_ID=your_client_id
   SPOTIFY_CLIENT_SECRET=your_client_secret
   ```
4. Run `python token_exchange.py YOUR_AUTH_CODE` to authenticate

### YouTube Setup
1. Follow the [YouTube Setup Guide](docs/youtube_setup.md) to create API credentials
2. Add your credentials to the `.env` file:
   ```
   YOUTUBE_API_KEY=your_api_key
   ```

## Usage

### Command Line Interface
```bash
# Create a Spotify playlist from YouTube tracks
python create_spotify_playlist.py --sources youtube --name "My YouTube Mix" --days 14 --limit 50

# Advanced options
python create_spotify_playlist.py --sources youtube traxsource --genre deep-house --days 30 --limit 100 --min-score 0.8 --public
```

### Web Interface
1. `python web_app.py` or use the included `./run.sh` script
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
FLASK_SECRET_KEY=generate_a_secure_random_key_here
PORT=8080
```

## Available Music Sources

### Traxsource
Genres: house, deep-house, soulful-house, afro-house, tech-house

### Beatport
Genres: house, techno, tech-house, deep-house, melodic-house, afro-house

### Juno Download
Genres: funky-house, deep-house, disco, drum-and-bass, dancehall

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
- Async processing for non-blocking web requests

## Contributing

Contributions welcome! Add new sources or destinations by implementing the appropriate interface classes.

<!-- explainer: This README provides comprehensive installation and usage instructions, with corrected references to existing files and scripts that match the actual repository structure -->