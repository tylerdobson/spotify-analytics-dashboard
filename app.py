from __future__ import annotations

from datetime import date, timedelta
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

import data_processor as dp
import visualizations as viz
from config import DB_PATH, DEFAULT_REDIRECT_URI, load_config
from spotify_client import SpotifyClient, SpotifyFeatureUnavailableError


st.set_page_config(page_title="Spotify Analytics", layout="wide")


TIME_RANGES = {
    "Last 4 Weeks": "short_term",
    "Last 6 Months": "medium_term",
    "All Time": "long_term",
}


MOOD_FILTERS = {
    "Workout": {
        "description": "High energy, higher tempo tracks from your top music.",
        "rules": lambda df: df[(df["energy"] >= 0.68) & (df["tempo"] >= 115)],
    },
    "Focus": {
        "description": "Lower energy, more acoustic or instrumental tracks.",
        "rules": lambda df: df[(df["energy"] <= 0.55) & ((df["acousticness"] >= 0.35) | (df["instrumentalness"] >= 0.25))],
    },
    "Happy": {
        "description": "Positive mood tracks with enough movement.",
        "rules": lambda df: df[(df["valence"] >= 0.6) & (df["danceability"] >= 0.45)],
    },
    "Chill": {
        "description": "Lower energy tracks with gentler mood.",
        "rules": lambda df: df[(df["energy"] <= 0.6) & (df["valence"] <= 0.65)],
    },
}

OAUTH_CALLBACK_CAPTURE_PATH = DB_PATH.parent / "oauth_callback_url.txt"


@st.cache_resource(show_spinner=False)
def get_spotify_client() -> SpotifyClient:
    return SpotifyClient()


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --spotify-green: #1DB954;
            --ink: #17251d;
            --muted: #637066;
            --line: #dfe8df;
            --surface: #ffffff;
            --soft: #f5f8f4;
        }
        .block-container {
            padding-top: 2.1rem;
            padding-bottom: 3rem;
            max-width: 1380px;
        }
        h1, h2, h3 {
            letter-spacing: 0;
            color: var(--ink);
        }
        [data-testid="stSidebar"] {
            background: #0c1510;
        }
        [data-testid="stSidebar"] * {
            color: #f5fff7;
        }
        .app-title {
            display: flex;
            align-items: center;
            gap: .75rem;
            margin-bottom: .35rem;
        }
        .brand-dot {
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: var(--spotify-green);
            box-shadow: 0 0 0 6px rgba(29,185,84,.12);
            flex: 0 0 auto;
        }
        .subtle {
            color: var(--muted);
            margin-top: -.3rem;
        }
        .metric-card {
            border: 1px solid var(--line);
            background: var(--surface);
            border-radius: 8px;
            padding: 1rem 1.05rem;
            min-height: 104px;
        }
        .metric-label {
            color: var(--muted);
            font-size: .78rem;
            text-transform: uppercase;
            letter-spacing: .04em;
            margin-bottom: .45rem;
        }
        .metric-value {
            font-size: 1.65rem;
            font-weight: 750;
            color: var(--ink);
            line-height: 1.1;
        }
        .metric-help {
            color: var(--muted);
            font-size: .86rem;
            margin-top: .35rem;
        }
        .track-card {
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 1.15rem;
            background: linear-gradient(135deg, #ffffff 0%, #f7fbf6 100%);
        }
        .track-title {
            font-size: 1.35rem;
            font-weight: 760;
            color: var(--ink);
            line-height: 1.2;
        }
        .track-meta {
            color: var(--muted);
            margin-top: .25rem;
        }
        .table-rank {
            color: var(--spotify-green);
            font-weight: 760;
        }
        .html-table-wrap {
            overflow-x: auto;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: white;
            margin: .35rem 0 1rem;
        }
        table.html-table {
            width: 100%;
            border-collapse: collapse;
            font-size: .9rem;
        }
        .html-table th {
            text-align: left;
            padding: .7rem .8rem;
            background: #f5f8f4;
            color: #17251d;
            border-bottom: 1px solid var(--line);
            white-space: nowrap;
        }
        .html-table td {
            padding: .65rem .8rem;
            border-bottom: 1px solid #edf2ec;
            color: #26352b;
            vertical-align: top;
        }
        .html-table tr:last-child td {
            border-bottom: 0;
        }
        .html-table a {
            color: #0f7a3b;
            font-weight: 700;
            text-decoration: none;
        }
        .stButton > button, .stDownloadButton > button {
            border-radius: 8px;
            border: 1px solid #12863c;
            background: #12863c;
            color: white;
            font-weight: 650;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            border-color: #0b6d2d;
            background: #0b6d2d;
            color: white;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="app-title">
            <div class="brand-dot"></div>
            <h1 style="margin:0">{title}</h1>
        </div>
        <p class="subtle">{subtitle}</p>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str | int | float, help_text: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-help">{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_table(
    data: pd.DataFrame | list[dict[str, Any]],
    max_rows: int = 30,
    link_columns: set[str] | None = None,
    hidden_columns: set[str] | None = None,
    empty_message: str = "No rows to show.",
) -> None:
    df = pd.DataFrame(data).copy()
    if df.empty:
        st.info(empty_message)
        return

    link_columns = link_columns or set()
    hidden_columns = hidden_columns or set()
    hidden_columns = hidden_columns | {"artist_ids", "album_image_url", "image_url"}
    columns = [column for column in df.columns if column not in hidden_columns]
    df = df[columns].head(max_rows).fillna("")

    def format_value(column: str, value: Any) -> str:
        if isinstance(value, pd.Timestamp):
            value = value.strftime("%Y-%m-%d %H:%M")
        elif isinstance(value, (list, tuple, set)):
            value = ", ".join(str(item) for item in value)
        else:
            value = str(value)

        if column in link_columns and value.startswith("http"):
            return f'<a href="{escape(value)}" target="_blank">Open</a>'

        if len(value) > 140:
            value = value[:137] + "..."
        return escape(value)

    header = "".join(f"<th>{escape(str(column).replace('_', ' ').title())}</th>" for column in df.columns)
    body_rows = []
    for _, row in df.iterrows():
        cells = "".join(f"<td>{format_value(column, row[column])}</td>" for column in df.columns)
        body_rows.append(f"<tr>{cells}</tr>")

    if len(pd.DataFrame(data)) > max_rows:
        st.caption(f"Showing first {max_rows} rows.")

    st.markdown(
        f"""
        <div class="html-table-wrap">
          <table class="html-table">
            <thead><tr>{header}</tr></thead>
            <tbody>{''.join(body_rows)}</tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_notices(client: SpotifyClient) -> None:
    for notice in dict.fromkeys(client.notices):
        st.info(notice)


@st.cache_resource(show_spinner=False)
def start_oauth_callback_listener(redirect_uri: str) -> str:
    parsed = urlparse(redirect_uri)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port
    if not port:
        return "OAuth callback listener was not started because the redirect URI has no port."

    class OAuthCallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            full_url = f"{parsed.scheme}://{self.headers.get('Host')}{self.path}"
            OAUTH_CALLBACK_CAPTURE_PATH.parent.mkdir(exist_ok=True)
            OAUTH_CALLBACK_CAPTURE_PATH.write_text(full_url, encoding="utf-8")
            body = b"""
            <html>
              <head><title>Spotify authorization received</title></head>
              <body style="font-family: Arial, sans-serif; margin: 48px;">
                <h1>Spotify authorization received</h1>
                <p>You can return to the Spotify Analytics dashboard now.</p>
              </body>
            </html>
            """
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    try:
        server = ThreadingHTTPServer((host, port), OAuthCallbackHandler)
    except OSError as exc:
        return f"OAuth callback listener could not bind to {host}:{port}: {exc}"

    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return f"OAuth callback listener is ready on {host}:{port}."


def authentication_page(client: SpotifyClient) -> None:
    page_header(
        "Connect Spotify",
        "Authorize your Spotify account so the dashboard can load live playback, top content, and playlists.",
    )
    listener_status = start_oauth_callback_listener(str(client.config["redirect_uri"]))
    st.info(listener_status)

    if OAUTH_CALLBACK_CAPTURE_PATH.exists():
        callback_url = OAUTH_CALLBACK_CAPTURE_PATH.read_text(encoding="utf-8").strip()
        if "code=" in callback_url:
            try:
                if client.complete_authentication(callback_url):
                    OAUTH_CALLBACK_CAPTURE_PATH.unlink(missing_ok=True)
                    st.cache_resource.clear()
                    st.success("Spotify authentication completed. Reloading the dashboard.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Spotify token exchange failed: {exc}")

    auth_url = client.get_authorize_url()
    if auth_url:
        st.markdown(
            f"""
            <a href="{auth_url}" target="_self" style="
                display:inline-block;
                padding:0.7rem 1rem;
                background:#12863c;
                color:white;
                border-radius:8px;
                text-decoration:none;
                font-weight:700;
            ">Log in with Spotify</a>
            """,
            unsafe_allow_html=True,
        )

    st.write(
        "After approving Spotify access, you should see a simple authorization success page. "
        "Then come back to this dashboard and reload it."
    )
    pasted_url = st.text_input(
        "If the callback page still fails, paste the full redirected URL here",
        placeholder="http://127.0.0.1:8888/callback?code=...",
    )
    if st.button("Complete Spotify authentication", disabled=not pasted_url):
        try:
            if client.complete_authentication(pasted_url):
                OAUTH_CALLBACK_CAPTURE_PATH.unlink(missing_ok=True)
                st.cache_resource.clear()
                st.success("Spotify authentication completed. Reloading the dashboard.")
                st.rerun()
        except Exception as exc:
            st.error(f"Spotify token exchange failed: {exc}")


def sync_recently_played(client: SpotifyClient) -> int:
    tracks = client.get_recently_played(limit=50)
    return dp.save_listening_history(DB_PATH, tracks)


def get_features_for_tracks(client: SpotifyClient, tracks: list[dict[str, Any]]) -> pd.DataFrame:
    track_ids = [track["id"] for track in tracks if track.get("id")]
    cached = dp.get_cached_audio_features(DB_PATH, track_ids)
    missing = sorted(set(track_ids) - set(cached["track_id"].tolist() if not cached.empty else []))

    if missing:
        try:
            fetched = client.get_audio_features(missing)
        except SpotifyFeatureUnavailableError:
            fetched = []
        if fetched:
            dp.save_audio_features(DB_PATH, fetched)
            cached = dp.get_cached_audio_features(DB_PATH, track_ids)

    if cached.empty:
        return pd.DataFrame()

    track_df = pd.DataFrame(tracks)
    return track_df.merge(cached, left_on="id", right_on="track_id", how="inner")


def home_page(client: SpotifyClient) -> None:
    page_header(
        "Spotify Analytics",
        "Live playback, personal listening trends, playlist hygiene, and exportable music data.",
    )

    col_a, col_b = st.columns([1.15, 1])
    with col_a:
        st.subheader("Currently playing")
        current = client.get_current_track()
        if current:
            art_col, text_col = st.columns([0.28, 0.72])
            with art_col:
                if current.get("album_image_url"):
                    st.image(current["album_image_url"], use_column_width=True)
                else:
                    st.markdown(
                        "<div class='track-card' style='height:180px;display:flex;align-items:center;justify-content:center;color:#637066'>No artwork</div>",
                        unsafe_allow_html=True,
                    )
            with text_col:
                state = "Playing" if current.get("is_playing") else "Paused"
                st.markdown(
                    f"""
                    <div class="track-card">
                        <div class="metric-label">{state}</div>
                        <div class="track-title">{current.get("name")}</div>
                        <div class="track-meta">{current.get("artist_name")} - {current.get("album_name")}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.progress(int(current.get("progress_percent") or 0))
                minutes = int((current.get("progress_ms") or 0) / 60000)
                seconds = int(((current.get("progress_ms") or 0) % 60000) / 1000)
                duration_min = int((current.get("duration_ms") or 0) / 60000)
                duration_sec = int(((current.get("duration_ms") or 0) % 60000) / 1000)
                st.caption(f"{minutes}:{seconds:02d} / {duration_min}:{duration_sec:02d}")
                if st.button("Pause", disabled=client.demo_mode or not current.get("is_playing")):
                    client.pause_playback()
                    st.rerun()
                if st.button("Play", disabled=client.demo_mode or current.get("is_playing")):
                    client.start_playback()
                    st.rerun()
        else:
            st.info("Nothing is playing right now, or Spotify playback is not available.")

    with col_b:
        st.subheader("Quick actions")
        if st.button("Sync last 50 plays to database", use_container_width=True):
            inserted = sync_recently_played(client)
            st.success(f"Saved {inserted} new plays.")
        st.caption("Spotify only exposes the latest 50 recently played tracks, so open or schedule the app regularly for richer history.")

    today = date.today()
    week_start = today - timedelta(days=6)
    month_start = today.replace(day=1)
    today_stats = dp.get_listening_stats(DB_PATH, today, today)
    week_stats = dp.get_listening_stats(DB_PATH, week_start, today)
    month_stats = dp.get_listening_stats(DB_PATH, month_start, today)
    playlists = client.get_user_playlists()
    top_artists = client.get_top_artists(limit=20)
    genres = dp.analyze_genre_distribution(artists=top_artists)
    top_genre = next(iter(genres.keys()), "No data yet")

    st.subheader("At a glance")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Today", f"{today_stats['minutes']} min", f"{today_stats['plays']} plays")
    with col2:
        metric_card("Last 7 days", f"{week_stats['hours']} hr", f"{week_stats['unique_artists']} artists")
    with col3:
        metric_card("This month", f"{month_stats['hours']} hr", f"{month_stats['unique_tracks']} tracks")
    with col4:
        metric_card("Top genre now", top_genre.title(), f"{len(playlists)} playlists")

    st.subheader("Recent activity")
    history = dp.listening_timeline(DB_PATH, "D")
    st.plotly_chart(viz.plot_listening_timeline(history.tail(45)), use_container_width=True)


def top_content_page(client: SpotifyClient) -> None:
    page_header("Top Content", "Compare your strongest tracks, artists, and genres across Spotify time windows.")
    label = st.radio("Time period", list(TIME_RANGES.keys()), index=1, horizontal=True)
    time_range = TIME_RANGES[label]

    tracks = client.get_top_tracks(time_range=time_range, limit=50)
    artists = client.get_top_artists(time_range=time_range, limit=50)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Top tracks")
        st.plotly_chart(viz.plot_top_tracks_chart(tracks), use_container_width=True)
        render_table(dp.tracks_to_dataframe(tracks[:25]), link_columns={"spotify_url"})
    with col2:
        st.subheader("Top artists")
        st.plotly_chart(viz.plot_top_artists_chart(artists), use_container_width=True)
        render_table(pd.DataFrame(artists[:25]), link_columns={"spotify_url"})

    genre_data = dp.analyze_genre_distribution(artists=artists)
    genre_col, action_col = st.columns([0.65, 0.35])
    with genre_col:
        st.subheader("Genre distribution")
        st.plotly_chart(viz.plot_genre_pie_chart(genre_data), use_container_width=True)
    with action_col:
        st.subheader("Snapshot")
        st.write("Save today's top tracks and artists so you can compare taste changes over time.")
        if st.button("Save top content snapshot", use_container_width=True):
            count = dp.save_top_content_snapshot(DB_PATH, time_range, tracks, artists)
            st.success(f"Saved {count} ranked items.")
        st.download_button(
            "Download top tracks CSV",
            data=dp.tracks_to_dataframe(tracks).to_csv(index=False),
            file_name=f"spotify_top_tracks_{time_range}.csv",
            mime="text/csv",
            use_container_width=True,
        )


def history_page(client: SpotifyClient) -> None:
    page_header("Listening History", "Build a local history from Spotify's recently played feed and inspect patterns over time.")
    col_a, col_b = st.columns([0.25, 0.75])
    with col_a:
        if st.button("Sync recent plays", use_container_width=True):
            inserted = sync_recently_played(client)
            st.success(f"Saved {inserted} new plays.")
        history_df = dp.get_listening_history(DB_PATH)
        metric_card("Saved plays", len(history_df), "Local SQLite rows")
        if not history_df.empty:
            metric_card("Unique artists", history_df["artist_name"].nunique(), "Across saved history")
    with col_b:
        frequency = st.radio("Timeline grain", ["Daily", "Weekly"], horizontal=True)
        timeline = dp.listening_timeline(DB_PATH, "D" if frequency == "Daily" else "W")
        st.plotly_chart(viz.plot_listening_timeline(timeline), use_container_width=True)

    heat_col, monthly_col = st.columns(2)
    with heat_col:
        st.subheader("Listening heatmap")
        st.plotly_chart(viz.plot_listening_heatmap(dp.generate_heatmap_data(DB_PATH)), use_container_width=True)
    with monthly_col:
        st.subheader("Top artists per month")
        st.plotly_chart(viz.plot_monthly_artists(dp.monthly_top_artists(DB_PATH)), use_container_width=True)

    st.subheader("Month-over-month")
    st.plotly_chart(viz.plot_month_over_month(dp.get_month_over_month_stats(DB_PATH)), use_container_width=True)


def audio_features_page(client: SpotifyClient) -> None:
    page_header("Audio Features", "Map your taste by energy, mood, tempo, and texture where Spotify allows feature access.")
    label = st.radio("Track source", list(TIME_RANGES.keys()), index=1, horizontal=True)
    tracks = client.get_top_tracks(time_range=TIME_RANGES[label], limit=50)
    features = get_features_for_tracks(client, tracks)

    if features.empty:
        st.warning(
            "No audio features are available yet. If you created your Spotify app after November 27, 2024, Spotify may block the audio features endpoint for new apps."
        )
    else:
        col1, col2 = st.columns([0.45, 0.55])
        with col1:
            st.subheader("Average feature profile")
            st.plotly_chart(viz.plot_audio_features_radar(features), use_container_width=True)
        with col2:
            st.subheader("Energy vs valence")
            st.plotly_chart(viz.plot_energy_valence_scatter(features), use_container_width=True)
        st.subheader("Preferred tempo")
        st.plotly_chart(viz.plot_bpm_distribution(features), use_container_width=True)
        render_table(
            features[
                [
                    "name",
                    "artist_name",
                    "danceability",
                    "energy",
                    "valence",
                    "tempo",
                    "acousticness",
                    "instrumentalness",
                    "popularity",
                ]
            ]
        )


def playlists_page(client: SpotifyClient) -> None:
    page_header("Playlist Manager", "Audit playlists, find duplicates, back up snapshots, and generate mood-based playlists.")
    playlists = client.get_user_playlists()
    playlist_df = dp.playlists_to_dataframe(playlists)
    st.subheader("Your playlists")
    render_table(playlist_df, link_columns={"spotify_url"})

    if not playlists:
        st.info("No playlists were returned.")
        return

    selected_name = st.selectbox("Analyze playlist", [playlist["name"] for playlist in playlists])
    selected = next(playlist for playlist in playlists if playlist["name"] == selected_name)
    tracks = client.get_playlist_tracks(selected["id"])

    col1, col2, col3 = st.columns(3)
    with col1:
        metric_card("Tracks", len(tracks), selected_name)
    with col2:
        metric_card("Estimated length", f"{dp.calculate_listening_time(tracks)} min", "Based on track durations")
    with col3:
        metric_card("Unique artists", len({track.get("artist_name") for track in tracks}), "In selected playlist")

    action_a, action_b = st.columns(2)
    with action_a:
        st.download_button(
            "Export selected playlist CSV",
            data=dp.tracks_to_dataframe(tracks).to_csv(index=False),
            file_name=f"{selected_name.lower().replace(' ', '_')}_tracks.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with action_b:
        if st.button("Back up selected playlist", use_container_width=True):
            backup_id = dp.backup_playlist(DB_PATH, selected, tracks)
            st.success(f"Created playlist backup #{backup_id}.")

    st.subheader("Selected playlist tracks")
    render_table(dp.tracks_to_dataframe(tracks), link_columns={"spotify_url"})

    if len(playlists) >= 2:
        with st.expander("Find duplicate tracks across playlists"):
            max_playlists = st.slider("Playlists to scan", 2, min(25, len(playlists)), min(8, len(playlists)))
            if st.button("Scan duplicates", use_container_width=True):
                playlist_tracks = {
                    playlist["name"]: client.get_playlist_tracks(playlist["id"])
                    for playlist in playlists[:max_playlists]
                }
                duplicates = dp.find_duplicate_tracks(playlist_tracks)
                if duplicates.empty:
                    st.success("No duplicates found across the scanned playlists.")
                else:
                    render_table(duplicates)

    with st.expander("Create mood playlist from top tracks"):
        mood = st.selectbox("Mood/activity", list(MOOD_FILTERS.keys()))
        st.caption(MOOD_FILTERS[mood]["description"])
        name = st.text_input("Playlist name", value=f"My {mood} Mix")
        public = st.toggle("Make playlist public", value=False)
        top_tracks = client.get_top_tracks(limit=50)
        features = get_features_for_tracks(client, top_tracks)
        if features.empty:
            st.info("Mood playlist generation needs Spotify audio features access.")
        else:
            candidates = MOOD_FILTERS[mood]["rules"](features).head(30)
            st.write(f"{len(candidates)} tracks match this mood.")
            render_table(candidates[["name", "artist_name", "energy", "valence", "tempo"]])
            if st.button("Create playlist", disabled=client.demo_mode or candidates.empty, use_container_width=True):
                playlist = client.create_playlist(
                    name=name,
                    description=f"Generated from Spotify Analytics using the {mood.lower()} filter.",
                    track_ids=candidates["id"].tolist(),
                    public=public,
                )
                if playlist:
                    st.success(f"Created playlist: {playlist['name']}")


def discovery_page(client: SpotifyClient) -> None:
    page_header("Discovery Tracker", "Track newly discovered artists, deep cuts, and month-over-month listening changes.")
    if st.button("Sync recent plays before discovery analysis"):
        inserted = sync_recently_played(client)
        st.success(f"Saved {inserted} new plays.")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("New artists this month")
        render_table(dp.track_new_discoveries(DB_PATH))
    with col2:
        st.subheader("Deep cuts")
        threshold = st.slider("Popularity threshold", 10, 70, 45)
        render_table(dp.deep_cuts(DB_PATH, popularity_threshold=threshold))

    top_artists = client.get_top_artists(limit=20)
    first_listens = dp.first_listen_for_artists(DB_PATH, [artist["name"] for artist in top_artists])
    st.subheader("When you first listened to current favorites")
    render_table(first_listens)


def settings_page(client: SpotifyClient) -> None:
    page_header("Settings & Exports", "Credentials status, database exports, backups, and monthly report generation.")
    config = load_config()

    st.subheader("Spotify configuration")
    if client.demo_mode:
        st.warning("Running in demo mode. Add `.env` credentials and restart Streamlit to authenticate with Spotify.")
    else:
        st.success("Spotify credentials are configured. Spotipy will handle OAuth token caching.")
    st.code(
        f"""SPOTIPY_CLIENT_ID={"set" if config["client_id"] else "missing"}
SPOTIPY_CLIENT_SECRET={"set" if config["client_secret"] else "missing"}
SPOTIPY_REDIRECT_URI={config["redirect_uri"] or DEFAULT_REDIRECT_URI}""",
        language="text",
    )

    history_df = dp.get_listening_history(DB_PATH)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Export listening history")
        st.download_button(
            "Download listening_history.csv",
            data=history_df.to_csv(index=False),
            file_name="listening_history.csv",
            mime="text/csv",
            disabled=history_df.empty,
            use_container_width=True,
        )
    with col2:
        st.subheader("Monthly HTML report")
        months = sorted(history_df["played_at"].dt.strftime("%Y-%m").unique(), reverse=True) if not history_df.empty else []
        if months:
            month = st.selectbox("Report month", months)
            html = dp.generate_monthly_report_html(DB_PATH, month)
            st.download_button(
                "Download monthly report HTML",
                data=html,
                file_name=f"spotify_report_{month}.html",
                mime="text/html",
                use_container_width=True,
            )
        else:
            st.info("Save listening history before generating a monthly report.")

    st.subheader("Playlist backups")
    backups = dp.get_playlist_backups(DB_PATH)
    render_table(backups, hidden_columns={"track_ids"})


def main() -> None:
    inject_css()
    dp.init_db(DB_PATH)
    client = get_spotify_client()

    st.sidebar.markdown("## Spotify Analytics")
    page = st.sidebar.radio(
        "Navigation",
        [
            "Home",
            "Top Content",
            "Listening History",
            "Audio Features",
            "Playlists",
            "Discovery",
            "Settings",
        ],
    )
    st.sidebar.divider()
    if st.sidebar.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()

    if client.needs_authentication():
        authentication_page(client)
        show_notices(client)
        return

    if page == "Home":
        home_page(client)
    elif page == "Top Content":
        top_content_page(client)
    elif page == "Listening History":
        history_page(client)
    elif page == "Audio Features":
        audio_features_page(client)
    elif page == "Playlists":
        playlists_page(client)
    elif page == "Discovery":
        discovery_page(client)
    elif page == "Settings":
        settings_page(client)

    show_notices(client)


if __name__ == "__main__":
    main()
