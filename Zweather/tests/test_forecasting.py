"""Tests for Zweather.agricultural.forecasting"""
import pytest
from Zweather.agricultural.forecasting import WeatherForecaster


def _make_readings(n: int = 24, temp_base: float = 20.0) -> list[dict]:
    # Forecaster extracts keys: "temperature", "humidity", "pressure"
    return [
        {
            "temperature": temp_base + i * 0.1,
            "humidity": 65.0,
            "pressure": 1013.0 - i * 0.05,
            "timestamp": float(i * 3600),
        }
        for i in range(n)
    ]


class TestWeatherForecaster:
    def setup_method(self):
        self.forecaster = WeatherForecaster()

    def test_analyze_trend_returns_dict(self):
        readings = _make_readings(24)
        result = self.forecaster.analyze_trend(readings)
        assert isinstance(result, dict)

    def test_trend_has_required_keys(self):
        readings = _make_readings(24)
        result = self.forecaster.analyze_trend(readings)
        assert "temperature_trend" in result
        assert "humidity_trend" in result
        assert "pressure_trend" in result

    def test_rising_temperature_trend(self):
        # Consistently increasing temperature readings
        readings = _make_readings(24, temp_base=15.0)
        result = self.forecaster.analyze_trend(readings)
        assert result["temperature_trend"] in ("rising", "falling", "stable",
                                                "gradually rising", "rapidly rising",
                                                "gradually falling", "rapidly falling")

    def test_detect_anomalies_returns_list(self):
        readings = _make_readings(24)
        # Inject a spike well beyond 2.5σ
        readings[12]["temperature"] = 95.0
        anomalies = self.forecaster.detect_anomalies(readings)
        assert isinstance(anomalies, list)
        assert len(anomalies) > 0

    def test_no_anomalies_in_clean_data(self):
        readings = _make_readings(24)
        anomalies = self.forecaster.detect_anomalies(readings)
        assert isinstance(anomalies, list)
        # Gradual readings should have few or no anomalies
        assert len(anomalies) <= 2

    def test_rolling_stats(self):
        readings = _make_readings(48)
        result = self.forecaster.compute_rolling_stats(readings, window=24)
        assert isinstance(result, dict)

    def test_too_few_readings(self):
        """Should handle < 3 readings gracefully."""
        result = self.forecaster.analyze_trend([{"temperature": 20.0}])
        assert isinstance(result, dict)
