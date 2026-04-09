"""
Unified sensor aggregation manager.

Initialises every enabled sensor driver, collects their readings into a
single ``dict``, and provides a clean shutdown path.

Hardware profile (production Raspberry Pi Weather Node):
    - Sense HAT v2   – environmental + IMU sensors, 8×8 LED matrix
    - AI HAT+ (Hailo-8L NPU via M.2 Key E) – on-device edge inference
    - GPIO / I2C / Modbus peripherals
"""
import time
import logging

from Zweather.node1_telemetry import config
from Zweather.node1_telemetry.sensors.sense_hat_driver import SenseHatDriver
from Zweather.node1_telemetry.sensors.ai_hat_driver import AIHatDriver
from Zweather.node1_telemetry.sensors.gpio_sensors import RainGaugeSensor
from Zweather.node1_telemetry.sensors.uv_sensor import UVSensor
from Zweather.node1_telemetry.sensors.enviro_plus import EnviroPlusSensor
from Zweather.node1_telemetry.sensors.modbus_sensors import ModbusSensors

logger = logging.getLogger(__name__)


class SensorManager:
    """Facade that aggregates all registered sensor drivers."""

    def __init__(self):
        self._drivers = []
        self._sense_hat: SenseHatDriver | None = None
        self._ai_hat: AIHatDriver | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        """Discover and initialise all enabled sensor drivers."""
        logger.info("Initialising sensor manager …")

        if config.SENSE_HAT_ENABLED:
            driver = SenseHatDriver()
            driver.initialize()
            self._drivers.append(driver)
            self._sense_hat = driver

        if config.AI_HAT_ENABLED:
            ai_driver = AIHatDriver()
            ai_driver.initialize()
            self._drivers.append(ai_driver)
            self._ai_hat = ai_driver

        rain = RainGaugeSensor()
        rain.initialize()
        self._drivers.append(rain)

        uv = UVSensor()
        uv.initialize()
        self._drivers.append(uv)

        enviro = EnviroPlusSensor()
        enviro.initialize()
        self._drivers.append(enviro)

        modbus = ModbusSensors()
        modbus.initialize()
        self._drivers.append(modbus)

        active = [d.name for d in self._drivers if d.available]
        logger.info(
            "Sensor manager ready — %d driver(s) active: %s",
            len(active), ", ".join(active) or "(mock only)",
        )

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def read_all(self) -> dict:
        """Return a merged dict of all sensor readings plus a timestamp."""
        payload: dict = {"timestamp": time.time()}
        for driver in self._drivers:
            try:
                readings = driver.read()
                payload.update(readings)
            except Exception as exc:
                logger.error("Error reading %s: %s", driver.name, exc)
        return payload

    # ------------------------------------------------------------------
    # Sense HAT access (for HAT control layer)
    # ------------------------------------------------------------------
    @property
    def sense_hat(self) -> SenseHatDriver | None:
        """Return the Sense HAT driver instance (or *None*)."""
        return self._sense_hat

    # ------------------------------------------------------------------
    # AI HAT access (for NPU inference)
    # ------------------------------------------------------------------
    @property
    def ai_hat(self) -> AIHatDriver | None:
        """Return the AI HAT driver instance (or *None*)."""
        return self._ai_hat

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def cleanup(self) -> None:
        """Release all hardware resources."""
        for driver in self._drivers:
            try:
                driver.cleanup()
            except Exception as exc:
                logger.warning("Error cleaning up %s: %s", driver.name, exc)
        logger.info("Sensor manager shut down.")
