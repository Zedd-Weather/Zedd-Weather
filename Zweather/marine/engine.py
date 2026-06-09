"""
Marine intelligence engine for Zedd Weather.
Heuristic-based analysis of telemetry data for maritime and offshore
safety assessments, sea state evaluation, and vessel operational windows.
"""
from Zweather.utils import compute_wind_chill
from Zweather.global_regions.regions import (
    get_region,
    resolve_season,
    region_adjusted_wind_threshold,
    region_adjusted_cold_threshold,
)
from Zweather.global_regions.models import UKRegion, Season

from .models import (
    VesselProfile,
    VESSEL_PROFILES,
    SeaStateAssessment,
    VesselSafety,
    MarineHazard,
    BeaufortScale,
)


class MarineEngine:

    _GALE_WIND_MS = 17.2
    _STORM_WIND_MS = 24.5
    _HIGH_SWELL_M = 3.0
    _EXTREME_SWELL_M = 5.0

    def analyze(
        self,
        telemetry: dict,
        vessel: str = "general",
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> dict:
        profile = self._get_profile(vessel)
        rp = get_region(region)
        sn = resolve_season(season)

        sea_state = self.assess_sea_state(telemetry, region)
        vessel_safety = self.assess_vessel_safety(telemetry, profile, region)
        hazards = self.detect_marine_hazards(telemetry, profile, region, season)
        risk_level = self.compute_risk_level(telemetry, profile, region, season)

        recommendations = self._build_recommendations(
            telemetry, profile, sea_state, vessel_safety, hazards,
        )

        return {
            "vessel": vessel,
            "vessel_name": profile.name,
            "risk_level": risk_level,
            "region": rp.name,
            "season": sn.value,
            "sea_state": {
                "beaufort": sea_state.beaufort,
                "beaufort_number": sea_state.beaufort_number,
                "wind_wave_risk": sea_state.wind_wave_risk,
                "swell_estimate_m": sea_state.swell_estimate_m,
                "navigation_risk": sea_state.navigation_risk,
                "recommendation": sea_state.recommendation,
            },
            "vessel_safety": {
                "icing_risk": vessel_safety.icing_risk,
                "deck_operation_safe": vessel_safety.deck_operation_safe,
                "cargo_transfer_safe": vessel_safety.cargo_transfer_safe,
                "stability_concern": vessel_safety.stability_concern,
                "wind_warning": vessel_safety.wind_warning,
                "recommendations": vessel_safety.recommendations,
            },
            "marine_hazards": [
                {"hazard": h.hazard, "risk_level": h.risk_level,
                 "condition": h.condition, "recommendation": h.recommendation,
                 "affected_operations": h.affected_operations}
                for h in hazards
            ],
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Sea state
    # ------------------------------------------------------------------

    def assess_sea_state(
        self,
        telemetry: dict,
        region: str | UKRegion | None = None,
    ) -> SeaStateAssessment:
        rp = get_region(region)
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        pressure = float(telemetry.get("pressure", 1013.0))
        wave_height = float(telemetry.get("wave_height_m", 0.0))

        beaufort = BeaufortScale.from_wind_speed(wind_speed)
        wind_adjusted = region_adjusted_wind_threshold(wind_speed, rp)
        effective_wind = max(wind_speed, wind_adjusted - rp.wind_threshold_adjustment)

        # Estimate swell from wind if not directly measured
        if wave_height == 0.0:
            swell = max(0.0, (effective_wind * 0.15) - 0.5)
        else:
            swell = wave_height

        # Wind-wave risk
        if effective_wind > self._STORM_WIND_MS:
            wind_wave_risk = "critical"
        elif effective_wind > self._GALE_WIND_MS:
            wind_wave_risk = "high"
        elif effective_wind > 13.8:
            wind_wave_risk = "medium"
        else:
            wind_wave_risk = "low"

        # Navigation risk
        if wind_wave_risk == "critical" or pressure < 990.0:
            nav_risk = "critical"
        elif wind_wave_risk == "high":
            nav_risk = "high"
        elif wind_wave_risk == "medium":
            nav_risk = "medium"
        else:
            nav_risk = "low"

        # Recommendation
        if nav_risk == "critical":
            rec = "Remain in port or seek shelter immediately. Avoid all navigation."
        elif nav_risk == "high":
            rec = "Coastal navigation only. Small craft should remain in port."
        elif nav_risk == "medium":
            rec = "Exercise caution. Monitor weather radar for deteriorating conditions."
        else:
            rec = "Conditions favourable for navigation. Continue routine watch."

        return SeaStateAssessment(
            beaufort=beaufort.bf_name,
            beaufort_number=beaufort.number,
            wind_wave_risk=wind_wave_risk,
            swell_estimate_m=round(swell, 1),
            navigation_risk=nav_risk,
            recommendation=rec,
        )

    # ------------------------------------------------------------------
    # Vessel safety
    # ------------------------------------------------------------------

    def assess_vessel_safety(
        self,
        telemetry: dict,
        vessel: str | VesselProfile | None = None,
        region: str | UKRegion | None = None,
    ) -> VesselSafety:
        profile = self._resolve_profile(vessel)
        rp = get_region(region)

        temp = float(telemetry.get("temperature", 20.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        wave_height = float(telemetry.get("wave_height_m", 0.0))
        visibility_m = float(telemetry.get("visibility_m", 9999.0))

        wind_adjusted = region_adjusted_wind_threshold(wind_speed, rp)

        # Icing risk
        wind_chill = compute_wind_chill(temp, wind_speed)
        icing = wind_chill < profile.ice_formation_temp_c and wind_speed > 5.0

        # Deck operations
        deck_safe = wind_adjusted <= profile.max_operational_wind and wave_height <= profile.max_operational_wave_m

        # Cargo transfer
        cargo_safe = wind_adjusted <= profile.max_operational_wind * 0.8 and wave_height <= profile.max_operational_wave_m * 0.7

        # Stability
        stability_concern = (wind_adjusted > profile.max_safe_wind or wave_height > profile.max_safe_wave_m)

        # Wind warning
        if wind_adjusted > profile.max_safe_wind:
            wind_warning = f"Wind {wind_speed:.1f} m/s exceeds vessel safe limit ({profile.max_safe_wind:.1f} m/s)"
        elif wind_adjusted > profile.max_operational_wind:
            wind_warning = f"Wind {wind_speed:.1f} m/s exceeds operational limit ({profile.max_operational_wind:.1f} m/s)"
        else:
            wind_warning = None

        # Recommendations
        recs: list[str] = []
        if icing:
            recs.append("Ice formation risk — activate de-icing systems. Monitor deck for slippery conditions.")
        if not deck_safe:
            recs.append("Deck operations restricted due to wind/wave conditions. Secure all loose deck items.")
        if not cargo_safe:
            recs.append("Cargo transfer unsafe. Secure hatches and postpone transfer operations.")
        if stability_concern:
            recs.append("Stability risk — check ballast and secure cargo. Reduce speed if necessary.")
        if visibility_m < profile.min_operational_visibility_m:
            recs.append(f"Visibility reduced ({visibility_m:.0f} m) — sound fog signals, reduce speed, use radar.")
        if wind_adjusted > profile.storm_avoidance_wind_ms:
            recs.append("Storm conditions — alter course to avoid worst weather. Notify shore authorities.")
        if not recs:
            recs.append("Vessel conditions are safe. Continue normal operations.")

        return VesselSafety(
            icing_risk=icing,
            deck_operation_safe=deck_safe,
            cargo_transfer_safe=cargo_safe,
            stability_concern=stability_concern,
            wind_warning=wind_warning,
            recommendations=recs,
        )

    # ------------------------------------------------------------------
    # Marine hazards
    # ------------------------------------------------------------------

    def detect_marine_hazards(
        self,
        telemetry: dict,
        vessel: str | VesselProfile | None = None,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> list[MarineHazard]:
        profile = self._resolve_profile(vessel)
        rp = get_region(region)
        sn = resolve_season(season)

        temp = float(telemetry.get("temperature", 20.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        pressure = float(telemetry.get("pressure", 1013.0))
        wave_height = float(telemetry.get("wave_height_m", 0.0))
        visibility_m = float(telemetry.get("visibility_m", 9999.0))
        rainfall_mm = float(telemetry.get("rainfall_mm", 0.0))

        wind_adjusted = region_adjusted_wind_threshold(wind_speed, rp)
        cold_caution = region_adjusted_cold_threshold(5.0, rp, sn)

        hazards: list[MarineHazard] = []

        # Gale / storm
        if wind_adjusted > self._STORM_WIND_MS:
            hazards.append(MarineHazard(
                hazard="Storm Force Winds",
                risk_level="critical",
                condition=f"Wind {wind_speed:.1f} m/s — storm force. Beaufort {BeaufortScale.from_wind_speed(wind_speed).number}",
                recommendation="Heave to or seek immediate shelter. Batten down all hatches.",
                affected_operations=["open_sea_transit", "coastal_navigation", "fishing", "offshore_work"],
            ))
        elif wind_adjusted > self._GALE_WIND_MS:
            hazards.append(MarineHazard(
                hazard="Gale Force Winds",
                risk_level="high",
                condition=f"Wind {wind_speed:.1f} m/s — gale force. Secure deck and reduce speed.",
                recommendation="Seek shelter if possible. Secure all deck cargo. Warn crew for heavy weather.",
                affected_operations=["fishing", "pleasure_craft", "coastal_navigation"],
            ))

        # Storm / low pressure
        if pressure < 985.0:
            hazards.append(MarineHazard(
                hazard="Deep Low Pressure / Storm System",
                risk_level="critical",
                condition=f"Pressure {pressure:.1f} hPa — deep low. Severe weather expected.",
                recommendation="Alter course to avoid storm centre. Prepare heavy weather procedures.",
            ))

        # High swell
        if wave_height > self._EXTREME_SWELL_M:
            hazards.append(MarineHazard(
                hazard="Extreme Swell",
                risk_level="critical",
                condition=f"Swell {wave_height:.1f} m — extreme. Risk of broaching and cargo shift.",
                recommendation="Reduce speed. Alter course to take swell on the bow. Check lashings.",
            ))
        elif wave_height > self._HIGH_SWELL_M:
            hazards.append(MarineHazard(
                hazard="High Swell",
                risk_level="high",
                condition=f"Swell {wave_height:.1f} m — elevated roll risk.",
                recommendation="Reduce speed. Secure loose items. Exercise caution on deck.",
            ))

        # Dense fog
        if visibility_m < 100.0:
            hazards.append(MarineHazard(
                hazard="Dense Fog",
                risk_level="critical",
                condition=f"Visibility {visibility_m:.0f} m — dangerous for navigation",
                recommendation="Sound fog signals. Reduce to safe speed. Use radar. Station lookout forward.",
                affected_operations=["open_sea_transit", "coastal_navigation", "port_entry"],
            ))
        elif visibility_m < profile.min_operational_visibility_m:
            hazards.append(MarineHazard(
                hazard="Reduced Visibility",
                risk_level="medium",
                condition=f"Visibility {visibility_m:.0f} m — below operational threshold",
                recommendation="Proceed with caution. Use navigation lights and radar.",
            ))

        # Icing
        if temp < profile.ice_formation_temp_c and wind_speed > 5.0:
            wc = compute_wind_chill(temp, wind_speed)
            hazards.append(MarineHazard(
                hazard="Vessel Icing",
                risk_level="high" if wc < -10.0 else "medium",
                condition=f"Temp {temp:.1f}°C, wind {wind_speed:.1f} m/s — ice accretion risk. Wind chill {wc:.1f}°C",
                recommendation="Activate de-icing. Keep crew off exposed decks. Monitor stability from ice accumulation.",
                affected_operations=["deck_operations", "fishing"],
            ))

        # Lightning / electrical storm
        if pressure < 995.0 and float(telemetry.get("humidity", 60.0)) > 75.0:
            hazards.append(MarineHazard(
                hazard="Electrical Storm Risk",
                risk_level="medium",
                condition=f"Low pressure ({pressure:.1f} hPa) with high humidity — thunderstorm risk",
                recommendation="Secure electronic equipment. Avoid open deck during storm. Check lightning protection.",
            ))

        if not hazards:
            hazards.append(MarineHazard(
                hazard="None identified",
                risk_level="low",
                condition="Conditions are safe for maritime operations.",
                recommendation="Continue routine navigation and vessel monitoring.",
            ))

        return hazards

    # ------------------------------------------------------------------
    # Risk level
    # ------------------------------------------------------------------

    def compute_risk_level(
        self,
        telemetry: dict,
        vessel: str | VesselProfile | None = None,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> str:
        sea_state = self.assess_sea_state(telemetry, region)
        vessel_safety = self.assess_vessel_safety(telemetry, vessel, region)
        hazards = self.detect_marine_hazards(telemetry, vessel, region, season)

        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        current = risk_order.get(sea_state.navigation_risk, 0)

        for h in hazards:
            current = max(current, risk_order.get(h.risk_level, 0))

        if vessel_safety.stability_concern:
            current = max(current, risk_order["high"])
        if vessel_safety.icing_risk:
            current = max(current, risk_order["high"])

        levels = {v: k for k, v in risk_order.items()}
        return levels[current]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_profile(self, vessel: str) -> VesselProfile:
        return VESSEL_PROFILES.get(vessel.lower(), VESSEL_PROFILES["general"])

    def _resolve_profile(self, v: str | VesselProfile | None) -> VesselProfile:
        if v is None or isinstance(v, str):
            return self._get_profile(v or "general")
        return v

    def _build_recommendations(
        self,
        telemetry: dict,
        profile: VesselProfile,
        sea_state: SeaStateAssessment,
        vessel_safety: VesselSafety,
        hazards: list[MarineHazard],
    ) -> list[str]:
        recs: list[str] = []

        for h in hazards:
            if h.risk_level in ("high", "critical"):
                recs.append(f"{h.hazard}: {h.recommendation}")

        for r in vessel_safety.recommendations:
            recs.append(r)

        if sea_state.navigation_risk in ("high", "critical"):
            recs.append(f"Navigation: {sea_state.recommendation}")

        if not recs:
            recs.append("All conditions nominal. Continue safe navigation.")

        return recs
