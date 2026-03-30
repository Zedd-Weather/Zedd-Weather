"""
Full Sense HAT v2 driver.

Exposes:
    - Environmental sensors: temperature, humidity, barometric pressure
    - IMU: accelerometer, gyroscope, magnetometer (compass heading)
    - LED 8×8 matrix control (delegated to hat_control for higher-level use)
    - Joystick events

CPU-proximity temperature compensation is applied automatically using the
offset value from ``config.SENSE_HAT_TEMP_OFFSET``.
"""
import random
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
            logger.warning("Sense HAT unavailable (%s). Using mock data.", exc)
            self._available = False

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def read(self) -> dict:
        """Return a full snapshot of Sense HAT sensor data."""
        if self._available:
            return self._read_hardware()
        return self._read_mock()

    def _read_hardware(self) -> dict:
        raw_temp = self._sense.get_temperature()
        compensated_temp = round(raw_temp - config.SENSE_HAT_TEMP_OFFSET, 2)

        orientation = self._sense.get_orientation_degrees()
        accel = self._sense.get_accelerometer_raw()
        gyro = self._sense.get_gyroscope_raw()
        mag = self._sense.get_compass_raw()

        return {
            "temperature_c": compensated_temp,
            "pressure_hpa": round(self._sense.get_pressure(), 2),
            "humidity_pct": round(self._sense.get_humidity(), 2),
            "orientation": {
                "pitch": round(orientation.get("pitch", 0), 2),
                "roll": round(orientation.get("roll", 0), 2),
                "yaw": round(orientation.get("yaw", 0), 2),
            },
            "accelerometer": {
                "x": round(accel.get("x", 0), 4),
                "y": round(accel.get("y", 0), 4),
                "z": round(accel.get("z", 0), 4),
            },
            "gyroscope": {
                "x": round(gyro.get("x", 0), 4),
                "y": round(gyro.get("y", 0), 4),
                "z": round(gyro.get("z", 0), 4),
            },
            "magnetometer": {
                "x": round(mag.get("x", 0), 4),
                "y": round(mag.get("y", 0), 4),
                "z": round(mag.get("z", 0), 4),
            },
        }

    @staticmethod
    def _read_mock() -> dict:
        return {
            "temperature_c": round(random.uniform(18.0, 30.0), 2),
            "pressure_hpa": round(random.uniform(1005.0, 1020.0), 2),
            "humidity_pct": round(random.uniform(30.0, 70.0), 2),
            "orientation": {"pitch": 0.0, "roll": 0.0, "yaw": 0.0},
            "accelerometer": {"x": 0.0, "y": 0.0, "z": 1.0},
            "gyroscope": {"x": 0.0, "y": 0.0, "z": 0.0},
            "magnetometer": {"x": 20.0, "y": -5.0, "z": -40.0},
        }

    # ------------------------------------------------------------------
    # Joystick helpers
    # ------------------------------------------------------------------
    def get_joystick_events(self) -> list:
        """Return pending joystick events (empty list if unavailable)."""
        if self._available:
            return self._sense.stick.get_events()
        return []

    # ------------------------------------------------------------------
    # LED matrix pass-through (low-level)
    # ------------------------------------------------------------------
    def set_pixels(self, pixel_list: list) -> None:
        """Set all 64 pixels at once. *pixel_list* is 64 × [R, G, B]."""
        if self._available:
            self._sense.set_pixels(pixel_list)

    def show_message(self, text: str, scroll_speed: float = 0.1,
                     text_colour: list | None = None,
                     back_colour: list | None = None) -> None:
        """Scroll a text message across the LED matrix."""
        if self._available:
            self._sense.show_message(
                text,
                scroll_speed=scroll_speed,
                text_colour=text_colour or [255, 255, 255],
                back_colour=back_colour or [0, 0, 0],
            )

    def clear_display(self) -> None:
        """Turn off all LEDs."""
        if self._available:
            self._sense.clear()

    def set_pixel(self, x: int, y: int, colour: list) -> None:
        """Set a single pixel at (x, y) to [R, G, B]."""
        if self._available:
            self._sense.set_pixel(x, y, colour)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def cleanup(self) -> None:
        if self._available:
            self._sense.clear()
