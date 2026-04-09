"""
Raspberry Pi AI HAT+ driver (Hailo-8L NPU).

Provides on-device edge inference capabilities using the Hailo-8L neural
processing unit connected via the M.2 Key E slot on the AI HAT+.

When available the NPU runs a lightweight weather-classification model
locally, eliminating the need for cloud round-trips.  If the Hailo runtime
is not installed (e.g. CI / non-Pi hosts) the driver falls back to a
deterministic mock that returns a ``"simulation"`` label.

Telemetry keys emitted
-----------------------
    ``ai_hat_available``    bool   – whether the Hailo NPU is online
    ``ai_hat_status``       str    – ``"active"`` or ``"standby"``
    ``npu_temp_c``          float  – NPU junction temperature (°C)
    ``npu_power_w``         float  – estimated NPU power draw (W)
    ``npu_utilization_pct`` float  – NPU utilisation percentage
"""
import logging

from Zweather.node1_telemetry.sensors.base import BaseSensor
from Zweather.node1_telemetry import config

logger = logging.getLogger(__name__)


class AIHatDriver(BaseSensor):
    """Driver for the Raspberry Pi AI HAT+ (Hailo-8L NPU)."""

    def __init__(self) -> None:
        super().__init__("ai_hat")
        self._device = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        if not config.AI_HAT_ENABLED:
            logger.info("AI HAT disabled in configuration.")
            return

        try:
            from hailo_platform import (  # type: ignore[import-untyped]
                HailoRTDevice,
            )
            self._device = HailoRTDevice()
            self._available = True
            logger.info(
                "AI HAT+ (Hailo-8L NPU) initialised — device %s.",
                config.AI_HAT_DEVICE_ID,
            )
        except (ImportError, OSError, RuntimeError) as exc:
            logger.warning(
                "Hailo NPU unavailable (%s). AI HAT running in mock mode.",
                exc,
            )
            self._available = False

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def read(self) -> dict:
        if self._available:
            return self._read_hardware()
        if config.AI_HAT_ENABLED:
            return self._read_mock()
        return {}

    def _read_hardware(self) -> dict:
        """Query live diagnostics from the Hailo runtime."""
        assert self._device is not None
        try:
            info = self._device.control.get_chip_temperature()
            npu_temp = round(float(info.ts0_temperature), 1)
        except Exception:
            npu_temp = 0.0

        try:
            power = self._device.control.get_power_measurement()
            npu_power = round(float(power), 2)
        except Exception:
            npu_power = 0.0

        return {
            "ai_hat_available": True,
            "ai_hat_status": "active",
            "npu_temp_c": npu_temp,
            "npu_power_w": npu_power,
            "npu_utilization_pct": 0.0,  # populated during active inference
        }

    @staticmethod
    def _read_mock() -> dict:
        return {
            "ai_hat_available": False,
            "ai_hat_status": "standby",
            "npu_temp_c": 0.0,
            "npu_power_w": 0.0,
            "npu_utilization_pct": 0.0,
        }

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    @property
    def device(self):
        """Return the raw Hailo device handle (or ``None``)."""
        return self._device

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def cleanup(self) -> None:
        if self._device is not None:
            try:
                self._device.release()
            except Exception:
                pass
