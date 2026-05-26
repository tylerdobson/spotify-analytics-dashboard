from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from config import DB_PATH, LOCAL_TIMEZONE


def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listening_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                played_at TIMESTAMP,
                track_id TEXT,
                track_name TEXT,
                artist_name TEXT,
                album_name TEXT,
                duration_ms INTEGER,
                popularity INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(played_at, track_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audio_features (
                track_id TEXT PRIMARY KEY,
                danceability REAL,
                energy REAL,
                valence REAL,
                tempo REAL,
                acousticness REAL,
                instrumentalness REAL,
                speechiness REAL,
                liveness REAL,
                loudness REAL,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS top_content_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date DATE,
                time_period TEXT,
                content_type TEXT,
                rank INTEGER,
                item_id TEXT,
                item_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS playlist_backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id TEXT,
                playlist_name TEXT,
                backup_date DATE,
                track_ids TEXT,
                track_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_played_at ON listening_history(played_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_track_id ON listening_history(track_id)")


def save_listening_history(db_path: Path, tracks: Iterable[dict[str, Any]]) -> int:
    init_db(db_path)
    inserted = 0
    with sqlite3.connect(db_path) as conn:
        for track in tracks:
            if not track.get("played_at") or not track.get("id"):
                continue
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO listening_history (
                    played_at, track_id, track_name, artist_name, album_name,
                    duration_ms, popularity
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    track.get("played_at"),
                    track.get("id"),
                    track.get("name"),
                    track.get("artist_name"),
                    track.get("album_name"),
                    track.get("duration_ms"),
                    track.get("popularity"),
                ),
            )
            inserted += cursor.rowcount
    return inserted


def save_audio_features(db_path: Path, features: Iterable[dict[str, Any]]) -> int:
    init_db(db_path)
    saved = 0
    with sqlite3.connect(db_path) as conn:
        for row in features:
            track_id = row.get("id") or row.get("track_id")
            if not track_id:
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO audio_features (
                    track_id, danceability, energy, valence, tempo, acousticness,
                    instrumentalness, speechiness, liveness, loudness, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    track_id,
                    row.get("danceability"),
                    row.get("energy"),
                    row.get("valence"),
                    row.get("tempo"),
                    row.get("acousticness"),
                    row.get("instrumentalness"),
                    row.get("speechiness"),
                    row.get("liveness"),
                    row.get("loudness"),
                ),
            )
            saved += 1
    return saved


def get_cached_audio_features(db_path: Path, track_ids: Iterable[str]) -> pd.DataFrame:
    init_db(db_path)
    ids = [track_id for track_id in track_ids if track_id]
    if not ids:
        return pd.DataFrame()
    placeholders = ",".join("?" for _ in ids)
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            f"SELECT * FROM audio_features WHERE track_id IN ({placeholders})",
            conn,
            params=ids,
        )


def get_listening_history(db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(
            "SELECT * FROM listening_history ORDER BY played_at DESC",
            conn,
        )
    if df.empty:
        return df
    df["played_at"] = to_local_datetime(df["played_at"])
    df["minutes"] = (df["duration_ms"].fillna(0) / 60000).round(2)
    return df


def get_listening_stats(db_path: Path, start_date: date, end_date: date) -> dict[str, Any]:
    df = get_listening_history(db_path)
    if df.empty:
        return {
            "minutes": 0,
            "hours": 0,
            "plays": 0,
            "unique_artists": 0,
            "unique_tracks": 0,
            "top_artist": "No data yet",
            "top_track": "No data yet",
        }
    mask = (df["played_at"].dt.date >= start_date) & (df["played_at"].dt.date <= end_date)
    scoped = df.loc[mask].copy()
    if scoped.empty:
        return {
            "minutes": 0,
            "hours": 0,
            "plays": 0,
            "unique_artists": 0,
            "unique_tracks": 0,
            "top_artist": "No data yet",
            "top_track": "No data yet",
        }
    minutes = float(scoped["minutes"].sum())
    return {
        "minutes": round(minutes, 1),
        "hours": round(minutes / 60, 1),
        "plays": int(len(scoped)),
        "unique_artists": int(scoped["artist_name"].nunique()),
        "unique_tracks": int(scoped["track_id"].nunique()),
        "top_artist": scoped["artist_name"].mode().iloc[0],
        "top_track": scoped["track_name"].mode().iloc[0],
    }


def calculate_listening_time(tracks: Iterable[dict[str, Any]]) -> float:
    return round(sum((track.get("duration_ms") or 0) for track in tracks) / 60000, 1)


def analyze_genre_distribution(
    artists: Iterable[dict[str, Any]] | None = None,
    tracks: Iterable[dict[str, Any]] | None = None,
    artist_genres: dict[str, list[str]] | None = None,
) -> dict[str, float]:
    counts: Counter[str] = Counter()
    if artists:
        for artist in artists:
            for genre in artist.get("genres", []):
                counts[genre] += 1
    if tracks and artist_genres:
        for track in tracks:
            for artist_id in track.get("artist_ids", []):
                for genre in artist_genres.get(artist_id, []):
                    counts[genre] += 1
    total = sum(counts.values())
    if not total:
        return {}
    return {genre: round(count / total * 100, 1) for genre, count in counts.most_common(15)}


def generate_heatmap_data(db_path: Path = DB_PATH) -> pd.DataFrame:
    df = get_listening_history(db_path)
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    hours = list(range(24))
    if df.empty:
        return pd.DataFrame(0, index=days, columns=hours)
    df["day"] = pd.Categorical(df["played_at"].dt.day_name(), categories=days, ordered=True)
    df["hour"] = df["played_at"].dt.hour
    pivot = df.pivot_table(
        index="day",
        columns="hour",
        values="track_id",
        aggfunc="count",
        fill_value=0,
        observed=False,
    )
    return pivot.reindex(index=days, columns=hours, fill_value=0)


def listening_timeline(db_path: Path = DB_PATH, frequency: str = "D") -> pd.DataFrame:
    df = get_listening_history(db_path)
    if df.empty:
        return pd.DataFrame(columns=["period", "minutes", "plays"])
    grouped = (
        df.set_index("played_at")
        .resample(frequency)
        .agg(minutes=("minutes", "sum"), plays=("track_id", "count"))
        .reset_index()
        .rename(columns={"played_at": "period"})
    )
    grouped["minutes"] = grouped["minutes"].round(1)
    return grouped


def monthly_top_artists(db_path: Path = DB_PATH, months: int = 6) -> pd.DataFrame:
    df = get_listening_history(db_path)
    if df.empty:
        return pd.DataFrame(columns=["month", "artist_name", "plays"])
    cutoff = pd.Timestamp.now(tz=LOCAL_TIMEZONE) - pd.DateOffset(months=months)
    scoped = df[df["played_at"] >= cutoff].copy()
    scoped["month"] = scoped["played_at"].dt.strftime("%Y-%m")
    counts = (
        scoped.groupby(["month", "artist_name"])
        .size()
        .reset_index(name="plays")
        .sort_values(["month", "plays"], ascending=[True, False])
    )
    return counts.groupby("month").head(5)


def track_new_discoveries(db_path: Path = DB_PATH, today: date | None = None) -> pd.DataFrame:
    df = get_listening_history(db_path)
    if df.empty:
        return pd.DataFrame(columns=["artist_name", "first_played_at", "plays"])
    today = today or date.today()
    month_start = today.replace(day=1)
    first_seen = (
        df.groupby("artist_name")
        .agg(first_played_at=("played_at", "min"), plays=("track_id", "count"))
        .reset_index()
    )
    discovered = first_seen[first_seen["first_played_at"].dt.date >= month_start]
    return discovered.sort_values("first_played_at", ascending=False)


def first_listen_for_artists(db_path: Path, artist_names: Iterable[str]) -> pd.DataFrame:
    df = get_listening_history(db_path)
    if df.empty:
        return pd.DataFrame(columns=["artist_name", "first_played_at", "plays"])
    target = set(artist_names)
    scoped = df[df["artist_name"].isin(target)]
    if scoped.empty:
        return pd.DataFrame(columns=["artist_name", "first_played_at", "plays"])
    return (
        scoped.groupby("artist_name")
        .agg(first_played_at=("played_at", "min"), plays=("track_id", "count"))
        .reset_index()
        .sort_values("first_played_at")
    )


def deep_cuts(db_path: Path = DB_PATH, popularity_threshold: int = 45, min_plays: int = 2) -> pd.DataFrame:
    df = get_listening_history(db_path)
    if df.empty:
        return pd.DataFrame(columns=["track_name", "artist_name", "plays", "popularity"])
    scoped = df[df["popularity"].fillna(100) <= popularity_threshold]
    grouped = (
        scoped.groupby(["track_id", "track_name", "artist_name"])
        .agg(plays=("id", "count"), popularity=("popularity", "mean"))
        .reset_index()
    )
    return grouped[grouped["plays"] >= min_plays].sort_values(["plays", "popularity"], ascending=[False, True])


def find_duplicate_tracks(playlists: dict[str, list[dict[str, Any]]]) -> pd.DataFrame:
    track_map: dict[str, dict[str, Any]] = {}
    appearances: defaultdict[str, list[str]] = defaultdict(list)
    for playlist_name, tracks in playlists.items():
        for track in tracks:
            track_id = track.get("id")
            if not track_id:
                continue
            appearances[track_id].append(playlist_name)
            track_map.setdefault(track_id, track)
    rows = []
    for track_id, playlist_names in appearances.items():
        unique_names = sorted(set(playlist_names))
        if len(unique_names) < 2:
            continue
        track = track_map[track_id]
        rows.append(
            {
                "track_id": track_id,
                "track_name": track.get("name"),
                "artist_name": track.get("artist_name"),
                "playlist_count": len(unique_names),
                "playlists": ", ".join(unique_names),
            }
        )
    return pd.DataFrame(rows).sort_values("playlist_count", ascending=False) if rows else pd.DataFrame()


def backup_playlist(db_path: Path, playlist: dict[str, Any], tracks: list[dict[str, Any]]) -> int:
    init_db(db_path)
    track_ids = [track.get("id") for track in tracks if track.get("id")]
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO playlist_backups (
                playlist_id, playlist_name, backup_date, track_ids, track_count
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                playlist.get("id"),
                playlist.get("name"),
                date.today().isoformat(),
                json.dumps(track_ids),
                len(track_ids),
            ),
        )
        return int(cursor.lastrowid)


def get_playlist_backups(db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            "SELECT * FROM playlist_backups ORDER BY created_at DESC",
            conn,
        )


def save_top_content_snapshot(
    db_path: Path,
    time_period: str,
    tracks: Iterable[dict[str, Any]],
    artists: Iterable[dict[str, Any]],
) -> int:
    init_db(db_path)
    snapshot_date = date.today().isoformat()
    rows: list[tuple[str, str, str, int | None, str | None, str | None]] = []
    for item in tracks:
        rows.append((snapshot_date, time_period, "track", item.get("rank"), item.get("id"), item.get("name")))
    for item in artists:
        rows.append((snapshot_date, time_period, "artist", item.get("rank"), item.get("id"), item.get("name")))
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO top_content_snapshots (
                snapshot_date, time_period, content_type, rank, item_id, item_name
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)


def get_month_over_month_stats(db_path: Path = DB_PATH) -> pd.DataFrame:
    df = get_listening_history(db_path)
    if df.empty:
        return pd.DataFrame(columns=["month", "minutes", "plays", "unique_artists"])
    df["month"] = df["played_at"].dt.strftime("%Y-%m")
    return (
        df.groupby("month")
        .agg(
            minutes=("minutes", "sum"),
            plays=("track_id", "count"),
            unique_artists=("artist_name", "nunique"),
        )
        .reset_index()
        .assign(minutes=lambda data: data["minutes"].round(1))
        .sort_values("month")
    )


def generate_monthly_report_html(db_path: Path, report_month: str | None = None) -> str:
    df = get_listening_history(db_path)
    if df.empty:
        return "<html><body><h1>Spotify Monthly Report</h1><p>No listening history saved yet.</p></body></html>"
    if report_month is None:
        report_month = df["played_at"].dt.strftime("%Y-%m").max()
    scoped = df[df["played_at"].dt.strftime("%Y-%m") == report_month]
    if scoped.empty:
        return f"<html><body><h1>Spotify Monthly Report: {report_month}</h1><p>No data for this month.</p></body></html>"

    top_artists = scoped["artist_name"].value_counts().head(10)
    top_tracks = scoped["track_name"].value_counts().head(10)
    minutes = scoped["minutes"].sum()
    items = "\n".join(f"<li>{name}: {count} plays</li>" for name, count in top_artists.items())
    tracks = "\n".join(f"<li>{name}: {count} plays</li>" for name, count in top_tracks.items())
    return f"""
    <html>
      <head>
        <meta charset="utf-8">
        <title>Spotify Monthly Report - {report_month}</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 40px; color: #102018; }}
          h1, h2 {{ color: #0f7a3b; }}
          .stat {{ display: inline-block; margin-right: 24px; font-size: 18px; }}
        </style>
      </head>
      <body>
        <h1>Spotify Monthly Report: {report_month}</h1>
        <p class="stat"><strong>{round(minutes, 1)}</strong> minutes</p>
        <p class="stat"><strong>{len(scoped)}</strong> plays</p>
        <p class="stat"><strong>{scoped["artist_name"].nunique()}</strong> unique artists</p>
        <h2>Top Artists</h2>
        <ol>{items}</ol>
        <h2>Top Tracks</h2>
        <ol>{tracks}</ol>
      </body>
    </html>
    """


def tracks_to_dataframe(tracks: Iterable[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(list(tracks))
    if df.empty:
        return df
    columns = [
        "rank",
        "name",
        "artist_name",
        "album_name",
        "duration_ms",
        "popularity",
        "played_at",
        "id",
        "spotify_url",
    ]
    return df[[column for column in columns if column in df.columns]]


def playlists_to_dataframe(playlists: Iterable[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(list(playlists))
    if df.empty:
        return df
    columns = ["name", "track_count", "owner", "public", "collaborative", "id", "spotify_url"]
    return df[[column for column in columns if column in df.columns]]


def to_local_datetime(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, utc=True, errors="coerce").dt.tz_convert(LOCAL_TIMEZONE)
