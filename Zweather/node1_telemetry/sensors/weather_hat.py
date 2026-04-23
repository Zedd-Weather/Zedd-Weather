"""
Pimoroni Weather HAT driver.

The Weather HAT is an all-in-one Raspberry Pi add-on board that exposes the
following weather peripherals:

    - BME280               – temperature, pressure, humidity (high accuracy)
    - LTR559               – ambient light (lux) and proximity
    - Wind direction       – analog vane read via the on-board ADS1015 ADC
    - Wind speed           – reed-switch anemometer (pulse counter)
    - Rain gauge           – tipping-bucket rain gauge (pulse counter)
    - 4 user buttons       – mapped to GPIO 5, 6, 16, 24 (A, B, X, Y)
    - 1.54" 240x240 LCD    – ST7789 SPI display

The official ``weatherhat`` Python package from Pimoroni provides a single
``WeatherHAT`` class that bundles BME280 + LTR559 + ADC + pulse counters and
exposes ``.update(interval)`` / ``.compensated_temperature`` / ``.wind_speed``
/ ``.wind_direction`` / ``.rain`` etc.  This driver wraps that API in our
``BaseSensor`` interface so readings flow into the standard telemetry pipeline.

When the hardware (or library) is not available, the driver degrades to mock
mode — exactly like every other sensor driver in this package.
"""
import random
import logging

from Zweather.node1_telemetry.sensors.base import BaseSensor
from Zweather.node1_telemetry import config

logger = logging.getLogger(__name__)


class WeatherHatSensor(BaseSensor):
    """Composite driver for the Pimoroni Weather HAT."""

    def __init__(self):
        super().__init__("weather_hat")
        self._hat = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        if not config.WEATHER_HAT_ENABLED:
            logger.info("Weather HAT disabled in configuration.")
            return

        try:
            import weatherhat  # type: ignore
            self._hat = weatherhat.WeatherHAT()
            # Apply CPU-temperature compensation factor (board sits close to
            # the Pi CPU; default factor of 0.8 matches Pimoroni's example).
            self._hat.temperature_offset = config.WEATHER_HAT_TEMP_OFFSET
            # Discard first reading (sensors warm-up).
            self._hat.update(interval=1.0)
            self._available = True
            logger.info("Weather HAT initialised.")
        except (ImportError, OSError, RuntimeError) as exc:
            logger.warning(
                "Weather HAT unavailable (%s). Using mock data.", exc
            )
            self._available = False

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def read(self) -> dict:
        if self._available:
            return self._read_hardware()
        if config.WEATHER_HAT_ENABLED:
            return self._read_mock()
        return {}

    def _read_hardware(self) -> dict:
        data: dict = {}
        try:
            # ``update()`` refreshes BME280 + LTR559 readings and integrates
            # accumulated anemometer / rain-gauge pulses over ``interval``
            # seconds.  We use the configured publish interval so the wind
            # speed / rainfall figures match the cadence of the publisher.
            self._hat.update(interval=config.WEATHER_HAT_UPDATE_INTERVAL)

            data["weather_hat_temp_c"] = round(
                float(self._hat.compensated_temperature), 2
            )
            data["weather_hat_pressure_hpa"] = round(
                float(self._hat.pressure), 2
            )
            data["weather_hat_humidity_pct"] = round(
                float(self._hat.relative_humidity), 2
            )
            data["weather_hat_lux"] = round(float(self._hat.lux), 2)
            data["wind_speed_ms"] = round(float(self._hat.wind_speed), 2)
            # ``wind_direction`` is in degrees (0–360).
            data["wind_direction_deg"] = round(
                float(self._hat.wind_direction), 1
            )
            data["wind_direction_cardinal"] = self._degrees_to_cardinal(
                data["wind_direction_deg"]
            )
            # ``rain`` is mm of rainfall accumulated since the last update.
            data["rain_mm"] = round(float(self._hat.rain), 3)
        except (OSError, AttributeError, RuntimeError) as exc:
            logger.error("Weather HAT read error: %s", exc)
        return data

    @staticmethod
    def _read_mock() -> dict:
        direction = round(random.uniform(0, 360), 1)
        return {
            "weather_hat_temp_c": round(random.uniform(15.0, 30.0), 2),
            "weather_hat_pressure_hpa": round(random.uniform(1000.0, 1025.0), 2),
            "weather_hat_humidity_pct": round(random.uniform(30.0, 80.0), 2),
            "weather_hat_lux": round(random.uniform(0, 60000), 2),
            "wind_speed_ms": round(random.uniform(0, 15.0), 2),
            "wind_direction_deg": direction,
            "wind_direction_cardinal":
                WeatherHatSensor._degrees_to_cardinal(direction),
            "rain_mm": round(random.uniform(0, 1.5), 3),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _degrees_to_cardinal(degrees: float) -> str:
        """Convert a 0–360° wind bearing to a 16-point compass direction."""
        points = [
            "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
        ]
        # Each sector is 22.5°; offset by half a sector so 0° lands on N.
        idx = int((degrees % 360) / 22.5 + 0.5) % 16
        return points[idx]

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def cleanup(self) -> None:
        # The weatherhat library does not expose an explicit close hook;
        # underlying I2C / GPIO resources are released on process exit.
        self._hat = None
