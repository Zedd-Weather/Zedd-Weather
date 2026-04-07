"""
Construction intelligence engine for Zedd Weather.
Heuristic-based analysis of telemetry data to produce construction site
safety assessments and work-window recommendations.
"""
from .models import (
    ActivityProfile,
    ACTIVITY_PROFILES,
    SafetyAssessment,
    WorkWindow,
)


class ConstructionEngine:
    """
    Analyses weather telemetry and produces actionable construction site
    safety recommendations.

    All algorithms are heuristic — no external ML libraries required.
    """

    # Wind thresholds
    _HIGH_WIND_MS = 10.0          # m/s — caution threshold for most activities
    _EXTREME_WIND_MS = 18.0       # m/s — halt threshold for most activities

    # Temperature thresholds for worker safety
    _HEAT_CAUTION_C = 30.0        # °C — heat caution begins
    _HEAT_EXTREME_C = 40.0        # °C — extreme heat, outdoor work halts
    _COLD_CAUTION_C = 5.0         # °C — cold caution begins
    _COLD_EXTREME_C = -10.0       # °C — extreme cold

    # Pressure threshold
    _PRESSURE_STORM = 995.0       # hPa below which storm risk is flagged

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def analyze(self, telemetry: dict, activity: str = "general") -> dict:
        """
        Run a full construction site analysis for the given telemetry snapshot.

        Parameters
        ----------
        telemetry:
            Dict with keys: temperature (°C), humidity (%), pressure (hPa).
            Additional keys (wind_speed, uv_index, rainfall_mm) are used
            when present.
        activity:
            One of the keys in ACTIVITY_PROFILES (default: "general").

        Returns
        -------
        dict with keys:
            activity, risk_level, safety, work_window, weather_hazards,
            material_risks, recommendations
        """
        profile = self._get_profile(activity)
        safety = self.assess_worker_safety(telemetry)
        work_window = self.evaluate_work_window(telemetry, activity)
        hazards = self.detect_weather_hazards(telemetry, activity)
        material_risks = self.detect_material_risks(telemetry, activity)
        risk_level = self.compute_risk_level(telemetry, activity)

        recommendations = self._build_recommendations(
            telemetry, profile, safety, work_window, hazards, material_risks
        )

        return {
            "activity": activity,
            "activity_name": profile.name,
            "risk_level": risk_level,
            "safety": {
                "heat_stress_index": safety.heat_stress_index,
                "cold_stress_index": safety.cold_stress_index,
                "work_rest_ratio": safety.work_rest_ratio,
                "hydration_litres_hr": safety.hydration_litres_hr,
                "ppe_recommendations": safety.ppe_recommendations,
            },
            "work_window": {
                "safe_to_proceed": work_window.safe_to_proceed,
                "risk_level": work_window.risk_level,
                "halt_reasons": work_window.halt_reasons,
                "caution_reasons": work_window.caution_reasons,
                "recommended_delay_hours": work_window.recommended_delay_hours,
                "next_check_hours": work_window.next_check_hours,
            },
            "weather_hazards": hazards,
            "material_risks": material_risks,
            "recommendations": recommendations,
        }

    def assess_worker_safety(self, telemetry: dict) -> SafetyAssessment:
        """
        Assess worker safety conditions from atmospheric readings.

        Uses WBGT (Wet Bulb Globe Temperature) inspired approximation for
        heat stress and wind-chill for cold stress.

        Returns
        -------
        SafetyAssessment
        """
        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        uv_index = float(telemetry.get("uv_index", 0.0))

        # Heat stress index: simplified WBGT approximation
        # WBGT ≈ 0.7 * Tw + 0.2 * Tg + 0.1 * Td
        # Simplified: use humidity-adjusted temperature
        heat_index = self._compute_heat_index(temp, humidity)
        heat_stress = min(1.0, max(0.0, (heat_index - 25.0) / 25.0))

        # Cold stress: wind-chill factor
        wind_chill = self._compute_wind_chill(temp, wind_speed)
        cold_stress = min(1.0, max(0.0, (5.0 - wind_chill) / 25.0))

        # Work:rest ratio based on heat stress
        if heat_stress > 0.8:
            work_rest = "15:45"
        elif heat_stress > 0.6:
            work_rest = "30:30"
        elif heat_stress > 0.4:
            work_rest = "45:15"
        elif heat_stress > 0.2:
            work_rest = "50:10"
        else:
            work_rest = "60:0"

        # Hydration recommendation (litres per hour)
        base_hydration = 0.25  # baseline
        hydration = base_hydration + heat_stress * 0.75  # up to 1.0 L/hr

        # PPE recommendations
        ppe: list[str] = ["Hard hat", "High-visibility vest", "Safety boots"]
        if uv_index >= 6.0:
            ppe.append("UV-protective sunscreen (SPF 50+)")
            ppe.append("UV-blocking safety glasses")
        if uv_index >= 8.0:
            ppe.append("Wide-brim hard hat attachment")
        if temp < self._COLD_CAUTION_C:
            ppe.append("Insulated work gloves")
            ppe.append("Thermal base layers")
        if temp < -5.0:
            ppe.append("Balaclava / face protection")
        if wind_speed > self._HIGH_WIND_MS:
            ppe.append("Windproof outer layer")
        if humidity > 85.0 or float(telemetry.get("rainfall_mm", 0.0)) > 0:
            ppe.append("Waterproof outerwear")

        return SafetyAssessment(
            heat_stress_index=round(heat_stress, 2),
            cold_stress_index=round(cold_stress, 2),
            work_rest_ratio=work_rest,
            hydration_litres_hr=round(hydration, 2),
            ppe_recommendations=ppe,
        )

    def evaluate_work_window(self, telemetry: dict, activity: str) -> WorkWindow:
        """
        Determine whether the specified construction activity can safely proceed.

        Returns
        -------
        WorkWindow
        """
        profile = self._get_profile(activity)
        temp = float(telemetry.get("temperature", 20.0))
        pressure = float(telemetry.get("pressure", 1013.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        rainfall_mm = float(telemetry.get("rainfall_mm", 0.0))
        uv_index = float(telemetry.get("uv_index", 0.0))

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
                f"Rainfall ({rainfall_mm:.1f} mm) detected — activity is rain-sensitive."
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

        return WorkWindow(
            activity=activity,
            safe_to_proceed=safe_to_proceed,
            risk_level=risk_level,
            halt_reasons=halt_reasons,
            caution_reasons=caution_reasons,
            recommended_delay_hours=delay_hours,
            next_check_hours=next_check,
        )

    def detect_weather_hazards(self, telemetry: dict, activity: str) -> list[dict]:
        """
        Identify weather-related hazards for the construction site.

        Rules:
        - High wind → crane/scaffolding hazard
        - Lightning risk (low pressure + high humidity)
        - Reduced visibility
        - Extreme temperatures

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
                    "Halt all crane and elevated work immediately. "
                    "Secure loose materials and equipment."
                ),
            })
        elif wind_speed > self._HIGH_WIND_MS:
            hazards.append({
                "hazard": "High Wind",
                "risk_level": "high",
                "condition": f"Wind speed {wind_speed:.1f} m/s — elevated risk for work at height",
                "recommendation": (
                    "Suspend crane operations and scaffold work. "
                    "Secure sheeting and lightweight materials."
                ),
            })

        # Lightning / storm risk
        if pressure < self._PRESSURE_STORM and humidity > 75.0:
            hazards.append({
                "hazard": "Lightning / Storm Risk",
                "risk_level": "high",
                "condition": (
                    f"Low pressure ({pressure:.1f} hPa) with high humidity ({humidity:.1f}%) "
                    "indicates approaching storm"
                ),
                "recommendation": (
                    "Prepare to evacuate elevated positions. "
                    "Secure crane booms and suspend steel erection."
                ),
            })

        # Extreme heat
        if temp > self._HEAT_EXTREME_C:
            hazards.append({
                "hazard": "Extreme Heat",
                "risk_level": "critical",
                "condition": f"Temperature {temp:.1f}°C — extreme heat danger",
                "recommendation": (
                    "Halt outdoor work. Enforce shade breaks and hydration protocols."
                ),
            })
        elif temp > self._HEAT_CAUTION_C:
            heat_index = self._compute_heat_index(temp, humidity)
            if heat_index > 38.0:
                hazards.append({
                    "hazard": "Heat Stress",
                    "risk_level": "high" if heat_index > 45.0 else "medium",
                    "condition": (
                        f"Heat index {heat_index:.1f}°C (temp {temp:.1f}°C, "
                        f"humidity {humidity:.1f}%)"
                    ),
                    "recommendation": (
                        "Implement work/rest cycles. Provide shade and cool drinking water."
                    ),
                })

        # Extreme cold
        if temp < self._COLD_EXTREME_C:
            hazards.append({
                "hazard": "Extreme Cold",
                "risk_level": "critical",
                "condition": f"Temperature {temp:.1f}°C — frostbite risk",
                "recommendation": (
                    "Halt outdoor work. Provide heated rest areas. "
                    "Monitor for hypothermia symptoms."
                ),
            })
        elif temp < self._COLD_CAUTION_C:
            wind_chill = self._compute_wind_chill(temp, wind_speed)
            if wind_chill < -5.0:
                hazards.append({
                    "hazard": "Wind Chill",
                    "risk_level": "high" if wind_chill < -15.0 else "medium",
                    "condition": (
                        f"Wind chill {wind_chill:.1f}°C (temp {temp:.1f}°C, "
                        f"wind {wind_speed:.1f} m/s)"
                    ),
                    "recommendation": (
                        "Limit exposure time. Require thermal PPE and warm-up breaks."
                    ),
                })

        # Heavy rain / flooding
        if rainfall_mm > 15.0:
            hazards.append({
                "hazard": "Heavy Rainfall / Flooding",
                "risk_level": "high",
                "condition": f"Rainfall {rainfall_mm:.1f} mm — waterlogging and flooding risk",
                "recommendation": (
                    "Check excavation drainage. Halt concrete pours. "
                    "Monitor for slope instability."
                ),
            })
        elif rainfall_mm > 5.0:
            hazards.append({
                "hazard": "Moderate Rainfall",
                "risk_level": "medium",
                "condition": f"Rainfall {rainfall_mm:.1f} mm — slippery surfaces",
                "recommendation": (
                    "Ensure anti-slip measures on walkways and scaffolds. "
                    "Delay surface coating activities."
                ),
            })

        if not hazards:
            hazards.append({
                "hazard": "None identified",
                "risk_level": "low",
                "condition": "Current conditions are within normal safety parameters.",
                "recommendation": "Continue routine site safety monitoring.",
            })

        return hazards

    def detect_material_risks(self, telemetry: dict, activity: str) -> list[dict]:
        """
        Identify risks to construction materials from weather conditions.

        Rules:
        - Concrete: rain, extreme temp, fast drying from low humidity/high wind
        - Steel: condensation, ice, lightning
        - Paint/coatings: humidity, rain, temp
        - Timber: moisture, UV degradation

        Returns
        -------
        list of dicts with keys: material, risk_level, condition, recommendation
        """
        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        rainfall_mm = float(telemetry.get("rainfall_mm", 0.0))
        risks: list[dict] = []

        # Concrete risks
        if temp < 5.0:
            risks.append({
                "material": "Concrete",
                "risk_level": "high",
                "condition": f"Temperature {temp:.1f}°C — concrete may not cure properly",
                "recommendation": (
                    "Use accelerators or insulating blankets. "
                    "Do not pour if temperature is below 0°C."
                ),
            })
        if temp > 35.0 and humidity < 40.0:
            risks.append({
                "material": "Concrete",
                "risk_level": "high",
                "condition": (
                    f"Hot ({temp:.1f}°C) and dry ({humidity:.1f}%) — rapid moisture loss"
                ),
                "recommendation": (
                    "Apply curing compound immediately after finishing. "
                    "Use chilled mixing water and ice."
                ),
            })

        # Steel / metalwork risks
        if humidity > 85.0 and temp < 15.0:
            risks.append({
                "material": "Steel / Metalwork",
                "risk_level": "medium",
                "condition": (
                    f"High humidity ({humidity:.1f}%) at low temp ({temp:.1f}°C) — "
                    "condensation risk"
                ),
                "recommendation": (
                    "Inspect steel surfaces for moisture before welding or bolting. "
                    "Pre-heat if necessary."
                ),
            })
        if temp < 0.0:
            risks.append({
                "material": "Steel / Metalwork",
                "risk_level": "high",
                "condition": f"Temperature {temp:.1f}°C — ice formation on steel",
                "recommendation": (
                    "De-ice steel connections before assembly. "
                    "Check for brittle fracture risk in cold conditions."
                ),
            })

        # Paint / coating risks
        if humidity > 75.0:
            risks.append({
                "material": "Paint / Coatings",
                "risk_level": "medium",
                "condition": f"High humidity ({humidity:.1f}%) may prevent proper adhesion",
                "recommendation": (
                    "Delay painting until humidity drops below 75%. "
                    "Monitor dew point temperature."
                ),
            })

        # Timber / wood risks
        if rainfall_mm > 5.0 or humidity > 85.0:
            risks.append({
                "material": "Timber / Wood",
                "risk_level": "medium",
                "condition": (
                    f"Moisture exposure (rain {rainfall_mm:.1f} mm, "
                    f"humidity {humidity:.1f}%) — swelling and warping risk"
                ),
                "recommendation": (
                    "Cover stored timber. Do not install saturated wood. "
                    "Allow drying before enclosure."
                ),
            })

        if not risks:
            risks.append({
                "material": "None identified",
                "risk_level": "low",
                "condition": "Current conditions pose no significant material risks.",
                "recommendation": "Continue routine material storage and handling.",
            })

        return risks

    def compute_risk_level(self, telemetry: dict, activity: str) -> str:
        """
        Compute overall construction site risk level from telemetry.

        Returns
        -------
        "low", "medium", "high", or "critical"
        """
        work_window = self.evaluate_work_window(telemetry, activity)
        hazards = self.detect_weather_hazards(telemetry, activity)
        material_risks = self.detect_material_risks(telemetry, activity)
        safety = self.assess_worker_safety(telemetry)

        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        current = risk_order.get(work_window.risk_level, 0)

        # Escalate based on hazards and material risks
        for item in hazards + material_risks:
            rl = item.get("risk_level", "low")
            current = max(current, risk_order.get(rl, 0))

        # Extreme worker safety indices escalate risk
        if safety.heat_stress_index > 0.8 or safety.cold_stress_index > 0.8:
            current = max(current, risk_order["critical"])
        elif safety.heat_stress_index > 0.6 or safety.cold_stress_index > 0.6:
            current = max(current, risk_order["high"])

        levels = {v: k for k, v in risk_order.items()}
        return levels[current]

    # ---------------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------------

    def _get_profile(self, activity: str) -> ActivityProfile:
        """Return the activity profile, falling back to general if unknown."""
        return ACTIVITY_PROFILES.get(activity.lower(), ACTIVITY_PROFILES["general"])

    @staticmethod
    def _compute_heat_index(temp: float, humidity: float) -> float:
        """
        Simplified heat index (°C) from temperature and relative humidity.

        Uses the Rothfusz regression adapted to Celsius.
        Returns the raw temperature when below the heat-index threshold.
        """
        if temp < 27.0 or humidity < 40.0:
            return temp

        # Rothfusz regression (Celsius adaptation)
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
            - 0.000004 * t * t * r * r  # very small correction term
        )
        return round(hi, 1)

    @staticmethod
    def _compute_wind_chill(temp: float, wind_speed_ms: float) -> float:
        """
        Compute wind chill temperature (°C).

        Uses the North American wind chill index formula (adapted to m/s).
        Only applicable when temp < 10°C and wind > 1.3 m/s.
        """
        if temp >= 10.0 or wind_speed_ms < 1.3:
            return temp

        # Convert m/s to km/h for the standard formula
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
        profile: ActivityProfile,
        safety: SafetyAssessment,
        work_window: WorkWindow,
        hazards: list[dict],
        material_risks: list[dict],
    ) -> list[str]:
        """Compile a human-readable list of prioritised recommendations."""
        recs: list[str] = []

        # Halt reasons first
        for reason in work_window.halt_reasons:
            recs.append(f"🚫 HALT: {reason}")

        # Safety recommendations
        if safety.heat_stress_index > 0.6:
            recs.append(
                f"🌡️ Heat stress elevated ({safety.heat_stress_index:.0%}): "
                f"enforce {safety.work_rest_ratio} work:rest cycle, "
                f"hydrate {safety.hydration_litres_hr:.1f} L/hr."
            )
        if safety.cold_stress_index > 0.6:
            recs.append(
                f"❄️ Cold stress elevated ({safety.cold_stress_index:.0%}): "
                "require thermal PPE and warm-up breaks."
            )

        # Hazard recommendations
        for h in hazards:
            if h["risk_level"] in ("high", "critical"):
                recs.append(f"⚠️ {h['hazard']}: {h['recommendation']}")

        # Material risk recommendations
        for m in material_risks:
            if m["risk_level"] in ("high", "critical"):
                recs.append(f"🏗️ {m['material']}: {m['recommendation']}")

        # Caution items
        for reason in work_window.caution_reasons:
            recs.append(f"⚡ Caution: {reason}")

        if not recs:
            recs.append("✅ Conditions are favourable for construction. Continue routine safety monitoring.")

        return recs
