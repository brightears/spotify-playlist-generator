"""
YouTube implementation of the PlaylistDestination interface.
"""
import os
import json
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

from utils.sources.base import Track
from utils.destinations.base import PlaylistDestination, MatchResult, PlaylistResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# YouTube API scopes
SCOPES = ["https://www.googleapis.com/auth/youtube"]

# Credentials file paths
CREDENTIALS_FILE = Path.home() / ".youtube_credentials.json"
TOKEN_FILE = Path.home() / ".youtube_token.json"

class YouTubeDestination(PlaylistDestination):
    """Creates playlists on YouTube."""
    
    def __init__(self):
        self.youtube = None
        self.credentials = None
    
    @property
    def name(self) -> str:
        return "YouTube"
    
    @property
    def description(self) -> str:
        return "Creates playlists on YouTube using the YouTube Data API"
    
    async def authenticate(self, auth_data: Dict[str, Any] = None) -> bool:
        """
        Authenticate with YouTube.
        
        Args:
            auth_data: Optional authentication data
            
        Returns:
            True if authentication was successful, False otherwise
        """
        # Check if we're running in a web server context
        in_web_context = os.environ.get("WERKZEUG_RUN_MAIN") or os.environ.get("FLASK_ENV")
        
        try:
            # First try to use token file
            if TOKEN_FILE.exists():
                logger.info("Loading credentials from token file")
                with open(TOKEN_FILE, "r") as token:
                    token_data = json.load(token)
                    self.credentials = Credentials.from_authorized_user_info(token_data, SCOPES)
            
            # If credentials don't exist or are invalid, we need to log in
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    logger.info("Refreshing expired credentials")
                    await asyncio.to_thread(self.credentials.refresh, Request())
                elif not in_web_context:
                    # Only run full OAuth flow if not in web context
                    if not CREDENTIALS_FILE.exists():
                        logger.error(f"Credentials file not found at {CREDENTIALS_FILE}")
                        return False
                    
                    logger.info("Starting OAuth flow")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        CREDENTIALS_FILE, SCOPES
                    )
                    self.credentials = await asyncio.to_thread(
                        flow.run_local_server, port=8090
                    )
                else:
                    # In web context, don't try to open a browser
                    logger.error("Authentication required but running in web context")
                    logger.error("Please run 'python create_youtube_playlist_cli.py' first")
                    return False
                
                # Save the credentials for the next run
                token_data = {
                    "token": self.credentials.token,
                    "refresh_token": self.credentials.refresh_token,
                    "token_uri": self.credentials.token_uri,
                    "client_id": self.credentials.client_id,
                    "client_secret": self.credentials.client_secret,
                    "scopes": self.credentials.scopes
                }
                
                with open(TOKEN_FILE, "w") as token:
                    json.dump(token_data, token)
                logger.info(f"Saved credentials to {TOKEN_FILE}")
            
            # Build the YouTube API client
            self.youtube = googleapiclient.discovery.build(
                "youtube", "v3", credentials=self.credentials
            )
            
            # Test connection
            response = await asyncio.to_thread(
                self.youtube.channels().list(part="snippet", mine=True).execute
            )
            
            if "items" in response and len(response["items"]) > 0:
                channel_name = response["items"][0]["snippet"]["title"]
                logger.info(f"Authenticated as YouTube channel: {channel_name}")
                return True
            else:
                logger.error("Failed to get channel information")
                return False
        
        except RefreshError:
            logger.error("Failed to refresh token, need to re-authenticate")
            # Delete the token file to force re-authentication next time
            if TOKEN_FILE.exists():
                TOKEN_FILE.unlink()
            return False
        
        except Exception as e:
            logger.error(f"Error authenticating with YouTube: {e}")
            return False
    
    async def search_track(self, track: Track) -> MatchResult:
        """
        Search for a track on YouTube.
        
        Args:
            track: Track to search for
            
        Returns:
            MatchResult object with match details
        """
        if not self.youtube:
            raise ValueError("Not authenticated. Call authenticate() first.")
        
        # Create search query
        query = f"{track.artist} - {track.title}"
        if track.remix:
            query += f" {track.remix}"
        
        # If the track already has a YouTube URL, use that
        if track.source == "YouTube" and track.source_url:
            try:
                # Extract video ID from URL
                import re
                video_id_match = re.search(r"(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\s]+)", track.source_url)
                
                if video_id_match:
                    video_id = video_id_match.group(1)
                    
                    # Get video details
                    response = await asyncio.to_thread(
                        self.youtube.videos().list(
                            part="snippet",
                            id=video_id
                        ).execute
                    )
                    
                    if "items" in response and len(response["items"]) > 0:
                        video = response["items"][0]
                        return MatchResult(
                            track=track,
                            matched=True,
                            match_id=video_id,
                            match_url=f"https://www.youtube.com/watch?v={video_id}",
                            match_name=video["snippet"]["title"],
                            match_artist=video["snippet"]["channelTitle"],
                            score=1.0,
                            message="Direct YouTube URL match"
                        )
            except Exception as e:
                logger.error(f"Error getting video details: {e}")
        
        try:
            # Search for the track
            response = await asyncio.to_thread(
                self.youtube.search().list(
                    part="snippet",
                    q=query,
                    type="video",
                    maxResults=5
                ).execute
            )
            
            if "items" not in response or len(response["items"]) == 0:
                return MatchResult(
                    track=track,
                    matched=False,
                    message="No videos found on YouTube"
                )
            
            # Find the best match
            best_score = 0.0
            best_video = None
            
            for video in response["items"]:
                video_title = video["snippet"]["title"]
                video_channel = video["snippet"]["channelTitle"]
                
                # Calculate match score
                score = self.calculate_match_score(track, video_title, video_channel)
                
                if score > best_score:
                    best_score = score
                    best_video = video
            
            # Return the best match if it's good enough
            if best_video and best_score >= 0.5:
                video_id = best_video["id"]["videoId"]
                return MatchResult(
                    track=track,
                    matched=True,
                    match_id=video_id,
                    match_url=f"https://www.youtube.com/watch?v={video_id}",
                    match_name=best_video["snippet"]["title"],
                    match_artist=best_video["snippet"]["channelTitle"],
                    score=best_score,
                    message=f"Found match with score {best_score:.2f}"
                )
            
            return MatchResult(
                track=track,
                matched=False,
                message=f"No good matches found (best score: {best_score:.2f})"
            )
        
        except Exception as e:
            logger.error(f"Error searching YouTube: {e}")
            return MatchResult(
                track=track,
                matched=False,
                message=f"Error searching YouTube: {str(e)}"
            )
    
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
        Create a playlist on YouTube.
        
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
        if not self.youtube:
            raise ValueError("Not authenticated. Call authenticate() first.")
        
        # Replace {date} placeholder in playlist name
        today = datetime.now().strftime("%Y-%m-%d")
        name = name.replace("{date}", today)
        
        try:
            # Create the playlist
            playlist_response = await asyncio.to_thread(
                self.youtube.playlists().insert(
                    part="snippet,status",
                    body={
                        "snippet": {
                            "title": name,
                            "description": description
                        },
                        "status": {
                            "privacyStatus": "public" if public else "private"
                        }
                    }
                ).execute
            )
            
            playlist_id = playlist_response["id"]
            playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
            
            logger.info(f"Created playlist: {name} ({playlist_id})")
            
            # Search for tracks and add them to the playlist
            matched_track_ids = []
            
            for i, track in enumerate(tracks):
                # Update progress
                if progress_callback:
                    await progress_callback(i, len(tracks), f"Searching for track {i+1}/{len(tracks)}: {track.artist} - {track.title}")
                
                # If the track is already from YouTube, use its URL directly
                if track.source == "YouTube" and track.source_url:
                    import re
                    video_id_match = re.search(r"(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\s]+)", track.source_url)
                    
                    if video_id_match:
                        video_id = video_id_match.group(1)
                        matched_track_ids.append(video_id)
                        if progress_callback:
                            await progress_callback(i, len(tracks), f"✅ Using direct YouTube URL for {track.artist} - {track.title}")
                        continue
                
                # Otherwise, search for the track
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
            
            # YouTube API allows adding up to 50 videos at once
            batch_size = 50
            added_count = 0
            
            for i in range(0, len(matched_track_ids), batch_size):
                batch = matched_track_ids[i:i+batch_size]
                
                if progress_callback:
                    await progress_callback(i, len(matched_track_ids), f"Adding videos to playlist ({i+1}-{i+len(batch)}/{len(matched_track_ids)})")
                
                # Add videos to playlist
                for video_id in batch:
                    try:
                        await asyncio.to_thread(
                            self.youtube.playlistItems().insert(
                                part="snippet",
                                body={
                                    "snippet": {
                                        "playlistId": playlist_id,
                                        "resourceId": {
                                            "kind": "youtube#video",
                                            "videoId": video_id
                                        }
                                    }
                                }
                            ).execute
                        )
                        added_count += 1
                    except Exception as e:
                        logger.error(f"Error adding video {video_id} to playlist: {e}")
            
            return PlaylistResult(
                success=True,
                playlist_id=playlist_id,
                playlist_url=playlist_url,
                tracks_added=added_count,
                message=f"Created playlist with {added_count} videos"
            )
        
        except Exception as e:
            logger.error(f"Error creating YouTube playlist: {e}")
            return PlaylistResult(
                success=False,
                message=f"Error creating YouTube playlist: {str(e)}"
            )