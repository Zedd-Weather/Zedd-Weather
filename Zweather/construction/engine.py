"""
Construction intelligence engine for Zedd Weather.
Heuristic-based analysis of telemetry data to produce construction site
safety assessments, work-window recommendations, and material risk reports.

Supports UK regional climate profiles (Glasgow, London, Cardiff, etc.)
with seasonally-adjusted thresholds and UK-specific hazard detection.
"""
from Zweather.utils import compute_heat_index, compute_wind_chill

from .models import (
    ActivityProfile,
    ACTIVITY_PROFILES,
    UKRegion,
    Season,
    SafetyAssessment,
    WorkWindow,
    HazardReport,
    MaterialRisk,
)
from Zweather.global_regions import (
    get_region,
    resolve_season,
    region_adjusted_heat_threshold,
    region_adjusted_cold_threshold,
    region_adjusted_wind_threshold,
    region_adjusted_rain_threshold,
)


class ConstructionEngine:
    """
    Analyses weather telemetry and produces actionable construction site
    safety recommendations.

    Accepts an optional ``region`` parameter (UK region or city name) and
    optional ``season`` to adjust thresholds for local climate norms.

    All algorithms are heuristic — no external ML libraries required.
    """

    # Wind thresholds (Midlands baseline)
    _HIGH_WIND_MS = 10.0
    _EXTREME_WIND_MS = 18.0

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
        activity: str = "general",
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> dict:
        """
        Run a full construction site analysis for the given telemetry snapshot.

        Parameters
        ----------
        telemetry:
            Dict with keys: temperature (°C), humidity (%), pressure (hPa).
            Optional keys: wind_speed, wind_gust, uv_index, rainfall_mm,
            visibility_m, cloud_cover_pct.
        activity:
            One of the keys in ACTIVITY_PROFILES (default: ``"general"``).
        region:
            UK region or city name (e.g. ``"glasgow"``, ``"london"``).
            Defaults to Midlands.
        season:
            Season override if automatic detection is not desired.

        Returns
        -------
        dict with keys: activity, activity_name, risk_level, region, season,
        safety, work_window, weather_hazards, material_risks, recommendations.
        """
        profile = self._get_profile(activity)
        rp = get_region(region)
        sn = resolve_season(season)

        safety = self.assess_worker_safety(telemetry, region, season)
        work_window = self.evaluate_work_window(telemetry, activity, region, season)
        hazards = self.detect_weather_hazards(telemetry, activity, region, season)
        material_risks = self.detect_material_risks(telemetry, activity, region, season)
        risk_level = self.compute_risk_level(telemetry, activity, region, season)

        recommendations = self._build_recommendations(
            telemetry, profile, safety, work_window, hazards, material_risks,
        )

        return {
            "activity": activity,
            "activity_name": profile.name,
            "risk_level": risk_level,
            "region": rp.name,
            "season": sn.value,
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
            "weather_hazards": [self._hazard_to_dict(h) for h in hazards],
            "material_risks": [self._risk_to_dict(r) for r in material_risks],
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Worker safety
    # ------------------------------------------------------------------

    def assess_worker_safety(
        self,
        telemetry: dict,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> SafetyAssessment:
        """
        Assess worker safety conditions with regionally-adjusted thresholds.

        Uses WBGT-inspired approximation for heat stress and wind-chill
        for cold stress.
        """
        rp = get_region(region)
        sn = resolve_season(season)

        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        uv_index = float(telemetry.get("uv_index", 0.0))

        # --- Heat stress ---
        heat_caution = region_adjusted_heat_threshold(self._HEAT_CAUTION_C, rp, sn)
        heat_extreme = region_adjusted_heat_threshold(self._HEAT_EXTREME_C, rp, sn)

        heat_index = self._compute_heat_index(temp, humidity)
        if heat_index > heat_caution:
            heat_stress = min(1.0, max(0.0, (heat_index - heat_caution) / (heat_extreme - heat_caution + 5.0)))
        else:
            heat_stress = 0.0

        # --- Cold stress ---
        cold_caution = region_adjusted_cold_threshold(self._COLD_CAUTION_C, rp, sn)
        cold_extreme = region_adjusted_cold_threshold(self._COLD_EXTREME_C, rp, sn)

        wind_chill = self._compute_wind_chill(temp, wind_speed)
        if wind_chill < cold_caution:
            cold_stress = min(1.0, max(0.0, (cold_caution - wind_chill) / (cold_caution - cold_extreme + 5.0)))
        else:
            cold_stress = 0.0

        # --- Work:rest ratio ---
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

        base_hydration = 0.25
        hydration = base_hydration + heat_stress * 0.75

        # --- PPE ---
        ppe: list[str] = ["Hard hat", "High-visibility vest", "Safety boots"]
        if uv_index >= 6.0:
            ppe.append("UV-protective sunscreen (SPF 50+)")
            ppe.append("UV-blocking safety glasses")
        if uv_index >= 8.0:
            ppe.append("Wide-brim hard hat attachment")
        if temp < cold_caution:
            ppe.append("Insulated work gloves")
            ppe.append("Thermal base layers")
        if temp < cold_caution - 5.0:
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

    # ------------------------------------------------------------------
    # Work window
    # ------------------------------------------------------------------

    def evaluate_work_window(
        self,
        telemetry: dict,
        activity: str,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> WorkWindow:
        """
        Determine whether a construction activity can safely proceed
        given current weather and the local region's climate norms.
        """
        profile = self._get_profile(activity)
        rp = get_region(region)
        sn = resolve_season(season)

        temp = float(telemetry.get("temperature", 20.0))
        pressure = float(telemetry.get("pressure", 1013.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        wind_gust = float(telemetry.get("wind_gust", wind_speed))
        rainfall_mm = float(telemetry.get("rainfall_mm", 0.0))
        uv_index = float(telemetry.get("uv_index", 0.0))
        visibility_m = float(telemetry.get("visibility_m", 9999.0))
        cloud_cover = float(telemetry.get("cloud_cover_pct", 50.0))

        halt_reasons: list[str] = []
        caution_reasons: list[str] = []

        # Apply region-adjusted thresholds
        safe_min = region_adjusted_cold_threshold(profile.temp_safe_min, rp, sn)
        safe_max = region_adjusted_heat_threshold(profile.temp_safe_max, rp, sn)
        halt_min = region_adjusted_cold_threshold(profile.temp_halt_min, rp, sn)
        halt_max = region_adjusted_heat_threshold(profile.temp_halt_max, rp, sn)
        wind_op = region_adjusted_wind_threshold(profile.wind_max_operational, rp)
        wind_halt = region_adjusted_wind_threshold(profile.wind_halt, rp)
        rain_limit = region_adjusted_rain_threshold(profile.rain_max_mm_hr, rp)

        # Temperature
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

        # Sustained wind
        if wind_speed > wind_halt:
            halt_reasons.append(
                f"Wind speed ({wind_speed:.1f} m/s) exceeds halt limit ({wind_halt:.1f} m/s)."
            )
        elif wind_speed > wind_op:
            caution_reasons.append(
                f"Wind speed ({wind_speed:.1f} m/s) exceeds operational limit."
            )

        # Wind gust
        gust_halt = profile.wind_gust_halt
        if gust_halt and wind_gust >= gust_halt:
            halt_reasons.append(
                f"Wind gust ({wind_gust:.1f} m/s) exceeds gust safety limit ({gust_halt:.1f} m/s)."
            )
        elif gust_halt and wind_gust >= wind_halt:
            caution_reasons.append(
                f"Wind gust ({wind_gust:.1f} m/s) approaching safety limit."
            )

        # Rainfall
        if profile.rain_sensitive and rainfall_mm > rain_limit:
            halt_reasons.append(
                f"Rainfall ({rainfall_mm:.1f} mm) — activity is rain-sensitive."
            )
        elif not profile.rain_sensitive and rainfall_mm > rain_limit:
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

        # Pressure / storm
        storm_threshold = region_adjusted_rain_threshold(
            profile.pressure_storm_threshold, rp,
        )
        if pressure < storm_threshold:
            caution_reasons.append(
                f"Low pressure ({pressure:.1f} hPa) — storm risk elevated."
            )

        # UV
        if uv_index >= profile.uv_halt_threshold:
            halt_reasons.append(
                f"UV index ({uv_index:.1f}) exceeds halt threshold."
            )
        elif uv_index >= profile.uv_caution_threshold:
            caution_reasons.append(
                f"UV index ({uv_index:.1f}) elevated — sun protection required."
            )

        # Cloud cover — prolonged overcast affects morale, solar-powered tools
        if cloud_cover > 90.0 and sn in (Season.AUTUMN, Season.WINTER):
            caution_reasons.append(
                f"Near-total cloud cover ({cloud_cover:.0f}%) — reduced natural lighting."
            )

        # Overall assessment
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
            region=rp.name,
            season=sn.value,
        )

    # ------------------------------------------------------------------
    # Weather hazard detection
    # ------------------------------------------------------------------

    def detect_weather_hazards(
        self,
        telemetry: dict,
        activity: str,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> list[HazardReport]:
        """
        Identify weather-related hazards with UK-region awareness.
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
        rain_light = region_adjusted_rain_threshold(rp.rain_light_threshold, rp)
        rain_moderate = region_adjusted_rain_threshold(rp.rain_moderate_threshold, rp)

        hazards: list[HazardReport] = []

        # --- Wind hazards ---
        if wind_speed > wind_extreme or wind_gust > wind_extreme * 1.2:
            hazards.append(HazardReport(
                hazard="Extreme Wind",
                risk_level="critical",
                condition=(
                    f"Wind {wind_speed:.1f} m/s (gust {wind_gust:.1f} m/s) "
                    f"exceeds safe limits for {rp.name}"
                ),
                recommendation=(
                    "Halt all crane and elevated work immediately. "
                    "Secure loose materials, sheeting, and scaffolding."
                ),
                affected_activities=["crane_operations", "roofing", "scaffolding", "steel_erection"],
            ))
        elif wind_speed > wind_high:
            hazards.append(HazardReport(
                hazard="High Wind",
                risk_level="high",
                condition=(
                    f"Wind speed {wind_speed:.1f} m/s — elevated risk "
                    f"for work at height in {rp.name}"
                ),
                recommendation=(
                    "Suspend crane operations and scaffold work. "
                    "Secure lightweight materials and site hoardings."
                ),
                affected_activities=["crane_operations", "roofing", "scaffolding"],
            ))

        # --- Storm / lightning risk ---
        if pressure < storm_pressure and humidity > 75.0:
            hazards.append(HazardReport(
                hazard="Storm / Lightning Risk",
                risk_level="high",
                condition=(
                    f"Low pressure ({pressure:.1f} hPa) with high humidity "
                    f"({humidity:.1f}%) — approaching storm"
                ),
                recommendation=(
                    "Evacuate elevated positions. "
                    "Secure crane booms and suspend steel erection. "
                    "Unplug sensitive equipment."
                ),
                affected_activities=["crane_operations", "steel_erection", "demolition"],
            ))

        # --- Heat ---
        if temp > heat_extreme:
            hazards.append(HazardReport(
                hazard="Extreme Heat",
                risk_level="critical",
                condition=(
                    f"Temperature {temp:.1f}°C exceeds {rp.name} extreme "
                    f"heat threshold ({heat_extreme:.0f}°C)"
                ),
                recommendation="Halt outdoor work. Enforce shade breaks and hydration protocols.",
            ))
        elif temp > heat_caution:
            hi = self._compute_heat_index(temp, humidity)
            if hi > 35.0:
                hazards.append(HazardReport(
                    hazard="Heat Stress",
                    risk_level="high" if hi > 42.0 else "medium",
                    condition=(
                        f"Heat index {hi:.1f}°C (temp {temp:.1f}°C, "
                        f"humidity {humidity:.1f}%) in {rp.name}"
                    ),
                    recommendation=(
                        "Implement work/rest cycles. "
                        "Provide shade and cool drinking water."
                    ),
                ))

        # --- Cold ---
        if temp < cold_extreme:
            hazards.append(HazardReport(
                hazard="Extreme Cold",
                risk_level="critical",
                condition=f"Temperature {temp:.1f}°C — frostbite risk in {rp.name}",
                recommendation=(
                    "Halt outdoor work. Provide heated rest areas. "
                    "Monitor for hypothermia symptoms."
                ),
            ))
        elif temp < cold_caution:
            wc = self._compute_wind_chill(temp, wind_speed)
            if wc < -5.0:
                hazards.append(HazardReport(
                    hazard="Wind Chill / Cold Stress",
                    risk_level="high" if wc < -15.0 else "medium",
                    condition=(
                        f"Wind chill {wc:.1f}°C (temp {temp:.1f}°C, "
                        f"wind {wind_speed:.1f} m/s) in {rp.name}"
                    ),
                    recommendation=(
                        "Limit exposure time. Require thermal PPE and warm-up breaks."
                    ),
                ))

        # --- Rainfall hazards ---
        if rainfall_mm > rain_moderate * 2:
            hazards.append(HazardReport(
                hazard="Heavy Rainfall / Flooding",
                risk_level="high",
                condition=(
                    f"Rainfall {rainfall_mm:.1f} mm — exceeds {rp.name} "
                    f"heavy rain threshold. Flood risk modifier: {rp.flood_risk_modifier:.1f}x"
                ),
                recommendation=(
                    "Check excavation drainage. Halt concrete pours. "
                    "Monitor for slope instability and surface water ingress."
                ),
                affected_activities=["excavation", "ground_works", "concrete_pouring"],
            ))
        elif rainfall_mm > rain_moderate:
            hazards.append(HazardReport(
                hazard="Moderate Rainfall",
                risk_level="medium",
                condition=(
                    f"Rainfall {rainfall_mm:.1f} mm — moderate for {rp.name} "
                    f"(threshold: {rain_moderate:.1f} mm)"
                ),
                recommendation=(
                    "Ensure anti-slip measures on walkways and scaffolds. "
                    "Delay surface coating and sealant activities."
                ),
            ))

        # --- Visibility ---
        if visibility_m < 50.0:
            hazards.append(HazardReport(
                hazard="Dense Fog / Very Poor Visibility",
                risk_level="critical",
                condition=f"Visibility {visibility_m:.0f} m — dangerous for all site movement",
                recommendation=(
                    "Halt crane operations and vehicle movements. "
                    "Use audible warning signals. Ensure site lighting is active."
                ),
                affected_activities=["crane_operations", "demolition", "excavation"],
            ))
        elif visibility_m < 200.0:
            hazards.append(HazardReport(
                hazard="Reduced Visibility",
                risk_level="medium",
                condition=(
                    f"Visibility {visibility_m:.0f} m — reduced for "
                    f"{rp.name} norms ({rp.visibility_norm_m:.0f} m typical)"
                ),
                recommendation=(
                    "Reduce vehicle speeds. Use signalers for crane operations. "
                    "Increase site lighting."
                ),
            ))

        # --- Frost / ice (UK-specific: groundworks impact) ---
        if temp < 0.0 and humidity > 70.0:
            hazards.append(HazardReport(
                hazard="Frost / Ice Risk",
                risk_level="high" if temp < -3.0 else "medium",
                condition=(
                    f"Temperature {temp:.1f}°C with humidity {humidity:.1f}% — "
                    f"ice formation likely. Frost probability: {rp.frost_probability:.0%}"
                ),
                recommendation=(
                    "Treat walkways and access roads with de-icer. "
                    "Check scaffold boards for ice. Suspend steel erection if ice present."
                ),
                affected_activities=["steel_erection", "scaffolding", "ground_works"],
            ))

        # --- Flooding risk (UK-specific) ---
        if rainfall_mm > rain_moderate and rp.flood_risk_modifier > 1.0:
            sustained_rain = telemetry.get("rain_duration_hours", 0.0)
            if sustained_rain > 2.0 or rainfall_mm > rain_moderate * 1.5:
                hazards.append(HazardReport(
                    hazard="Surface Water Flooding Risk",
                    risk_level="high",
                    condition=(
                        f"Prolonged/heavy rainfall ({rainfall_mm:.1f} mm over "
                        f"{sustained_rain:.1f}h) in {rp.name} — flood risk "
                        f"modifier {rp.flood_risk_modifier:.1f}x"
                    ),
                    recommendation=(
                        "Inspect excavations for water ingress. "
                        "Ensure pumps are operational. "
                        "Move materials to high ground. Monitor weather radar."
                    ),
                    affected_activities=["excavation", "ground_works", "concrete_pouring"],
                ))

        if not hazards:
            hazards.append(HazardReport(
                hazard="None identified",
                risk_level="low",
                condition=f"Current conditions are within normal safety parameters for {rp.name}.",
                recommendation="Continue routine site safety monitoring.",
            ))

        return hazards

    # ------------------------------------------------------------------
    # Material risk detection
    # ------------------------------------------------------------------

    def detect_material_risks(
        self,
        telemetry: dict,
        activity: str,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> list[MaterialRisk]:
        """
        Identify risks to construction materials from weather conditions,
        with UK-specific risks (damp rot, condensation, frost heave).
        """
        rp = get_region(region)
        sn = resolve_season(season)

        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        rainfall_mm = float(telemetry.get("rainfall_mm", 0.0))
        wind_speed = float(telemetry.get("wind_speed", 0.0))
        rain_duration = float(telemetry.get("rain_duration_hours", 0.0))

        cold_caution = region_adjusted_cold_threshold(self._COLD_CAUTION_C, rp, sn)
        heat_caution = region_adjusted_heat_threshold(self._HEAT_CAUTION_C, rp, sn)
        rain_light = region_adjusted_rain_threshold(rp.rain_light_threshold, rp)

        risks: list[MaterialRisk] = []

        # --- Concrete ---
        if temp < cold_caution:
            risks.append(MaterialRisk(
                material="Concrete",
                risk_level="high",
                condition=(
                    f"Temperature {temp:.1f}°C — concrete curing slowed. "
                    f"Safe range: {cold_caution:.0f}–{heat_caution:.0f}°C"
                ),
                recommendation=(
                    "Use accelerated curing methods or insulating blankets. "
                    "Do not pour below 0°C."
                ),
            ))
        if temp > heat_caution and humidity < 40.0:
            risks.append(MaterialRisk(
                material="Concrete",
                risk_level="high",
                condition=f"Hot ({temp:.1f}°C) and dry ({humidity:.1f}%) — rapid moisture loss",
                recommendation="Apply curing compound. Use chilled mixing water.",
            ))
        if rainfall_mm > rain_light:
            risks.append(MaterialRisk(
                material="Concrete",
                risk_level="medium",
                condition=f"Rainfall {rainfall_mm:.1f} mm — washout risk for fresh concrete",
                recommendation="Cover fresh concrete immediately. Delay pour if heavy rain forecast.",
            ))

        # --- Steel / metalwork ---
        if humidity > 80.0 and temp < 15.0:
            risks.append(MaterialRisk(
                material="Steel / Metalwork",
                risk_level="medium",
                condition=(
                    f"High humidity ({humidity:.1f}%) at {temp:.1f}°C — "
                    f"condensation risk (common in {rp.name})"
                ),
                recommendation=(
                    "Inspect steel for moisture before welding or bolting. "
                    "Pre-heat if necessary. Store sections under cover."
                ),
            ))
        if humidity > 85.0 and temp < 5.0:
            risks.append(MaterialRisk(
                material="Steel / Metalwork",
                risk_level="high",
                condition=(
                    f"Sustained damp conditions — accelerated corrosion "
                    f"risk in {rp.name}"
                ),
                recommendation=(
                    "Apply temporary corrosion protection. "
                    "Ensure adequate ventilation in storage areas."
                ),
            ))
        if temp < -2.0:
            risks.append(MaterialRisk(
                material="Steel / Metalwork",
                risk_level="high",
                condition=f"Temperature {temp:.1f}°C — ice formation on steel",
                recommendation="De-ice connections before assembly. Check for brittle fracture risk.",
            ))

        # --- Paint / coatings ---
        if humidity > 75.0:
            risks.append(MaterialRisk(
                material="Paint / Coatings",
                risk_level="medium",
                condition=(
                    f"High humidity ({humidity:.1f}%) — may prevent proper "
                    f"adhesion in {rp.name} climate"
                ),
                recommendation="Delay painting until humidity drops below 75%. Monitor dew point.",
            ))
        if rainfall_mm > rain_light:
            risks.append(MaterialRisk(
                material="Paint / Coatings",
                risk_level="high",
                condition="Rain within application window — coating washout risk",
                recommendation="Postpone coating work. Allow 24h dry time after rain.",
            ))

        # --- Timber / wood (UK-specific: damp rot risk) ---
        if rainfall_mm > rain_light or humidity > 80.0:
            risk_level = "high" if (rain_duration > 24.0 or humidity > 90.0) else "medium"
            risks.append(MaterialRisk(
                material="Timber / Wood",
                risk_level=risk_level,
                condition=(
                    f"Moisture exposure: rain {rainfall_mm:.1f} mm, "
                    f"humidity {humidity:.1f}% over {rain_duration:.1f}h — "
                    f"swelling, warping, and damp rot risk in {rp.name}"
                ),
                recommendation=(
                    "Cover stored timber. Do not install saturated wood. "
                    "Allow drying before enclosure. Treat with preservative "
                    "if prolonged damp expected."
                ),
            ))

        # --- UK-specific: frost heave risk for ground works ---
        if temp < -2.0 and sn in (Season.WINTER, Season.AUTUMN):
            risks.append(MaterialRisk(
                material="Ground / Foundation",
                risk_level="high",
                condition=(
                    f"Sub-zero temperature ({temp:.1f}°C) — frost heave "
                    f"risk to shallow foundations in {rp.name}. "
                    f"Frost probability: {rp.frost_probability:.0%}"
                ),
                recommendation=(
                    "Protect exposed foundations with insulated blankets. "
                    "Delay ground works until thaw. Monitor ground temperature."
                ),
            ))

        # --- UK-specific: material degradation from persistent damp ---
        if humidity > 85.0 and rain_duration > 48.0:
            risks.append(MaterialRisk(
                material="General Materials Storage",
                risk_level="medium",
                condition=(
                    f"Prolonged damp conditions ({rain_duration:.0f}h) — "
                    f"risk to packaging, gypsum, adhesives, and insulation"
                ),
                recommendation=(
                    "Move sensitive materials indoors or under waterproof cover. "
                    "Ensure storage areas are ventilated. Discard water-damaged materials."
                ),
            ))

        if not risks:
            risks.append(MaterialRisk(
                material="None identified",
                risk_level="low",
                condition=f"Conditions are safe for material storage and handling in {rp.name}.",
                recommendation="Continue routine material storage and handling.",
            ))

        return risks

    # ------------------------------------------------------------------
    # Risk level computation
    # ------------------------------------------------------------------

    def compute_risk_level(
        self,
        telemetry: dict,
        activity: str,
        region: str | UKRegion | None = None,
        season: str | Season | None = None,
    ) -> str:
        """
        Compute overall construction site risk level.

        Aggregates work window, hazards, material risks, and worker safety
        into a single level: ``"low"``, ``"medium"``, ``"high"``, ``"critical"``.
        """
        work_window = self.evaluate_work_window(telemetry, activity, region, season)
        hazards = self.detect_weather_hazards(telemetry, activity, region, season)
        material_risks = self.detect_material_risks(telemetry, activity, region, season)
        safety = self.assess_worker_safety(telemetry, region, season)

        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        current = risk_order.get(work_window.risk_level, 0)

        for item in hazards + material_risks:
            rl = item.risk_level
            current = max(current, risk_order.get(rl, 0))

        if safety.heat_stress_index > 0.8 or safety.cold_stress_index > 0.8:
            current = max(current, risk_order["critical"])
        elif safety.heat_stress_index > 0.6 or safety.cold_stress_index > 0.6:
            current = max(current, risk_order["high"])

        levels = {v: k for k, v in risk_order.items()}
        return levels[current]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_profile(self, activity: str) -> ActivityProfile:
        return ACTIVITY_PROFILES.get(activity.lower(), ACTIVITY_PROFILES["general"])

    @staticmethod
    def _compute_heat_index(temp: float, humidity: float) -> float:
        return compute_heat_index(temp, humidity)

    @staticmethod
    def _compute_wind_chill(temp: float, wind_speed_ms: float) -> float:
        return compute_wind_chill(temp, wind_speed_ms)

    @staticmethod
    def _hazard_to_dict(h: HazardReport) -> dict:
        return {
            "hazard": h.hazard,
            "risk_level": h.risk_level,
            "condition": h.condition,
            "recommendation": h.recommendation,
            "affected_activities": h.affected_activities,
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
        profile: ActivityProfile,
        safety: SafetyAssessment,
        work_window: WorkWindow,
        hazards: list[HazardReport],
        material_risks: list[MaterialRisk],
    ) -> list[str]:
        """Compile a human-readable list of prioritised recommendations."""
        recs: list[str] = []

        for reason in work_window.halt_reasons:
            recs.append(f"HALT: {reason}")

        if safety.heat_stress_index > 0.6:
            recs.append(
                f"Heat stress elevated ({safety.heat_stress_index:.0%}): "
                f"enforce {safety.work_rest_ratio} work:rest cycle, "
                f"hydrate {safety.hydration_litres_hr:.1f} L/hr."
            )
        if safety.cold_stress_index > 0.6:
            recs.append(
                f"Cold stress elevated ({safety.cold_stress_index:.0%}): "
                "require thermal PPE and warm-up breaks."
            )

        for h in hazards:
            if h.risk_level in ("high", "critical"):
                recs.append(f"{h.hazard}: {h.recommendation}")

        for m in material_risks:
            if m.risk_level in ("high", "critical"):
                recs.append(f"{m.material}: {m.recommendation}")

        for reason in work_window.caution_reasons:
            recs.append(f"Caution: {reason}")

        if not recs:
            recs.append(
                f"Conditions are favourable for construction "
                f"in {work_window.region}. Continue routine safety monitoring."
            )

        return recs
