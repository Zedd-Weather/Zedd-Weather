"""
GPIO-based sensors — tipping-bucket rain gauge.

The rain gauge closes a reed-switch contact once per *tip*, producing a
falling-edge interrupt on the configured GPIO pin.  Each tip corresponds to
``config.RAIN_GAUGE_MM_PER_TIP`` mm of rainfall (typically 0.2794 mm for
standard tipping-bucket gauges).

The driver accumulates tips and exposes both the running total and a
per-interval rainfall rate that resets on every ``read()`` call.
"""
import time
import threading
import random
import logging

from Zweather.node1_telemetry.sensors.base import BaseSensor
from Zweather.node1_telemetry import config

logger = logging.getLogger(__name__)


class RainGaugeSensor(BaseSensor):
    """Tipping-bucket rain gauge connected via GPIO."""

    def __init__(self):
        super().__init__("rain_gauge")
        self._tip_count = 0
        self._total_tips = 0
        self._lock = threading.Lock()
        self._last_read_time = time.monotonic()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        if not config.RAIN_GAUGE_ENABLED:
            logger.info("Rain gauge disabled in configuration.")
            return

        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(config.RAIN_GAUGE_GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                config.RAIN_GAUGE_GPIO_PIN,
                GPIO.FALLING,
                callback=self._on_tip,
                bouncetime=300,
            )
            self._available = True
            logger.info(
                "Rain gauge initialised on GPIO %d.", config.RAIN_GAUGE_GPIO_PIN
            )
        except (ImportError, RuntimeError) as exc:
            logger.warning("Rain gauge GPIO unavailable (%s). Using mock data.", exc)
            self._available = False

    def _on_tip(self, _channel: int) -> None:
        """Interrupt callback – one bucket tip."""
        with self._lock:
            self._tip_count += 1
            self._total_tips += 1

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def read(self) -> dict:
        if self._available:
            return self._read_hardware()
        if config.RAIN_GAUGE_ENABLED:
            return self._read_mock()
        return {}

    def _read_hardware(self) -> dict:
        now = time.monotonic()
        with self._lock:
            tips = self._tip_count
            self._tip_count = 0
            elapsed = max(now - self._last_read_time, 0.001)
            self._last_read_time = now

        interval_mm = round(tips * config.RAIN_GAUGE_MM_PER_TIP, 4)
        rate_mm_h = round((interval_mm / elapsed) * 3600, 2)

        return {
            "rain_interval_mm": interval_mm,
            "rain_rate_mm_h": rate_mm_h,
            "rain_total_mm": round(
                self._total_tips * config.RAIN_GAUGE_MM_PER_TIP, 4
            ),
        }

    @staticmethod
    def _read_mock() -> dict:
        return {
            "rain_interval_mm": round(random.uniform(0, 0.6), 4),
            "rain_rate_mm_h": round(random.uniform(0, 5.0), 2),
            "rain_total_mm": round(random.uniform(0, 25.0), 4),
        }

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def cleanup(self) -> None:
        if self._available:
            try:
                import RPi.GPIO as GPIO
                GPIO.remove_event_detect(config.RAIN_GAUGE_GPIO_PIN)
            except (ImportError, RuntimeError):
                pass
