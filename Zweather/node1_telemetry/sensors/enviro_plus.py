"""
Pimoroni Enviro+ sensor suite driver.

Exposes readings from:
    - BME280  — temperature, pressure, humidity (higher accuracy than Sense HAT)
    - LTR559  — ambient light and proximity
    - MICS6814 (analog via ADS1015) — reducing, oxidising, and NH3 gas levels
    - PMS5003  — particulate matter (PM1.0, PM2.5, PM10)

All sub-sensors degrade gracefully: if one component fails to initialise the
driver still returns data from the remaining components.  When **no**
sub-sensor is available the driver emits an empty payload — it never
synthesises fake readings.
"""
import logging

from Zweather.node1_telemetry.sensors.base import BaseSensor
from Zweather.node1_telemetry import config

logger = logging.getLogger(__name__)


class EnviroPlusSensor(BaseSensor):
    """Composite driver for the Pimoroni Enviro+ HAT."""

    def __init__(self):
        super().__init__("enviro_plus")
        self._bme280 = None
        self._bme280_bus = None
        self._ltr559 = None
        self._gas = None
        self._pms5003 = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        if not config.ENVIRO_PLUS_ENABLED:
            logger.info("Enviro+ disabled in configuration.")
            return

        any_ok = False

        # BME280
        try:
            from bme280 import BME280
            from smbus2 import SMBus
            bus = SMBus(1)
            self._bme280_bus = bus
            self._bme280 = BME280(i2c_dev=bus)
            # Discard first reading (sensor warm-up)
            self._bme280.get_temperature()
            any_ok = True
            logger.info("Enviro+ BME280 initialized.")
        except (ImportError, OSError) as exc:
            logger.warning("BME280 unavailable (%s).", exc)

        # LTR559 light / proximity
        try:
            from ltr559 import LTR559
            self._ltr559 = LTR559()
            any_ok = True
            logger.info("Enviro+ LTR559 light sensor initialized.")
        except (ImportError, OSError) as exc:
            logger.warning("LTR559 unavailable (%s).", exc)

        # Analog gas sensor (enviroplus library wraps ADS1015)
        try:
            from enviroplus import gas as gas_module
            self._gas = gas_module
            any_ok = True
            logger.info("Enviro+ gas sensor initialized.")
        except (ImportError, OSError) as exc:
            logger.warning("Gas sensor unavailable (%s).", exc)

        # PMS5003 particulate matter
        try:
            from pms5003 import PMS5003
            self._pms5003 = PMS5003()
            any_ok = True
            logger.info("Enviro+ PMS5003 particulate sensor initialized.")
        except (ImportError, OSError) as exc:
            logger.warning("PMS5003 unavailable (%s).", exc)

        self._available = any_ok
        if not any_ok:
            logger.warning(
                "No Enviro+ sub-sensors available. No Enviro+ readings will "
                "be emitted."
            )

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def read(self) -> dict:
        if self._available:
            return self._read_hardware()
        return {}

    def _read_hardware(self) -> dict:
        data: dict = {}

        if self._bme280 is not None:
            try:
                data["enviro_temp_c"] = round(self._bme280.get_temperature(), 2)
                data["enviro_pressure_hpa"] = round(self._bme280.get_pressure(), 2)
                data["enviro_humidity_pct"] = round(self._bme280.get_humidity(), 2)
            except OSError as exc:
                logger.error("BME280 read error: %s", exc)

        if self._ltr559 is not None:
            try:
                data["light_lux"] = round(self._ltr559.get_lux(), 2)
                data["proximity"] = self._ltr559.get_proximity()
            except OSError as exc:
                logger.error("LTR559 read error: %s", exc)

        if self._gas is not None:
            try:
                readings = self._gas.read_all()
                data["gas_reducing_kohm"] = round(readings.reducing / 1000, 2)
                data["gas_oxidising_kohm"] = round(readings.oxidising / 1000, 2)
                data["gas_nh3_kohm"] = round(readings.nh3 / 1000, 2)
            except (OSError, AttributeError) as exc:
                logger.error("Gas sensor read error: %s", exc)

        if self._pms5003 is not None:
            try:
                pm = self._pms5003.read()
                data["pm1_0_ug_m3"] = pm.pm_ug_per_m3(1.0)
                data["pm2_5_ug_m3"] = pm.pm_ug_per_m3(2.5)
                data["pm10_ug_m3"] = pm.pm_ug_per_m3(10)
            except (OSError, AttributeError) as exc:
                logger.error("PMS5003 read error: %s", exc)

        return data

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def cleanup(self) -> None:
        if self._bme280_bus is not None:
            try:
                self._bme280_bus.close()
            except OSError:
                logger.debug("Enviro+ BME280 bus close failed", exc_info=True)

        if self._ltr559 is not None:
            try:
                self._ltr559._light_sensor = None  # no public close method
            except AttributeError:
                pass

        if self._pms5003 is not None:
            try:
                self._pms5003.reset()
            except (OSError, RuntimeError):
                logger.debug("Enviro+ PMS5003 cleanup failed", exc_info=True)
