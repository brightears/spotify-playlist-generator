# Render Deployment Guide

## Quick Deploy to Render

1. **Fork or push this repository to GitHub**

2. **Create a new Web Service on Render**
   - Go to https://render.com/
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Use these settings:
     - **Name**: bright-ears (or your preferred name)
     - **Runtime**: Python
     - **Build Command**: `./build.sh`
     - **Start Command**: `gunicorn web_app:app`

3. **Set Environment Variables**
   In the Render dashboard, add these environment variables:
   
   **Required:**
   - `SPOTIFY_CLIENT_ID` - From Spotify Developer Dashboard
   - `SPOTIFY_CLIENT_SECRET` - From Spotify Developer Dashboard
   - `YOUTUBE_API_KEY` - From Google Cloud Console
   
   **Optional:**
   - `GOOGLE_CLIENT_ID` - For Google OAuth login
   - `GOOGLE_CLIENT_SECRET` - For Google OAuth login
   - `STRIPE_PUBLISHABLE_KEY` - For payment processing
   - `STRIPE_SECRET_KEY` - For payment processing
   - `STRIPE_WEBHOOK_SECRET` - For Stripe webhooks

4. **Database Setup**
   - The render.yaml file will automatically create a PostgreSQL database
   - The build script will initialize the database schema

5. **Deploy**
   - Click "Create Web Service"
   - Render will automatically build and deploy your app

## Manual Deployment (without render.yaml)

If you prefer to configure manually:

1. Create a PostgreSQL database on Render
2. Add the database connection string as `DATABASE_URL` environment variable
3. Set Python version to 3.11 in environment variables: `PYTHON_VERSION=3.11`
4. Use the same build and start commands as above

## Post-Deployment

1. **Update OAuth Redirect URIs**
   - Spotify: Add `https://your-app.onrender.com/spotify/callback`
   - Google: Add `https://your-app.onrender.com/auth/google/callback`

2. **Test the deployment**
   - Visit `https://your-app.onrender.com`
   - Try creating an account and logging in
   - Test playlist generation

## Troubleshooting

- **Database errors**: Check that DATABASE_URL is properly set
- **OAuth errors**: Verify redirect URIs match your Render URL
- **Import errors**: Check logs in Render dashboard
- **CSRF errors**: Ensure cookies are enabled and using HTTPS