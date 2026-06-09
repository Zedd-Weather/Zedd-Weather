"""
Transportation intelligence engine for Zedd Weather.
Heuristic-based analysis of telemetry data for transport sector:
route conditions, logistics risk assessment, and travel advisories.
"""
from Zweather.utils import compute_heat_index, compute_wind_chill
from Zweather.global_regions.regions import (
    get_region,
    resolve_season,
    region_adjusted_heat_threshold,
    region_adjusted_cold_threshold,
    region_adjusted_wind_threshold,
    region_adjusted_rain_threshold,
)
from Zweather.global_regions.models import UKRegion, Season

from .models import (
    TransportProfile,
    TRANSPORT_PROFILES,
    TransportMode,
    RouteType,
    RouteCondition,
    LogisticsRisk,
    TravelAdvisory,
)


class TransportEngine:

    _FOG_HUMIDITY = 85.0
    _FOG_TEMP_DEWPOINT_DELTA = 2.0
    _HEAVY_RAIN_MMH = 20.0
    _EXTREME_RAIN_MMH = 40.0
    _HEATWAVE_C = 35.0
    _FREEZING_C = 2.0
    _HIGH_WIND_MS = 15.0
    _STORM_WIND_MS = 22.0

    def analyze(
        self,
        telemetry: dict,
        transport_mode: str = "general",
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> dict:
        profile = self._get_profile(transport_mode)
        rp = get_region(region)
        sn = resolve_season(season)

        route = self.assess_route_conditions(telemetry, profile, region)
        risks = self.assess_logistics_risks(telemetry, profile, region, season)
        advisories = self.generate_advisories(telemetry, profile, region, route, risks)
        risk_level = self.compute_risk_level(telemetry, profile, route, risks)

        recommendations = self._build_recommendations(
            profile, route, risks, advisories,
        )

        return {
            "transport_mode": transport_mode,
            "mode_name": profile.name,
            "risk_level": risk_level,
            "region": rp.name,
            "season": sn.value,
            "route": {
                "surface_condition": route.surface_condition,
                "visibility_condition": route.visibility_condition,
                "risk_level": route.risk_level,
                "recommendation": route.recommendation,
            },
            "logistics_risks": [
                {"risk": r.risk, "risk_level": r.risk_level,
                 "condition": r.condition, "impact": r.impact,
                 "recommendation": r.recommendation}
                for r in risks
            ],
            "advisories": [
                {"advisory": a.advisory, "severity": a.severity,
                 "affected_routes": a.affected_routes,
                 "duration_hours": a.duration_hours,
                 "recommendation": a.recommendation}
                for a in advisories
            ],
            "recommendations": recommendations,
        }

    def assess_route_conditions(
        self,
        telemetry: dict,
        transport_mode: str | TransportProfile | None = None,
        region: str | UKRegion | None = None,
    ) -> RouteCondition:
        profile = self._resolve_profile(transport_mode)
        rp = get_region(region)

        temp = float(telemetry.get("temperature", 15.0))
        humidity = float(telemetry.get("humidity", 50.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        precip = float(telemetry.get("precipitation", 0.0))
        visibility = float(telemetry.get("visibility_m", 10000.0))

        surface = "dry"
        visibility_cond = "good"
        risk = "low"
        rec = "Route conditions normal."

        # Surface condition
        rain_adjusted = region_adjusted_rain_threshold(precip, rp)
        if precip > 50 or (humidity > profile.constraints.get("skid_risk_humidity", 90) and temp > 5):
            surface = "wet"
            risk = "medium"
            rec = "Wet surfaces — reduce speed."
        if precip > 80 or (temp < profile.icing_temp_c and precip > 40):
            surface = "icy"
            risk = "high"
            rec = "Icy conditions — extreme caution advised."
        if rain_adjusted > profile.flood_risk_precip_mm:
            surface = "flooded"
            risk = "critical"
            rec = "Surface flooding reported — avoid if possible."

        # Visibility
        if visibility < 200.0:
            visibility_cond = "dense_fog"
            risk = risk_order("high", risk)
            rec += " Dense fog — significantly reduced visibility."
        elif visibility < 500.0:
            visibility_cond = "fog"
            risk = risk_order("medium", risk)
            rec += " Fog — use headlights."
        elif humidity > self._FOG_HUMIDITY and temp < 10.0:
            visibility_cond = "mist"
            rec += " Misty conditions."

        return RouteCondition(
            route_type=RouteType.GENERAL,
            surface_condition=surface,
            visibility_condition=visibility_cond,
            risk_level=risk,
            recommendation=rec,
        )

    def assess_logistics_risks(
        self,
        telemetry: dict,
        transport_mode: str | TransportProfile | None = None,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> list[LogisticsRisk]:
        profile = self._resolve_profile(transport_mode)
        rp = get_region(region)
        sn = resolve_season(season)
        risks: list[LogisticsRisk] = []

        wind_speed = float(telemetry.get("wind_speed", 0.0))
        temp = float(telemetry.get("temperature", 15.0))
        precip = float(telemetry.get("precipitation", 0.0))
        humidity = float(telemetry.get("humidity", 50.0))
        pressure = float(telemetry.get("pressure", 1013.0))
        aqi = float(telemetry.get("aqi", 42.0))

        wind_adjusted = region_adjusted_wind_threshold(wind_speed, rp)
        rain_adjusted = region_adjusted_rain_threshold(precip, rp)
        heat_adjusted = region_adjusted_heat_threshold(temp, rp, sn)
        cold_adjusted = region_adjusted_cold_threshold(temp, rp, sn)

        if wind_adjusted > profile.max_wind_ms:
            level = "critical" if wind_adjusted > profile.max_gust_ms else "high"
            risks.append(LogisticsRisk(
                risk="high_wind", risk_level=level,
                condition=f"Wind {wind_adjusted:.1f} m/s",
                impact="Route disruption, vehicle instability",
                recommendation="Postpone travel or use wind-sheltered routes.",
            ))

        if cold_adjusted < profile.min_temp_c:
            risks.append(LogisticsRisk(
                risk="extreme_cold", risk_level="high",
                condition=f"Temp {cold_adjusted:.1f}°C (limit: {profile.min_temp_c})",
                impact="Vehicle startup issues, fuel gelling",
                recommendation="Use cold-weather fuel blend, pre-warm engines.",
            ))

        if heat_adjusted > profile.max_temp_c:
            risks.append(LogisticsRisk(
                risk="extreme_heat", risk_level="high",
                condition=f"Temp {heat_adjusted:.1f}°C (limit: {profile.max_temp_c})",
                impact="Cargo degradation, vehicle overheating",
                recommendation="Schedule night operations, monitor cargo temp.",
            ))

        if rain_adjusted > profile.max_precip_mmh:
            risks.append(LogisticsRisk(
                risk="heavy_precipitation", risk_level="high",
                condition=f"Rain {rain_adjusted:.0f} mm/h",
                impact="Flooding, reduced traction",
                recommendation="Delay non-essential travel.",
            ))

        if temp < 5.0 and humidity > 70 and profile.mode == TransportMode.ROAD:
            risks.append(LogisticsRisk(
                risk="black_ice", risk_level="high",
                condition=f"Temp {temp:.1f}°C, humidity {humidity:.0f}%",
                impact="Loss of vehicle control",
                recommendation="Beware of black ice on bridges and shaded areas.",
            ))

        if profile.mode == TransportMode.RAIL:
            track_limit = profile.constraints.get("track_buckling_temp_c", 35.0)
            if heat_adjusted > track_limit:
                risks.append(LogisticsRisk(
                    risk="track_buckling", risk_level="high",
                    condition=f"Temp {heat_adjusted:.1f}°C (limit: {track_limit})",
                    impact="Speed restrictions, service delays",
                    recommendation="Implement heat-based speed restrictions.",
                ))

        if profile.mode == TransportMode.RAIL:
            if temp < 5.0 and humidity > 75:
                risks.append(LogisticsRisk(
                    risk="leaf_fall", risk_level="medium",
                    condition=f"Temp {temp:.1f}°C, humidity {humidity:.0f}%",
                    impact="Reduced rail adhesion",
                    recommendation="Apply autumn timetable (leaf-fall season).",
                ))

        if aqi > 150 and profile.mode == TransportMode.ROAD:
            risks.append(LogisticsRisk(
                risk="poor_air_quality", risk_level="medium",
                condition=f"AQI {aqi:.0f}",
                impact="Health risk for outdoor workers",
                recommendation="Provide respiratory protection for outdoor staff.",
            ))

        return risks

    def generate_advisories(
        self,
        telemetry: dict,
        transport_mode: str | TransportProfile | None = None,
        region: str | UKRegion | None = None,
        route: RouteCondition | None = None,
        risks: list[LogisticsRisk] | None = None,
    ) -> list[TravelAdvisory]:
        profile = self._resolve_profile(transport_mode)
        rp = get_region(region)
        advisories: list[TravelAdvisory] = []

        wind_speed = float(telemetry.get("wind_speed", 0.0))
        temp = float(telemetry.get("temperature", 15.0))
        precip = float(telemetry.get("precipitation", 0.0))
        pressure = float(telemetry.get("pressure", 1013.0))

        if wind_speed > profile.max_wind_ms:
            advisories.append(TravelAdvisory(
                advisory="high_wind_warning",
                severity="severe",
                affected_routes=[f"{profile.mode.value}_network"],
                duration_hours=6,
                recommendation="High wind alert — high-sided vehicles avoid exposed routes.",
            ))

        if precip > 60 and temp < 2.0:
            advisories.append(TravelAdvisory(
                advisory="snow_ice_warning",
                severity="severe",
                affected_routes=[f"{profile.mode.value}_network"],
                duration_hours=12,
                recommendation="Snow/ice — check route status before travel.",
            ))

        if precip > 40 and temp > 2.0:
            advisories.append(TravelAdvisory(
                advisory="flood_risk",
                severity="moderate",
                affected_routes=["low_lying_areas", "coastal_routes"],
                duration_hours=4,
                recommendation="Flood risk — avoid low-lying routes.",
            ))

        return advisories

    def compute_risk_level(
        self,
        telemetry: dict,
        transport_mode: str | TransportProfile | None = None,
        route: RouteCondition | None = None,
        risks: list[LogisticsRisk] | None = None,
    ) -> str:
        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        current = risk_order.get("low", 0)

        if route:
            current = max(current, risk_order.get(route.risk_level, 0))

        for r in (risks or []):
            current = max(current, risk_order.get(r.risk_level, 0))

        levels = {v: k for k, v in risk_order.items()}
        return levels[current]

    def _get_profile(self, transport_mode: str) -> TransportProfile:
        return TRANSPORT_PROFILES.get(transport_mode, TRANSPORT_PROFILES["general"])

    def _resolve_profile(
        self, transport_mode: str | TransportProfile | None
    ) -> TransportProfile:
        if isinstance(transport_mode, TransportProfile):
            return transport_mode
        return self._get_profile(transport_mode or "general")

    def _build_recommendations(
        self,
        profile: TransportProfile,
        route: RouteCondition,
        risks: list[LogisticsRisk],
        advisories: list[TravelAdvisory],
    ) -> list[str]:
        recs = []
        if route.risk_level != "low":
            recs.append(route.recommendation)
        for r in risks:
            if r.risk_level in ("high", "critical"):
                recs.append(r.recommendation)
        for a in advisories:
            if a.severity == "severe":
                recs.append(a.recommendation)
        if not recs:
            recs.append(f"Conditions suitable for {profile.name} operations.")
        return recs


def risk_order(current: str, new: str) -> str:
    levels = ["low", "medium", "high", "critical"]
    if levels.index(new) > levels.index(current):
        return new
    return current
