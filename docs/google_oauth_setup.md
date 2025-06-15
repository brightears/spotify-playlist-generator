# Google OAuth Setup Guide for Render Deployment

This guide explains how to configure Google OAuth for Gmail login functionality on your Bright Ears application.

## Prerequisites

- Google Cloud Platform account
- Your application deployed on Render (e.g., `https://bright-ears.onrender.com`)

## Setup Steps

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Identity API (not the deprecated Google+ API)

### 2. Configure OAuth Consent Screen

1. Navigate to **APIs & Services** > **OAuth consent screen**
2. Choose **External** user type
3. Fill in required fields:
   - App name: "Bright Ears"
   - User support email: Your email
   - Developer contact information: Your email
4. Add scopes: `openid`, `email`, `profile`
5. Add test users (your Gmail accounts for testing)
6. Submit for review if needed (for production use)

### 3. Create OAuth 2.0 Credentials

1. Navigate to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth 2.0 Client IDs**
3. Choose **Web application**
4. Configure:
   - Name: "Bright Ears Web Client"
   - Authorized JavaScript origins: 
     - `https://bright-ears.onrender.com` (replace with your Render URL)
   - Authorized redirect URIs: 
     - `https://bright-ears.onrender.com/auth/google-callback` (replace with your Render URL)

### 4. Configure Render Environment Variables

1. Go to your Render dashboard
2. Select your web service
3. Go to "Environment" in the left sidebar
4. Add these environment variables:
   - `GOOGLE_CLIENT_ID`: Your OAuth 2.0 Client ID
   - `GOOGLE_CLIENT_SECRET`: Your OAuth 2.0 Client Secret

### 5. Important: Match Redirect URIs Exactly

The redirect URI in your Google Console MUST match exactly with your Render app URL:
- Use HTTPS (not HTTP)
- No trailing slashes
- Case sensitive
- Must include `/auth/google-callback` path

## Testing

1. Start your application: `python web_app.py`
2. Navigate to `http://127.0.0.1:8080/auth/login`
3. Click "Sign in with Google"
4. Complete the OAuth flow
5. You should be redirected back and logged in

## Troubleshooting

- **"redirect_uri_mismatch"**: Ensure your redirect URI exactly matches what's configured in Google Cloud Console
- **"invalid_client"**: Double-check your `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
- **"access_blocked"**: Your app may need verification if using external user type with more than 100 users

## Security Notes

- Keep your client secret secure and never commit it to version control
- Use environment variables for all OAuth credentials
- Consider using internal user type for production if you control user access