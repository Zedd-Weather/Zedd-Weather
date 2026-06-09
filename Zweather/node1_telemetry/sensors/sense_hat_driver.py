"""
Full Sense HAT v2 driver.

Exposes:
    - Environmental sensors: temperature, humidity, barometric pressure
    - IMU: accelerometer, gyroscope, magnetometer (compass heading)
    - LED 8×8 matrix control (delegated to hat_control for higher-level use)
    - Joystick events

CPU-proximity temperature compensation is applied automatically using the
offset value from ``config.SENSE_HAT_TEMP_OFFSET``.

When the Sense HAT hardware (or its Python library) is not available the
driver does **not** emit any synthetic data — ``read()`` simply returns
an empty dict and downstream consumers receive no Sense HAT keys.
"""
import logging

from Zweather.node1_telemetry.sensors.base import BaseSensor
from Zweather.node1_telemetry import config

logger = logging.getLogger(__name__)


class SenseHatDriver(BaseSensor):
    """Driver for the Raspberry Pi Sense HAT v2."""

    def __init__(self):
        super().__init__("sense_hat")
        self._sense = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        try:
            from sense_hat import SenseHat
            self._sense = SenseHat()
            self._available = True
            logger.info("Sense HAT initialised successfully.")
        except (ImportError, OSError) as exc:
            logger.warning(
                "Sense HAT unavailable (%s). No Sense HAT readings will be "
                "emitted.", exc,
            )
            self._available = False

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def read(self) -> dict:
        """Return a full snapshot of Sense HAT sensor data, or an empty
        dict when the hardware is unavailable."""
        if self._available:
            return self._read_hardware()
        return {}

    def _read_hardware(self) -> dict:
        data: dict = {}

        try:
            raw_temp = self._sense.get_temperature()
            data["temperature_c"] = round(raw_temp - config.SENSE_HAT_TEMP_OFFSET, 2)
        except OSError as exc:
            logger.error("Sense HAT temperature read failed: %s", exc)

        try:
            data["pressure_hpa"] = round(self._sense.get_pressure(), 2)
        except OSError as exc:
            logger.error("Sense HAT pressure read failed: %s", exc)

        try:
            data["humidity_pct"] = round(self._sense.get_humidity(), 2)
        except OSError as exc:
            logger.error("Sense HAT humidity read failed: %s", exc)

        try:
            orientation = self._sense.get_orientation_degrees()
            data["orientation"] = {
                "pitch": round(orientation.get("pitch", 0), 2),
                "roll": round(orientation.get("roll", 0), 2),
                "yaw": round(orientation.get("yaw", 0), 2),
            }
        except OSError as exc:
            logger.error("Sense HAT orientation read failed: %s", exc)

        try:
            accel = self._sense.get_accelerometer_raw()
            data["accelerometer"] = {
                "x": round(accel.get("x", 0), 4),
                "y": round(accel.get("y", 0), 4),
                "z": round(accel.get("z", 0), 4),
            }
        except OSError as exc:
            logger.error("Sense HAT accelerometer read failed: %s", exc)

        try:
            gyro = self._sense.get_gyroscope_raw()
            data["gyroscope"] = {
                "x": round(gyro.get("x", 0), 4),
                "y": round(gyro.get("y", 0), 4),
                "z": round(gyro.get("z", 0), 4),
            }
        except OSError as exc:
            logger.error("Sense HAT gyroscope read failed: %s", exc)

        try:
            mag = self._sense.get_compass_raw()
            data["magnetometer"] = {
                "x": round(mag.get("x", 0), 4),
                "y": round(mag.get("y", 0), 4),
                "z": round(mag.get("z", 0), 4),
            }
        except OSError as exc:
            logger.error("Sense HAT magnetometer read failed: %s", exc)

        return data

    # ------------------------------------------------------------------
    # Joystick helpers
    # ------------------------------------------------------------------
    def get_joystick_events(self) -> list:
        """Return pending joystick events (empty list if unavailable)."""
        if self._available:
            try:
                return self._sense.stick.get_events()
            except (OSError, RuntimeError):
                logger.debug("Sense HAT joystick read failed", exc_info=True)
        return []

    # ------------------------------------------------------------------
    # LED matrix pass-through (low-level)
    # ------------------------------------------------------------------
    def set_pixels(self, pixel_list: list) -> None:
        """Set all 64 pixels at once. *pixel_list* is 64 × [R, G, B]."""
        if self._available:
            try:
                self._sense.set_pixels(pixel_list)
            except (OSError, RuntimeError):
                logger.debug("Sense HAT set_pixels failed", exc_info=True)

    def show_message(self, text: str, scroll_speed: float = 0.1,
                     text_colour: list | None = None,
                     back_colour: list | None = None) -> None:
        """Scroll a text message across the LED matrix."""
        if self._available:
            try:
                self._sense.show_message(
                    text,
                    scroll_speed=scroll_speed,
                    text_colour=text_colour or [255, 255, 255],
                    back_colour=back_colour or [0, 0, 0],
                )
            except (OSError, RuntimeError):
                logger.debug("Sense HAT show_message failed", exc_info=True)

    def clear_display(self) -> None:
        """Turn off all LEDs."""
        if self._available:
            try:
                self._sense.clear()
            except (OSError, RuntimeError):
                logger.debug("Sense HAT clear failed", exc_info=True)

    def set_pixel(self, x: int, y: int, colour: list) -> None:
        """Set a single pixel at (x, y) to [R, G, B]."""
        if self._available:
            try:
                self._sense.set_pixel(x, y, colour)
            except (OSError, RuntimeError):
                logger.debug("Sense HAT set_pixel failed", exc_info=True)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def cleanup(self) -> None:
        if self._available:
            try:
                self._sense.clear()
            except (OSError, RuntimeError):
                pass
