# Validation Notes

This repository includes review-safe validation artifacts generated from demo mode. Demo mode uses deterministic sample data and does not expose private Spotify listening data, credentials, or OAuth tokens.

Finding: demo mode keeps the API workflow reviewable without requiring Spotify credentials, OAuth tokens, or private listening-history exports.

## Validation Assets

- Hero dashboard screenshot: `assets/demo/hero.png`
- Listening history dashboard screenshot: `assets/demo/dashboard.png`
- Audio features screenshot: `assets/demo/features.png`
- Playlist workflow screenshot: `assets/demo/workflow.png`
- Screenshot poster: `assets/demo/demo-poster.png`

The screenshots are captured from a real Streamlit session at a 1600x900 viewport with device scale factor 2, producing 3200x1800 PNG files for crisp GitHub README rendering.

## Verification Performed

- Streamlit server started locally.
- Main dashboard pages loaded in browser automation.
- Screenshot capture workflow regenerated static files in `assets/demo`.
- README image and documentation references resolve to existing files.
- Demo-mode dashboard rendered without Spotify credentials.
- Python files compiled successfully.
- Data-processing tests passed.
- Validation artifacts do not expose private Spotify listening data or OAuth tokens.

## Local Validation Commands

```powershell
python -m compileall app.py config.py data_processor.py spotify_client.py visualizations.py oauth_callback_capture.py tests
python -m unittest discover -s tests
$env:SPOTIFY_DEMO_MODE="true"
streamlit run app.py --server.port 8502 --server.headless true
npm run capture:media
```

## Recruiter-Facing Summary

This project demonstrates a reviewable analytics workflow: OAuth-aware configuration, API-boundary design, local storage, data transformation, visualization, export workflows, and graceful handling of restricted third-party API endpoints.
