"""
Tests for the Gravity Analog Capacitive Soil Moisture Sensor driver.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from Zweather.node1_telemetry.sensors.soil_moisture import (
    SoilMoistureSensor,
    _DEFAULT_DRY_V,
    _DEFAULT_WET_V,
)


# =========================================================================
# Calibration tests
# =========================================================================

class TestVoltageToMoisture:
    def setup_method(self):
        self.sensor = SoilMoistureSensor(
            channel=0, dry_voltage=2.5, wet_voltage=1.0,
        )
        # Bypass ADC dependency — test calibration directly
        self.sensor._available = True
        self.sensor._adc_provider = MagicMock()
        self.sensor._adc_provider.read_channel.return_value = (0, 0.0)

    def test_dry_soil(self):
        pct = self.sensor._voltage_to_moisture(2.5)
        assert pct == 0.0

    def test_wet_soil(self):
        pct = self.sensor._voltage_to_moisture(1.0)
        assert pct == 100.0

    def test_half_moisture(self):
        pct = self.sensor._voltage_to_moisture(1.75)
        assert pct == pytest.approx(50.0, rel=1e-3)

    def test_clamp_below_zero(self):
        pct = self.sensor._voltage_to_moisture(3.0)
        assert pct == 0.0

    def test_clamp_above_100(self):
        pct = self.sensor._voltage_to_moisture(0.5)
        assert pct == 100.0

    def test_inverted_calibration_falls_back(self):
        """When dry_v <= wet_v, fall back to default calibration."""
        sensor = SoilMoistureSensor(
            channel=0, dry_voltage=1.0, wet_voltage=2.5,
        )
        pct = sensor._voltage_to_moisture(1.75)
        # With defaults (dry=2.5, wet=1.0), 1.75V = 50%
        assert pct == pytest.approx(50.0, rel=1e-3)

    def test_custom_calibration(self):
        sensor = SoilMoistureSensor(
            channel=0, dry_voltage=3.0, wet_voltage=0.5,
        )
        pct = sensor._voltage_to_moisture(1.75)
        # (3.0 - 1.75) / (3.0 - 0.5) * 100 = 50%
        assert pct == pytest.approx(50.0, rel=1e-3)


# =========================================================================
# Driver tests
# =========================================================================

class TestSoilMoistureSensor:
    @patch.dict(os.environ, {"SOIL_MOISTURE_ENABLED": "false"})
    def test_disabled_returns_empty(self):
        sensor = SoilMoistureSensor()
        sensor.initialize()
        assert sensor.available is False
        assert sensor.read() == {}

    @patch.dict(os.environ, {"SOIL_MOISTURE_ENABLED": "true"})
    def test_read_with_adc_provider(self):
        mock_adc = MagicMock()
        mock_adc.read_channel.return_value = (384, 1.2395)
        sensor = SoilMoistureSensor(adc_provider=mock_adc, channel=0)
        sensor.initialize()
        assert sensor.available is True
        data = sensor.read()
        assert "soil_moisture_pct" in data
        assert "soil_moisture_v" in data
        # 1.2395V with dry=2.5V, wet=1.0V:
        # (2.5 - 1.2395) / (2.5 - 1.0) * 100 ≈ 84.0%
        assert data["soil_moisture_pct"] == pytest.approx(84.0, rel=1e-1)
        assert data["soil_moisture_v"] == 1.2395

    @patch.dict(os.environ, {"SOIL_MOISTURE_ENABLED": "true"})
    def test_read_adc_unavailable_returns_empty(self):
        mock_adc = MagicMock()
        mock_adc.read_channel.return_value = (None, None)
        sensor = SoilMoistureSensor(adc_provider=mock_adc, channel=0)
        sensor.initialize()
        assert sensor.read() == {}

    def test_read_without_adc_provider(self):
        """Without an ADC provider, initialise should try to create its own."""
        sensor = SoilMoistureSensor(channel=0)
        sensor.initialize()
        # Without hardware, eigen ADC creation will fail gracefully
        assert sensor.available is False
        assert sensor.read() == {}

    @patch.dict(os.environ, {"SOIL_MOISTURE_ENABLED": "true"})
    def test_cleanup_with_own_adc(self):
        mock_adc = MagicMock()
        sensor = SoilMoistureSensor(adc_provider=mock_adc, channel=0)
        sensor.initialize()
        sensor.cleanup()
        assert sensor.available is False

    @patch.dict(os.environ, {"SOIL_MOISTURE_ENABLED": "true"})
    def test_dry_soil_read(self):
        mock_adc = MagicMock()
        mock_adc.read_channel.return_value = (775, 2.5)  # dry = 2.5V
        sensor = SoilMoistureSensor(
            adc_provider=mock_adc, channel=0,
            dry_voltage=2.5, wet_voltage=1.0,
        )
        sensor.initialize()
        data = sensor.read()
        assert data["soil_moisture_pct"] == 0.0

    @patch.dict(os.environ, {"SOIL_MOISTURE_ENABLED": "true"})
    def test_wet_soil_read(self):
        mock_adc = MagicMock()
        mock_adc.read_channel.return_value = (310, 1.0)  # wet = 1.0V
        sensor = SoilMoistureSensor(
            adc_provider=mock_adc, channel=0,
            dry_voltage=2.5, wet_voltage=1.0,
        )
        sensor.initialize()
        data = sensor.read()
        assert data["soil_moisture_pct"] == 100.0

    def test_init_with_explicit_params(self):
        sensor = SoilMoistureSensor(
            channel=3, dry_voltage=3.0, wet_voltage=0.5,
        )
        assert sensor._channel == 3
        assert sensor._dry_v == 3.0
        assert sensor._wet_v == 0.5
