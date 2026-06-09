"""
Gravity Analog Waterproof Capacitive Soil Moisture Sensor driver.

This sensor outputs an analog voltage inversely proportional to soil moisture:
higher voltage = drier soil.  It requires an ADC (such as the BC Robotics
16CH Analog Input HAT) to read the analog signal.

When the ADC provider is unavailable the driver returns an empty dict — no
synthetic data is emitted.

Calibration
-----------
The factory-default calibration maps voltage to moisture percentage:

    moisture_pct = ((dry_voltage - measured_voltage)
                    / (dry_voltage - wet_voltage)) * 100

Clamped to [0, 100].  Typical voltage ranges (at 3.3 V VREF):

    - Dry soil (in air)        ~2.5 V
    - Wet soil (fully soaked)  ~1.0 V

Adjust ``SOIL_MOISTURE_DRY_V`` and ``SOIL_MOISTURE_WET_V`` to match your
specific sensor and soil type.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from Zweather.node1_telemetry.sensors.base import BaseSensor
from Zweather.node1_telemetry import config

logger = logging.getLogger(__name__)

# Default calibration for Gravity Analog Capacitive Soil Moisture Sensor
# at 3.3 V VREF.
_DEFAULT_DRY_V = 2.5
_DEFAULT_WET_V = 1.0

# Factory recommended voltage range
_SENSOR_VMIN = 0.0
_SENSOR_VMAX = 3.0


class SoilMoistureSensor(BaseSensor):
    """Gravity Analog Capacitive Soil Moisture Sensor.

    Parameters
    ----------
    adc_provider:
        Optional object with a ``read_channel(channel)`` method returning
        ``(raw, voltage)``.  When omitted the sensor creates its own
        ``BCRobotics16CHADC`` instance.
    channel:
        ADC channel the sensor is wired to.
    dry_voltage:
        Voltage reading when soil is completely dry.
    wet_voltage:
        Voltage reading when soil is fully saturated.
    """

    def __init__(
        self,
        adc_provider: Optional[Any] = None,
        channel: int = -1,
        dry_voltage: float = -1.0,
        wet_voltage: float = -1.0,
    ) -> None:
        super().__init__("soil_moisture")
        self._adc_provider = adc_provider
        self._channel = channel if channel >= 0 else config.SOIL_MOISTURE_ADC_CHANNEL
        self._dry_v = dry_voltage if dry_voltage >= 0 else config.SOIL_MOISTURE_DRY_V
        self._wet_v = wet_voltage if wet_voltage >= 0 else config.SOIL_MOISTURE_WET_V
        self._own_adc: Any = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        if not config.SOIL_MOISTURE_ENABLED and self._adc_provider is None:
            logger.info("Soil moisture sensor disabled in configuration.")
            return

        if self._adc_provider is not None:
            self._available = True
            logger.info(
                "Soil moisture sensor using external ADC provider on channel %d.",
                self._channel,
            )
            return

        try:
            from Zweather.node1_telemetry.sensors.bc_robotics_adc import (
                BCRobotics16CHADC,
            )
            self._own_adc = BCRobotics16CHADC()
            self._own_adc.initialize()
            if self._own_adc.available:
                self._adc_provider = self._own_adc
                self._available = True
                logger.info(
                    "Soil moisture sensor initialised (own ADC, channel %d).",
                    self._channel,
                )
            else:
                logger.warning("No ADC available for soil moisture sensor.")
                self._available = False
        except ImportError:
            logger.warning(
                "BCRobotics16CHADC not importable — soil moisture sensor "
                "unavailable."
            )
            self._available = False

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read(self) -> dict[str, Any]:
        if not self._available or self._adc_provider is None:
            return {}

        _, voltage = self._adc_provider.read_channel(self._channel)
        if voltage is None:
            logger.warning("Soil moisture read failed — no voltage from ADC.")
            return {}

        moisture = self._voltage_to_moisture(voltage)

        return {
            "soil_moisture_pct": round(moisture, 1),
            "soil_moisture_v": round(voltage, 4),
        }

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def _voltage_to_moisture(self, voltage: float) -> float:
        """Convert ADC voltage to moisture percentage [0–100]."""
        if voltage < _SENSOR_VMIN or voltage > _SENSOR_VMAX:
            logger.debug(
                "Soil moisture voltage %.4f V outside expected range "
                "[%.1f, %.1f] V — clamping.",
                voltage, _SENSOR_VMIN, _SENSOR_VMAX,
            )

        if self._dry_v <= self._wet_v:
            logger.warning(
                "Soil moisture calibration invalid: dry_v=%.4f <= wet_v=%.4f. "
                "Falling back to defaults.",
                self._dry_v, self._wet_v,
            )
            dry_v, wet_v = _DEFAULT_DRY_V, _DEFAULT_WET_V
        else:
            dry_v, wet_v = self._dry_v, self._wet_v

        ratio = (dry_v - voltage) / (dry_v - wet_v)
        pct = ratio * 100.0
        return max(0.0, min(100.0, pct))

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        if self._own_adc is not None:
            self._own_adc.cleanup()
            self._own_adc = None
        self._adc_provider = None
        self._available = False
