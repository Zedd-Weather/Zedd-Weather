"""
Marine data models for Zedd Weather.
Vessel profiles, maritime operations, and offshore risk assessment.
"""
from dataclasses import dataclass, field
from enum import Enum


class VesselType(Enum):
    CONTAINER_SHIP = "container_ship"
    BULK_CARRIER = "bulk_carrier"
    TANKER = "tanker"
    FISHING_VESSEL = "fishing_vessel"
    PLEASURE_CRAFT = "pleasure_craft"
    OFFSHORE_SUPPLY = "offshore_supply"
    PASSENGER_FERRY = "passenger_ferry"
    TUG = "tug"
    GENERAL = "general"


class MaritimeOperation(Enum):
    OPEN_SEA_TRANSIT = "open_sea_transit"
    COASTAL_NAVIGATION = "coastal_navigation"
    PORT_ENTRY = "port_entry"
    BERTHING = "berthing"
    CARGO_TRANSFER = "cargo_transfer"
    FISHING = "fishing"
    OFFSHORE_WORK = "offshore_work"
    ANCHORED = "anchored"
    GENERAL = "general"


class BeaufortScale(Enum):
    CALM = (0, "Calm", 0.0, 0.2)
    LIGHT_AIR = (1, "Light Air", 0.3, 1.5)
    LIGHT_BREEZE = (2, "Light Breeze", 1.6, 3.3)
    GENTLE_BREEZE = (3, "Gentle Breeze", 3.4, 5.4)
    MODERATE_BREEZE = (4, "Moderate Breeze", 5.5, 7.9)
    FRESH_BREEZE = (5, "Fresh Breeze", 8.0, 10.7)
    STRONG_BREEZE = (6, "Strong Breeze", 10.8, 13.8)
    NEAR_GALE = (7, "Near Gale", 13.9, 17.1)
    GALE = (8, "Gale", 17.2, 20.7)
    STRONG_GALE = (9, "Strong Gale", 20.8, 24.4)
    STORM = (10, "Storm", 24.5, 28.4)
    VIOLENT_STORM = (11, "Violent Storm", 28.5, 32.6)
    HURRICANE_FORCE = (12, "Hurricane Force", 32.7, 999.0)

    def __init__(self, number, name, wind_min, wind_max):
        self.number = number
        self.bf_name = name
        self.wind_min = wind_min
        self.wind_max = wind_max

    @staticmethod
    def from_wind_speed(ms: float):
        for b in BeaufortScale:
            if b.wind_min <= ms <= b.wind_max:
                return b
        return BeaufortScale.HURRICANE_FORCE


@dataclass
class VesselProfile:
    """Operating thresholds for a specific vessel type."""
    name: str
    vessel_type: VesselType
    # Wind limits (m/s)
    max_operational_wind: float = 15.0
    max_safe_wind: float = 20.0
    # Wave/swell limits (m) — where data available
    max_operational_wave_m: float = 2.5
    max_safe_wave_m: float = 4.0
    # Visibility limits (m)
    min_operational_visibility_m: float = 500.0
    min_safe_visibility_m: float = 200.0
    # Ice formation threshold
    ice_formation_temp_c: float = -2.0
    # Storm avoidance
    storm_avoidance_wind_ms: float = 22.0
    # Vessel-specific constraints
    constraints: dict = field(default_factory=dict)


VESSEL_PROFILES: dict[str, VesselProfile] = {
    "container_ship": VesselProfile(
        name="Container Ship",
        vessel_type=VesselType.CONTAINER_SHIP,
        max_operational_wind=17.0,
        max_safe_wind=22.0,
        max_operational_wave_m=3.0,
        max_safe_wave_m=5.0,
        min_operational_visibility_m=500.0,
        min_safe_visibility_m=200.0,
    ),
    "fishing_vessel": VesselProfile(
        name="Fishing Vessel",
        vessel_type=VesselType.FISHING_VESSEL,
        max_operational_wind=12.0,
        max_safe_wind=17.0,
        max_operational_wave_m=2.0,
        max_safe_wave_m=3.5,
        min_operational_visibility_m=300.0,
        min_safe_visibility_m=100.0,
        constraints={"deck_cargo_secure_wind_max": 15.0},
    ),
    "passenger_ferry": VesselProfile(
        name="Passenger Ferry",
        vessel_type=VesselType.PASSENGER_FERRY,
        max_operational_wind=14.0,
        max_safe_wind=18.0,
        max_operational_wave_m=2.5,
        max_safe_wave_m=3.5,
        min_operational_visibility_m=1000.0,
        min_safe_visibility_m=500.0,
        constraints={"passenger_comfort_wind_max": 12.0},
    ),
    "offshore_supply": VesselProfile(
        name="Offshore Supply Vessel",
        vessel_type=VesselType.OFFSHORE_SUPPLY,
        max_operational_wind=16.0,
        max_safe_wind=22.0,
        max_operational_wave_m=3.5,
        max_safe_wave_m=5.0,
        min_operational_visibility_m=400.0,
        min_safe_visibility_m=150.0,
        constraints={"helicopter_ops_wind_max": 13.0},
    ),
    "pleasure_craft": VesselProfile(
        name="Pleasure Craft / Yacht",
        vessel_type=VesselType.PLEASURE_CRAFT,
        max_operational_wind=10.0,
        max_safe_wind=14.0,
        max_operational_wave_m=1.5,
        max_safe_wave_m=2.5,
        min_operational_visibility_m=500.0,
        min_safe_visibility_m=200.0,
        ice_formation_temp_c=-1.0,
    ),
    "general": VesselProfile(
        name="General Maritime",
        vessel_type=VesselType.GENERAL,
    ),
}


@dataclass
class SeaStateAssessment:
    """Sea state and navigation conditions."""
    beaufort: str                       # Beaufort scale name
    beaufort_number: int
    wind_wave_risk: str                 # "low", "medium", "high", "critical"
    swell_estimate_m: float             # Estimated swell height
    navigation_risk: str
    recommendation: str


@dataclass
class VesselSafety:
    """Vessel-specific safety assessment."""
    icing_risk: bool
    deck_operation_safe: bool
    cargo_transfer_safe: bool
    stability_concern: bool
    wind_warning: str | None
    recommendations: list[str]


@dataclass
class MarineHazard:
    """A single maritime hazard."""
    hazard: str
    risk_level: str
    condition: str
    recommendation: str
    affected_operations: list[str] | None = None
