"""
Weather pattern analysis and trend detection for Zedd Weather.
Provides rolling statistics, trend analysis, and anomaly detection
from a time-series of telemetry readings.
"""
import math
import statistics
from typing import Optional


class WeatherForecaster:
    """
    Analyses a sequence of telemetry readings to detect trends and anomalies.

    Each reading in the input list is expected to be a dict with at minimum:
        temperature (°C), humidity (%), pressure (hPa)
    Optional keys: timestamp, wind_speed, uv_index, rainfall_mm.
    """

    # Anomaly detection: flag if reading deviates more than this many std devs
    _ANOMALY_ZSCORE = 2.5

    # Minimum readings required for meaningful trend analysis
    _MIN_READINGS = 3

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def analyze_trend(self, readings: list[dict]) -> dict:
        """
        Compute temperature, humidity, and pressure trends plus storm probability.

        Parameters
        ----------
        readings:
            Ordered list of telemetry dicts (oldest first).

        Returns
        -------
        dict with keys:
            temperature_trend, humidity_trend, pressure_trend,
            storm_probability, summary
        """
        if len(readings) < self._MIN_READINGS:
            return {
                "temperature_trend": "insufficient_data",
                "humidity_trend": "insufficient_data",
                "pressure_trend": "insufficient_data",
                "storm_probability": 0.0,
                "summary": "Not enough readings for trend analysis.",
            }

        temps = self._extract(readings, "temperature")
        humids = self._extract(readings, "humidity")
        pressures = self._extract(readings, "pressure")

        temp_trend = self._linear_trend(temps)
        humidity_trend = self._linear_trend(humids)
        pressure_trend = self._linear_trend(pressures)

        storm_prob = self._storm_probability(pressures, humids, temps)

        def trend_label(slope: float, unit: str) -> str:
            if abs(slope) < 0.01:
                return "stable"
            direction = "rising" if slope > 0 else "falling"
            magnitude = "rapidly" if abs(slope) > 0.5 else "gradually"
            return f"{magnitude} {direction}"

        return {
            "temperature_trend": trend_label(temp_trend, "°C"),
            "temperature_slope_per_reading": round(temp_trend, 4),
            "humidity_trend": trend_label(humidity_trend, "%"),
            "humidity_slope_per_reading": round(humidity_trend, 4),
            "pressure_trend": trend_label(pressure_trend, "hPa"),
            "pressure_slope_per_reading": round(pressure_trend, 4),
            "storm_probability": round(storm_prob, 2),
            "summary": self._trend_summary(temp_trend, humidity_trend, pressure_trend, storm_prob),
        }

    def detect_anomalies(self, readings: list[dict]) -> list[dict]:
        """
        Identify readings that deviate significantly from the overall distribution.

        Uses a Z-score approach: readings with |Z| > _ANOMALY_ZSCORE are flagged.

        Returns
        -------
        list of dicts with keys: index, metric, value, mean, std_dev, zscore, reason
        """
        if len(readings) < self._MIN_READINGS:
            return []

        anomalies: list[dict] = []
        for metric in ("temperature", "humidity", "pressure"):
            values = self._extract(readings, metric)
            if len(values) < 2:
                continue

            mean = statistics.mean(values)
            std = statistics.stdev(values)
            if std == 0:
                continue

            for i, val in enumerate(values):
                z = (val - mean) / std
                if abs(z) > self._ANOMALY_ZSCORE:
                    anomalies.append({
                        "index": i,
                        "metric": metric,
                        "value": round(val, 2),
                        "mean": round(mean, 2),
                        "std_dev": round(std, 2),
                        "zscore": round(z, 2),
                        "reason": (
                            f"{metric.capitalize()} reading of {val:.1f} deviates "
                            f"{abs(z):.1f}σ from mean ({mean:.1f})"
                        ),
                    })

        return anomalies

    def compute_rolling_stats(self, readings: list[dict], window: int = 24) -> dict:
        """
        Compute rolling averages and standard deviations over the last `window` readings.

        Parameters
        ----------
        readings:
            Ordered list of telemetry dicts (oldest first).
        window:
            Number of most-recent readings to include.

        Returns
        -------
        dict with keys: window_size, temperature, humidity, pressure
        Each metric sub-dict has: mean, std_dev, min, max, latest
        """
        slice_ = readings[-window:] if len(readings) > window else readings
        actual_window = len(slice_)

        result: dict = {"window_size": actual_window}
        for metric in ("temperature", "humidity", "pressure"):
            values = self._extract(slice_, metric)
            if not values:
                result[metric] = {}
                continue
            mean = statistics.mean(values)
            std = statistics.stdev(values) if len(values) > 1 else 0.0
            result[metric] = {
                "mean": round(mean, 2),
                "std_dev": round(std, 2),
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "latest": round(values[-1], 2),
            }

        return result

    # ---------------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------------

    @staticmethod
    def _extract(readings: list[dict], key: str, default: float = 20.0) -> list[float]:
        """Extract a numeric metric from a list of reading dicts."""
        return [float(r.get(key, default)) for r in readings]

    @staticmethod
    def _linear_trend(values: list[float]) -> float:
        """
        Return the slope of a least-squares linear regression over the values.
        Positive slope = rising trend.
        """
        n = len(values)
        if n < 2:
            return 0.0
        x_mean = (n - 1) / 2.0
        y_mean = sum(values) / n
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        return numerator / denominator if denominator != 0 else 0.0

    @staticmethod
    def _storm_probability(
        pressures: list[float],
        humids: list[float],
        temps: list[float],
    ) -> float:
        """
        Estimate storm probability (0.0–1.0) from pressure drop, humidity, and temperature.

        Heuristic rules:
        - Rapidly falling pressure is the strongest indicator
        - High humidity amplifies the probability
        - Large temperature variance suggests unstable air masses
        """
        if not pressures:
            return 0.0

        # Pressure drop over the series
        pressure_drop = pressures[0] - pressures[-1]  # positive = falling
        pressure_score = min(1.0, max(0.0, pressure_drop / 20.0))  # 20 hPa drop → 1.0

        # Absolute low pressure
        low_pressure_score = min(1.0, max(0.0, (1013.0 - min(pressures)) / 30.0))

        # High humidity
        avg_humidity = sum(humids) / len(humids)
        humidity_score = min(1.0, max(0.0, (avg_humidity - 60.0) / 40.0))

        # Temperature variance (instability)
        temp_range = max(temps) - min(temps) if temps else 0.0
        instability_score = min(1.0, temp_range / 15.0)

        # Weighted combination
        probability = (
            0.4 * pressure_score
            + 0.3 * low_pressure_score
            + 0.2 * humidity_score
            + 0.1 * instability_score
        )
        return min(1.0, probability)

    @staticmethod
    def _trend_summary(
        temp_slope: float,
        humid_slope: float,
        pressure_slope: float,
        storm_prob: float,
    ) -> str:
        """Generate a plain-language summary of detected trends."""
        parts: list[str] = []

        if abs(temp_slope) > 0.3:
            parts.append(f"Temperature {'rising' if temp_slope > 0 else 'falling'} quickly.")
        if abs(humid_slope) > 0.5:
            parts.append(f"Humidity {'increasing' if humid_slope > 0 else 'decreasing'}.")
        if pressure_slope < -0.3:
            parts.append("Pressure dropping — weather deterioration possible.")
        elif pressure_slope > 0.3:
            parts.append("Pressure rising — conditions improving.")

        if storm_prob > 0.7:
            parts.append("⚠️ High storm probability detected.")
        elif storm_prob > 0.4:
            parts.append("Moderate storm risk — monitor conditions.")

        return " ".join(parts) if parts else "Conditions are stable."
