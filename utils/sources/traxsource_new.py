"""
Traxsource implementation of the MusicSource interface.

This module scrapes tracks from Traxsource's Top 100 charts.
"""
import asyncio
import re
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any

import aiohttp
from bs4 import BeautifulSoup

from utils.sources.base import MusicSource, Track

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TraxsourceSource(MusicSource):
    """Scrapes tracks from Traxsource's charts."""
    
    BASE_URL = "https://www.traxsource.com"
    CHART_URL = f"{BASE_URL}/top100"
    
    # Map of genre keys to their Traxsource URLs
    GENRE_URLS = {
        "all": "",
        "house": "5",
        "deep-house": "67",
        "soulful-house": "12",
        "afro-house": "107",
        "tech-house": "14",
    }
    
    @property
    def name(self) -> str:
        return "Traxsource"
    
    @property
    def description(self) -> str:
        return "Scrapes tracks from Traxsource's Top 100 charts"
    
    @property
    def available_genres(self) -> List[str]:
        return list(self.GENRE_URLS.keys())
    
    def get_chart_url(self, genre: Optional[str] = None, page: int = 1) -> str:
        """Get the URL for a genre chart on Traxsource."""
        genre = genre.lower() if genre else "all"
        genre_id = self.GENRE_URLS.get(genre, "")
        
        if genre_id:
            base_url = f"{self.CHART_URL}/{genre_id}"
        else:
            base_url = self.CHART_URL
            
        # Add page parameter if beyond page 1
        if page > 1:
            return f"{base_url}?page={page}"
        return base_url
    
    async def get_tracks(self, days_to_look_back: int = 14, 
                          genre: Optional[str] = None, 
                          limit: int = 100) -> List[Track]:
        """
        Fetch tracks from Traxsource's charts.
        
        Args:
            days_to_look_back: Number of days to look back for tracks
            genre: Optional genre filter (must be one of available_genres)
            limit: Maximum number of tracks to return
            
        Returns:
            List of Track objects
        """
        # Calculate date threshold
        date_threshold = datetime.now() - timedelta(days=days_to_look_back)
        
        logger.info(f"Fetching tracks from Traxsource with genre={genre}, days_back={days_to_look_back}")
        
        # Initialize HTTP session with headers to mimic a browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/91.0.4472.114 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0"
        }
        
        tracks = []
        
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # Process multiple pages until we have enough tracks or no more pages
                page = 1
                max_pages = 5  # Safety limit to prevent infinite loops
                
                while len(tracks) < limit and page <= max_pages:
                    # Get chart URL for the current page
                    url = self.get_chart_url(genre, page)
                    logger.info(f"Fetching Traxsource page {page}: {url}")
                    
                    # Get the chart page
                    async with session.get(url) as response:
                        if response.status != 200:
                            logger.error(f"Failed to fetch chart page {page}: {response.status}")
                            break
                        
                        html = await response.text()
                    
                    # Parse the HTML
                    soup = BeautifulSoup(html, "html.parser")
                    
                    # Find all track entries in the chart
                    track_elements = soup.select(".trk-row")
                    
                    if not track_elements:
                        logger.info(f"No more tracks found on page {page}")
                        break
                    
                    logger.info(f"Found {len(track_elements)} track elements on page {page}")
                    
                    # Process each track
                    track_tasks = []
                    for track_el in track_elements:
                        track_tasks.append(self._process_track(session, track_el, date_threshold))
                    
                    # Process tracks in batches to avoid overwhelming the server
                    batch_size = 5
                    for i in range(0, len(track_tasks), batch_size):
                        batch = track_tasks[i:i+batch_size]
                        batch_results = await asyncio.gather(*batch)
                        valid_tracks = [t for t in batch_results if t]
                        tracks.extend(valid_tracks)
                        logger.info(f"Processed {min(i+batch_size, len(track_tasks))}/{len(track_tasks)} tracks on page {page}, found {len(valid_tracks)} valid tracks")
                    
                    # Check if we have a next page by looking for pagination links
                    next_page_link = soup.select_one(f"a.pag-next")
                    if not next_page_link:
                        logger.info(f"No next page link found on page {page}")
                        break
                    
                    # Move to next page
                    page += 1
                
                # Filter tracks by date if we have more than needed
                date_filtered_tracks = []
                for track in tracks:
                    if track.release_date:
                        track_date = track.release_date
                        if isinstance(track_date, datetime):
                            track_date = track_date.date()
                        
                        if track_date >= date_threshold.date():
                            date_filtered_tracks.append(track)
                    else:
                        # Include tracks with unknown dates
                        date_filtered_tracks.append(track)
                
                logger.info(f"After date filtering: {len(date_filtered_tracks)}/{len(tracks)} tracks remain")
                
                # Sort by release date (newest first) and apply limit
                date_filtered_tracks.sort(key=lambda x: x.release_date if x.release_date else date.today(), reverse=True)
                result_tracks = date_filtered_tracks[:limit]
                
                logger.info(f"Returning {len(result_tracks)} tracks from Traxsource")
                
                return result_tracks
        
        except Exception as e:
            logger.error(f"Error fetching Traxsource tracks: {e}")
            return []
    
    async def _process_track(self, session: aiohttp.ClientSession, 
                            track_element, date_threshold: datetime) -> Optional[Track]:
        """Process a track element and return a Track object."""
        try:
            # Extract track information
            title_element = track_element.select_one(".title a")
            if not title_element:
                return None
            
            title = title_element.get_text(strip=True)
            track_url = self.BASE_URL + title_element.get("href") if title_element.get("href") else None
            
            artist_element = track_element.select_one(".artist a")
            artist = artist_element.get_text(strip=True) if artist_element else "Unknown Artist"
            
            # Try to extract remix info from the title
            remix = None
            remix_match = re.search(r'\(([^)]+(?:mix|remix|edit|dub|version)[^)]*)\)', title, re.IGNORECASE)
            if remix_match:
                remix = remix_match.group(1)
            
            # If we have a track URL, fetch the track page to get more details
            release_date = None
            if track_url:
                try:
                    async with session.get(track_url) as response:
                        if response.status == 200:
                            track_html = await response.text()
                            track_soup = BeautifulSoup(track_html, "html.parser")
                            
                            # Try to extract release date using multiple patterns
                            release_info = track_soup.select_one(".release-date")
                            if release_info:
                                date_text = release_info.get_text(strip=True)
                                
                                # Try various date formats that might appear on Traxsource
                                date_formats = [
                                    r'(\d{2}-\d{2}-\d{4})',            # dd-mm-yyyy
                                    r'(\d{2}/\d{2}/\d{4})',            # dd/mm/yyyy
                                    r'(\d{1,2} [A-Za-z]+ \d{4})',      # d MMM yyyy or dd MMM yyyy
                                    r'([A-Za-z]+ \d{1,2}, \d{4})',     # MMM d, yyyy or MMM dd, yyyy
                                    r'(\d{4}-\d{2}-\d{2})'             # yyyy-mm-dd
                                ]
                                
                                for pattern in date_formats:
                                    date_match = re.search(pattern, date_text)
                                    if date_match:
                                        date_str = date_match.group(1)
                                        
                                        # Try various date parsing formats
                                        for fmt in [
                                            "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y",
                                            "%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"
                                        ]:
                                            try:
                                                release_date = datetime.strptime(date_str, fmt).date()
                                                break
                                            except ValueError:
                                                continue
                                        
                                        if release_date:
                                            break
                except Exception as e:
                    logger.warning(f"Could not fetch track page at {track_url}: {e}")
            
            # If we couldn't get a release date, use today's date
            if not release_date:
                logger.debug(f"Could not find release date for track at {track_url}, using today's date")
                release_date = date.today()
            
            # Create Track object
            track = Track(
                title=title,
                artist=artist,
                remix=remix,
                release_date=release_date,
                source="Traxsource",
                source_url=track_url
            )
            
            return track
        
        except Exception as e:
            logger.error(f"Error processing Traxsource track: {e}")
            return None