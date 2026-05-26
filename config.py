from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "listening_history.db"
EXPORT_DIR = BASE_DIR / "exports"
TOKEN_CACHE_PATH = BASE_DIR / ".spotify_cache"

DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"
LOCAL_TIMEZONE = os.getenv("SPOTIFY_LOCAL_TIMEZONE", "America/New_York")

SPOTIFY_SCOPES = " ".join(
    [
        "user-read-currently-playing",
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-recently-played",
        "user-top-read",
        "playlist-read-private",
        "playlist-read-collaborative",
        "playlist-modify-public",
        "playlist-modify-private",
    ]
)


def load_config() -> dict[str, str | bool | Path]:
    load_dotenv(BASE_DIR / ".env")
    DATA_DIR.mkdir(exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)
    EXPORT_DIR.mkdir(exist_ok=True)

    client_id = os.getenv("SPOTIPY_CLIENT_ID", "").strip()
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI", DEFAULT_REDIRECT_URI).strip()
    demo_mode = os.getenv("SPOTIFY_DEMO_MODE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "demo_mode": demo_mode,
        "db_path": DB_PATH,
        "token_cache_path": TOKEN_CACHE_PATH,
        "local_timezone": LOCAL_TIMEZONE,
    }


def credentials_are_configured(config: dict[str, str | bool | Path]) -> bool:
    return bool(config.get("client_id") and config.get("client_secret"))
