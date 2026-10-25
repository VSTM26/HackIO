"""AEP Storm Assistant - Network-Dependent Labor Restoration Estimator.

Bridges the official AEP HackOHI/O 2026 labor workbook (`Install_Labor_HackOHIO.xlsx`)
and the upstream topological dependency graph (`matched_upstream.txt`).

Key Utility Principles:
1. Upstream Electrical Hierarchy:
   Power cannot reach a customer premise until ALL upstream protective devices,
   switchgear, line segments, and distribution transformers are repaired and closed.
2. Labor-Grounded CUs:
   Uses standard utility Compatible Units (CUs) for poles, transformers, crossarms,
   and protective cutouts, scaled by the official 4.5x Indirect Labor Multiplier (ILM).
3. Access & Terrain Adders:
   Confined backyard equipment access, off-road remote locations, and manual
   excavation add direct labor hours per AEP engineering guidelines.
4. Transparent Restoration Intervals:
   Presents earliest, most likely, and latest restoration bounds with clear
   distinction between confirmed operational facts and modeling assumptions.
"""

from __future__ import annotations

import datetime
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from data.challenge.labor_model import (
    LaborRestorationModel,
    RepairTask,
    RestorationEstimate,
    labor_model,
)


@dataclass
class NetworkIncident:
    """An active damage incident affecting a specific grid asset."""
    incident_id: str
    asset_id: str
    asset_type: str  # "transformer", "pole", "wire", "fuse", "recloser", "service_drop"
    damage_description: str
    cu_type: str
    quantity: int = 1
    access_modifiers: List[str] = field(default_factory=list)
    is_upstream: bool = False
    is_repaired: bool = False


@dataclass
class CustomerRestorationProfile:
    """Customer-facing restoration assessment with upstream dependency tracing."""
    premise_id: str
    status: str  # "normal", "at_risk", "outage_confirmed", "restored"
    has_active_outage: bool
    earliest_restoration: Optional[str]
    likely_restoration: Optional[str]
    latest_restoration: Optional[str]
    duration_hours_likely: float
    confidence: str
    upstream_dependencies_summary: str
    active_incidents: List[str]
    assumptions: List[str]
    missing_factors: List[str]
    labor_breakdown: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LaborGroundedETREngine:
    """Estimates restoration times grounded in labor standards and grid hierarchy."""

    def __init__(self, model: Optional[LaborRestorationModel] = None):
        self.model = model or labor_model

    def evaluate_premise_restoration(
        self,
        premise_id: str,
        upstream_chain: List[Dict[str, Any]],
        active_incidents: List[NetworkIncident],
        crews_available: int = 1,
        storm_active: bool = False,
        sustained_wind_mph: float = 0.0,
        sim_time_iso: Optional[str] = None,
    ) -> CustomerRestorationProfile:
        """Trace network dependencies and compute labor-grounded restoration bounds."""
        # 1. Identify all asset IDs on this customer's supply path
        # Upstream chain contains: transformer -> isolating devices -> reclosers -> breaker
        upstream_tags: Set[str] = set()
        upstream_ids: Set[str] = set()
        for dev in upstream_chain:
            tag = dev.get("tag") or dev.get("location_n")
            dev_id = dev.get("device_id") or dev.get("id")
            if tag:
                upstream_tags.add(str(tag).strip())
            if dev_id:
                upstream_ids.add(str(dev_id).strip())

        # 2. Filter incidents that interrupt this customer's power
        relevant_incidents: List[NetworkIncident] = []
        is_direct_premise_damage = False

        for inc in active_incidents:
            if inc.is_repaired:
                continue

            # Check if incident is on customer's direct premise/service drop
            if inc.asset_id == premise_id:
                relevant_incidents.append(inc)
                is_direct_premise_damage = True
            # Check if incident is on customer's upstream transformer or protective devices
            elif inc.asset_id in upstream_tags or inc.asset_id in upstream_ids:
                inc.is_upstream = True
                relevant_incidents.append(inc)

        has_outage = len(relevant_incidents) > 0
        now = datetime.datetime.fromisoformat(sim_time_iso) if sim_time_iso else datetime.datetime.now()

        if not has_outage:
            # No active outage recorded
            return CustomerRestorationProfile(
                premise_id=premise_id,
                status="normal",
                has_active_outage=False,
                earliest_restoration=None,
                likely_restoration=None,
                latest_restoration=None,
                duration_hours_likely=0.0,
                confidence="high",
                upstream_dependencies_summary="All upstream equipment (fuses, reclosers, circuit breakers) energized and operational.",
                active_incidents=[],
                assumptions=["No unverified faults reported by smart meters or automated sensors."],
                missing_factors=[],
                labor_breakdown={},
            )

        # 3. Convert relevant incidents into labor RepairTasks
        tasks: List[RepairTask] = []
        for inc in relevant_incidents:
            tasks.append(
                RepairTask(
                    task_id=inc.incident_id,
                    cu_type=inc.cu_type,
                    description=inc.damage_description,
                    quantity=inc.quantity,
                    access_modifiers=inc.access_modifiers,
                    equipment_tag=inc.asset_id,
                    is_upstream=inc.is_upstream,
                )
            )

        # 4. Calculate labor estimate
        est: RestorationEstimate = self.model.estimate_restoration(
            tasks=tasks,
            crews_available=crews_available,
            storm_active=storm_active,
            sustained_wind_mph=sustained_wind_mph,
        )

        earliest_dt = now + datetime.timedelta(hours=est.earliest_hours)
        likely_dt = now + datetime.timedelta(hours=est.likely_hours)
        latest_dt = now + datetime.timedelta(hours=est.latest_hours)

        fmt = "%b %d, %I:%M %p"
        earliest_str = earliest_dt.strftime(fmt)
        likely_str = likely_dt.strftime(fmt)
        latest_str = latest_dt.strftime(fmt)

        upstream_count = sum(1 for inc in relevant_incidents if inc.is_upstream)
        if upstream_count > 0:
            up_summary = f"{upstream_count} upstream distribution asset(s) faulted on supply path. Must be repaired and energized before customer service can be safely restored."
        else:
            up_summary = "Service drop / meter attachment fault at local premise."

        return CustomerRestorationProfile(
            premise_id=premise_id,
            status="outage_confirmed",
            has_active_outage=True,
            earliest_restoration=earliest_str,
            likely_restoration=likely_str,
            latest_restoration=latest_str,
            duration_hours_likely=round(est.likely_hours, 1),
            confidence=est.confidence,
            upstream_dependencies_summary=up_summary,
            active_incidents=est.contributing_damage,
            assumptions=est.assumptions,
            missing_factors=est.missing_factors,
            labor_breakdown=est.to_dict(),
        )


# Global singleton instance
labor_etr_engine = LaborGroundedETREngine()
