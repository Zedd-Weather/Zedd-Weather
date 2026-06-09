"""
Energy intelligence engine for Zedd Weather.
Heuristic-based analysis of telemetry data for energy sector:
grid stability, renewable generation forecasting, and asset protection.
"""
from Zweather.global_regions.regions import (
    get_region,
    resolve_season,
    region_adjusted_heat_threshold,
    region_adjusted_cold_threshold,
    region_adjusted_wind_threshold,
)
from Zweather.global_regions.models import UKRegion, Season

from .models import (
    EnergyAssetProfile,
    ENERGY_ASSET_PROFILES,
    EnergyAssetType,
    GridStabilityAssessment,
    GenerationForecast,
    EnergyHazard,
)


class EnergyEngine:

    _STORM_PRESSURE_HPA = 990.0
    _HEATWAVE_TEMP_C = 35.0
    _FREEZING_TEMP_C = 0.0
    _HIGH_DEMAND_TEMP_C = 30.0
    _HIGH_DEMAND_COLD_C = 5.0
    _OPTIMAL_SOLAR_IRRADIANCE = 800.0
    _OPTIMAL_WIND_MS = 12.0
    _WIND_CUT_IN_MS = 3.0
    _WIND_CUT_OUT_MS = 25.0

    def analyze(
        self,
        telemetry: dict,
        asset: str = "general",
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> dict:
        profile = self._get_profile(asset)
        rp = get_region(region)

        grid = self.assess_grid_stability(telemetry, region, season)
        forecast = self.forecast_generation(telemetry, profile, region)
        hazards = self.detect_energy_hazards(telemetry, profile, region, season)
        risk_level = self.compute_risk_level(telemetry, profile, grid, hazards)

        recommendations = self._build_recommendations(
            profile, grid, forecast, hazards,
        )

        return {
            "asset": asset,
            "asset_name": profile.name,
            "risk_level": risk_level,
            "region": rp.name,
            "grid_stability": {
                "risk_level": grid.risk_level,
                "demand_pressure": grid.demand_pressure,
                "renewable_contribution_pct": grid.renewable_contribution_pct,
                "volatility_risk": grid.volatility_risk,
                "recommendation": grid.recommendation,
            },
            "generation_forecast": {
                "estimated_output_mw": forecast.estimated_output_mw,
                "capacity_factor_pct": forecast.capacity_factor_pct,
                "limiting_factors": forecast.limiting_factors,
                "recommendation": forecast.recommendation,
            },
            "hazards": [
                {"hazard": h.hazard, "risk_level": h.risk_level,
                 "condition": h.condition,
                 "affected_capacity_mw": h.affected_capacity_mw,
                 "recommendation": h.recommendation}
                for h in hazards
            ],
            "recommendations": recommendations,
        }

    def assess_grid_stability(
        self,
        telemetry: dict,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> GridStabilityAssessment:
        rp = get_region(region)
        sn = resolve_season(season)
        temp = float(telemetry.get("temperature", 15.0))
        humidity = float(telemetry.get("humidity", 50.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        pressure = float(telemetry.get("pressure", 1013.0))

        heat_adjusted = region_adjusted_heat_threshold(temp, rp, sn)
        wind_adjusted = region_adjusted_wind_threshold(wind_speed, rp)

        demand = "normal"
        volatility = "low"
        renewable_pct = 30.0
        risk = "low"
        rec = "Grid conditions normal."

        if heat_adjusted > self._HIGH_DEMAND_TEMP_C:
            demand = "high"
            renewable_pct = 60.0 if wind_speed > 5.0 else 25.0
            rec = "High temperatures driving cooling demand — reserve generation advised."
            risk = "medium"
        elif heat_adjusted < self._HIGH_DEMAND_COLD_C:
            demand = "high"
            renewable_pct = 35.0 if wind_speed > 8.0 else 20.0
            rec = "Cold weather driving heating demand — monitor supply margins."
            risk = "medium"

        if pressure < self._STORM_PRESSURE_HPA:
            volatility = "high"
            risk = "high"
            rec = "Low pressure system — renewable output may be volatile."
            renewable_pct = wind_adjusted / 25.0 * 80.0 if wind_adjusted > 0 else 20.0

        if wind_adjusted > self._WIND_CUT_OUT_MS:
            volatility = "high"
            risk = "high"
            rec = "High wind — potential curtailment of wind generation."
            renewable_pct = 15.0

        return GridStabilityAssessment(
            risk_level=risk,
            demand_pressure=demand,
            renewable_contribution_pct=round(renewable_pct, 1),
            volatility_risk=volatility,
            recommendation=rec,
        )

    def forecast_generation(
        self,
        telemetry: dict,
        asset: str | EnergyAssetProfile | None = None,
        region: str | UKRegion | None = None,
    ) -> GenerationForecast:
        profile = self._resolve_profile(asset)
        rp = get_region(region)

        temp = float(telemetry.get("temperature", 15.0))
        humidity = float(telemetry.get("humidity", 50.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        irradiance = float(telemetry.get("solar_irradiance_wm2", 500.0))
        pressure = float(telemetry.get("pressure", 1013.0))
        precip = float(telemetry.get("precipitation", 0.0))

        output = 0.0
        limiting: list[str] = []
        rec = ""

        if profile.asset_type == EnergyAssetType.SOLAR_FARM:
            cloud_factor = max(0.0, 1.0 - precip / 100.0)
            temp_derate = 1.0
            if temp > 35.0:
                temp_derate = 0.85
                limiting.append("High temperature derating")
            if precip > 70:
                limiting.append("Heavy cloud cover")
            output = profile.capacity_mw * profile.derating_factor * cloud_factor * temp_derate * min(1.0, irradiance / self._OPTIMAL_SOLAR_IRRADIANCE)
            rec = f"Solar output estimated at {output:.1f} MW."

        elif profile.asset_type == EnergyAssetType.WIND_FARM:
            constraints = profile.constraints
            cut_in = constraints.get("cut_in_wind_ms", 3.0)
            cut_out = constraints.get("cut_out_wind_ms", 25.0)
            optimal = constraints.get("optimal_wind_ms", 12.0)

            if wind_speed < cut_in:
                output = 0.0
                limiting.append("Wind below cut-in speed")
                rec = "Wind speeds too low for generation."
            elif wind_speed > cut_out:
                output = 0.0
                limiting.append("Wind above cut-out speed — turbines feathered")
                rec = "Turbines feathered — wind too high."
            else:
                cf = (wind_speed / optimal) ** 3 if wind_speed < optimal else min(1.0, (cut_out - wind_speed) / (cut_out - optimal))
                output = profile.capacity_mw * profile.derating_factor * cf
                if wind_speed > 20.0:
                    limiting.append("High wind — reduced output")
                rec = f"Wind output estimated at {output:.1f} MW."

        else:
            output = profile.capacity_mw * profile.derating_factor
            rec = f"Base output {output:.1f} MW — weather effects minimal."

        cf_pct = (output / profile.capacity_mw * 100) if profile.capacity_mw > 0 else 0.0

        return GenerationForecast(
            asset_type=profile.asset_type,
            estimated_output_mw=round(output, 1),
            capacity_factor_pct=round(cf_pct, 1),
            limiting_factors=limiting,
            recommendation=rec,
        )

    def detect_energy_hazards(
        self,
        telemetry: dict,
        asset: str | EnergyAssetProfile | None = None,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> list[EnergyHazard]:
        profile = self._resolve_profile(asset)
        rp = get_region(region)
        sn = resolve_season(season)
        hazards: list[EnergyHazard] = []

        wind_speed = float(telemetry.get("wind_speed", 0.0))
        temp = float(telemetry.get("temperature", 15.0))
        humidity = float(telemetry.get("humidity", 50.0))
        pressure = float(telemetry.get("pressure", 1013.0))
        precip = float(telemetry.get("precipitation", 0.0))

        heat_adjusted = region_adjusted_heat_threshold(temp, rp, sn)
        wind_adjusted = region_adjusted_wind_threshold(wind_speed, rp)

        if wind_adjusted > profile.max_operational_wind_ms:
            severity = "critical" if wind_adjusted > profile.max_survival_wind_ms else "high"
            hazards.append(EnergyHazard(
                hazard="extreme_wind",
                risk_level=severity,
                condition=f"Wind {wind_adjusted:.1f} m/s (limit: {profile.max_operational_wind_ms})",
                affected_capacity_mw=profile.capacity_mw,
                recommendation="Secure outdoor equipment — potential structural risk.",
            ))

        if heat_adjusted > profile.max_ambient_temp_c:
            hazards.append(EnergyHazard(
                hazard="overheating",
                risk_level="high",
                condition=f"Temperature {heat_adjusted:.1f}°C (max: {profile.max_ambient_temp_c})",
                affected_capacity_mw=profile.capacity_mw * 0.3,
                recommendation="Reduce load — equipment cooling limits reached.",
            ))

        if temp < profile.min_ambient_temp_c:
            hazards.append(EnergyHazard(
                hazard="freezing",
                risk_level="high",
                condition=f"Temperature {temp:.1f}°C (min: {profile.min_ambient_temp_c})",
                affected_capacity_mw=profile.capacity_mw * 0.5,
                recommendation="Freeze protection measures required.",
            ))

        if humidity > profile.max_humidity_pct and temp > 25.0:
            hazards.append(EnergyHazard(
                hazard="high_humidity",
                risk_level="medium",
                condition=f"Humidity {humidity:.0f}% at {temp:.1f}°C",
                affected_capacity_mw=profile.capacity_mw * 0.1,
                recommendation="Electrical insulation monitoring advised.",
            ))

        return hazards

    def compute_risk_level(
        self,
        telemetry: dict,
        asset: str | EnergyAssetProfile | None = None,
        grid: GridStabilityAssessment | None = None,
        hazards: list[EnergyHazard] | None = None,
    ) -> str:
        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        current = risk_order.get("low", 0)

        if grid:
            current = max(current, risk_order.get(grid.risk_level, 0))

        for h in (hazards or []):
            current = max(current, risk_order.get(h.risk_level, 0))

        levels = {v: k for k, v in risk_order.items()}
        return levels[current]

    def _get_profile(self, asset: str) -> EnergyAssetProfile:
        return ENERGY_ASSET_PROFILES.get(asset, ENERGY_ASSET_PROFILES["general"])

    def _resolve_profile(
        self, asset: str | EnergyAssetProfile | None
    ) -> EnergyAssetProfile:
        if isinstance(asset, EnergyAssetProfile):
            return asset
        return self._get_profile(asset or "general")

    def _build_recommendations(
        self,
        profile: EnergyAssetProfile,
        grid: GridStabilityAssessment,
        forecast: GenerationForecast,
        hazards: list[EnergyHazard],
    ) -> list[str]:
        recs = []
        if grid.risk_level != "low":
            recs.append(grid.recommendation)
        recs.append(forecast.recommendation)
        for h in hazards:
            if h.risk_level in ("high", "critical"):
                recs.append(h.recommendation)
        if not recs:
            recs.append(f"{profile.name} operating within normal parameters.")
        return recs
