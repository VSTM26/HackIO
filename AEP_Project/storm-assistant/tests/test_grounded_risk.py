"""Unit tests for Grounded Explainable Outage Risk Engine."""

import pytest
from analytics.predictive.grounded_risk import grounded_risk_engine, haversine_distance_km


def test_haversine_distance():
    # Columbus (39.9612, -82.9988) to Dayton (39.7589, -84.1916) is approx 105-115 km
    d = haversine_distance_km(39.9612, -82.9988, 39.7589, -84.1916)
    assert 100.0 <= d <= 120.0


def test_overhead_vs_underground_risk_differential():
    # Direct hit scenario (distance 5 km, radius 35 km, 90 km/h gusts)
    overhead = grounded_risk_engine.assess_risk(
        premise_lat=37.25, premise_lon=-80.20,
        service_type="Overhead",
        upstream_devices=["fuse1", "recloser1"],
        storm_lat=37.26, storm_lon=-80.19,
        storm_wind_radius_km=35.0,
        storm_peak_gust_kmh=90.0,
    )
    underground = grounded_risk_engine.assess_risk(
        premise_lat=37.25, premise_lon=-80.20,
        service_type="Underground",
        upstream_devices=["fuse1", "recloser1"],
        storm_lat=37.26, storm_lon=-80.19,
        storm_wind_radius_km=35.0,
        storm_peak_gust_kmh=90.0,
    )

    # Overhead must have substantially higher risk than underground
    assert overhead.risk_score > underground.risk_score
    assert overhead.risk_band in ("Elevated", "Severe")
    assert underground.risk_band in ("Low", "Moderate")
    assert overhead.confidence == "High"
    assert "Overhead distribution service is exposed" in overhead.contributing_factors[2]
    assert "Underground electrical service shields" in underground.contributing_factors[2]


def test_distance_decay_and_confidence():
    # Peripheral watch zone (distance 50 km, radius 35 km -> within 2.2x radius)
    watch_res = grounded_risk_engine.assess_risk(
        premise_lat=37.25, premise_lon=-80.20,
        service_type="Overhead",
        upstream_devices=[],
        storm_lat=37.70, storm_lon=-80.20,
        storm_wind_radius_km=35.0,
        storm_peak_gust_kmh=80.0,
    )
    assert watch_res.confidence == "Medium"
    assert watch_res.in_direct_path is False

    # Outside storm envelope (> 2.2x radius)
    far_res = grounded_risk_engine.assess_risk(
        premise_lat=37.25, premise_lon=-80.20,
        service_type="Overhead",
        upstream_devices=[],
        storm_lat=39.00, storm_lon=-80.20,
        storm_wind_radius_km=35.0,
        storm_peak_gust_kmh=80.0,
    )
    assert far_res.confidence == "Low"
    assert far_res.risk_score <= 0.10


def test_insufficient_data_fallback():
    # If coordinates are missing, returns explicit insufficient-data fallback
    res = grounded_risk_engine.assess_risk(
        premise_lat=None, premise_lon=None,
        service_type="Overhead",
        upstream_devices=[],
        storm_lat=37.25, storm_lon=-80.20,
        storm_wind_radius_km=35.0,
    )
    assert res.is_sufficient_data is False
    assert res.confidence == "Insufficient Data"
    assert res.error_message is not None
