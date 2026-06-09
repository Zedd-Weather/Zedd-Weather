"""Tests for Zweather.transportation.engine."""
from Zweather.transportation.engine import TransportEngine, risk_order
from Zweather.transportation.models import TRANSPORT_PROFILES, RouteCondition, LogisticsRisk, TravelAdvisory
from Zweather.global_regions.models import UKRegion


class TestTransportEngine:
    def setup_method(self):
        self.engine = TransportEngine()
        self.normal_telemetry = {
            "temperature": 15.0,
            "humidity": 50.0,
            "pressure": 1013.0,
            "wind_speed": 5.0,
            "precipitation": 10.0,
            "visibility_m": 10000.0,
        }

    # Core API

    def test_analyze_returns_dict(self):
        result = self.engine.analyze(self.normal_telemetry)
        assert isinstance(result, dict)
        assert "risk_level" in result
        assert "transport_mode" in result
        assert "route" in result
        assert "logistics_risks" in result
        assert "advisories" in result

    def test_analyze_with_region(self):
        result = self.engine.analyze(self.normal_telemetry, region="manchester")
        assert result["region"] == "Northern England"

    def test_analyze_with_season(self):
        result = self.engine.analyze(self.normal_telemetry, season="winter")
        assert result["season"] == "winter"

    def test_analyze_all_modes(self):
        for key in TRANSPORT_PROFILES:
            result = self.engine.analyze(self.normal_telemetry, transport_mode=key)
            assert "risk_level" in result

    def test_missing_telemetry_keys(self):
        partial = {"temperature": 15.0}
        result = self.engine.analyze(partial)
        assert isinstance(result, dict)

    # Route conditions

    def test_route_normal(self):
        r = self.engine.assess_route_conditions(self.normal_telemetry)
        assert isinstance(r, RouteCondition)
        assert r.risk_level in ("low", "medium", "high", "critical")

    def test_route_wet(self):
        wet = {**self.normal_telemetry, "precipitation": 60.0}
        r = self.engine.assess_route_conditions(wet)
        assert r.surface_condition in ("wet", "icy", "flooded")

    def test_route_icy(self):
        icy = {**self.normal_telemetry, "temperature": -3.0, "precipitation": 80.0}
        r = self.engine.assess_route_conditions(icy)
        assert r.surface_condition in ("icy", "flooded")

    def test_route_fog(self):
        fog = {**self.normal_telemetry, "visibility_m": 50.0}
        r = self.engine.assess_route_conditions(fog)
        assert r.visibility_condition in ("fog", "dense_fog")

    # Logistics risks

    def test_logistics_risks_normal(self):
        risks = self.engine.assess_logistics_risks(self.normal_telemetry)
        assert isinstance(risks, list)

    def test_logistics_risks_high_wind(self):
        windy = {**self.normal_telemetry, "wind_speed": 20.0}
        risks = self.engine.assess_logistics_risks(windy, "road")
        high = [r for r in risks if r.risk == "high_wind"]
        assert len(high) >= 1

    def test_logistics_risks_extreme_cold(self):
        cold = {**self.normal_telemetry, "temperature": -20.0}
        risks = self.engine.assess_logistics_risks(cold)
        cold_risks = [r for r in risks if r.risk == "extreme_cold"]
        assert len(cold_risks) >= 1

    def test_logistics_risks_heat(self):
        hot = {**self.normal_telemetry, "temperature": 48.0}
        risks = self.engine.assess_logistics_risks(hot)
        heat_risks = [r for r in risks if r.risk == "extreme_heat"]
        assert len(heat_risks) >= 1

    def test_logistics_risks_black_ice(self):
        icy = {**self.normal_telemetry, "temperature": 2.0, "humidity": 85.0}
        risks = self.engine.assess_logistics_risks(icy, "road")
        ice = [r for r in risks if r.risk == "black_ice"]
        assert len(ice) >= 1

    def test_logistics_risks_poor_aqi(self):
        bad = {**self.normal_telemetry, "aqi": 200.0}
        risks = self.engine.assess_logistics_risks(bad, "road")
        aqi_risks = [r for r in risks if r.risk == "poor_air_quality"]
        assert len(aqi_risks) >= 1

    # Advisories

    def test_advisories_normal(self):
        ad = self.engine.generate_advisories(self.normal_telemetry)
        assert isinstance(ad, list)

    def test_advisories_high_wind(self):
        windy = {**self.normal_telemetry, "wind_speed": 20.0}
        ad = self.engine.generate_advisories(windy, "road")
        warnings = [a for a in ad if a.advisory == "high_wind_warning"]
        assert len(warnings) >= 1

    def test_advisories_snow(self):
        snowy = {**self.normal_telemetry, "temperature": -3.0, "precipitation": 80.0}
        ad = self.engine.generate_advisories(snowy)
        snow = [a for a in ad if a.advisory == "snow_ice_warning"]
        assert len(snow) >= 1

    # Risk level

    def test_risk_level_normal(self):
        risk = self.engine.compute_risk_level(self.normal_telemetry)
        assert risk in ("low", "medium", "high", "critical")

    def test_risk_order(self):
        assert risk_order("low", "high") == "high"
        assert risk_order("critical", "low") == "critical"
        assert risk_order("medium", "medium") == "medium"
