"""
Beatport RSS implementation of the MusicSource interface.

This module fetches tracks from Beatport's RSS feeds for new releases and top 100 charts.
"""
import asyncio
import re
import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple

import aiohttp

from utils.sources.base import MusicSource, Track

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BeatportRSSSource(MusicSource):
    """Fetches tracks from Beatport's RSS feeds."""
    
    # Base URLs for Beatport feeds
    RELEASES_FEED = "https://www.beatport.com/feed/releases"
    TOP_100_FEED = "https://www.beatport.com/feed/top-100"
    
    # Map of genre keys to their Beatport IDs
    GENRE_IDS = {
        "all": None,
        "house": 5,
        "deep-house": 12,
        "tech-house": 11,
        "techno": 6,
        "electronica": 3,
        "drum-and-bass": 1,
        "minimal": 14,
        "progressive-house": 15,
        "melodic-house": 90,
        "afro-house": 89
    }
    
    @property
    def name(self) -> str:
        return "Beatport RSS"
    
    @property
    def description(self) -> str:
        return "Fetches tracks from Beatport's RSS feeds for new releases and charts"
    
    @property
    def available_genres(self) -> List[str]:
        return list(self.GENRE_IDS.keys())
    
    def get_feeds_urls(self, genre: Optional[str] = None) -> List[str]:
        """
        Get the RSS feed URLs for a given genre.
        
        Args:
            genre: Optional genre to filter by
            
        Returns:
            List of feed URLs
        """
        urls = []
        
        # Normalize genre
        normalized_genre = genre.lower() if genre else "all"
        genre_id = self.GENRE_IDS.get(normalized_genre)
        
        # Releases feed
        if genre_id:
            urls.append(f"{self.RELEASES_FEED}/genre/{genre_id}")
            urls.append(f"{self.TOP_100_FEED}/genre/{genre_id}")
        else:
            urls.append(self.RELEASES_FEED)
            urls.append(self.TOP_100_FEED)
        
        return urls
    
    async def get_tracks(self, days_to_look_back: int = 14, 
                          genre: Optional[str] = None, 
                          limit: int = 100) -> List[Track]:
        """
        Fetch tracks from Beatport's RSS feeds.
        
        Args:
            days_to_look_back: Number of days to look back for tracks
            genre: Optional genre filter
            limit: Maximum number of tracks to return
            
        Returns:
            List of Track objects
        """
        # Calculate date threshold
        date_threshold = datetime.now() - timedelta(days=days_to_look_back)
        
        # Get feed URLs
        feed_urls = self.get_feeds_urls(genre)
        
        logger.info(f"Fetching tracks from {len(feed_urls)} Beatport RSS feeds")
        
        # Initialize HTTP session
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/91.0.4472.114 Safari/537.36",
            "Accept": "application/rss+xml, application/xml",
            "Cache-Control": "no-cache"
        }
        
        all_tracks = []
        
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # Process each feed
                feed_tasks = []
                for url in feed_urls:
                    feed_tasks.append(self._process_feed(session, url, date_threshold))
                
                # Wait for all feeds to be processed
                results = await asyncio.gather(*feed_tasks, return_exceptions=True)
                
                # Combine results
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Error processing feed: {result}")
                    elif result:
                        all_tracks.extend(result)
                
                # Remove duplicates by source_url
                unique_tracks = {}
                for track in all_tracks:
                    if track.source_url and track.source_url not in unique_tracks:
                        unique_tracks[track.source_url] = track
                
                # Convert back to list
                tracks = list(unique_tracks.values())
                
                # Sort by release date (newest first)
                tracks.sort(key=lambda x: x.release_date, reverse=True)
                
                # Apply limit
                tracks = tracks[:limit]
                
                logger.info(f"Found {len(tracks)} tracks from Beatport RSS")
                
                return tracks
                
        except Exception as e:
            logger.error(f"Error fetching Beatport RSS tracks: {e}")
            return []
    
    async def _process_feed(self, session: aiohttp.ClientSession, 
                           feed_url: str, date_threshold: datetime) -> List[Track]:
        """
        Process an RSS feed and extract tracks.
        
        Args:
            session: HTTP session
            feed_url: URL of the RSS feed
            date_threshold: Date threshold for tracks
            
        Returns:
            List of Track objects
        """
        logger.info(f"Processing Beatport feed: {feed_url}")
        
        tracks = []
        
        try:
            async with session.get(feed_url) as response:
                if response.status != 200:
                    logger.error(f"Error fetching feed {feed_url}: {response.status}")
                    return []
                
                feed_content = await response.text()
                
                # Parse XML
                try:
                    # Add namespace
                    namespace = {"atom": "http://www.w3.org/2005/Atom"}
                    
                    # Parse XML
                    root = ET.fromstring(feed_content)
                    
                    # Find all items
                    for item in root.findall(".//item"):
                        try:
                            # Extract item data
                            title_element = item.find("title")
                            link_element = item.find("link")
                            pub_date_element = item.find("pubDate")
                            
                            if title_element is None or link_element is None:
                                continue
                            
                            title = title_element.text
                            link = link_element.text
                            
                            # Parse pub date
                            pub_date = None
                            if pub_date_element is not None and pub_date_element.text:
                                try:
                                    # RSS dates are in this format: Wed, 19 May 2021 00:00:00 +0000
                                    pub_date = datetime.strptime(
                                        pub_date_element.text.strip(), 
                                        "%a, %d %b %Y %H:%M:%S %z"
                                    )
                                except ValueError:
                                    logger.warning(f"Could not parse date: {pub_date_element.text}")
                            
                            # Use today's date if we couldn't parse the pub date
                            if not pub_date:
                                pub_date = datetime.now()
                            
                            # Skip if older than date threshold
                            if pub_date.replace(tzinfo=None) < date_threshold:
                                logger.debug(f"Skipping old track: {title} ({pub_date})")
                                continue
                            
                            # Parse title and extract artist and remix information
                            artist, track_title, remix = self._parse_title(title)
                            
                            # Create Track object
                            track = Track(
                                title=track_title,
                                artist=artist,
                                remix=remix,
                                release_date=pub_date.date(),
                                source="Beatport",
                                source_url=link
                            )
                            
                            tracks.append(track)
                            
                        except Exception as e:
                            logger.error(f"Error processing RSS item: {e}")
                            continue
                
                except ET.ParseError as e:
                    logger.error(f"Error parsing XML: {e}")
                    return []
                
                logger.info(f"Found {len(tracks)} tracks in feed {feed_url}")
                
                return tracks
                
        except Exception as e:
            logger.error(f"Error processing feed {feed_url}: {e}")
            return []
    
    def _parse_title(self, full_title: str) -> Tuple[str, str, Optional[str]]:
        """
        Parse a Beatport title to extract artist, title, and remix information.
        
        Beatport titles are usually formatted as "Artist - Title (Remix)"
        
        Args:
            full_title: The full title from the RSS feed
            
        Returns:
            Tuple of (artist, title, remix)
        """
        # Default values
        artist = "Unknown Artist"
        title = full_title
        remix = None
        
        try:
            # Split artist and title
            if " - " in full_title:
                artist, title_part = full_title.split(" - ", 1)
            else:
                title_part = full_title
            
            # Extract remix if available
            remix_match = re.search(r'\(([^)]*(?:mix|remix|edit|dub|version)[^)]*)\)', title_part, re.IGNORECASE)
            if remix_match:
                remix = remix_match.group(1)
                title = title_part[:remix_match.start()].strip()
            else:
                title = title_part
        
        except Exception as e:
            logger.error(f"Error parsing title '{full_title}': {e}")
        
        return artist, title, remix