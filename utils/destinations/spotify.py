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
            auth_string = f"{client_id}:{client_secret}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://accounts.spotify.com/api/token",
                    headers={
                        "Authorization": f"Basic {auth_string}",
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self.auth_data["refresh_token"]
                    }
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to refresh token: {response.status}")
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
                    await progress_callback(i, len(batches), f"Adding tracks batch {i+1}/{len(batches)}")
                
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
    
    def _generate_csv_data(self, matched_tracks: List[MatchResult], unmatched_tracks: List[MatchResult]) -> str:
        """
        Generate CSV data for export.
        
        Args:
            matched_tracks: List of matched tracks
            unmatched_tracks: List of unmatched tracks
            
        Returns:
            CSV data as a string
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow([
            "Title", "Artist", "Source", "Matched", "Spotify Title", "Spotify Artist", "Spotify URL", "Match Score"
        ])
        
        # Write matched tracks
        for match in matched_tracks:
            writer.writerow([
                match.track.title,
                match.track.artist,
                match.track.source,
                "Yes",
                match.match_name,
                match.match_artist,
                match.match_url,
                f"{match.score:.2f}"
            ])
        
        # Write unmatched tracks
        for match in unmatched_tracks:
            writer.writerow([
                match.track.title,
                match.track.artist,
                match.track.source,
                "No",
                "",
                "",
                "",
                f"{match.score:.2f}"
            ])
        
        return output.getvalue()
    
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
        if not self.auth_data:
            return PlaylistResult(
                success=False,
                message="Not authenticated"
            )
        
        if progress_callback:
            await progress_callback(0, 100, "Creating playlist...")
        
        try:
            # Create the playlist
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.auth_data['access_token']}",
                    "Content-Type": "application/json"
                }
                
                # Get user ID
                async with session.get(
                    f"{self.API_BASE_URL}/me",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        return PlaylistResult(
                            success=False,
                            message=f"Failed to get user profile: {response.status}"
                        )
                    
                    user_data = await response.json()
                    user_id = user_data["id"]
                
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
                    if response.status != 201:
                        return PlaylistResult(
                            success=False,
                            message=f"Failed to create playlist: {response.status}"
                        )
                    
                    playlist_data = await response.json()
                    playlist_id = playlist_data["id"]
                    playlist_url = playlist_data["external_urls"]["spotify"]
                
                if progress_callback:
                    await progress_callback(10, 100, f"Playlist created: {name}")
                
                # Match tracks with Spotify
                matched_track_ids = []
                matched_results = []
                unmatched_results = []
                
                for i, track in enumerate(tracks):
                    if progress_callback:
                        await progress_callback(
                            10 + int((i / len(tracks)) * 70),
                            100,
                            f"Matching track {i+1}/{len(tracks)}: {track.title} by {track.artist}"
                        )
                    
                    match_result = await self.search_track(track)
                    
                    # Add to appropriate lists for later CSV generation
                    if match_result.matched and match_result.score >= min_match_score:
                        matched_track_ids.append(match_result.match_id)
                        matched_results.append(match_result)
                    else:
                        unmatched_results.append(match_result)
                
                if progress_callback:
                    await progress_callback(80, 100, f"Found {len(matched_track_ids)} matching tracks")
                
                # Add tracks to playlist
                if matched_track_ids:
                    success = await self.add_tracks_to_playlist(
                        playlist_id,
                        matched_track_ids,
                        progress_callback=lambda current, total, message: progress_callback(
                            80 + int((current / total) * 15),
                            100,
                            message
                        ) if progress_callback else None
                    )
                    
                    if not success:
                        return PlaylistResult(
                            success=False,
                            playlist_id=playlist_id,
                            playlist_url=playlist_url,
                            message="Failed to add tracks to playlist"
                        )
                
                if progress_callback:
                    await progress_callback(95, 100, "Generating CSV data...")
                
                # Generate CSV data
                csv_data = None
                if export_unmatched:
                    csv_data = self._generate_csv_data(matched_results, unmatched_results)
                
                if progress_callback:
                    await progress_callback(100, 100, "Playlist creation complete")
                
                return PlaylistResult(
                    success=True,
                    playlist_id=playlist_id,
                    playlist_url=playlist_url,
                    tracks_added=len(matched_track_ids),
                    message=f"Created playlist with {len(matched_track_ids)} tracks",
                    added_tracks=matched_results,
                    unmatched_tracks=unmatched_results,
                    csv_data=csv_data
                )