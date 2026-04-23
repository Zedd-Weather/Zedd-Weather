"""
BCRobotics Weather HAT PRO driver.

The Weather HAT PRO (BCRobotics) is a Raspberry Pi add-on board that
exposes the following weather peripherals via three RJ12 jacks and an
on-board environmental sensor:

    - BME280               – temperature, pressure, humidity (I2C)
    - Reed-switch anemometer (RJ12 J2) – wind speed via pulse counter
                                          (one closure per revolution)
    - Wind vane (RJ12 J2) – analog wind direction read via the on-board
                            ADS1015 / MCP3008 ADC
    - Tipping-bucket rain gauge (RJ12 J3) – pulse counter on a reed
                                            switch (one closure per tip,
                                            ``RAIN_GAUGE_MM_PER_TIP`` mm)

The pinout matches the SparkFun / Argent Data Systems weather sensor
suite, which the Weather HAT PRO breaks out via standard 6-pin RJ12
sockets so the same anemometer / vane / rain gauge can be plugged in.

Unlike the Pimoroni Weather HAT, the BCRobotics Weather HAT PRO does
**not** ship with an ambient-light sensor or an LCD; the focus is on the
weather instruments themselves.

When the underlying I²C bus, ADC, or GPIO is not available the driver
emits **no readings** — it never synthesises fake values.
"""
import math
import time
import threading
import logging

from Zweather.node1_telemetry.sensors.base import BaseSensor
from Zweather.node1_telemetry import config

logger = logging.getLogger(__name__)


# A standard SparkFun-style anemometer reports one reed-switch closure
# per revolution; one closure per second corresponds to 2.4 km/h
# (= 0.6667 m/s) wind speed at the cup centre.
_ANEMOMETER_MS_PER_HZ = 0.6667

# Reed-switch debounce times (in milliseconds, passed to
# ``RPi.GPIO.add_event_detect``).  The anemometer pulses several times
# per second in strong winds, so we use a short 10 ms debounce; the
# rain-gauge bucket physically takes ~200 ms to tip and re-arm, hence
# the much longer 300 ms guard time.
_ANEMOMETER_DEBOUNCE_MS = 10
_RAIN_GAUGE_DEBOUNCE_MS = 300

# Maximum allowed delta (Volts) between a measured wind-vane voltage
# and a known calibration point in ``_VANE_LOOKUP``.  Readings further
# away than this are treated as a wiring fault and the bearing is
# omitted from the payload (instead of returning a misleading value).
_VANE_VOLTAGE_TOLERANCE_V = 0.30

# Wind-vane resistor-divider voltages (Volts, 5 V supply) → bearing in
# degrees.  Values are taken from the SparkFun weather meter datasheet
# and are accurate to ±5°.  Readings within ``_VANE_VOLTAGE_TOLERANCE_V``
# of an entry are matched to that bearing.
_VANE_LOOKUP = [
    (3.84, 0.0),    (1.98, 22.5),  (2.25, 45.0),  (0.41, 67.5),
    (0.45, 90.0),   (0.32, 112.5), (0.90, 135.0), (0.62, 157.5),
    (1.40, 180.0),  (1.19, 202.5), (3.08, 225.0), (2.93, 247.5),
    (4.62, 270.0),  (4.04, 292.5), (4.34, 315.0), (3.43, 337.5),
]


class WeatherHatProDriver(BaseSensor):
    """Composite driver for the BCRobotics Weather HAT PRO."""

    def __init__(self):
        super().__init__("weather_hat_pro")
        self._bme280 = None
        self._adc = None

        # Pulse counters (incremented from GPIO interrupt callbacks).
        self._anemometer_pulses = 0
        self._rain_pulses = 0
        self._rain_total_pulses = 0
        self._lock = threading.Lock()
        self._last_read_time = time.monotonic()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        if not config.WEATHER_HAT_PRO_ENABLED:
            logger.info("Weather HAT PRO disabled in configuration.")
            return

        any_ok = False

        # BME280 environmental sensor (I2C).
        try:
            from bme280 import BME280  # type: ignore[import-untyped]
            from smbus2 import SMBus  # type: ignore[import-untyped]
            bus = SMBus(config.WEATHER_HAT_PRO_I2C_BUS)
            self._bme280 = BME280(i2c_dev=bus)
            # Discard first reading (sensor warm-up).
            self._bme280.get_temperature()
            any_ok = True
            logger.info("Weather HAT PRO BME280 initialised.")
        except (ImportError, OSError) as exc:
            logger.warning("Weather HAT PRO BME280 unavailable (%s).", exc)

        # MCP3008 / ADS1015 ADC for the wind vane.
        try:
            from gpiozero import MCP3008  # type: ignore[import-untyped]
            self._adc = MCP3008(channel=config.WEATHER_HAT_PRO_VANE_ADC_CHANNEL)
            any_ok = True
            logger.info(
                "Weather HAT PRO wind-vane ADC initialised on channel %d.",
                config.WEATHER_HAT_PRO_VANE_ADC_CHANNEL,
            )
        except (ImportError, OSError, RuntimeError) as exc:
            logger.warning("Weather HAT PRO wind-vane ADC unavailable (%s).", exc)

        # GPIO reed-switch counters for the anemometer and rain gauge.
        try:
            import RPi.GPIO as GPIO  # type: ignore[import-untyped]
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(
                config.WEATHER_HAT_PRO_ANEMOMETER_GPIO_PIN,
                GPIO.IN, pull_up_down=GPIO.PUD_UP,
            )
            GPIO.setup(
                config.WEATHER_HAT_PRO_RAIN_GAUGE_GPIO_PIN,
                GPIO.IN, pull_up_down=GPIO.PUD_UP,
            )
            GPIO.add_event_detect(
                config.WEATHER_HAT_PRO_ANEMOMETER_GPIO_PIN,
                GPIO.FALLING,
                callback=self._on_anemometer_pulse,
                bouncetime=_ANEMOMETER_DEBOUNCE_MS,
            )
            GPIO.add_event_detect(
                config.WEATHER_HAT_PRO_RAIN_GAUGE_GPIO_PIN,
                GPIO.FALLING,
                callback=self._on_rain_pulse,
                bouncetime=_RAIN_GAUGE_DEBOUNCE_MS,
            )
            any_ok = True
            logger.info(
                "Weather HAT PRO GPIO pulse counters initialised "
                "(anemometer=BCM%d, rain=BCM%d).",
                config.WEATHER_HAT_PRO_ANEMOMETER_GPIO_PIN,
                config.WEATHER_HAT_PRO_RAIN_GAUGE_GPIO_PIN,
            )
        except (ImportError, RuntimeError) as exc:
            logger.warning("Weather HAT PRO GPIO unavailable (%s).", exc)

        self._available = any_ok
        if not any_ok:
            logger.warning(
                "No Weather HAT PRO sub-components available. No Weather "
                "HAT PRO readings will be emitted."
            )

    # ------------------------------------------------------------------
    # Interrupt callbacks
    # ------------------------------------------------------------------
    def _on_anemometer_pulse(self, _channel: int) -> None:
        with self._lock:
            self._anemometer_pulses += 1

    def _on_rain_pulse(self, _channel: int) -> None:
        with self._lock:
            self._rain_pulses += 1
            self._rain_total_pulses += 1

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def read(self) -> dict:
        if not self._available:
            return {}

        data: dict = {}

        # --- BME280 environmental ---
        if self._bme280 is not None:
            try:
                raw_temp = float(self._bme280.get_temperature())
                data["weather_hat_pro_temp_c"] = round(
                    raw_temp - config.WEATHER_HAT_PRO_TEMP_OFFSET, 2
                )
                data["weather_hat_pro_pressure_hpa"] = round(
                    float(self._bme280.get_pressure()), 2
                )
                data["weather_hat_pro_humidity_pct"] = round(
                    float(self._bme280.get_humidity()), 2
                )
            except OSError as exc:
                logger.error("Weather HAT PRO BME280 read error: %s", exc)

        # --- Anemometer (pulse → m/s integrated over the read interval) ---
        now = time.monotonic()
        with self._lock:
            anemo_pulses = self._anemometer_pulses
            self._anemometer_pulses = 0
            rain_pulses = self._rain_pulses
            self._rain_pulses = 0
            elapsed = max(now - self._last_read_time, 0.001)
            self._last_read_time = now

        wind_hz = anemo_pulses / elapsed
        data["wind_speed_ms"] = round(wind_hz * _ANEMOMETER_MS_PER_HZ, 2)

        # --- Rain gauge (mm in this interval + cumulative) ---
        data["rain_mm"] = round(
            rain_pulses * config.WEATHER_HAT_PRO_RAIN_MM_PER_TIP, 3
        )
        data["rain_total_mm"] = round(
            self._rain_total_pulses * config.WEATHER_HAT_PRO_RAIN_MM_PER_TIP, 3
        )

        # --- Wind vane (analog → bearing) ---
        if self._adc is not None:
            try:
                # gpiozero MCP3008.value is normalised to 0.0–1.0 of the
                # ADC reference voltage (default 3.3 V, but the vane is
                # divided down from 5 V via the on-board resistor network
                # so the lookup table values are pre-scaled).
                voltage = float(self._adc.value) * 5.0
                bearing = self._voltage_to_bearing(voltage)
                if bearing is not None:
                    data["wind_direction_deg"] = round(bearing, 1)
                    data["wind_direction_cardinal"] = (
                        self._degrees_to_cardinal(bearing)
                    )
            except (OSError, RuntimeError) as exc:
                logger.error("Weather HAT PRO wind-vane read error: %s", exc)

        return data

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _voltage_to_bearing(voltage: float) -> float | None:
        """Match a vane voltage to the closest entry in the lookup table."""
        best_bearing = None
        best_delta = math.inf
        for vane_v, bearing in _VANE_LOOKUP:
            delta = abs(voltage - vane_v)
            if delta < best_delta:
                best_delta = delta
                best_bearing = bearing
        # Reject readings that are far from any expected resistor value
        # (likely a disconnected vane or wiring fault).
        if best_delta > _VANE_VOLTAGE_TOLERANCE_V:
            return None
        return best_bearing

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
        try:
            import RPi.GPIO as GPIO  # type: ignore[import-untyped]
            for pin in (
                config.WEATHER_HAT_PRO_ANEMOMETER_GPIO_PIN,
                config.WEATHER_HAT_PRO_RAIN_GAUGE_GPIO_PIN,
            ):
                try:
                    GPIO.remove_event_detect(pin)
                except (RuntimeError, ValueError):
                    pass
        except (ImportError, RuntimeError):
            pass
        self._bme280 = None
        self._adc = None
