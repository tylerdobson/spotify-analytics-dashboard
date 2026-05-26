from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import spotipy
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

from config import SPOTIFY_SCOPES, credentials_are_configured, load_config


class SpotifyClientError(RuntimeError):
    pass


class SpotifyFeatureUnavailableError(SpotifyClientError):
    pass


@dataclass
class SpotifyClient:
    demo_mode: bool | None = None
    notices: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.config = load_config()
        self.configured = credentials_are_configured(self.config)
        self.demo_mode = bool(self.demo_mode) if self.demo_mode is not None else bool(
            self.config["demo_mode"] or not self.configured
        )
        self._sp: spotipy.Spotify | None = None
        self.auth_manager: SpotifyOAuth | None = None
        self._user_id: str | None = None

        if self.demo_mode:
            if not self.configured:
                self.notices.append(
                    "Spotify credentials are not configured. The app is showing demo data."
                )
            return

        self.auth_manager = SpotifyOAuth(
            client_id=str(self.config["client_id"]),
            client_secret=str(self.config["client_secret"]),
            redirect_uri=str(self.config["redirect_uri"]),
            scope=SPOTIFY_SCOPES,
            cache_path=str(self.config["token_cache_path"]),
            open_browser=False,
            show_dialog=True,
        )
        self._sp = spotipy.Spotify(auth_manager=self.auth_manager, requests_timeout=20, retries=3)

    @property
    def api(self) -> spotipy.Spotify:
        if not self._sp:
            raise SpotifyClientError("Spotify is not configured. Add .env credentials first.")
        if not self.is_authenticated():
            raise SpotifyClientError("Spotify authentication is not complete.")
        return self._sp

    def is_authenticated(self) -> bool:
        if self.demo_mode:
            return True
        return self.get_token_info() is not None

    def get_token_info(self) -> dict[str, Any] | None:
        if not self.auth_manager:
            return None
        token_info = self.auth_manager.get_cached_token()
        if not token_info:
            return None
        if self.auth_manager.is_token_expired(token_info):
            token_info = self.auth_manager.refresh_access_token(token_info["refresh_token"])
        return token_info

    def get_authorize_url(self) -> str | None:
        if not self.auth_manager:
            return None
        return self.auth_manager.get_authorize_url()

    def complete_authentication(self, callback_url: str) -> bool:
        if not self.auth_manager:
            self.notices.append("Spotify credentials are not configured.")
            return False
        code = self.auth_manager.parse_response_code(callback_url.strip())
        if not code:
            self.notices.append("That callback URL did not include a Spotify authorization code.")
            return False
        self.auth_manager.get_access_token(code=code, as_dict=True, check_cache=False)
        return True

    def needs_authentication(self) -> bool:
        return bool(self.configured and not self.demo_mode and not self.is_authenticated())

    def get_current_user_id(self) -> str:
        if self.demo_mode:
            return "demo-user"
        if not self._user_id:
            self._user_id = self.api.current_user()["id"]
        return self._user_id

    def get_current_track(self) -> dict[str, Any] | None:
        if self.demo_mode:
            return demo_current_track()
        try:
            payload = self.api.current_user_playing_track()
        except SpotifyException as exc:
            self._notice_from_exception(exc, "current playback")
            return None
        if not payload or not payload.get("item"):
            return None
        return normalize_current_track(payload)

    def pause_playback(self) -> bool:
        if self.demo_mode:
            return False
        try:
            self.api.pause_playback()
            return True
        except SpotifyException as exc:
            self._notice_from_exception(exc, "pause playback")
            return False

    def start_playback(self) -> bool:
        if self.demo_mode:
            return False
        try:
            self.api.start_playback()
            return True
        except SpotifyException as exc:
            self._notice_from_exception(exc, "start playback")
            return False

    def get_top_tracks(self, time_range: str = "medium_term", limit: int = 50) -> list[dict[str, Any]]:
        if self.demo_mode:
            return demo_top_tracks(time_range, limit)
        try:
            payload = self.api.current_user_top_tracks(time_range=time_range, limit=limit)
        except SpotifyException as exc:
            self._notice_from_exception(exc, "top tracks")
            return []
        return [normalize_track(item, rank=index + 1) for index, item in enumerate(payload.get("items", []))]

    def get_top_artists(self, time_range: str = "medium_term", limit: int = 50) -> list[dict[str, Any]]:
        if self.demo_mode:
            return demo_top_artists(time_range, limit)
        try:
            payload = self.api.current_user_top_artists(time_range=time_range, limit=limit)
        except SpotifyException as exc:
            self._notice_from_exception(exc, "top artists")
            return []
        return [normalize_artist(item, rank=index + 1) for index, item in enumerate(payload.get("items", []))]

    def get_recently_played(self, limit: int = 50) -> list[dict[str, Any]]:
        if self.demo_mode:
            return demo_recently_played(limit)
        try:
            payload = self.api.current_user_recently_played(limit=limit)
        except SpotifyException as exc:
            self._notice_from_exception(exc, "recently played")
            return []
        tracks: list[dict[str, Any]] = []
        for item in payload.get("items", []):
            track = normalize_track(item.get("track", {}))
            track["played_at"] = item.get("played_at")
            tracks.append(track)
        return tracks

    def get_audio_features(self, track_ids: Iterable[str]) -> list[dict[str, Any]]:
        ids = [track_id for track_id in track_ids if track_id]
        if not ids:
            return []
        if self.demo_mode:
            return demo_audio_features(ids)

        features: list[dict[str, Any]] = []
        try:
            for chunk in chunked(ids, 100):
                rows = self.api.audio_features(chunk) or []
                features.extend([row for row in rows if row])
        except SpotifyException as exc:
            if exc.http_status == 403:
                message = (
                    "Spotify audio features are unavailable for this app. "
                    "New Spotify apps may not have access to that endpoint."
                )
                self.notices.append(message)
                raise SpotifyFeatureUnavailableError(message) from exc
            self._notice_from_exception(exc, "audio features")
        return features

    def get_user_playlists(self, limit: int = 50) -> list[dict[str, Any]]:
        if self.demo_mode:
            return demo_playlists()

        playlists: list[dict[str, Any]] = []
        offset = 0
        while True:
            try:
                payload = self.api.current_user_playlists(limit=limit, offset=offset)
            except SpotifyException as exc:
                self._notice_from_exception(exc, "playlists")
                break
            playlists.extend(normalize_playlist(item) for item in payload.get("items", []))
            if not payload.get("next"):
                break
            offset += limit
        return playlists

    def get_playlist_tracks(self, playlist_id: str) -> list[dict[str, Any]]:
        if self.demo_mode:
            return demo_playlist_tracks(playlist_id)

        tracks: list[dict[str, Any]] = []
        offset = 0
        fields = "items(added_at,track(id,name,duration_ms,popularity,album(name,images),artists(id,name))),next"
        while True:
            try:
                payload = self.api.playlist_items(
                    playlist_id,
                    limit=100,
                    offset=offset,
                    fields=fields,
                    additional_types=("track",),
                )
            except SpotifyException as exc:
                self._notice_from_exception(exc, "playlist tracks")
                break
            for item in payload.get("items", []):
                track = item.get("track")
                if not track:
                    continue
                row = normalize_track(track)
                row["added_at"] = item.get("added_at")
                tracks.append(row)
            if not payload.get("next"):
                break
            offset += 100
        return tracks

    def create_playlist(
        self,
        name: str,
        description: str,
        track_ids: Iterable[str],
        public: bool = False,
    ) -> dict[str, Any] | None:
        ids = [track_id for track_id in track_ids if track_id]
        if self.demo_mode:
            self.notices.append("Demo mode cannot create playlists.")
            return None
        if not ids:
            self.notices.append("No tracks matched the playlist criteria.")
            return None

        try:
            playlist = self.api.user_playlist_create(
                user=self.get_current_user_id(),
                name=name,
                public=public,
                description=description,
            )
            playlist_id = playlist["id"]
            for chunk in chunked([f"spotify:track:{track_id}" for track_id in ids], 100):
                self.api.playlist_add_items(playlist_id, chunk)
            return normalize_playlist(playlist)
        except SpotifyException as exc:
            self._notice_from_exception(exc, "create playlist")
            return None

    def get_artist_genres(self, artist_ids: Iterable[str]) -> dict[str, list[str]]:
        ids = sorted({artist_id for artist_id in artist_ids if artist_id})
        if self.demo_mode:
            artists = demo_top_artists("medium_term", 50)
            return {artist["id"]: artist.get("genres", []) for artist in artists}
        genres: dict[str, list[str]] = {}
        try:
            for chunk in chunked(ids, 50):
                payload = self.api.artists(chunk)
                for artist in payload.get("artists", []):
                    genres[artist["id"]] = artist.get("genres", [])
        except SpotifyException as exc:
            self._notice_from_exception(exc, "artist genres")
        return genres

    def snapshot_top_content(self, time_range: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return self.get_top_tracks(time_range=time_range, limit=50), self.get_top_artists(
            time_range=time_range, limit=50
        )

    def _notice_from_exception(self, exc: SpotifyException, label: str) -> None:
        status = f"HTTP {exc.http_status}" if exc.http_status else "Spotify API error"
        self.notices.append(f"{label}: {status}. {exc.msg or 'Request failed.'}")


def chunked(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def image_url(images: list[dict[str, Any]] | None, smallest: bool = False) -> str | None:
    if not images:
        return None
    ordered = sorted(images, key=lambda item: item.get("width") or 0)
    return ordered[0 if smallest else -1].get("url")


def normalize_track(track: dict[str, Any], rank: int | None = None) -> dict[str, Any]:
    artists = track.get("artists") or []
    album = track.get("album") or {}
    return {
        "rank": rank,
        "id": track.get("id"),
        "name": track.get("name", "Unknown track"),
        "artist_name": ", ".join(artist.get("name", "Unknown artist") for artist in artists),
        "artist_ids": [artist.get("id") for artist in artists if artist.get("id")],
        "album_name": album.get("name", "Unknown album"),
        "album_image_url": image_url(album.get("images")),
        "duration_ms": track.get("duration_ms") or 0,
        "popularity": track.get("popularity"),
        "spotify_url": (track.get("external_urls") or {}).get("spotify"),
    }


def normalize_artist(artist: dict[str, Any], rank: int | None = None) -> dict[str, Any]:
    return {
        "rank": rank,
        "id": artist.get("id"),
        "name": artist.get("name", "Unknown artist"),
        "genres": artist.get("genres", []),
        "popularity": artist.get("popularity"),
        "followers": (artist.get("followers") or {}).get("total"),
        "image_url": image_url(artist.get("images")),
        "spotify_url": (artist.get("external_urls") or {}).get("spotify"),
    }


def normalize_playlist(playlist: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": playlist.get("id"),
        "name": playlist.get("name", "Untitled playlist"),
        "description": playlist.get("description") or "",
        "track_count": (playlist.get("tracks") or {}).get("total", 0),
        "public": playlist.get("public"),
        "collaborative": playlist.get("collaborative"),
        "owner": (playlist.get("owner") or {}).get("display_name"),
        "image_url": image_url(playlist.get("images")),
        "spotify_url": (playlist.get("external_urls") or {}).get("spotify"),
    }


def normalize_current_track(payload: dict[str, Any]) -> dict[str, Any]:
    track = normalize_track(payload.get("item", {}))
    progress_ms = payload.get("progress_ms") or 0
    duration_ms = track.get("duration_ms") or 1
    track.update(
        {
            "is_playing": bool(payload.get("is_playing")),
            "progress_ms": progress_ms,
            "progress_percent": min(100, round(progress_ms / duration_ms * 100, 1)),
            "device": (payload.get("device") or {}).get("name"),
        }
    )
    return track


def demo_top_artists(time_range: str = "medium_term", limit: int = 50) -> list[dict[str, Any]]:
    base = [
        ("the midnight", ["synthwave", "indie pop"], 74),
        ("Khruangbin", ["psychedelic funk", "instrumental"], 73),
        ("Little Simz", ["alternative hip hop", "uk hip hop"], 76),
        ("Fred again..", ["uk dance", "electronica"], 82),
        ("Nils Frahm", ["compositional ambient", "neo-classical"], 66),
        ("Japanese Breakfast", ["indie rock", "dream pop"], 70),
        ("Bad Bunny", ["reggaeton", "latin trap"], 91),
        ("boygenius", ["indie rock", "folk rock"], 75),
        ("Jungle", ["modern funk", "neo soul"], 74),
        ("SZA", ["r&b", "pop"], 88),
    ]
    return [
        {
            "rank": index + 1,
            "id": f"demo-artist-{index + 1}",
            "name": name,
            "genres": genres,
            "popularity": popularity,
            "followers": 100000 + index * 47000,
            "image_url": None,
            "spotify_url": None,
        }
        for index, (name, genres, popularity) in enumerate(base[:limit])
    ]


def demo_top_tracks(time_range: str = "medium_term", limit: int = 50) -> list[dict[str, Any]]:
    artists = demo_top_artists(time_range, 10)
    names = [
        "Night Drive",
        "August 10",
        "Introvert",
        "Delilah",
        "Says",
        "Paprika",
        "Titi Me Pregunto",
        "Not Strong Enough",
        "Back on 74",
        "Good Days",
        "Sunset Static",
        "Late Checkout",
        "Blue Hour",
        "North Loop",
        "Afterimage",
    ]
    rows = []
    for index in range(limit):
        name = names[index % len(names)]
        artist = artists[index % len(artists)]
        rows.append(
            {
                "rank": index + 1,
                "id": f"demo-track-{index + 1}",
                "name": name,
                "artist_name": artist["name"],
                "artist_ids": [artist["id"]],
                "album_name": "Demo Rotation",
                "album_image_url": None,
                "duration_ms": 185000 + index * 7000,
                "popularity": max(35, 88 - index * 3),
                "spotify_url": None,
            }
        )
    return rows


def demo_recently_played(limit: int = 50) -> list[dict[str, Any]]:
    tracks = demo_top_tracks(limit=15)
    now = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for index in range(limit):
        track = dict(tracks[index % len(tracks)])
        played_at = now - timedelta(hours=index * 5 + (index % 3) * 2)
        track["played_at"] = played_at.isoformat().replace("+00:00", "Z")
        rows.append(track)
    return rows


def demo_current_track() -> dict[str, Any]:
    track = dict(demo_top_tracks(limit=1)[0])
    track.update(
        {
            "is_playing": True,
            "progress_ms": 87000,
            "progress_percent": 47,
            "device": "Demo device",
        }
    )
    return track


def demo_audio_features(track_ids: Iterable[str]) -> list[dict[str, Any]]:
    rows = []
    for index, track_id in enumerate(track_ids):
        rows.append(
            {
                "id": track_id,
                "danceability": round(0.42 + (index % 6) * 0.08, 2),
                "energy": round(0.35 + (index % 7) * 0.07, 2),
                "valence": round(0.28 + (index % 8) * 0.07, 2),
                "tempo": 86 + (index % 12) * 8,
                "acousticness": round(max(0.05, 0.7 - (index % 6) * 0.09), 2),
                "instrumentalness": round((index % 5) * 0.08, 2),
                "speechiness": round(0.03 + (index % 4) * 0.025, 2),
                "liveness": round(0.08 + (index % 5) * 0.05, 2),
                "loudness": -14 + (index % 8),
            }
        )
    return rows


def demo_playlists() -> list[dict[str, Any]]:
    return [
        {
            "id": "demo-playlist-workout",
            "name": "Workout: high energy",
            "description": "Demo playlist",
            "track_count": 32,
            "public": False,
            "collaborative": False,
            "owner": "demo-user",
            "image_url": None,
            "spotify_url": None,
        },
        {
            "id": "demo-playlist-focus",
            "name": "Focus: quiet loops",
            "description": "Demo playlist",
            "track_count": 45,
            "public": False,
            "collaborative": False,
            "owner": "demo-user",
            "image_url": None,
            "spotify_url": None,
        },
        {
            "id": "demo-playlist-weekend",
            "name": "Weekend reset",
            "description": "Demo playlist",
            "track_count": 28,
            "public": True,
            "collaborative": False,
            "owner": "demo-user",
            "image_url": None,
            "spotify_url": None,
        },
    ]


def demo_playlist_tracks(playlist_id: str) -> list[dict[str, Any]]:
    tracks = demo_top_tracks(limit=12)
    if playlist_id.endswith("focus"):
        return tracks[3:12]
    if playlist_id.endswith("weekend"):
        return tracks[0:8] + tracks[10:12]
    return tracks[0:10]
