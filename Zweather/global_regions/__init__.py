"""
Zedd Weather — Global Region Profiles

Shared region climate profiles and threshold adjustment logic
for all sector engines (construction, industrial, residential, marine).
"""
from .models import (
    ClimateZone,
    UKRegion,
    Season,
    RegionProfile,
    REGION_PROFILES,
)
from .regions import (
    get_region,
    resolve_season,
    region_adjusted_heat_threshold,
    region_adjusted_cold_threshold,
    region_adjusted_wind_threshold,
    region_adjusted_rain_threshold,
)

__all__ = [
    "ClimateZone",
    "UKRegion",
    "Season",
    "RegionProfile",
    "REGION_PROFILES",
    "get_region",
    "resolve_season",
    "region_adjusted_heat_threshold",
    "region_adjusted_cold_threshold",
    "region_adjusted_wind_threshold",
    "region_adjusted_rain_threshold",
]
