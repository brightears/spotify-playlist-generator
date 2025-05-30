# Spotify Playlist Generator from YouTube

## Project Repository

This project is available on GitHub at: https://github.com/brightears/spotify-playlist-generator

To clone the repository:
```bash
git clone https://github.com/brightears/spotify-playlist-generator.git
```

## Overview

This application automates playlist creation by fetching tracks from YouTube music channels and playlists, then creating playlists on Spotify. The application provides a clean web interface for easy configuration and tracks the matching process, providing clear feedback on matched and unmatched tracks.

## Key Features

- **YouTube as Source**: Extracts tracks from curated YouTube channels and playlists across different genres
- **Spotify Integration**: Creates playlists directly on your Spotify account
- **Smart Track Matching**: Intelligently matches YouTube tracks with Spotify's catalog
- **Track Summary**: Clear display of matched vs. unmatched tracks
- **CSV Export**: Export matched and unmatched tracks to CSV for further analysis
- **User-friendly Interface**: Simple web interface with progress tracking and feedback

## Supported Platforms

### Source
- **YouTube**: Extracts tracks from channels and playlists across multiple genres

### Destination
- **Spotify**: Creates playlists via Spotify Web API

## Quick Start

### Setup
1. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the project root directory with your API credentials:
   ```
   # Spotify API Credentials
   SPOTIFY_CLIENT_ID=your_client_id
   SPOTIFY_CLIENT_SECRET=your_client_secret
   
   # YouTube API Credentials
   YOUTUBE_API_KEY=your_api_key
   ```

### API Setup

#### Spotify Setup
1. Create a Spotify Developer App at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Add `http://127.0.0.1:8888/callback` as a Redirect URI
3. Copy your Client ID and Client Secret to the `.env` file
4. When you first run the application, it will guide you through the OAuth authentication process

#### YouTube Setup
1. Create a Google Cloud project and enable the YouTube Data API v3
2. Create an API Key (see [YouTube Setup Guide](docs/youtube_setup.md) for detailed instructions)
3. Add your YouTube API Key to the `.env` file

## Usage

### Web Interface

1. Start the web server:
   ```bash
   source venv/bin/activate
   python3 web_app.py
   ```

2. Open your browser and navigate to `http://127.0.0.1:8080`

3. Fill in the playlist form:
   - **Playlist Name**: Name for your Spotify playlist
   - **Description**: Description for your playlist
   - **Genre**: Select a music genre (house, deep-house, nu-disco, or all)
   - **Days to Look Back**: How many days of YouTube content to include
   - **Public Playlist**: Whether the playlist should be public or private

4. Click "Create Playlist" to begin the process

5. Track the progress on the status page:
   - View real-time updates as tracks are found and matched
   - See the final summary of matched and unmatched tracks
   - Open the created playlist directly in Spotify
   - Download a CSV file with all track details

### Command Line Interface

While the web interface is the recommended way to use the application, a command-line interface is also available for advanced users:

```bash
# Create a Spotify playlist from YouTube tracks
python cli.py create-playlist --name "My YouTube Playlist" --description "Great tracks from YouTube" --genre "house" --days 7
```

## Recent Improvements

### Streamlined for YouTube Source
- **Focus on Quality**: Application now exclusively uses YouTube as the track source for improved reliability
- **Simplified Interface**: Removed unnecessary source selection and track limit fields
- **Enhanced Matching**: Improved track matching algorithm with Spotify

### Added CSV Export Functionality
- **Track Reporting**: Export both matched and unmatched tracks to CSV for further analysis
- **Data Consistency**: CSV reports accurately reflect which tracks were matched and added to the playlist

### Improved User Experience
- **Real-time Updates**: Status page shows live progress as tracks are processed
- **Clear Summaries**: Easy-to-understand summaries of matched vs. unmatched tracks
- **Enhanced Feedback**: Waiting messages and progress indicators for better user experience
- **Direct Access**: Open created playlists directly in Spotify with a single click

## Project Structure

```
.
├── cli.py                 # Command-line interface
├── web_app.py             # Web application (Flask)
├── playlist_generator.py  # Core playlist generation logic
├── utils/
│   ├── sources/          # Track source implementations
│   │   ├── base.py       # Base classes for track sources
│   │   └── youtube.py    # YouTube implementation
│   └── destinations/     # Playlist destination implementations
│       ├── base.py       # Base classes for playlist destinations
│       └── spotify.py    # Spotify implementation
├── templates/            # HTML templates for web interface
│   ├── index.html        # Main form page
│   └── status.html       # Playlist creation status page
└── static/               # Static assets (CSS, JS, images)
```

## Contributing

Contributions are welcome! If you'd like to contribute, please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

<!-- explainer: Updated README to reflect streamlined application with YouTube as exclusive source, added sections for recent improvements, and included clear user instructions -->