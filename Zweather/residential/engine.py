"""
Residential intelligence engine for Zedd Weather.
Heuristic-based analysis of telemetry data for residential property
safety, comfort, building fabric, and energy assessments.

Supports UK regional climate profiles with seasonally-adjusted thresholds.
"""
from Zweather.utils import compute_heat_index, compute_wind_chill
from Zweather.global_regions.regions import (
    get_region,
    resolve_season,
    region_adjusted_heat_threshold,
    region_adjusted_cold_threshold,
)
from Zweather.global_regions.models import UKRegion, Season, RegionProfile

from .models import (
    PropertyProfile,
    PROPERTY_PROFILES,
    BuildingFabricAssessment,
    OccupantSafety,
    PropertyHazard,
    EnergyAssessment,
)


class ResidentialEngine:

    _HEAT_CAUTION_C = 30.0
    _HEAT_EXTREME_C = 38.0
    _COLD_CAUTION_C = 5.0
    _COLD_EXTREME_C = -8.0
    _HIGH_WIND_MS = 12.0
    _PRESSURE_STORM = 995.0

    def analyze(
        self,
        telemetry: dict,
        property_type: str = "general",
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> dict:
        profile = self._get_profile(property_type)
        rp = get_region(region)
        sn = resolve_season(season)

        fabric = self.assess_building_fabric(telemetry, profile, region, season)
        safety = self.assess_occupant_safety(telemetry, profile, region, season)
        hazards = self.detect_property_hazards(telemetry, profile, region, season)
        energy = self.assess_energy_demand(telemetry, profile, region, season)
        risk_level = self.compute_risk_level(telemetry, profile, region, season)

        recommendations = self._build_recommendations(
            telemetry, profile, fabric, safety, hazards, energy,
        )

        return {
            "property_type": property_type,
            "property_name": profile.name,
            "risk_level": risk_level,
            "region": rp.name,
            "season": sn.value,
            "building_fabric": {
                "damp_risk_index": fabric.damp_risk_index,
                "mould_risk_index": fabric.mould_risk_index,
                "condensation_risk": fabric.condensation_risk,
                "pipe_freeze_risk": fabric.pipe_freeze_risk,
                "insulation_effectiveness_pct": fabric.insulation_effectiveness_pct,
                "ventilation_recommendations": fabric.ventilation_recommendations,
            },
            "occupant_safety": {
                "heat_stress_index": safety.heat_stress_index,
                "cold_stress_index": safety.cold_stress_index,
                "indoor_air_quality_concern": safety.indoor_air_quality_concern,
                "recommended_indoor_temp": safety.recommended_indoor_temp,
                "recommendations": safety.recommendations,
            },
            "property_hazards": [
                {"hazard": h.hazard, "risk_level": h.risk_level,
                 "condition": h.condition, "recommendation": h.recommendation,
                 "affected_rooms": h.affected_rooms}
                for h in hazards
            ],
            "energy": {
                "heating_demand_index": energy.heating_demand_index,
                "cooling_demand_index": energy.cooling_demand_index,
                "power_outage_risk": energy.power_outage_risk,
                "estimated_daily_cost_pct": energy.estimated_daily_cost_pct,
                "recommendations": energy.recommendations,
            },
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Building fabric
    # ------------------------------------------------------------------

    def assess_building_fabric(
        self,
        telemetry: dict,
        property_type: str | PropertyProfile | None = None,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> BuildingFabricAssessment:
        profile = self._resolve_profile(property_type)
        rp = get_region(region)
        sn = resolve_season(season)

        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        rainfall_mm = float(telemetry.get("rainfall_mm", 0.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))

        # Damp risk: external humidity + rain + poor fabric
        damp_base = 0.0
        if humidity > 75.0:
            damp_base = (humidity - 60.0) / 40.0
        if rainfall_mm > 5.0:
            damp_base += 0.2
        damp_risk = min(1.0, damp_base * (0.5 + profile.damp_sensitivity))
        damp_risk = max(0.0, damp_risk)

        # Mould risk: damp + warmth + poor ventilation
        mould_base = 0.0
        if humidity > 70.0 and 10.0 <= temp <= 30.0:
            mould_base = (humidity - 60.0) / 40.0
        mould_risk = min(1.0, mould_base * (0.4 + profile.mould_sensitivity))
        if profile.ventilation_adequacy < 0.3:
            mould_risk = min(1.0, mould_risk * 1.5)
        mould_risk = max(0.0, mould_risk)

        # Condensation risk
        condensation = humidity > 75.0 and temp < 18.0

        # Pipe freeze risk
        freeze_risk = temp < 0.0
        if freeze_risk and profile.frost_pipe_risk > 0.5:
            freeze_risk = True

        # Insulation effectiveness
        insulation_pct = profile.insulation_quality * 100.0
        if temp < 0.0:
            insulation_pct *= 0.8

        # Ventilation recommendations
        vent_recs: list[str] = []
        if humidity > 75.0 and profile.ventilation_adequacy < 0.5:
            vent_recs.append("Increase natural ventilation — open trickle vents or windows")
        if condensation:
            vent_recs.append("Use extractor fans in kitchen and bathroom")
        if humidity > 85.0 and profile.ventilation_adequacy < 0.3:
            vent_recs.append("Consider installing a mechanical ventilation system (MVHR)")
        if not vent_recs:
            vent_recs.append("Current ventilation conditions are adequate")

        return BuildingFabricAssessment(
            damp_risk_index=round(damp_risk, 2),
            mould_risk_index=round(mould_risk, 2),
            condensation_risk=condensation,
            pipe_freeze_risk=freeze_risk,
            insulation_effectiveness_pct=round(insulation_pct, 1),
            ventilation_recommendations=vent_recs,
        )

    # ------------------------------------------------------------------
    # Occupant safety
    # ------------------------------------------------------------------

    def assess_occupant_safety(
        self,
        telemetry: dict,
        property_type: str | PropertyProfile | None = None,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> OccupantSafety:
        profile = self._resolve_profile(property_type)
        rp = get_region(region)
        sn = resolve_season(season)

        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        aqi = float(telemetry.get("aqi", 0))

        heat_caution = region_adjusted_heat_threshold(profile.comfort_temp_max, rp, sn)
        cold_caution = region_adjusted_cold_threshold(profile.comfort_temp_min, rp, sn)

        heat_index = compute_heat_index(temp, humidity)
        heat_stress = min(1.0, max(0.0, (heat_index - heat_caution) / 20.0)) if heat_index > heat_caution else 0.0

        wind_chill = compute_wind_chill(temp, wind_speed)
        cold_stress = min(1.0, max(0.0, (cold_caution - wind_chill) / 20.0)) if wind_chill < cold_caution else 0.0

        # Indoor air quality
        aqi_concern = aqi > 100.0
        if profile.respiratory_conditions:
            aqi_concern = aqi > 50.0 or aqi_concern

        # Recommended indoor temp
        if temp < cold_caution:
            rec_temp = profile.comfort_temp_min
        elif temp > heat_caution:
            rec_temp = profile.comfort_temp_max
        else:
            rec_temp = temp

        # Recommendations
        recs: list[str] = []
        if heat_stress > 0.6:
            recs.append("Use fans or air conditioning. Stay hydrated. Check on elderly/young occupants.")
        if cold_stress > 0.6:
            recs.append("Increase heating. Wear warm clothing. Check for drafts around windows and doors.")
        if aqi_concern:
            recs.append("Keep windows closed. Use air purifiers if available. Limit outdoor exposure.")
        if profile.elderly_occupants and (cold_stress > 0.4 or heat_stress > 0.4):
            recs.append("Check on elderly occupants regularly during extreme temperatures.")
        if profile.young_children and (cold_stress > 0.4 or heat_stress > 0.4):
            recs.append("Ensure children wear appropriate clothing and maintain room temperature.")
        if not recs:
            recs.append("Conditions are comfortable. Continue routine home monitoring.")

        return OccupantSafety(
            heat_stress_index=round(heat_stress, 2),
            cold_stress_index=round(cold_stress, 2),
            indoor_air_quality_concern=aqi_concern,
            recommended_indoor_temp=round(rec_temp, 1),
            recommendations=recs,
        )

    # ------------------------------------------------------------------
    # Property hazards
    # ------------------------------------------------------------------

    def detect_property_hazards(
        self,
        telemetry: dict,
        property_type: str | PropertyProfile | None = None,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> list[PropertyHazard]:
        profile = self._resolve_profile(property_type)
        rp = get_region(region)
        sn = resolve_season(season)

        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        pressure = float(telemetry.get("pressure", 1013.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        rainfall_mm = float(telemetry.get("rainfall_mm", 0.0))
        uv_index = float(telemetry.get("uv_index", 0.0))

        heat_caution = region_adjusted_heat_threshold(self._HEAT_CAUTION_C, rp, sn)
        cold_caution = region_adjusted_cold_threshold(self._COLD_CAUTION_C, rp, sn)

        hazards: list[PropertyHazard] = []

        # Flooding
        if rainfall_mm > 15.0:
            hazards.append(PropertyHazard(
                hazard="Surface Water Flooding",
                risk_level="high",
                condition=f"Rainfall {rainfall_mm:.1f} mm — flood risk elevated in {rp.name}",
                recommendation=(
                    "Check gutters and drains are clear. "
                    "Move valuables from ground floor. "
                    "Prepare sandbags if historically flood-prone."
                ),
                affected_rooms=["basement", "ground_floor"],
            ))
        elif rainfall_mm > 8.0 and rp.flood_risk_modifier > 1.0:
            hazards.append(PropertyHazard(
                hazard="Localised Flooding Risk",
                risk_level="medium",
                condition=f"Rainfall {rainfall_mm:.1f} mm with elevated flood risk in {rp.name}",
                recommendation="Monitor drainage around property. Ensure gutters are clear.",
                affected_rooms=["basement"],
            ))

        # Storm damage
        if wind_speed > self._HIGH_WIND_MS:
            hazards.append(PropertyHazard(
                hazard="Wind Damage Risk",
                risk_level="high" if wind_speed > 18.0 else "medium",
                condition=f"Wind speed {wind_speed:.1f} m/s — property damage risk",
                recommendation=(
                    "Secure loose garden items and bins. "
                    "Park vehicles away from trees. "
                    "Check roof tiles and aerial fittings."
                ),
                affected_rooms=["roof", "garden"],
            ))

        # Extreme heat
        if temp > self._HEAT_EXTREME_C:
            hazards.append(PropertyHazard(
                hazard="Extreme Heat",
                risk_level="critical",
                condition=f"Temperature {temp:.1f}°C — dangerous indoor conditions without cooling",
                recommendation=(
                    "Close curtains during day. Use fans/AC. "
                    "Check on vulnerable neighbours. Keep pets indoors."
                ),
                affected_rooms=["bedrooms", "living_room"],
            ))

        # Extreme cold
        if temp < self._COLD_EXTREME_C:
            hazards.append(PropertyHazard(
                hazard="Extreme Cold / Freezing",
                risk_level="critical",
                condition=f"Temperature {temp:.1f}°C — pipe freezing and hypothermia risk",
                recommendation=(
                    "Set heating to maintain minimum 12°C. "
                    "Insulate exposed pipes. Drip taps overnight. "
                    "Check on elderly neighbours."
                ),
                affected_rooms=["bathroom", "kitchen", "loft"],
            ))

        # Storm alert
        if pressure < rp.cold_spell_threshold_c and humidity > 75.0:
            hazards.append(PropertyHazard(
                hazard="Approaching Storm",
                risk_level="medium",
                condition=f"Low pressure ({pressure:.1f} hPa) with high humidity — storm likely",
                recommendation=(
                    "Secure garden furniture. Charge devices. "
                    "Prepare torches and emergency supplies."
                ),
            ))

        # UV exposure
        if uv_index >= 8.0:
            hazards.append(PropertyHazard(
                hazard="High UV Exposure",
                risk_level="high",
                condition=f"UV index {uv_index:.1f} — extreme for {rp.name}",
                recommendation=(
                    "Use SPF 50+ sunscreen if outdoors. "
                    "Stay indoors during peak hours (11am-3pm). "
                    "Close south-facing curtains."
                ),
            ))

        if not hazards:
            hazards.append(PropertyHazard(
                hazard="None identified",
                risk_level="low",
                condition=f"Conditions are safe for {rp.name}.",
                recommendation="Continue routine property maintenance.",
            ))

        return hazards

    # ------------------------------------------------------------------
    # Energy demand
    # ------------------------------------------------------------------

    def assess_energy_demand(
        self,
        telemetry: dict,
        property_type: str | PropertyProfile | None = None,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> EnergyAssessment:
        profile = self._resolve_profile(property_type)
        rp = get_region(region)
        sn = resolve_season(season)

        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))

        heat_caution = region_adjusted_heat_threshold(profile.comfort_temp_max, rp, sn)
        cold_caution = region_adjusted_cold_threshold(profile.comfort_temp_min, rp, sn)

        # Heating demand
        if temp < cold_caution:
            heat_demand = min(1.0, (cold_caution - temp) / 25.0)
        else:
            heat_demand = 0.0
        # Insulation reduces demand
        heat_demand *= (1.5 - profile.insulation_quality)

        # Cooling demand
        if temp > heat_caution:
            cool_demand = min(1.0, (temp - heat_caution) / 15.0)
        else:
            cool_demand = 0.0
        cool_demand *= (1.0 - profile.insulation_quality * 0.3)

        # Power outage risk (simplified)
        outage_temp_factor = 1.0 if temp > 35.0 or temp < -5.0 else 0.0
        outage_wind_factor = 1.0 if wind_speed > 20.0 else 0.0
        outage_score = outage_temp_factor + outage_wind_factor
        if outage_score >= 2.0:
            outage_risk = "high"
        elif outage_score >= 1.0:
            outage_risk = "medium"
        else:
            outage_risk = "low"

        # Cost estimation
        cost_pct = (heat_demand + cool_demand) * 100.0

        # Recommendations
        recs: list[str] = []
        if heat_demand > 0.5:
            recs.append("Use programmable thermostat to optimise heating schedule")
        if cool_demand > 0.5:
            recs.append("Use ceiling fans as low-energy alternative to AC")
        if outage_risk == "high":
            recs.append("Charge devices. Prepare backup power sources if available")
        if profile.insulation_quality < 0.3:
            recs.append("Consider loft insulation and draft-proofing to reduce bills")
        if profile.heating.name == "HEAT_PUMP" and temp < 0.0:
            recs.append("Heat pump efficiency reduced below 0°C — supplement with backup heating")
        if not recs:
            recs.append("Energy demand is within normal range")

        return EnergyAssessment(
            heating_demand_index=round(heat_demand, 2),
            cooling_demand_index=round(cool_demand, 2),
            power_outage_risk=outage_risk,
            estimated_daily_cost_pct=round(cost_pct, 1),
            recommendations=recs,
        )

    # ------------------------------------------------------------------
    # Risk level
    # ------------------------------------------------------------------

    def compute_risk_level(
        self,
        telemetry: dict,
        property_type: str | PropertyProfile | None = None,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> str:
        profile = self._resolve_profile(property_type)
        rp = get_region(region)
        sn = resolve_season(season)

        fabric = self.assess_building_fabric(telemetry, profile, region, season)
        safety = self.assess_occupant_safety(telemetry, profile, region, season)
        hazards = self.detect_property_hazards(telemetry, profile, region, season)

        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        current = risk_order.get("low", 0)

        for h in hazards:
            current = max(current, risk_order.get(h.risk_level, 0))

        if fabric.damp_risk_index > 0.7 or fabric.mould_risk_index > 0.7:
            current = max(current, risk_order["high"])
        if fabric.condensation_risk:
            current = max(current, risk_order["medium"])

        if safety.heat_stress_index > 0.8 or safety.cold_stress_index > 0.8:
            current = max(current, risk_order["critical"])
        elif safety.heat_stress_index > 0.6 or safety.cold_stress_index > 0.6:
            current = max(current, risk_order["high"])

        if fabric.pipe_freeze_risk:
            current = max(current, risk_order["high"])

        levels = {v: k for k, v in risk_order.items()}
        return levels[current]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_profile(self, property_type: str) -> PropertyProfile:
        return PROPERTY_PROFILES.get(
            property_type.lower(), PROPERTY_PROFILES["general"]
        )

    def _resolve_profile(
        self, prop: str | PropertyProfile | None
    ) -> PropertyProfile:
        if prop is None or isinstance(prop, str):
            return self._get_profile(prop or "general")
        return prop

    @staticmethod
    def _compute_heat_index(temp: float, humidity: float) -> float:
        return compute_heat_index(temp, humidity)

    @staticmethod
    def _compute_wind_chill(temp: float, wind_speed_ms: float) -> float:
        return compute_wind_chill(temp, wind_speed_ms)

    def _build_recommendations(
        self,
        telemetry: dict,
        profile: PropertyProfile,
        fabric: BuildingFabricAssessment,
        safety: OccupantSafety,
        hazards: list[PropertyHazard],
        energy: EnergyAssessment,
    ) -> list[str]:
        recs: list[str] = []

        for h in hazards:
            if h.risk_level in ("high", "critical"):
                recs.append(f"{h.hazard}: {h.recommendation}")

        if fabric.damp_risk_index > 0.5:
            recs.append(f"Damp risk elevated ({fabric.damp_risk_index:.0%}): increase ventilation")
        if fabric.pipe_freeze_risk:
            recs.append("Pipe freeze risk: insulate exposed pipes and maintain heating")

        for vent_rec in fabric.ventilation_recommendations:
            if "adequate" not in vent_rec.lower():
                recs.append(vent_rec)

        if safety.heat_stress_index > 0.6:
            recs.append(f"Heat stress ({safety.heat_stress_index:.0%}): {safety.recommendations[0]}")
        if safety.cold_stress_index > 0.6:
            recs.append(f"Cold stress ({safety.cold_stress_index:.0%}): {safety.recommendations[0]}")

        if energy.power_outage_risk == "high":
            recs.append("High power outage risk — prepare emergency supplies")

        if not recs:
            recs.append("No significant hazards. Continue routine home maintenance.")

        return recs
