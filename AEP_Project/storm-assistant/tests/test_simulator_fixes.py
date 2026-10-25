"""Unit tests for Simulator Server bug fixes and Android compatibility."""

import pytest
from apps.simulator.server import (
    SimulationState,
    StormCreate,
    GridCreate,
    app,
)
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    return TestClient(app)


def test_android_polling_alias(client):
    res1 = client.get("/api/notifications/poll?since_id=0")
    res2 = client.get("/api/alerts/poll?since_id=0")
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert "notifications" in res2.json()
    assert "count" in res2.json()


def test_customer_portal_routes(client):
    res_ui = client.get("/customer")
    assert res_ui.status_code == 200
    assert "text/html" in res_ui.headers["content-type"]

    res_premises = client.get("/api/customer/premises")
    assert res_premises.status_code == 200
    assert len(res_premises.json()) >= 1

    sample_id = res_premises.json()[0]["premise_id"]
    res_prof = client.get(f"/api/customer/profile?premise_id={sample_id}")
    assert res_prof.status_code == 200
    prof = res_prof.json()
    assert "power_status" in prof
    assert "risk_assessment" in prof
    assert "restoration" in prof


def test_multi_storm_worst_case_aggregation():
    sim = SimulationState()
    # Add two storms: one distant, one directly impacting TR-101
    sim.storms = {
        "far_storm": {
            "id": "far_storm",
            "name": "Far Storm",
            "radius_km": 20.0,
            "speed_kmh": 40.0,
            "peak_gust_kmh": 60.0,
            "path": [{"lat": 35.0, "lon": -84.0}],
            "progress": 0.0,
            "auto_notify": False,
        },
        "near_storm": {
            "id": "near_storm",
            "name": "Near Storm",
            "radius_km": 30.0,
            "speed_kmh": 40.0,
            "peak_gust_kmh": 85.0,
            "path": [{"lat": 39.7621, "lon": -84.1848}],  # Exact TR-101 location
            "progress": 0.0,
            "auto_notify": False,
        },
    }
    sim.recalculate()
    tr101 = sim.grids.get("TR-101")
    assert tr101 is not None
    # Nearest storm should win threat_level direct_hit
    assert tr101["threat_level"] == "direct_hit"
    assert tr101["distance_km"] <= 1.0


def test_input_validation_coordinates(client):
    # Invalid latitude > 90
    bad_payload = {
        "name": "Illegal Storm",
        "radius_km": 35.0,
        "speed_kmh": 45.0,
        "peak_gust_kmh": 90.0,
        "path": [{"lat": 195.0, "lon": -84.0}],
    }
    res = client.post("/api/storms", json=bad_payload)
    # FastApi/Pydantic validation should reject or raise
    # Our Pydantic validator validates lat/lon in GridCreate and fields in StormCreate
    bad_grid = {
        "id": "BAD-GRID",
        "name": "Out of Bounds Grid",
        "type": "substation",
        "lat": 120.0,  # Invalid
        "lon": -84.0,
    }
    res_grid = client.post("/api/grids", json=bad_grid)
    assert res_grid.status_code == 422  # Unprocessable Entity
