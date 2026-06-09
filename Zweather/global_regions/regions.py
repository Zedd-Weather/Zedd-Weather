"""
Region resolution and threshold adjustment utilities.
Shared across construction, industrial, residential, and marine engines.
"""
from datetime import date
from .models import (
    UKRegion,
    Season,
    RegionProfile,
    REGION_PROFILES,
)


def get_region(region: str | UKRegion | RegionProfile | None) -> RegionProfile:
    """Resolve a region string, enum, or profile to a RegionProfile."""
    if region is None:
        return REGION_PROFILES[UKRegion.MIDLANDS]

    if isinstance(region, RegionProfile):
        return region

    if isinstance(region, UKRegion):
        return REGION_PROFILES[region]

    key = region.lower().strip().replace(" ", "_")

    ALIASES: dict[str, UKRegion] = {
        "glasgow": UKRegion.SCOTLAND_WEST,
        "edinburgh": UKRegion.SCOTLAND_EAST,
        "scotland": UKRegion.SCOTLAND_WEST,
        "manchester": UKRegion.NORTHERN_ENGLAND,
        "liverpool": UKRegion.NORTHERN_ENGLAND,
        "leeds": UKRegion.NORTHERN_ENGLAND,
        "newcastle": UKRegion.NORTHERN_ENGLAND,
        "birmingham": UKRegion.MIDLANDS,
        "nottingham": UKRegion.MIDLANDS,
        "leicester": UKRegion.MIDLANDS,
        "london": UKRegion.SOUTHERN_ENGLAND,
        "southampton": UKRegion.SOUTHERN_ENGLAND,
        "bristol": UKRegion.SOUTHERN_ENGLAND,
        "brighton": UKRegion.SOUTHERN_ENGLAND,
        "cardiff": UKRegion.WALES,
        "swansea": UKRegion.WALES,
        "belfast": UKRegion.NORTHERN_IRELAND,
        "northern ireland": UKRegion.NORTHERN_IRELAND,
        "west scotland": UKRegion.SCOTLAND_WEST,
        "east scotland": UKRegion.SCOTLAND_EAST,
        "northern england": UKRegion.NORTHERN_ENGLAND,
        "southern england": UKRegion.SOUTHERN_ENGLAND,
    }

    resolved = ALIASES.get(key)
    if resolved is not None:
        return REGION_PROFILES[resolved]

    try:
        return REGION_PROFILES[UKRegion(key)]
    except (ValueError, KeyError):
        return REGION_PROFILES[UKRegion.MIDLANDS]


def resolve_season(override: str | Season | None = None) -> Season:
    """Determine the current season, or return the override if given."""
    if isinstance(override, Season):
        return override
    if isinstance(override, str):
        try:
            return Season(override.lower().strip())
        except ValueError:
            pass

    today = date.today()
    m = today.month
    if 3 <= m <= 5:
        return Season.SPRING
    if 6 <= m <= 8:
        return Season.SUMMER
    if 9 <= m <= 11:
        return Season.AUTUMN
    return Season.WINTER


def region_adjusted_heat_threshold(
    base_threshold: float, region: RegionProfile, season: Season,
) -> float:
    """Adjust a heat threshold for regional acclimatisation."""
    adj = region.temp_threshold_adjustment
    if season in (Season.WINTER, Season.AUTUMN):
        adj -= 1.0
    return base_threshold + adj


def region_adjusted_cold_threshold(
    base_threshold: float, region: RegionProfile, season: Season,
) -> float:
    """Adjust a cold threshold for regional acclimatisation."""
    adj = region.temp_threshold_adjustment
    if season in (Season.SUMMER, Season.SPRING):
        adj += 1.0
    return base_threshold + adj


def region_adjusted_wind_threshold(
    base_threshold: float, region: RegionProfile,
) -> float:
    """Adjust a wind threshold for regional windiness."""
    return base_threshold + region.wind_threshold_adjustment


def region_adjusted_rain_threshold(
    base_mm_hr: float, region: RegionProfile,
) -> float:
    """Adjust a rain threshold for regional rainfall norms.

    A region that gets more rain will have higher thresholds —
    the same 5 mm/hr is "business as usual" in Glasgow but
    "notable" in London.
    """
    midlands_norm = REGION_PROFILES[UKRegion.MIDLANDS].rain_moderate_threshold
    factor = midlands_norm / region.rain_moderate_threshold
    return base_mm_hr * factor
