"""Tests for Zweather.industrial.engine"""
import pytest
from Zweather.industrial.engine import IndustrialEngine
from Zweather.industrial.models import (
    FACILITY_PROFILES,
    EquipmentAssessment,
    OperationalWindow,
)


class TestIndustrialEngine:
    def setup_method(self):
        self.engine = IndustrialEngine()
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

    def test_equipment_safety_assessment(self):
        result = self.engine.assess_equipment_safety(self.normal_telemetry)
        assert isinstance(result, EquipmentAssessment)
        assert 0.0 <= result.thermal_stress_index <= 1.0
        assert 0.0 <= result.corrosion_risk_index <= 1.0
        assert 0.0 <= result.worker_heat_index <= 1.0
        assert 0.0 <= result.worker_cold_index <= 1.0
        assert isinstance(result.ppe_recommendations, list)
        assert len(result.ppe_recommendations) > 0

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

    def test_weather_hazard_detection(self):
        hazards = self.engine.detect_weather_hazards(
            self.normal_telemetry, "general"
        )
        assert isinstance(hazards, list)

    def test_extreme_wind_hazard(self):
        windy = {**self.normal_telemetry, "wind_speed": 25.0}
        hazards = self.engine.detect_weather_hazards(windy, "general")
        hazard_names = [h["hazard"] for h in hazards]
        assert "Extreme Wind" in hazard_names

    def test_process_risk_detection(self):
        risks = self.engine.detect_process_risks(self.normal_telemetry, "general")
        assert isinstance(risks, list)

    def test_equipment_overheating_risk(self):
        hot = {**self.normal_telemetry, "temperature": 55.0}
        risks = self.engine.detect_process_risks(hot, "manufacturing")
        process_names = [r["process"] for r in risks]
        assert "Equipment Overheating" in process_names

    def test_all_facility_profiles_analyzable(self):
        for facility_key in FACILITY_PROFILES:
            result = self.engine.analyze(
                self.normal_telemetry, facility_type=facility_key
            )
            assert "risk_level" in result

    def test_missing_telemetry_keys(self):
        """Engine should handle missing keys gracefully."""
        partial = {"temperature": 20.0}
        result = self.engine.analyze(partial, "general")
        assert isinstance(result, dict)

    def test_normal_conditions_safe_to_proceed(self):
        """Normal conditions should allow operations to proceed."""
        result = self.engine.evaluate_operational_window(
            self.normal_telemetry, "general"
        )
        assert result.safe_to_proceed is True
        assert result.risk_level == "low"

    def test_chemical_static_discharge_risk(self):
        """Low humidity should trigger static discharge risk for chemical."""
        dry = {**self.normal_telemetry, "humidity": 20.0}
        risks = self.engine.detect_process_risks(dry, "chemical")
        process_names = [r["process"] for r in risks]
        assert "Static Discharge" in process_names

    def test_aqi_halt(self):
        """High AQI should halt operations."""
        polluted = {**self.normal_telemetry, "aqi": 250.0}
        result = self.engine.evaluate_operational_window(polluted, "general")
        assert result.safe_to_proceed is False
