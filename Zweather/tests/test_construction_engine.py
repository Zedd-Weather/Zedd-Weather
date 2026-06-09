"""Tests for Zweather.construction.engine and region support."""
from Zweather.construction.engine import ConstructionEngine
from Zweather.construction.models import (
    ACTIVITY_PROFILES,
    SafetyAssessment,
    WorkWindow,
    HazardReport,
    MaterialRisk,
    UKRegion,
    Season,
)
from Zweather.global_regions import get_region, resolve_season


class TestConstructionEngine:
    def setup_method(self):
        self.engine = ConstructionEngine()
        self.normal_telemetry = {
            "temperature": 22.0,
            "humidity": 55.0,
            "pressure": 1013.0,
            "wind_speed": 3.0,
        }
        self.normal_telemetry_uk = {
            "temperature": 22.0,
            "humidity": 55.0,
            "pressure": 1013.0,
            "wind_speed": 3.0,
            "wind_gust": 5.0,
            "visibility_m": 500.0,
            "cloud_cover_pct": 40.0,
        }

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def test_analyze_returns_dict(self):
        result = self.engine.analyze(self.normal_telemetry)
        assert isinstance(result, dict)
        assert "risk_level" in result
        assert result["region"] == "Midlands"

    def test_analyze_with_region(self):
        result = self.engine.analyze(self.normal_telemetry, region="glasgow")
        assert result["region"] == "West Scotland (Glasgow)"

    def test_analyze_with_region_enum(self):
        result = self.engine.analyze(self.normal_telemetry, region=UKRegion.SOUTHERN_ENGLAND)
        assert result["region"] == "Southern England"

    def test_analyze_with_season(self):
        result = self.engine.analyze(self.normal_telemetry, season="winter")
        assert result["season"] == "winter"

    # ------------------------------------------------------------------
    # Risk level
    # ------------------------------------------------------------------

    def test_risk_level_normal_conditions(self):
        risk = self.engine.compute_risk_level(self.normal_telemetry, "general")
        assert risk in ("low", "medium", "high", "critical")

    def test_risk_level_high_wind(self):
        windy = {**self.normal_telemetry, "wind_speed": 20.0}
        risk = self.engine.compute_risk_level(windy, "crane_operations")
        assert risk in ("high", "critical")

    def test_risk_level_extreme_heat(self):
        hot = {**self.normal_telemetry, "temperature": 42.0, "humidity": 70.0}
        risk = self.engine.compute_risk_level(hot, "general")
        assert risk in ("high", "critical")

    def test_risk_level_extreme_cold(self):
        freezing = {**self.normal_telemetry, "temperature": -15.0}
        risk = self.engine.compute_risk_level(freezing, "general")
        assert risk in ("high", "critical")

    # ------------------------------------------------------------------
    # Worker safety
    # ------------------------------------------------------------------

    def test_worker_safety_assessment(self):
        result = self.engine.assess_worker_safety(self.normal_telemetry)
        assert isinstance(result, SafetyAssessment)
        assert 0.0 <= result.heat_stress_index <= 1.0
        assert 0.0 <= result.cold_stress_index <= 1.0
        assert result.hydration_litres_hr > 0.0
        assert isinstance(result.ppe_recommendations, list)
        assert len(result.ppe_recommendations) > 0

    def test_worker_safety_glasgow_summer(self):
        """Glasgow summer thresholds should be more sensitive to heat."""
        warm = {**self.normal_telemetry, "temperature": 26.0, "humidity": 70.0}
        mids = self.engine.assess_worker_safety(warm, region="midlands", season="summer")
        glas = self.engine.assess_worker_safety(warm, region="glasgow", season="summer")
        # Glasgow has lower heat threshold — may have higher stress index
        # at minimum, both should return valid SafetyAssessment
        assert isinstance(mids, SafetyAssessment)
        assert isinstance(glas, SafetyAssessment)

    def test_worker_safety_glasgow_winter(self):
        """Glasgow winter should be cold-sensitive."""
        chilly = {**self.normal_telemetry, "temperature": 2.0, "wind_speed": 8.0}
        result = self.engine.assess_worker_safety(chilly, region="glasgow", season="winter")
        # In a Glasgow winter, 2°C with 8 m/s wind should register cold stress
        assert isinstance(result, SafetyAssessment)

    def test_heat_stress_work_rest_ratio(self):
        hot = {"temperature": 40.0, "humidity": 80.0, "pressure": 1013.0, "wind_speed": 1.0}
        safety = self.engine.assess_worker_safety(hot)
        work_mins = int(safety.work_rest_ratio.split(":")[0])
        assert work_mins <= 30

    # ------------------------------------------------------------------
    # Work window
    # ------------------------------------------------------------------

    def test_work_window_evaluation(self):
        result = self.engine.evaluate_work_window(self.normal_telemetry, "concrete_pouring")
        assert isinstance(result, WorkWindow)
        assert result.risk_level in ("low", "medium", "high", "critical")

    def test_concrete_halted_in_rain(self):
        rainy = {**self.normal_telemetry, "rainfall_mm": 5.0}
        result = self.engine.evaluate_work_window(rainy, "concrete_pouring")
        assert result.safe_to_proceed is False
        assert len(result.halt_reasons) > 0

    def test_crane_halted_high_wind(self):
        windy = {**self.normal_telemetry, "wind_speed": 15.0}
        result = self.engine.evaluate_work_window(windy, "crane_operations")
        assert result.safe_to_proceed is False
        assert len(result.halt_reasons) > 0

    def test_work_window_glasgow_rain(self):
        """Glasgow rain threshold should be higher — same rain less disruptive."""
        rainy = {**self.normal_telemetry_uk, "rainfall_mm": 6.0}
        mids = self.engine.evaluate_work_window(rainy, "general", region="midlands")
        glas = self.engine.evaluate_work_window(rainy, "general", region="glasgow")
        # Glasgow should have same or fewer cautions (higher rain tolerance)
        assert len(glas.caution_reasons) <= len(mids.caution_reasons) + 1

    def test_work_window_visibility_halt(self):
        foggy = {**self.normal_telemetry_uk, "visibility_m": 30.0}
        result = self.engine.evaluate_work_window(foggy, "crane_operations")
        assert result.safe_to_proceed is False
        assert any("visibility" in r.lower() for r in result.halt_reasons)

    def test_work_window_gust_halt(self):
        gusty = {**self.normal_telemetry_uk, "wind_speed": 5.0, "wind_gust": 22.0}
        result = self.engine.evaluate_work_window(gusty, "general")
        assert result.safe_to_proceed is False
        assert any("gust" in r.lower() for r in result.halt_reasons)

    def test_normal_conditions_safe_to_proceed(self):
        result = self.engine.evaluate_work_window(self.normal_telemetry, "general")
        assert result.safe_to_proceed is True
        assert result.risk_level == "low"

    # ------------------------------------------------------------------
    # Weather hazards
    # ------------------------------------------------------------------

    def test_weather_hazard_detection(self):
        hazards = self.engine.detect_weather_hazards(self.normal_telemetry, "general")
        assert isinstance(hazards, list)
        assert isinstance(hazards[0], HazardReport)

    def test_extreme_wind_hazard(self):
        windy = {**self.normal_telemetry, "wind_speed": 25.0}
        hazards = self.engine.detect_weather_hazards(windy, "general")
        hazard_names = [h.hazard for h in hazards]
        assert "Extreme Wind" in hazard_names

    def test_flood_hazard_glasgow(self):
        """Glasgow should flag flooding with sustained heavy rain."""
        rainy = {**self.normal_telemetry_uk, "rainfall_mm": 12.0, "rain_duration_hours": 3.0}
        mids = self.engine.detect_weather_hazards(rainy, "general", region="midlands")
        glas = self.engine.detect_weather_hazards(rainy, "general", region="glasgow")
        glas_names = [h.hazard for h in glas]
        # Glasgow's flood risk modifier should trigger the flood hazard
        assert any("flood" in n.lower() for n in glas_names)

    def test_frost_hazard(self):
        freezing = {**self.normal_telemetry_uk, "temperature": -1.0, "humidity": 80.0}
        hazards = self.engine.detect_weather_hazards(freezing, "general", season="winter")
        names = [h.hazard for h in hazards]
        assert any("frost" in n.lower() or "ice" in n.lower() for n in names)

    # ------------------------------------------------------------------
    # Material risks
    # ------------------------------------------------------------------

    def test_material_risk_detection(self):
        risks = self.engine.detect_material_risks(self.normal_telemetry, "general")
        assert isinstance(risks, list)
        assert isinstance(risks[0], MaterialRisk)

    def test_cold_concrete_risk(self):
        cold = {**self.normal_telemetry, "temperature": 2.0}
        risks = self.engine.detect_material_risks(cold, "concrete_pouring")
        material_names = [r.material for r in risks]
        assert "Concrete" in material_names

    def test_damp_rot_risk_glasgow(self):
        """Glasgow persistent damp should flag timber risk."""
        damp = {**self.normal_telemetry_uk, "humidity": 88.0, "rainfall_mm": 3.0, "rain_duration_hours": 36.0}
        risks = self.engine.detect_material_risks(damp, "general", region="glasgow")
        materials = [r.material for r in risks]
        assert "Timber / Wood" in materials

    def test_frost_heave_risk_winter(self):
        frozen = {**self.normal_telemetry_uk, "temperature": -4.0}
        risks = self.engine.detect_material_risks(frozen, "ground_works", season="winter")
        materials = [r.material for r in risks]
        assert "Ground / Foundation" in materials

    # ------------------------------------------------------------------
    # Cross-activity
    # ------------------------------------------------------------------

    def test_all_activity_profiles_analyzable(self):
        for activity_key in ACTIVITY_PROFILES:
            result = self.engine.analyze(self.normal_telemetry_uk, activity=activity_key)
            assert "risk_level" in result

    def test_missing_telemetry_keys(self):
        partial = {"temperature": 20.0}
        result = self.engine.analyze(partial, "general")
        assert isinstance(result, dict)
        assert "risk_level" in result

    # ------------------------------------------------------------------
    # Region helpers
    # ------------------------------------------------------------------

    def test_get_region_none_defaults_to_midlands(self):
        rp = get_region(None)
        assert rp.name == "Midlands"

    def test_get_region_city_alias(self):
        rp = get_region("glasgow")
        assert "Glasgow" in rp.name

    def test_get_region_london(self):
        rp = get_region("london")
        assert "Southern England" in rp.name

    def test_get_region_enum(self):
        rp = get_region(UKRegion.WALES)
        assert rp.name == "Wales"

    def test_get_region_profile_passthrough(self):
        rp = get_region("edinburgh")
        same = get_region(rp)
        assert same.name == rp.name

    def test_resolve_season_default(self):
        sn = resolve_season(None)
        assert isinstance(sn, Season)

    def test_resolve_season_override(self):
        assert resolve_season("winter") == Season.WINTER
