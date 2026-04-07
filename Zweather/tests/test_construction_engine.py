"""Tests for Zweather.construction.engine"""
import pytest
from Zweather.construction.engine import ConstructionEngine
from Zweather.construction.models import (
    ACTIVITY_PROFILES,
    SafetyAssessment,
    WorkWindow,
)


class TestConstructionEngine:
    def setup_method(self):
        self.engine = ConstructionEngine()
        # Engine reads keys: "temperature", "humidity", "pressure", "wind_speed"
        self.normal_telemetry = {
            "temperature": 22.0,
            "humidity": 55.0,
            "pressure": 1013.0,
            "wind_speed": 3.0,
        }

    def test_analyze_returns_dict(self):
        result = self.engine.analyze(self.normal_telemetry)
        assert isinstance(result, dict)
        assert "risk_level" in result

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

    def test_worker_safety_assessment(self):
        result = self.engine.assess_worker_safety(self.normal_telemetry)
        assert isinstance(result, SafetyAssessment)
        assert 0.0 <= result.heat_stress_index <= 1.0
        assert 0.0 <= result.cold_stress_index <= 1.0
        assert result.hydration_litres_hr > 0.0
        assert isinstance(result.ppe_recommendations, list)
        assert len(result.ppe_recommendations) > 0

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

    def test_weather_hazard_detection(self):
        hazards = self.engine.detect_weather_hazards(self.normal_telemetry, "general")
        assert isinstance(hazards, list)

    def test_extreme_wind_hazard(self):
        windy = {**self.normal_telemetry, "wind_speed": 25.0}
        hazards = self.engine.detect_weather_hazards(windy, "general")
        hazard_names = [h["hazard"] for h in hazards]
        assert "Extreme Wind" in hazard_names

    def test_material_risk_detection(self):
        risks = self.engine.detect_material_risks(self.normal_telemetry, "general")
        assert isinstance(risks, list)

    def test_cold_concrete_risk(self):
        cold = {**self.normal_telemetry, "temperature": 2.0}
        risks = self.engine.detect_material_risks(cold, "concrete_pouring")
        material_names = [r["material"] for r in risks]
        assert "Concrete" in material_names

    def test_all_activity_profiles_analyzable(self):
        for activity_key in ACTIVITY_PROFILES:
            result = self.engine.analyze(self.normal_telemetry, activity=activity_key)
            assert "risk_level" in result

    def test_missing_telemetry_keys(self):
        """Engine should handle missing keys gracefully."""
        partial = {"temperature": 20.0}
        result = self.engine.analyze(partial, "general")
        assert isinstance(result, dict)

    def test_heat_stress_work_rest_ratio(self):
        """Very hot conditions should mandate shorter work periods."""
        hot = {"temperature": 40.0, "humidity": 80.0, "pressure": 1013.0, "wind_speed": 1.0}
        safety = self.engine.assess_worker_safety(hot)
        # With extreme heat, work period should be <= 30 min
        work_mins = int(safety.work_rest_ratio.split(":")[0])
        assert work_mins <= 30

    def test_normal_conditions_safe_to_proceed(self):
        """Normal conditions should allow work to proceed."""
        result = self.engine.evaluate_work_window(self.normal_telemetry, "general")
        assert result.safe_to_proceed is True
        assert result.risk_level == "low"
