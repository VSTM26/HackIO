"""Unit tests for Labor-Grounded Restoration Model and ETR Engine."""

import pytest
from data.challenge.labor_model import labor_model, RepairTask, DEFAULT_ILM
from analytics.predictive.labor_etr import labor_etr_engine, NetworkIncident


def test_labor_model_cu_hours_and_ilm_multiplier():
    assert labor_model.ilm == 4.5

    # Blown fuse cutout: 0.256 install + 0.128 remove = 0.384 direct CU hrs
    fuse_task = RepairTask(
        task_id="T1", cu_type="fuse_cutout", description="Fuse replacement", quantity=1
    )
    est = labor_model.estimate_restoration([fuse_task], crews_available=1)

    assert est.direct_cu_hours == pytest.approx(0.384, rel=1e-2)
    # Direct * 4.5 = 1.728 labor hours
    assert est.total_labor_hours == pytest.approx(0.384 * DEFAULT_ILM, rel=1e-2)
    assert est.active_crews == 1
    assert est.confidence == "high"


def test_access_adders_applied():
    # 50kVA transformer with backyard confined access adder (0.5h)
    xfmr_task = RepairTask(
        task_id="T2",
        cu_type="transformer_50kva",
        description="50kVA replacement",
        quantity=1,
        access_modifiers=["backyard"],
    )
    est = labor_model.estimate_restoration([xfmr_task], crews_available=1)

    assert est.access_adder_hours == 0.5
    # Total labor includes both CU and access adder scaled by ILM
    expected_labor = (est.direct_cu_hours + 0.5) * DEFAULT_ILM
    assert est.total_labor_hours == pytest.approx(expected_labor, rel=1e-2)


def test_labor_etr_upstream_dependency_resolution():
    chain = [
        {"layer": "eo_power_xfrmr_inst", "device_id": "107301290", "tag": "37800368000008"},
        {"layer": "eo_isolating_eqpt_inst", "device_id": "106806731", "tag": "37800343D00129"},
        {"layer": "eo_circuit", "device_id": "157965269", "tag": "0000027"},
    ]

    # Incident on upstream transformer
    inc = NetworkIncident(
        incident_id="INC-01",
        asset_id="37800368000008",
        asset_type="transformer",
        damage_description="Damaged 50kVA transformer",
        cu_type="transformer_50kva",
        quantity=1,
    )

    profile = labor_etr_engine.evaluate_premise_restoration(
        premise_id="PREM-001",
        upstream_chain=chain,
        active_incidents=[inc],
        crews_available=1,
    )

    assert profile.has_active_outage is True
    assert profile.status == "outage_confirmed"
    assert "upstream distribution asset(s) faulted" in profile.upstream_dependencies_summary
    assert profile.duration_hours_likely > 0.0
    assert profile.earliest_restoration is not None
    assert profile.likely_restoration is not None
    assert profile.latest_restoration is not None
