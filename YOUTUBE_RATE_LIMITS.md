# YouTube API Rate Limits & Scaling Strategy

## Current State (Jan 2025)

### API Quota
- **Daily Quota**: 10,000 units per project
- **Current Usage**: ~3-6 units per source
- **Per Playlist**: ~33-66 units (11 sources)
- **Daily Capacity**: ~150-300 playlists

### Current Implementation (Jan 2025)
```python
# Parallel batch processing for speed (task_manager.py line 407-459)
# Dynamic batch size based on source count
if total_sources <= 3:
    batch_size = total_sources  # All at once
elif total_sources <= 10:
    batch_size = 3  # 3 at a time
else:
    batch_size = 5  # 5 at a time for many sources

# Process in parallel batches
for batch in batches:
    batch_results = await asyncio.gather(
        *[fetch_source(s) for s in batch],
        return_exceptions=True
    )
    # 0.5 second delay between batches only
```

### Performance Improvements
- **Sequential**: 30 sources = ~60+ seconds
- **Parallel (3x)**: 30 sources = ~20 seconds
- **Parallel (5x)**: 30 sources = ~12 seconds

### Track Limits
- **Preset channels**: 100 tracks (effectively unlimited within date range)
- **Custom sources (Pro)**: 10 tracks per source
- **Rationale**: Preset channels post ~5-10 tracks/week, custom sources need limits for scaling

### Error Handling
- Graceful failure: If one source fails, others continue
- HttpError catching in youtube.py (lines 153-156, 213-216)
- Users still get partial results if some sources fail

## Monitoring Rate Limits

### How to Check Current Usage
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to APIs & Services → Dashboard
3. Click on YouTube Data API v3
4. View Quotas & Metrics

### Warning Signs
- `HttpError 403: quotaExceeded` in logs
- Consistent failures after processing ~150 playlists
- All YouTube sources failing simultaneously

## Scaling Solutions (When Needed)

### Level 1: Optimize Current Usage (Easy)
```python
# Reduce API calls by increasing cache time
# Currently fetches fresh data every time
# Could cache channel data for 2-4 hours

# In youtube.py, add caching:
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=100)
def get_cached_playlist_items(playlist_id, cache_time):
    # Implementation here
    pass
```

### Level 2: Multiple API Keys (Medium)
```python
# Rotate between multiple API keys
API_KEYS = [
    os.environ.get("YOUTUBE_API_KEY_1"),
    os.environ.get("YOUTUBE_API_KEY_2"),
    os.environ.get("YOUTUBE_API_KEY_3"),
]

# In youtube.py constructor:
def __init__(self):
    self.current_key_index = 0
    self.api_keys = [k for k in API_KEYS if k]
    
def get_next_api_key(self):
    key = self.api_keys[self.current_key_index]
    self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
    return key
```

### Level 3: User-Provided Keys (Complex)
```python
# Allow Pro users to add their own API key
# Add to User model:
youtube_api_key = db.Column(db.String(100), nullable=True, encrypted=True)

# In task processing:
user_key = user.youtube_api_key or os.environ.get("YOUTUBE_API_KEY")
youtube = build("youtube", "v3", developerKey=user_key)
```

### Level 4: Quota Management System (Advanced)
```python
# Track API usage per user
class ApiUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.Date, default=datetime.utcnow)
    units_used = db.Column(db.Integer, default=0)
    
# Before API calls:
def check_quota(user_id, units_needed):
    usage = ApiUsage.query.filter_by(
        user_id=user_id,
        date=datetime.utcnow().date()
    ).first()
    
    if usage and usage.units_used + units_needed > USER_DAILY_LIMIT:
        raise QuotaExceededException("Daily limit reached")
```

## Cost Considerations

### Current: Free Tier
- 10,000 units/day free
- No cost unless you need more

### Scaling Options
1. **Multiple Projects**: Create additional Google Cloud projects (free)
2. **YouTube API Pricing**: Currently no paid tier available
3. **Alternative**: Consider YouTube scraping libraries if API limits become blocking

## Implementation Priority

When you hit rate limits, implement in this order:
1. **Add caching** (2-4 hour cache for channel data)
2. **Better error messages** (tell users when rate limited)
3. **Multiple API keys** (3x capacity instantly)
4. **User quotas** (limit heavy users)
5. **User-provided keys** (unlimited for Pro users)

## Testing Rate Limits

```python
# Add to test_youtube_limits.py
async def stress_test_youtube_api():
    """Test how many requests before hitting limits"""
    youtube_source = YouTubeSource()
    successful_requests = 0
    
    try:
        for i in range(1000):
            await youtube_source.get_tracks(limit=1)
            successful_requests += 1
            print(f"Request {i+1} successful")
            await asyncio.sleep(0.1)
    except HttpError as e:
        if "quotaExceeded" in str(e):
            print(f"Hit quota limit after {successful_requests} requests")
```

## Current Protection Mechanisms

1. **Sequential Processing**: Prevents parallel API calls
2. **0.5s Delay**: Between each source
3. **Error Isolation**: One source failing doesn't break others
4. **10 tracks/source limit**: Reduces pagination needs
5. **Database result storage**: Users can re-download without new API calls

## Notes for Future

- Current implementation is good for 150-300 playlists/day
- Most users generate 1-5 playlists/day, so plenty of headroom
- If you get popular (1000+ daily users), implement Level 2 first
- Consider showing users their daily usage in Account page
- Add Sentry/logging to track quota errors in production