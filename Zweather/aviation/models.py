"""
Aviation data models for Zedd Weather.
Aircraft profiles, runway conditions, and flight risk assessment.
"""
from dataclasses import dataclass, field
from enum import Enum


class AircraftType(Enum):
    LIGHT_AIRCRAFT = "light_aircraft"
    COMMERCIAL_JET = "commercial_jet"
    REGIONAL_TURBOPROP = "regional_turboprop"
    BUSINESS_JET = "business_jet"
    HELICOPTER = "helicopter"
    MILITARY = "military"
    GENERAL = "general"


class OperationType(Enum):
    TAKEOFF = "takeoff"
    LANDING = "landing"
    EN_ROUTE = "en_route"
    GROUND_HANDLING = "ground_handling"
    GENERAL = "general"


@dataclass
class AircraftProfile:
    name: str
    aircraft_type: AircraftType
    max_crosswind_ms: float = 10.0
    max_tailwind_ms: float = 5.0
    max_gust_ms: float = 15.0
    min_visibility_m: float = 800.0
    min_ceiling_ft: float = 500.0
    max_icing_intensity: str = "moderate"
    wind_shear_tolerance_ms: float = 7.5
    constraints: dict = field(default_factory=dict)


AIRCRAFT_PROFILES: dict[str, AircraftProfile] = {
    "light_aircraft": AircraftProfile(
        name="Light Aircraft (Cessna 172)",
        aircraft_type=AircraftType.LIGHT_AIRCRAFT,
        max_crosswind_ms=7.0,
        max_tailwind_ms=3.0,
        max_gust_ms=10.0,
        min_visibility_m=1600.0,
        min_ceiling_ft=800.0,
        max_icing_intensity="light",
        constraints={"pilot_skill_factor": 1.0},
    ),
    "commercial_jet": AircraftProfile(
        name="Commercial Jet (B737/A320)",
        aircraft_type=AircraftType.COMMERCIAL_JET,
        max_crosswind_ms=12.0,
        max_tailwind_ms=5.0,
        max_gust_ms=20.0,
        min_visibility_m=400.0,
        min_ceiling_ft=200.0,
        max_icing_intensity="moderate",
        constraints={"cat_iii_autoland": True},
    ),
    "regional_turboprop": AircraftProfile(
        name="Regional Turboprop (ATR 72)",
        aircraft_type=AircraftType.REGIONAL_TURBOPROP,
        max_crosswind_ms=9.0,
        max_tailwind_ms=4.0,
        max_gust_ms=14.0,
        min_visibility_m=1200.0,
        min_ceiling_ft=600.0,
        max_icing_intensity="moderate",
    ),
    "business_jet": AircraftProfile(
        name="Business Jet (Gulfstream G650)",
        aircraft_type=AircraftType.BUSINESS_JET,
        max_crosswind_ms=11.0,
        max_tailwind_ms=5.0,
        max_gust_ms=18.0,
        min_visibility_m=600.0,
        min_ceiling_ft=300.0,
        max_icing_intensity="moderate",
    ),
    "helicopter": AircraftProfile(
        name="Helicopter (Bell 429)",
        aircraft_type=AircraftType.HELICOPTER,
        max_crosswind_ms=8.0,
        max_tailwind_ms=4.0,
        max_gust_ms=12.0,
        min_visibility_m=800.0,
        min_ceiling_ft=300.0,
        max_icing_intensity="light",
        constraints={"hoisting_ops_wind_max": 10.0},
    ),
    "general": AircraftProfile(
        name="General Aviation",
        aircraft_type=AircraftType.GENERAL,
    ),
}


@dataclass
class RunwayCondition:
    operation: OperationType
    crosswind_ms: float
    tailwind_ms: float
    headwind_ms: float
    surface_condition: str
    braking_action: str
    risk_level: str
    recommendation: str


@dataclass
class FlightRisk:
    phase: str
    risk_level: str
    factor: str
    value: float
    threshold: float
    recommendation: str


@dataclass
class IcingAssessment:
    icing_risk: bool
    intensity: str
    altitude_range: str
    recommendation: str
