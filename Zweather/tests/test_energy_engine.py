"""Tests for Zweather.energy.engine."""
from Zweather.energy.engine import EnergyEngine
from Zweather.energy.models import ENERGY_ASSET_PROFILES, GridStabilityAssessment, GenerationForecast, EnergyHazard
from Zweather.global_regions.models import UKRegion


class TestEnergyEngine:
    def setup_method(self):
        self.engine = EnergyEngine()
        self.normal_telemetry = {
            "temperature": 20.0,
            "humidity": 50.0,
            "pressure": 1013.0,
            "wind_speed": 6.0,
            "solar_irradiance_wm2": 600.0,
            "precipitation": 10.0,
        }

    # Core API

    def test_analyze_returns_dict(self):
        result = self.engine.analyze(self.normal_telemetry)
        assert isinstance(result, dict)
        assert "risk_level" in result
        assert "asset" in result
        assert "grid_stability" in result
        assert "generation_forecast" in result
        assert "hazards" in result

    def test_analyze_with_region(self):
        result = self.engine.analyze(self.normal_telemetry, region="edinburgh")
        assert "Edinburgh" in result["region"]

    def test_analyze_all_asset_types(self):
        for key in ENERGY_ASSET_PROFILES:
            result = self.engine.analyze(self.normal_telemetry, asset=key)
            assert "risk_level" in result

    def test_missing_telemetry_keys(self):
        partial = {"temperature": 20.0}
        result = self.engine.analyze(partial)
        assert isinstance(result, dict)

    # Grid stability

    def test_grid_stability_normal(self):
        g = self.engine.assess_grid_stability(self.normal_telemetry)
        assert isinstance(g, GridStabilityAssessment)
        assert g.risk_level in ("low", "medium", "high")

    def test_grid_stability_heatwave(self):
        hot = {**self.normal_telemetry, "temperature": 38.0}
        g = self.engine.assess_grid_stability(hot)
        assert g.demand_pressure == "high"

    def test_grid_stability_storm(self):
        storm = {**self.normal_telemetry, "pressure": 980.0}
        g = self.engine.assess_grid_stability(storm)
        assert g.volatility_risk == "high"

    # Generation forecast

    def test_forecast_solar(self):
        f = self.engine.forecast_generation(self.normal_telemetry, "solar_farm")
        assert isinstance(f, GenerationForecast)
        assert f.estimated_output_mw > 0
        assert f.capacity_factor_pct > 0

    def test_forecast_wind_optimal(self):
        windy = {**self.normal_telemetry, "wind_speed": 12.0}
        f = self.engine.forecast_generation(windy, "wind_farm")
        assert f.estimated_output_mw > 0

    def test_forecast_wind_cut_out(self):
        storm = {**self.normal_telemetry, "wind_speed": 30.0}
        f = self.engine.forecast_generation(storm, "wind_farm")
        assert f.estimated_output_mw == 0.0

    def test_forecast_wind_cut_in(self):
        calm = {**self.normal_telemetry, "wind_speed": 1.0}
        f = self.engine.forecast_generation(calm, "wind_farm")
        assert f.estimated_output_mw == 0.0

    # Energy hazards

    def test_hazards_normal(self):
        hazards = self.engine.detect_energy_hazards(self.normal_telemetry)
        assert isinstance(hazards, list)

    def test_hazards_extreme_wind(self):
        extreme = {**self.normal_telemetry, "wind_speed": 45.0}
        hazards = self.engine.detect_energy_hazards(extreme, "wind_farm")
        assert len(hazards) >= 1
        assert hazards[0].hazard == "extreme_wind"

    def test_hazards_overheating(self):
        hot = {**self.normal_telemetry, "temperature": 50.0}
        hazards = self.engine.detect_energy_hazards(hot)
        wind = [h for h in hazards if h.hazard == "overheating"]
        assert len(wind) >= 1

    def test_hazards_freezing(self):
        cold = {**self.normal_telemetry, "temperature": -25.0}
        hazards = self.engine.detect_energy_hazards(cold)
        freeze = [h for h in hazards if h.hazard == "freezing"]
        assert len(freeze) >= 1

    # Risk level

    def test_risk_level_normal(self):
        risk = self.engine.compute_risk_level(self.normal_telemetry)
        assert risk in ("low", "medium", "high", "critical")
