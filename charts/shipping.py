from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config.theme import BG, ORANGE, CYAN, BLUE, PURPLE, GREEN, RED, MUTED
from charts.common import apply_terminal_layout
from shipping.chokepoints import Chokepoint


CATEGORY_COLORS = {
    "Tanker": ORANGE,
    "Gas carrier": CYAN,
    "Cargo": BLUE,
    "Passenger": PURPLE,
    "Fishing": GREEN,
    "Tug / tow": "#d0d0d0",
    "Service vessel": "#f4d35e",
    "Other": MUTED,
}


def create_live_vessel_map(frame: pd.DataFrame, chokepoint: Chokepoint) -> go.Figure:
    if frame.empty:
        fig = go.Figure()
        fig.update_layout(
            mapbox={"style": "carto-darkmatter", "center": {"lat": chokepoint.center_lat, "lon": chokepoint.center_lon}, "zoom": chokepoint.zoom},
            height=610,
            paper_bgcolor=BG,
            plot_bgcolor=BG,
            margin=dict(l=0, r=0, t=0, b=0),
            annotations=[dict(text="Waiting for live AIS messages...", x=0.5, y=0.5, showarrow=False, font=dict(color="#f2f2f2", size=16))],
        )
        return fig

    hover_data = {
        "mmsi": True,
        "category": True,
        "speed_knots": ":.1f",
        "course": ":.0f",
        "destination": True,
        "flow": True,
        "age_minutes": ":.1f",
        "latitude": False,
        "longitude": False,
    }
    fig = px.scatter_mapbox(
        frame,
        lat="latitude",
        lon="longitude",
        color="category",
        hover_name="display_name",
        hover_data=hover_data,
        color_discrete_map=CATEGORY_COLORS,
        category_orders={"category": list(CATEGORY_COLORS)},
        zoom=chokepoint.zoom,
        center={"lat": chokepoint.center_lat, "lon": chokepoint.center_lon},
        height=610,
    )
    fig.update_traces(marker={"size": 10, "opacity": 0.85})
    fig.update_layout(
        mapbox_style="carto-darkmatter",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(bgcolor="rgba(5,5,5,0.78)", font=dict(color="#f2f2f2")),
    )
    return fig


def create_traffic_history(history: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if not history.empty:
        fig.add_trace(go.Scatter(x=history["timestamp"], y=history["active_vessels"], name="Active vessels", line=dict(color=ORANGE, width=2)))
        fig.add_trace(go.Scatter(x=history["timestamp"], y=history["tankers"], name="Tankers / gas", line=dict(color=CYAN, width=2)))
    fig.update_layout(title="LIVE SESSION TRAFFIC", yaxis_title="Vessels")
    return apply_terminal_layout(fig, 330)
