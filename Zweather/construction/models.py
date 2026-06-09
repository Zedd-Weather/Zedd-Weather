"""
Construction data models for Zedd Weather.
Activity profiles with safe operating conditions, risk thresholds, work categories,
and region-specific climate profiles for UK construction sites.

Region types (UKRegion, Season, RegionProfile, REGION_PROFILES) are re-exported
from the shared global_regions module for cross-engine consistency.
"""
from dataclasses import dataclass, field
from enum import Enum

from Zweather.global_regions.models import (
    UKRegion,
    Season,
    RegionProfile,
    REGION_PROFILES,
)


class WorkCategory(Enum):
    CONCRETE_POURING = "concrete_pouring"
    CRANE_OPERATIONS = "crane_operations"
    ROOFING = "roofing"
    EXCAVATION = "excavation"
    STEEL_ERECTION = "steel_erection"
    PAINTING = "painting"
    SCAFFOLDING = "scaffolding"
    DEMOLITION = "demolition"
    GROUND_WORKS = "ground_works"
    FACADE_WORKS = "facade_works"
    GENERAL = "general"


@dataclass
class ActivityProfile:
    """Safe operating conditions and thresholds for a construction activity."""
    name: str
    # Temperature ranges (Celsius)
    temp_safe_min: float
    temp_safe_max: float
    temp_halt_min: float        # Below this = work must stop
    temp_halt_max: float        # Above this = work must stop
    # Wind speed limits (m/s)
    wind_max_operational: float  # Max wind for normal operations
    wind_halt: float             # Wind speed that halts the activity
    # Wind gust limit (m/s) — often lower than sustained for safety
    wind_gust_halt: float | None = None
    # Humidity ranges (%)
    humidity_safe_min: float = 10.0
    humidity_safe_max: float = 90.0
    # Precipitation sensitivity
    rain_sensitive: bool = True
    rain_max_mm_hr: float = 0.0
    # Pressure (hPa) — storm detection
    pressure_storm_threshold: float = 995.0
    # UV / heat stress for workers
    uv_caution_threshold: float = 6.0
    uv_halt_threshold: float = 11.0
    # Visibility (metres) — relevant for crane/heavy equipment
    min_visibility_m: float = 100.0
    # Additional constraints
    constraints: dict = field(default_factory=dict)


# Built-in activity profiles
ACTIVITY_PROFILES: dict[str, ActivityProfile] = {
    "concrete_pouring": ActivityProfile(
        name="Concrete Pouring",
        temp_safe_min=5.0, temp_safe_max=35.0,
        temp_halt_min=0.0, temp_halt_max=40.0,
        wind_max_operational=10.0, wind_halt=15.0,
        wind_gust_halt=20.0,
        humidity_safe_min=40.0, humidity_safe_max=90.0,
        rain_sensitive=True, rain_max_mm_hr=0.0,
        constraints={
            "curing_temp_min": 5.0,
            "curing_temp_max": 30.0,
            "max_wind_for_finish": 8.0,
        },
    ),
    "crane_operations": ActivityProfile(
        name="Crane Operations",
        temp_safe_min=-10.0, temp_safe_max=40.0,
        temp_halt_min=-20.0, temp_halt_max=45.0,
        wind_max_operational=9.0, wind_halt=13.0,
        wind_gust_halt=18.0,
        humidity_safe_min=10.0, humidity_safe_max=95.0,
        rain_sensitive=False, rain_max_mm_hr=10.0,
        min_visibility_m=200.0,
        constraints={
            "lightning_halt": True,
            "gust_halt_ms": 18.0,
        },
    ),
    "roofing": ActivityProfile(
        name="Roofing",
        temp_safe_min=2.0, temp_safe_max=38.0,
        temp_halt_min=-5.0, temp_halt_max=42.0,
        wind_max_operational=8.0, wind_halt=12.0,
        wind_gust_halt=15.0,
        humidity_safe_min=20.0, humidity_safe_max=85.0,
        rain_sensitive=True, rain_max_mm_hr=0.0,
        uv_caution_threshold=6.0, uv_halt_threshold=11.0,
        constraints={
            "surface_wet_halt": True,
            "frost_halt": True,
        },
    ),
    "scaffolding": ActivityProfile(
        name="Scaffolding Erection / Dismantling",
        temp_safe_min=-2.0, temp_safe_max=35.0,
        temp_halt_min=-8.0, temp_halt_max=40.0,
        wind_max_operational=7.0, wind_halt=11.0,
        wind_gust_halt=14.0,
        humidity_safe_min=10.0, humidity_safe_max=90.0,
        rain_sensitive=True, rain_max_mm_hr=1.0,
        min_visibility_m=100.0,
        constraints={
            "ice_on_tubes_halt": True,
            "wet_surface_halt": True,
        },
    ),
    "excavation": ActivityProfile(
        name="Excavation",
        temp_safe_min=-5.0, temp_safe_max=40.0,
        temp_halt_min=-15.0, temp_halt_max=45.0,
        wind_max_operational=15.0, wind_halt=20.0,
        wind_gust_halt=25.0,
        humidity_safe_min=10.0, humidity_safe_max=95.0,
        rain_sensitive=False, rain_max_mm_hr=5.0,
        min_visibility_m=50.0,
        constraints={
            "soil_saturation_halt": True,
            "frost_depth_concern_cm": 30.0,
        },
    ),
    "ground_works": ActivityProfile(
        name="Ground Works / Foundation",
        temp_safe_min=1.0, temp_safe_max=35.0,
        temp_halt_min=-5.0, temp_halt_max=40.0,
        wind_max_operational=12.0, wind_halt=18.0,
        humidity_safe_min=10.0, humidity_safe_max=90.0,
        rain_sensitive=False, rain_max_mm_hr=8.0,
        min_visibility_m=50.0,
        constraints={
            "frost_heave_risk": True,
            "waterlogged_soil_halt": True,
        },
    ),
    "steel_erection": ActivityProfile(
        name="Steel Erection",
        temp_safe_min=-5.0, temp_safe_max=40.0,
        temp_halt_min=-15.0, temp_halt_max=45.0,
        wind_max_operational=10.0, wind_halt=14.0,
        wind_gust_halt=18.0,
        humidity_safe_min=10.0, humidity_safe_max=90.0,
        rain_sensitive=True, rain_max_mm_hr=2.0,
        min_visibility_m=150.0,
        constraints={
            "lightning_halt": True,
            "ice_on_steel_halt": True,
        },
    ),
    "painting": ActivityProfile(
        name="Painting / Coating",
        temp_safe_min=10.0, temp_safe_max=35.0,
        temp_halt_min=5.0, temp_halt_max=40.0,
        wind_max_operational=6.0, wind_halt=10.0,
        wind_gust_halt=12.0,
        humidity_safe_min=30.0, humidity_safe_max=75.0,
        rain_sensitive=True, rain_max_mm_hr=0.0,
        constraints={
            "dew_point_margin_c": 3.0,
            "surface_temp_min_c": 10.0,
        },
    ),
    "demolition": ActivityProfile(
        name="Demolition",
        temp_safe_min=-5.0, temp_safe_max=38.0,
        temp_halt_min=-12.0, temp_halt_max=42.0,
        wind_max_operational=10.0, wind_halt=15.0,
        wind_gust_halt=18.0,
        humidity_safe_min=10.0, humidity_safe_max=90.0,
        rain_sensitive=False, rain_max_mm_hr=5.0,
        min_visibility_m=100.0,
        constraints={
            "lightning_halt": True,
            "high_wind_debris_risk": True,
        },
    ),
    "facade_works": ActivityProfile(
        name="Facade / Cladding Works",
        temp_safe_min=2.0, temp_safe_max=35.0,
        temp_halt_min=-5.0, temp_halt_max=40.0,
        wind_max_operational=8.0, wind_halt=12.0,
        wind_gust_halt=15.0,
        humidity_safe_min=20.0, humidity_safe_max=85.0,
        rain_sensitive=True, rain_max_mm_hr=0.0,
        min_visibility_m=100.0,
        constraints={
            "sealant_temp_min_c": 5.0,
            "adhesion_rain_halt": True,
        },
    ),
    "general": ActivityProfile(
        name="General Construction",
        temp_safe_min=0.0, temp_safe_max=38.0,
        temp_halt_min=-10.0, temp_halt_max=43.0,
        wind_max_operational=12.0, wind_halt=18.0,
        wind_gust_halt=22.0,
        humidity_safe_min=15.0, humidity_safe_max=90.0,
        rain_sensitive=False, rain_max_mm_hr=8.0,
        min_visibility_m=50.0,
    ),
}


@dataclass
class SafetyAssessment:
    """Worker safety assessment from atmospheric data."""
    heat_stress_index: float   # 0.0 - 1.0 (1.0 = extreme)
    cold_stress_index: float   # 0.0 - 1.0 (1.0 = extreme)
    work_rest_ratio: str       # e.g. "50:10" (50 min work, 10 min rest)
    hydration_litres_hr: float  # Recommended water intake per hour
    ppe_recommendations: list[str]


@dataclass
class WorkWindow:
    """Recommendation for whether a construction activity can proceed."""
    activity: str
    safe_to_proceed: bool
    risk_level: str             # "low", "medium", "high", "critical"
    halt_reasons: list[str]
    caution_reasons: list[str]
    recommended_delay_hours: int
    next_check_hours: int
    region: str | None = None
    season: str | None = None


@dataclass
class HazardReport:
    """A single identified hazard with assessment."""
    hazard: str
    risk_level: str
    condition: str
    recommendation: str
    affected_activities: list[str] | None = None


@dataclass
class MaterialRisk:
    """A single material risk from weather conditions."""
    material: str
    risk_level: str
    condition: str
    recommendation: str
