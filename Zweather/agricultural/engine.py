"""
Agricultural intelligence engine for Zedd Weather.
Heuristic-based analysis of telemetry data to produce crop recommendations.
"""
import math
from typing import Optional

from .models import (
    CropProfile,
    CROP_PROFILES,
    GrowthStage,
    IrrigationSchedule,
    SoilMoisturePrediction,
)


class AgriculturalEngine:
    """
    Analyses weather telemetry and produces actionable agricultural recommendations.

    All algorithms are heuristic — no external ML libraries required.
    """

    # Thresholds used across multiple methods
    _HIGH_HUMIDITY_THRESHOLD = 80.0   # % RH above which fungal/disease risk rises
    _LOW_HUMIDITY_THRESHOLD = 35.0    # % RH below which spider-mite risk rises
    _HIGH_TEMP_THRESHOLD = 32.0       # °C above which heat-stress insects thrive
    _PRESSURE_STORM = 990.0           # hPa below which storm risk is flagged

    # ET estimation constants (Hargreaves-like approximation)
    # Even under fully overcast/humid conditions some solar radiation reaches the
    # crop; floor the humidity proxy at 10 % to avoid zero ET.
    _MIN_SOLAR_FRACTION = 0.1
    # Scales the dimensionless Hargreaves coefficient to realistic daily mm/day
    # values (calibrated to ~2–8 mm/day across typical tropical/subtropical ranges).
    _ET_MM_SCALE = 10.0

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def analyze(self, telemetry: dict, crop: str = "maize") -> dict:
        """
        Run a full agricultural analysis for the given telemetry snapshot.

        Parameters
        ----------
        telemetry:
            Dict with keys: temperature (°C), humidity (%), pressure (hPa).
            Additional keys (wind_speed, uv_index, rainfall_mm) are used when present.
        crop:
            One of the keys in CROP_PROFILES (default: "maize").

        Returns
        -------
        dict with keys:
            crop, risk_level, soil_moisture, irrigation, pest_risks,
            disease_risks, weather_stress, recommendations
        """
        profile = self._get_profile(crop)
        soil = self.predict_soil_moisture(telemetry)
        irrigation = self.irrigation_schedule(telemetry, crop)
        pest_risks = self.detect_pest_risk(telemetry, crop)
        disease_risks = self.detect_disease_risk(telemetry, crop)
        stress = self.weather_stress_analysis(telemetry, crop)
        risk_level = self.compute_risk_level(telemetry, crop)

        recommendations = self._build_recommendations(
            telemetry, profile, soil, irrigation, pest_risks, disease_risks, stress
        )

        return {
            "crop": crop,
            "crop_name": profile.name,
            "risk_level": risk_level,
            "soil_moisture": {
                "estimated_vwc_pct": soil.estimated_vwc_pct,
                "confidence": soil.confidence,
                "days_to_irrigation": soil.days_to_irrigation,
                "irrigation_volume_mm": soil.irrigation_volume_mm,
            },
            "irrigation": {
                "recommended": irrigation.recommended,
                "urgency": irrigation.urgency,
                "volume_mm": irrigation.volume_mm,
                "reason": irrigation.reason,
                "next_check_hours": irrigation.next_check_hours,
            },
            "pest_risks": pest_risks,
            "disease_risks": disease_risks,
            "weather_stress": stress,
            "recommendations": recommendations,
        }

    def predict_soil_moisture(self, telemetry: dict) -> SoilMoisturePrediction:
        """
        Estimate volumetric soil water content from atmospheric readings.

        Uses a simplified Penman-Monteith inspired evapotranspiration proxy:
        ET_o ≈ 0.0023 * (T_mean + 17.8) * (T_max - T_min)^0.5 * R_a
        where R_a is approximated from a reference solar radiation constant.

        Without multi-reading min/max we fall back to a humidity-adjusted proxy.

        Returns
        -------
        SoilMoisturePrediction
        """
        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        rainfall_mm = float(telemetry.get("rainfall_mm", 0.0))

        # Simplified daily ET estimate (mm/day) using Hargreaves-like approximation
        # Reference ET ≈ 0.0135 * (T + 17.8) * solar_fraction
        solar_fraction = max(self._MIN_SOLAR_FRACTION, (100.0 - humidity) / 100.0)  # proxy: dry = sunny
        et_daily = 0.0135 * (temp + 17.8) * solar_fraction * self._ET_MM_SCALE

        # Start from an assumed "field capacity" baseline (VWC ~35 %)
        baseline_vwc = 35.0
        # Humidity adds moisture proxy; rainfall adds directly
        humidity_contrib = (humidity - 50.0) * 0.15  # ±% deviation from 50 %
        rain_contrib = rainfall_mm * 0.5             # rough soil infiltration factor
        et_loss = et_daily * 0.5                     # half-day proxy

        estimated_vwc = max(5.0, min(55.0, baseline_vwc + humidity_contrib + rain_contrib - et_loss))

        # Days to irrigation: assume crop needs irrigation below ~20 % VWC
        deficit = max(0.0, 20.0 - estimated_vwc)
        daily_depletion = max(0.1, et_daily - rainfall_mm * 0.3)
        days_to_irr = int(max(0, (estimated_vwc - 20.0) / daily_depletion)) if estimated_vwc > 20.0 else 0

        # Irrigation volume to refill to field capacity
        irr_volume = max(0.0, (35.0 - estimated_vwc) * 0.5)  # simplified mm equivalent

        # Confidence: lower when humidity is very high or low (proxy less reliable)
        confidence = max(0.3, 1.0 - abs(humidity - 60.0) / 100.0)

        return SoilMoisturePrediction(
            estimated_vwc_pct=round(estimated_vwc, 1),
            confidence=round(confidence, 2),
            days_to_irrigation=days_to_irr,
            irrigation_volume_mm=round(irr_volume, 1),
        )

    def irrigation_schedule(self, telemetry: dict, crop: str) -> IrrigationSchedule:
        """
        Produce an irrigation scheduling recommendation.

        Urgency is derived from estimated soil moisture relative to crop needs
        and current atmospheric conditions.

        Returns
        -------
        IrrigationSchedule
        """
        profile = self._get_profile(crop)
        soil = self.predict_soil_moisture(telemetry)
        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        rainfall_mm = float(telemetry.get("rainfall_mm", 0.0))

        # Recent rain reduces need
        effective_rainfall = rainfall_mm * 0.8

        vwc = soil.estimated_vwc_pct
        daily_need = profile.water_requirement_mm_day

        if rainfall_mm > daily_need * 1.5:
            return IrrigationSchedule(
                crop=crop,
                recommended=False,
                urgency="none",
                volume_mm=0.0,
                reason="Sufficient rainfall detected — irrigation not required.",
                next_check_hours=24,
            )

        if vwc < 12.0:
            urgency, recommended = "critical", True
            reason = f"Soil moisture critically low ({vwc:.1f}% VWC). Immediate irrigation required."
            volume = daily_need * 3.0
            next_check = 6
        elif vwc < 18.0:
            urgency, recommended = "high", True
            reason = f"Soil moisture low ({vwc:.1f}% VWC). Irrigation strongly recommended."
            volume = daily_need * 2.0
            next_check = 12
        elif vwc < 22.0:
            urgency, recommended = "medium", True
            reason = f"Soil moisture below optimal ({vwc:.1f}% VWC). Schedule irrigation soon."
            volume = daily_need * 1.5
            next_check = 18
        elif temp > profile.temp_stress_max and humidity < 40.0:
            urgency, recommended = "low", True
            reason = "Heat stress and low humidity — supplemental irrigation advised."
            volume = daily_need
            next_check = 24
        else:
            urgency, recommended = "none", False
            reason = f"Soil moisture adequate ({vwc:.1f}% VWC). No irrigation needed."
            volume = 0.0
            next_check = 24

        return IrrigationSchedule(
            crop=crop,
            recommended=recommended,
            urgency=urgency,
            volume_mm=round(volume - effective_rainfall, 1),
            reason=reason,
            next_check_hours=next_check,
        )

    def detect_pest_risk(self, telemetry: dict, crop: str) -> list[dict]:
        """
        Identify pest risk conditions from telemetry.

        Rules:
        - High temp + high humidity → aphid / fungal-feeding insect risk
        - Low humidity + high temp → spider mite risk
        - Warm night temperatures (proxy: high temp persisting) → moth/larva risk

        Returns
        -------
        list of dicts, each with keys: pest, risk_level, condition, recommendation
        """
        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        risks: list[dict] = []

        # Spider mites: hot and dry
        if temp > self._HIGH_TEMP_THRESHOLD and humidity < self._LOW_HUMIDITY_THRESHOLD:
            risks.append({
                "pest": "Spider Mites",
                "risk_level": "high",
                "condition": f"Temp {temp:.1f}°C and humidity {humidity:.1f}% RH (hot & dry)",
                "recommendation": "Increase irrigation frequency; consider miticide application.",
            })

        # Aphids / soft-bodied insects: warm and humid
        if temp > 20.0 and humidity > self._HIGH_HUMIDITY_THRESHOLD:
            risks.append({
                "pest": "Aphids / Whiteflies",
                "risk_level": "medium" if humidity < 90.0 else "high",
                "condition": f"Temp {temp:.1f}°C and humidity {humidity:.1f}% RH (warm & humid)",
                "recommendation": "Scout crops for aphid colonies; apply neem oil or insecticidal soap.",
            })

        # Locust / grasshopper: very hot and dry
        if temp > 38.0 and humidity < 30.0:
            risks.append({
                "pest": "Locusts / Grasshoppers",
                "risk_level": "high",
                "condition": f"Extreme heat ({temp:.1f}°C) and very low humidity ({humidity:.1f}%)",
                "recommendation": "Monitor surrounding vegetation; coordinate with regional pest control.",
            })

        # Moth larvae: sustained high temperatures
        if temp > 28.0 and humidity > 50.0:
            risks.append({
                "pest": "Moth Larvae / Stem Borers",
                "risk_level": "low" if temp < 32.0 else "medium",
                "condition": f"Warm ({temp:.1f}°C) with moderate-high humidity ({humidity:.1f}%)",
                "recommendation": "Install pheromone traps; inspect plant stems for entry holes.",
            })

        if not risks:
            risks.append({
                "pest": "None identified",
                "risk_level": "low",
                "condition": "Current conditions are within normal pest-risk parameters.",
                "recommendation": "Continue routine scouting.",
            })

        return risks

    def detect_disease_risk(self, telemetry: dict, crop: str) -> list[dict]:
        """
        Identify crop disease risk conditions from telemetry.

        Rules:
        - Prolonged high humidity → mold, blight, powdery mildew
        - High humidity + moderate temp → downy mildew
        - Low humidity + heat → leaf scorch

        Returns
        -------
        list of dicts with keys: disease, risk_level, condition, recommendation
        """
        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        risks: list[dict] = []

        # Late blight (e.g., Phytophthora): cool-to-moderate + very humid
        if 10.0 <= temp <= 25.0 and humidity > 85.0:
            risks.append({
                "disease": "Late Blight (Phytophthora)",
                "risk_level": "high",
                "condition": f"Cool-moderate temp ({temp:.1f}°C) with very high humidity ({humidity:.1f}%)",
                "recommendation": "Apply preventative fungicide; improve canopy air circulation.",
            })

        # Powdery mildew: warm and moderately humid
        if 20.0 <= temp <= 30.0 and 60.0 <= humidity <= 80.0:
            risks.append({
                "disease": "Powdery Mildew",
                "risk_level": "medium",
                "condition": f"Warm ({temp:.1f}°C) with moderate humidity ({humidity:.1f}%)",
                "recommendation": "Monitor leaf surfaces; apply sulphur-based fungicide if detected.",
            })

        # Gray mold (Botrytis): cool and very humid
        if temp < 20.0 and humidity > 90.0:
            risks.append({
                "disease": "Gray Mold (Botrytis)",
                "risk_level": "high",
                "condition": f"Cool ({temp:.1f}°C) with very high humidity ({humidity:.1f}%)",
                "recommendation": "Remove infected plant material; improve drainage and ventilation.",
            })

        # Leaf scorch: very hot and dry
        if temp > 35.0 and humidity < 30.0:
            risks.append({
                "disease": "Leaf Scorch / Heat Stress Necrosis",
                "risk_level": "medium",
                "condition": f"Very high temp ({temp:.1f}°C) and low humidity ({humidity:.1f}%)",
                "recommendation": "Provide shade nets; increase irrigation to cool leaf surface temperature.",
            })

        if not risks:
            risks.append({
                "disease": "None identified",
                "risk_level": "low",
                "condition": "Current conditions are within normal disease-risk parameters.",
                "recommendation": "Continue routine plant health monitoring.",
            })

        return risks

    def weather_stress_analysis(self, telemetry: dict, crop: str) -> dict:
        """
        Analyse atmospheric conditions for crop stress indicators.

        Returns
        -------
        dict with keys: heat_stress, cold_stress, frost_risk, humidity_stress,
                        pressure_alert, overall_stress
        """
        profile = self._get_profile(crop)
        temp = float(telemetry.get("temperature", 20.0))
        humidity = float(telemetry.get("humidity", 60.0))
        pressure = float(telemetry.get("pressure", 1013.0))

        heat_stress = temp > profile.temp_stress_max
        cold_stress = temp < profile.temp_stress_min
        frost_risk = temp <= profile.temp_frost_kill
        humidity_stress = (
            humidity < profile.humidity_optimal_min or humidity > profile.humidity_optimal_max
        )
        pressure_alert = pressure < profile.pressure_storm_threshold

        # Overall stress: any critical flag raises the level
        stress_count = sum([heat_stress, cold_stress, frost_risk, humidity_stress, pressure_alert])
        if frost_risk or (heat_stress and humidity_stress):
            overall = "critical"
        elif stress_count >= 2:
            overall = "high"
        elif stress_count == 1:
            overall = "medium"
        else:
            overall = "low"

        return {
            "heat_stress": heat_stress,
            "cold_stress": cold_stress,
            "frost_risk": frost_risk,
            "humidity_stress": humidity_stress,
            "pressure_alert": pressure_alert,
            "overall_stress": overall,
            "detail": {
                "temperature": temp,
                "humidity": humidity,
                "pressure": pressure,
                "temp_optimal_range": (profile.temp_optimal_min, profile.temp_optimal_max),
                "humidity_optimal_range": (profile.humidity_optimal_min, profile.humidity_optimal_max),
            },
        }

    def compute_risk_level(self, telemetry: dict, crop: str) -> str:
        """
        Compute overall agricultural risk level from telemetry.

        Returns
        -------
        "low", "medium", "high", or "critical"
        """
        stress = self.weather_stress_analysis(telemetry, crop)
        pest_risks = self.detect_pest_risk(telemetry, crop)
        disease_risks = self.detect_disease_risk(telemetry, crop)
        soil = self.predict_soil_moisture(telemetry)

        # Start from weather stress
        stress_level = stress["overall_stress"]
        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        current = risk_order.get(stress_level, 0)

        # Escalate based on pest/disease
        for risk in pest_risks + disease_risks:
            rl = risk.get("risk_level", "low")
            current = max(current, risk_order.get(rl, 0))

        # Critically low soil moisture escalates to at least high
        if soil.estimated_vwc_pct < 12.0:
            current = max(current, risk_order["high"])

        levels = {v: k for k, v in risk_order.items()}
        return levels[current]

    # ---------------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------------

    def _get_profile(self, crop: str) -> CropProfile:
        """Return the crop profile, falling back to maize if unknown."""
        return CROP_PROFILES.get(crop.lower(), CROP_PROFILES["maize"])

    def _build_recommendations(
        self,
        telemetry: dict,
        profile: CropProfile,
        soil: SoilMoisturePrediction,
        irrigation: IrrigationSchedule,
        pest_risks: list[dict],
        disease_risks: list[dict],
        stress: dict,
    ) -> list[str]:
        """Compile a human-readable list of prioritised recommendations."""
        recs: list[str] = []

        if stress["frost_risk"]:
            recs.append("⚠️ FROST RISK: Protect crops with frost cloth or smudge pots immediately.")
        if stress["heat_stress"]:
            recs.append("🌡️ Heat stress detected: increase irrigation and consider shade netting.")
        if stress["cold_stress"]:
            recs.append("❄️ Cold stress detected: monitor for growth slowdown and disease susceptibility.")
        if stress["pressure_alert"]:
            recs.append("🌩️ Low pressure alert: storm likely — secure equipment and assess drainage.")

        if irrigation.recommended:
            recs.append(f"💧 Irrigation: {irrigation.reason} (Volume: {irrigation.volume_mm:.1f} mm)")

        for p in pest_risks:
            if p["risk_level"] in ("medium", "high"):
                recs.append(f"🐛 Pest — {p['pest']}: {p['recommendation']}")

        for d in disease_risks:
            if d["risk_level"] in ("medium", "high"):
                recs.append(f"🍂 Disease — {d['disease']}: {d['recommendation']}")

        if not recs:
            recs.append("✅ Conditions are favourable. Continue routine monitoring.")

        return recs
