"""
Tests for the BC Robotics 16-Channel Analog Input HAT driver.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from Zweather.node1_telemetry import config as n1_config
from Zweather.node1_telemetry.sensors.bc_robotics_adc import (
    BCRobotics16CHADC,
    _decode_mcp3008,
    _decode_mcp3208,
)


# =========================================================================
# Decoder unit tests
# =========================================================================

class TestDecodeMCP3008:
    def test_zero(self):
        assert _decode_mcp3008((0x00, 0x00, 0x00)) == 0

    def test_max(self):
        assert _decode_mcp3008((0x00, 0x03, 0xFF)) == 1023

    def test_mid_value(self):
        assert _decode_mcp3008((0x00, 0x01, 0x80)) == 384

    def test_null_bytes_ignored(self):
        assert _decode_mcp3008((0xFF, 0x02, 0x00)) == 512


class TestDecodeMCP3208:
    def test_zero(self):
        assert _decode_mcp3208((0x00, 0x00, 0x00)) == 0

    def test_max(self):
        assert _decode_mcp3208((0x00, 0x0F, 0xFF)) == 4095

    def test_mid_value(self):
        assert _decode_mcp3208((0x00, 0x08, 0x00)) == 2048


# =========================================================================
# Driver tests
# =========================================================================

class TestBCRoboticsADC:
    def test_disabled_returns_empty(self):
        driver = BCRobotics16CHADC()
        driver.initialize()
        assert driver.available is False
        assert driver.read() == {}

    @patch.object(n1_config, "BC_ROBOTICS_ADC_ENABLED", True)
    @patch("spidev.SpiDev")
    def test_initialize_opens_two_spi_devices(self, mock_spi):
        dev = MagicMock()
        mock_spi.return_value = dev
        driver = BCRobotics16CHADC()
        driver.initialize()
        assert driver.available is True
        assert mock_spi.call_count == 2

    @patch.object(n1_config, "BC_ROBOTICS_ADC_ENABLED", True)
    @patch("spidev.SpiDev")
    def test_read_returns_16_channels(self, mock_spi):
        dev = MagicMock()
        dev.xfer2.return_value = (0x00, 0x01, 0x80)  # 384 raw
        mock_spi.return_value = dev
        driver = BCRobotics16CHADC(vref=3.3)
        driver.initialize()
        data = driver.read()
        for ch in range(16):
            assert f"adc_ch{ch}_raw" in data
            assert f"adc_ch{ch}_v" in data
        # 384 / 1023 * 3.3 ≈ 1.2395 V
        assert data["adc_ch0_v"] == pytest.approx(1.2395, rel=1e-3)

    @patch.object(n1_config, "BC_ROBOTICS_ADC_ENABLED", True)
    @patch("spidev.SpiDev")
    def test_read_channel_returns_tuple(self, mock_spi):
        dev = MagicMock()
        dev.xfer2.return_value = (0x00, 0x01, 0x80)
        mock_spi.return_value = dev
        driver = BCRobotics16CHADC(vref=3.3)
        driver.initialize()
        raw, voltage = driver.read_channel(0)
        assert raw == 384
        assert voltage == pytest.approx(1.2395, rel=1e-3)

    @patch.object(n1_config, "BC_ROBOTICS_ADC_ENABLED", True)
    @patch("spidev.SpiDev")
    def test_read_channel_out_of_range(self, mock_spi):
        dev = MagicMock()
        mock_spi.return_value = dev
        driver = BCRobotics16CHADC()
        driver.initialize()
        raw, voltage = driver.read_channel(99)
        assert raw is None
        assert voltage is None

    @patch.object(n1_config, "BC_ROBOTICS_ADC_ENABLED", True)
    @patch("spidev.SpiDev")
    def test_mcp3208_resolution(self, mock_spi):
        dev = MagicMock()
        dev.xfer2.return_value = (0x00, 0x08, 0x00)  # 2048 raw (12-bit half)
        mock_spi.return_value = dev
        driver = BCRobotics16CHADC(chip_type="MCP3208", vref=3.3)
        driver.initialize()
        raw, voltage = driver.read_channel(0)
        assert raw == 2048
        # 2048 / 4095 * 3.3 ≈ 1.6508 V
        assert voltage == pytest.approx(1.6508, rel=1e-3)

    def test_init_with_explicit_params(self):
        driver = BCRobotics16CHADC(chip_type="MCP3008", spi_bus=0, vref=4.096)
        assert driver._chip_type == "MCP3008"
        assert driver._spi_bus == 0
        assert driver._vref == 4.096

    @patch.object(n1_config, "BC_ROBOTICS_ADC_ENABLED", True)
    @patch("spidev.SpiDev")
    def test_spi_error_returns_none(self, mock_spi):
        dev = MagicMock()
        dev.xfer2.side_effect = OSError("SPI bus error")
        mock_spi.return_value = dev
        driver = BCRobotics16CHADC()
        driver.initialize()
        raw, voltage = driver.read_channel(0)
        assert raw is None
        assert voltage is None

    @patch.object(n1_config, "BC_ROBOTICS_ADC_ENABLED", True)
    @patch("spidev.SpiDev")
    def test_cleanup_closes_devices(self, mock_spi):
        dev = MagicMock()
        mock_spi.return_value = dev
        driver = BCRobotics16CHADC()
        driver.initialize()
        driver.cleanup()
        assert dev.close.call_count == 2
        assert driver.available is False
