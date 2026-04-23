"""Tests for the Pimoroni Weather HAT sensor driver."""
import importlib
import os
from unittest.mock import patch


def _reload_config():
    import Zweather.node1_telemetry.config as cfg
    importlib.reload(cfg)
    # Reload the driver module so it picks up the refreshed config import.
    import Zweather.node1_telemetry.sensors.weather_hat as wh
    importlib.reload(wh)
    return wh


class TestWeatherHatSensor:
    """Tests for Zweather.node1_telemetry.sensors.weather_hat.WeatherHatSensor."""

    def test_disabled_returns_empty(self):
        """When WEATHER_HAT_ENABLED is false the driver should return no readings."""
        with patch.dict(os.environ, {"WEATHER_HAT_ENABLED": "false"}):
            wh = _reload_config()
            driver = wh.WeatherHatSensor()
            driver.initialize()
            assert driver.available is False
            assert driver.read() == {}

    def test_mock_mode_returns_expected_keys(self):
        """When the weatherhat library is absent, enabled driver returns mock data."""
        with patch.dict(os.environ, {"WEATHER_HAT_ENABLED": "true"}):
            wh = _reload_config()
            driver = wh.WeatherHatSensor()
            driver.initialize()

            # Without the hardware library installed, available should be False
            # but read() should still yield mock data because the sensor is enabled.
            assert driver.available is False
            data = driver.read()
            for key in (
                "weather_hat_temp_c",
                "weather_hat_pressure_hpa",
                "weather_hat_humidity_pct",
                "weather_hat_lux",
                "wind_speed_ms",
                "wind_direction_deg",
                "wind_direction_cardinal",
                "rain_mm",
            ):
                assert key in data

    def test_mock_values_within_expected_ranges(self):
        """Mock readings should fall within physically plausible ranges."""
        with patch.dict(os.environ, {"WEATHER_HAT_ENABLED": "true"}):
            wh = _reload_config()
            driver = wh.WeatherHatSensor()
            driver.initialize()
            data = driver.read()

            assert 15.0 <= data["weather_hat_temp_c"] <= 30.0
            assert 1000.0 <= data["weather_hat_pressure_hpa"] <= 1025.0
            assert 30.0 <= data["weather_hat_humidity_pct"] <= 80.0
            assert 0.0 <= data["weather_hat_lux"] <= 60000.0
            assert 0.0 <= data["wind_speed_ms"] <= 15.0
            assert 0.0 <= data["wind_direction_deg"] <= 360.0
            assert 0.0 <= data["rain_mm"] <= 1.5

    def test_cardinal_conversion(self):
        """_degrees_to_cardinal should map common bearings correctly."""
        from Zweather.node1_telemetry.sensors.weather_hat import WeatherHatSensor
        cases = {
            0: "N",
            45: "NE",
            90: "E",
            135: "SE",
            180: "S",
            225: "SW",
            270: "W",
            315: "NW",
            360: "N",
        }
        for degrees, expected in cases.items():
            assert WeatherHatSensor._degrees_to_cardinal(degrees) == expected

    def test_cardinal_in_mock_payload_is_valid(self):
        """The cardinal field in mock data must be one of 16 compass points."""
        with patch.dict(os.environ, {"WEATHER_HAT_ENABLED": "true"}):
            wh = _reload_config()
            driver = wh.WeatherHatSensor()
            driver.initialize()
            data = driver.read()
            valid = {
                "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
            }
            assert data["wind_direction_cardinal"] in valid

    def test_cleanup_no_error_when_unavailable(self):
        """cleanup() should not raise even when no hardware is present."""
        with patch.dict(os.environ, {"WEATHER_HAT_ENABLED": "true"}):
            wh = _reload_config()
            driver = wh.WeatherHatSensor()
            driver.initialize()
            driver.cleanup()  # should not raise


class TestSensorManagerRegistration:
    """Ensure the Weather HAT driver is wired into the SensorManager."""

    def test_sensor_manager_initialises_weather_hat(self):
        with patch.dict(os.environ, {
            "WEATHER_HAT_ENABLED": "true",
            "SENSE_HAT_ENABLED": "false",
            "AI_HAT_ENABLED": "false",
            "RAIN_GAUGE_ENABLED": "false",
            "UV_SENSOR_ENABLED": "false",
            "ENVIRO_PLUS_ENABLED": "false",
            "MODBUS_ENABLED": "false",
        }):
            _reload_config()
            import Zweather.node1_telemetry.sensors.sensor_manager as sm
            importlib.reload(sm)

            manager = sm.SensorManager()
            manager.initialize()
            try:
                names = [d.name for d in manager._drivers]
                assert "weather_hat" in names
                payload = manager.read_all()
                assert "timestamp" in payload
                # Mock data should be present since hardware is absent.
                assert "weather_hat_temp_c" in payload
            finally:
                manager.cleanup()
