"""
Storm Assistant - Live Outage Management Dashboard
Hackathon demo dashboard for the AEP Storm Assistant project.

Run from C:/Users/mvsla/Downloads/AEP/:
    streamlit run AEP_Project/storm-assistant/apps/web/dashboard.py
"""
import sys
import time
import math
from pathlib import Path
from datetime import datetime, timedelta

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

# ── Path setup ───────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Storm Assistant",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
/* ── Base ────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Header bar ─────────────────────────────────────── */
.dash-header {
    background: linear-gradient(135deg, #003087 0%, #001a4d 100%);
    border-bottom: 3px solid #FFB81C;
    padding: 18px 28px 14px 28px;
    border-radius: 12px;
    margin-bottom: 16px;
    box-shadow: 0 4px 20px rgba(0,48,135,0.4);
}
.dash-header h1 {
    color: #FFB81C;
    font-size: 2rem;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.5px;
}
.dash-header p {
    color: #a8c4f0;
    font-size: 0.92rem;
    margin: 4px 0 0 0;
}

/* ── Metric cards ───────────────────────────────────── */
.metric-card {
    background: #0a1929;
    border: 1px solid #1e3a5f;
    border-radius: 10px;
    padding: 18px 20px;
    text-align: center;
    box-shadow: 0 2px 12px rgba(0,0,0,0.3);
    min-height: 110px;
}
.metric-card .label {
    color: #7aadda;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 6px;
}
.metric-card .value {
    color: #f0f4ff;
    font-size: 2.2rem;
    font-weight: 800;
    line-height: 1.1;
}
.metric-card .delta {
    font-size: 0.78rem;
    font-weight: 600;
    margin-top: 4px;
    padding: 2px 8px;
    border-radius: 20px;
    display: inline-block;
}
.delta-red   { background: rgba(220,53,69,0.15); color: #ff6b7a; }
.delta-green { background: rgba(40,167,69,0.15); color: #5dde7b; }
.delta-gold  { background: rgba(255,184,28,0.15); color: #FFB81C; }
.delta-blue  { background: rgba(23,162,184,0.15); color: #4dd4e4; }

/* ── Section headers ────────────────────────────────── */
.section-title {
    color: #FFB81C;
    font-size: 1rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 16px 0 10px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid #1e3a5f;
}

/* ── SMS bubble ─────────────────────────────────────── */
.sms-feed-container {
    max-height: 420px;
    overflow-y: auto;
    padding-right: 4px;
    scrollbar-width: thin;
    scrollbar-color: #1e3a5f transparent;
}
.sms-bubble {
    background: #0e2240;
    border: 1px solid #1e3a5f;
    border-left: 4px solid #FFB81C;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 10px;
    font-size: 0.84rem;
}
.sms-bubble.blocked {
    border-left-color: #555;
    opacity: 0.65;
}
.sms-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
}
.sms-name { color: #f0f4ff; font-weight: 700; font-size: 0.85rem; }
.sms-time { color: #6b8db3; font-size: 0.72rem; }
.sms-body { color: #c8daf0; font-size: 0.82rem; line-height: 1.45; margin-top: 4px; }
.sms-footer {
    margin-top: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.badge {
    font-size: 0.68rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.badge-pre_storm    { background:#1a3a5c; color:#7fc8f8; }
.badge-outage_confirmed { background:#3a0a0a; color:#ff8080; }
.badge-crew_assigned{ background:#2a1a00; color:#ffcc55; }
.badge-etr_update   { background:#0a2a1a; color:#55ddaa; }
.badge-restored     { background:#0a1f2a; color:#4dd4e4; }
.sent-tag   { color:#5dde7b; font-size:0.75rem; font-weight:600; }
.blocked-tag{ color:#888; font-size:0.75rem; font-weight:600; }

/* ── Grid tree ──────────────────────────────────────── */
.grid-tree {
    background: #0a1929;
    border: 1px solid #1e3a5f;
    border-radius: 10px;
    padding: 16px;
    font-family: 'Courier New', monospace;
    font-size: 0.82rem;
    color: #c8daf0;
    max-height: 420px;
    overflow-y: auto;
}
.grid-tree .sub  { color: #FFB81C; font-weight: 700; }
.grid-tree .fdr  { color: #7aadda; }
.grid-tree .tr-ok   { color: #5dde7b; }
.grid-tree .tr-fail { color: #ff6b7a; }
.grid-tree .tr-crew { color: #ffcc55; }
.grid-tree .c-ok     { color: #5dde7b; }
.grid-tree .c-risk   { color: #ffcc55; }
.grid-tree .c-out    { color: #ff6b7a; }
.grid-tree .c-rest   { color: #4dd4e4; }

/* ── Customer cards ─────────────────────────────────── */
.cust-card {
    background: #0a1929;
    border: 1px solid #1e3a5f;
    border-radius: 10px;
    padding: 16px;
    height: 100%;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}
.cust-name { color: #f0f4ff; font-weight: 700; font-size: 1rem; }
.cust-id   { color: #5a7a9a; font-size: 0.72rem; font-family: monospace; }
.status-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 700;
    margin: 6px 0;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.pill-normal   { background:#142814; color:#5dde7b; border:1px solid #28553a; }
.pill-at_risk  { background:#2a1e00; color:#ffcc55; border:1px solid #665500; }
.pill-outage_confirmed { background:#2a0a0a; color:#ff6b7a; border:1px solid #661a1a; }
.pill-restored { background:#0a1e2a; color:#4dd4e4; border:1px solid #0a4a5a; }
.etr-text { color:#7aadda; font-size:0.75rem; margin-top:4px; }
.sms-preview { color:#8ab0d0; font-size:0.73rem; margin-top:6px; font-style:italic; border-top:1px solid #1e3a5f; padding-top:6px; }

/* ── Timeline controls ──────────────────────────────── */
.ctrl-row { display:flex; gap:8px; align-items:center; }
.stSlider > div { padding-top:0 !important; }
div[data-testid="stHorizontalBlock"] { gap: 12px !important; }

/* ── Table ──────────────────────────────────────────── */
.stDataFrame { border-radius: 8px; overflow: hidden; }

/* scrollbar global */
::-webkit-scrollbar { width:6px; height:6px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:#1e3a5f; border-radius:4px; }
</style>
""",
    unsafe_allow_html=True,
)

# ── Static grid data ──────────────────────────────────────────────────────────
SUBSTATION = {"id": "SUB-01", "name": "Maple Ridge Substation", "lat": 39.7584, "lon": -84.1916}
FEEDERS = [
    {"id": "FDR-01", "substation_id": "SUB-01"},
    {"id": "FDR-02", "substation_id": "SUB-01"},
]
TRANSFORMERS = [
    {"id": "TR-101", "feeder_id": "FDR-01", "lat": 39.7621, "lon": -84.1848},
    {"id": "TR-102", "feeder_id": "FDR-01", "lat": 39.7640, "lon": -84.1809},
    {"id": "TR-201", "feeder_id": "FDR-02", "lat": 39.7615, "lon": -84.1772},
]
CUSTOMERS = [
    {"id": "CUST-001", "name": "Avery",  "transformer_id": "TR-101", "medical": True,  "consent": True,  "lat": 39.7623, "lon": -84.1845},
    {"id": "CUST-002", "name": "Jordan", "transformer_id": "TR-101", "medical": False, "consent": True,  "lat": 39.7626, "lon": -84.1841},
    {"id": "CUST-003", "name": "Casey",  "transformer_id": "TR-102", "medical": False, "consent": False, "lat": 39.7642, "lon": -84.1811},
    {"id": "CUST-004", "name": "Riley",  "transformer_id": "TR-201", "medical": False, "consent": True,  "lat": 39.7618, "lon": -84.1770},
]

STATUS_COLORS = {
    "normal":            "#28a745",
    "at_risk":           "#ffc107",
    "outage_confirmed":  "#dc3545",
    "restored":          "#17a2b8",
}

ALERT_COLORS = {
    "pre_storm":         "#7fc8f8",
    "outage_confirmed":  "#ff8080",
    "crew_assigned":     "#ffcc55",
    "etr_update":        "#55ddaa",
    "restored":          "#4dd4e4",
}

# ── Simulation (cached) ───────────────────────────────────────────────────────
@st.cache_resource(show_spinner="⚡ Running storm simulation…")
def get_simulation():
    try:
        import messaging
        messaging.reset_for_test()
        from tests.storm_replay.integration import load_runtime
        from tests.storm_replay.replay import run_replay
        runtime = load_runtime("integrated")
        result = run_replay(runtime, crews_available=1, log=lambda x: None)
        return result, None
    except Exception as exc:
        return None, str(exc)

result, sim_error = get_simulation()

# ── Timeline index ────────────────────────────────────────────────────────────
def build_timeline(result):
    times = set()
    if result:
        for alert in result.alerts:
            t = alert.sim_time
            if isinstance(t, str):
                t = datetime.fromisoformat(t)
            times.add(t)
        for event in result.applied_events:
            t = event.get("time")
            if isinstance(t, str):
                t = datetime.fromisoformat(t)
            if t:
                times.add(t)
    times = sorted(times)
    return times

timeline = build_timeline(result) if result else []

# ── Session state ─────────────────────────────────────────────────────────────
if "step_idx" not in st.session_state:
    st.session_state.step_idx = len(timeline) - 1 if timeline else 0
if "playing" not in st.session_state:
    st.session_state.playing = False

# ── Helpers ───────────────────────────────────────────────────────────────────
def fmt_time(t) -> str:
    if t is None:
        return "—"
    if isinstance(t, str):
        try:
            t = datetime.fromisoformat(t)
        except Exception:
            return t
    return t.strftime("%H:%M")

def fmt_dt(t) -> str:
    if t is None:
        return "—"
    if isinstance(t, str):
        try:
            t = datetime.fromisoformat(t)
        except Exception:
            return t
    return t.strftime("%b %d %H:%M")


def storm_position_at(t: datetime):
    """Compute storm lat/lon at time t using the storm.json parameters."""
    start_time = datetime.fromisoformat("2026-10-24T16:00:00-04:00").replace(tzinfo=None)
    if hasattr(t, 'tzinfo') and t.tzinfo is not None:
        t = t.replace(tzinfo=None)
    dt_hours = (t - start_time).total_seconds() / 3600
    heading_rad = math.radians(72.0)
    dist_km = 27.0 * dt_hours
    dlat = (dist_km * math.cos(heading_rad)) / 111.0
    dlon = (dist_km * math.sin(heading_rad)) / (111.0 * math.cos(math.radians(39.91)))
    return 39.91 + dlat, -84.28 + dlon


def circle_points(lat, lon, radius_km, n=36):
    """Generate n lat/lon points forming a circle of given radius_km."""
    lats, lons = [], []
    for i in range(n + 1):
        angle = 2 * math.pi * i / n
        dlat = (radius_km * math.cos(angle)) / 111.0
        dlon = (radius_km * math.sin(angle)) / (111.0 * math.cos(math.radians(lat)))
        lats.append(lat + dlat)
        lons.append(lon + dlon)
    return lats, lons


def current_snapshots_at(result, T):
    """Build customer_id → latest snapshot up to time T."""
    if result is None:
        return {}
    snaps = {}
    for alert in result.alerts:
        t = alert.sim_time
        if isinstance(t, str):
            t = datetime.fromisoformat(t)
        t_naive = t.replace(tzinfo=None) if hasattr(t, 'tzinfo') and t.tzinfo else t
        T_naive = T.replace(tzinfo=None) if hasattr(T, 'tzinfo') and T.tzinfo else T
        if t_naive <= T_naive:
            snaps[alert.customer_id] = alert.snapshot
    # Fallback to final snapshots for customers with no alerts yet
    for cid, snap in result.snapshots.items():
        if cid not in snaps:
            snaps[cid] = snap
    return snaps


def alerts_up_to(result, T):
    """Return (alert, outcome) pairs with sim_time <= T."""
    if result is None:
        return []
    pairs = []
    for i, alert in enumerate(result.alerts):
        t = alert.sim_time
        if isinstance(t, str):
            t = datetime.fromisoformat(t)
        t_naive = t.replace(tzinfo=None) if hasattr(t, 'tzinfo') and t.tzinfo else t
        T_naive = T.replace(tzinfo=None) if hasattr(T, 'tzinfo') and T.tzinfo else T
        if t_naive <= T_naive:
            outcome = result.outcomes[i] if i < len(result.outcomes) else {}
            pairs.append((alert, outcome))
    return pairs


def events_up_to(result, T):
    if result is None:
        return []
    out = []
    for e in result.applied_events:
        t = e.get("time")
        if isinstance(t, str):
            t = datetime.fromisoformat(t)
        t_naive = t.replace(tzinfo=None) if hasattr(t, 'tzinfo') and t.tzinfo else t
        T_naive = T.replace(tzinfo=None) if hasattr(T, 'tzinfo') and T.tzinfo else T
        if t_naive <= T_naive:
            out.append(e)
    return out


def transformer_status_at(events):
    """Derive transformer status from applied events."""
    status = {tr["id"]: "healthy" for tr in TRANSFORMERS}
    cause_map = {}
    for e in events:
        did = e.get("device_id", "")
        typ = e.get("type", "")
        if did in status:
            if typ == "device_failed":
                status[did] = "failed"
                cause_map[did] = e.get("damage_type", "unknown")
            elif typ == "crew_assigned":
                if status[did] == "failed":
                    status[did] = "crew_assigned"
            elif typ == "crew_on_site":
                if status[did] in ("failed", "crew_assigned"):
                    status[did] = "on_site"
            elif typ == "damage_assessed":
                cause_map[did] = e.get("damage_type", cause_map.get(did, "unknown"))
            elif typ == "device_restored":
                status[did] = "healthy"
                cause_map.pop(did, None)
    return status, cause_map


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="dash-header">
  <h1>⚡ Storm Assistant — Live Outage Management</h1>
  <p>🌩️ Storm Rowan &nbsp;|&nbsp; AEP Dayton Region &nbsp;|&nbsp; Real-Time Simulation Dashboard</p>
</div>
""",
    unsafe_allow_html=True,
)

# ── Controls ──────────────────────────────────────────────────────────────────
if sim_error:
    st.error(f"⚠️ Simulation error: {sim_error}")
    st.info("Dashboard will render with partial static data.")

ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4, ctrl_col5 = st.columns([4, 1, 1, 1, 2])

with ctrl_col1:
    if timeline:
        labels = [fmt_time(t) for t in timeline]
        step_idx = st.slider(
            "⏱ Simulation time",
            min_value=0,
            max_value=len(timeline) - 1,
            value=st.session_state.step_idx,
            format="%d",
            key="time_slider",
            label_visibility="collapsed",
        )
        st.session_state.step_idx = step_idx
        current_T = timeline[step_idx]
    else:
        st.info("No simulation data to display.")
        current_T = datetime(2026, 10, 24, 22, 0)
        step_idx = 0

if not timeline:
    current_T = datetime(2026, 10, 24, 22, 0)
    step_idx = 0

with ctrl_col2:
    if st.button("▶ Play", use_container_width=True):
        st.session_state.playing = True

with ctrl_col3:
    if st.button("⏸ Pause", use_container_width=True):
        st.session_state.playing = False

with ctrl_col4:
    if st.button("↺ Reset", use_container_width=True):
        st.session_state.step_idx = 0
        st.session_state.playing = False
        st.rerun()

with ctrl_col5:
    if timeline:
        st.markdown(
            f"<div style='text-align:center;color:#FFB81C;font-weight:700;font-size:1.1rem;padding-top:4px'>"
            f"🕐 {fmt_dt(current_T)}</div>",
            unsafe_allow_html=True,
        )

# Auto-advance when playing
if st.session_state.playing and timeline:
    if st.session_state.step_idx < len(timeline) - 1:
        time.sleep(0.5)
        st.session_state.step_idx += 1
        st.rerun()
    else:
        st.session_state.playing = False

# ── Derive state at current_T ─────────────────────────────────────────────────
snaps_now = current_snapshots_at(result, current_T) if result else {}
alert_pairs = alerts_up_to(result, current_T)
events_now = events_up_to(result, current_T)
tr_status, tr_cause = transformer_status_at(events_now)
storm_lat, storm_lon = storm_position_at(current_T)

customers_affected = sum(
    1 for s in snaps_now.values() if hasattr(s, 'status') and s.status == "outage_confirmed"
)
messages_sent = sum(1 for _, o in alert_pairs if o.get("sent"))
active_failures = sum(1 for st_val in tr_status.values() if st_val != "healthy")

# ── Metrics row ───────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(
        f"""<div class="metric-card">
  <div class="label">🏘 Customers Affected</div>
  <div class="value">{customers_affected}</div>
  <div class="delta delta-red">of {len(CUSTOMERS)} total</div>
</div>""",
        unsafe_allow_html=True,
    )
with m2:
    st.markdown(
        f"""<div class="metric-card">
  <div class="label">📱 Messages Sent</div>
  <div class="value">{messages_sent}</div>
  <div class="delta delta-gold">{len(alert_pairs)} alerts total</div>
</div>""",
        unsafe_allow_html=True,
    )
with m3:
    st.markdown(
        f"""<div class="metric-card">
  <div class="label">🔴 Active Failures</div>
  <div class="value">{active_failures}</div>
  <div class="delta delta-red">transformers</div>
</div>""",
        unsafe_allow_html=True,
    )
with m4:
    st.markdown(
        f"""<div class="metric-card">
  <div class="label">🌩 Storm Position</div>
  <div class="value" style="font-size:1.1rem;padding-top:8px">{storm_lat:.4f}°N</div>
  <div class="delta delta-blue">{storm_lon:.4f}°W</div>
</div>""",
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)

# ── Map ───────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🗺 Live Grid Map</div>', unsafe_allow_html=True)

def build_map(storm_lat, storm_lon, snaps_now, tr_status, tr_cause):
    traces = []

    # Storm wind radius circle (filled)
    c_lats, c_lons = circle_points(storm_lat, storm_lon, 34.0, n=72)
    traces.append(go.Scattermap(
        lat=c_lats,
        lon=c_lons,
        mode="lines",
        fill="toself",
        fillcolor="rgba(255,80,30,0.18)",
        line=dict(color="rgba(255,120,30,0.6)", width=2),
        name="Wind Radius (34 km)",
        hoverinfo="name",
    ))

    # Storm center
    traces.append(go.Scattermap(
        lat=[storm_lat],
        lon=[storm_lon],
        mode="markers+text",
        marker=dict(size=22, color="#ff6a00", opacity=0.9),
        text=["⚡ Rowan"],
        textposition="top right",
        textfont=dict(size=13, color="#FFB81C"),
        name="Storm Center",
        hovertemplate="<b>Storm Rowan</b><br>Lat: %{lat:.4f}°<br>Lon: %{lon:.4f}°<extra></extra>",
    ))

    # Electrical lines: SUB → Transformers → Customers
    line_lats, line_lons = [], []
    sub_lat, sub_lon = SUBSTATION["lat"], SUBSTATION["lon"]
    for tr in TRANSFORMERS:
        line_lats += [sub_lat, tr["lat"], None]
        line_lons += [sub_lon, tr["lon"], None]
        for cust in CUSTOMERS:
            if cust["transformer_id"] == tr["id"]:
                line_lats += [tr["lat"], cust["lat"], None]
                line_lons += [tr["lon"], cust["lon"], None]
    traces.append(go.Scattermap(
        lat=line_lats,
        lon=line_lons,
        mode="lines",
        line=dict(color="rgba(100,160,220,0.35)", width=1.5),
        name="Grid Lines",
        hoverinfo="skip",
    ))

    # Substation
    traces.append(go.Scattermap(
        lat=[SUBSTATION["lat"]],
        lon=[SUBSTATION["lon"]],
        mode="markers+text",
        marker=dict(size=18, color="#FFB81C", opacity=1.0),
        text=["⭐ SUB-01"],
        textposition="top right",
        textfont=dict(size=11, color="#FFB81C"),
        name="Substation",
        hovertemplate="<b>SUB-01 Maple Ridge</b><extra></extra>",
    ))

    # Transformers
    tr_color_map = {
        "healthy":       "#28a745",
        "failed":        "#dc3545",
        "crew_assigned": "#ffc107",
        "on_site":       "#ff8800",
    }
    for tr in TRANSFORMERS:
        st_val = tr_status.get(tr["id"], "healthy")
        color = tr_color_map.get(st_val, "#888")
        cause = tr_cause.get(tr["id"], "")
        label_map = {
            "healthy":       "✅",
            "failed":        "❌",
            "crew_assigned": "🔧",
            "on_site":       "👷",
        }
        icon = label_map.get(st_val, "❓")
        traces.append(go.Scattermap(
            lat=[tr["lat"]],
            lon=[tr["lon"]],
            mode="markers+text",
            marker=dict(size=14, color=color, opacity=0.95),
            text=[f"{icon} {tr['id']}"],
            textposition="top center",
            textfont=dict(size=10, color=color),
            name=tr["id"],
            hovertemplate=f"<b>{tr['id']}</b><br>Status: {st_val}<br>Cause: {cause or '—'}<extra></extra>",
        ))

    # Customers
    cust_color_map = {
        "normal":           "#28a745",
        "at_risk":          "#ffc107",
        "outage_confirmed": "#dc3545",
        "restored":         "#17a2b8",
    }
    for cust in CUSTOMERS:
        snap = snaps_now.get(cust["id"])
        status = getattr(snap, "status", "normal") if snap else "normal"
        color = cust_color_map.get(status, "#888")
        med = "🏥 " if cust["medical"] else ""
        nc = "🔕 " if not cust["consent"] else ""
        risk = getattr(snap, "risk_score", None)
        risk_str = f"{risk:.2f}" if risk is not None else "—"
        traces.append(go.Scattermap(
            lat=[cust["lat"]],
            lon=[cust["lon"]],
            mode="markers+text",
            marker=dict(size=11, color=color, opacity=0.95),
            text=[f"{med}{nc}{cust['name']}"],
            textposition="bottom right",
            textfont=dict(size=9, color="#e0eeff"),
            name=cust["id"],
            hovertemplate=(
                f"<b>{cust['name']} ({cust['id']})</b><br>"
                f"Status: {status}<br>Risk: {risk_str}<extra></extra>"
            ),
        ))

    layout = go.Layout(
        map=dict(
            style="open-street-map",
            center=dict(lat=39.762, lon=-84.182),
            zoom=13.2,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=460,
        paper_bgcolor="#0a1929",
        plot_bgcolor="#0a1929",
        legend=dict(
            bgcolor="rgba(10,25,41,0.85)",
            bordercolor="#1e3a5f",
            borderwidth=1,
            font=dict(color="#c8daf0", size=11),
            x=0.01, y=0.99,
        ),
        showlegend=True,
    )

    return go.Figure(data=traces, layout=layout)


map_fig = build_map(storm_lat, storm_lon, snaps_now, tr_status, tr_cause)
st.plotly_chart(map_fig, use_container_width=True, config={"displayModeBar": False})

# ── Two-column layout ─────────────────────────────────────────────────────────
left_col, right_col = st.columns([1, 1], gap="medium")

# ── LEFT: SMS Feed ────────────────────────────────────────────────────────────
with left_col:
    st.markdown('<div class="section-title">📱 SMS Message Feed</div>', unsafe_allow_html=True)

    if not alert_pairs:
        st.markdown(
            "<div style='color:#5a7a9a;font-style:italic;padding:12px'>No messages sent yet…</div>",
            unsafe_allow_html=True,
        )
    else:
        bubbles_html = '<div class="sms-feed-container">'
        for alert, outcome in reversed(alert_pairs):
            sent = outcome.get("sent", False)
            body = outcome.get("body") or ""
            reason = outcome.get("reason") or ""
            cid = alert.customer_id
            atype = alert.alert_type
            snap = alert.snapshot
            name = getattr(snap, "first_name", cid)
            t_str = fmt_time(alert.sim_time)
            badge_cls = f"badge-{atype}"
            atype_label = atype.replace("_", " ").title()
            bubble_cls = "sms-bubble" + ("" if sent else " blocked")
            status_tag = (
                '<span class="sent-tag">✅ Sent</span>'
                if sent
                else f'<span class="blocked-tag">⛔ Blocked — {reason}</span>'
            )
            body_display = body.replace("\n", "<br>") if body else "<em style='color:#666'>No message body</em>"
            bubbles_html += f"""
<div class="{bubble_cls}">
  <div class="sms-header">
    <span class="sms-name">{name} <span class="cust-id">{cid}</span></span>
    <span class="sms-time">{t_str}</span>
  </div>
  <div class="sms-footer">
    <span class="badge {badge_cls}">{atype_label}</span>
    {status_tag}
  </div>
  <div class="sms-body">{body_display}</div>
</div>"""
        bubbles_html += "</div>"
        st.markdown(bubbles_html, unsafe_allow_html=True)

# ── RIGHT: Grid Status tree ───────────────────────────────────────────────────
with right_col:
    st.markdown('<div class="section-title">🔌 Grid Status</div>', unsafe_allow_html=True)

    tr_color_class = {
        "healthy":       "tr-ok",
        "failed":        "tr-fail",
        "crew_assigned": "tr-crew",
        "on_site":       "tr-crew",
    }
    tr_icon = {
        "healthy":       "✅",
        "failed":        "❌",
        "crew_assigned": "🔧",
        "on_site":       "👷",
    }
    status_class = {
        "normal":           "c-ok",
        "at_risk":          "c-risk",
        "outage_confirmed": "c-out",
        "restored":         "c-rest",
    }
    status_icon = {
        "normal":           "🟢",
        "at_risk":          "🟡",
        "outage_confirmed": "🔴",
        "restored":         "🔵",
    }

    # Compute feeder risk from snapshots
    def feeder_risk(fdr_id):
        risks = []
        for cust in CUSTOMERS:
            snap = snaps_now.get(cust["id"])
            if snap and hasattr(snap, "risk_score") and snap.risk_score is not None:
                tr_obj = next((t for t in TRANSFORMERS if t["id"] == cust["transformer_id"]), None)
                if tr_obj:
                    fdr = next((f for f in FEEDERS if f["id"] == tr_obj["feeder_id"] and f["id"] == fdr_id), None)
                    if fdr:
                        risks.append(snap.risk_score)
        return sum(risks) / len(risks) if risks else 0.0

    tree_html = '<div class="grid-tree">'
    tree_html += f'<div><span class="sub">⭐ SUB-01</span> <span style="color:#aaa">— Maple Ridge Substation 🟡</span></div>'

    for fdr in FEEDERS:
        risk_val = feeder_risk(fdr["id"])
        tree_html += f'<div style="margin-left:12px"><span class="fdr">└ {fdr["id"]}</span> <span style="color:#6b8db3;font-size:0.78rem">(risk: {risk_val:.2f})</span></div>'
        fdr_transformers = [t for t in TRANSFORMERS if t["feeder_id"] == fdr["id"]]
        for ti, tr in enumerate(fdr_transformers):
            is_last_tr = (ti == len(fdr_transformers) - 1)
            st_val = tr_status.get(tr["id"], "healthy")
            cause = tr_cause.get(tr["id"], "")
            cause_str = f" — {cause}" if cause else ""
            tr_cls = tr_color_class.get(st_val, "tr-ok")
            icon = tr_icon.get(st_val, "❓")
            tr_prefix = "└" if is_last_tr else "├"
            tree_html += f'<div style="margin-left:24px"><span class="{tr_cls}">{tr_prefix} {tr["id"]} {icon} {st_val}{cause_str}</span></div>'
            cust_list = [c for c in CUSTOMERS if c["transformer_id"] == tr["id"]]
            for ci, cust in enumerate(cust_list):
                is_last_c = (ci == len(cust_list) - 1)
                snap = snaps_now.get(cust["id"])
                s = getattr(snap, "status", "normal") if snap else "normal"
                c_cls = status_class.get(s, "c-ok")
                c_icon = status_icon.get(s, "🟢")
                med = "🏥" if cust["medical"] else ""
                nc = " (no consent)" if not cust["consent"] else ""
                c_prefix = "└" if is_last_c else "├"
                tree_html += (
                    f'<div style="margin-left:40px"><span class="{c_cls}">'
                    f'{c_prefix} {cust["id"]} {cust["name"]} {c_icon} {s}{med}{nc}'
                    f'</span></div>'
                )
    tree_html += "</div>"
    st.markdown(tree_html, unsafe_allow_html=True)

# ── Alert Decision Log ────────────────────────────────────────────────────────
st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
with st.expander("📋 Alert Decision Log", expanded=False):
    if result and result.audit and result.audit.entries:
        T_naive = (
            current_T.replace(tzinfo=None)
            if hasattr(current_T, 'tzinfo') and current_T.tzinfo else current_T
        )
        rows = []
        for entry in result.audit.entries:
            t = entry.time if hasattr(entry, 'time') else None
            if t is None:
                continue
            if isinstance(t, str):
                t = datetime.fromisoformat(t)
            t_n = t.replace(tzinfo=None) if hasattr(t, 'tzinfo') and t.tzinfo else t
            if t_n > T_naive:
                continue
            cat = getattr(entry, 'category', '')
            if cat not in ("alert_decision", "delivery_outcome", "deferred_delivery_outcome"):
                continue
            rows.append({
                "Time": fmt_time(t),
                "Customer": getattr(entry, 'customer_id', '—') or '—',
                "Alert Type": getattr(entry, 'alert_type', '—') or '—',
                "Decision": getattr(entry, 'decision', '—') or '—',
                "Reason": getattr(entry, 'reason_code', '—') or '—',
            })
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Decision": st.column_config.TextColumn(width="small"),
                    "Time": st.column_config.TextColumn(width="small"),
                },
            )
        else:
            st.info("No alert decisions recorded yet.")
    else:
        st.info("No audit entries available.")

# ── Customer Detail Cards ─────────────────────────────────────────────────────
st.markdown('<div class="section-title">👥 Customer Detail</div>', unsafe_allow_html=True)

card_cols = st.columns(4)
for i, cust in enumerate(CUSTOMERS):
    with card_cols[i]:
        snap = snaps_now.get(cust["id"])
        status = getattr(snap, "status", "normal") if snap else "normal"
        risk = getattr(snap, "risk_score", None) if snap else None
        etr_s = getattr(snap, "etr_start", None) if snap else None
        etr_e = getattr(snap, "etr_end", None) if snap else None
        conf = getattr(snap, "confidence", None) if snap else None
        crew = getattr(snap, "crew_status", None) if snap else None

        # Find last SMS body for this customer
        last_body = None
        for alert, outcome in reversed(alert_pairs):
            if alert.customer_id == cust["id"] and outcome.get("body"):
                last_body = outcome["body"]
                break

        med_badge = ' <span style="background:#2a0a0a;color:#ff8080;font-size:0.65rem;padding:2px 6px;border-radius:10px;font-weight:700">🏥 MEDICAL</span>' if cust["medical"] else ""
        nc_badge = ' <span style="background:#1a1a1a;color:#888;font-size:0.65rem;padding:2px 6px;border-radius:10px;font-weight:700">🔕 NO SMS</span>' if not cust["consent"] else ""

        pill_cls = f"pill-{status}"
        status_label = status.replace("_", " ").title()

        etr_html = ""
        if etr_s or etr_e:
            etr_html = f'<div class="etr-text">🕐 ETR: {fmt_time(etr_s)} – {fmt_time(etr_e)}'
            if conf:
                etr_html += f' <em>({conf})</em>'
            etr_html += "</div>"

        crew_html = ""
        if crew:
            crew_html = f'<div class="etr-text">👷 Crew: {crew.replace("_", " ").title()}</div>'

        last_sms_html = ""
        if last_body:
            preview = last_body[:120] + ("…" if len(last_body) > 120 else "")
            last_sms_html = f'<div class="sms-preview">💬 {preview}</div>'
        elif not cust["consent"]:
            last_sms_html = '<div class="sms-preview">No consent — SMS blocked</div>'

        st.markdown(
            f"""<div class="cust-card">
  <div class="cust-name">{cust['name']}{med_badge}{nc_badge}</div>
  <div class="cust-id">{cust['id']} · {cust['transformer_id']}</div>
  <div><span class="status-pill {pill_cls}">{status_label}</span></div>
  {etr_html}
  {crew_html}
  {last_sms_html}
</div>""",
            unsafe_allow_html=True,
        )
        # Risk score progress bar
        if risk is not None:
            st.progress(float(risk), text=f"Risk: {risk:.0%}")
        else:
            st.progress(0.0, text="Risk: —")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div style='text-align:center;color:#3a5a7a;font-size:0.72rem;margin-top:24px;padding-top:12px;
border-top:1px solid #1e3a5f'>
  ⚡ Storm Assistant &nbsp;|&nbsp; AEP Hackathon 2026 &nbsp;|&nbsp;
  Maple Ridge District &nbsp;|&nbsp; Built with Streamlit + Plotly
</div>
""",
    unsafe_allow_html=True,
)
