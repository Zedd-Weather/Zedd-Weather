"""Tests for Zweather.industrial.engine — refined with region support."""
from Zweather.industrial.engine import IndustrialEngine
from Zweather.industrial.models import (
    FACILITY_PROFILES,
    EquipmentAssessment,
    OperationalWindow,
    IndustrialHazard,
    MaterialRisk,
)
from Zweather.global_regions.models import UKRegion, Season


class TestIndustrialEngine:
    def setup_method(self):
        self.engine = IndustrialEngine()
        self.normal_telemetry = {
            "temperature": 22.0,
            "humidity": 55.0,
            "pressure": 1013.0,
            "wind_speed": 3.0,
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
        result = self.engine.analyze(
            self.normal_telemetry, region=UKRegion.SOUTHERN_ENGLAND
        )
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
        windy = {**self.normal_telemetry, "wind_speed": 25.0}
        risk = self.engine.compute_risk_level(windy, "manufacturing")
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
    # Equipment safety
    # ------------------------------------------------------------------

    def test_equipment_safety_assessment(self):
        result = self.engine.assess_equipment_safety(self.normal_telemetry)
        assert isinstance(result, EquipmentAssessment)
        assert 0.0 <= result.thermal_stress_index <= 1.0
        assert 0.0 <= result.corrosion_risk_index <= 1.0
        assert 0.0 <= result.worker_heat_index <= 1.0
        assert 0.0 <= result.worker_cold_index <= 1.0
        assert isinstance(result.ppe_recommendations, list)
        assert len(result.ppe_recommendations) > 0

    def test_equipment_safety_glasgow_winter(self):
        chilly = {**self.normal_telemetry, "temperature": 2.0, "wind_speed": 8.0}
        result = self.engine.assess_equipment_safety(
            chilly, "general", region="glasgow", season="winter"
        )
        assert isinstance(result, EquipmentAssessment)
        # Glasgow winter with wind should register cold stress
        assert result.worker_cold_index > 0.0

    # ------------------------------------------------------------------
    # Operational window
    # ------------------------------------------------------------------

    def test_operational_window_evaluation(self):
        result = self.engine.evaluate_operational_window(
            self.normal_telemetry, "manufacturing"
        )
        assert isinstance(result, OperationalWindow)
        assert result.risk_level in ("low", "medium", "high", "critical")

    def test_chemical_halted_in_rain(self):
        rainy = {**self.normal_telemetry, "rainfall_mm": 10.0}
        result = self.engine.evaluate_operational_window(rainy, "chemical")
        assert result.safe_to_proceed is False
        assert len(result.halt_reasons) > 0

    def test_manufacturing_halted_high_wind(self):
        windy = {**self.normal_telemetry, "wind_speed": 30.0}
        result = self.engine.evaluate_operational_window(windy, "manufacturing")
        assert result.safe_to_proceed is False
        assert len(result.halt_reasons) > 0

    def test_normal_conditions_safe_to_proceed(self):
        result = self.engine.evaluate_operational_window(
            self.normal_telemetry, "general"
        )
        assert result.safe_to_proceed is True
        assert result.risk_level == "low"

    def test_wind_gust_halt(self):
        gusty = {**self.normal_telemetry, "wind_speed": 5.0, "wind_gust": 32.0}
        result = self.engine.evaluate_operational_window(gusty, "manufacturing")
        # Manufacturing wind_gust_halt = 30.0
        assert result.safe_to_proceed is False
        assert any("gust" in r.lower() for r in result.halt_reasons)

    def test_visibility_halt(self):
        foggy = {**self.normal_telemetry, "visibility_m": 30.0}
        result = self.engine.evaluate_operational_window(foggy, "chemical")
        assert result.safe_to_proceed is False
        assert any("visibility" in r.lower() for r in result.halt_reasons)

    def test_glasgow_higher_rain_tolerance(self):
        """Glasgow has higher rain thresholds — same rain less disruptive."""
        rainy = {**self.normal_telemetry, "rainfall_mm": 8.0}
        mids = self.engine.evaluate_operational_window(rainy, "general", region="midlands")
        glas = self.engine.evaluate_operational_window(rainy, "general", region="glasgow")
        assert len(glas.halt_reasons) <= len(mids.halt_reasons)

    # ------------------------------------------------------------------
    # Weather hazards
    # ------------------------------------------------------------------

    def test_weather_hazard_detection(self):
        hazards = self.engine.detect_weather_hazards(self.normal_telemetry, "general")
        assert isinstance(hazards, list)
        assert isinstance(hazards[0], IndustrialHazard)

    def test_extreme_wind_hazard(self):
        windy = {**self.normal_telemetry, "wind_speed": 25.0}
        hazards = self.engine.detect_weather_hazards(windy, "general")
        hazard_names = [h.hazard for h in hazards]
        assert "Extreme Wind" in hazard_names

    def test_process_risk_detection(self):
        risks = self.engine.detect_material_risks(self.normal_telemetry, "general")
        assert isinstance(risks, list)
        assert isinstance(risks[0], MaterialRisk)

    def test_equipment_overheating_risk(self):
        hot = {**self.normal_telemetry, "temperature": 55.0}
        risks = self.engine.detect_material_risks(hot, "manufacturing")
        material_names = [r.material for r in risks]
        assert "Heat-Sensitive Equipment" in material_names

    def test_chemical_static_discharge_risk(self):
        dry = {**self.normal_telemetry, "humidity": 20.0}
        risks = self.engine.detect_material_risks(dry, "chemical")
        material_names = [r.material for r in risks]
        assert "Flammable Materials / Vapours" in material_names

    def test_aqi_halt(self):
        polluted = {**self.normal_telemetry, "aqi": 250.0}
        result = self.engine.evaluate_operational_window(polluted, "general")
        assert result.safe_to_proceed is False

    # ------------------------------------------------------------------
    # Cross-facility
    # ------------------------------------------------------------------

    def test_all_facility_profiles_analyzable(self):
        for facility_key in FACILITY_PROFILES:
            result = self.engine.analyze(
                self.normal_telemetry, facility_type=facility_key
            )
            assert "risk_level" in result

    def test_missing_telemetry_keys(self):
        partial = {"temperature": 20.0}
        result = self.engine.analyze(partial, "general")
        assert isinstance(result, dict)
        assert "risk_level" in result
