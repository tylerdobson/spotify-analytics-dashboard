# Validation Notes

This repository includes public-safe validation artifacts generated from demo mode. Demo mode uses deterministic sample data and does not expose private Spotify listening data, credentials, or OAuth tokens.

Finding: In May 2026, my saved Spotify history showed a repeat-listening pattern: the leading artist had 8 plays, and the top repeated track appeared 4 times, turning the raw API feed into a repeat-listening pattern.

## Validation Assets

- Hero dashboard screenshot: `assets/demo/hero.png`
- Listening history dashboard screenshot: `assets/demo/dashboard.png`
- Audio features screenshot: `assets/demo/features.png`
- Playlist workflow screenshot: `assets/demo/workflow.png`
- Demo video poster: `assets/demo/demo-poster.png`
- Demo recording: `assets/demo/demo.mp4`

The screenshots are captured from a real Streamlit session at a 1600x900 viewport with device scale factor 2, producing 3200x1800 PNG files for crisp GitHub README rendering. The MP4 demo is generated from the same fresh app captures at 1920x1080.

## Verification Performed

- Streamlit server started locally.
- Main dashboard pages loaded in browser automation.
- Media capture workflow regenerated all files in `assets/demo`.
- README image and video references resolve to existing files.
- Demo-mode dashboard rendered without Spotify credentials.
- Python files compiled successfully.
- Data-processing tests passed.
- Public validation artifacts do not expose private Spotify listening data or OAuth tokens.

## Local Validation Commands

```powershell
python -m compileall app.py config.py data_processor.py spotify_client.py visualizations.py oauth_callback_capture.py tests
python -m unittest discover -s tests
$env:SPOTIFY_DEMO_MODE="true"
streamlit run app.py --server.port 8502 --server.headless true
npm run capture:media
```

## Recruiter-Facing Summary

This project demonstrates a complete analytics workflow: OAuth authentication, API ingestion, local storage, data transformation, visualization, export workflows, and graceful handling of restricted third-party API endpoints.
