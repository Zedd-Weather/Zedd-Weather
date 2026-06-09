"""
Global region and climate models for Zedd Weather.
Shared across construction, industrial, residential, and marine engines.
"""
from dataclasses import dataclass, field
from enum import Enum


class ClimateZone(Enum):
    MARITIME = "maritime"
    CONTINENTAL = "continental"
    MEDITERRANEAN = "mediterranean"
    ARID = "arid"
    TROPICAL = "tropical"
    ARCTIC = "arctic"
    MOUNTAIN = "mountain"


class UKRegion(Enum):
    SCOTLAND_WEST = "scotland_west"
    SCOTLAND_EAST = "scotland_east"
    NORTHERN_ENGLAND = "northern_england"
    MIDLANDS = "midlands"
    SOUTHERN_ENGLAND = "southern_england"
    WALES = "wales"
    NORTHERN_IRELAND = "northern_ireland"


class Season(Enum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


@dataclass
class RegionProfile:
    """Climate-adjusted thresholds for a geographic region."""
    name: str
    code: UKRegion
    zone: ClimateZone = ClimateZone.MARITIME
    summer_temp_range: tuple[float, float] = (14.0, 26.0)
    winter_temp_range: tuple[float, float] = (1.0, 8.0)
    rain_light_threshold: float = 2.5
    rain_moderate_threshold: float = 7.0
    wind_sustained_norm: float = 4.5
    wind_gust_norm: float = 9.0
    uv_summer_peak: float = 6.5
    humidity_norm: float = 77.0
    frost_probability: float = 0.3
    heat_wave_threshold_c: float = 28.0
    cold_spell_threshold_c: float = -4.0
    storm_risk_modifier: float = 1.0
    flood_risk_modifier: float = 1.0
    visibility_norm_m: float = 400.0
    temp_threshold_adjustment: float = 0.0
    wind_threshold_adjustment: float = 0.0


REGION_PROFILES: dict[UKRegion, RegionProfile] = {
    UKRegion.SCOTLAND_WEST: RegionProfile(
        name="West Scotland (Glasgow)",
        code=UKRegion.SCOTLAND_WEST,
        summer_temp_range=(12.0, 22.0),
        winter_temp_range=(0.0, 7.0),
        rain_light_threshold=2.0,
        rain_moderate_threshold=5.0,
        wind_sustained_norm=6.0,
        wind_gust_norm=12.0,
        uv_summer_peak=5.5,
        humidity_norm=82.0,
        frost_probability=0.4,
        heat_wave_threshold_c=25.0,
        cold_spell_threshold_c=-5.0,
        storm_risk_modifier=1.3,
        flood_risk_modifier=1.4,
        visibility_norm_m=300.0,
        temp_threshold_adjustment=-2.0,
        wind_threshold_adjustment=1.5,
    ),
    UKRegion.SCOTLAND_EAST: RegionProfile(
        name="East Scotland (Edinburgh)",
        code=UKRegion.SCOTLAND_EAST,
        summer_temp_range=(11.0, 21.0),
        winter_temp_range=(-1.0, 6.0),
        rain_light_threshold=1.5,
        rain_moderate_threshold=4.0,
        wind_sustained_norm=5.5,
        wind_gust_norm=11.0,
        uv_summer_peak=5.5,
        humidity_norm=78.0,
        frost_probability=0.5,
        heat_wave_threshold_c=25.0,
        cold_spell_threshold_c=-7.0,
        storm_risk_modifier=1.1,
        flood_risk_modifier=1.1,
        visibility_norm_m=400.0,
        temp_threshold_adjustment=-3.0,
        wind_threshold_adjustment=1.0,
    ),
    UKRegion.NORTHERN_ENGLAND: RegionProfile(
        name="Northern England",
        code=UKRegion.NORTHERN_ENGLAND,
        summer_temp_range=(13.0, 24.0),
        winter_temp_range=(0.0, 7.0),
        rain_light_threshold=2.0,
        rain_moderate_threshold=6.0,
        wind_sustained_norm=5.0,
        wind_gust_norm=10.0,
        uv_summer_peak=6.0,
        humidity_norm=79.0,
        frost_probability=0.35,
        heat_wave_threshold_c=27.0,
        cold_spell_threshold_c=-5.0,
        storm_risk_modifier=1.1,
        flood_risk_modifier=1.2,
        visibility_norm_m=350.0,
        temp_threshold_adjustment=-1.0,
        wind_threshold_adjustment=0.5,
    ),
    UKRegion.MIDLANDS: RegionProfile(
        name="Midlands",
        code=UKRegion.MIDLANDS,
        summer_temp_range=(14.0, 26.0),
        winter_temp_range=(1.0, 8.0),
        rain_light_threshold=2.5,
        rain_moderate_threshold=7.0,
        wind_sustained_norm=4.5,
        wind_gust_norm=9.0,
        uv_summer_peak=6.5,
        humidity_norm=77.0,
        frost_probability=0.3,
        heat_wave_threshold_c=28.0,
        cold_spell_threshold_c=-4.0,
        storm_risk_modifier=0.9,
        flood_risk_modifier=1.0,
        visibility_norm_m=400.0,
        temp_threshold_adjustment=0.0,
        wind_threshold_adjustment=0.0,
    ),
    UKRegion.SOUTHERN_ENGLAND: RegionProfile(
        name="Southern England",
        code=UKRegion.SOUTHERN_ENGLAND,
        summer_temp_range=(15.0, 28.0),
        winter_temp_range=(2.0, 9.0),
        rain_light_threshold=3.0,
        rain_moderate_threshold=8.0,
        wind_sustained_norm=4.0,
        wind_gust_norm=8.0,
        uv_summer_peak=7.0,
        humidity_norm=75.0,
        frost_probability=0.2,
        heat_wave_threshold_c=30.0,
        cold_spell_threshold_c=-3.0,
        storm_risk_modifier=0.8,
        flood_risk_modifier=0.9,
        visibility_norm_m=500.0,
        temp_threshold_adjustment=1.0,
        wind_threshold_adjustment=-0.5,
    ),
    UKRegion.WALES: RegionProfile(
        name="Wales",
        code=UKRegion.WALES,
        summer_temp_range=(12.0, 23.0),
        winter_temp_range=(1.0, 7.0),
        rain_light_threshold=2.0,
        rain_moderate_threshold=5.0,
        wind_sustained_norm=6.0,
        wind_gust_norm=12.0,
        uv_summer_peak=5.5,
        humidity_norm=81.0,
        frost_probability=0.3,
        heat_wave_threshold_c=26.0,
        cold_spell_threshold_c=-4.0,
        storm_risk_modifier=1.2,
        flood_risk_modifier=1.3,
        visibility_norm_m=300.0,
        temp_threshold_adjustment=-1.0,
        wind_threshold_adjustment=1.0,
    ),
    UKRegion.NORTHERN_IRELAND: RegionProfile(
        name="Northern Ireland",
        code=UKRegion.NORTHERN_IRELAND,
        summer_temp_range=(12.0, 22.0),
        winter_temp_range=(1.0, 7.0),
        rain_light_threshold=2.0,
        rain_moderate_threshold=5.0,
        wind_sustained_norm=5.5,
        wind_gust_norm=11.0,
        uv_summer_peak=5.5,
        humidity_norm=83.0,
        frost_probability=0.25,
        heat_wave_threshold_c=25.0,
        cold_spell_threshold_c=-4.0,
        storm_risk_modifier=1.2,
        flood_risk_modifier=1.2,
        visibility_norm_m=350.0,
        temp_threshold_adjustment=-1.5,
        wind_threshold_adjustment=0.5,
    ),
}
