"""
Juno Download implementation of the MusicSource interface.

This module scrapes tracks from Juno Download's bestsellers and new releases pages.
"""
import asyncio
import re
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any

import aiohttp
from bs4 import BeautifulSoup

from utils.sources.base import MusicSource, Track

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JunoDownloadSource(MusicSource):
    """Scrapes tracks from Juno Download."""
    
    BASE_URL = "https://www.junodownload.com"
    
    # Map of genre keys to their Juno Download URLs
    # Using exact URLs for precision
    GENRE_URLS = {
        "all": "all",
        "funky-house": "funky-club-house",
        "deep-house": "deep-house",
        "disco": "disco",
        "drum-and-bass": "drumandbass",
        "dancehall": "dancehall-reggae"
    }
    
    @property
    def name(self) -> str:
        return "Juno Download"
    
    @property
    def description(self) -> str:
        return "Scrapes tracks from Juno Download's bestsellers and new releases"
    
    @property
    def available_genres(self) -> List[str]:
        return list(self.GENRE_URLS.keys())
    
    def get_source_url(self, genre: Optional[str] = None, chart_type: str = "bestsellers") -> str:
        """Get the URL for Juno Download, optionally filtered by genre."""
        genre_path = self.GENRE_URLS.get(genre.lower(), "all") if genre else "all"
        
        # Add single filter to focus on tracks rather than albums
        return f"{self.BASE_URL}/{genre_path}/charts/{chart_type}/this-week/releases/?music_product_type=single&items_per_page=100"
    
    async def get_tracks(self, days_to_look_back: int = 14, 
                          genre: Optional[str] = None, 
                          limit: int = 100) -> List[Track]:
        """Fetch tracks from Juno Download."""
        # We'll combine results from bestsellers and new releases
        urls_to_scrape = [
            self.get_source_url(genre, "bestsellers"),
            # Add hype filter for more variety
            self.get_source_url(genre, "hype")
        ]
        
        logger.info(f"Will scrape {len(urls_to_scrape)} Juno Download pages for tracks")
        
        # Add headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            all_track_links = set()  # Use a set to avoid duplicates
            tracks = []
            
            try:
                # Process each URL to collect track links
                for url in urls_to_scrape:
                    try:
                        logger.info(f"Scraping Juno Download URL: {url}")
                        async with session.get(url) as response:
                            if response.status != 200:
                                logger.warning(f"Error accessing {url}: HTTP {response.status}")
                                continue
                            
                            html = await response.text()
                            if "404 Not Found" in html:
                                logger.warning(f"URL {url} returned a 404 page")
                                continue
                            
                            soup = BeautifulSoup(html, "html.parser")
                            page_track_links = []
                            
                            # Find track links in the page
                            for track_el in soup.select(".jd-listing-item"):
                                link_el = track_el.select_one(".juno-title a")
                                if link_el and link_el.get("href"):
                                    # Make sure it's a track link and not an album
                                    href = link_el.get("href")
                                    if "/track/" in href:
                                        page_track_links.append(self.BASE_URL + href)
                            
                            all_track_links.update(page_track_links)
                            logger.info(f"Found {len(page_track_links)} track links on {url}")
                    
                    except Exception as e:
                        logger.error(f"Error processing {url}: {e}")
                
                # Convert to list and limit to prevent excessive requests
                track_links = list(all_track_links)[:limit * 2]  # Get more than needed to account for failures
                logger.info(f"Will process {len(track_links)} unique track links")
                
                # Process track links in batches to avoid overwhelming the server
                batch_size = 5
                for i in range(0, len(track_links), batch_size):
                    batch = track_links[i:i+batch_size]
                    batch_tasks = [self._process_track(session, url) for url in batch]
                    batch_results = await asyncio.gather(*batch_tasks)
                    
                    # Filter out None results (failed tracks)
                    batch_tracks = [t for t in batch_results if t]
                    tracks.extend(batch_tracks)
                    
                    # Stop if we have enough tracks
                    if len(tracks) >= limit:
                        break
                    
                    # Log progress
                    logger.info(f"Processed {min(i+batch_size, len(track_links))}/{len(track_links)} tracks, found {len(tracks)} valid tracks")
                
                # Apply limit
                tracks = tracks[:limit]
                logger.info(f"Found {len(tracks)} tracks from Juno Download")
                
                return tracks
            
            except Exception as e:
                logger.error(f"Error scraping Juno Download: {e}", exc_info=True)
                return []
    
    async def _process_track(self, session: aiohttp.ClientSession, track_url: str) -> Optional[Track]:
        """Process a track page and extract track information."""
        try:
            async with session.get(track_url) as response:
                if response.status != 200:
                    logger.warning(f"Error accessing track page {track_url}: {response.status}")
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                
                # Extract track title
                title_el = soup.select_one("h1.product-title")
                if not title_el:
                    logger.warning(f"Could not find title on {track_url}")
                    return None
                
                full_title = title_el.get_text(strip=True)
                
                # Extract artist
                artist_el = soup.select_one(".product-artist a")
                if not artist_el:
                    logger.warning(f"Could not find artist on {track_url}")
                    return None
                
                artist = artist_el.get_text(strip=True)
                
                # Parse title to extract mix info
                title, remix = self._parse_title(full_title)
                
                # Try to extract release date
                release_date = None
                date_el = soup.select_one(".release-date-value")
                if date_el:
                    date_text = date_el.get_text(strip=True)
                    try:
                        # Parse various date formats (Juno uses several)
                        for fmt in ["%d %b %Y", "%d %B %Y", "%B %d, %Y", "%b %d, %Y"]:
                            try:
                                release_date = datetime.strptime(date_text, fmt).date()
                                break
                            except ValueError:
                                continue
                    except Exception:
                        pass
                
                # If no release date found, use today's date
                if not release_date:
                    release_date = date.today()
                
                # Check if the track is too old
                if (date.today() - release_date).days > 60:  # 60 days as a safety margin
                    logger.debug(f"Track too old: {track_url} - {release_date}")
                    return None
                
                # Create Track object
                track = Track(
                    title=title,
                    artist=artist,
                    remix=remix,
                    release_date=release_date,
                    source="Juno Download",
                    source_url=track_url
                )
                
                return track
        
        except Exception as e:
            logger.error(f"Error processing track page {track_url}: {e}")
            return None
    
    def _parse_title(self, full_title: str) -> Tuple[str, Optional[str]]:
        """Parse a track title to extract the base title and remix information."""
        # Common patterns for remix/mix information
        remix_patterns = [
            r'\(([^)]*(?:mix|remix|edit|dub|version)[^)]*)\)',
            r'\[([^]]*(?:mix|remix|edit|dub|version)[^]]*)\]',
        ]
        
        # Try each pattern
        for pattern in remix_patterns:
            match = re.search(pattern, full_title, re.IGNORECASE)
            if match:
                # Extract the remix part and the base title
                remix = match.group(1).strip()
                base_title = full_title[:match.start()].strip()
                return base_title, remix
        
        # If no remix information found, return the full title
        return full_title, None