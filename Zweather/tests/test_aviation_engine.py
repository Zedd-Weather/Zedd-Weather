"""Tests for Zweather.aviation.engine."""
from Zweather.aviation.engine import AviationEngine
from Zweather.aviation.models import AIRCRAFT_PROFILES, RunwayCondition, FlightRisk, IcingAssessment
from Zweather.global_regions.models import UKRegion


class TestAviationEngine:
    def setup_method(self):
        self.engine = AviationEngine()
        self.normal_telemetry = {
            "temperature": 15.0,
            "humidity": 50.0,
            "pressure": 1013.0,
            "wind_speed": 5.0,
            "wind_direction": 180.0,
            "runway_heading": 180.0,
            "visibility_m": 10000.0,
        }

    # Core API

    def test_analyze_returns_dict(self):
        result = self.engine.analyze(self.normal_telemetry)
        assert isinstance(result, dict)
        assert "risk_level" in result
        assert "aircraft" in result
        assert "runway" in result
        assert "flight_risks" in result
        assert "icing" in result

    def test_analyze_with_region(self):
        result = self.engine.analyze(self.normal_telemetry, region="glasgow")
        assert "Glasgow" in result["region"]

    def test_analyze_all_aircraft_types(self):
        for key in AIRCRAFT_PROFILES:
            result = self.engine.analyze(self.normal_telemetry, aircraft=key)
            assert "risk_level" in result

    def test_missing_telemetry_keys(self):
        partial = {"temperature": 15.0}
        result = self.engine.analyze(partial)
        assert isinstance(result, dict)

    # Runway conditions

    def test_runway_normal(self):
        r = self.engine.assess_runway_conditions(self.normal_telemetry)
        assert isinstance(r, RunwayCondition)
        assert r.risk_level in ("low", "medium", "high", "critical")

    def test_runway_high_crosswind(self):
        windy = {**self.normal_telemetry, "wind_speed": 15.0, "wind_direction": 90.0}
        r = self.engine.assess_runway_conditions(windy)
        assert r.risk_level in ("high", "critical")

    def test_runway_wet_surface(self):
        wet = {**self.normal_telemetry, "precipitation": 80.0, "humidity": 95.0}
        r = self.engine.assess_runway_conditions(wet)
        assert r.surface_condition in ("wet", "icy")

    # Icing

    def test_icing_no_risk(self):
        i = self.engine.assess_icing_risk(self.normal_telemetry)
        assert not i.icing_risk
        assert i.intensity == "none"

    def test_icing_risk_cold_wet(self):
        cold = {**self.normal_telemetry, "temperature": -5.0, "humidity": 80.0}
        i = self.engine.assess_icing_risk(cold)
        assert i.icing_risk
        assert i.intensity in ("light", "moderate", "severe")

    def test_icing_severe(self):
        severe = {**self.normal_telemetry, "temperature": -15.0, "humidity": 90.0}
        i = self.engine.assess_icing_risk(severe)
        assert i.icing_risk
        assert i.intensity == "severe"

    # Flight risks

    def test_flight_risks_normal(self):
        risks = self.engine.assess_flight_risks(self.normal_telemetry)
        assert isinstance(risks, list)

    def test_flight_risks_gust(self):
        gusty = {**self.normal_telemetry, "wind_speed": 15.0, "wind_gust": 22.0}
        risks = self.engine.assess_flight_risks(gusty, "light_aircraft")
        critical = [r for r in risks if r.risk_level == "critical"]
        assert len(critical) >= 1

    def test_flight_risks_low_visibility(self):
        fog = {**self.normal_telemetry, "visibility_m": 100.0}
        risks = self.engine.assess_flight_risks(fog)
        critical = [r for r in risks if r.risk_level == "critical"]
        assert len(critical) >= 1

    # Risk level

    def test_risk_level_normal(self):
        risk = self.engine.compute_risk_level(self.normal_telemetry)
        assert risk in ("low", "medium", "high", "critical")

    def test_risk_level_critical_crosswind(self):
        windy = {**self.normal_telemetry, "wind_speed": 20.0, "wind_direction": 90.0}
        runway = self.engine.assess_runway_conditions(windy, "light_aircraft")
        risks = self.engine.assess_flight_risks(windy, "light_aircraft")
        icing = self.engine.assess_icing_risk(windy)
        risk = self.engine.compute_risk_level(windy, "light_aircraft", runway, risks, icing)
        assert risk in ("high", "critical")
