# Setup Guide

This guide walks through a clean local setup on Windows PowerShell.

## 1. Create a Spotify App

1. Open https://developer.spotify.com/dashboard
2. Create a new app.
3. Select **Web API**.
4. Add this redirect URI:

   ```text
   http://127.0.0.1:8888/callback
   ```

5. Save the app.
6. Copy the Client ID and Client Secret.

## 2. Create `.env`

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```text
SPOTIPY_CLIENT_ID=your_client_id_here
SPOTIPY_CLIENT_SECRET=your_client_secret_here
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
SPOTIFY_DEMO_MODE=false
```

## 3. Install Dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 4. Run the App

```powershell
streamlit run app.py
```

Open:

```text
http://localhost:8501
```

## 5. Authenticate

Click **Log in with Spotify** and approve access. If the callback page says authorization was received, return to the dashboard and reload.

## 6. Build Local History

Click **Sync last 50 plays to database**. Spotify only exposes the latest 50 recently played items, so repeat this periodically for richer history.
