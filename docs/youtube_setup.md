# YouTube API Setup Guide

This guide will walk you through setting up the necessary credentials to use the YouTube Data API with the Spotify Playlist Generator.

## Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the project dropdown at the top of the page and select "New Project".
3. Name your project (e.g., "Spotify Playlist Generator") and click "Create".
4. Wait for the project to be created, then select it from the project dropdown.

## Step 2: Enable the YouTube Data API

1. In the left sidebar, navigate to "APIs & Services" > "Library".
2. Search for "YouTube Data API v3" and click on it.
3. Click "Enable" to enable the API for your project.

## Step 3: Create API Credentials

For this application, you'll need an API key to access public YouTube data:

1. In the left sidebar, navigate to "APIs & Services" > "Credentials".
2. Click the "Create Credentials" button and select "API key".
3. Your new API key will be displayed. Copy this key.
4. (Optional but recommended) Click "Restrict key" to limit the API key usage:
   - Under "Application restrictions", choose "HTTP referrers" and add your domains.
   - Under "API restrictions", select "Restrict key" and choose "YouTube Data API v3".
   - Click "Save".

## Step 4: Add the API Key to Your Environment

1. Open your `.env` file in the root directory of the project.
2. Add the following line with your API key:
   ```
   YOUTUBE_API_KEY=your_api_key_here
   ```
3. Save the file.

## Step 5: Verify Your Setup

To verify that your YouTube API key is working correctly:

1. Run the application with `python web_app.py`.
2. Create a new playlist and select "YouTube" as a source.
3. If tracks are successfully fetched from YouTube, your setup is working.

## API Usage and Quotas

The YouTube Data API has usage limits:

- Free tier: 10,000 units per day
- Each search request costs approximately 100 units
- Each video details request costs approximately 1 unit

Monitor your usage in the Google Cloud Console under "APIs & Services" > "Dashboard".

## Troubleshooting

If you encounter any issues:

1. **403 Forbidden Error**: Verify your API key is correct and has the proper permissions.
2. **Quota Exceeded Error**: You've reached your daily quota limit. Wait until it resets or request increased quota.
3. **API Not Enabled Error**: Make sure you've enabled the YouTube Data API v3 for your project.

For more detailed information, visit the [YouTube Data API Documentation](https://developers.google.com/youtube/v3/getting-started).

<!-- explainer: This guide explains how to set up YouTube API access for fetching track data from YouTube channels and playlists -->