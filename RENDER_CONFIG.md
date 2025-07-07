# Render Configuration Update

## Worker Timeout Fix

To fix the worker timeout issue when processing all YouTube channels, update your Render service configuration:

### Option 1: Update Start Command (Recommended)
In your Render dashboard, go to your service settings and update the Start Command to:

```bash
gunicorn web_app:app --config gunicorn_config.py
```

This will use the new `gunicorn_config.py` file which sets:
- Worker timeout: 120 seconds (increased from default 30)
- 2 workers for better performance
- Proper logging configuration

### Option 2: Inline Configuration
Alternatively, you can update the Start Command directly with timeout settings:

```bash
gunicorn web_app:app --timeout 120 --workers 2 --bind 0.0.0.0:10000
```

### What Changed
1. **Increased Worker Timeout**: From 30s to 120s to handle processing multiple YouTube sources
2. **Batched Processing**: YouTube sources are now processed one at a time with progress updates between each
3. **Better Error Handling**: If one source fails, others will still process
4. **Progress Updates**: Database is updated after each source to persist progress

### Testing
After updating the configuration:
1. Deploy the changes
2. Test with "All Channels" selected
3. Monitor the progress updates as each channel is processed