#!/usr/bin/env python
"""YouTube Playlist CLI

This script provides a command line interface for creating YouTube playlists
from various music sources.
"""
import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

from utils.sources.youtube import YouTubeSource
from utils.destinations.youtube import YouTubeDestination
from utils.sources.traxsource_new import TraxsourceSource
from utils.sources.beatport_rss import BeatportRSSSource
from utils.sources.juno_download import JunoDownloadSource
from playlist_generator import create_playlist

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Create a YouTube playlist from music sources")
    
    parser.add_argument(
        "--name",
        "-n",
        default=f"New Music {datetime.now().strftime('%Y-%m-%d')}",
        help="Playlist name (use {date} for current date)",
    )
    
    parser.add_argument(
        "--description",
        "-d",
        default="Automatically generated playlist of the latest tracks",
        help="Playlist description",
    )
    
    parser.add_argument(
        "--sources",
        "-s",
        nargs="+",
        choices=["youtube", "traxsource", "beatport", "juno"],
        default=["youtube"],
        help="Music sources to fetch tracks from",
    )
    
    parser.add_argument(
        "--genre",
        "-g",
        default="all",
        help="Genre to filter tracks by",
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Number of days to look back for tracks",
    )
    
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=50,
        help="Maximum number of tracks to include",
    )
    
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.7,
        help="Minimum match score (0.0-1.0)",
    )
    
    parser.add_argument(
        "--public",
        action="store_true",
        help="Make the playlist public",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without creating the playlist",
    )
    
    return parser.parse_args()


async def progress_callback(current, total, message=None):
    """Callback function to display progress."""
    if message:
        # Calculate percentage
        percentage = int((current / total) * 100) if total > 0 else 0
        
        # Create progress bar
        bar_length = 30
        filled_length = int(bar_length * current / total) if total > 0 else 0
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        
        # Print progress
        print(f"\r[{bar}] {percentage}% ({current}/{total}) {message}", end="")
        
        # Print newline if complete
        if current == total:
            print()


async def main():
    """Main function."""
    # Parse command line arguments
    args = parse_args()
    
    # Initialize sources
    sources = []
    for source_name in args.sources:
        if source_name == "youtube":
            sources.append(YouTubeSource())
            logger.info("Added YouTube source")
        elif source_name == "traxsource":
            sources.append(TraxsourceSource())
            logger.info("Added Traxsource source")
        elif source_name == "beatport":
            sources.append(BeatportRSSSource())
            logger.info("Added Beatport source")
        elif source_name == "juno":
            sources.append(JunoDownloadSource())
            logger.info("Added Juno Download source")
    
    if not sources:
        logger.error("No valid sources selected")
        return 1
    
    # Initialize destination
    destination = YouTubeDestination()
    logger.info("Using YouTube as destination")
    
    # Authenticate with YouTube
    logger.info("Authenticating with YouTube...")
    authenticated = await destination.authenticate()
    
    if not authenticated:
        logger.error("Failed to authenticate with YouTube")
        return 1
    
    logger.info("Successfully authenticated with YouTube")
    
    # Replace {date} placeholder in playlist name
    today = datetime.now().strftime("%Y-%m-%d")
    name = args.name.replace("{date}", today)
    
    if args.dry_run:
        logger.info("Performing dry run (no playlist will be created)")
        logger.info(f"Would create playlist '{name}' with the following settings:")
        logger.info(f"  Description: {args.description}")
        logger.info(f"  Sources: {', '.join(args.sources)}")
        logger.info(f"  Genre: {args.genre}")
        logger.info(f"  Days to look back: {args.days}")
        logger.info(f"  Track limit: {args.limit}")
        logger.info(f"  Minimum match score: {args.min_score}")
        logger.info(f"  Public: {args.public}")
        
        # Fetch tracks without creating playlist
        all_tracks = []
        
        for source in sources:
            logger.info(f"Fetching tracks from {source.name}...")
            
            try:
                tracks = await source.get_tracks(
                    days_to_look_back=args.days,
                    genre=args.genre,
                    limit=args.limit // len(sources)
                )
                logger.info(f"Found {len(tracks)} tracks from {source.name}")
                all_tracks.extend(tracks)
            except Exception as e:
                logger.error(f"Error fetching tracks from {source.name}: {e}")
        
        logger.info(f"Found {len(all_tracks)} total tracks from all sources")
        
        # Print tracks
        for i, track in enumerate(all_tracks, 1):
            logger.info(f"{i}. {track.artist} - {track.title}")
            if track.remix:
                logger.info(f"   Remix: {track.remix}")
            if track.source_url:
                logger.info(f"   URL: {track.source_url}")
            logger.info("")
        
        return 0
    
    # Create the playlist
    logger.info(f"Creating playlist '{name}'...")
    
    try:
        result = await create_playlist(
            sources=sources,
            destination=destination,
            name=name,
            description=args.description,
            genre=args.genre,
            days_to_look_back=args.days,
            public=args.public,
            limit=args.limit,
            min_match_score=args.min_score,
            progress_callback=progress_callback
        )
        
        if result.success:
            logger.info(f"Playlist created successfully!")
            logger.info(f"URL: {result.playlist_url}")
            logger.info(f"Added {result.tracks_added} tracks")
            return 0
        else:
            logger.error(f"Failed to create playlist: {result.message}")
            return 1
    except Exception as e:
        logger.error(f"Error creating playlist: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))