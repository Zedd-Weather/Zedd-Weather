"""Tests for Zweather.agricultural.engine"""
import pytest
from Zweather.agricultural.engine import AgriculturalEngine
from Zweather.agricultural.models import CROP_PROFILES, IrrigationSchedule, SoilMoisturePrediction


class TestAgriculturalEngine:
    def setup_method(self):
        self.engine = AgriculturalEngine()
        # Engine reads keys: "temperature", "humidity", "pressure"
        self.normal_telemetry = {
            "temperature": 22.0,
            "humidity": 65.0,
            "pressure": 1013.0,
        }

    def test_analyze_returns_dict(self):
        result = self.engine.analyze(self.normal_telemetry)
        assert isinstance(result, dict)
        assert "risk_level" in result

    def test_risk_level_normal_conditions(self):
        risk = self.engine.compute_risk_level(self.normal_telemetry, "maize")
        assert risk in ("low", "medium", "high", "critical")

    def test_risk_level_high_temp(self):
        # heat_stress + humidity_stress together push overall to "critical"
        hot = {**self.normal_telemetry, "temperature": 42.0, "humidity": 25.0}
        risk = self.engine.compute_risk_level(hot, "maize")
        assert risk in ("high", "critical")

    def test_risk_level_frost(self):
        freezing = {**self.normal_telemetry, "temperature": -3.0}
        risk = self.engine.compute_risk_level(freezing, "maize")
        assert risk in ("high", "critical")

    def test_soil_moisture_prediction(self):
        result = self.engine.predict_soil_moisture(self.normal_telemetry)
        assert isinstance(result, SoilMoisturePrediction)
        assert 0.0 <= result.estimated_vwc_pct <= 100.0
        assert 0.0 <= result.confidence <= 1.0
        assert result.days_to_irrigation >= 0

    def test_irrigation_schedule(self):
        result = self.engine.irrigation_schedule(self.normal_telemetry, "maize")
        assert isinstance(result, IrrigationSchedule)
        assert result.urgency in ("none", "low", "medium", "high", "critical")

    def test_drought_triggers_irrigation(self):
        # temperature > maize temp_stress_max (35°C) + low humidity → irrigation advised
        dry = {**self.normal_telemetry, "humidity": 15.0, "temperature": 36.0}
        result = self.engine.irrigation_schedule(dry, "maize")
        assert result.recommended is True

    def test_pest_risk_detection(self):
        risks = self.engine.detect_pest_risk(self.normal_telemetry, "maize")
        assert isinstance(risks, list)

    def test_high_humidity_fungal_risk(self):
        humid = {**self.normal_telemetry, "humidity": 92.0, "temperature": 28.0}
        risks = self.engine.detect_pest_risk(humid, "tomato")
        assert isinstance(risks, list)

    def test_disease_risk_detection(self):
        risks = self.engine.detect_disease_risk(self.normal_telemetry, "tomato")
        assert isinstance(risks, list)

    def test_all_crop_profiles_analyzable(self):
        for crop_key in CROP_PROFILES:
            result = self.engine.analyze(self.normal_telemetry, crop=crop_key)
            assert "risk_level" in result

    def test_weather_stress_analysis(self):
        result = self.engine.weather_stress_analysis(self.normal_telemetry, "wheat")
        assert isinstance(result, dict)

    def test_missing_telemetry_keys(self):
        """Engine should handle missing keys gracefully."""
        partial = {"temperature": 20.0}
        result = self.engine.analyze(partial, "maize")
        assert isinstance(result, dict)
