"""
Industrial data models for Zedd Weather.
Facility profiles with safe operating conditions, risk thresholds, and process categories.
"""
from dataclasses import dataclass, field
from enum import Enum


class FacilityCategory(Enum):
    MANUFACTURING = "manufacturing"
    POWER_PLANT = "power_plant"
    CHEMICAL = "chemical"
    WAREHOUSE = "warehouse"
    REFINERY = "refinery"
    GENERAL = "general"


@dataclass
class FacilityProfile:
    """Safe operating conditions and thresholds for an industrial facility type."""
    name: str
    # Temperature ranges (Celsius)
    temp_safe_min: float
    temp_safe_max: float
    temp_halt_min: float        # Below this = operations must stop
    temp_halt_max: float        # Above this = operations must stop
    # Wind speed limits (m/s)
    wind_max_operational: float  # Max wind for normal operations
    wind_halt: float             # Wind speed that halts operations
    # Humidity ranges (%)
    humidity_safe_min: float
    humidity_safe_max: float
    # Precipitation sensitivity
    rain_sensitive: bool = False
    rain_max_mm_hr: float = 10.0
    # Pressure (hPa) - storm detection
    pressure_storm_threshold: float = 995.0
    # UV / heat stress for outdoor workers
    uv_caution_threshold: float = 6.0
    uv_halt_threshold: float = 11.0
    # AQI thresholds
    aqi_caution: int = 100
    aqi_halt: int = 200
    # Equipment sensitivity
    equipment_temp_min: float = -10.0
    equipment_temp_max: float = 50.0
    # Additional constraints
    constraints: dict = field(default_factory=dict)


# Built-in facility profiles
FACILITY_PROFILES: dict[str, FacilityProfile] = {
    "manufacturing": FacilityProfile(
        name="Manufacturing Plant",
        temp_safe_min=5.0, temp_safe_max=38.0,
        temp_halt_min=-10.0, temp_halt_max=45.0,
        wind_max_operational=15.0, wind_halt=25.0,
        humidity_safe_min=20.0, humidity_safe_max=80.0,
        rain_sensitive=False, rain_max_mm_hr=15.0,
        aqi_caution=100, aqi_halt=200,
        equipment_temp_min=-5.0, equipment_temp_max=45.0,
        constraints={
            "power_outage_risk_temp_max": 42.0,
            "ventilation_required_above_c": 30.0,
        },
    ),
    "power_plant": FacilityProfile(
        name="Power Plant",
        temp_safe_min=-15.0, temp_safe_max=42.0,
        temp_halt_min=-25.0, temp_halt_max=48.0,
        wind_max_operational=20.0, wind_halt=30.0,
        humidity_safe_min=15.0, humidity_safe_max=85.0,
        rain_sensitive=False, rain_max_mm_hr=20.0,
        aqi_caution=150, aqi_halt=250,
        equipment_temp_min=-20.0, equipment_temp_max=50.0,
        constraints={
            "cooling_water_temp_max_c": 30.0,
            "lightning_halt": True,
            "grid_stability_wind_max_ms": 25.0,
        },
    ),
    "chemical": FacilityProfile(
        name="Chemical Processing",
        temp_safe_min=5.0, temp_safe_max=35.0,
        temp_halt_min=-5.0, temp_halt_max=42.0,
        wind_max_operational=10.0, wind_halt=18.0,
        humidity_safe_min=25.0, humidity_safe_max=75.0,
        rain_sensitive=True, rain_max_mm_hr=5.0,
        aqi_caution=80, aqi_halt=150,
        equipment_temp_min=0.0, equipment_temp_max=40.0,
        constraints={
            "vapour_dispersion_wind_min_ms": 1.0,
            "static_discharge_humidity_max": 30.0,
            "exothermic_reaction_temp_max_c": 35.0,
        },
    ),
    "warehouse": FacilityProfile(
        name="Warehouse / Logistics",
        temp_safe_min=-5.0, temp_safe_max=40.0,
        temp_halt_min=-20.0, temp_halt_max=45.0,
        wind_max_operational=18.0, wind_halt=25.0,
        humidity_safe_min=20.0, humidity_safe_max=85.0,
        rain_sensitive=True, rain_max_mm_hr=10.0,
        aqi_caution=100, aqi_halt=200,
        equipment_temp_min=-15.0, equipment_temp_max=45.0,
        constraints={
            "forklift_outdoor_wind_max_ms": 15.0,
            "loading_dock_rain_halt": True,
        },
    ),
    "refinery": FacilityProfile(
        name="Refinery / Petrochemical",
        temp_safe_min=0.0, temp_safe_max=38.0,
        temp_halt_min=-10.0, temp_halt_max=45.0,
        wind_max_operational=12.0, wind_halt=20.0,
        humidity_safe_min=20.0, humidity_safe_max=80.0,
        rain_sensitive=True, rain_max_mm_hr=8.0,
        aqi_caution=80, aqi_halt=150,
        equipment_temp_min=-5.0, equipment_temp_max=42.0,
        constraints={
            "flare_wind_max_ms": 15.0,
            "lightning_halt": True,
            "vapour_cloud_humidity_max": 70.0,
        },
    ),
    "general": FacilityProfile(
        name="General Industrial",
        temp_safe_min=-5.0, temp_safe_max=40.0,
        temp_halt_min=-15.0, temp_halt_max=45.0,
        wind_max_operational=15.0, wind_halt=22.0,
        humidity_safe_min=15.0, humidity_safe_max=85.0,
        rain_sensitive=False, rain_max_mm_hr=12.0,
        aqi_caution=100, aqi_halt=200,
        equipment_temp_min=-10.0, equipment_temp_max=48.0,
    ),
}


@dataclass
class EquipmentAssessment:
    """Equipment and process safety assessment from atmospheric data."""
    thermal_stress_index: float     # 0.0 - 1.0 (1.0 = extreme)
    corrosion_risk_index: float     # 0.0 - 1.0 (1.0 = extreme)
    worker_heat_index: float        # 0.0 - 1.0
    worker_cold_index: float        # 0.0 - 1.0
    ventilation_required: bool
    ppe_recommendations: list[str]


@dataclass
class OperationalWindow:
    """Recommendation for whether industrial operations can proceed."""
    facility_type: str
    safe_to_proceed: bool
    risk_level: str             # "low", "medium", "high", "critical"
    halt_reasons: list[str]
    caution_reasons: list[str]
    recommended_delay_hours: int
    next_check_hours: int
