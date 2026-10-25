"""Storm Assistant Interactive Outage Concierge & Simulator Server.

Powers:
1. Operator Control Center (/operator)
2. Public Threat Display (/user)
3. Dedicated Customer Experience (/customer)
4. Mobile Android APK Real-time Alerts (/api/alerts/poll, /api/notifications/poll)

Integrates:
- Official HackOHI/O 2026 challenge data (Circuit 0000027, matched_upstream.txt, ARCOS damage)
- Grounded explainable risk engine (analytics/predictive/grounded_risk.py)
- Labor-grounded restoration engine using Install_Labor_HackOHIO.xlsx (analytics/predictive/labor_etr.py)
- Synthetic mode backward compatibility for offline testing
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import json
import math
import os
from pathlib import Path
import uuid
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Local analytics imports
from analytics.predictive.grounded_risk import grounded_risk_engine, haversine_distance_km
from analytics.predictive.labor_etr import labor_etr_engine, NetworkIncident
from data.challenge.labor_model import labor_model, RepairTask

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
PROJECT_ROOT = BASE_DIR.parents[2]
CHALLENGE_DATA_PATH = BASE_DIR.parents[1] / "data" / "challenge" / "curated_demo_grid.json"

APK_PATHS = [
    STATIC_DIR / "StormAlert.apk",
    PROJECT_ROOT / "StormAlert.apk",
    BASE_DIR.parents[1] / "apps" / "web" / "static" / "StormAlert.apk",
    PROJECT_ROOT / "android_app" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk",
]

app = FastAPI(title="AEP Storm Assistant - AI Outage Concierge Simulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Math & Spatial Helpers ───────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return haversine_distance_km(lat1, lon1, lat2, lon2)


def interpolate_path(path: List[Dict[str, float]], progress: float) -> Dict[str, float]:
    """Given a list of [{lat, lon}], return interpolated lat/lon at progress in [0, 1]."""
    if not path:
        return {"lat": 37.25, "lon": -80.20}
    if len(path) == 1 or progress <= 0:
        return {"lat": path[0]["lat"], "lon": path[0]["lon"]}
    if progress >= 1.0:
        return {"lat": path[-1]["lat"], "lon": path[-1]["lon"]}

    lengths = []
    total_len = 0.0
    for i in range(len(path) - 1):
        d = haversine_km(path[i]["lat"], path[i]["lon"], path[i + 1]["lat"], path[i + 1]["lon"])
        lengths.append(d)
        total_len += d

    if total_len <= 1e-6:
        return {"lat": path[0]["lat"], "lon": path[0]["lon"]}

    target_dist = progress * total_len
    acc = 0.0
    for i in range(len(path) - 1):
        seg = lengths[i]
        if acc + seg >= target_dist:
            ratio = (target_dist - acc) / seg if seg > 0 else 0
            lat = path[i]["lat"] + ratio * (path[i + 1]["lat"] - path[i]["lat"])
            lon = path[i]["lon"] + ratio * (path[i + 1]["lon"] - path[i]["lon"])
            return {"lat": round(lat, 5), "lon": round(lon, 5)}
        acc += seg

    return {"lat": path[-1]["lat"], "lon": path[-1]["lon"]}


# ── Grid State & Datasets ─────────────────────────────────────────────────────

# Default Synthetic Grids (Dayton, OH & Regional Transmission)
SYNTHETIC_GRIDS = [
    {
        "id": "SUB-01",
        "name": "Maple Ridge Substation",
        "type": "substation",
        "lat": 39.7584,
        "lon": -84.1916,
        "feeder_count": 2,
        "customers_count": 2400,
        "status": "normal",
        "threat_level": "none",
        "service_type": "Overhead",
    },
    {
        "id": "TR-101",
        "name": "TR-101 (Oakwood / Medical Priority)",
        "type": "transformer",
        "lat": 39.7621,
        "lon": -84.1848,
        "feeder_count": 1,
        "customers_count": 48,
        "status": "normal",
        "threat_level": "none",
        "service_type": "Overhead",
    },
    {
        "id": "TR-102",
        "name": "TR-102 (Pine Hill Feeder)",
        "type": "transformer",
        "lat": 39.7640,
        "lon": -84.1809,
        "feeder_count": 1,
        "customers_count": 62,
        "status": "normal",
        "threat_level": "none",
        "service_type": "Underground",
    },
    {
        "id": "TR-201",
        "name": "TR-201 (Cedar Grove Lateral)",
        "type": "transformer",
        "lat": 39.7615,
        "lon": -84.1772,
        "feeder_count": 1,
        "customers_count": 55,
        "status": "normal",
        "threat_level": "none",
        "service_type": "Overhead",
    },
]

# Initial Storms
DEFAULT_STORMS = [
    {
        "id": "storm-helene-track",
        "name": "Tropical Storm Helene Path",
        "radius_km": 35.0,
        "speed_kmh": 40.0,
        "peak_gust_kmh": 90.0,
        "rainfall_mm": 40.0,
        "path": [
            {"lat": 37.0500, "lon": -80.4500},
            {"lat": 37.1800, "lon": -80.3200},
            {"lat": 37.2340, "lon": -80.2100},  # Direct over Elliston Circuit 0000027
            {"lat": 37.2900, "lon": -80.0500},  # Salem / Roanoke
            {"lat": 37.3800, "lon": -79.9200},
        ],
        "progress": 0.35,
        "current_pos": {"lat": 37.2340, "lon": -80.2100},
        "is_playing": False,
        "auto_notify": True,
    },
    {
        "id": "storm-rowan",
        "name": "Storm Rowan (Midwest)",
        "radius_km": 35.0,
        "speed_kmh": 45.0,
        "peak_gust_kmh": 85.0,
        "rainfall_mm": 30.0,
        "path": [
            {"lat": 39.9100, "lon": -84.2800},
            {"lat": 39.7900, "lon": -84.2100},
            {"lat": 39.7600, "lon": -84.1850},
            {"lat": 39.6800, "lon": -83.9500},
        ],
        "progress": 0.05,
        "current_pos": {"lat": 39.9100, "lon": -84.2800},
        "is_playing": False,
        "auto_notify": True,
    },
]


class SimulationState:
    """Central simulation state with official challenge grid support."""

    def __init__(self):
        self.data_source: str = "official_challenge"  # "official_challenge" or "synthetic"
        self.storms: Dict[str, Dict[str, Any]] = {s["id"]: dict(s) for s in DEFAULT_STORMS}
        self.grids: Dict[str, Dict[str, Any]] = {}
        self.challenge_premises: Dict[str, Dict[str, Any]] = {}
        self.challenge_facilities: List[Dict[str, Any]] = []
        self.historical_damage_points: List[Dict[str, Any]] = []

        # Scenario state
        self.active_incidents: Dict[str, NetworkIncident] = {}
        self.crews_available: int = 2
        self.access_conditions: List[str] = ["backyard"]

        # Notification state
        self.notifications: List[Dict[str, Any]] = []
        self.notification_counter: int = 1
        self.notified_pairs: Set[str] = set()
        self.subscribers: Set[WebSocket] = set()

        self._load_datasets()

    def _load_datasets(self):
        """Load official challenge dataset if present, else fallback to synthetic."""
        # Always populate base synthetic grids
        for g in SYNTHETIC_GRIDS:
            self.grids[g["id"]] = dict(g)

        if CHALLENGE_DATA_PATH.exists():
            try:
                with open(CHALLENGE_DATA_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.challenge_facilities = data.get("facilities", [])
                self.historical_damage_points = data.get("historical_damage", [])

                for p in data.get("premises", []):
                    pid = p["premise_id"]
                    self.challenge_premises[pid] = p

                    # Add representative equipment as visible grid nodes
                    if p.get("is_medical_priority") or len(self.grids) < 30:
                        tag = p.get("transformer_tag")
                        grid_node_id = f"XFMR-{tag[-6:]}" if tag else pid
                        if grid_node_id not in self.grids:
                            self.grids[grid_node_id] = {
                                "id": grid_node_id,
                                "name": f"Transformer {tag} ({p.get('city', 'VA')})",
                                "type": "transformer",
                                "lat": p["latitude"],
                                "lon": p["longitude"],
                                "feeder_count": 1,
                                "customers_count": 8,
                                "status": "normal",
                                "threat_level": "none",
                                "service_type": p.get("service_type", "Overhead"),
                                "is_medical_priority": p.get("is_medical_priority", False),
                            }

                # Add critical facilities (Hospitals, Fire Stations) to grids
                for fac in self.challenge_facilities:
                    fid = fac["facility_id"]
                    self.grids[fid] = {
                        "id": fid,
                        "name": fac["name"],
                        "type": "critical_facility",
                        "lat": fac["latitude"],
                        "lon": fac["longitude"],
                        "feeder_count": 2,
                        "customers_count": 1,
                        "status": "normal",
                        "threat_level": "none",
                        "service_type": "Underground",
                        "is_medical_priority": True,
                    }
                self.data_source = "official_challenge"
            except Exception as e:
                self.data_source = "synthetic"
        else:
            self.data_source = "synthetic"

    def add_notification(
        self,
        storm_name: str,
        grid_id: str,
        grid_name: str,
        alert_type: str,
        title: str,
        body: str,
        eta_minutes: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Record and broadcast a new customer/grid notification with stable UUID."""
        notif = {
            "id": self.notification_counter,
            "uuid": str(uuid.uuid4()),
            "timestamp": datetime.now().strftime("%I:%M:%S %p"),
            "iso_time": datetime.now().isoformat(),
            "storm_name": storm_name,
            "grid_id": grid_id,
            "grid_name": grid_name,
            "alert_type": alert_type,
            "title": title,
            "body": body,
            "eta_minutes": eta_minutes,
        }
        self.notification_counter += 1
        self.notifications.insert(0, notif)
        if len(self.notifications) > 200:
            self.notifications.pop()
        return notif

    def recalculate(self) -> List[Dict[str, Any]]:
        """Recalculate proximity across ALL storms, aggregating worst-case threat."""
        new_notifications = []

        # 1. Reset all grids to baseline normal
        for grid in self.grids.values():
            # Check if this asset has an active damaged incident
            is_damaged = any(
                inc.asset_id == grid["id"] or inc.asset_id in grid.get("name", "")
                for inc in self.active_incidents.values()
                if not inc.is_repaired
            )
            grid["status"] = "outage" if is_damaged else "normal"
            grid["threat_level"] = "direct_hit" if is_damaged else "none"
            grid["distance_km"] = None
            grid["predicted_arrival"] = "FIELD REPAIR IN PROGRESS" if is_damaged else None
            grid["predicted_eta_min"] = None
            grid["worst_gust_kmh"] = 0.0

        # 2. Multi-storm evaluation: keep worst-case threat per grid
        for storm in self.storms.values():
            path = storm.get("path", [])
            progress = storm.get("progress", 0.0)
            cur_pos = interpolate_path(path, progress)
            storm["current_pos"] = cur_pos
            radius = max(5.0, float(storm.get("radius_km", 35.0)))
            speed = max(5.0, float(storm.get("speed_kmh", 40.0)))
            gust_kmh = float(storm.get("peak_gust_kmh", 80.0))
            auto_notify = storm.get("auto_notify", True)

            for grid in self.grids.values():
                d = haversine_km(cur_pos["lat"], cur_pos["lon"], grid["lat"], grid["lon"])

                # Update minimum distance to any storm
                if grid["distance_km"] is None or d < grid["distance_km"]:
                    grid["distance_km"] = round(d, 1)

                if gust_kmh > grid["worst_gust_kmh"]:
                    grid["worst_gust_kmh"] = gust_kmh

                # Direct Hit Zone
                if d <= radius:
                    if grid["threat_level"] != "direct_hit":
                        grid["threat_level"] = "direct_hit"
                        # Honest outage confirmation rule:
                        # Only confirmed outage if physical damage recorded OR severe hurricane wind >= 105 km/h on overhead lines
                        is_overhead = grid.get("service_type") == "Overhead"
                        if grid["status"] != "outage":
                            if gust_kmh >= 105.0 and is_overhead:
                                grid["status"] = "outage"
                            else:
                                grid["status"] = "warning"

                        grid["predicted_arrival"] = "ACTIVE IMPACT NOW"
                        grid["predicted_eta_min"] = 0

                    dedup_key = f"{storm['id']}:{grid['id']}:hit"
                    if dedup_key not in self.notified_pairs and auto_notify:
                        self.notified_pairs.add(dedup_key)
                        alert_type = "outage_confirmed" if grid["status"] == "outage" else "impact_warning"
                        notif = self.add_notification(
                            storm_name=storm["name"],
                            grid_id=grid["id"],
                            grid_name=grid["name"],
                            alert_type=alert_type,
                            title=f"⚠️ STORM IMPACT: {grid['name']}",
                            body=f"{storm['name']} is impacting {grid['name']} with peak gusts of {gust_kmh:.0f} km/h. High monitoring in effect.",
                            eta_minutes=0,
                        )
                        new_notifications.append(notif)

                # Warning / Approaching Zone (within 2.2x radius)
                elif d <= radius * 2.2:
                    dist_to_edge = max(0.0, d - radius)
                    eta_mins = int((dist_to_edge / speed) * 60)
                    arrival_time = (datetime.now() + timedelta(minutes=eta_mins)).strftime("%I:%M %p")

                    if grid["threat_level"] not in ("direct_hit",):
                        grid["threat_level"] = "approaching"
                        if grid["status"] != "outage":
                            grid["status"] = "warning"
                        grid["predicted_arrival"] = f"{arrival_time} (in {eta_mins}m)"
                        grid["predicted_eta_min"] = eta_mins

                    dedup_key = f"{storm['id']}:{grid['id']}:warn"
                    if dedup_key not in self.notified_pairs and auto_notify:
                        self.notified_pairs.add(dedup_key)
                        notif = self.add_notification(
                            storm_name=storm["name"],
                            grid_id=grid["id"],
                            grid_name=grid["name"],
                            alert_type="predicted_hit",
                            title=f"⚡ PREPARE: {grid['name']} in Storm Path",
                            body=f"{storm['name']} is forecast to approach {grid['name']} around {arrival_time} (in {eta_mins}m). Please prepare backup power and charge medical devices.",
                            eta_minutes=eta_mins,
                        )
                        new_notifications.append(notif)

        return new_notifications


state = SimulationState()


# ── Background Animation Task ────────────────────────────────────────────────

async def simulation_loop():
    """Background task to advance playing storms and broadcast live updates."""
    while True:
        try:
            has_playing = any(s.get("is_playing", False) for s in state.storms.values())
            if has_playing:
                for storm in state.storms.values():
                    if storm.get("is_playing", False):
                        cur = storm.get("progress", 0.0)
                        cur += 0.006
                        if cur >= 1.0:
                            cur = 0.0
                        storm["progress"] = round(cur, 4)

                new_notifs = state.recalculate()
                await broadcast_state(new_notifs)
            await asyncio.sleep(0.4)
        except Exception:
            await asyncio.sleep(0.4)


@app.on_event("startup")
async def startup_event():
    state.recalculate()
    asyncio.create_task(simulation_loop())


async def broadcast_state(new_notifications: Optional[List[Dict[str, Any]]] = None):
    """Push the latest state payload to all connected WebSockets."""
    if not state.subscribers:
        return
    payload = {
        "type": "state_update",
        "data_source": state.data_source,
        "storms": list(state.storms.values()),
        "grids": list(state.grids.values()),
        "notifications": state.notifications[:30],
        "new_alerts": new_notifications or [],
        "active_incidents": [
            {
                "incident_id": inc.incident_id,
                "asset_id": inc.asset_id,
                "description": inc.damage_description,
                "cu_type": inc.cu_type,
                "is_repaired": inc.is_repaired,
            }
            for inc in state.active_incidents.values()
        ],
        "crews_available": state.crews_available,
        "access_conditions": state.access_conditions,
    }
    dead = set()
    for ws in list(state.subscribers):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)
    state.subscribers.difference_update(dead)


# ── REST Input Models with Strict Validation ──────────────────────────────────

class StormCreate(BaseModel):
    id: Optional[str] = None
    name: str = Field(default="New Storm", min_length=2, max_length=60)
    radius_km: float = Field(default=35.0, ge=1.0, le=500.0)
    speed_kmh: float = Field(default=45.0, ge=0.0, le=300.0)
    peak_gust_kmh: float = Field(default=95.0, ge=0.0, le=350.0)
    path: List[Dict[str, float]]
    auto_notify: bool = True


class StormUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=60)
    radius_km: Optional[float] = Field(default=None, ge=1.0, le=500.0)
    speed_kmh: Optional[float] = Field(default=None, ge=0.0, le=300.0)
    peak_gust_kmh: Optional[float] = Field(default=None, ge=0.0, le=350.0)
    progress: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    path: Optional[List[Dict[str, float]]] = None
    is_playing: Optional[bool] = None
    auto_notify: Optional[bool] = None


class GridCreate(BaseModel):
    id: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=80)
    type: str = "substation"
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    customers_count: int = Field(default=1500, ge=1)


class IncidentCreate(BaseModel):
    asset_id: str
    asset_type: str = "transformer"  # transformer, pole, wire, fuse, recloser
    cu_type: str = "transformer_50kva"
    description: str = "Damaged 50kVA transformer"
    quantity: int = 1
    access_modifiers: List[str] = Field(default_factory=list)


class ScenarioControls(BaseModel):
    crews_available: Optional[int] = Field(default=None, ge=1, le=10)
    access_conditions: Optional[List[str]] = None


class ManualAlert(BaseModel):
    grid_id: str
    storm_id: Optional[str] = None
    message: Optional[str] = None


# ── REST Endpoints ───────────────────────────────────────────────────────────

@app.get("/api/state")
def get_state():
    state.recalculate()
    return {
        "data_source": state.data_source,
        "storms": list(state.storms.values()),
        "grids": list(state.grids.values()),
        "notifications": state.notifications,
        "active_incidents": [
            {
                "incident_id": inc.incident_id,
                "asset_id": inc.asset_id,
                "description": inc.damage_description,
                "cu_type": inc.cu_type,
                "is_repaired": inc.is_repaired,
            }
            for inc in state.active_incidents.values()
        ],
        "crews_available": state.crews_available,
        "access_conditions": state.access_conditions,
    }


@app.post("/api/storms")
async def create_storm(payload: StormCreate):
    storm_id = payload.id or f"storm-{uuid.uuid4().hex[:6]}"
    storm = {
        "id": storm_id,
        "name": payload.name,
        "radius_km": payload.radius_km,
        "speed_kmh": payload.speed_kmh,
        "peak_gust_kmh": payload.peak_gust_kmh,
        "path": payload.path,
        "progress": 0.0,
        "current_pos": payload.path[0] if payload.path else {"lat": 37.25, "lon": -80.20},
        "is_playing": False,
        "auto_notify": payload.auto_notify,
    }
    state.storms[storm_id] = storm
    new_notifs = state.recalculate()
    await broadcast_state(new_notifs)
    return storm


@app.put("/api/storms/{storm_id}")
async def update_storm(storm_id: str, payload: StormUpdate):
    if storm_id not in state.storms:
        raise HTTPException(status_code=404, detail="Storm not found")
    storm = state.storms[storm_id]
    for key, val in payload.dict(exclude_unset=True).items():
        storm[key] = val
    new_notifs = state.recalculate()
    await broadcast_state(new_notifs)
    return storm


@app.delete("/api/storms/{storm_id}")
async def delete_storm(storm_id: str):
    if storm_id in state.storms:
        del state.storms[storm_id]
        state.recalculate()
        await broadcast_state()
    return {"ok": True}


@app.post("/api/storms/{storm_id}/progress")
async def set_storm_progress(storm_id: str, progress: float):
    if storm_id not in state.storms:
        raise HTTPException(status_code=404, detail="Storm not found")
    storm = state.storms[storm_id]
    storm["progress"] = max(0.0, min(1.0, progress))
    new_notifs = state.recalculate()
    await broadcast_state(new_notifs)
    return storm


@app.post("/api/storms/{storm_id}/play")
async def toggle_play(storm_id: str):
    if storm_id not in state.storms:
        raise HTTPException(status_code=404, detail="Storm not found")
    storm = state.storms[storm_id]
    storm["is_playing"] = not storm.get("is_playing", False)
    await broadcast_state()
    return {"is_playing": storm["is_playing"]}


@app.post("/api/grids")
async def create_grid(payload: GridCreate):
    grid = {
        "id": payload.id,
        "name": payload.name,
        "type": payload.type,
        "lat": payload.lat,
        "lon": payload.lon,
        "feeder_count": 2,
        "customers_count": payload.customers_count,
        "status": "normal",
        "threat_level": "none",
    }
    state.grids[payload.id] = grid
    state.recalculate()
    await broadcast_state()
    return grid


# ── Scenario & Damage Simulation Endpoints ───────────────────────────────────

@app.post("/api/scenario/incident")
async def inject_incident(payload: IncidentCreate):
    """Inject a verified physical damage ticket affecting a grid asset."""
    inc_id = f"INC-{uuid.uuid4().hex[:6]}"
    incident = NetworkIncident(
        incident_id=inc_id,
        asset_id=payload.asset_id,
        asset_type=payload.asset_type,
        damage_description=payload.description,
        cu_type=payload.cu_type,
        quantity=payload.quantity,
        access_modifiers=payload.access_modifiers or list(state.access_conditions),
    )
    state.active_incidents[inc_id] = incident

    # Emit confirmed outage notification
    notif = state.add_notification(
        storm_name="Grid Operations Center",
        grid_id=payload.asset_id,
        grid_name=f"Equipment {payload.asset_id}",
        alert_type="outage_confirmed",
        title=f"🚨 DAMAGE REPORTED: {payload.description}",
        body=f"Physical damage confirmed on {payload.asset_id}. Repair crew dispatch queued.",
        eta_minutes=None,
    )
    state.recalculate()
    await broadcast_state([notif])
    return incident


@app.delete("/api/scenario/incident/{incident_id}")
async def resolve_incident(incident_id: str):
    """Mark an incident repaired and restore power."""
    if incident_id in state.active_incidents:
        inc = state.active_incidents[incident_id]
        inc.is_repaired = True
        del state.active_incidents[incident_id]
        notif = state.add_notification(
            storm_name="Grid Operations Center",
            grid_id=inc.asset_id,
            grid_name=f"Equipment {inc.asset_id}",
            alert_type="power_restored",
            title=f"✅ POWER RESTORED: {inc.asset_id}",
            body=f"Repairs completed on {inc.damage_description}. Feeder re-energized successfully.",
            eta_minutes=0,
        )
        state.recalculate()
        await broadcast_state([notif])
    return {"ok": True}


@app.post("/api/scenario/controls")
async def update_scenario_controls(payload: ScenarioControls):
    """Update crew count and access condition adders."""
    if payload.crews_available is not None:
        state.crews_available = payload.crews_available
    if payload.access_conditions is not None:
        state.access_conditions = payload.access_conditions
    state.recalculate()
    await broadcast_state()
    return {
        "crews_available": state.crews_available,
        "access_conditions": state.access_conditions,
    }


# ── Dedicated Customer Experience Endpoints ──────────────────────────────────

@app.get("/api/customer/premises")
def list_demo_premises():
    """List curated demonstration premises (Life Support, Underground, Overhead, Hospital)."""
    options = []
    # If challenge premises exist, surface representative selections
    if state.challenge_premises:
        # Medical priority first
        for pid, p in state.challenge_premises.items():
            if p.get("is_medical_priority"):
                options.append({
                    "premise_id": pid,
                    "label": f"🏥 {pid} (Medical Priority / Life Support - {p['service_type']}, {p['city']})",
                    "service_type": p["service_type"],
                    "is_medical_priority": True,
                    "city": p["city"],
                })
        # Next standard premises
        for pid, p in list(state.challenge_premises.items())[:12]:
            if not p.get("is_medical_priority"):
                options.append({
                    "premise_id": pid,
                    "label": f"⚡ {pid} (Residential {p['service_type']} - {p['city']})",
                    "service_type": p["service_type"],
                    "is_medical_priority": False,
                    "city": p["city"],
                })
    else:
        # Synthetic fallback premises
        options = [
            {"premise_id": "CUST-001", "label": "🏥 CUST-001 (Avery - Medical Priority, Oakwood)", "service_type": "Overhead", "is_medical_priority": True, "city": "Dayton, OH"},
            {"premise_id": "CUST-002", "label": "⚡ CUST-002 (Jordan - Standard Residential, Oakwood)", "service_type": "Overhead", "is_medical_priority": False, "city": "Dayton, OH"},
            {"premise_id": "CUST-003", "label": "⚡ CUST-003 (Casey - Underground Feeder)", "service_type": "Underground", "is_medical_priority": False, "city": "Dayton, OH"},
        ]
    return options


@app.get("/api/customer/profile")
def get_customer_profile(premise_id: str = Query(...)):
    """
    Complete customer experience evaluation:
    - Confirmed power status
    - Explainable outage-risk assessment
    - Labor-grounded restoration bounds (ETR)
    - Upstream electrical dependency status
    - Personalized preparation actions
    - Alert eligibility & transparency audit
    """
    premise_data = state.challenge_premises.get(premise_id)

    # Fallback synthetic premise handling
    if not premise_data:
        if premise_id == "CUST-001":
            premise_data = {
                "premise_id": "CUST-001",
                "service_type": "Overhead",
                "is_medical_priority": True,
                "city": "Dayton",
                "state": "OH",
                "latitude": 39.7621,
                "longitude": -84.1848,
                "transformer_tag": "TR-101",
                "circuit_id": "FDR-01",
                "upstream_devices": [{"layer": "eo_power_xfrmr_inst", "tag": "TR-101", "device_type": "Transformer"}],
            }
        elif premise_id == "CUST-003":
            premise_data = {
                "premise_id": "CUST-003",
                "service_type": "Underground",
                "is_medical_priority": False,
                "city": "Dayton",
                "state": "OH",
                "latitude": 39.7640,
                "longitude": -84.1809,
                "transformer_tag": "TR-102",
                "circuit_id": "FDR-01",
                "upstream_devices": [{"layer": "eo_power_xfrmr_inst", "tag": "TR-102", "device_type": "Transformer"}],
            }
        else:
            # Insufficient data response
            assessment = grounded_risk_engine.assess_risk(
                premise_lat=None, premise_lon=None, service_type=None,
                upstream_devices=None, storm_lat=None, storm_lon=None, storm_wind_radius_km=None
            )
            return JSONResponse(
                status_code=404,
                content={
                    "error": "Premise not found in active utility network registry.",
                    "assessment": assessment.to_dict(),
                }
            )

    # Find the nearest active storm
    nearest_storm = None
    min_dist = float("inf")
    p_lat = premise_data["latitude"]
    p_lon = premise_data["longitude"]

    for storm in state.storms.values():
        c_pos = storm.get("current_pos") or storm["path"][0]
        d = haversine_km(p_lat, p_lon, c_pos["lat"], c_pos["lon"])
        if d < min_dist:
            min_dist = d
            nearest_storm = storm

    s_lat = nearest_storm["current_pos"]["lat"] if nearest_storm else 37.25
    s_lon = nearest_storm["current_pos"]["lon"] if nearest_storm else -80.20
    s_radius = float(nearest_storm.get("radius_km", 35.0)) if nearest_storm else 35.0
    s_gust = float(nearest_storm.get("peak_gust_kmh", 80.0)) if nearest_storm else 80.0

    # 1. Honest Outage Risk Assessment
    risk_assessment = grounded_risk_engine.assess_risk(
        premise_lat=p_lat,
        premise_lon=p_lon,
        service_type=premise_data.get("service_type", "Overhead"),
        upstream_devices=premise_data.get("upstream_devices", []),
        storm_lat=s_lat,
        storm_lon=s_lon,
        storm_wind_radius_km=s_radius,
        storm_peak_gust_kmh=s_gust,
        historical_damage_count=len(state.historical_damage_points),
    )

    # 2. Labor-Grounded Restoration Assessment (ETR)
    # Check upstream devices
    upstream_chain = premise_data.get("upstream_devices", [])
    transformer_tag = premise_data.get("transformer_tag", "")
    if transformer_tag and not any(d.get("tag") == transformer_tag for d in upstream_chain):
        upstream_chain = [{"tag": transformer_tag, "device_type": "Distribution Transformer"}] + upstream_chain

    restoration_profile = labor_etr_engine.evaluate_premise_restoration(
        premise_id=premise_data["premise_id"],
        upstream_chain=upstream_chain,
        active_incidents=list(state.active_incidents.values()),
        crews_available=state.crews_available,
        storm_active=nearest_storm.get("is_playing", False) if nearest_storm else False,
        sustained_wind_mph=s_gust * 0.621371,
    )

    # 3. Personalized Preparation Actions
    is_med = premise_data.get("is_medical_priority", False)
    prep_actions = []
    if is_med:
        prep_actions.append("⚡ Medical Priority Alert: Verify backup oxygen/battery power systems are fully charged.")
        prep_actions.append("📞 Have emergency caregiver and regional utility priority contact numbers on hand.")
    prep_actions.append("🔋 Fully charge mobile phones, laptops, and portable emergency power banks.")
    prep_actions.append("🧊 Keep refrigerator and freezer doors closed to preserve food freshness for up to 48 hours.")
    prep_actions.append("🔦 Prepare battery-powered LED flashlights; avoid open-flame candles.")

    # 4. Alert Eligibility & Reason
    alert_eligibility = {
        "eligible": True,
        "consent_status": "Opted-in (SMS Priority Emergency Channel)",
        "priority_level": "Tier 1: Life Support Emergency" if is_med else "Tier 2: Standard Residential",
        "quiet_hours_exempt": is_med,
        "throttling_status": "Active (1 update per status transition to prevent notification fatigue)",
    }

    # 5. Recent notifications for this premise
    recent_notifs = [
        n for n in state.notifications
        if n["grid_id"] == premise_id or n["grid_id"] in transformer_tag or "CRITICAL" in n["title"]
    ][:5]

    return {
        "premise": {
            "premise_id": premise_data["premise_id"],
            "region": f"{premise_data.get('city', 'Roanoke')}, {premise_data.get('state', 'VA')}",
            "grid_zone": f"Circuit {premise_data.get('circuit_id', '0000027')}",
            "service_type": premise_data.get("service_type", "Overhead"),
            "is_medical_priority": is_med,
        },
        "power_status": {
            "status": restoration_profile.status,
            "has_active_outage": restoration_profile.has_active_outage,
            "summary": "Confirmed power outage" if restoration_profile.has_active_outage else (
                "At Risk - Severe Storm Approaching" if risk_assessment.risk_score >= 0.5 else "Normal Grid Service"
            ),
        },
        "risk_assessment": risk_assessment.to_dict(),
        "restoration": restoration_profile.to_dict(),
        "preparation_actions": prep_actions,
        "alert_eligibility": alert_eligibility,
        "recent_notifications": recent_notifs,
    }


# ── Mobile & Notification Endpoints ──────────────────────────────────────────

@app.get("/api/notifications")
def get_notifications():
    """List all notifications."""
    return state.notifications


@app.get("/api/notifications/poll")
@app.get("/api/alerts/poll")
def poll_notifications(since_id: int = 0):
    """
    Lightweight polling endpoint for Android app and mobile clients.
    Available under both /api/notifications/poll and /api/alerts/poll.
    """
    new_items = [n for n in state.notifications if n["id"] > since_id]
    return {
        "latest_id": state.notifications[0]["id"] if state.notifications else 0,
        "notifications": new_items,
        "count": len(new_items),
    }


@app.post("/api/notifications/test")
async def test_notification(payload: ManualAlert):
    """Manually blast a high-priority alert to test phones and public boards."""
    grid = state.grids.get(payload.grid_id)
    grid_name = grid["name"] if grid else payload.grid_id
    storm_name = "Storm Simulator"
    if payload.storm_id and payload.storm_id in state.storms:
        storm_name = state.storms[payload.storm_id]["name"]

    notif = state.add_notification(
        storm_name=storm_name,
        grid_id=payload.grid_id,
        grid_name=grid_name,
        alert_type="test_alert",
        title=f"⚡ ALERT: {grid_name} Threat Imminent",
        body=payload.message or f"Power Grid {grid_name} is predicted to get hit by {storm_name}. Please prepare immediately!",
        eta_minutes=25,
    )
    await broadcast_state([notif])
    return notif


# ── APK Download Endpoints ───────────────────────────────────────────────────

@app.get("/download-apk")
@app.get("/api/download/apk")
@app.get("/StormAlert.apk")
def download_apk():
    """Download the standalone Android APK."""
    for path in APK_PATHS:
        if path.is_file():
            return FileResponse(
                path=str(path),
                filename="StormAlert.apk",
                media_type="application/vnd.android.package-archive",
            )
    return HTMLResponse(
        """
        <html>
        <head><title>Storm Assistant APK</title></head>
        <body style="font-family:sans-serif; text-align:center; padding:50px; background:#0f172a; color:#f8fafc;">
          <h1>⚡ Storm Assistant Android APK</h1>
          <p>The APK file is being generated or was moved.</p>
        </body>
        </html>
        """,
        status_code=202,
    )


# ── WebSocket Endpoint ───────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state.subscribers.add(websocket)
    await websocket.send_json({
        "type": "state_update",
        "data_source": state.data_source,
        "storms": list(state.storms.values()),
        "grids": list(state.grids.values()),
        "notifications": state.notifications[:20],
        "new_alerts": [],
        "crews_available": state.crews_available,
        "access_conditions": state.access_conditions,
    })
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "recalculate":
                    new_notifs = state.recalculate()
                    await broadcast_state(new_notifs)
            except Exception:
                pass
    except WebSocketDisconnect:
        state.subscribers.discard(websocket)
    except Exception:
        state.subscribers.discard(websocket)


# ── Static UI Routes ─────────────────────────────────────────────────────────

@app.get("/operator")
def operator_view():
    return FileResponse(STATIC_DIR / "operator.html")


@app.get("/user")
def user_view():
    return FileResponse(STATIC_DIR / "user.html")


@app.get("/customer")
def customer_view():
    return FileResponse(STATIC_DIR / "customer.html")


@app.get("/")
def index():
    return RedirectResponse(url="/operator")
