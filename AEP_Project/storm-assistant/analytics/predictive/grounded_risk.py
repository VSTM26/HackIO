"""AEP Storm Assistant - Explainable Grounded Outage Risk Engine.

Methodology & Honesty Standard:
--------------------------------
This model calculates outage vulnerability using physical heuristics and verified
challenge dataset attributes. It explicitly separates RISK MAGNITUDE from CONFIDENCE
and reports clear assumptions, contributing factors, and sensitivity triggers.

Signals:
1. Storm Proximity & Wind Radius:
   - d <= radius: Direct impact envelope
   - d <= 2.2 * radius: Peripheral watch envelope
   - d > 2.2 * radius: Outside storm hazard envelope
2. Peak Gust vs Infrastructure Thresholds:
   - < 35 mph (56 km/h): Baseline tree sway, low fault probability
   - 35 - 50 mph (56 - 80 km/h): Large limb break hazard, moderate fault probability
   - > 50 mph (80+ km/h): Whole tree uprooting, structural pole & conductor stress
3. Construction Type (Customer_Clip):
   - Overhead: Full exposure to falling limbs and flying debris
   - Underground: High physical resilience (~85% reduction in storm-induced faults)
4. Upstream Dependency Depth (matched_upstream.txt):
   - Number of upstream series devices (fuses, reclosers, circuit breakers)
5. Explicit Insufficient-Data Fallback:
   - If premise is unrecognized or coordinates are missing, returns an explicit
     `insufficient_data` response instead of returning a misleading default score.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in kilometers."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


@dataclass
class GroundedRiskAssessment:
    """Honest, customer-explainable risk assessment result."""
    is_sufficient_data: bool
    risk_score: float  # 0.00 to 0.99
    risk_band: str     # "Low", "Moderate", "Elevated", "Severe"
    confidence: str    # "High", "Medium", "Low", "Insufficient Data"
    distance_to_storm_km: Optional[float]
    storm_radius_km: Optional[float]
    in_direct_path: bool
    service_type: str  # "Overhead", "Underground", or "Unknown"
    upstream_device_count: int
    contributing_factors: List[str]
    assumptions: List[str]
    what_could_change: List[str]
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GroundedRiskEngine:
    """Calculates defensible, explainable outage risk."""

    def assess_risk(
        self,
        premise_lat: Optional[float],
        premise_lon: Optional[float],
        service_type: Optional[str],
        upstream_devices: Optional[List[Any]],
        storm_lat: Optional[float],
        storm_lon: Optional[float],
        storm_wind_radius_km: Optional[float],
        storm_peak_gust_kmh: Optional[float] = 80.0,
        historical_damage_count: int = 0,
    ) -> GroundedRiskAssessment:
        """Evaluate physical risk factors with explicit uncertainty."""
        # 1. Validation check for sufficient data
        if premise_lat is None or premise_lon is None:
            return GroundedRiskAssessment(
                is_sufficient_data=False,
                risk_score=0.0,
                risk_band="Unknown",
                confidence="Insufficient Data",
                distance_to_storm_km=None,
                storm_radius_km=storm_wind_radius_km,
                in_direct_path=False,
                service_type="Unknown",
                upstream_device_count=0,
                contributing_factors=[],
                assumptions=["Location coordinates are missing from the system record."],
                what_could_change=["Providing verified premise coordinates enables storm proximity calculation."],
                error_message="Cannot compute risk assessment: premise coordinates missing.",
            )

        if storm_lat is None or storm_lon is None or storm_wind_radius_km is None:
            return GroundedRiskAssessment(
                is_sufficient_data=False,
                risk_score=0.0,
                risk_band="Unknown",
                confidence="Insufficient Data",
                distance_to_storm_km=None,
                storm_radius_km=None,
                in_direct_path=False,
                service_type=service_type or "Unknown",
                upstream_device_count=len(upstream_devices or []),
                contributing_factors=[],
                assumptions=["No active or forecast storm track data available."],
                what_could_change=["Risk assessment will run once meteorologist storm tracking data is received."],
                error_message="No active storm trajectory loaded.",
            )

        # 2. Geospatial proximity
        dist_km = haversine_distance_km(premise_lat, premise_lon, storm_lat, storm_lon)
        radius_km = max(5.0, float(storm_wind_radius_km))
        gust_kmh = max(20.0, float(storm_peak_gust_kmh or 80.0))
        gust_mph = gust_kmh * 0.621371

        stype = (service_type or "Overhead").capitalize()
        is_underground = "underground" in stype.lower()
        upstream_count = len(upstream_devices or [])

        factors: List[str] = []
        assumptions: List[str] = []
        what_could_change: List[str] = []

        # 3. Physical proximity factor
        in_direct_hit = dist_km <= radius_km
        in_watch_zone = dist_km <= (2.2 * radius_km)

        if in_direct_hit:
            dist_factor = 1.0
            factors.append(f"Premise is inside the active wind radius ({dist_km:.1f} km from center, radius is {radius_km:.1f} km)")
        elif in_watch_zone:
            # Linear decay from 1.0 at radius down to 0.1 at 2.2 * radius
            excess = dist_km - radius_km
            max_excess = 1.2 * radius_km
            dist_factor = max(0.1, 1.0 - 0.75 * (excess / max_excess))
            factors.append(f"Premise is in the peripheral storm watch zone ({dist_km:.1f} km from storm center)")
        else:
            dist_factor = 0.02
            factors.append(f"Premise is outside immediate storm envelope ({dist_km:.1f} km away)")

        # 4. Wind intensity factor
        if gust_mph < 35.0:
            wind_factor = 0.20
            factors.append(f"Forecast wind gusts ({gust_mph:.0f} mph) are below critical tree-fall threshold (35 mph)")
        elif gust_mph < 50.0:
            wind_factor = 0.55
            factors.append(f"Moderate wind gusts ({gust_mph:.0f} mph) may cause isolated limb falls on lines")
        elif gust_mph < 65.0:
            wind_factor = 0.85
            factors.append(f"Severe wind gusts ({gust_mph:.0f} mph) capable of breaking tree branches and utility poles")
        else:
            wind_factor = 1.0
            factors.append(f"Violent storm gusts ({gust_mph:.0f} mph) likely to cause widespread structural tree and line damage")

        # 5. Construction type resilience
        if is_underground:
            construction_resilience = 0.15  # 85% protection
            factors.append("Underground electrical service shields equipment from falling branches and high winds")
            assumptions.append("Assumes underground pad-mount equipment is not flooded by localized standing water")
        else:
            construction_resilience = 1.0
            factors.append("Overhead distribution service is exposed to surrounding tree canopy and flying debris")
            assumptions.append("Regional tree canopy density assumed near distribution right-of-way")

        # 6. Upstream equipment depth multiplier
        # Each upstream protective device represents a potential tripping point
        depth_multiplier = 1.0 + min(0.35, upstream_count * 0.05)
        if upstream_count > 0:
            factors.append(f"Power flows through {upstream_count} upstream protective devices (reclosers/fuses) on the supply path")

        # 7. Calculate composite risk score
        raw_risk = dist_factor * wind_factor * construction_resilience * depth_multiplier
        risk_score = round(max(0.01, min(0.95, raw_risk)), 2)

        # Determine Risk Band
        if risk_score < 0.25:
            risk_band = "Low"
        elif risk_score < 0.50:
            risk_band = "Moderate"
        elif risk_score < 0.75:
            risk_band = "Elevated"
        else:
            risk_band = "Severe"

        # 8. Determine Confidence
        # Proximity confidence: higher when storm is close and track is clear
        if in_direct_hit and gust_mph >= 40.0:
            confidence = "High"
        elif in_watch_zone:
            confidence = "Medium"
        else:
            confidence = "Low"

        # Sensitivity / What could change
        if dist_km > radius_km:
            what_could_change.append(
                f"A storm track shift of {dist_km - radius_km:.0f} km toward this area would elevate risk directly to High/Severe."
            )
        if gust_mph < 50.0:
            what_could_change.append(
                "Peak gust increases above 50 mph would trigger elevated limb-break and pole stress risk."
            )
        what_could_change.append(
            "Rapid clearing or weakening of storm center as it moves inland will reduce outage likelihood."
        )

        return GroundedRiskAssessment(
            is_sufficient_data=True,
            risk_score=risk_score,
            risk_band=risk_band,
            confidence=confidence,
            distance_to_storm_km=round(dist_km, 1),
            storm_radius_km=round(radius_km, 1),
            in_direct_path=in_direct_hit,
            service_type=stype,
            upstream_device_count=upstream_count,
            contributing_factors=factors,
            assumptions=assumptions,
            what_could_change=what_could_change,
        )


# Global singleton instance
grounded_risk_engine = GroundedRiskEngine()
