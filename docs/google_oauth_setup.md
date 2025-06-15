# Google OAuth Setup Guide

This guide explains how to configure Google OAuth for Gmail login functionality.

## Prerequisites

- Google Cloud Platform account
- Your application running on `http://127.0.0.1:8080` (or your configured domain)

## Setup Steps

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google+ API (legacy) or Google Identity API

### 2. Configure OAuth Consent Screen

1. Navigate to **APIs & Services** > **OAuth consent screen**
2. Choose **External** user type (for testing)
3. Fill in required fields:
   - App name: "Tidal Fresh" (or your app name)
   - User support email: Your email
   - Developer contact information: Your email
4. Add scopes: `openid`, `email`, `profile`
5. Add test users (your Gmail accounts for testing)

### 3. Create OAuth 2.0 Credentials

1. Navigate to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth 2.0 Client IDs**
3. Choose **Web application**
4. Configure:
   - Name: "Tidal Fresh Web Client"
   - Authorized JavaScript origins: `http://127.0.0.1:8080`
   - Authorized redirect URIs: `http://127.0.0.1:8080/auth/google-callback`

### 4. Configure Environment Variables

Add the following to your `.env` file:

```bash
# Google OAuth Configuration
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
```

Replace the values with your actual credentials from the Google Cloud Console.

### 5. Update Redirect URI for Production

When deploying to production, update the authorized redirect URI to:
```
https://yourdomain.com/auth/google-callback
```

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