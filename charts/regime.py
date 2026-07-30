import plotly.graph_objects as go
from analysis.regime.models import RegimeLayer
from config.theme import BG, TEXT, GRID, ORANGE, MUTED

def create_regime_radar(layer: RegimeLayer) -> go.Figure:
    labels = [pillar.name for pillar in layer.pillars]
    values = [pillar.score for pillar in layer.pillars]
    labels += [labels[0]]
    values += [values[0]]

    fig = go.Figure(
        go.Scatterpolar(
            r=values,
            theta=labels,
            fill="toself",
            line=dict(color=ORANGE, width=2),
            fillcolor="rgba(255,159,0,0.18)",
        )
    )
    fig.update_layout(
        height=430,
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(color=TEXT, family="Consolas, Courier New, monospace"),
        polar=dict(
            bgcolor=BG,
            radialaxis=dict(range=[-2, 2], gridcolor=GRID, tickfont=dict(color=MUTED)),
            angularaxis=dict(gridcolor=GRID),
        ),
        margin=dict(l=30, r=30, t=55, b=30),
        showlegend=False,
        title=f"{layer.title} // PILLAR MAP",
    )
    return fig
