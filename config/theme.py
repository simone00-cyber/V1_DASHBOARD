BG = "#050505"
PANEL = "#0e0e0e"
PANEL_2 = "#151515"
ORANGE = "#ff9f00"
GREEN = "#00d26a"
RED = "#ff3b3b"
TEXT = "#f2f2f2"
MUTED = "#9a9a9a"
GRID = "#2a2a2a"
BLUE = "#4da3ff"
CYAN = "#3ee6e0"
PURPLE = "#b58cff"

# Semantic aliases layered on the palette above. Values are intentionally
# identical to existing constants so every chart/table that already imports
# BG/ORANGE/GREEN/RED/etc. keeps rendering exactly as before.
AI_ACCENT = PURPLE
STATUS_GOOD = GREEN
STATUS_WARNING = ORANGE
STATUS_CRITICAL = RED
STATUS_INFO = BLUE

SURFACE_RAISED = "#131316"
BORDER_SOFT = "rgba(255, 255, 255, 0.08)"
BORDER_STRONG = "rgba(255, 255, 255, 0.16)"
TEXT_DIM = "#7a7a7a"

SANS_STACK = (
    '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", '
    'Roboto, Helvetica, Arial, sans-serif'
)
MONO_STACK = '"JetBrains Mono", Consolas, "Courier New", monospace'

CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {{ font-family: {SANS_STACK}; }}
.stApp {{ background: {BG}; color: {TEXT}; }}
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer {{ display:none !important; visibility:hidden !important; height:0 !important; }}
.block-container {{ padding-top:.25rem !important; padding-bottom:3rem; max-width:100%; }}
h1,h2,h3 {{ color:{TEXT}; font-weight:700; letter-spacing:-0.01em; }}

.top-terminal-bar {{ display:flex; justify-content:space-between; align-items:center; background:{ORANGE}; color:#000; padding:.42rem .70rem; font-weight:900; border-bottom:2px solid #000; margin-bottom:.18rem; }}
.ticker-strip {{ display:flex; gap:1.10rem; flex-wrap:wrap; background:#0a0a0a; border-top:1px solid #292929; border-bottom:1px solid #292929; padding:.42rem .70rem; margin-bottom:.70rem; font-size:.84rem; font-family:{MONO_STACK}; font-variant-numeric: tabular-nums; }}
.terminal-header {{ background:{ORANGE}; color:#000; padding:.55rem .8rem; font-weight:800; font-size:1.05rem; margin-bottom:.7rem; border-radius:4px; }}
.terminal-subheader {{ color:{ORANGE}; border-bottom:1px solid {ORANGE}; padding-bottom:.25rem; margin:.9rem 0 .55rem 0; font-size:.95rem; font-weight:700; }}
.panel {{ border:1px solid {BORDER_SOFT}; background:{PANEL}; padding:.8rem; border-radius:8px; }}
.report-box {{ border:1px solid {BORDER_SOFT}; border-left:4px solid {ORANGE}; padding:1rem 1.1rem; background:{PANEL}; line-height:1.6; color:{TEXT}; border-radius:0 8px 8px 0; }}
.signal-box {{ border:1px solid {BORDER_SOFT}; border-left:5px solid {ORANGE}; padding:.9rem 1rem; background:{PANEL_2}; margin-bottom:.8rem; border-radius:0 8px 8px 0; }}
.small-note {{ color:{MUTED}; font-size:.82rem; }}
.regime-badge {{ padding:.55rem .8rem; font-size:1.35rem; font-weight:900; text-align:center; border:1px solid {BORDER_STRONG}; background:{PANEL}; border-radius:8px; }}

div[data-testid="stMetric"] {{ background:{PANEL}; border:1px solid {BORDER_SOFT}; border-radius:10px; padding:.85rem 1rem; transition: border-color .15s ease; }}
div[data-testid="stMetric"]:hover {{ border-color:{BORDER_STRONG}; }}
div[data-testid="stMetricLabel"] {{ color:{MUTED}; font-size:.78rem; text-transform:uppercase; letter-spacing:.04em; }}
div[data-testid="stMetricValue"] {{ color:{TEXT}; font-family:{MONO_STACK}; font-variant-numeric: tabular-nums; }}

button[kind="primary"] {{ background:{ORANGE} !important; color:#000 !important; border:1px solid {ORANGE} !important; font-weight:700 !important; }}
.stTabs [data-baseweb="tab-list"] {{ gap:2px; background:#080808; }}
.stTabs [data-baseweb="tab"] {{ background:{PANEL}; border:1px solid #292929; color:{TEXT}; border-radius:6px 6px 0 0; }}
.stTabs [aria-selected="true"] {{ background:{ORANGE} !important; color:#000 !important; }}
div[data-testid="stDataFrame"] {{ border:1px solid {BORDER_SOFT}; border-radius:8px; font-family:{MONO_STACK}; }}
hr {{ border-color:#2b2b2b; }} code {{ color:{ORANGE}; font-family:{MONO_STACK}; }}

/* ---- Section headers ---- */
.section-eyebrow {{ color:{ORANGE}; font-size:.72rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; margin-bottom:.35rem; }}
.section-eyebrow.is-ai {{ color:{AI_ACCENT}; }}
.section-title {{ font-size:1.9rem; line-height:1.15; font-weight:800; letter-spacing:-0.03em; color:{TEXT}; }}
.section-subtitle {{ margin-top:.5rem; max-width:820px; font-size:.94rem; line-height:1.55; color:{MUTED}; }}
div[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius:10px; }}

/* ---- Command Center: thin status line above the assistant ---- */
.status-line {{ font-size:.86rem; color:{TEXT}; padding:.5rem 0 .9rem 0; }}
.status-dot {{ display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:.4rem; }}
.status-muted {{ color:{MUTED}; }}
.tick-up {{ color:{STATUS_GOOD}; font-family:{MONO_STACK}; font-variant-numeric: tabular-nums; }}
.tick-down {{ color:{STATUS_CRITICAL}; font-family:{MONO_STACK}; font-variant-numeric: tabular-nums; }}

/* ---- Market Intelligence: the assistant IS the Command Center ---- */
.cio-persona {{ color:{AI_ACCENT}; font-size:.72rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; margin-bottom:.5rem; }}

/* ---- Top navigation (st.navigation position="top") ---- */
header[data-testid="stHeader"] {{ background:{PANEL} !important; border-bottom:1px solid {BORDER_SOFT}; }}

/* ---- Status / severity chips (validation, health) ---- */
.status-chip {{ display:inline-flex; align-items:center; gap:.35rem; padding:.22rem .6rem; border-radius:999px; font-size:.76rem; font-weight:700; border:1px solid transparent; }}
.status-chip.is-good {{ background:rgba(0,210,106,0.12); color:{STATUS_GOOD}; border-color:rgba(0,210,106,0.35); }}
.status-chip.is-warning {{ background:rgba(255,159,0,0.12); color:{STATUS_WARNING}; border-color:rgba(255,159,0,0.35); }}
.status-chip.is-critical {{ background:rgba(255,59,59,0.12); color:{STATUS_CRITICAL}; border-color:rgba(255,59,59,0.35); }}
.status-chip.is-info {{ background:rgba(77,163,255,0.12); color:{STATUS_INFO}; border-color:rgba(77,163,255,0.35); }}
.status-chip.is-neutral {{ background:rgba(255,255,255,0.06); color:{MUTED}; border-color:{BORDER_SOFT}; }}

.badge {{ display:inline-block; padding:.18rem .55rem; border-radius:6px; font-size:.72rem; font-weight:700; letter-spacing:.03em; text-transform:uppercase; background:{PANEL_2}; color:{MUTED}; border:1px solid {BORDER_SOFT}; }}
.badge.is-long {{ color:{STATUS_GOOD}; border-color:rgba(0,210,106,0.35); }}
.badge.is-short {{ color:{STATUS_CRITICAL}; border-color:rgba(255,59,59,0.35); }}

/* ---- Workflow stepper (AI Strategy Lab progress) ---- */
.workflow-stepper {{ display:flex; align-items:center; flex-wrap:wrap; gap:.15rem; margin:.4rem 0 1.1rem 0; }}
.workflow-step {{ display:flex; align-items:center; gap:.4rem; padding:.35rem .7rem; border-radius:999px; font-size:.76rem; font-weight:600; color:{TEXT_DIM}; background:{PANEL}; border:1px solid {BORDER_SOFT}; }}
.workflow-step .dot {{ width:7px; height:7px; border-radius:50%; background:{TEXT_DIM}; }}
.workflow-step.is-done {{ color:{TEXT}; border-color:rgba(0,210,106,0.3); }}
.workflow-step.is-done .dot {{ background:{STATUS_GOOD}; }}
.workflow-step.is-active {{ color:#000; background:{AI_ACCENT}; border-color:{AI_ACCENT}; font-weight:700; }}
.workflow-step.is-active .dot {{ background:#000; }}
.workflow-step.is-locked {{ opacity:.45; }}
.workflow-arrow {{ color:{BORDER_STRONG}; font-size:.8rem; }}

/* ---- Research workspace (Technical + Cyclical synthesis) ---- */
.insight-banner {{ font-size:1.05rem; line-height:1.6; color:{TEXT}; background:{PANEL}; border:1px solid {BORDER_SOFT}; border-left:4px solid {ORANGE}; padding:.9rem 1.1rem; border-radius:0 8px 8px 0; margin-bottom:.7rem; }}
.evidence-list {{ list-style:none; margin:.4rem 0 .8rem 0; padding:0; }}
.evidence-list li {{ font-size:.86rem; line-height:1.55; color:{TEXT}; padding:.28rem 0 .28rem 1.1rem; border-left:2px solid {BORDER_SOFT}; margin-bottom:.15rem; }}
.risk-callout {{ border:1px solid {BORDER_SOFT}; border-left:4px solid {ORANGE}; background:{PANEL_2}; padding:.7rem .9rem; border-radius:0 8px 8px 0; font-size:.88rem; line-height:1.5; color:{TEXT}; margin-bottom:.5rem; }}
.invalidation-callout {{ border:1px solid {BORDER_SOFT}; border-left:4px solid {RED}; background:{PANEL_2}; padding:.7rem .9rem; border-radius:0 8px 8px 0; font-size:.88rem; line-height:1.5; color:{TEXT}; margin-bottom:.5rem; }}
.confidence-row {{ display:flex; align-items:center; gap:.6rem; margin:.3rem 0 .7rem 0; }}
.confidence-track {{ flex:1; height:8px; border-radius:999px; background:{PANEL_2}; border:1px solid {BORDER_SOFT}; overflow:hidden; }}
.confidence-fill {{ height:100%; border-radius:999px; }}
.confidence-label {{ font-family:{MONO_STACK}; font-size:.8rem; color:{MUTED}; min-width:3.2rem; text-align:right; }}
.pattern-card {{ border:1px solid {BORDER_SOFT}; border-radius:8px; padding:.75rem .9rem; margin-bottom:.6rem; background:{PANEL}; }}
.pattern-card-title {{ font-weight:700; font-size:.95rem; color:{TEXT}; display:flex; justify-content:space-between; align-items:center; }}
.pattern-card-meta {{ color:{MUTED}; font-size:.78rem; margin:.15rem 0 .5rem 0; }}
.timeframe-row {{ display:flex; gap:.5rem; flex-wrap:wrap; margin:.4rem 0 .8rem 0; }}
.timeframe-chip {{ border:1px solid {BORDER_SOFT}; border-radius:8px; padding:.4rem .7rem; font-size:.82rem; font-family:{MONO_STACK}; background:{PANEL_2}; }}

/* ---- Opportunities workspace ---- */
.opportunity-insight {{ font-size:1.05rem; line-height:1.6; color:{TEXT}; background:{PANEL}; border:1px solid {BORDER_SOFT}; border-left:4px solid {ORANGE}; padding:.9rem 1.1rem; border-radius:0 8px 8px 0; margin-bottom:.9rem; }}
.opp-card-ticker {{ font-family:{MONO_STACK}; font-size:1.15rem; font-weight:800; color:{TEXT}; display:flex; justify-content:space-between; align-items:center; }}
.opp-card-rating {{ color:{ORANGE}; font-size:.95rem; letter-spacing:.06em; }}
.opp-card-company {{ color:{MUTED}; font-size:.82rem; margin-bottom:.4rem; }}
.opp-card-metrics {{ display:flex; gap:.5rem; margin:.6rem 0; }}
.opp-card-metric {{ flex:1; min-width:0; background:{PANEL_2}; border:1px solid {BORDER_SOFT}; border-radius:8px; padding:.45rem .55rem; }}
.opp-card-metric-label {{ display:block; color:{MUTED}; font-size:.66rem; font-weight:600; text-transform:uppercase; letter-spacing:.03em; margin-bottom:.2rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.opp-card-metric-value {{ display:block; font-family:{MONO_STACK}; font-size:1.02rem; font-weight:700; color:{TEXT}; font-variant-numeric: tabular-nums; white-space:nowrap; }}
.opp-card-regime {{ font-family:{MONO_STACK}; font-size:.78rem; color:{BLUE}; margin:.5rem 0; letter-spacing:.02em; }}
.opp-card-reason {{ font-size:.85rem; line-height:1.45; color:{TEXT}; margin-bottom:.4rem; }}
.opp-card-risk {{ font-size:.85rem; line-height:1.45; color:{MUTED}; margin-bottom:.6rem; }}
.side-panel-header {{ font-size:.82rem; font-weight:800; letter-spacing:.07em; text-transform:uppercase; padding-bottom:.4rem; margin-bottom:.5rem; border-bottom:2px solid currentColor; }}
.sector-group-row {{ display:flex; gap:.5rem; margin:.4rem 0 .9rem 0; flex-wrap:wrap; }}
.funnel-tier-caption {{ color:{MUTED}; font-size:.82rem; margin-bottom:.5rem; }}

/* ---- Research Workspace: hero header, executive summary, star ratings, dot rows ---- */
.hero-regime {{ display:inline-block; padding:.3rem .7rem; border-radius:6px; font-weight:800; font-size:.85rem; letter-spacing:.03em; }}
.exec-summary {{ border:1px solid {ORANGE}; background:{PANEL}; border-radius:10px; padding:1rem 1.2rem; margin:.6rem 0 1.1rem 0; }}
.exec-summary-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:.9rem 1.4rem; margin-top:.5rem; }}
.exec-summary-item .label {{ display:block; color:{MUTED}; font-size:.72rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase; margin-bottom:.2rem; }}
.exec-summary-item .value {{ display:block; font-family:{MONO_STACK}; font-size:1.05rem; font-weight:700; color:{TEXT}; line-height:1.3; }}
.stars {{ font-size:1.1rem; letter-spacing:.1em; color:{ORANGE}; font-family:{MONO_STACK}; }}
.stars.is-muted {{ color:{BORDER_STRONG}; }}
.star-row {{ display:flex; justify-content:space-between; align-items:center; padding:.3rem 0; border-bottom:1px solid {BORDER_SOFT}; }}
.star-row:last-child {{ border-bottom:none; }}
.star-row .star-label {{ font-size:.82rem; color:{MUTED}; font-weight:600; text-transform:uppercase; letter-spacing:.04em; }}
.dot-row {{ display:flex; align-items:center; gap:.55rem; padding:.32rem 0; border-bottom:1px solid {BORDER_SOFT}; font-size:.86rem; }}
.dot-row:last-child {{ border-bottom:none; }}
.dot-row .dot-timeframe {{ font-weight:700; min-width:80px; color:{TEXT}; }}
.dot-row .dot-detail {{ color:{MUTED}; font-family:{MONO_STACK}; font-size:.8rem; }}

/* Fixed loading experience used during page and Asset Workspace transitions. */
.terminal-loading-overlay {{
    position: fixed;
    inset: 0;
    z-index: 999999;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.985);
    backdrop-filter: blur(5px);
}}
.terminal-loading-panel {{
    width: min(680px, 82vw);
    padding: 34px 38px;
    border: 1px solid {ORANGE};
    background: #090909;
    box-shadow: 0 0 50px rgba(255, 159, 0, 0.12);
    font-family: {MONO_STACK};
}}
.terminal-loading-kicker {{
    color: {ORANGE};
    font-weight: 800;
    letter-spacing: 0.08em;
    margin-bottom: 22px;
}}
.terminal-loading-title {{
    color: #f4f4f4;
    font-size: 1.35rem;
    font-weight: 800;
    margin-bottom: 9px;
    font-family: {SANS_STACK};
}}
.terminal-loading-detail {{
    color: #8c8c8c;
    font-size: 0.92rem;
    margin-bottom: 24px;
}}
.terminal-loading-track {{
    height: 8px;
    overflow: hidden;
    background: #1d1d1d;
    border: 1px solid #303030;
}}
.terminal-loading-bar {{
    height: 100%;
    width: 42%;
    background: {ORANGE};
    animation: terminal-loading-slide 1.05s ease-in-out infinite;
}}
@keyframes terminal-loading-slide {{
    0% {{ transform: translateX(-110%); }}
    100% {{ transform: translateX(255%); }}
}}

/* ---- Executive Research Summary (institutional redesign) ---- */
.conviction-badge {{ display:inline-flex; align-items:center; padding:.5rem 1rem; border-radius:10px; font-size:1.15rem; font-weight:800; letter-spacing:-0.01em; border:1px solid transparent; }}
.conviction-badge.is-good {{ background:rgba(0,210,106,0.14); color:{GREEN}; border-color:rgba(0,210,106,0.4); }}
.conviction-badge.is-warning {{ background:rgba(255,159,0,0.14); color:{ORANGE}; border-color:rgba(255,159,0,0.4); }}
.conviction-badge.is-critical {{ background:rgba(255,59,59,0.14); color:{RED}; border-color:rgba(255,59,59,0.4); }}
.conviction-badge.is-neutral {{ background:rgba(255,255,255,0.07); color:{MUTED}; border-color:{BORDER_SOFT}; }}
.lens-chip-row {{ display:flex; gap:.45rem; flex-wrap:wrap; margin:.5rem 0 .8rem 0; }}
.summary-line {{ display:flex; gap:.5rem; font-size:.86rem; line-height:1.5; padding:.2rem 0; }}
.summary-line .summary-label {{ color:{MUTED}; font-weight:700; text-transform:uppercase; letter-spacing:.04em; font-size:.72rem; min-width:110px; padding-top:.15rem; }}
.summary-line .summary-value {{ color:{TEXT}; flex:1; }}
.thesis-headline {{ font-size:1rem; line-height:1.55; color:{TEXT}; margin:.6rem 0 .9rem 0; padding:.15rem 0; }}

/* ---- Valuation range visual ---- */
.valuation-range {{ margin:.9rem 0 .5rem 0; }}
.valuation-range-labels {{ display:flex; justify-content:space-between; font-size:.72rem; color:{MUTED}; font-weight:700; text-transform:uppercase; letter-spacing:.03em; margin-bottom:.3rem; }}
.valuation-range-track {{ position:relative; height:10px; border-radius:999px; background:linear-gradient(90deg, rgba(255,59,59,0.35), rgba(255,159,0,0.35), rgba(0,210,106,0.35)); border:1px solid {BORDER_SOFT}; }}
.valuation-range-marker {{ position:absolute; top:-7px; width:2px; height:24px; background:{TEXT}; }}
.valuation-range-marker .marker-tag {{ position:absolute; top:-20px; left:50%; transform:translateX(-50%); font-size:.68rem; font-weight:700; white-space:nowrap; color:{TEXT}; }}
.valuation-range-marker.is-price {{ background:{ORANGE}; width:3px; height:28px; top:-9px; }}
.valuation-range-marker.is-price .marker-tag {{ color:{ORANGE}; top:-22px; }}
.valuation-range-values {{ display:flex; justify-content:space-between; font-family:{MONO_STACK}; font-size:.82rem; color:{TEXT}; margin-top:1.6rem; }}

.ai-lab-header {{
    padding: 0.25rem 0 0.8rem 0;
}}

.ai-lab-kicker {{
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    opacity: 0.65;
    margin-bottom: 0.35rem;
    color: {AI_ACCENT};
}}

.ai-lab-title {{
    font-size: 2rem;
    line-height: 1.1;
    font-weight: 800;
    letter-spacing: -0.035em;
}}

.ai-lab-subtitle {{
    margin-top: 0.55rem;
    max-width: 780px;
    font-size: 0.94rem;
    line-height: 1.5;
    opacity: 0.72;
}}

[data-testid="stChatMessage"] {{
    border: 1px solid {BORDER_SOFT};
    border-radius: 12px;
    padding: 0.35rem 0.6rem;
    margin-bottom: 0.65rem;
}}

[data-testid="stChatInput"] {{
    border-radius: 10px;
}}

/* Hide Streamlit header */
header[data-testid="stHeader"] {{
    display: none;
}}

/* Hide toolbar (top-right menu) */
[data-testid="stToolbar"] {{
    display: none;
}}

/* Hide top decoration */
[data-testid="stDecoration"] {{
    display: none;
}}

/* Reduce top padding */
.block-container {{
    padding-top: 1rem !important;
}}
</style>
"""

# Design System v2.0 (workflow-oriented redesign) is layered on top of v1.0
# via new semantic classes (section-eyebrow/title/subtitle, cta-card-*,
# status-chip, badge, workflow-step, nav-*). Existing views deliberately keep
# reusing terminal-header, terminal-subheader, report-box, regime-badge and
# native metric cards so this file is the single place visual changes fan out
# from.
