"""
YouTube implementation of the MusicSource interface.

This module fetches tracks from various YouTube channels and playlists.
"""
import os
import re
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

import aiohttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from utils.sources.base import MusicSource, Track

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class YouTubeSource(MusicSource):
    """Fetches tracks from YouTube channels and playlists."""
    
    # Mapping of channel keys to YouTube channels/playlists
    GENRE_CHANNELS = {
        "selected-base": [
            {"type": "playlist", "id": "PLSr_oFUba1jtP9x5ZFs5Y0GJkb8fmC161", "name": "Selected Base"}
        ],
        "defected-music": [
            {"type": "playlist", "id": "PLoRGBexfBL8dbhIs6-GqWapmosx-0gqa7", "name": "Defected Music"}
        ],
        "glitterbox-ibiza": [
            {"type": "playlist", "id": "PLIxQjHO1yTm99RG32st06TnxZHMgCbT4H", "name": "Glitterbox Ibiza"}
        ],
        "anjunadeep": [
            {"type": "playlist", "id": "PLp0LvzekmDePVdSozfdcux2Lm-zw25Iie", "name": "Anjunadeep"}
        ],
        "toolroom-records": [
            {"type": "playlist", "id": "PLGdqhGdToks3HVLQqYbkp1pkyyuZUkJ8U", "name": "Toolroom Records"},
            {"type": "playlist", "id": "PLGdqhGdToks1CslquLlNQ4mofBwqnyrjW", "name": "Toolroom Records"}
        ],
        "spinnin-records": [
            {"type": "playlist", "id": "PL53244BC75ACF40D0", "name": "Spinnin' Records"}
        ],
        "stay-true-sounds": [
            {"type": "playlist", "id": "PLOH68idrufmjnBkoJLchYzyRN_uFcH628", "name": "Stay True Sounds"}
        ],
        "all": [
            {"type": "playlist", "id": "PLSr_oFUba1jtP9x5ZFs5Y0GJkb8fmC161", "name": "Selected Base"},
            {"type": "playlist", "id": "PLIxQjHO1yTm99RG32st06TnxZHMgCbT4H", "name": "Glitterbox Ibiza"},
            {"type": "playlist", "id": "PLoRGBexfBL8dbhIs6-GqWapmosx-0gqa7", "name": "Defected Music"},
            {"type": "playlist", "id": "PLp0LvzekmDePVdSozfdcux2Lm-zw25Iie", "name": "Anjunadeep"},
            {"type": "playlist", "id": "PLGdqhGdToks3HVLQqYbkp1pkyyuZUkJ8U", "name": "Toolroom Records"},
            {"type": "playlist", "id": "PL53244BC75ACF40D0", "name": "Spinnin' Records"},
            {"type": "playlist", "id": "PLOH68idrufmjnBkoJLchYzyRN_uFcH628", "name": "Stay True Sounds"}
        ]
    }
    
    # Filter keywords to exclude non-track content (mixes, sets, etc.)
    FILTER_KEYWORDS = [
        "mix compilation", "dj set", "live set", "mixtape", "megamix", 
        "year mix", "monthly selection", "best of", "top 10", "top tracks", 
        "mix show", "radio show", "special mix", "mixed by", "album mix",
        "tracklist", "interview", "behind the scenes", "vlog", "tutorial",
        "mashup", "yearmix", "classics", "throwback", "back to back"
    ]
    
    # Keywords that should still be allowed
    ALLOWED_TERMS = [
        "extended mix", "club mix", "radio edit", "original mix", "remix"
    ]
    
    @property
    def name(self) -> str:
        return "YouTube"
    
    @property
    def description(self) -> str:
        return "Fetches tracks from YouTube channels and playlists"
    
    @property
    def available_genres(self) -> List[str]:
        return list(self.GENRE_CHANNELS.keys())
    
    async def get_tracks(self, days_to_look_back: int = 14, 
                          genre: Optional[str] = None, 
                          limit: int = 100) -> List[Track]:
        """
        Fetch tracks from YouTube channels and playlists.
        
        Args:
            days_to_look_back: Number of days to look back for tracks
            genre: Optional genre filter (must be one of available_genres)
            limit: Maximum number of tracks to return
            
        Returns:
            List of Track objects
        """
        genre = genre.lower() if genre else "all"
        if genre not in self.GENRE_CHANNELS:
            logger.warning(f"Genre {genre} not found in YouTube sources, using 'all'")
            genre = "all"
        
        # Get channels/playlists for the selected genre
        sources = self.GENRE_CHANNELS.get(genre, self.GENRE_CHANNELS["all"])
        
        # Calculate the date threshold
        date_threshold = datetime.utcnow() - timedelta(days=days_to_look_back)
        logger.info(f"Date threshold for {days_to_look_back} days: {date_threshold} (UTC now: {datetime.utcnow()})")
        
        # Use API key if available, otherwise fallback to scraping
        api_key = os.environ.get("YOUTUBE_API_KEY")
        
        if not api_key:
            logger.warning("No YouTube API key found, results will be limited")
            return await self._scrape_youtube_tracks(sources, limit, date_threshold)
        
        # Initialize YouTube API client
        youtube = build("youtube", "v3", developerKey=api_key)
        
        all_tracks = []
        per_source_limit = max(limit // len(sources), 10)  # Ensure at least 10 per source
        
        # Process each source (playlist or channel)
        for source in sources:
            source_tracks = []
            source_type = source["type"]
            source_id = source["id"]
            source_name = source["name"]
            
            try:
                if source_type == "playlist":
                    # Fetch videos from playlist
                    source_tracks = await self._get_playlist_tracks(youtube, source_id, source_name, date_threshold, per_source_limit)
                elif source_type == "channel":
                    # Fetch videos from channel
                    source_tracks = await self._get_channel_tracks(youtube, source_id, source_name, date_threshold, per_source_limit)
            except HttpError as e:
                error_details = e.error_details[0] if hasattr(e, 'error_details') and e.error_details else {}
                error_reason = error_details.get('reason', 'unknown')
                logger.error(f"YouTube API error for {source_name} (ID: {source_id}): {e.resp.status} - {error_reason} - {str(e)}")
                # Continue to next source instead of failing entirely
                continue
            except Exception as e:
                logger.error(f"Error fetching tracks from {source_name} (ID: {source_id}): {type(e).__name__}: {e}", exc_info=True)
                # Continue to next source
                continue
            
            logger.info(f"Found {len(source_tracks)} tracks from {source_name}")
            all_tracks.extend(source_tracks)
            
            # Respect the overall limit
            if len(all_tracks) >= limit:
                break
        
        # Shuffle tracks to ensure variety, then limit
        import random
        if all_tracks:
            random.shuffle(all_tracks)
        else:
            logger.warning(f"No tracks found from any of the {len(sources)} sources")
        
        return all_tracks[:limit]
    
    async def get_tracks_from_sources(self, sources: List[Dict], days_to_look_back: int = 14, limit: int = 100, progress_callback=None) -> List[Track]:
        """
        Fetch tracks from provided sources list (can include custom user sources).
        
        Args:
            sources: List of source dictionaries with 'id', 'name', 'type' keys
            days_to_look_back: Number of days to look back for tracks
            limit: Maximum number of tracks to return
            
        Returns:
            List of Track objects
        """
        # Calculate the date threshold
        date_threshold = datetime.utcnow() - timedelta(days=days_to_look_back)
        
        # Use API key if available, otherwise fallback to scraping
        api_key = os.environ.get("YOUTUBE_API_KEY")
        
        if not api_key:
            logger.warning("No YouTube API key found, results will be limited")
            return await self._scrape_youtube_tracks(sources, limit, date_threshold)
        
        # Initialize YouTube API client
        youtube = build("youtube", "v3", developerKey=api_key)
        
        all_tracks = []
        per_source_limit = max(limit // len(sources), 10) if sources else limit
        
        # Process each source (playlist or channel)
        for source in sources:
            source_tracks = []
            source_type = source["type"]
            source_id = source["id"]
            source_name = source["name"]
            
            try:
                if source_type == "playlist":
                    # Fetch videos from playlist
                    source_tracks = await self._get_playlist_tracks(youtube, source_id, source_name, date_threshold, per_source_limit)
                elif source_type == "channel":
                    # Fetch videos from channel
                    source_tracks = await self._get_channel_tracks(youtube, source_id, source_name, date_threshold, per_source_limit)
            except HttpError as e:
                error_details = e.error_details[0] if hasattr(e, 'error_details') and e.error_details else {}
                error_reason = error_details.get('reason', 'unknown')
                logger.error(f"YouTube API error for {source_name} (ID: {source_id}): {e.resp.status} - {error_reason} - {str(e)}")
                # Continue to next source instead of failing entirely
                continue
            except Exception as e:
                logger.error(f"Error fetching tracks from {source_name} (ID: {source_id}): {type(e).__name__}: {e}", exc_info=True)
                # Continue to next source
                continue
            
            logger.info(f"Found {len(source_tracks)} tracks from {source_name}")
            all_tracks.extend(source_tracks)
            
            # Respect the overall limit
            if len(all_tracks) >= limit:
                break
        
        # Shuffle tracks to ensure variety, then limit
        import random
        if all_tracks:
            random.shuffle(all_tracks)
        else:
            logger.warning(f"No tracks found from any of the {len(sources)} sources")
        
        return all_tracks[:limit]
    
    async def _get_playlist_tracks(self, youtube, playlist_id: str, playlist_name: str, 
                                   date_threshold: datetime, limit: int) -> List[Track]:
        """Fetch tracks from a YouTube playlist."""
        tracks = []
        next_page_token = None
        pages_scanned = 0
        max_pages_to_scan = 4  # Scan up to 200 videos (50 per page)
        
        loop = asyncio.get_event_loop()
        
        while pages_scanned < max_pages_to_scan:
            # Get playlist items
            playlist_request = youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            
            # Execute request in the thread pool
            playlist_response = await loop.run_in_executor(None, playlist_request.execute)
            pages_scanned += 1
            
            items = playlist_response.get("items", [])
            logger.info(f"Playlist {playlist_name}: Page {pages_scanned}, found {len(items)} items")
            
            # Process videos
            for item in items:
                snippet = item.get("snippet", {})
                video_id = item.get("contentDetails", {}).get("videoId")
                
                # Skip if no video ID
                if not video_id:
                    continue
                
                # Get video details
                title = snippet.get("title", "")
                channel_title = snippet.get("channelTitle", "")
                published_at = snippet.get("publishedAt", "")
                
                # Skip private videos
                if title == "Private video" or not title:
                    continue
                
                # Skip if video is too old
                if published_at:
                    publish_date = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
                    if publish_date < date_threshold:
                        continue
                    else:
                        days_old = (datetime.utcnow() - publish_date).days
                        logger.info(f"[{playlist_name}] Video '{title}' is {days_old} days old, within date range")
                
                # Skip if it matches any filter keywords (but allow specific terms)
                should_filter = False
                for keyword in self.FILTER_KEYWORDS:
                    if keyword.lower() in title.lower():
                        # Check if it contains an allowed term
                        has_allowed_term = False
                        for allowed in self.ALLOWED_TERMS:
                            if allowed.lower() in title.lower():
                                has_allowed_term = True
                                break
                        
                        if not has_allowed_term:
                            should_filter = True
                            break
                
                if should_filter:
                    continue
                
                # Extract artist and track title
                artist, track_title, remix = self._parse_title(title)
                
                # Create Track object
                track = Track(
                    title=track_title,
                    artist=artist,
                    remix=remix,
                    release_date=publish_date.date() if publish_date else None,
                    source=playlist_name,
                    source_url=f"https://www.youtube.com/watch?v={video_id}"
                )
                
                tracks.append(track)
                
                # Respect the limit
                if len(tracks) >= limit:
                    return tracks
            
            # Check if there are more pages
            next_page_token = playlist_response.get("nextPageToken")
            if not next_page_token:
                break
        
        logger.info(f"Playlist {playlist_name}: Scanned {pages_scanned} pages, found {len(tracks)} tracks within date range")
        return tracks
    
    async def _get_channel_tracks(self, youtube, channel_id: str, channel_name: str,
                                 date_threshold: datetime, limit: int) -> List[Track]:
        """Fetch tracks from a YouTube channel."""
        tracks = []
        next_page_token = None
        
        loop = asyncio.get_event_loop()
        
        # Handle @username format by resolving to channel ID first
        if channel_id.startswith('@'):
            username = channel_id[1:]  # Remove @ symbol
            logger.info(f"Resolving @{username} to channel ID...")
            try:
                # Search for the channel by username
                search_request = youtube.search().list(
                    part="snippet",
                    q=f"@{username}",
                    type="channel",
                    maxResults=5
                )
                search_response = await loop.run_in_executor(None, search_request.execute)
                
                # Find the best matching channel
                channel_id_found = None
                for item in search_response.get("items", []):
                    # First result is usually the best match
                    channel_id_found = item["snippet"]["channelId"]
                    channel_name = item["snippet"]["channelTitle"]
                    logger.info(f"Found channel: {channel_name} with ID: {channel_id_found}")
                    break
                
                if not channel_id_found:
                    logger.warning(f"Channel @{username} not found in search")
                    return []
                
                channel_id = channel_id_found
                logger.info(f"Resolved @{username} to channel ID: {channel_id}")
            except Exception as e:
                logger.error(f"Error resolving @{username}: {e}")
                return []
        
        # Now get the uploads playlist ID for the channel
        channel_request = youtube.channels().list(
            part="contentDetails",
            id=channel_id
        )
        
        channel_response = await loop.run_in_executor(None, channel_request.execute)
        
        if not channel_response.get("items"):
            logger.warning(f"Channel {channel_name} not found")
            return []
        
        uploads_playlist_id = channel_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        
        # Now get videos from the uploads playlist
        while True:
            playlist_request = youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            
            playlist_response = await loop.run_in_executor(None, playlist_request.execute)
            
            # Process videos
            for item in playlist_response.get("items", []):
                snippet = item.get("snippet", {})
                video_id = item.get("contentDetails", {}).get("videoId")
                
                # Skip if no video ID
                if not video_id:
                    continue
                
                # Get video details
                title = snippet.get("title", "")
                published_at = snippet.get("publishedAt", "")
                
                # Skip private videos
                if title == "Private video" or not title:
                    continue
                
                # Skip if video is too old
                if published_at:
                    publish_date = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
                    if publish_date < date_threshold:
                        continue
                    else:
                        days_old = (datetime.utcnow() - publish_date).days
                        logger.info(f"[{channel_name}] Video '{title}' is {days_old} days old, within date range")
                
                # Skip if it matches any filter keywords
                should_filter = False
                for keyword in self.FILTER_KEYWORDS:
                    if keyword.lower() in title.lower():
                        # Check if it contains an allowed term
                        has_allowed_term = False
                        for allowed in self.ALLOWED_TERMS:
                            if allowed.lower() in title.lower():
                                has_allowed_term = True
                                break
                        
                        if not has_allowed_term:
                            should_filter = True
                            break
                
                if should_filter:
                    continue
                
                # Extract artist and track title
                artist, track_title, remix = self._parse_title(title)
                
                # Create Track object
                track = Track(
                    title=track_title,
                    artist=artist,
                    remix=remix,
                    release_date=publish_date.date() if publish_date else None,
                    source=channel_name,
                    source_url=f"https://www.youtube.com/watch?v={video_id}"
                )
                
                tracks.append(track)
                
                # Respect the limit
                if len(tracks) >= limit:
                    return tracks
            
            # Check if there are more pages
            next_page_token = playlist_response.get("nextPageToken")
            if not next_page_token:
                break
        
        return tracks
    
    async def _scrape_youtube_tracks(self, sources: List[Dict], limit: int, 
                                    date_threshold: datetime) -> List[Track]:
        """Fallback method to scrape YouTube without API key."""
        # This is a simplified scraping implementation
        logger.warning("Using YouTube scraping fallback (limited functionality)")
        
        all_tracks = []
        
        async with aiohttp.ClientSession() as session:
            for source in sources:
                source_type = source["type"]
                source_id = source["id"]
                source_name = source["name"]
                
                if source_type == "playlist":
                    url = f"https://www.youtube.com/playlist?list={source_id}"
                else:
                    url = f"https://www.youtube.com/channel/{source_id}/videos"
                
                try:
                    async with session.get(url) as response:
                        if response.status != 200:
                            logger.warning(f"Error accessing {url}: {response.status}")
                            continue
                        
                        html = await response.text()
                        
                        # Extract video information from the HTML
                        # This is a simplified implementation and may break if YouTube changes their HTML structure
                        video_titles = re.findall(r'"title":{"runs":\[{"text":"(.*?)"}\]}', html)
                        video_ids = re.findall(r'"videoId":"(.*?)"', html)
                        
                        # Match titles with IDs
                        for i, (title, video_id) in enumerate(zip(video_titles, video_ids)):
                            if i >= limit // len(sources):
                                break
                            
                            # Skip private videos
                            if title == "Private video" or not title:
                                continue
                            
                            # Skip if it matches any filter keywords
                            should_filter = False
                            for keyword in self.FILTER_KEYWORDS:
                                if keyword.lower() in title.lower():
                                    has_allowed_term = False
                                    for allowed in self.ALLOWED_TERMS:
                                        if allowed.lower() in title.lower():
                                            has_allowed_term = True
                                            break
                                    
                                    if not has_allowed_term:
                                        should_filter = True
                                        break
                            
                            if should_filter:
                                continue
                            
                            # Extract artist and track title
                            artist, track_title, remix = self._parse_title(title)
                            
                            # Create Track object
                            track = Track(
                                title=track_title,
                                artist=artist,
                                remix=remix,
                                release_date=None,  # No date info in scraping
                                source=source_name,
                                source_url=f"https://www.youtube.com/watch?v={video_id}"
                            )
                            
                            all_tracks.append(track)
                
                except Exception as e:
                    logger.error(f"Error scraping {url}: {e}", exc_info=True)
        
        # Shuffle tracks to ensure variety, then limit
        import random
        if all_tracks:
            random.shuffle(all_tracks)
        else:
            logger.warning(f"No tracks found from any of the {len(sources)} sources")
        
        return all_tracks[:limit]
    
    def _parse_title(self, title: str) -> Tuple[str, str, Optional[str]]:
        """
        Parse a YouTube video title to extract artist and track information.
        
        Returns a tuple of (artist, track_title, remix)
        """
        # Clean up the title
        title = title.strip()
        
        # Common patterns in electronic music YouTube titles
        patterns = [
            # Artist - Title (Remix) pattern
            r"^([^-]+)\s*-\s*([^(\[]+)(?:\(([^)]+)\))?",
            # Artist "Title" pattern
            r'^([^"]+)\s*"([^"]+)"(?:\s*\(([^)]+)\))?',
            # Artist 'Title' pattern
            r"^([^']+)\s*'([^']+)'(?:\s*\(([^)]+)\))?",
            # Artist | Title pattern
            r"^([^|]+)\s*\|\s*([^(\[]+)(?:\s*\(([^)]+)\))?",
            # Title by Artist pattern
            r"^([^(byB)]+)\s+(?:by|BY)\s+([^(\[]+)(?:\s*\(([^)]+)\))?",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    artist = groups[0].strip()
                    track_title = groups[1].strip()
                    remix = groups[2].strip() if len(groups) > 2 and groups[2] else None
                    
                    # Check if remix info is already in title and not in the remix field
                    if not remix:
                        remix_match = re.search(r'\(([^)]*(?:remix|mix|edit|version)[^)]*)\)', track_title, re.IGNORECASE)
                        if remix_match:
                            remix = remix_match.group(1)
                            # Remove the remix info from the title
                            track_title = re.sub(r'\s*\([^)]*(?:remix|mix|edit|version)[^)]*\)', '', track_title)
                    
                    return artist, track_title, remix
        
        # If no pattern matches, use a default split on first delimiter found
        for delimiter in [" - ", " | ", ": ", " _ "]:
            if delimiter in title:
                parts = title.split(delimiter, 1)
                artist = parts[0].strip()
                track_title = parts[1].strip()
                
                # Check for remix info in parentheses
                remix_match = re.search(r'\(([^)]*(?:remix|mix|edit|version)[^)]*)\)', track_title, re.IGNORECASE)
                if remix_match:
                    remix = remix_match.group(1)
                    # Remove the remix info from the title
                    track_title = re.sub(r'\s*\([^)]*(?:remix|mix|edit|version)[^)]*\)', '', track_title)
                else:
                    remix = None
                
                return artist, track_title, remix
        
        # If all else fails, treat the whole title as the track title
        return "Unknown Artist", title, None