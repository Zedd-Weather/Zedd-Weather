"""
Transportation data models for Zedd Weather.
Transport mode profiles, route conditions, and logistics risk assessment.
"""
from dataclasses import dataclass, field
from enum import Enum


class TransportMode(Enum):
    ROAD = "road"
    RAIL = "rail"
    MARITIME = "maritime"
    AIR = "air"
    PIPELINE = "pipeline"
    GENERAL = "general"


class RouteType(Enum):
    HIGHWAY = "highway"
    URBAN = "urban"
    RURAL = "rural"
    MOUNTAIN = "mountain"
    COASTAL = "coastal"
    TUNNEL = "tunnel"
    BRIDGE = "bridge"
    GENERAL = "general"


@dataclass
class TransportProfile:
    name: str
    mode: TransportMode
    max_wind_ms: float = 15.0
    max_gust_ms: float = 20.0
    min_visibility_m: float = 100.0
    min_temp_c: float = -15.0
    max_temp_c: float = 45.0
    max_precip_mmh: float = 30.0
    flood_risk_precip_mm: float = 50.0
    icing_temp_c: float = 2.0
    constraints: dict = field(default_factory=dict)


TRANSPORT_PROFILES: dict[str, TransportProfile] = {
    "road": TransportProfile(
        name="Road Transport (HGV)",
        mode=TransportMode.ROAD,
        max_wind_ms=14.0,
        max_gust_ms=18.0,
        min_visibility_m=50.0,
        max_precip_mmh=35.0,
        flood_risk_precip_mm=50.0,
        icing_temp_c=2.0,
        constraints={"high_sides_wind_limit": 10.0, "skid_risk_humidity": 80.0},
    ),
    "rail": TransportProfile(
        name="Rail Transport",
        mode=TransportMode.RAIL,
        max_wind_ms=20.0,
        max_gust_ms=25.0,
        min_visibility_m=200.0,
        max_precip_mmh=40.0,
        flood_risk_precip_mm=60.0,
        icing_temp_c=0.0,
        constraints={"leaf_fall_risk": "autumn", "track_buckling_temp_c": 35.0},
    ),
    "maritime": TransportProfile(
        name="Maritime Transport (Inland)",
        mode=TransportMode.MARITIME,
        max_wind_ms=17.0,
        max_gust_ms=22.0,
        min_visibility_m=500.0,
        max_precip_mmh=30.0,
        flood_risk_precip_mm=80.0,
        constraints={"lock_closure_water_level": "high", "fog_risk_temp_dewpoint": 2.0},
    ),
    "air": TransportProfile(
        name="Air Transport (Cargo)",
        mode=TransportMode.AIR,
        max_wind_ms=12.0,
        max_gust_ms=15.0,
        min_visibility_m=400.0,
        max_precip_mmh=20.0,
        icing_temp_c=2.0,
        constraints={"lightning_standby": True, "deicing_temp_c": 3.0},
    ),
    "pipeline": TransportProfile(
        name="Pipeline Transport",
        mode=TransportMode.PIPELINE,
        max_wind_ms=30.0,
        max_temp_c=50.0,
        min_temp_c=-30.0,
        max_precip_mmh=60.0,
        constraints={"ground_heave_temp_c": -5.0, "flood_risk": True},
    ),
    "general": TransportProfile(
        name="General Transport",
        mode=TransportMode.GENERAL,
    ),
}


@dataclass
class RouteCondition:
    route_type: RouteType
    surface_condition: str
    visibility_condition: str
    risk_level: str
    recommendation: str


@dataclass
class LogisticsRisk:
    risk: str
    risk_level: str
    condition: str
    impact: str
    recommendation: str


@dataclass
class TravelAdvisory:
    advisory: str
    severity: str
    affected_routes: list[str]
    duration_hours: int
    recommendation: str
