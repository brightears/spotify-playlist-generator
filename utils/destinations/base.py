"""
Base class for playlist destinations.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

from utils.sources.base import Track


@dataclass
class MatchResult:
    """Represents the result of a track match search."""
    track: Track
    matched: bool
    match_id: str = ""
    match_url: str = ""
    match_name: str = ""
    match_artist: str = ""
    score: float = 0.0
    message: str = ""


@dataclass
class PlaylistResult:
    """Represents the result of playlist creation."""
    success: bool
    playlist_id: str = ""
    playlist_url: str = ""
    tracks_added: int = 0
    message: str = ""
    # Enhanced fields for better reporting
    added_tracks: List[MatchResult] = field(default_factory=list)
    unmatched_tracks: List[MatchResult] = field(default_factory=list)
    csv_data: Optional[str] = None  # Store CSV data for export


class PlaylistDestination(ABC):
    """Abstract base class for playlist destinations."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the destination."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Return a description of the destination."""
        pass
    
    @abstractmethod
    async def authenticate(self, auth_data: Dict[str, Any] = None) -> bool:
        """
        Authenticate with the destination service.
        
        Args:
            auth_data: Optional authentication data
            
        Returns:
            True if authentication was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def create_playlist(
        self, 
        name: str,
        description: str,
        tracks: List[Track],
        public: bool = True,
        min_match_score: float = 0.85,
        progress_callback = None,
        export_unmatched: bool = False
    ) -> PlaylistResult:
        """
        Create a playlist with the given tracks.
        
        Args:
            name: Playlist name
            description: Playlist description
            tracks: List of tracks to add to the playlist
            public: Whether the playlist should be public
            min_match_score: Minimum score required for a track to be considered a match
            progress_callback: Optional callback for progress updates
            export_unmatched: Whether to export unmatched tracks in the result
            
        Returns:
            Result of playlist creation
        """
        pass
    
    @abstractmethod
    async def search_track(self, track: Track) -> MatchResult:
        """
        Search for a track.
        
        Args:
            track: Track to search for
            
        Returns:
            MatchResult with the best match
        """
        pass
    
    @abstractmethod
    async def add_tracks_to_playlist(
        self, 
        playlist_id: str, 
        track_ids: List[str],
        progress_callback = None
    ) -> bool:
        """
        Add tracks to an existing playlist.
        
        Args:
            playlist_id: ID of the playlist
            track_ids: List of track IDs to add
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if all tracks were added successfully, False otherwise
        """
        pass
    
    @staticmethod
    def calculate_title_similarity(title1: str, title2: str) -> float:
        """
        Calculate similarity between two track titles.
        
        Args:
            title1: First title
            title2: Second title
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Clean and normalize titles
        title1 = PlaylistDestination.normalize_title(title1)
        title2 = PlaylistDestination.normalize_title(title2)
        
        # If titles are identical after normalization, return 1.0
        if title1 == title2:
            return 1.0
        
        # Calculate Levenshtein distance
        distance = PlaylistDestination.levenshtein_distance(title1, title2)
        max_length = max(len(title1), len(title2))
        
        # Convert distance to similarity score
        if max_length == 0:
            return 0.0
        
        return 1.0 - (distance / max_length)
    
    @staticmethod
    def calculate_artist_similarity(artist1: str, artist2: str) -> float:
        """
        Calculate similarity between two artist names.
        
        Args:
            artist1: First artist
            artist2: Second artist
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Clean and normalize artist names
        artist1 = PlaylistDestination.normalize_artist(artist1)
        artist2 = PlaylistDestination.normalize_artist(artist2)
        
        # If artist names are identical after normalization, return 1.0
        if artist1 == artist2:
            return 1.0
        
        # Check if one artist name contains the other
        if artist1 in artist2 or artist2 in artist1:
            return 0.9
        
        # Calculate Levenshtein distance
        distance = PlaylistDestination.levenshtein_distance(artist1, artist2)
        max_length = max(len(artist1), len(artist2))
        
        # Convert distance to similarity score
        if max_length == 0:
            return 0.0
        
        return 1.0 - (distance / max_length)
    
    @staticmethod
    def normalize_title(title: str) -> str:
        """
        Normalize a track title for comparison.
        
        Args:
            title: Track title to normalize
            
        Returns:
            Normalized title
        """
        if not title:
            return ""
        
        # Convert to lowercase
        title = title.lower()
        
        # Remove common words and punctuation
        for word in ["official", "video", "audio", "lyric", "lyrics", "ft.", "feat.", "remix", "edit"]:
            title = title.replace(word, "")
        
        # Remove punctuation
        for char in ",.()[]{}!?\"':-;":
            title = title.replace(char, "")
        
        # Remove extra whitespace
        title = " ".join(title.split())
        
        return title
    
    @staticmethod
    def normalize_artist(artist: str) -> str:
        """
        Normalize an artist name for comparison.
        
        Args:
            artist: Artist name to normalize
            
        Returns:
            Normalized artist name
        """
        if not artist:
            return ""
        
        # Convert to lowercase
        artist = artist.lower()
        
        # Remove common words and punctuation
        for word in ["official", "dj", "feat.", "ft."]:
            artist = artist.replace(word, "")
        
        # Remove punctuation
        for char in ",.()[]{}!?\"':-;":
            artist = artist.replace(char, "")
        
        # Remove extra whitespace
        artist = " ".join(artist.split())
        
        return artist
    
    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """
        Calculate the Levenshtein distance between two strings.
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Levenshtein distance
        """
        if len(s1) < len(s2):
            return PlaylistDestination.levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    @classmethod
    def calculate_match_score(cls, track: Track, match_title: str, match_artist: str) -> float:
        """
        Calculate a match score between a track and a potential match.
        
        Args:
            track: Original track
            match_title: Title of the potential match
            match_artist: Artist of the potential match
            
        Returns:
            Match score between 0.0 and 1.0
        """
        # Calculate title similarity (50% of score)
        title_score = cls.calculate_title_similarity(track.title, match_title)
        
        # Calculate artist similarity (50% of score)
        artist_score = cls.calculate_artist_similarity(track.artist, match_artist)
        
        # For electronic music, title is often more distinctive than artist
        # (many remixes, versions, etc) so we give equal weight
        weighted_score = (title_score * 0.5) + (artist_score * 0.5)
        
        # Add bonus for remix consistency
        remix_bonus = 0.0
        if track.remix:
            # Check if the remix info appears in the match title
            if track.remix.lower() in match_title.lower():
                remix_bonus = 0.05
        
        # Return final score with bonus (capped at 1.0)
        return min(1.0, weighted_score + remix_bonus)