"""
Base class for playlist destinations.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
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
    async def search_track(self, track: Track) -> MatchResult:
        """
        Search for a track in the destination service.
        
        Args:
            track: Track to search for
            
        Returns:
            MatchResult object with match details
        """
        pass
    
    @abstractmethod
    async def create_playlist(
        self, 
        name: str,
        description: str,
        tracks: List[Track],
        public: bool = True,
        min_match_score: float = 0.7,
        progress_callback = None
    ) -> PlaylistResult:
        """
        Create a playlist with the given tracks.
        
        Args:
            name: Name of the playlist
            description: Description of the playlist
            tracks: List of tracks to add to the playlist
            public: Whether the playlist should be public
            min_match_score: Minimum score to consider a track a match
            progress_callback: Optional callback function to report progress
            
        Returns:
            PlaylistResult object with creation details
        """
        pass
    
    @staticmethod
    def calculate_title_similarity(title1: str, title2: str) -> float:
        """Calculate similarity between two track titles."""
        # Normalize titles
        t1 = title1.lower()
        t2 = title2.lower()
        
        # Enhanced cleaning of titles - more thorough for better matching
        # Remove common words, punctuation, and variant spellings
        remove_words = [
            'feat', 'ft', 'featuring', 'presents', 'pres', 'pres.', 
            'original', 'mix', 'remix', 'rmx', 're-work', 'rework', 'refix',
            'extended', 'ext', 'radio', 'edit', 'version', 'vocal', 'instrumental',
            'club', 'dub', '(', ')', '[', ']', '{', '}', '-', ':', '&', '+', '/',
            'official', 'audio', 'music', 'video'
        ]
        
        # Apply replacements
        for word in remove_words:
            t1 = t1.replace(word, ' ')
            t2 = t2.replace(word, ' ')
        
        # Further normalization
        import re
        t1 = re.sub(r'\s+', ' ', t1).strip()  # Replace multiple spaces with single space
        t2 = re.sub(r'\s+', ' ', t2).strip()
        
        # If either title is empty after cleaning, use original titles
        if not t1 or not t2:
            t1 = title1.lower()
            t2 = title2.lower()
        
        # Check for substantial substring matches (helpful for very different formats)
        # This helps when one title is completely contained within another
        if len(t1) > 5 and t1 in t2:
            return 0.9  # High confidence for substring match
        if len(t2) > 5 and t2 in t1:
            return 0.9
        
        # Split into words and count overlaps
        words1 = set(t1.split())
        words2 = set(t2.split())
        
        if not words1 or not words2:
            return 0.0
        
        # Calculate Jaccard similarity with word overlap
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        # Give bonus for consecutive word matches
        word_seq1 = t1.split()
        word_seq2 = t2.split()
        consecutive_matches = 0
        
        for i in range(len(word_seq1) - 1):
            if i < len(word_seq2) - 1 and word_seq1[i] == word_seq2[i] and word_seq1[i+1] == word_seq2[i+1]:
                consecutive_matches += 1
        
        # Base similarity plus bonus for consecutive matches
        base_similarity = intersection / union if union > 0 else 0.0
        consecutive_bonus = 0.1 * consecutive_matches if consecutive_matches > 0 else 0.0
        
        return min(1.0, base_similarity + consecutive_bonus)
    
    @staticmethod
    def calculate_artist_similarity(artist1: str, artist2: str) -> float:
        """Calculate similarity between two artist names."""
        import re
        
        # Normalize artist names
        a1 = artist1.lower()
        a2 = artist2.lower()
        
        # Handle common separators
        for sep in [' & ', ' and ', ', ', '; ', ' x ', ' + ', ' vs ', ' with ', ' feat ', ' ft ']:
            a1 = a1.replace(sep, ', ')
            a2 = a2.replace(sep, ', ')
        
        # Clean up artist names - remove common prefixes/suffixes
        prefixes = ['dj ', 'mc ', 'the ', 'mr ', 'ms ', 'dr ', 'sir ']
        for prefix in prefixes:
            a1 = re.sub(f'^{prefix}', '', a1)
            a2 = re.sub(f'^{prefix}', '', a2)
            
        # Remove special characters and standardize spacing
        a1 = re.sub(r'[^\w\s,]', '', a1)
        a2 = re.sub(r'[^\w\s,]', '', a2)
        a1 = re.sub(r'\s+', ' ', a1).strip()
        a2 = re.sub(r'\s+', ' ', a2).strip()
        
        # Split into individual artists
        artists1 = [a.strip() for a in a1.split(',') if a.strip()]
        artists2 = [a.strip() for a in a2.split(',') if a.strip()]
        
        # Handle empty lists (safeguard)
        if not artists1 or not artists2:
            artists1 = [artist1.lower()]
            artists2 = [artist2.lower()]
        
        # Direct substring matching - check if any artist is a substring of another
        # This helps with abbreviated names or partial matches
        direct_matches = 0
        partial_matches = 0
        
        for artist1 in artists1:
            # Perfect match - exact artist name
            if artist1 in artists2:
                direct_matches += 1
                continue
                
            # Partial match - one artist name contains the other
            for artist2 in artists2:
                # Substantial substring match (at least 4 chars)
                if len(artist1) >= 4 and artist1 in artist2:
                    partial_matches += 0.8  # 80% confidence for substring
                    break
                if len(artist2) >= 4 and artist2 in artist1:
                    partial_matches += 0.8
                    break
                
                # Word-level matching - check if words in artist1 appear in artist2
                words1 = set(artist1.split())
                words2 = set(artist2.split())
                if words1 and words2:
                    overlap = len(words1.intersection(words2))
                    if overlap > 0:
                        # Score based on percentage of matching words
                        word_score = overlap / max(len(words1), len(words2))
                        partial_matches += word_score * 0.7  # 70% confidence for word matching
                        break
        
        # Calculate weighted score - perfect matches are worth more
        direct_match_score = direct_matches / len(artists1) if artists1 else 0
        partial_match_score = partial_matches / len(artists1) if artists1 else 0
        
        # Combine scores with preference for direct matches
        final_score = direct_match_score * 0.7 + partial_match_score * 0.3
        
        return min(1.0, final_score)  # Cap at 1.0
    
    @classmethod
    def calculate_match_score(cls, track: Track, 
                              match_title: str, 
                              match_artist: str) -> float:
        """
        Calculate overall match score between a track and a potential match.
        
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