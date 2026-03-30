"""
Adafruit VEML6075 UV sensor driver (I2C).

Reads raw UVA / UVB irradiance counts and calculates the UV Index using the
standard coefficients published in the VEML6075 application note.

Register map (subset):
    0x00  UV_CONF   – integration time, mode
    0x07  UVA_DATA  – raw UVA count
    0x09  UVB_DATA  – raw UVB count
    0x0A  UVCOMP1   – visible compensation channel 1
    0x0B  UVCOMP2   – IR compensation channel 2
"""
import random
import logging

from Zweather.node1_telemetry.sensors.base import BaseSensor
from Zweather.node1_telemetry import config

logger = logging.getLogger(__name__)

# VEML6075 register addresses
_REG_CONF = 0x00
_REG_UVA = 0x07
_REG_UVB = 0x09
_REG_UVCOMP1 = 0x0A
_REG_UVCOMP2 = 0x0B

# Application-note compensation coefficients (100 ms integration, no HD)
_UVA_A = 2.22
_UVA_B = 1.33
_UVB_C = 2.95
_UVB_D = 1.74
_UVA_RESP = 0.001461
_UVB_RESP = 0.002591


class UVSensor(BaseSensor):
    """Driver for the VEML6075 UV Index sensor over I2C / SMBus."""

    def __init__(self):
        super().__init__("uv_veml6075")
        self._bus = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        if not config.UV_SENSOR_ENABLED:
            logger.info("UV sensor disabled in configuration.")
            return

        try:
            import smbus2
            self._bus = smbus2.SMBus(config.UV_SENSOR_I2C_BUS)
            # Configure: 100 ms integration, active force mode, power on
            self._bus.write_word_data(config.UV_SENSOR_I2C_ADDR, _REG_CONF, 0x0010)
            self._available = True
            logger.info(
                "VEML6075 UV sensor initialised on I2C bus %d, addr 0x%02X.",
                config.UV_SENSOR_I2C_BUS, config.UV_SENSOR_I2C_ADDR,
            )
        except (ImportError, OSError) as exc:
            logger.warning("VEML6075 unavailable (%s). Using mock data.", exc)
            self._available = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _read_word(self, register: int) -> int:
        return self._bus.read_word_data(config.UV_SENSOR_I2C_ADDR, register)

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def read(self) -> dict:
        if self._available:
            return self._read_hardware()
        if config.UV_SENSOR_ENABLED:
            return self._read_mock()
        return {}

    def _read_hardware(self) -> dict:
        raw_uva = self._read_word(_REG_UVA)
        raw_uvb = self._read_word(_REG_UVB)
        comp1 = self._read_word(_REG_UVCOMP1)
        comp2 = self._read_word(_REG_UVCOMP2)

        # Compensated readings
        uva_comp = raw_uva - (_UVA_A * comp1) - (_UVA_B * comp2)
        uvb_comp = raw_uvb - (_UVB_C * comp1) - (_UVB_D * comp2)

        uv_index = round(((uva_comp * _UVA_RESP) + (uvb_comp * _UVB_RESP)) / 2, 2)
        uv_index = max(uv_index, 0.0)

        return {
            "uv_index": uv_index,
            "uva_raw": raw_uva,
            "uvb_raw": raw_uvb,
        }

    @staticmethod
    def _read_mock() -> dict:
        return {
            "uv_index": round(random.uniform(0, 11.0), 2),
            "uva_raw": random.randint(0, 3000),
            "uvb_raw": random.randint(0, 3000),
        }

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def cleanup(self) -> None:
        if self._bus is not None:
            try:
                # Power down
                self._bus.write_word_data(
                    config.UV_SENSOR_I2C_ADDR, _REG_CONF, 0x0001
                )
                self._bus.close()
            except OSError:
                pass
