"""
Agricultural data models for Zedd Weather.
Crop profiles with optimal growing conditions, stress thresholds, and growth stages.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class GrowthStage(Enum):
    GERMINATION = "germination"
    SEEDLING = "seedling"
    VEGETATIVE = "vegetative"
    FLOWERING = "flowering"
    FRUITING = "fruiting"
    MATURATION = "maturation"
    DORMANT = "dormant"


@dataclass
class CropProfile:
    """Optimal growing conditions and thresholds for a specific crop."""
    name: str
    # Temperature ranges (Celsius)
    temp_optimal_min: float
    temp_optimal_max: float
    temp_stress_min: float   # Below this = cold stress
    temp_stress_max: float   # Above this = heat stress
    temp_frost_kill: float   # Below this = frost kill
    # Humidity ranges (%)
    humidity_optimal_min: float
    humidity_optimal_max: float
    # Pressure (hPa) - mostly for weather pattern detection
    pressure_storm_threshold: float = 990.0
    # Irrigation (mm per day)
    water_requirement_mm_day: float = 5.0
    # Growth stages with day ranges from planting
    growth_stages: dict = field(default_factory=dict)


# Built-in crop profiles
CROP_PROFILES: dict[str, CropProfile] = {
    "maize": CropProfile(
        name="Maize (Corn)",
        temp_optimal_min=18.0, temp_optimal_max=30.0,
        temp_stress_min=10.0, temp_stress_max=35.0,
        temp_frost_kill=0.0,
        humidity_optimal_min=50.0, humidity_optimal_max=80.0,
        water_requirement_mm_day=6.0,
        growth_stages={
            GrowthStage.GERMINATION: (0, 7),
            GrowthStage.SEEDLING: (7, 21),
            GrowthStage.VEGETATIVE: (21, 70),
            GrowthStage.FLOWERING: (70, 90),
            GrowthStage.FRUITING: (90, 120),
            GrowthStage.MATURATION: (120, 150),
        }
    ),
    "wheat": CropProfile(
        name="Wheat",
        temp_optimal_min=12.0, temp_optimal_max=25.0,
        temp_stress_min=4.0, temp_stress_max=30.0,
        temp_frost_kill=-5.0,
        humidity_optimal_min=40.0, humidity_optimal_max=70.0,
        water_requirement_mm_day=4.0,
        growth_stages={
            GrowthStage.GERMINATION: (0, 10),
            GrowthStage.SEEDLING: (10, 30),
            GrowthStage.VEGETATIVE: (30, 90),
            GrowthStage.FLOWERING: (90, 120),
            GrowthStage.MATURATION: (120, 180),
        }
    ),
    "tomato": CropProfile(
        name="Tomato",
        temp_optimal_min=18.0, temp_optimal_max=29.0,
        temp_stress_min=10.0, temp_stress_max=35.0,
        temp_frost_kill=0.0,
        humidity_optimal_min=55.0, humidity_optimal_max=75.0,
        water_requirement_mm_day=7.0,
        growth_stages={
            GrowthStage.GERMINATION: (0, 14),
            GrowthStage.SEEDLING: (14, 42),
            GrowthStage.VEGETATIVE: (42, 90),
            GrowthStage.FLOWERING: (90, 120),
            GrowthStage.FRUITING: (120, 160),
            GrowthStage.MATURATION: (160, 180),
        }
    ),
    "rice": CropProfile(
        name="Rice",
        temp_optimal_min=20.0, temp_optimal_max=32.0,
        temp_stress_min=15.0, temp_stress_max=38.0,
        temp_frost_kill=5.0,
        humidity_optimal_min=60.0, humidity_optimal_max=90.0,
        water_requirement_mm_day=8.0,
    ),
    "potato": CropProfile(
        name="Potato",
        temp_optimal_min=15.0, temp_optimal_max=22.0,
        temp_stress_min=5.0, temp_stress_max=30.0,
        temp_frost_kill=-2.0,
        humidity_optimal_min=60.0, humidity_optimal_max=80.0,
        water_requirement_mm_day=5.5,
    ),
}


@dataclass
class SoilMoisturePrediction:
    """Predicted soil moisture level from atmospheric data."""
    estimated_vwc_pct: float    # Volumetric water content %
    confidence: float            # 0.0 - 1.0
    days_to_irrigation: int      # Estimated days until irrigation needed
    irrigation_volume_mm: float  # Recommended irrigation amount


@dataclass
class IrrigationSchedule:
    """Irrigation scheduling recommendation."""
    crop: str
    recommended: bool
    urgency: str                 # "none", "low", "medium", "high", "critical"
    volume_mm: float
    reason: str
    next_check_hours: int
