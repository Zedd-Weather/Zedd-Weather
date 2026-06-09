"""Tests for Zweather.marine.engine."""
from Zweather.marine.engine import MarineEngine
from Zweather.marine.models import (
    VESSEL_PROFILES,
    SeaStateAssessment,
    VesselSafety,
    MarineHazard,
)
from Zweather.global_regions.models import UKRegion


class TestMarineEngine:
    def setup_method(self):
        self.engine = MarineEngine()
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

    def test_analyze_with_season(self):
        result = self.engine.analyze(self.normal_telemetry, season="winter")
        assert result["season"] == "winter"

    def test_analyze_all_vessel_types(self):
        for vessel_key in VESSEL_PROFILES:
            result = self.engine.analyze(
                self.normal_telemetry, vessel=vessel_key
            )
            assert "risk_level" in result

    def test_missing_telemetry_keys(self):
        partial = {"temperature": 20.0}
        result = self.engine.analyze(partial, "general")
        assert isinstance(result, dict)
        assert "risk_level" in result

    # ------------------------------------------------------------------
    # Risk level
    # ------------------------------------------------------------------

    def test_risk_level_normal_conditions(self):
        risk = self.engine.compute_risk_level(self.normal_telemetry)
        assert risk in ("low", "medium", "high", "critical")

    def test_risk_level_storm(self):
        stormy = {**self.normal_telemetry, "wind_speed": 28.0, "pressure": 980.0}
        risk = self.engine.compute_risk_level(stormy)
        assert risk in ("high", "critical")

    def test_risk_level_high_wind(self):
        windy = {**self.normal_telemetry, "wind_speed": 18.0}
        risk = self.engine.compute_risk_level(windy)
        assert risk in ("medium", "high", "critical")

    # ------------------------------------------------------------------
    # Sea state
    # ------------------------------------------------------------------

    def test_sea_state_assessment(self):
        result = self.engine.assess_sea_state(self.normal_telemetry)
        assert isinstance(result, SeaStateAssessment)
        assert result.beaufort_number >= 0
        assert result.wind_wave_risk in ("low", "medium", "high", "critical")
        assert result.swell_estimate_m >= 0.0

    def test_calm_conditions_low_risk(self):
        result = self.engine.assess_sea_state(self.normal_telemetry)
        assert result.wind_wave_risk == "low"
        assert result.navigation_risk == "low"

    def test_gale_conditions_high_risk(self):
        gale = {**self.normal_telemetry, "wind_speed": 18.0}
        result = self.engine.assess_sea_state(gale)
        assert result.wind_wave_risk in ("high", "critical")
        assert result.navigation_risk in ("high", "critical")

    def test_storm_critical_risk(self):
        storm = {**self.normal_telemetry, "wind_speed": 26.0}
        result = self.engine.assess_sea_state(storm)
        assert result.wind_wave_risk == "critical"

    def test_beaufort_scale_mapping(self):
        calm = self.engine.assess_sea_state(
            {**self.normal_telemetry, "wind_speed": 0.5}
        )
        assert calm.beaufort_number == 0 or calm.beaufort_number == 1

    # ------------------------------------------------------------------
    # Vessel safety
    # ------------------------------------------------------------------

    def test_vessel_safety_assessment(self):
        result = self.engine.assess_vessel_safety(self.normal_telemetry)
        assert isinstance(result, VesselSafety)
        assert isinstance(result.icing_risk, bool)
        assert isinstance(result.deck_operation_safe, bool)
        assert isinstance(result.cargo_transfer_safe, bool)
        assert isinstance(result.stability_concern, bool)
        assert isinstance(result.recommendations, list)
        assert len(result.recommendations) > 0

    def test_normal_conditions_safe(self):
        result = self.engine.assess_vessel_safety(self.normal_telemetry)
        assert result.deck_operation_safe is True
        assert result.cargo_transfer_safe is True
        assert result.stability_concern is False

    def test_high_wind_affects_deck_ops(self):
        windy = {**self.normal_telemetry, "wind_speed": 18.0}
        result = self.engine.assess_vessel_safety(windy)
        assert result.deck_operation_safe is False

    def test_icing_risk_in_freezing_wind(self):
        icy = {**self.normal_telemetry, "temperature": -5.0, "wind_speed": 8.0}
        result = self.engine.assess_vessel_safety(icy)
        assert result.icing_risk is True

    def test_stability_concern_in_storm(self):
        stormy = {**self.normal_telemetry, "wind_speed": 25.0, "wave_height_m": 5.0}
        result = self.engine.assess_vessel_safety(stormy)
        assert result.stability_concern is True

    def test_fishing_vessel_more_sensitive(self):
        windy = {**self.normal_telemetry, "wind_speed": 14.0}
        general = self.engine.assess_vessel_safety(windy, vessel="general")
        fishing = self.engine.assess_vessel_safety(windy, vessel="fishing_vessel")
        # Fishing vessel has lower wind thresholds
        if fishing.deck_operation_safe != general.deck_operation_safe:
            assert fishing.deck_operation_safe is False

    # ------------------------------------------------------------------
    # Marine hazards
    # ------------------------------------------------------------------

    def test_marine_hazard_detection(self):
        hazards = self.engine.detect_marine_hazards(self.normal_telemetry)
        assert isinstance(hazards, list)
        assert isinstance(hazards[0], MarineHazard)

    def test_storm_hazard_detected(self):
        stormy = {**self.normal_telemetry, "wind_speed": 26.0}
        hazards = self.engine.detect_marine_hazards(stormy)
        names = [h.hazard for h in hazards]
        assert any("storm" in n.lower() or "gale" in n.lower() for n in names)

    def test_fog_hazard(self):
        foggy = {**self.normal_telemetry, "visibility_m": 50.0}
        hazards = self.engine.detect_marine_hazards(foggy)
        names = [h.hazard for h in hazards]
        assert any("fog" in n.lower() for n in names)

    def test_icing_hazard(self):
        icy = {**self.normal_telemetry, "temperature": -3.0, "wind_speed": 8.0}
        hazards = self.engine.detect_marine_hazards(icy)
        names = [h.hazard for h in hazards]
        assert any("icing" in n.lower() or "ice" in n.lower() for n in names)

    def test_high_swell_hazard(self):
        swell = {**self.normal_telemetry, "wave_height_m": 4.0}
        hazards = self.engine.detect_marine_hazards(swell)
        names = [h.hazard for h in hazards]
        assert any("swell" in n.lower() for n in names)
