"""AEP Storm Assistant - Labor-Grounded Restoration Model.

Grounded directly in the official AEP HackOHI/O 2026 challenge workbook:
`Install_Labor_HackOHIO.xlsx`.

Key Principles:
1. Direct Labor Hours: Standard Compatible Units (CUs) for pole replacement,
   transformer installation/removal, crossarms, brackets, fuse cutouts, switches,
   reclosers, and conductors.
2. Indirect Labor Multiplier (ILM = 4.5): Explicitly required by AEP to account
   for drive time, tailboard safety discussions, job-site staging, hazard clearance,
   and switching protocols.
3. Access Adders: Site complexity modifiers (backyard access, off-road terrain,
   manual excavation / hand-dig, rock drilling).
4. Phased Restoration Sequencing:
   - Phase 1: Dispatch, travel, damage assessment & site hazard mitigation.
   - Phase 2: Physical asset replacement / repair (CU hours * ILM).
   - Phase 3: Switching, feeder re-energization, and meter verification.
5. Crew Constraints & Dependency Chains: Parallel vs sequential repair
   allocation across available line crews.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# --- Baseline CU Direct Labor Constants (from Install_Labor_HackOHIO.xlsx) ---

# Indirect Labor Multiplier (ILM)
# "The ILM should be multiplied times any labor hours to take into account
# drive time, safety discussion time, set up time, etc."
DEFAULT_ILM: float = 4.5

# Direct labor hours (install + removal) from Sheet: "Labor time material related"
CU_LABOR_HOURS: Dict[str, Dict[str, float]] = {
    # Poles: Small (25-35ft), Medium (40-55ft), Large (60ft+)
    "pole_small": {"install": 1.942, "remove": 0.764, "total": 2.706},
    "pole_medium": {"install": 2.503, "remove": 0.927, "total": 3.430},
    "pole_large": {"install": 3.368, "remove": 1.153, "total": 4.521},
    "pole_straighten": {"install": 0.544, "remove": 0.0, "total": 0.544},

    # Transformers by kVA (install + removal)
    "transformer_10kva": {"install": 1.189, "remove": 0.808, "total": 1.997},
    "transformer_25kva": {"install": 1.188, "remove": 0.806, "total": 1.994},
    "transformer_50kva": {"install": 1.245, "remove": 0.891, "total": 2.136},
    "transformer_100kva": {"install": 1.280, "remove": 0.944, "total": 2.224},
    "transformer_167kva": {"install": 1.280, "remove": 0.944, "total": 2.224},

    # Structural hardware
    "crossarm": {"install": 0.374, "remove": 0.212, "total": 0.586},
    "bracket": {"install": 0.617, "remove": 0.254, "total": 0.871},
    "anchor": {"install": 0.397, "remove": 0.119, "total": 0.516},
    "guy_wire": {"install": 0.367, "remove": 0.162, "total": 0.529},
    "insulator": {"install": 0.049, "remove": 0.039, "total": 0.088},

    # Protective and switching devices
    "fuse_cutout": {"install": 0.256, "remove": 0.128, "total": 0.384},
    "switch": {"install": 1.758, "remove": 1.010, "total": 2.768},
    "recloser": {"install": 0.573, "remove": 0.525, "total": 1.098},

    # Conductors & service connections
    "wire_primary_span": {"install": 1.693, "remove": 0.480, "total": 2.173},
    "wire_secondary_span": {"install": 0.233, "remove": 0.127, "total": 0.360},
    "service_attachment": {"install": 1.693, "remove": 0.480, "total": 2.173},
    "equipment_lead": {"install": 0.650, "remove": 0.206, "total": 0.856},
    "connector_lug": {"install": 0.215, "remove": 0.045, "total": 0.260},
}

# Access adders from Sheet: "Labor only work"
ACCESS_ADDERS: Dict[str, Dict[str, Any]] = {
    "backyard": {
        "name": "Backyard / Confined Property Access",
        "hours": 0.5,
        "description": "Restricted equipment access requiring manual material handling",
    },
    "off_road": {
        "name": "Off-Road / Track Access",
        "hours": 0.5,
        "description": "Non-standard access route requiring specialized tracked vehicles",
    },
    "remote": {
        "name": "Remote Site Adder",
        "hours": 1.312,
        "description": "Extended travel and staging over difficult rural or mountainous terrain",
    },
    "site_complexity": {
        "name": "Site Complexity Adder",
        "hours": 0.5,
        "description": "Physical site hazards or multiple utility crossings",
    },
    "hand_dig": {
        "name": "Manual Excavation (Hand Dig)",
        "hours": 1.5,  # per cubic foot, typical pole hole = 2 cu ft manual trim
        "description": "Manual excavation required near underground utilities",
    },
    "rock_hole": {
        "name": "Difficult Excavation (Rock Hole)",
        "hours": 4.0,  # per cubic foot, typical rock drill = 2 cu ft
        "description": "Subsurface rock requiring pneumatic drilling / blast hammer",
    },
}

# Phase timing buffers (in hours)
DEFAULT_DISPATCH_TRAVEL_HOURS: float = 0.5
DEFAULT_SAFETY_ASSESSMENT_HOURS: float = 0.5
DEFAULT_SWITCHING_VERIFICATION_HOURS: float = 0.25


@dataclass
class RepairTask:
    """A discrete repair task derived from damage assessment."""
    task_id: str
    cu_type: str
    description: str
    quantity: int = 1
    access_modifiers: List[str] = field(default_factory=list)
    equipment_tag: Optional[str] = None
    is_upstream: bool = False


@dataclass
class RestorationEstimate:
    """Transparent labor-grounded restoration estimate with breakdown."""
    earliest_hours: float
    likely_hours: float
    latest_hours: float
    direct_cu_hours: float
    access_adder_hours: float
    ilm_multiplier: float
    total_labor_hours: float
    active_crews: int
    phases: Dict[str, float]
    assumptions: List[str]
    missing_factors: List[str]
    confidence: str  # "high", "medium", "low"
    contributing_damage: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "earliest_hours": round(self.earliest_hours, 2),
            "likely_hours": round(self.likely_hours, 2),
            "latest_hours": round(self.latest_hours, 2),
            "direct_cu_hours": round(self.direct_cu_hours, 2),
            "access_adder_hours": round(self.access_adder_hours, 2),
            "ilm_multiplier": self.ilm_multiplier,
            "total_labor_hours": round(self.total_labor_hours, 2),
            "active_crews": self.active_crews,
            "phases": {k: round(v, 2) for k, v in self.phases.items()},
            "assumptions": self.assumptions,
            "missing_factors": self.missing_factors,
            "confidence": self.confidence,
            "contributing_damage": self.contributing_damage,
        }


class LaborRestorationModel:
    """Restoration model implementing AEP standard labor unit calculations."""

    def __init__(self, excel_path: Optional[str] = None):
        self.ilm = DEFAULT_ILM
        self.cu_hours = dict(CU_LABOR_HOURS)
        self.access_adders = dict(ACCESS_ADDERS)

        if excel_path and os.path.exists(excel_path):
            self._load_from_excel(excel_path)

    def _load_from_excel(self, path: str) -> None:
        """Optionally override defaults from official excel workbook."""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, data_only=True)
            if "Indirect Labor Multiplier" in wb.sheetnames:
                ws = wb["Indirect Labor Multiplier"]
                ilm_val = ws.cell(1, 2).value
                if isinstance(ilm_val, (int, float)):
                    self.ilm = float(ilm_val)
        except Exception:
            # Fall back safely to verified baseline constants
            pass

    def estimate_restoration(
        self,
        tasks: List[RepairTask],
        access_conditions: Optional[List[str]] = None,
        crews_available: int = 1,
        storm_active: bool = False,
        sustained_wind_mph: float = 0.0,
        historical_damage_count: int = 0,
    ) -> RestorationEstimate:
        """Calculate labor-grounded restoration estimate based on work items."""
        if crews_available < 1:
            crews_available = 1

        access_list = list(access_conditions or [])
        assumptions: List[str] = [
            f"Indirect Labor Multiplier (ILM) of {self.ilm}x applied for travel, staging, and tailboard safety protocols.",
            f"Restoration allocated across {crews_available} active line crew(s).",
        ]
        missing_factors: List[str] = []
        damage_descriptions: List[str] = []

        if not tasks:
            # Insufficient damage inspection information
            assumptions.append("No verified damage tickets recorded. Pending field crew patrol.")
            missing_factors.append("Exact physical damage type unconfirmed (field damage assessment pending)")
            return RestorationEstimate(
                earliest_hours=1.5,
                likely_hours=3.0,
                latest_hours=6.0,
                direct_cu_hours=0.5,
                access_adder_hours=0.0,
                ilm_multiplier=self.ilm,
                total_labor_hours=0.5 * self.ilm,
                active_crews=crews_available,
                phases={"patrol_and_assess": 1.0, "switching_isolation": 0.5, "restoration": 1.5},
                assumptions=assumptions,
                missing_factors=missing_factors,
                confidence="low",
                contributing_damage=["General storm patrol pending field assessment"],
            )

        # 1. Calculate direct CU labor hours
        total_direct_cu = 0.0
        for task in tasks:
            cu_info = self.cu_hours.get(task.cu_type)
            if cu_info:
                task_direct = cu_info["total"] * task.quantity
                total_direct_cu += task_direct
                tag = f" ({task.equipment_tag})" if task.equipment_tag else ""
                upstream_str = " [Upstream Grid]" if task.is_upstream else ""
                damage_descriptions.append(
                    f"{task.quantity}x {task.description}{tag}{upstream_str} ({round(task_direct, 2)} direct CU hrs)"
                )
            else:
                # Default generic task if unmapped
                total_direct_cu += 1.0 * task.quantity
                damage_descriptions.append(f"{task.quantity}x {task.description} (1.0h direct estimate)")

            # Task-specific access modifiers
            for m in task.access_modifiers:
                if m not in access_list:
                    access_list.append(m)

        # 2. Calculate access adders
        total_access_hours = 0.0
        for modifier in access_list:
            adder = self.access_adders.get(modifier)
            if adder:
                adder_h = float(adder["hours"])
                total_access_hours += adder_h
                assumptions.append(f"Site condition adder '{adder['name']}': +{adder_h} direct hours.")

        # 3. Apply Indirect Labor Multiplier
        subtotal_direct = total_direct_cu + total_access_hours
        total_labor_hours = subtotal_direct * self.ilm

        # 4. Phased scheduling under crew constraints
        # Multiple crews provide diminishing marginal returns due to site coordination
        crew_efficiency = 1.0 if crews_available == 1 else (1.0 + 0.8 * (crews_available - 1))
        field_work_hours = total_labor_hours / crew_efficiency

        # Weather / storm safety hold adder
        safety_delay = 0.0
        if storm_active and sustained_wind_mph >= 35.0:
            safety_delay = 1.5
            assumptions.append(
                f"Bucket truck elevation halted due to high winds ({sustained_wind_mph:.0f} mph >= 35 mph threshold). +1.5h weather delay."
            )
        elif storm_active:
            safety_delay = 0.5
            assumptions.append("Minor weather hold for active lightning / downpours. +0.5h precaution delay.")

        travel_assess_hours = DEFAULT_DISPATCH_TRAVEL_HOURS + DEFAULT_SAFETY_ASSESSMENT_HOURS + safety_delay
        switching_hours = DEFAULT_SWITCHING_VERIFICATION_HOURS

        likely_hours = travel_assess_hours + field_work_hours + switching_hours
        earliest_hours = max(0.5, likely_hours * 0.75)
        latest_hours = likely_hours * 1.5

        # Missing factors & confidence
        if storm_active:
            missing_factors.append("Storm trajectory may cause additional tree falls or delay crew travel")
        if not access_list:
            missing_factors.append("Subsurface soil conditions and property access gates uninspected")
        if historical_damage_count > 5:
            assumptions.append(f"Area has {historical_damage_count} regional damage tickets competing for crew dispatch.")

        confidence = "high" if len(tasks) >= 1 and not storm_active else ("medium" if len(tasks) >= 1 else "low")

        return RestorationEstimate(
            earliest_hours=earliest_hours,
            likely_hours=likely_hours,
            latest_hours=latest_hours,
            direct_cu_hours=total_direct_cu,
            access_adder_hours=total_access_hours,
            ilm_multiplier=self.ilm,
            total_labor_hours=total_labor_hours,
            active_crews=crews_available,
            phases={
                "travel_and_safety_tailboard": travel_assess_hours,
                "asset_replacement_and_labor": field_work_hours,
                "switching_and_energization": switching_hours,
            },
            assumptions=assumptions,
            missing_factors=missing_factors,
            confidence=confidence,
            contributing_damage=damage_descriptions,
        )


# Global singleton instance
labor_model = LaborRestorationModel()
