"""Tests for Zweather.global_regions — shared region infrastructure."""
from Zweather.global_regions.models import (
    UKRegion, Season, RegionProfile, REGION_PROFILES, ClimateZone,
)
from Zweather.global_regions.regions import (
    get_region,
    resolve_season,
    region_adjusted_heat_threshold,
    region_adjusted_cold_threshold,
    region_adjusted_wind_threshold,
    region_adjusted_rain_threshold,
)


class TestUKRegion:
    def test_all_regions_have_profiles(self):
        assert len(REGION_PROFILES) == 7
        for r in UKRegion:
            assert r in REGION_PROFILES

    def test_region_profiles_have_names(self):
        for rp in REGION_PROFILES.values():
            assert rp.name
            assert isinstance(rp.zone, ClimateZone)


class TestGetRegion:
    def test_none_defaults_to_midlands(self):
        rp = get_region(None)
        assert rp.name == "Midlands"

    def test_city_alias_glasgow(self):
        rp = get_region("glasgow")
        assert "Glasgow" in rp.name

    def test_city_alias_london(self):
        rp = get_region("london")
        assert "Southern England" in rp.name

    def test_enum_direct(self):
        rp = get_region(UKRegion.WALES)
        assert rp.name == "Wales"

    def test_profile_passthrough(self):
        rp = get_region("edinburgh")
        same = get_region(rp)
        assert same.name == rp.name

    def test_unknown_falls_back_to_midlands(self):
        rp = get_region("atlantis")
        assert rp.name == "Midlands"

    def test_all_city_aliases_resolve(self):
        cities = [
            "glasgow", "edinburgh", "manchester", "liverpool", "leeds",
            "newcastle", "birmingham", "nottingham", "leicester",
            "london", "southampton", "bristol", "brighton",
            "cardiff", "swansea", "belfast",
        ]
        for city in cities:
            rp = get_region(city)
            assert rp is not None


class TestResolveSeason:
    def test_default_returns_season(self):
        sn = resolve_season(None)
        assert isinstance(sn, Season)

    def test_override_string(self):
        assert resolve_season("winter") == Season.WINTER
        assert resolve_season("SUMMER") == Season.SUMMER

    def test_override_enum(self):
        assert resolve_season(Season.SPRING) == Season.SPRING

    def test_invalid_string_falls_back(self):
        sn = resolve_season("invalid_season")
        assert isinstance(sn, Season)


class TestThresholdAdjustments:
    def setup_method(self):
        self.midlands = get_region("midlands")
        self.glasgow = get_region("glasgow")
        self.london = get_region("london")
        self.summer = Season.SUMMER
        self.winter = Season.WINTER

    def test_heat_threshold_midlands_summer(self):
        adj = region_adjusted_heat_threshold(30.0, self.midlands, self.summer)
        # Midlands temp_adjustment = 0.0, no season penalty in summer
        assert adj == 30.0

    def test_heat_threshold_glasgow_summer(self):
        adj = region_adjusted_heat_threshold(30.0, self.glasgow, self.summer)
        # Glasgow temp_adjustment = -2.0
        assert adj == 28.0

    def test_heat_threshold_glasgow_winter(self):
        adj = region_adjusted_heat_threshold(30.0, self.glasgow, self.winter)
        # Glasgow temp_adjustment = -2.0, winter penalty -1.0
        assert adj == 27.0

    def test_cold_threshold_london_summer(self):
        adj = region_adjusted_cold_threshold(5.0, self.london, self.summer)
        # London temp_adjustment = 1.0, summer penalty +1.0
        assert adj == 7.0

    def test_cold_threshold_london_winter(self):
        adj = region_adjusted_cold_threshold(5.0, self.london, self.winter)
        # London temp_adjustment = 1.0, no summer penalty
        assert adj == 6.0

    def test_wind_threshold_glasgow(self):
        adj = region_adjusted_wind_threshold(10.0, self.glasgow)
        # Glasgow wind_adjustment = 1.5
        assert adj == 11.5

    def test_rain_threshold_glasgow_higher(self):
        # Glasgow gets more rain, so thresholds are higher
        glas = region_adjusted_rain_threshold(5.0, self.glasgow)
        mids = region_adjusted_rain_threshold(5.0, self.midlands)
        assert glas > mids
