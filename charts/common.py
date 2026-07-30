import numpy as np
import pandas as pd
import plotly.graph_objects as go
from config.theme import BG, TEXT, GRID, GREEN, RED, ORANGE, BLUE

def apply_terminal_layout(fig: go.Figure, height: int = 480) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(color=TEXT, family="Consolas, Courier New, monospace"),
        margin=dict(l=25, r=25, t=55, b=25),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
        ),
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor="#444")
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor="#444")
    return fig

def create_line_chart(
    frame: pd.DataFrame,
    title: str,
    y_title: str = "",
    height: int = 480,
) -> go.Figure:
    fig = go.Figure()
    for column in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[column],
                mode="lines",
                name=str(column),
                line=dict(width=1.8),
            )
        )
    fig.update_layout(title=title, yaxis_title=y_title)
    return apply_terminal_layout(fig, height)

def create_bar_chart(table: pd.DataFrame, value_column: str, title: str) -> go.Figure:
    data = table.dropna(subset=[value_column]).sort_values(value_column)
    colors = [GREEN if value >= 0 else RED for value in data[value_column]]

    fig = go.Figure(
        go.Bar(
            x=data[value_column],
            y=data["Strumento"],
            orientation="h",
            marker_color=colors,
            text=[f"{value:+.2f}%" for value in data[value_column]],
            textposition="outside",
        )
    )
    fig.update_layout(title=title, xaxis_title=value_column)
    return apply_terminal_layout(fig, 500)

def create_yield_curve_chart(rates: pd.DataFrame) -> go.Figure:
    order = ["US 13W", "US 2Y", "US 5Y", "US 10Y", "US 30Y"]
    available = [label for label in order if label in rates.columns and not rates[label].dropna().empty]

    current = [float(rates[label].dropna().iloc[-1]) for label in available]

    previous = []
    for label in available:
        series = rates[label].dropna()
        previous.append(float(series.iloc[-6]) if len(series) >= 6 else np.nan)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=available,
            y=current,
            mode="lines+markers",
            name="Current",
            line=dict(color=ORANGE, width=3),
            marker=dict(size=9),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=available,
            y=previous,
            mode="lines+markers",
            name="5 sessions ago",
            line=dict(color=BLUE, width=1.8, dash="dash"),
        )
    )
    fig.update_layout(title="US TREASURY YIELD CURVE", yaxis_title="Yield %")
    return apply_terminal_layout(fig, 440)
