"""
Core playlist generation logic.
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable

from utils.sources.base import MusicSource, Track
from utils.destinations.base import PlaylistDestination, PlaylistResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_playlist(
    sources: List[MusicSource],
    destination: PlaylistDestination,
    name: str,
    description: str,
    genre: str = "all",
    days_to_look_back: int = 14,
    public: bool = True,
    limit: int = 100,
    min_match_score: float = 0.7,
    progress_callback: Optional[Callable] = None
) -> PlaylistResult:
    """
    Create a playlist by fetching tracks from sources and adding them to the destination.
    
    Args:
        sources: List of MusicSource objects to fetch tracks from
        destination: PlaylistDestination object to create the playlist on
        name: Name of the playlist
        description: Description of the playlist
        genre: Genre to filter tracks by
        days_to_look_back: Number of days to look back for tracks
        public: Whether the playlist should be public
        limit: Maximum number of tracks to include
        min_match_score: Minimum score to consider a track a match
        progress_callback: Optional callback function to report progress
        
    Returns:
        PlaylistResult object with creation details
    """
    if not sources:
        raise ValueError("No sources provided")
    
    if not destination:
        raise ValueError("No destination provided")
    
    # Helper function to report progress
    async def report_progress(current, total, message=None):
        if progress_callback:
            await progress_callback(current, total, message)
        else:
            if message:
                logger.info(f"{current}/{total}: {message}")
    
    # Authenticate with the destination
    logger.info(f"Authenticating with {destination.name}...")
    authenticated = await destination.authenticate()
    
    if not authenticated:
        raise ValueError(f"Failed to authenticate with {destination.name}")
    
    logger.info(f"Successfully authenticated with {destination.name}")
    
    # Fetch tracks from sources
    all_tracks = []
    per_source_limit = max(limit // len(sources), 10)  # Ensure at least 10 per source
    
    for i, source in enumerate(sources):
        logger.info(f"Fetching tracks from {source.name} ({i+1}/{len(sources)})...")
        await report_progress(i, len(sources), f"Fetching tracks from {source.name}...")
        
        try:
            tracks = await source.get_tracks(
                days_to_look_back=days_to_look_back,
                genre=genre,
                limit=per_source_limit
            )
            
            # Add source information to each track
            for track in tracks:
                track.source = source.name
            
            logger.info(f"Found {len(tracks)} tracks from {source.name}")
            all_tracks.extend(tracks)
        except Exception as e:
            logger.error(f"Error fetching tracks from {source.name}: {e}", exc_info=True)
            await report_progress(i, len(sources), f"Error fetching tracks from {source.name}: {e}")
    
    if not all_tracks:
        raise ValueError("No tracks found from any source")
    
    logger.info(f"Found {len(all_tracks)} total tracks from all sources")
    
    # Create the playlist
    result = await destination.create_playlist(
        name=name,
        description=description,
        tracks=all_tracks,
        public=public,
        min_match_score=min_match_score,
        progress_callback=progress_callback
    )
    
    logger.info(f"Playlist creation result: {result}")
    return result