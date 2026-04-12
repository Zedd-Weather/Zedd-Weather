"""
Industrial intelligence engine for Zedd Weather.
Heuristic-based analysis of telemetry data to produce industrial facility
safety assessments and operational-window recommendations.
"""
from .models import (
    FacilityProfile,
    FACILITY_PROFILES,
    EquipmentAssessment,
    OperationalWindow,
)


class IndustrialEngine:
    """
    Analyses weather telemetry and produces actionable industrial facility
    safety recommendations.

    All algorithms are heuristic — no external ML libraries required.
    """

    # Wind thresholds
    _HIGH_WIND_MS = 12.0          # m/s — caution threshold for outdoor operations
    _EXTREME_WIND_MS = 22.0       # m/s — halt threshold for most operations

    # Temperature thresholds for worker safety
    _HEAT_CAUTION_C = 30.0
    _HEAT_EXTREME_C = 40.0
    _COLD_CAUTION_C = 5.0
    _COLD_EXTREME_C = -10.0

    # Pressure threshold
    _PRESSURE_STORM = 995.0

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def analyze(self, telemetry: dict, facility_type: str = "general") -> dict:
        """
        Run a full industrial facility analysis for the given telemetry snapshot.

        Parameters
        ----------
        telemetry:
            Dict with keys: temperature (°C), humidity (%), pressure (hPa).
            Additional keys (wind_speed, uv_index, rainfall_mm, aqi) are used
            when present.
        facility_type:
            One of the keys in FACILITY_PROFILES (default: "general").

        Returns
        -------
        dict with keys:
            facility_type, risk_level, equipment, operational_window,
            weather_hazards, process_risks, recommendations
        """
        profile = self._get_profile(facility_type)
        equipment = self.assess_equipment_safety(telemetry, facility_type)
        op_window = self.evaluate_operational_window(telemetry, facility_type)
        hazards = self.detect_weather_hazards(telemetry, facility_type)
        process_risks = self.detect_process_risks(telemetry, facility_type)
        risk_level = self.compute_risk_level(telemetry, facility_type)

        recommendations = self._build_recommendations(
            telemetry, profile, equipment, op_window, hazards, process_risks
        )

        return {
            "facility_type": facility_type,
            "facility_name": profile.name,
            "risk_level": risk_level,
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
            "weather_hazards": hazards,
            "process_risks": process_risks,
            "recommendations": recommendations,
        }

    def assess_equipment_safety(
        self, telemetry: dict, facility_type: str = "general"
    ) -> EquipmentAssessment:
        """
        Assess equipment and worker safety conditions from atmospheric readings.

        Returns
        -------
        EquipmentAssessment
        """
        profile = self._get_profile(facility_type)
        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        uv_index = float(telemetry.get("uv_index", 0.0))

        # Thermal stress index for equipment
        equip_range = profile.equipment_temp_max - profile.equipment_temp_min
        if equip_range <= 0:
            equip_range = 1.0
        if temp > profile.equipment_temp_max:
            thermal_stress = min(
                1.0, (temp - profile.equipment_temp_max) / 10.0 + 0.5
            )
        elif temp < profile.equipment_temp_min:
            thermal_stress = min(
                1.0, (profile.equipment_temp_min - temp) / 10.0 + 0.5
            )
        else:
            # Within range — compute distance from ideal midpoint
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
        worker_heat = min(1.0, max(0.0, (heat_index - 25.0) / 25.0))

        # Worker cold index (wind-chill)
        wind_chill = self._compute_wind_chill(temp, wind_speed)
        worker_cold = min(1.0, max(0.0, (5.0 - wind_chill) / 25.0))

        # Ventilation required check
        ventilation = temp > 30.0 or humidity > 80.0

        # PPE recommendations
        ppe: list[str] = ["Safety boots", "High-visibility vest"]
        if uv_index >= 6.0:
            ppe.append("UV-protective sunscreen (SPF 50+)")
        if temp < self._COLD_CAUTION_C:
            ppe.append("Insulated work gloves")
            ppe.append("Thermal base layers")
        if temp < -5.0:
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

    def evaluate_operational_window(
        self, telemetry: dict, facility_type: str
    ) -> OperationalWindow:
        """
        Determine whether the specified industrial facility can safely operate.

        Returns
        -------
        OperationalWindow
        """
        profile = self._get_profile(facility_type)
        temp = float(telemetry.get("temperature", 20.0))
        pressure = float(telemetry.get("pressure", 1013.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        rainfall_mm = float(telemetry.get("rainfall_mm", 0.0))
        uv_index = float(telemetry.get("uv_index", 0.0))
        aqi = float(telemetry.get("aqi", 0))

        halt_reasons: list[str] = []
        caution_reasons: list[str] = []

        # Temperature checks
        if temp < profile.temp_halt_min:
            halt_reasons.append(
                f"Temperature ({temp:.1f}°C) below halt threshold "
                f"({profile.temp_halt_min:.1f}°C)."
            )
        elif temp < profile.temp_safe_min:
            caution_reasons.append(
                f"Temperature ({temp:.1f}°C) below safe operating range."
            )
        if temp > profile.temp_halt_max:
            halt_reasons.append(
                f"Temperature ({temp:.1f}°C) above halt threshold "
                f"({profile.temp_halt_max:.1f}°C)."
            )
        elif temp > profile.temp_safe_max:
            caution_reasons.append(
                f"Temperature ({temp:.1f}°C) above safe operating range."
            )

        # Wind checks
        if wind_speed > profile.wind_halt:
            halt_reasons.append(
                f"Wind speed ({wind_speed:.1f} m/s) exceeds halt limit "
                f"({profile.wind_halt:.1f} m/s)."
            )
        elif wind_speed > profile.wind_max_operational:
            caution_reasons.append(
                f"Wind speed ({wind_speed:.1f} m/s) exceeds operational limit."
            )

        # Rain checks
        if profile.rain_sensitive and rainfall_mm > profile.rain_max_mm_hr:
            halt_reasons.append(
                f"Rainfall ({rainfall_mm:.1f} mm) detected — facility is rain-sensitive."
            )
        elif not profile.rain_sensitive and rainfall_mm > profile.rain_max_mm_hr:
            caution_reasons.append(
                f"Rainfall ({rainfall_mm:.1f} mm) above tolerable limit."
            )

        # Pressure / storm check
        if pressure < profile.pressure_storm_threshold:
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
                f"UV index ({uv_index:.1f}) elevated — additional sun protection required."
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
        )

    def detect_weather_hazards(
        self, telemetry: dict, facility_type: str
    ) -> list[dict]:
        """
        Identify weather-related hazards for the industrial facility.

        Returns
        -------
        list of dicts with keys: hazard, risk_level, condition, recommendation
        """
        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        pressure = float(telemetry.get("pressure", 1013.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        rainfall_mm = float(telemetry.get("rainfall_mm", 0.0))
        hazards: list[dict] = []

        # High wind
        if wind_speed > self._EXTREME_WIND_MS:
            hazards.append({
                "hazard": "Extreme Wind",
                "risk_level": "critical",
                "condition": f"Wind speed {wind_speed:.1f} m/s exceeds safe limits",
                "recommendation": (
                    "Halt outdoor operations and loading/unloading. "
                    "Secure loose materials and equipment."
                ),
            })
        elif wind_speed > self._HIGH_WIND_MS:
            hazards.append({
                "hazard": "High Wind",
                "risk_level": "high",
                "condition": (
                    f"Wind speed {wind_speed:.1f} m/s — "
                    "elevated risk for outdoor operations"
                ),
                "recommendation": (
                    "Restrict outdoor material handling. "
                    "Monitor structural integrity of temporary shelters."
                ),
            })

        # Lightning / storm risk
        if pressure < self._PRESSURE_STORM and humidity > 75.0:
            hazards.append({
                "hazard": "Lightning / Storm Risk",
                "risk_level": "high",
                "condition": (
                    f"Low pressure ({pressure:.1f} hPa) with high humidity "
                    f"({humidity:.1f}%) indicates approaching storm"
                ),
                "recommendation": (
                    "Activate lightning protection protocols. "
                    "Halt outdoor operations and hazardous material transfers."
                ),
            })

        # Extreme heat
        if temp > self._HEAT_EXTREME_C:
            hazards.append({
                "hazard": "Extreme Heat",
                "risk_level": "critical",
                "condition": f"Temperature {temp:.1f}°C — extreme heat danger",
                "recommendation": (
                    "Halt outdoor operations. Enforce cooling breaks and hydration. "
                    "Monitor equipment for thermal overload."
                ),
            })
        elif temp > self._HEAT_CAUTION_C:
            heat_index = self._compute_heat_index(temp, humidity)
            if heat_index > 38.0:
                hazards.append({
                    "hazard": "Heat Stress",
                    "risk_level": "high" if heat_index > 45.0 else "medium",
                    "condition": (
                        f"Heat index {heat_index:.1f}°C "
                        f"(temp {temp:.1f}°C, humidity {humidity:.1f}%)"
                    ),
                    "recommendation": (
                        "Implement work/rest cycles for outdoor workers. "
                        "Ensure HVAC systems are operational."
                    ),
                })

        # Extreme cold
        if temp < self._COLD_EXTREME_C:
            hazards.append({
                "hazard": "Extreme Cold",
                "risk_level": "critical",
                "condition": f"Temperature {temp:.1f}°C — frostbite and equipment risk",
                "recommendation": (
                    "Halt outdoor operations. Check for pipe freezing. "
                    "Monitor equipment startup procedures for cold conditions."
                ),
            })
        elif temp < self._COLD_CAUTION_C:
            wind_chill = self._compute_wind_chill(temp, wind_speed)
            if wind_chill < -5.0:
                hazards.append({
                    "hazard": "Wind Chill",
                    "risk_level": "high" if wind_chill < -15.0 else "medium",
                    "condition": (
                        f"Wind chill {wind_chill:.1f}°C "
                        f"(temp {temp:.1f}°C, wind {wind_speed:.1f} m/s)"
                    ),
                    "recommendation": (
                        "Limit outdoor exposure. Require thermal PPE. "
                        "Check for ice on walkways and equipment."
                    ),
                })

        # Heavy rain / flooding
        if rainfall_mm > 15.0:
            hazards.append({
                "hazard": "Heavy Rainfall / Flooding",
                "risk_level": "high",
                "condition": (
                    f"Rainfall {rainfall_mm:.1f} mm — flooding and drainage risk"
                ),
                "recommendation": (
                    "Check drainage systems. Halt outdoor logistics. "
                    "Monitor for electrical hazards from water ingress."
                ),
            })
        elif rainfall_mm > 5.0:
            hazards.append({
                "hazard": "Moderate Rainfall",
                "risk_level": "medium",
                "condition": (
                    f"Rainfall {rainfall_mm:.1f} mm — slippery surfaces"
                ),
                "recommendation": (
                    "Ensure anti-slip measures at loading areas. "
                    "Protect sensitive outdoor equipment."
                ),
            })

        if not hazards:
            hazards.append({
                "hazard": "None identified",
                "risk_level": "low",
                "condition": (
                    "Current conditions are within normal safety parameters."
                ),
                "recommendation": "Continue routine facility safety monitoring.",
            })

        return hazards

    def detect_process_risks(
        self, telemetry: dict, facility_type: str
    ) -> list[dict]:
        """
        Identify risks to industrial processes and equipment from weather conditions.

        Returns
        -------
        list of dicts with keys: process, risk_level, condition, recommendation
        """
        profile = self._get_profile(facility_type)
        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        rainfall_mm = float(telemetry.get("rainfall_mm", 0.0))
        aqi = float(telemetry.get("aqi", 0))
        risks: list[dict] = []

        # Equipment thermal risk
        if temp > profile.equipment_temp_max:
            risks.append({
                "process": "Equipment Overheating",
                "risk_level": "critical",
                "condition": (
                    f"Temperature {temp:.1f}°C exceeds equipment limit "
                    f"({profile.equipment_temp_max:.1f}°C)"
                ),
                "recommendation": (
                    "Reduce load on heat-sensitive equipment. "
                    "Activate supplemental cooling systems."
                ),
            })
        elif temp < profile.equipment_temp_min:
            risks.append({
                "process": "Equipment Cold Start",
                "risk_level": "high",
                "condition": (
                    f"Temperature {temp:.1f}°C below equipment minimum "
                    f"({profile.equipment_temp_min:.1f}°C)"
                ),
                "recommendation": (
                    "Pre-warm equipment before operation. "
                    "Check hydraulic fluid viscosity and lubrication."
                ),
            })

        # Corrosion / condensation risk
        if humidity > 80.0 and temp < 15.0:
            risks.append({
                "process": "Condensation / Corrosion",
                "risk_level": "medium",
                "condition": (
                    f"High humidity ({humidity:.1f}%) at low temp ({temp:.1f}°C)"
                ),
                "recommendation": (
                    "Inspect electrical panels for condensation. "
                    "Run dehumidifiers in sensitive areas."
                ),
            })

        # Static discharge risk (chemical/refinery)
        if facility_type in ("chemical", "refinery"):
            static_max = profile.constraints.get("static_discharge_humidity_max", 30.0)
            if humidity < static_max:
                risks.append({
                    "process": "Static Discharge",
                    "risk_level": "high",
                    "condition": (
                        f"Low humidity ({humidity:.1f}%) increases "
                        "electrostatic discharge risk"
                    ),
                    "recommendation": (
                        "Activate humidification in process areas. "
                        "Enforce bonding and grounding procedures."
                    ),
                })

        # Vapour dispersion (chemical/refinery)
        if facility_type in ("chemical", "refinery"):
            wind_speed = float(telemetry.get("wind_speed", 0.0))
            wind_min = profile.constraints.get("vapour_dispersion_wind_min_ms", 1.0)
            if wind_speed < wind_min:
                risks.append({
                    "process": "Vapour Accumulation",
                    "risk_level": "high",
                    "condition": (
                        f"Low wind ({wind_speed:.1f} m/s) — "
                        "insufficient vapour dispersion"
                    ),
                    "recommendation": (
                        "Increase monitoring of gas detectors. "
                        "Restrict flammable material handling."
                    ),
                })

        # AQI risks for outdoor workers
        if aqi > profile.aqi_caution:
            risks.append({
                "process": "Air Quality Degradation",
                "risk_level": "high" if aqi > profile.aqi_halt else "medium",
                "condition": f"AQI {aqi:.0f} exceeds caution threshold ({profile.aqi_caution})",
                "recommendation": (
                    "Provide respiratory protection for outdoor workers. "
                    "Limit outdoor exposure time."
                ),
            })

        # Supply chain / logistics
        if rainfall_mm > 10.0:
            risks.append({
                "process": "Logistics Disruption",
                "risk_level": "medium",
                "condition": (
                    f"Rainfall {rainfall_mm:.1f} mm may disrupt loading/unloading"
                ),
                "recommendation": (
                    "Adjust delivery schedules. "
                    "Cover materials at loading docks."
                ),
            })

        if not risks:
            risks.append({
                "process": "None identified",
                "risk_level": "low",
                "condition": (
                    "Current conditions pose no significant process risks."
                ),
                "recommendation": "Continue routine facility monitoring.",
            })

        return risks

    def compute_risk_level(self, telemetry: dict, facility_type: str) -> str:
        """
        Compute overall industrial facility risk level from telemetry.

        Returns
        -------
        "low", "medium", "high", or "critical"
        """
        op_window = self.evaluate_operational_window(telemetry, facility_type)
        hazards = self.detect_weather_hazards(telemetry, facility_type)
        process_risks = self.detect_process_risks(telemetry, facility_type)
        equipment = self.assess_equipment_safety(telemetry, facility_type)

        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        current = risk_order.get(op_window.risk_level, 0)

        # Escalate based on hazards and process risks
        for item in hazards + process_risks:
            rl = item.get("risk_level", "low")
            current = max(current, risk_order.get(rl, 0))

        # Extreme worker safety indices escalate risk
        if equipment.worker_heat_index > 0.8 or equipment.worker_cold_index > 0.8:
            current = max(current, risk_order["critical"])
        elif equipment.worker_heat_index > 0.6 or equipment.worker_cold_index > 0.6:
            current = max(current, risk_order["high"])

        # Equipment thermal stress escalation
        if equipment.thermal_stress_index > 0.8:
            current = max(current, risk_order["high"])

        levels = {v: k for k, v in risk_order.items()}
        return levels[current]

    # ---------------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------------

    def _get_profile(self, facility_type: str) -> FacilityProfile:
        """Return the facility profile, falling back to general if unknown."""
        return FACILITY_PROFILES.get(
            facility_type.lower(), FACILITY_PROFILES["general"]
        )

    @staticmethod
    def _compute_heat_index(temp: float, humidity: float) -> float:
        """
        Simplified heat index (°C) from temperature and relative humidity.
        Uses the Rothfusz regression adapted to Celsius.
        """
        if temp < 27.0 or humidity < 40.0:
            return temp

        t = temp
        r = humidity
        hi = (
            -8.784
            + 1.611 * t
            + 2.339 * r
            - 0.1461 * t * r
            - 0.01231 * t * t
            - 0.01642 * r * r
            + 0.002212 * t * t * r
            + 0.000725 * t * r * r
            - 0.000004 * t * t * r * r
        )
        return round(hi, 1)

    @staticmethod
    def _compute_wind_chill(temp: float, wind_speed_ms: float) -> float:
        """
        Compute wind chill temperature (°C).
        Uses the North American wind chill index formula (adapted to m/s).
        """
        if temp >= 10.0 or wind_speed_ms < 1.3:
            return temp

        v_kmh = wind_speed_ms * 3.6
        wc = (
            13.12
            + 0.6215 * temp
            - 11.37 * (v_kmh ** 0.16)
            + 0.3965 * temp * (v_kmh ** 0.16)
        )
        return round(wc, 1)

    def _build_recommendations(
        self,
        telemetry: dict,
        profile: FacilityProfile,
        equipment: EquipmentAssessment,
        op_window: OperationalWindow,
        hazards: list[dict],
        process_risks: list[dict],
    ) -> list[str]:
        """Compile a human-readable list of prioritised recommendations."""
        recs: list[str] = []

        # Halt reasons first
        for reason in op_window.halt_reasons:
            recs.append(f"\U0001f6ab HALT: {reason}")

        # Equipment safety
        if equipment.thermal_stress_index > 0.6:
            recs.append(
                f"\U0001f321\ufe0f Equipment thermal stress elevated "
                f"({equipment.thermal_stress_index:.0%}): "
                "monitor critical equipment temperatures."
            )
        if equipment.corrosion_risk_index > 0.5:
            recs.append(
                f"\U0001f4a7 Corrosion risk elevated "
                f"({equipment.corrosion_risk_index:.0%}): "
                "run dehumidifiers and inspect surfaces."
            )

        # Worker safety
        if equipment.worker_heat_index > 0.6:
            recs.append(
                f"\U0001f321\ufe0f Worker heat stress elevated "
                f"({equipment.worker_heat_index:.0%}): "
                "enforce cooling breaks and hydration."
            )
        if equipment.worker_cold_index > 0.6:
            recs.append(
                f"\U00002744\ufe0f Worker cold stress elevated "
                f"({equipment.worker_cold_index:.0%}): "
                "require thermal PPE and warm-up breaks."
            )

        if equipment.ventilation_required:
            recs.append(
                "\U0001f4a8 Enhanced ventilation required — check HVAC systems."
            )

        # Caution reasons
        for reason in op_window.caution_reasons:
            recs.append(f"\u26a0\ufe0f CAUTION: {reason}")

        # Hazard-specific
        for hazard in hazards:
            if hazard["risk_level"] in ("high", "critical"):
                recs.append(
                    f"\u26a0\ufe0f {hazard['hazard']}: {hazard['recommendation']}"
                )

        # Process-specific
        for risk in process_risks:
            if risk["risk_level"] in ("high", "critical"):
                recs.append(
                    f"\U0001f527 {risk['process']}: {risk['recommendation']}"
                )

        if not recs:
            recs.append(
                "\u2705 All conditions nominal. "
                "Continue routine facility monitoring."
            )

        return recs
