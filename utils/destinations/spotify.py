"""
Spotify implementation of the PlaylistDestination interface.
"""
import os
import re
import json
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import aiohttp
from utils.sources.base import Track
from utils.destinations.base import PlaylistDestination, MatchResult, PlaylistResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SpotifyDestination(PlaylistDestination):
    """Creates playlists on Spotify."""
    
    API_BASE_URL = "https://api.spotify.com/v1"
    AUTH_FILE_PATH = os.path.expanduser("~/.spotify_auth.json")
    
    def __init__(self):
        self.auth_data = None
    
    @property
    def name(self) -> str:
        return "Spotify"
    
    @property
    def description(self) -> str:
        return "Creates playlists on Spotify using the Spotify Web API"
    
    async def authenticate(self, auth_data: Dict[str, Any] = None) -> bool:
        """
        Authenticate with Spotify.
        
        Args:
            auth_data: Optional authentication data. If not provided, 
                       will try to load from AUTH_FILE_PATH.
        
        Returns:
            True if authentication was successful, False otherwise.
        """
        if auth_data:
            self.auth_data = auth_data
            return True
        
        try:
            # Try to load auth data from file
            with open(self.AUTH_FILE_PATH, 'r') as f:
                self.auth_data = json.load(f)
            
            # Check if token is expired
            expires_at = self.auth_data.get('expires_at', 0)
            if expires_at < datetime.now().timestamp():
                logger.info("Spotify token is expired, refreshing...")
                await self._refresh_token()
            
            return True
        except FileNotFoundError:
            logger.error(f"Spotify auth file not found at {self.AUTH_FILE_PATH}")
            return False
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in Spotify auth file")
            return False
        except Exception as e:
            logger.error(f"Error authenticating with Spotify: {e}")
            return False
    
    async def _refresh_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        refresh_token = self.auth_data.get('refresh_token')
        client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
        
        if not refresh_token or not client_id or not client_secret:
            logger.error("Missing refresh token or client credentials")
            return False
        
        try:
            auth_str = f"{client_id}:{client_secret}"
            import base64
            auth_header = base64.b64encode(auth_str.encode()).decode()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://accounts.spotify.com/api/token",
                    headers={
                        "Authorization": f"Basic {auth_header}",
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token
                    }
                ) as response:
                    if response.status != 200:
                        logger.error(f"Error refreshing token: {response.status}")
                        return False
                    
                    data = await response.json()
                    self.auth_data['access_token'] = data['access_token']
                    self.auth_data['expires_at'] = datetime.now().timestamp() + data['expires_in']
                    
                    # Save updated token
                    with open(self.AUTH_FILE_PATH, 'w') as f:
                        json.dump(self.auth_data, f)
                    
                    return True
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return False
    
    async def search_track(self, track: Track) -> MatchResult:
        """
        Search for a track on Spotify.
        
        Args:
            track: Track to search for
            
        Returns:
            MatchResult object with match details
        """
        if not hasattr(self, 'auth_data'):
            raise ValueError("Not authenticated. Call authenticate() first.")
        
        # Special handling for Traxsource tracks
        if track.source == "Traxsource":
            return await self._search_traxsource_track(track)
            
        # Clean up the track title and artist for better matching
        title = track.title
        artist = track.artist
        
        # Build search query
        if track.remix:
            query = f"track:{title} artist:{artist} {track.remix}"
        else:
            query = f"track:{title} artist:{artist}"
        
        # URL encode the query
        encoded_query = query.replace(":", "%3A").replace(" ", "%20")
        url = f"{self.API_BASE_URL}/search?q={encoded_query}&type=track&limit=10"
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.auth_data['access_token']}"}
            
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return MatchResult(
                        track=track,
                        matched=False,
                        message=f"Spotify API error: {response.status}"
                    )
                
                data = await response.json()
            
            # Process results
            tracks = data.get("tracks", {}).get("items", [])
            if not tracks:
                return MatchResult(
                    track=track,
                    matched=False,
                    message="No matching tracks found on Spotify"
                )
            
            # Find the best match
            best_match = None
            best_score = 0.0
            
            for spotify_track in tracks:
                spotify_title = spotify_track["name"]
                spotify_artists = ", ".join([artist["name"] for artist in spotify_track["artists"]])
                
                # Calculate match score
                score = self.calculate_match_score(track, spotify_title, spotify_artists)
                
                if score > best_score:
                    best_score = score
                    best_match = spotify_track
            
            # If we found a good match, return it
            if best_match and best_score >= 0.7:
                return MatchResult(
                    track=track,
                    matched=True,
                    match_id=best_match["id"],
                    match_url=best_match["external_urls"]["spotify"],
                    match_name=best_match["name"],
                    match_artist=", ".join([artist["name"] for artist in best_match["artists"]]),
                    score=best_score,
                    message=f"Found match with score {best_score:.2f}"
                )
            
            return MatchResult(
                track=track,
                matched=False,
                message=f"No good matches found (best score: {best_score:.2f})"
            )
    
    async def _search_traxsource_track(self, track: Track) -> MatchResult:
        """Special search method optimized for Traxsource tracks.
        
        Electronic music from Traxsource often has different naming conventions than on Spotify.
        This method tries multiple search approaches to maximize the chances of finding matches.
        """
        import re
        
        # Extract the base title and mix info
        title = track.title
        
        # Common patterns for mix types in parentheses
        mix_pattern = r'\((.*?(?:mix|edit|remix|version|dub).*?)\)'
        mix_match = re.search(mix_pattern, title, re.IGNORECASE)
        
        if mix_match:
            base_title = title[:mix_match.start()].strip()
            mix_type = mix_match.group(1).strip()
        else:
            base_title = title
            mix_type = None
        
        # Clean up artist names - handle variations like "E-Man" vs "Eman"
        artist = track.artist
        clean_artist = re.sub(r'[-\\s]+', ' ', artist).strip()
        
        # Split artist field if multiple artists
        artist_list = [a.strip() for a in artist.split(',')]
        primary_artist = artist_list[0] if artist_list else artist
        
        # Build search queries
        search_attempts = []
        
        # 1. Try exact match first (with mix type)
        if mix_type:
            search_attempts.append(f'track:"{title}" artist:"{primary_artist}"')
            search_attempts.append(f'"{title}" "{artist}"')
        
        # 2. Try base title with artist
        search_attempts.append(f'track:"{base_title}" artist:"{primary_artist}"')
        search_attempts.append(f'"{base_title}" "{artist}"')
        
        # 3. Try with cleaned artist names (handles E-Man vs Eman)
        if clean_artist != artist:
            search_attempts.append(f'"{base_title}" "{clean_artist}"')
        
        # 4. Try just the base title
        search_attempts.append(f'track:"{base_title}"')
        
        # 5. Try a general search
        search_attempts.append(f'"{base_title}" {primary_artist}')
        
        best_match = None
        best_score = 0.0
        best_spotify_track = None
        
        # Try each search approach
        for query in search_attempts:
            encoded_query = query.replace('"', '%22').replace(":", "%3A").replace(" ", "%20")
            url = f"{self.API_BASE_URL}/search?q={encoded_query}&type=track&limit=20"
            
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.auth_data['access_token']}"}
                
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        continue
                    
                    data = await response.json()
                
                # Process results
                tracks = data.get("tracks", {}).get("items", [])
                if not tracks:
                    continue
                
                # Evaluate each track
                for spotify_track in tracks:
                    spotify_title = spotify_track["name"]
                    spotify_artists = ", ".join([artist["name"] for artist in spotify_track["artists"]])
                    
                    # Custom scoring for Traxsource tracks
                    score = self._calculate_traxsource_match_score(
                        track, base_title, mix_type, spotify_title, spotify_artists
                    )
                    
                    # Add popularity bonus
                    popularity_bonus = min(0.05, spotify_track.get("popularity", 0) / 2000)
                    adjusted_score = score + popularity_bonus
                    
                    if adjusted_score > best_score:
                        best_score = adjusted_score
                        best_spotify_track = spotify_track
                
            # If we found a good match, stop trying
            if best_score > 0.7:
                break
        
        # Return results with very lenient threshold
        if best_spotify_track and best_score > 0.3:
            return MatchResult(
                track=track,
                matched=True,
                match_id=best_spotify_track["id"],
                match_url=best_spotify_track["external_urls"]["spotify"],
                match_name=best_spotify_track["name"],
                match_artist=", ".join([artist["name"] for artist in best_spotify_track["artists"]]),
                score=best_score,
                message=f"Found Traxsource match with score {best_score:.2f}"
            )
        
        return MatchResult(
            track=track,
            matched=False,
            message="No good matches found for Traxsource track"
        )
    
    def _calculate_traxsource_match_score(self, track: Track, base_title: str, 
                                          mix_type: str, spotify_title: str, 
                                          spotify_artists: str) -> float:
        """Calculate match score specifically for Traxsource tracks."""
        import re
        
        # Normalize for comparison
        spotify_title_lower = spotify_title.lower()
        base_title_lower = base_title.lower()
        track_artist_lower = track.artist.lower()
        spotify_artists_lower = spotify_artists.lower()
        
        # Check if base title matches
        title_score = 0.0
        if base_title_lower in spotify_title_lower or spotify_title_lower in base_title_lower:
            title_score = 0.8
        else:
            # Word overlap check
            base_words = set(base_title_lower.split())
            spotify_words = set(spotify_title_lower.split())
            if base_words and spotify_words:
                overlap = len(base_words.intersection(spotify_words))
                title_score = (overlap / len(base_words)) * 0.6
        
        # Check artist match with flexibility for variations
        artist_score = 0.0
        
        # Split artists and normalize
        track_artists = [re.sub(r'[-\\s]+', ' ', a.strip().lower()) for a in track_artist_lower.split(',')]
        spotify_artist_list = [re.sub(r'[-\\s]+', ' ', a.strip().lower()) for a in spotify_artists_lower.split(',')]
        
        # Check each artist
        matched_artists = 0
        for t_artist in track_artists:
            for s_artist in spotify_artist_list:
                # Exact match
                if t_artist == s_artist:
                    matched_artists += 1
                    break
                # Substring match (e.g., "eman" in "e man")
                elif t_artist.replace(' ', '') == s_artist.replace(' ', ''):
                    matched_artists += 1
                    break
                # One contains the other
                elif len(t_artist) > 3 and (t_artist in s_artist or s_artist in t_artist):
                    matched_artists += 0.8
                    break
        
        if track_artists:
            artist_score = matched_artists / len(track_artists)
        
        # Mix type bonus
        mix_bonus = 0.0
        if mix_type and mix_type.lower() in spotify_title_lower:
            mix_bonus = 0.1
        
        # Calculate final score
        final_score = (title_score * 0.5) + (artist_score * 0.4) + mix_bonus
        
        return min(1.0, final_score)
    
    async def create_playlist(
        self, 
        name: str,
        description: str,
        tracks: List[Track],
        public: bool = True,
        min_match_score: float = 0.7,
        progress_callback = None
    ) -> PlaylistResult:
        """Create a playlist on Spotify."""
        if not hasattr(self, 'auth_data'):
            raise ValueError("Not authenticated. Call authenticate() first.")
        
        # Replace {date} placeholder in playlist name
        today = datetime.now().strftime("%Y-%m-%d")
        name = name.replace('{date}', today)
        
        # Get user ID
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.auth_data['access_token']}"}
            
            # Get user profile
            async with session.get(f"{self.API_BASE_URL}/me", headers=headers) as response:
                if response.status != 200:
                    return PlaylistResult(
                        success=False,
                        message=f"Failed to get user profile: {response.status}"
                    )
                
                user_data = await response.json()
                user_id = user_data['id']
            
            # Create playlist
            async with session.post(
                f"{self.API_BASE_URL}/users/{user_id}/playlists",
                headers=headers,
                json={
                    "name": name,
                    "description": description,
                    "public": public
                }
            ) as response:
                if response.status != 201:
                    return PlaylistResult(
                        success=False,
                        message=f"Failed to create playlist: {response.status}"
                    )
                
                playlist_data = await response.json()
                playlist_id = playlist_data['id']
                playlist_url = playlist_data['external_urls']['spotify']
            
            # Search for tracks and add them to the playlist
            matched_track_ids = []
            
            for i, track in enumerate(tracks):
                # Update progress
                if progress_callback:
                    await progress_callback(i, len(tracks), f"Searching for track {i+1}/{len(tracks)}: {track.artist} - {track.title}")
                
                # Search for the track
                match_result = await self.search_track(track)
                
                if match_result.matched and match_result.score >= min_match_score:
                    matched_track_ids.append(match_result.match_id)
                    if progress_callback:
                        await progress_callback(i, len(tracks), f"✅ Found match for {track.artist} - {track.title}")
                else:
                    if progress_callback:
                        await progress_callback(i, len(tracks), f"❌ No match found for {track.artist} - {track.title}")
            
            # Add tracks to playlist in batches
            if not matched_track_ids:
                return PlaylistResult(
                    success=True,
                    playlist_id=playlist_id,
                    playlist_url=playlist_url,
                    tracks_added=0,
                    message="Created empty playlist - no matching tracks found"
                )
            
            # Spotify API allows adding up to 100 tracks at once
            batch_size = 100
            for i in range(0, len(matched_track_ids), batch_size):
                batch = matched_track_ids[i:i+batch_size]
                
                if progress_callback:
                    await progress_callback(i, len(matched_track_ids), f"Adding tracks to playlist ({i+1}-{i+len(batch)}/{len(matched_track_ids)})")
                
                # Add tracks to playlist
                async with session.post(
                    f"{self.API_BASE_URL}/playlists/{playlist_id}/tracks",
                    headers=headers,
                    json={
                        "uris": [f"spotify:track:{track_id}" for track_id in batch]
                    }
                ) as response:
                    if response.status != 201:
                        return PlaylistResult(
                            success=False,
                            playlist_id=playlist_id,
                            playlist_url=playlist_url,
                            tracks_added=i,
                            message=f"Failed to add tracks to playlist: {response.status}"
                        )
            
            return PlaylistResult(
                success=True,
                playlist_id=playlist_id,
                playlist_url=playlist_url,
                tracks_added=len(matched_track_ids),
                message=f"Created playlist with {len(matched_track_ids)} tracks"
            )