"""
Base class for music track sources.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Dict, Any


@dataclass
class Track:
    """Represents a track from any source."""
    title: str
    artist: str
    remix: Optional[str] = None
    release_date: Optional[date] = None
    source: str = ""
    source_url: str = ""
    additional_info: Dict[str, Any] = None


class MusicSource(ABC):
    """Abstract base class for all music sources."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the source."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Return a description of the source."""
        pass
    
    @property
    def available_genres(self) -> List[str]:
        """Return a list of available genres for this source."""
        return []
    
    @abstractmethod
    async def get_tracks(self, days_to_look_back: int = 14, 
                         genre: Optional[str] = None, 
                         limit: int = 100) -> List[Track]:
        """
        Fetch tracks from the source.
        
        Args:
            days_to_look_back: Number of days to look back for tracks
            genre: Optional genre filter
            limit: Maximum number of tracks to return
            
        Returns:
            List of Track objects
        """
        pass