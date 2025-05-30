"""
Core playlist generation logic.
"""
import asyncio
import logging
import random
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
        PlaylistResult with the result of the playlist creation
    """
    # Define an async function to report progress
    async def report_progress(current, total, message=None):
        if progress_callback:
            await progress_callback(current, total, message)
    
    # Authenticate with the destination
    if not await destination.authenticate():
        raise ValueError(f"Failed to authenticate with {destination.name}")
    
    # Calculate per-source limit
    per_source_limit = limit * 3 // len(sources)  # Get 3x more than needed to account for duplicates and non-matches
    
    # Fetch tracks from all sources
    all_tracks = []
    
    for i, source in enumerate(sources):
        await report_progress(i, len(sources), f"Fetching tracks from {source.name}...")
        
        try:
            # Fetch tracks from the source
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
    
    # Shuffle and limit tracks to respect the limit parameter
    if len(all_tracks) > limit:
        logger.info(f"Limiting tracks from {len(all_tracks)} to {limit}")
        # Shuffle to get a random selection if we have more tracks than the limit
        random.shuffle(all_tracks)
        all_tracks = all_tracks[:limit]
    
    # Create the playlist
    result = await destination.create_playlist(
        name=name,
        description=description,
        tracks=all_tracks,
        public=public,
        min_match_score=min_match_score,
        progress_callback=progress_callback,
        export_unmatched=True  # Always enable CSV export
    )
    
    logger.info(f"Playlist creation result: {result}")
    return result