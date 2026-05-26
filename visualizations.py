from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


SPOTIFY_GREEN = "#1DB954"
DARK_TEXT = "#17251d"
MUTED_TEXT = "#637066"


def empty_figure(message: str = "No data yet") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        showarrow=False,
        font={"size": 18, "color": MUTED_TEXT},
    )
    fig.update_layout(
        height=320,
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    return fig


def plot_top_tracks_chart(tracks: list[dict[str, Any]]) -> go.Figure:
    if not tracks:
        return empty_figure("Fetch top tracks to populate this chart")
    df = pd.DataFrame(tracks[:15]).copy()
    df["label"] = df["name"] + " - " + df["artist_name"]
    df["score"] = list(range(len(df), 0, -1))
    fig = px.bar(
        df.sort_values("score"),
        x="score",
        y="label",
        orientation="h",
        labels={"score": "Relative rank", "label": ""},
        color_discrete_sequence=[SPOTIFY_GREEN],
    )
    fig.update_layout(
        height=max(360, len(df) * 30),
        showlegend=False,
        margin={"l": 10, "r": 20, "t": 20, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": DARK_TEXT},
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(tickfont={"size": 12})
    return fig


def plot_top_artists_chart(artists: list[dict[str, Any]]) -> go.Figure:
    if not artists:
        return empty_figure("Fetch top artists to populate this chart")
    df = pd.DataFrame(artists[:15]).copy()
    df["score"] = list(range(len(df), 0, -1))
    fig = px.bar(
        df.sort_values("score"),
        x="score",
        y="name",
        orientation="h",
        labels={"score": "Relative rank", "name": ""},
        color_discrete_sequence=["#15803d"],
    )
    fig.update_layout(
        height=max(360, len(df) * 30),
        showlegend=False,
        margin={"l": 10, "r": 20, "t": 20, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": DARK_TEXT},
    )
    fig.update_xaxes(visible=False)
    return fig


def plot_listening_timeline(history_df: pd.DataFrame) -> go.Figure:
    if history_df.empty:
        return empty_figure("Save recently played tracks to start the timeline")
    fig = px.line(
        history_df,
        x="period",
        y="minutes",
        markers=True,
        labels={"period": "Date", "minutes": "Minutes listened"},
    )
    fig.update_traces(line={"color": SPOTIFY_GREEN, "width": 3}, marker={"size": 6})
    fig.update_layout(
        height=360,
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": DARK_TEXT},
    )
    return fig


def plot_audio_features_radar(features: pd.DataFrame | list[dict[str, Any]]) -> go.Figure:
    df = pd.DataFrame(features)
    columns = [
        "danceability",
        "energy",
        "valence",
        "acousticness",
        "instrumentalness",
        "speechiness",
        "liveness",
    ]
    columns = [column for column in columns if column in df.columns]
    if df.empty or not columns:
        return empty_figure("Audio features are unavailable for this selection")
    averages = df[columns].astype(float).mean().fillna(0)
    fig = go.Figure(
        data=[
            go.Scatterpolar(
                r=averages.tolist() + [averages.iloc[0]],
                theta=columns + [columns[0]],
                fill="toself",
                line={"color": SPOTIFY_GREEN, "width": 3},
                fillcolor="rgba(29,185,84,0.22)",
            )
        ]
    )
    fig.update_layout(
        height=390,
        polar={"radialaxis": {"visible": True, "range": [0, 1]}},
        showlegend=False,
        margin={"l": 30, "r": 30, "t": 30, "b": 30},
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": DARK_TEXT},
    )
    return fig


def plot_genre_pie_chart(genre_data: dict[str, float]) -> go.Figure:
    if not genre_data:
        return empty_figure("Top artists with genres will populate this chart")
    df = pd.DataFrame({"genre": genre_data.keys(), "share": genre_data.values()})
    fig = px.pie(
        df.head(10),
        names="genre",
        values="share",
        hole=0.52,
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(
        height=360,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": DARK_TEXT},
    )
    return fig


def plot_listening_heatmap(heatmap_data: pd.DataFrame) -> go.Figure:
    if heatmap_data.empty:
        return empty_figure("No listening activity saved yet")
    fig = go.Figure(
        data=go.Heatmap(
            z=heatmap_data.values,
            x=[str(hour).zfill(2) for hour in heatmap_data.columns],
            y=heatmap_data.index,
            colorscale=[[0, "#f3f7f2"], [0.35, "#93d9a8"], [1, "#0f7a3b"]],
            hovertemplate="Day: %{y}<br>Hour: %{x}:00<br>Plays: %{z}<extra></extra>",
        )
    )
    fig.update_layout(
        height=420,
        xaxis_title="Hour of day",
        yaxis_title="Day of week",
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": DARK_TEXT},
    )
    return fig


def plot_energy_valence_scatter(tracks_with_features: pd.DataFrame | list[dict[str, Any]]) -> go.Figure:
    df = pd.DataFrame(tracks_with_features)
    if df.empty or not {"energy", "valence"}.issubset(df.columns):
        return empty_figure("Audio feature data is needed for mood mapping")
    hover = "name" if "name" in df.columns else None
    fig = px.scatter(
        df,
        x="energy",
        y="valence",
        hover_name=hover,
        hover_data=[column for column in ["artist_name", "tempo", "danceability"] if column in df.columns],
        color="danceability" if "danceability" in df.columns else None,
        color_continuous_scale="Greens",
        labels={"energy": "Energy", "valence": "Valence / mood"},
    )
    fig.add_hline(y=0.5, line_dash="dot", line_color="#aab4ac")
    fig.add_vline(x=0.5, line_dash="dot", line_color="#aab4ac")
    fig.add_annotation(x=0.25, y=0.78, text="Calm positive", showarrow=False, font={"color": MUTED_TEXT})
    fig.add_annotation(x=0.78, y=0.78, text="High energy positive", showarrow=False, font={"color": MUTED_TEXT})
    fig.add_annotation(x=0.25, y=0.22, text="Low energy moody", showarrow=False, font={"color": MUTED_TEXT})
    fig.add_annotation(x=0.78, y=0.22, text="Intense moody", showarrow=False, font={"color": MUTED_TEXT})
    fig.update_layout(
        height=430,
        xaxis={"range": [0, 1]},
        yaxis={"range": [0, 1]},
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": DARK_TEXT},
    )
    return fig


def plot_bpm_distribution(features: pd.DataFrame | list[dict[str, Any]]) -> go.Figure:
    df = pd.DataFrame(features)
    if df.empty or "tempo" not in df.columns:
        return empty_figure("Tempo data is unavailable")
    fig = px.histogram(
        df,
        x="tempo",
        nbins=20,
        labels={"tempo": "Tempo (BPM)", "count": "Tracks"},
        color_discrete_sequence=[SPOTIFY_GREEN],
    )
    fig.update_layout(
        height=320,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": DARK_TEXT},
    )
    return fig


def plot_monthly_artists(monthly_df: pd.DataFrame) -> go.Figure:
    if monthly_df.empty:
        return empty_figure("Monthly top artists will appear after history is saved")
    fig = go.Figure()
    for artist_name, artist_df in monthly_df.groupby("artist_name", sort=False):
        fig.add_trace(
            go.Bar(
                x=artist_df["month"],
                y=artist_df["plays"],
                name=str(artist_name),
                hovertemplate="Month: %{x}<br>Plays: %{y}<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="stack",
        height=400,
        xaxis_title="Month",
        yaxis_title="Plays",
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": DARK_TEXT},
    )
    return fig


def plot_month_over_month(month_df: pd.DataFrame) -> go.Figure:
    if month_df.empty:
        return empty_figure("Month-over-month stats need saved listening history")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=month_df["month"], y=month_df["minutes"], name="Minutes", marker_color=SPOTIFY_GREEN))
    fig.add_trace(
        go.Scatter(
            x=month_df["month"],
            y=month_df["unique_artists"],
            name="Unique artists",
            yaxis="y2",
            mode="lines+markers",
            line={"color": "#0f172a", "width": 3},
        )
    )
    fig.update_layout(
        height=360,
        yaxis={"title": "Minutes"},
        yaxis2={"title": "Unique artists", "overlaying": "y", "side": "right"},
        legend={"orientation": "h"},
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": DARK_TEXT},
    )
    return fig
