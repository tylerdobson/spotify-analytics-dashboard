# Spotify API Limitations

Spotify changed access to several Web API endpoints for many new apps on November 27, 2024. The affected endpoints include Audio Features, Audio Analysis, Recommendations, Related Artists, and some browsing endpoints.

## How This App Handles It

The dashboard treats restricted endpoints as optional. If Spotify returns `403` for audio features:

- The dashboard remains usable.
- Top tracks, top artists, playback, playlists, exports, and local listening history still work.
- Audio feature charts show an unavailable-state message instead of crashing.
- Mood playlist generation is disabled when feature vectors are unavailable.

## Why This Matters

The project remains review-ready even when Spotify API access differs between developer accounts. The important engineering behavior is graceful degradation, not assuming every optional endpoint is available.

## Reference

Spotify announcement:

https://developer.spotify.com/blog/2024-11-27-changes-to-the-web-api
