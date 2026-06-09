"""
Industrial intelligence engine for Zedd Weather.
Heuristic-based analysis of telemetry data to produce industrial facility
safety assessments and operational-window recommendations.

Supports UK regional climate profiles with seasonally-adjusted thresholds.
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
    FacilityProfile,
    FACILITY_PROFILES,
    EquipmentAssessment,
    OperationalWindow,
    IndustrialHazard,
    MaterialRisk,
)


class IndustrialEngine:
    """
    Analyses weather telemetry and produces actionable industrial facility
    safety recommendations.

    Accepts an optional ``region`` parameter (UK region or city name) and
    optional ``season`` to adjust thresholds for local climate norms.

    All algorithms are heuristic — no external ML libraries required.
    """

    # Wind thresholds (Midlands baseline)
    _HIGH_WIND_MS = 12.0          # m/s — caution threshold for outdoor ops
    _EXTREME_WIND_MS = 22.0       # m/s — halt threshold for most operations

    # Temperature thresholds for worker safety (Midlands baseline)
    _HEAT_CAUTION_C = 30.0
    _HEAT_EXTREME_C = 40.0
    _COLD_CAUTION_C = 5.0
    _COLD_EXTREME_C = -10.0

    # Pressure threshold
    _PRESSURE_STORM = 995.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        telemetry: dict,
        facility_type: str = "general",
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> dict:
        """
        Run a full industrial facility analysis for the given telemetry snapshot.

        Parameters
        ----------
        telemetry:
            Dict with keys: temperature (°C), humidity (%), pressure (hPa).
            Optional keys: wind_speed, wind_gust, uv_index, rainfall_mm,
            aqi, visibility_m.
        facility_type:
            One of the keys in FACILITY_PROFILES (default: ``"general"``).
        region:
            UK region or city name (e.g. ``"glasgow"``, ``"london"``).
            Defaults to Midlands.
        season:
            Season override if automatic detection is not desired.
        """
        profile = self._get_profile(facility_type)
        rp = get_region(region)
        sn = resolve_season(season)

        equipment = self.assess_equipment_safety(telemetry, facility_type, region, season)
        op_window = self.evaluate_operational_window(telemetry, facility_type, region, season)
        hazards = self.detect_weather_hazards(telemetry, facility_type, region, season)
        material_risks = self.detect_material_risks(telemetry, facility_type, region, season)
        risk_level = self.compute_risk_level(telemetry, facility_type, region, season)

        recommendations = self._build_recommendations(
            telemetry, profile, equipment, op_window, hazards, material_risks,
        )

        return {
            "facility_type": facility_type,
            "facility_name": profile.name,
            "risk_level": risk_level,
            "region": rp.name,
            "season": sn.value,
            "equipment": {
                "thermal_stress_index": equipment.thermal_stress_index,
                "corrosion_risk_index": equipment.corrosion_risk_index,
                "worker_heat_index": equipment.worker_heat_index,
                "worker_cold_index": equipment.worker_cold_index,
                "ventilation_required": equipment.ventilation_required,
                "ppe_recommendations": equipment.ppe_recommendations,
            },
            "operational_window": {
                "safe_to_proceed": op_window.safe_to_proceed,
                "risk_level": op_window.risk_level,
                "halt_reasons": op_window.halt_reasons,
                "caution_reasons": op_window.caution_reasons,
                "recommended_delay_hours": op_window.recommended_delay_hours,
                "next_check_hours": op_window.next_check_hours,
            },
            "weather_hazards": [self._hazard_to_dict(h) for h in hazards],
            "material_risks": [self._risk_to_dict(r) for r in material_risks],
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Equipment safety
    # ------------------------------------------------------------------

    def assess_equipment_safety(
        self,
        telemetry: dict,
        facility_type: str = "general",
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> EquipmentAssessment:
        """
        Assess equipment and worker safety conditions with regionally-adjusted
        thresholds.
        """
        profile = self._get_profile(facility_type)
        rp = get_region(region)
        sn = resolve_season(season)

        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        uv_index = float(telemetry.get("uv_index", 0.0))

        heat_caution = region_adjusted_heat_threshold(self._HEAT_CAUTION_C, rp, sn)
        cold_caution = region_adjusted_cold_threshold(self._COLD_CAUTION_C, rp, sn)

        # Thermal stress index for equipment
        equip_range = profile.equipment_temp_max - profile.equipment_temp_min
        if equip_range <= 0:
            equip_range = 1.0
        if temp > profile.equipment_temp_max:
            thermal_stress = min(1.0, (temp - profile.equipment_temp_max) / 10.0 + 0.5)
        elif temp < profile.equipment_temp_min:
            thermal_stress = min(1.0, (profile.equipment_temp_min - temp) / 10.0 + 0.5)
        else:
            mid = (profile.equipment_temp_max + profile.equipment_temp_min) / 2.0
            deviation = abs(temp - mid) / (equip_range / 2.0)
            thermal_stress = max(0.0, deviation - 0.5) * 0.6
            thermal_stress = min(1.0, thermal_stress)

        # Corrosion risk: high humidity + moderate/low temp → condensation
        if humidity > 80.0 and temp < 20.0:
            corrosion_risk = min(1.0, (humidity - 60.0) / 40.0)
        elif humidity > 70.0:
            corrosion_risk = min(1.0, (humidity - 60.0) / 60.0)
        else:
            corrosion_risk = 0.0

        # Worker heat index (simplified heat index)
        heat_index = self._compute_heat_index(temp, humidity)
        worker_heat = min(1.0, max(0.0, (heat_index - heat_caution) / 20.0)) if heat_index > heat_caution else 0.0

        # Worker cold index (wind-chill)
        wind_chill = self._compute_wind_chill(temp, wind_speed)
        worker_cold = min(1.0, max(0.0, (cold_caution - wind_chill) / 25.0)) if wind_chill < cold_caution else 0.0

        # Ventilation required check
        ventilation = temp > heat_caution or humidity > 80.0

        # PPE recommendations
        ppe: list[str] = ["Safety boots", "High-visibility vest"]
        if uv_index >= 6.0:
            ppe.append("UV-protective sunscreen (SPF 50+)")
        if temp < cold_caution:
            ppe.append("Insulated work gloves")
            ppe.append("Thermal base layers")
        if temp < cold_caution - 5.0:
            ppe.append("Balaclava / face protection")
        if wind_speed > self._HIGH_WIND_MS:
            ppe.append("Windproof outer layer")
        if humidity > 85.0 or float(telemetry.get("rainfall_mm", 0.0)) > 0:
            ppe.append("Waterproof outerwear")

        aqi = float(telemetry.get("aqi", 0))
        if aqi > profile.aqi_caution:
            ppe.append("Respiratory protection (P2/N95 minimum)")
        if facility_type in ("chemical", "refinery"):
            ppe.append("Chemical-resistant gloves")
            ppe.append("Safety goggles")

        return EquipmentAssessment(
            thermal_stress_index=round(thermal_stress, 2),
            corrosion_risk_index=round(corrosion_risk, 2),
            worker_heat_index=round(worker_heat, 2),
            worker_cold_index=round(worker_cold, 2),
            ventilation_required=ventilation,
            ppe_recommendations=ppe,
        )

    # ------------------------------------------------------------------
    # Operational window
    # ------------------------------------------------------------------

    def evaluate_operational_window(
        self,
        telemetry: dict,
        facility_type: str,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> OperationalWindow:
        """
        Determine whether the specified industrial facility can safely operate
        given current weather and regional climate norms.
        """
        profile = self._get_profile(facility_type)
        rp = get_region(region)
        sn = resolve_season(season)

        temp = float(telemetry.get("temperature", 20.0))
        pressure = float(telemetry.get("pressure", 1013.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        wind_gust = float(telemetry.get("wind_gust", wind_speed))
        rainfall_mm = float(telemetry.get("rainfall_mm", 0.0))
        uv_index = float(telemetry.get("uv_index", 0.0))
        aqi = float(telemetry.get("aqi", 0))
        visibility_m = float(telemetry.get("visibility_m", 9999.0))

        # Apply region-adjusted thresholds
        safe_min = region_adjusted_cold_threshold(profile.temp_safe_min, rp, sn)
        safe_max = region_adjusted_heat_threshold(profile.temp_safe_max, rp, sn)
        halt_min = region_adjusted_cold_threshold(profile.temp_halt_min, rp, sn)
        halt_max = region_adjusted_heat_threshold(profile.temp_halt_max, rp, sn)
        wind_op = region_adjusted_wind_threshold(profile.wind_max_operational, rp)
        wind_halt = region_adjusted_wind_threshold(profile.wind_halt, rp)
        rain_limit = region_adjusted_rain_threshold(profile.rain_max_mm_hr, rp)
        storm_threshold = region_adjusted_rain_threshold(
            profile.pressure_storm_threshold, rp,
        )

        halt_reasons: list[str] = []
        caution_reasons: list[str] = []

        # Temperature checks
        if temp < halt_min:
            halt_reasons.append(
                f"Temperature ({temp:.1f}°C) below halt threshold ({halt_min:.1f}°C)."
            )
        elif temp < safe_min:
            caution_reasons.append(
                f"Temperature ({temp:.1f}°C) below safe operating range."
            )
        if temp > halt_max:
            halt_reasons.append(
                f"Temperature ({temp:.1f}°C) above halt threshold ({halt_max:.1f}°C)."
            )
        elif temp > safe_max:
            caution_reasons.append(
                f"Temperature ({temp:.1f}°C) above safe operating range."
            )

        # Wind checks
        if wind_speed > wind_halt:
            halt_reasons.append(
                f"Wind speed ({wind_speed:.1f} m/s) exceeds halt limit ({wind_halt:.1f} m/s)."
            )
        elif wind_speed > wind_op:
            caution_reasons.append(
                f"Wind speed ({wind_speed:.1f} m/s) exceeds operational limit."
            )

        # Wind gust check
        gust_halt = profile.wind_gust_halt
        if gust_halt and wind_gust >= gust_halt:
            halt_reasons.append(
                f"Wind gust ({wind_gust:.1f} m/s) exceeds gust safety limit ({gust_halt:.1f} m/s)."
            )

        # Rain checks
        if profile.rain_sensitive and rainfall_mm > rain_limit:
            halt_reasons.append(
                f"Rainfall ({rainfall_mm:.1f} mm) — facility is rain-sensitive."
            )
        elif rainfall_mm > rain_limit:
            caution_reasons.append(
                f"Rainfall ({rainfall_mm:.1f} mm) may affect site conditions."
            )

        # Visibility
        if visibility_m < profile.min_visibility_m:
            halt_reasons.append(
                f"Visibility ({visibility_m:.0f} m) below minimum required."
            )
        elif visibility_m < profile.min_visibility_m * 2:
            caution_reasons.append(
                f"Visibility ({visibility_m:.0f} m) reduced — proceed with caution."
            )

        # Pressure / storm check
        if pressure < storm_threshold:
            caution_reasons.append(
                f"Low pressure ({pressure:.1f} hPa) — storm risk elevated."
            )

        # UV checks
        if uv_index >= profile.uv_halt_threshold:
            halt_reasons.append(
                f"UV index ({uv_index:.1f}) exceeds halt threshold — extreme UV."
            )
        elif uv_index >= profile.uv_caution_threshold:
            caution_reasons.append(
                f"UV index ({uv_index:.1f}) elevated — sun protection required."
            )

        # AQI checks
        if aqi >= profile.aqi_halt:
            halt_reasons.append(
                f"AQI ({aqi:.0f}) exceeds shutdown threshold ({profile.aqi_halt})."
            )
        elif aqi >= profile.aqi_caution:
            caution_reasons.append(
                f"AQI ({aqi:.0f}) elevated — respiratory protection required."
            )

        # Determine overall
        safe_to_proceed = len(halt_reasons) == 0
        if halt_reasons:
            risk_level = "critical"
            delay_hours = 4
            next_check = 1
        elif len(caution_reasons) >= 3:
            risk_level = "high"
            delay_hours = 2
            next_check = 2
        elif caution_reasons:
            risk_level = "medium"
            delay_hours = 0
            next_check = 4
        else:
            risk_level = "low"
            delay_hours = 0
            next_check = 8

        return OperationalWindow(
            facility_type=facility_type,
            safe_to_proceed=safe_to_proceed,
            risk_level=risk_level,
            halt_reasons=halt_reasons,
            caution_reasons=caution_reasons,
            recommended_delay_hours=delay_hours,
            next_check_hours=next_check,
            region=rp.name,
            season=sn.value,
        )

    # ------------------------------------------------------------------
    # Weather hazard detection
    # ------------------------------------------------------------------

    def detect_weather_hazards(
        self,
        telemetry: dict,
        facility_type: str,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> list[IndustrialHazard]:
        """
        Identify weather-related hazards for the industrial facility.
        """
        rp = get_region(region)
        sn = resolve_season(season)

        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        pressure = float(telemetry.get("pressure", 1013.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        wind_gust = float(telemetry.get("wind_gust", wind_speed))
        rainfall_mm = float(telemetry.get("rainfall_mm", 0.0))
        visibility_m = float(telemetry.get("visibility_m", 9999.0))

        heat_caution = region_adjusted_heat_threshold(self._HEAT_CAUTION_C, rp, sn)
        heat_extreme = region_adjusted_heat_threshold(self._HEAT_EXTREME_C, rp, sn)
        cold_caution = region_adjusted_cold_threshold(self._COLD_CAUTION_C, rp, sn)
        cold_extreme = region_adjusted_cold_threshold(self._COLD_EXTREME_C, rp, sn)
        wind_high = region_adjusted_wind_threshold(self._HIGH_WIND_MS, rp)
        wind_extreme = region_adjusted_wind_threshold(self._EXTREME_WIND_MS, rp)
        storm_pressure = region_adjusted_rain_threshold(self._PRESSURE_STORM, rp)

        hazards: list[IndustrialHazard] = []

        # Wind
        if wind_speed > wind_extreme or wind_gust > wind_extreme * 1.2:
            hazards.append(IndustrialHazard(
                hazard="Extreme Wind",
                risk_level="critical",
                condition=(
                    f"Wind speed {wind_speed:.1f} m/s (gust {wind_gust:.1f} m/s) "
                    f"exceeds safe limits"
                ),
                recommendation=(
                    "Halt outdoor operations and loading/unloading. "
                    "Secure loose materials and equipment."
                ),
                affected_processes=["outdoor_ops", "loading", "crane_ops"],
            ))
        elif wind_speed > wind_high:
            hazards.append(IndustrialHazard(
                hazard="High Wind",
                risk_level="high",
                condition=f"Wind speed {wind_speed:.1f} m/s — elevated risk for outdoor ops",
                recommendation=(
                    "Restrict outdoor material handling. "
                    "Monitor structural integrity of temporary shelters."
                ),
                affected_processes=["outdoor_ops", "loading"],
            ))

        # Storm / lightning
        if pressure < storm_pressure and humidity > 75.0:
            hazards.append(IndustrialHazard(
                hazard="Lightning / Storm Risk",
                risk_level="high",
                condition=(
                    f"Low pressure ({pressure:.1f} hPa) with high humidity "
                    f"({humidity:.1f}%) indicates approaching storm"
                ),
                recommendation=(
                    "Activate lightning protection protocols. "
                    "Halt outdoor operations and hazardous material transfers."
                ),
                affected_processes=["outdoor_ops", "material_transfer"],
            ))

        # Extreme heat
        if temp > heat_extreme:
            hazards.append(IndustrialHazard(
                hazard="Extreme Heat",
                risk_level="critical",
                condition=f"Temperature {temp:.1f}°C — extreme heat danger",
                recommendation=(
                    "Halt outdoor operations. Enforce cooling breaks and hydration. "
                    "Monitor equipment for thermal overload."
                ),
                affected_processes=["outdoor_ops", "equipment_ops"],
            ))
        elif temp > heat_caution:
            heat_index = self._compute_heat_index(temp, humidity)
            if heat_index > 38.0:
                hazards.append(IndustrialHazard(
                    hazard="Heat Stress",
                    risk_level="high" if heat_index > 45.0 else "medium",
                    condition=(
                        f"Heat index {heat_index:.1f}°C "
                        f"(temp {temp:.1f}°C, humidity {humidity:.1f}%)"
                    ),
                    recommendation=(
                        "Implement work/rest cycles for outdoor workers. "
                        "Ensure HVAC systems are operational."
                    ),
                ))

        # Extreme cold
        if temp < cold_extreme:
            hazards.append(IndustrialHazard(
                hazard="Extreme Cold",
                risk_level="critical",
                condition=f"Temperature {temp:.1f}°C — frostbite and equipment risk",
                recommendation=(
                    "Halt outdoor operations. Check for pipe freezing. "
                    "Monitor equipment startup procedures for cold conditions."
                ),
                affected_processes=["outdoor_ops", "equipment_ops"],
            ))
        elif temp < cold_caution:
            wind_chill = self._compute_wind_chill(temp, wind_speed)
            if wind_chill < -5.0:
                hazards.append(IndustrialHazard(
                    hazard="Wind Chill",
                    risk_level="high" if wind_chill < -15.0 else "medium",
                    condition=(
                        f"Wind chill {wind_chill:.1f}°C "
                        f"(temp {temp:.1f}°C, wind {wind_speed:.1f} m/s)"
                    ),
                    recommendation=(
                        "Limit outdoor exposure. Require thermal PPE. "
                        "Check for ice on walkways and equipment."
                    ),
                ))

        # Heavy rain
        if rainfall_mm > 15.0:
            hazards.append(IndustrialHazard(
                hazard="Heavy Rainfall / Flooding",
                risk_level="high",
                condition=f"Rainfall {rainfall_mm:.1f} mm — flooding and drainage risk",
                recommendation=(
                    "Check drainage systems. Halt outdoor logistics. "
                    "Monitor for electrical hazards from water ingress."
                ),
                affected_processes=["logistics", "outdoor_ops"],
            ))
        elif rainfall_mm > 5.0:
            hazards.append(IndustrialHazard(
                hazard="Moderate Rainfall",
                risk_level="medium",
                condition=f"Rainfall {rainfall_mm:.1f} mm — slippery surfaces",
                recommendation=(
                    "Ensure anti-slip measures at loading areas. "
                    "Protect sensitive outdoor equipment."
                ),
            ))

        # Dense fog
        if visibility_m < 50.0:
            hazards.append(IndustrialHazard(
                hazard="Dense Fog",
                risk_level="critical",
                condition=f"Visibility {visibility_m:.0f} m — dangerous for site movement",
                recommendation=(
                    "Halt vehicle movements and crane operations. "
                    "Use audible warnings. Increase site lighting."
                ),
                affected_processes=["logistics", "crane_ops"],
            ))
        elif visibility_m < 200.0:
            hazards.append(IndustrialHazard(
                hazard="Reduced Visibility",
                risk_level="medium",
                condition=f"Visibility {visibility_m:.0f} m — reduced",
                recommendation=(
                    "Reduce vehicle speeds. Use signalers for crane operations."
                ),
            ))

        if not hazards:
            hazards.append(IndustrialHazard(
                hazard="None identified",
                risk_level="low",
                condition=(
                    "Current conditions are within normal safety parameters "
                    f"for {rp.name}."
                ),
                recommendation="Continue routine facility safety monitoring.",
            ))

        return hazards

    # ------------------------------------------------------------------
    # Material / equipment risk detection
    # ------------------------------------------------------------------

    def detect_material_risks(
        self,
        telemetry: dict,
        facility_type: str,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> list[MaterialRisk]:
        """
        Identify risks to materials, equipment, and processes from
        weather conditions, with region and seasonal awareness.
        """
        profile = self._get_profile(facility_type)
        rp = get_region(region)
        sn = resolve_season(season)

        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        rainfall_mm = float(telemetry.get("rainfall_mm", 0.0))
        aqi = float(telemetry.get("aqi", 0))

        cold_caution = region_adjusted_cold_threshold(self._COLD_CAUTION_C, rp, sn)
        heat_caution = region_adjusted_heat_threshold(self._HEAT_CAUTION_C, rp, sn)

        risks: list[MaterialRisk] = []

        # Equipment thermal risk
        if temp > profile.equipment_temp_max:
            risks.append(MaterialRisk(
                material="Heat-Sensitive Equipment",
                risk_level="critical",
                condition=(
                    f"Temperature {temp:.1f}°C exceeds equipment limit "
                    f"({profile.equipment_temp_max:.1f}°C)"
                ),
                recommendation=(
                    "Reduce load on heat-sensitive equipment. "
                    "Activate supplemental cooling systems."
                ),
            ))
        elif temp < profile.equipment_temp_min:
            risks.append(MaterialRisk(
                material="Cold-Sensitive Equipment",
                risk_level="high",
                condition=(
                    f"Temperature {temp:.1f}°C below equipment minimum "
                    f"({profile.equipment_temp_min:.1f}°C)"
                ),
                recommendation=(
                    "Pre-warm equipment before operation. "
                    "Check hydraulic fluid viscosity and lubrication."
                ),
            ))

        # Corrosion / condensation risk
        if humidity > 80.0 and temp < 15.0:
            risks.append(MaterialRisk(
                material="Metalwork / Electrical",
                risk_level="medium",
                condition=(
                    f"High humidity ({humidity:.1f}%) at low temp ({temp:.1f}°C)"
                ),
                recommendation=(
                    "Inspect electrical panels for condensation. "
                    "Run dehumidifiers in sensitive areas."
                ),
            ))

        # Static discharge risk (chemical/refinery)
        if facility_type in ("chemical", "refinery"):
            static_max = profile.constraints.get("static_discharge_humidity_max", 30.0)
            if humidity < static_max:
                risks.append(MaterialRisk(
                    material="Flammable Materials / Vapours",
                    risk_level="high",
                    condition=(
                        f"Low humidity ({humidity:.1f}%) increases "
                        "electrostatic discharge risk"
                    ),
                    recommendation=(
                        "Activate humidification in process areas. "
                        "Enforce bonding and grounding procedures."
                    ),
                ))

        # Vapour dispersion (chemical/refinery)
        if facility_type in ("chemical", "refinery"):
            wind_speed = float(telemetry.get("wind_speed", 0.0))
            wind_min = profile.constraints.get("vapour_dispersion_wind_min_ms", 1.0)
            if wind_speed < wind_min:
                risks.append(MaterialRisk(
                    material="Vapour / Gas Accumulation",
                    risk_level="high",
                    condition=(
                        f"Low wind ({wind_speed:.1f} m/s) — "
                        "insufficient vapour dispersion"
                    ),
                    recommendation=(
                        "Increase monitoring of gas detectors. "
                        "Restrict flammable material handling."
                    ),
                ))

        # AQI risks
        if aqi > profile.aqi_caution:
            risks.append(MaterialRisk(
                material="Ambient Air Quality",
                risk_level="high" if aqi > profile.aqi_halt else "medium",
                condition=f"AQI {aqi:.0f} exceeds caution threshold ({profile.aqi_caution})",
                recommendation=(
                    "Provide respiratory protection for outdoor workers. "
                    "Limit outdoor exposure time."
                ),
            ))

        # Concrete / building materials (cold weather)
        if temp < cold_caution:
            risks.append(MaterialRisk(
                material="Concrete / Building Materials",
                risk_level="medium",
                condition=(
                    f"Temperature {temp:.1f}°C — concrete curing slowed. "
                    f"Safe range: {cold_caution:.0f}–{heat_caution:.0f}°C"
                ),
                recommendation=(
                    "Use accelerated curing methods or insulating blankets. "
                    "Do not pour below 0°C."
                ),
            ))

        # Supply chain / logistics
        if rainfall_mm > 10.0:
            risks.append(MaterialRisk(
                material="Logistics / Supply Chain",
                risk_level="medium",
                condition=f"Rainfall {rainfall_mm:.1f} mm may disrupt loading/unloading",
                recommendation=(
                    "Adjust delivery schedules. "
                    "Cover materials at loading docks."
                ),
            ))

        if not risks:
            risks.append(MaterialRisk(
                material="None identified",
                risk_level="low",
                condition=f"Conditions are safe for material handling in {rp.name}.",
                recommendation="Continue routine facility monitoring.",
            ))

        return risks

    # ------------------------------------------------------------------
    # Risk level
    # ------------------------------------------------------------------

    def compute_risk_level(
        self,
        telemetry: dict,
        facility_type: str,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> str:
        """
        Compute overall industrial facility risk level.

        Aggregates operational window, hazards, material risks, and
        equipment safety into a single level.
        """
        op_window = self.evaluate_operational_window(telemetry, facility_type, region, season)
        hazards = self.detect_weather_hazards(telemetry, facility_type, region, season)
        material_risks = self.detect_material_risks(telemetry, facility_type, region, season)
        equipment = self.assess_equipment_safety(telemetry, facility_type, region, season)

        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        current = risk_order.get(op_window.risk_level, 0)

        for item in hazards + material_risks:
            current = max(current, risk_order.get(item.risk_level, 0))

        if equipment.worker_heat_index > 0.8 or equipment.worker_cold_index > 0.8:
            current = max(current, risk_order["critical"])
        elif equipment.worker_heat_index > 0.6 or equipment.worker_cold_index > 0.6:
            current = max(current, risk_order["high"])

        if equipment.thermal_stress_index > 0.8:
            current = max(current, risk_order["high"])

        levels = {v: k for k, v in risk_order.items()}
        return levels[current]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_profile(self, facility_type: str) -> FacilityProfile:
        return FACILITY_PROFILES.get(
            facility_type.lower(), FACILITY_PROFILES["general"]
        )

    @staticmethod
    def _compute_heat_index(temp: float, humidity: float) -> float:
        return compute_heat_index(temp, humidity)

    @staticmethod
    def _compute_wind_chill(temp: float, wind_speed_ms: float) -> float:
        return compute_wind_chill(temp, wind_speed_ms)

    @staticmethod
    def _hazard_to_dict(h: IndustrialHazard) -> dict:
        return {
            "hazard": h.hazard,
            "risk_level": h.risk_level,
            "condition": h.condition,
            "recommendation": h.recommendation,
            "affected_processes": h.affected_processes,
        }

    @staticmethod
    def _risk_to_dict(r: MaterialRisk) -> dict:
        return {
            "material": r.material,
            "risk_level": r.risk_level,
            "condition": r.condition,
            "recommendation": r.recommendation,
        }

    def _build_recommendations(
        self,
        telemetry: dict,
        profile: FacilityProfile,
        equipment: EquipmentAssessment,
        op_window: OperationalWindow,
        hazards: list[IndustrialHazard],
        material_risks: list[MaterialRisk],
    ) -> list[str]:
        """Compile a human-readable list of prioritised recommendations."""
        recs: list[str] = []

        for reason in op_window.halt_reasons:
            recs.append(f"HALT: {reason}")

        if equipment.thermal_stress_index > 0.6:
            recs.append(
                f"Equipment thermal stress elevated "
                f"({equipment.thermal_stress_index:.0%}): "
                "monitor critical equipment temperatures."
            )
        if equipment.corrosion_risk_index > 0.5:
            recs.append(
                f"Corrosion risk elevated "
                f"({equipment.corrosion_risk_index:.0%}): "
                "run dehumidifiers and inspect surfaces."
            )

        if equipment.worker_heat_index > 0.6:
            recs.append(
                f"Worker heat stress elevated "
                f"({equipment.worker_heat_index:.0%}): "
                "enforce cooling breaks and hydration."
            )
        if equipment.worker_cold_index > 0.6:
            recs.append(
                f"Worker cold stress elevated "
                f"({equipment.worker_cold_index:.0%}): "
                "require thermal PPE and warm-up breaks."
            )

        if equipment.ventilation_required:
            recs.append("Enhanced ventilation required — check HVAC systems.")

        for reason in op_window.caution_reasons:
            recs.append(f"Caution: {reason}")

        for hazard in hazards:
            if hazard.risk_level in ("high", "critical"):
                recs.append(f"{hazard.hazard}: {hazard.recommendation}")

        for risk in material_risks:
            if risk.risk_level in ("high", "critical"):
                recs.append(f"{risk.material}: {risk.recommendation}")

        if not recs:
            recs.append(
                "All conditions nominal. "
                "Continue routine facility monitoring."
            )

        return recs
