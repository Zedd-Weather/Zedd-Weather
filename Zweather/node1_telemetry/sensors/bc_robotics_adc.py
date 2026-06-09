"""
BCRobotics 16-Channel Analog Input HAT driver.

The BC Robotics 16CH ADC HAT provides 16 analog input channels using two
MCP3008 (10-bit) or MCP3208 (12-bit) SPI ADC chips:

    - Chip 1 (CE0, ``/dev/spidev<bus>.0``)  → channels  0 –  7
    - Chip 2 (CE1, ``/dev/spidev<bus>.1``)  → channels  8 – 15

Each channel reads 0 V to ``VREF`` (default 3.3 V) and returns both the
raw ADC count and the computed voltage.

When the SPI bus or pycoral is not available the driver reports
``available=False`` and returns empty dicts — no synthetic data.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from Zweather.node1_telemetry.sensors.base import BaseSensor
from Zweather.node1_telemetry import config

logger = logging.getLogger(__name__)

# ── Chip-specific protocol helpers ──────────────────────────────────────────

_MCP3008_MAX_VALUE = 1023  # 10-bit
_MCP3208_MAX_VALUE = 4095  # 12-bit

_CHIP_PROTOCOLS: dict[str, dict[str, Any]] = {
    "MCP3008": {
        "resolution_bits": 10,
        "max_value": _MCP3008_MAX_VALUE,
    },
    "MCP3208": {
        "resolution_bits": 12,
        "max_value": _MCP3208_MAX_VALUE,
    },
}


def _decode_mcp3008(rx: tuple[int, int, int]) -> int:
    """Decode 3-byte SPI response for MCP3008 → 10-bit value."""
    return ((rx[1] & 0x03) << 8) | rx[2]


def _decode_mcp3208(rx: tuple[int, int, int]) -> int:
    """Decode 3-byte SPI response for MCP3208 → 12-bit value."""
    return ((rx[1] & 0x0F) << 8) | rx[2]


_DECODE_FN: dict[str, Any] = {
    "MCP3008": _decode_mcp3008,
    "MCP3208": _decode_mcp3208,
}


class BCRobotics16CHADC(BaseSensor):
    """Driver for the BC Robotics 16-Channel Analog Input HAT.

    Parameters
    ----------
    chip_type:
        ``"MCP3008"`` (10-bit) or ``"MCP3208"`` (12-bit).
    spi_bus:
        SPI bus number (default 0 → ``/dev/spidev0.X``).
    vref:
        ADC reference voltage in Volts.
    """

    def __init__(
        self,
        chip_type: str = "",
        spi_bus: int = -1,
        vref: float = -1.0,
    ) -> None:
        super().__init__("bc_robotics_adc")
        self._chip_type = chip_type or config.BC_ROBOTICS_ADC_CHIP_TYPE
        self._spi_bus = spi_bus if spi_bus >= 0 else config.BC_ROBOTICS_ADC_SPI_BUS
        self._vref = vref if vref >= 0 else config.BC_ROBOTICS_ADC_VREF
        self._decode = _DECODE_FN.get(self._chip_type, _decode_mcp3008)
        self._max_value = _CHIP_PROTOCOLS.get(self._chip_type, _CHIP_PROTOCOLS["MCP3008"])["max_value"]
        self._devices: list[Any] = []
        self._num_channels = 16

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        if not config.BC_ROBOTICS_ADC_ENABLED:
            logger.info("BC Robotics 16CH ADC disabled in configuration.")
            return

        try:
            import spidev  # type: ignore[import-untyped]

            for cs in (0, 1):
                dev = spidev.SpiDev()
                dev.open(self._spi_bus, cs)
                dev.max_speed_hz = 1_000_000
                dev.mode = 0b00  # SPI mode 0,0
                self._devices.append(dev)
                logger.debug(
                    "BC Robotics ADC: opened spidev%d.%d at %d Hz",
                    self._spi_bus, cs, dev.max_speed_hz,
                )

            self._available = True
            logger.info(
                "BC Robotics 16CH ADC initialised (%s, %d-bit, VREF=%.2f V, "
                "SPI bus %d).",
                self._chip_type,
                _CHIP_PROTOCOLS.get(self._chip_type, _CHIP_PROTOCOLS["MCP3008"])["resolution_bits"],
                self._vref,
                self._spi_bus,
            )

        except (ImportError, OSError, RuntimeError) as exc:
            logger.warning(
                "BC Robotics 16CH ADC unavailable (%s). "
                "No analog sensor readings will be emitted.",
                exc,
            )
            self._available = False

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read(self) -> dict[str, Any]:
        if not self._available:
            return {}

        data: dict[str, Any] = {}
        for ch in range(self._num_channels):
            raw = self._read_channel_raw(ch)
            voltage = round(raw / self._max_value * self._vref, 4) if raw is not None else None
            data[f"adc_ch{ch}_raw"] = raw
            data[f"adc_ch{ch}_v"] = voltage
        return data

    def read_channel(self, channel: int) -> tuple[int | None, float | None]:
        """Read a single ADC channel.

        Returns
        -------
        ``(raw_adc_count, voltage_v)`` — both ``None`` on error.
        """
        if not self._available:
            return None, None
        raw = self._read_channel_raw(channel)
        if raw is None:
            return None, None
        voltage = round(raw / self._max_value * self._vref, 4)
        return raw, voltage

    # ------------------------------------------------------------------
    # Low-level SPI
    # ------------------------------------------------------------------

    def _read_channel_raw(self, channel: int) -> int | None:
        """Read the raw ADC count for a single channel via SPI."""
        if not 0 <= channel < 16:
            logger.error("ADC channel %d out of range [0, 15]", channel)
            return None
        if not self._devices:
            return None

        chip_index = 0 if channel < 8 else 1
        local_ch = channel % 8
        dev = self._devices[chip_index]

        try:
            start_bit = 0x01
            mode_single = 0x80
            tx = [start_bit, mode_single | (local_ch << 4), 0x00]
            rx = dev.xfer2(tx)
            if len(rx) != 3:
                logger.error("SPI xfer2 returned %d bytes (expected 3)", len(rx))
                return None
            raw = self._decode(tuple(rx))
            return raw
        except (OSError, RuntimeError) as exc:
            logger.error("SPI read error on channel %d: %s", channel, exc)
            return None

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        for dev in self._devices:
            try:
                dev.close()
            except OSError:
                logger.debug("ADC SPI device close failed", exc_info=True)
        self._devices.clear()
        self._available = False
