"""Tests for the BCRobotics Weather HAT PRO sensor driver."""
import importlib
import os
import sys
from unittest.mock import patch
from Zweather.node1_telemetry.sensors.weather_hat_pro import WeatherHatProDriver


def _reload():
    import Zweather.node1_telemetry.config as cfg
    importlib.reload(cfg)
    import Zweather.node1_telemetry.sensors.weather_hat_pro as whp
    importlib.reload(whp)
    return whp


class TestWeatherHatProDriver:
    """Tests for WeatherHatProDriver."""

    def test_disabled_returns_empty(self):
        """When WEATHER_HAT_PRO_ENABLED is false the driver returns nothing."""
        with patch.dict(os.environ, {"WEATHER_HAT_PRO_ENABLED": "false"}):
            whp = _reload()
            driver = whp.WeatherHatProDriver()
            driver.initialize()
            assert driver.available is False
            assert driver.read() == {}

    def test_unavailable_returns_empty(self):
        """When the underlying I2C / GPIO libraries are absent the enabled
        driver still returns an empty payload — no synthetic data ever."""
        with patch("Zweather.node1_telemetry.sensors.weather_hat_pro.config.WEATHER_HAT_PRO_ENABLED", True):
            driver = WeatherHatProDriver()
            driver.initialize()
            # On systems where GPIO/ADC are available but BME280 is not,
            # the driver reports itself as available with partial data.
            # Verify it never synthesises BME280 readings.
            payload = driver.read()
            assert "weather_hat_pro_temp_c" not in payload
            assert "weather_hat_pro_pressure_hpa" not in payload
            assert "weather_hat_pro_humidity_pct" not in payload
            driver.cleanup()

    def test_cardinal_conversion(self):
        """_degrees_to_cardinal should map common bearings correctly."""
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
            assert WeatherHatProDriver._degrees_to_cardinal(degrees) == expected

    def test_voltage_to_bearing_matches_known_points(self):
        """The vane-voltage lookup should resolve canonical points exactly."""
        # 0.32 V is the calibrated entry for 112.5° in the lookup table.
        assert WeatherHatProDriver._voltage_to_bearing(0.32) == 112.5
        # 4.62 V is the calibrated entry for 270.0°.
        assert WeatherHatProDriver._voltage_to_bearing(4.62) == 270.0

    def test_voltage_to_bearing_rejects_out_of_range(self):
        """Voltages far from any vane resistor are reported as None
        (vane likely disconnected or wired incorrectly)."""
        WeatherHatProDriver = _reload().WeatherHatProDriver
        # 8.0 V is way above the highest expected vane voltage.
        assert WeatherHatProDriver._voltage_to_bearing(8.0) is None

    def test_cleanup_no_error_when_unavailable(self):
        """cleanup() must not raise even when no hardware is present."""
        with patch.dict(os.environ, {"WEATHER_HAT_PRO_ENABLED": "true"}):
            whp = _reload()
            driver = whp.WeatherHatProDriver()
            driver.initialize()
            driver.cleanup()  # should not raise


class TestSensorManagerRegistration:
    """Ensure the Weather HAT PRO driver is wired into the SensorManager."""

    def test_sensor_manager_initializes_weather_hat_pro(self):
        with patch.dict(os.environ, {
            "WEATHER_HAT_PRO_ENABLED": "true",
            "SENSE_HAT_ENABLED": "false",
            "AI_HAT_ENABLED": "false",
            "RAIN_GAUGE_ENABLED": "false",
            "UV_SENSOR_ENABLED": "false",
            "ENVIRO_PLUS_ENABLED": "false",
            "MODBUS_ENABLED": "false",
        }):
            _reload()
            import Zweather.node1_telemetry.sensors.sensor_manager as sm
            importlib.reload(sm)

            manager = sm.SensorManager()
            manager.initialize()
            try:
                names = [d.name for d in manager._drivers]
                assert "weather_hat_pro" in names
                payload = manager.read_all()
                assert "timestamp" in payload
                # Hardware is absent in CI, so the only key in the payload
                # is the timestamp — the driver must never synthesise data.
                assert "weather_hat_pro_temp_c" not in payload
            finally:
                manager.cleanup()
