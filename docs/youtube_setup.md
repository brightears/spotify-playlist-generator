# YouTube API Setup Guide

## Overview

This guide will walk you through setting up the necessary credentials to use the YouTube Data API with the Spotify Playlist Generator. The application uses YouTube as its primary source for discovering tracks that will be matched with Spotify.

## Why YouTube?

YouTube provides access to a wide range of music content, including:
- Official music videos
- Promotional channels with new releases
- Genre-specific curated playlists
- Independent music from emerging artists

This makes it an excellent source for discovering new tracks to add to your Spotify playlists.

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
- Each API request uses a different number of quota units
- Search operations are more expensive (100 units per call)
- List operations are less expensive (1 unit per call)

## Troubleshooting

If you encounter issues with the YouTube API:

1. Check that your API key is correctly added to the `.env` file
2. Verify that the YouTube Data API v3 is enabled for your project
3. Check your quota usage in the Google Cloud Console
4. Look for any error messages in the application logs

<!-- explainer: This guide provides comprehensive setup instructions for the YouTube API, explaining why YouTube is used as the primary source and how to properly configure API access -->