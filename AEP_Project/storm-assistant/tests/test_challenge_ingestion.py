"""Unit tests for AEP HackOHI/O 2026 Challenge Dataset Ingestion Pipeline."""

from pathlib import Path
import pytest

from data.challenge.ingest import ChallengeDataIngestionPipeline, mercator_to_wgs84


def test_mercator_to_wgs84_reprojection():
    # Test known EPSG:3857 coordinates for Salem VA hospital area
    # -8917822.98, 4493825.75
    lon, lat = mercator_to_wgs84(-8917822.98, 4493825.75)
    assert -80.20 <= lon <= -80.05, f"Unexpected longitude: {lon}"
    assert 37.30 <= lat <= 37.45, f"Unexpected latitude: {lat}"


def test_challenge_pipeline_runs_and_verifies():
    pipeline = ChallengeDataIngestionPipeline()
    assert pipeline.verify_raw_files() is True

    # Test curated ingestion of Circuit 0000027
    data = pipeline.ingest_curated_grid(target_circuit="0000027", limit_premises=50)

    assert data["circuit_id"] == "0000027"
    assert "Roanoke / Salem" in data["region"]
    assert len(data["premises"]) > 0
    assert len(data["facilities"]) > 0

    # Verify medical priority customers are present and flagged
    med_premises = [p for p in data["premises"] if p["is_medical_priority"]]
    assert len(med_premises) >= 1

    # Verify upstream equipment hierarchy is linked
    sample_p = data["premises"][0]
    assert "upstream_devices" in sample_p
    assert len(sample_p["upstream_devices"]) >= 1

    # Verify anonymization: no raw personal data exposed in customer view
    cust_view = sample_p
    assert "name" not in cust_view
    assert "phone" not in cust_view
    assert "address_nu" not in cust_view
