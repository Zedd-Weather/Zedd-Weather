"""
Aviation intelligence engine for Zedd Weather.
Heuristic-based analysis of telemetry data for aviation safety,
flight risk assessment, and operational decision support.
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
    AircraftProfile,
    AIRCRAFT_PROFILES,
    AircraftType,
    OperationType,
    RunwayCondition,
    FlightRisk,
    IcingAssessment,
)


class AviationEngine:

    _FREEZING_TEMP_C = 2.0
    _SEVERE_ICING_TEMP_C = -10.0
    _THUNDERSTORM_DELTA_P = 5.0
    _LOW_VISIBILITY_M = 2000.0
    _CRITICAL_VISIBILITY_M = 400.0
    _WIND_SHEAR_WARNING_MS = 5.0
    _WIND_SHEAR_CRITICAL_MS = 10.0
    _LIGHTNING_DISTANCE_KM = 16.0

    def analyze(
        self,
        telemetry: dict,
        aircraft: str = "general",
        operation: str = "general",
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> dict:
        profile = self._get_profile(aircraft)
        rp = get_region(region)

        runway = self.assess_runway_conditions(telemetry, profile, operation)
        flight_risks = self.assess_flight_risks(telemetry, profile, operation, region, season)
        icing = self.assess_icing_risk(telemetry, region, season)
        risk_level = self.compute_risk_level(
            telemetry, profile, runway, flight_risks, icing,
        )

        recommendations = self._build_recommendations(
            profile, runway, flight_risks, icing,
        )

        return {
            "aircraft": aircraft,
            "aircraft_name": profile.name,
            "risk_level": risk_level,
            "region": rp.name,
            "operation": operation,
            "runway": {
                "crosswind_ms": runway.crosswind_ms,
                "tailwind_ms": runway.tailwind_ms,
                "headwind_ms": runway.headwind_ms,
                "surface_condition": runway.surface_condition,
                "braking_action": runway.braking_action,
                "risk_level": runway.risk_level,
                "recommendation": runway.recommendation,
            },
            "flight_risks": [
                {"phase": r.phase, "risk_level": r.risk_level,
                 "factor": r.factor, "value": r.value,
                 "threshold": r.threshold, "recommendation": r.recommendation}
                for r in flight_risks
            ],
            "icing": {
                "icing_risk": icing.icing_risk,
                "intensity": icing.intensity,
                "altitude_range": icing.altitude_range,
                "recommendation": icing.recommendation,
            },
            "recommendations": recommendations,
        }

    def assess_runway_conditions(
        self,
        telemetry: dict,
        aircraft: str | AircraftProfile | None = None,
        operation: str = "general",
    ) -> RunwayCondition:
        profile = self._resolve_profile(aircraft)
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        wind_dir = float(telemetry.get("wind_direction", 0.0))
        runway_hdg = float(telemetry.get("runway_heading", 0.0))
        temp = float(telemetry.get("temperature", 15.0))
        precip = float(telemetry.get("precipitation", 0.0))
        humidity = float(telemetry.get("humidity", 50.0))

        crosswind = abs(wind_speed * wind_dir - runway_hdg)
        tailwind = wind_speed * (wind_dir - runway_hdg)
        headwind = wind_speed * (runway_hdg - wind_dir)

        surface = "dry"
        braking = "good"
        if precip > 50 or humidity > 90:
            surface = "wet"
            braking = "good"
        if precip > 80 or (temp < 2.0 and humidity > 85):
            surface = "icy"
            braking = "poor"

        risk = "low"
        rec = f"Runway {surface}, braking {braking}."
        if crosswind > profile.max_crosswind_ms:
            risk = "critical"
            rec += f" Crosswind {crosswind:.1f} m/s exceeds {profile.name} limit."
        elif crosswind > profile.max_crosswind_ms * 0.8:
            risk = "high"
            rec += f" Crosswind {crosswind:.1f} m/s approaching limit."

        op_type = OperationType.GENERAL
        try:
            op_type = OperationType(operation)
        except ValueError:
            pass

        return RunwayCondition(
            operation=op_type,
            crosswind_ms=round(crosswind, 1),
            tailwind_ms=round(tailwind, 1),
            headwind_ms=round(headwind, 1),
            surface_condition=surface,
            braking_action=braking,
            risk_level=risk,
            recommendation=rec,
        )

    def assess_flight_risks(
        self,
        telemetry: dict,
        aircraft: str | AircraftProfile | None = None,
        operation: str = "general",
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> list[FlightRisk]:
        profile = self._resolve_profile(aircraft)
        rp = get_region(region)
        sn = resolve_season(season)
        risks: list[FlightRisk] = []

        wind_speed = float(telemetry.get("wind_speed", 0.0))
        gust = float(telemetry.get("wind_gust", wind_speed))
        visibility = float(telemetry.get("visibility_m", 10000.0))
        temp = float(telemetry.get("temperature", 15.0))
        pressure = float(telemetry.get("pressure", 1013.0))
        humidity = float(telemetry.get("humidity", 50.0))

        wind_adjusted = region_adjusted_wind_threshold(wind_speed, rp)

        if gust > profile.max_gust_ms:
            risks.append(FlightRisk(
                phase=operation, risk_level="critical",
                factor="gust_wind", value=gust,
                threshold=profile.max_gust_ms,
                recommendation=f"Gust {gust:.1f} m/s exceeds {profile.name} limit.",
            ))
        elif gust > profile.max_gust_ms * 0.8:
            risks.append(FlightRisk(
                phase=operation, risk_level="high",
                factor="gust_wind", value=gust,
                threshold=profile.max_gust_ms,
                recommendation="Strong gusts — exercise caution.",
            ))

        if wind_speed > 5.0 and temp < self._FREEZING_TEMP_C:
            wc = compute_wind_chill(temp, wind_speed)
            if wc < -15.0:
                risks.append(FlightRisk(
                    phase=operation, risk_level="high",
                    factor="extreme_wind_chill", value=wc,
                    threshold=-15.0,
                    recommendation="Extreme wind chill — ground crew limits apply.",
                ))

        if visibility < profile.min_visibility_m:
            risks.append(FlightRisk(
                phase=operation, risk_level="critical",
                factor="visibility", value=visibility,
                threshold=profile.min_visibility_m,
                recommendation="Below minimum visibility for safe operation.",
            ))
        elif visibility < self._LOW_VISIBILITY_M:
            risks.append(FlightRisk(
                phase=operation, risk_level="medium",
                factor="visibility", value=visibility,
                threshold=self._LOW_VISIBILITY_M,
                recommendation="Reduced visibility — IFR required.",
            ))

        if wind_speed > 5.0 and (wind_adjusted - wind_speed) > self._WIND_SHEAR_WARNING_MS:
            shear = wind_adjusted - wind_speed
            level = "critical" if shear > self._WIND_SHEAR_CRITICAL_MS else "high"
            risks.append(FlightRisk(
                phase=operation, risk_level=level,
                factor="wind_shear", value=shear,
                threshold=self._WIND_SHEAR_WARNING_MS,
                recommendation="Wind shear potential detected.",
            ))

        if pressure < 1005.0 and humidity > 80:
            risks.append(FlightRisk(
                phase=operation, risk_level="high",
                factor="thunderstorm_potential",
                value=pressure, threshold=1005.0,
                recommendation="Thunderstorm potential — check radar.",
            ))

        return risks

    def assess_icing_risk(
        self,
        telemetry: dict,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> IcingAssessment:
        rp = get_region(region)
        sn = resolve_season(season)
        temp = float(telemetry.get("temperature", 15.0))
        humidity = float(telemetry.get("humidity", 50.0))
        altitude_m = float(telemetry.get("altitude_m", 0.0))

        risk = False
        intensity = "none"
        alt_range = "N/A"
        rec = "No icing risk."

        cold_adjusted = region_adjusted_cold_threshold(temp, rp, sn)

        if cold_adjusted < self._FREEZING_TEMP_C and humidity > 60:
            risk = True
            if cold_adjusted < self._SEVERE_ICING_TEMP_C:
                intensity = "severe"
                alt_range = f"{int(altitude_m)}–{int(altitude_m + 1500)}m"
                rec = "Severe icing conditions — avoid if possible."
            elif cold_adjusted < 0:
                intensity = "moderate"
                alt_range = f"{int(altitude_m)}–{int(altitude_m + 1000)}m"
                rec = "Moderate icing — activate anti-ice systems."
            else:
                intensity = "light"
                alt_range = f"{int(altitude_m)}–{int(altitude_m + 500)}m"
                rec = "Light icing possible — monitor conditions."

        return IcingAssessment(
            icing_risk=risk,
            intensity=intensity,
            altitude_range=alt_range,
            recommendation=rec,
        )

    def compute_risk_level(
        self,
        telemetry: dict,
        aircraft: str | AircraftProfile | None = None,
        runway: RunwayCondition | None = None,
        flight_risks: list[FlightRisk] | None = None,
        icing: IcingAssessment | None = None,
    ) -> str:
        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        current = risk_order.get("low", 0)

        if runway and runway.risk_level != "low":
            current = max(current, risk_order.get(runway.risk_level, 0))

        for r in (flight_risks or []):
            current = max(current, risk_order.get(r.risk_level, 0))

        if icing and icing.icing_risk:
            if icing.intensity == "severe":
                current = max(current, risk_order["critical"])
            elif icing.intensity == "moderate":
                current = max(current, risk_order["high"])

        levels = {v: k for k, v in risk_order.items()}
        return levels[current]

    def _get_profile(self, aircraft: str) -> AircraftProfile:
        return AIRCRAFT_PROFILES.get(aircraft, AIRCRAFT_PROFILES["general"])

    def _resolve_profile(
        self, aircraft: str | AircraftProfile | None
    ) -> AircraftProfile:
        if isinstance(aircraft, AircraftProfile):
            return aircraft
        return self._get_profile(aircraft or "general")

    def _build_recommendations(
        self,
        profile: AircraftProfile,
        runway: RunwayCondition,
        flight_risks: list[FlightRisk],
        icing: IcingAssessment,
    ) -> list[str]:
        recs = []
        if runway.risk_level != "low":
            recs.append(runway.recommendation)
        for r in flight_risks:
            if r.risk_level in ("high", "critical"):
                recs.append(r.recommendation)
        if icing.icing_risk:
            recs.append(icing.recommendation)
        if not recs:
            recs.append(f"Conditions suitable for {profile.name} operations.")
        return recs
