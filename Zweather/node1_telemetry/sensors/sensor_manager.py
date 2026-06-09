"""
Unified sensor aggregation manager.

Initialises every enabled sensor driver, collects their readings into a
single ``dict``, and provides a clean shutdown path.

Hardware profile (production Raspberry Pi Weather Node):
    - BCRobotics Weather HAT PRO – primary environmental + wind/rain station
    - AI HAT+ (Hailo-8L NPU via M.2 Key E) – on-device edge inference
    - Sense HAT v2 (optional) – IMU + 8×8 LED matrix
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
from Zweather.node1_telemetry.sensors.weather_hat_pro import WeatherHatProDriver
from Zweather.node1_telemetry.sensors.modbus_sensors import ModbusSensors
from Zweather.node1_telemetry.sensors.bc_robotics_adc import BCRobotics16CHADC
from Zweather.node1_telemetry.sensors.soil_moisture import SoilMoistureSensor

logger = logging.getLogger(__name__)


class SensorManager:
    """Facade that aggregates all registered sensor drivers."""

    def __init__(self):
        self._drivers: list = []
        self._sense_hat: SenseHatDriver | None = None
        self._ai_hat: AIHatDriver | None = None
        self._bc_adc: BCRobotics16CHADC | None = None
        self._soil_moisture: SoilMoistureSensor | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        """Discover and initialise all enabled sensor drivers."""
        logger.info("Initialising sensor manager …")

        # Warn about potential GPIO pin conflicts.
        if (config.RAIN_GAUGE_ENABLED and config.WEATHER_HAT_PRO_ENABLED
                and config.RAIN_GAUGE_GPIO_PIN == config.WEATHER_HAT_PRO_RAIN_GAUGE_GPIO_PIN):
            logger.warning(
                "GPIO pin %d is configured for both RainGaugeSensor and "
                "WeatherHatProDriver rain gauge. Only the first driver to "
                "claim it will succeed. Set RAIN_GAUGE_GPIO_PIN or "
                "WEATHER_HAT_PRO_RAIN_GAUGE_GPIO_PIN to different values.",
                config.RAIN_GAUGE_GPIO_PIN,
            )

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

        weather_hat_pro = WeatherHatProDriver()
        weather_hat_pro.initialize()
        self._drivers.append(weather_hat_pro)

        modbus = ModbusSensors()
        modbus.initialize()
        self._drivers.append(modbus)

        # BC Robotics 16CH ADC HAT (initialised first so soil moisture can
        # share the same ADC hardware).
        if config.BC_ROBOTICS_ADC_ENABLED:
            adc = BCRobotics16CHADC()
            adc.initialize()
            self._drivers.append(adc)
            self._bc_adc = adc

        # Gravity Capacitive Soil Moisture Sensor (shares ADC with the
        # BC Robotics HAT when available).
        if config.SOIL_MOISTURE_ENABLED:
            soil = SoilMoistureSensor(adc_provider=self._bc_adc)
            soil.initialize()
            self._drivers.append(soil)
            self._soil_moisture = soil

        active = [d.name for d in self._drivers if d.available]
        logger.info(
            "Sensor manager ready — %d driver(s) active: %s",
            len(active), ", ".join(active) or "(none — no real hardware detected)",
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
