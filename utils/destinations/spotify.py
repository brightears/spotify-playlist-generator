"""
Spotify implementation of the PlaylistDestination interface.
"""
import os
import re
import json
import logging
import asyncio
import csv
import io
import base64
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
            # Check if the token needs to be refreshed
            if self.auth_data.get("expires_at", 0) < datetime.now().timestamp():
                print("DEBUG: Token expired, attempting to refresh...")
                try:
                    await self._refresh_token()
                except Exception as e:
                    print(f"DEBUG: Token refresh failed: {e}")
                    return False
            return True
        
        try:
            # Try to load from existing auth file
            if os.path.exists(self.AUTH_FILE_PATH):
                with open(self.AUTH_FILE_PATH, "r") as f:
                    self.auth_data = json.load(f)
                
                # Check if the token is still valid or needs to be refreshed
                if self.auth_data.get("expires_at", 0) < datetime.now().timestamp():
                    await self._refresh_token()
            
            # If no auth file exists, start the OAuth flow
            if not self.auth_data:
                return await self._start_auth_flow()
            
            return True
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    async def _start_auth_flow(self) -> bool:
        """
        Start the OAuth flow to get an access token.
        """
        client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            logger.error("SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET not set in environment variables")
            return False
        
        # Instructions for manual auth
        print("\n=== Spotify Authentication Required ===")
        print("1. Go to: https://developer.spotify.com/dashboard/applications")
        print("2. Create a new app if you haven't already")
        print("3. Set the redirect URI to 'http://localhost:8080/callback'")
        print("4. Note the Client ID and Client Secret")
        print("5. Set them as environment variables: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET")
        print("6. Restart the application")
        print("=====================================\n")
        
        return False
    
    async def _refresh_token(self) -> bool:
        """
        Refresh an expired access token.
        """
        client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            logger.error("SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET not set in environment variables")
            return False
        
        if not self.auth_data or "refresh_token" not in self.auth_data:
            logger.error("No refresh token available")
            return False
        
        try:
            # Create the auth string and encode it properly
            auth_string = f"{client_id}:{client_secret}"
            auth_bytes = auth_string.encode('ascii')
            base64_auth = base64.b64encode(auth_bytes).decode('ascii')
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://accounts.spotify.com/api/token",
                    headers={
                        "Authorization": f"Basic {base64_auth}",
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self.auth_data["refresh_token"]
                    }
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to refresh token: {response.status}")
                        response_text = await response.text()
                        logger.error(f"Response: {response_text}")
                        return False
                    
                    data = await response.json()
                    
                    self.auth_data["access_token"] = data["access_token"]
                    self.auth_data["expires_at"] = datetime.now().timestamp() + data["expires_in"]
                    
                    # Save updated auth data
                    with open(self.AUTH_FILE_PATH, "w") as f:
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
            MatchResult with the best match
        """
        if not self.auth_data:
            return MatchResult(
                track=track,
                matched=False,
                message="Not authenticated"
            )
        
        # Create search query
        query = f"{track.title} {track.artist}"
        if track.remix:
            query += f" {track.remix}"
        
        # URL-encode the query
        query = query.replace(" ", "%20")
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.auth_data['access_token']}",
                "Content-Type": "application/json"
            }
            
            async with session.get(
                f"{self.API_BASE_URL}/search?q={query}&type=track&limit=5",
                headers=headers
            ) as response:
                if response.status != 200:
                    return MatchResult(
                        track=track,
                        matched=False,
                        message=f"Search failed with status {response.status}"
                    )
                
                data = await response.json()
                
                if "tracks" not in data or "items" not in data["tracks"] or len(data["tracks"]["items"]) == 0:
                    return MatchResult(
                        track=track,
                        matched=False,
                        message="No matching tracks found"
                    )
                
                # Find the best match
                best_match = None
                best_score = 0.0
                
                for item in data["tracks"]["items"]:
                    track_title = item["name"]
                    track_artist = item["artists"][0]["name"] if item["artists"] else ""
                    
                    score = self.calculate_match_score(track, track_title, track_artist)
                    
                    if score > best_score:
                        best_score = score
                        best_match = item
                
                if best_match and best_score >= 0.7:
                    return MatchResult(
                        track=track,
                        matched=True,
                        match_id=best_match["id"],
                        match_url=best_match["external_urls"]["spotify"],
                        match_name=best_match["name"],
                        match_artist=best_match["artists"][0]["name"] if best_match["artists"] else "",
                        score=best_score,
                        message="Match found"
                    )
                else:
                    return MatchResult(
                        track=track,
                        matched=False,
                        score=best_score if best_match else 0.0,
                        message="No good match found"
                    )
    
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
        if not self.auth_data:
            return False
        
        headers = {
            "Authorization": f"Bearer {self.auth_data['access_token']}",
            "Content-Type": "application/json"
        }
        
        # Split track IDs into batches of 100 (Spotify's limit)
        batches = [track_ids[i:i+100] for i in range(0, len(track_ids), 100)]
        
        async with aiohttp.ClientSession() as session:
            for i, batch in enumerate(batches):
                if progress_callback:
                    try:
                        if asyncio.iscoroutinefunction(progress_callback):
                            await progress_callback(i, len(batches), f"Adding tracks batch {i+1}/{len(batches)}")
                        else:
                            progress_callback(i, len(batches), f"Adding tracks batch {i+1}/{len(batches)}")
                    except Exception as e:
                        print(f"DEBUG: Progress callback error: {e}")
                        # Continue without progress callback
                        progress_callback = None
                
                async with session.post(
                    f"{self.API_BASE_URL}/playlists/{playlist_id}/tracks",
                    headers=headers,
                    json={
                        "uris": [f"spotify:track:{track_id}" for track_id in batch]
                    }
                ) as response:
                    if response.status != 201:
                        logger.error(f"Failed to add tracks to playlist: {response.status}")
                        return False
        
        return True
    
    def _generate_csv_data(self, tracks: List[Track], matched_results: List, unmatched_results: List) -> str:
        """Generate CSV data for the playlist tracks."""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Title', 'Artist', 'Source', 'Matched', 'Spotify Title', 
            'Spotify Artist', 'Spotify URL', 'Match Score'
        ])
        
        # Write matched tracks
        for match_result in matched_results:
            writer.writerow([
                match_result.track.title,
                match_result.track.artist,
                getattr(match_result.track, 'source', 'YouTube'),
                'Yes',
                match_result.match_name,
                match_result.match_artist,
                match_result.match_url,
                f"{match_result.score:.2f}"
            ])
        
        # Write unmatched tracks
        for match_result in unmatched_results:
            writer.writerow([
                match_result.track.title,
                match_result.track.artist,
                getattr(match_result.track, 'source', 'YouTube'),
                'No',
                '',
                '',
                '',
                f"{match_result.score:.2f}"
            ])
        
        return output.getvalue()
    
    async def create_playlist(
        self, 
        name: str,
        tracks: List[Track],
        description: str = "",
        public: bool = False,
        min_match_score: float = 0.7,
        progress_callback=None
    ) -> PlaylistResult:
        """
        Create a new playlist on Spotify with the given tracks.
        
        Args:
            name: Name of the playlist
            tracks: List of Track objects to add
            description: Optional description
            public: Whether the playlist should be public
            min_match_score: Minimum match score for tracks (0.0-1.0)
            progress_callback: Optional callback for progress updates
            
        Returns:
            PlaylistResult with success status and details
        """
        print(f"DEBUG: SpotifyDestination.create_playlist called with {len(tracks)} tracks")
        print(f"DEBUG: Auth data available: {bool(self.auth_data)}")
        
        if not self.auth_data:
            print("DEBUG: No auth data - returning failure")
            return PlaylistResult(
                success=False,
                message="Not authenticated"
            )
        
        if progress_callback:
            try:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(0, 100, "Creating playlist...")
                else:
                    progress_callback(0, 100, "Creating playlist...")
            except Exception as e:
                print(f"DEBUG: Progress callback error: {e}")
                # Continue without progress callback
                progress_callback = None
        
        try:
            print("DEBUG: Starting playlist creation process...")
            # Create the playlist
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.auth_data['access_token']}",
                    "Content-Type": "application/json"
                }
                
                print("DEBUG: Getting user profile...")
                # Get user ID
                async with session.get(
                    f"{self.API_BASE_URL}/me",
                    headers=headers
                ) as response:
                    print(f"DEBUG: User profile response status: {response.status}")
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"DEBUG: User profile error: {error_text}")
                        return PlaylistResult(
                            success=False,
                            message=f"Failed to get user profile: {response.status}"
                        )
                    
                    user_data = await response.json()
                    user_id = user_data["id"]
                    print(f"DEBUG: Got user ID: {user_id}")
                
                print("DEBUG: Creating playlist...")
                # Create a new playlist
                async with session.post(
                    f"{self.API_BASE_URL}/users/{user_id}/playlists",
                    headers=headers,
                    json={
                        "name": name,
                        "description": description,
                        "public": public
                    }
                ) as response:
                    print(f"DEBUG: Create playlist response status: {response.status}")
                    if response.status != 201:
                        error_text = await response.text()
                        print(f"DEBUG: Create playlist error: {error_text}")
                        return PlaylistResult(
                            success=False,
                            message=f"Failed to create playlist: {response.status}"
                        )
                    
                    playlist_data = await response.json()
                    playlist_id = playlist_data["id"]
                    playlist_url = playlist_data["external_urls"]["spotify"]
                    print(f"DEBUG: Created playlist {playlist_id} at {playlist_url}")
                
                if progress_callback:
                    try:
                        if asyncio.iscoroutinefunction(progress_callback):
                            await progress_callback(10, 100, f"Playlist created: {name}")
                        else:
                            progress_callback(10, 100, f"Playlist created: {name}")
                    except Exception as e:
                        print(f"DEBUG: Progress callback error: {e}")
                        # Continue without progress callback
                        progress_callback = None
                
                print("DEBUG: Starting track matching...")
                # Match tracks with Spotify
                matched_track_ids = []
                matched_results = []
                unmatched_results = []
                
                for i, track in enumerate(tracks):
                    if i < 3:  # Debug first 3 tracks
                        print(f"DEBUG: Processing track {i+1}: '{track.title}' by '{track.artist}'")
                    
                    if progress_callback:
                        try:
                            if asyncio.iscoroutinefunction(progress_callback):
                                await progress_callback(
                                    10 + int((i / len(tracks)) * 70),
                                    100,
                                    f"Matching track {i+1}/{len(tracks)}: {track.title} by {track.artist}"
                                )
                            else:
                                progress_callback(
                                    10 + int((i / len(tracks)) * 70),
                                    100,
                                    f"Matching track {i+1}/{len(tracks)}: {track.title} by {track.artist}"
                                )
                        except Exception as e:
                            print(f"DEBUG: Progress callback error: {e}")
                            # Continue without progress callback
                            progress_callback = None
                    
                    match_result = await self.search_track(track)
                    
                    if i < 3:  # Debug first 3 results
                        print(f"DEBUG: Track {i+1} match result: matched={match_result.matched}, score={getattr(match_result, 'score', 'N/A')}")
                    
                    # Add to appropriate lists for later CSV generation
                    if match_result.matched and match_result.score >= min_match_score:
                        matched_track_ids.append(match_result.match_id)
                        matched_results.append(match_result)
                    else:
                        unmatched_results.append(match_result)
                
                print(f"DEBUG: Track matching complete. Matched: {len(matched_track_ids)}, Unmatched: {len(unmatched_results)}")
                
                if progress_callback:
                    try:
                        if asyncio.iscoroutinefunction(progress_callback):
                            await progress_callback(80, 100, f"Found {len(matched_track_ids)} matching tracks")
                        else:
                            progress_callback(80, 100, f"Found {len(matched_track_ids)} matching tracks")
                    except Exception as e:
                        print(f"DEBUG: Progress callback error: {e}")
                        # Continue without progress callback
                        progress_callback = None
                
                # Add tracks to playlist
                if matched_track_ids:
                    print(f"DEBUG: Adding {len(matched_track_ids)} tracks to playlist...")
                    success = await self.add_tracks_to_playlist(
                        playlist_id,
                        matched_track_ids,
                        progress_callback=lambda current, total, message: progress_callback(
                            80 + int((current / total) * 15),
                            100,
                            message
                        ) if progress_callback else None
                    )
                    
                    print(f"DEBUG: Add tracks result: {success}")
                    
                    if not success:
                        return PlaylistResult(
                            success=False,
                            playlist_id=playlist_id,
                            playlist_url=playlist_url,
                            message="Failed to add tracks to playlist"
                        )
                else:
                    print("DEBUG: No tracks to add to playlist")
                
                if progress_callback:
                    try:
                        if asyncio.iscoroutinefunction(progress_callback):
                            await progress_callback(100, 100, "Playlist creation complete!")
                        else:
                            progress_callback(100, 100, "Playlist creation complete!")
                    except Exception as e:
                        print(f"DEBUG: Progress callback error: {e}")
                        # Continue without progress callback
                        progress_callback = None
                
                print("DEBUG: Playlist creation successful!")
                
                # Generate CSV data for export
                csv_data = self._generate_csv_data(tracks, matched_results, unmatched_results)
                
                return PlaylistResult(
                    success=True,
                    playlist_id=playlist_id,
                    playlist_url=playlist_url,
                    message=f"Successfully created playlist '{name}' with {len(matched_track_ids)} tracks",
                    added_tracks=matched_results,
                    unmatched_tracks=unmatched_results,
                    csv_data=csv_data
                )
                
        except Exception as e:
            print(f"DEBUG: Exception in create_playlist: {str(e)}")
            import traceback
            print(f"DEBUG: Traceback: {traceback.format_exc()}")
            return PlaylistResult(
                success=False,
                message=f"Error creating playlist: {str(e)}"
            )