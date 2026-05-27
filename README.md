# Spotify Analytics Dashboard

## Overview
A Python analytics dashboard for exploring Spotify listening and playlist-style data flows. The public copy keeps API credentials out of the repo and uses demo-safe paths only.

## Problem
Spotify API projects often mix credential handling, private listening history, and analysis code. This project separates the app workflow from real secrets and private account data.

## Features
- Spotify API client structure
- Token/cache exclusion through `.gitignore`
- Dashboard and visualization modules
- Demo-safe data-processing workflow
- Tests and documentation structure

## Tech Stack
- Python
- Streamlit
- Pandas
- Plotly
- Spotify Web API

## Architecture
The app is split across client, config, data-processing, visualization, and dashboard modules. API credentials are read from environment variables and are not included.

## Data Source

Live use depends on the Spotify Web API and the user account that authenticates locally. No private account exports are redistributed.

## Data Limitations

Any live results depend on the authenticated user account and Spotify API availability; public examples should be treated as workflow demonstrations only.

## AI / API Assumptions

This project does not include AI model calls. API credentials must be supplied locally through environment variables.

## Setup
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Environment Variables
Copy `.env.example` to `.env` locally and use your own Spotify API placeholders. Do not commit real tokens, cache files, or personal listening exports.

## How To Run
```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Tests
```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Demo / Screenshots
Demo assets are generated in public-safe demo mode:

- `assets/demo/hero.png`
- `assets/demo/dashboard.png`
- `assets/demo/top-content.png`
- `assets/demo/history.png`
- `assets/demo/features.png`
- `assets/demo/workflow.png`
- `assets/demo/demo.webm`
- `assets/demo/demo.gif`
- `assets/demo/narrated-demo.mp4`

The narrated MP4 is generated from the public-safe WebM capture plus local text-to-speech narration. It uses demo-mode data only and does not include Spotify credentials, tokens, or private listening exports.

Regenerate them with:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
$env:SPOTIFY_DEMO_MODE="true"
.\.venv\Scripts\python.exe scripts\capture_spotify_media.py
```

## Security / Privacy Notes
No Spotify client secrets, OAuth tokens, cache files, or private listening-history exports are included. The public repo is for code review and demo-safe operation.

## Limitations
- Requires a user-created Spotify developer app for live API use.
- Does not include private listening history.
- Demo assets use deterministic sample data, not a personal account export.

## Roadmap
- Add richer offline export examples.
- Add a deployment note only if a real public deployment exists.
- Keep API limitation notes current as Spotify endpoint access changes.

## License
MIT License. See `LICENSE`.
