"""
Modbus / RS485 industrial sensor driver (via Waveshare RS485 CAN HAT).

Reads holding registers from:
    - Anemometer (wind speed & direction)
    - Industrial rain gauge

Standard Modbus-RTU register layout assumed:
    Anemometer  – unit ``config.MODBUS_ANEMOMETER_UNIT_ID``
        Register 0x0000: wind speed  × 10 (0.1 m/s resolution)
        Register 0x0001: wind direction in degrees (0–359)
    Rain gauge  – unit ``config.MODBUS_RAIN_GAUGE_UNIT_ID``
        Register 0x0000: cumulative rainfall × 10 (0.1 mm resolution)
"""
import random
import logging

from Zweather.node1_telemetry.sensors.base import BaseSensor
from Zweather.node1_telemetry import config

logger = logging.getLogger(__name__)


class ModbusSensors(BaseSensor):
    """RS485 Modbus-RTU driver for industrial weather peripherals."""

    def __init__(self):
        super().__init__("modbus_rs485")
        self._client = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> None:
        if not config.MODBUS_ENABLED:
            logger.info("Modbus sensors disabled in configuration.")
            return

        try:
            from pymodbus.client import ModbusSerialClient
            self._client = ModbusSerialClient(
                port=config.MODBUS_PORT,
                baudrate=config.MODBUS_BAUDRATE,
                parity="N",
                stopbits=1,
                bytesize=8,
                timeout=2,
            )
            connected = self._client.connect()
            if connected:
                self._available = True
                logger.info(
                    "Modbus RS485 client connected on %s @ %d baud.",
                    config.MODBUS_PORT, config.MODBUS_BAUDRATE,
                )
            else:
                logger.warning("Modbus client failed to connect on %s.", config.MODBUS_PORT)
        except (ImportError, OSError) as exc:
            logger.warning("Modbus unavailable (%s). Using mock data.", exc)
            self._available = False

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def read(self) -> dict:
        if self._available:
            return self._read_hardware()
        if config.MODBUS_ENABLED:
            return self._read_mock()
        return {}

    def _read_hardware(self) -> dict:
        data: dict = {}

        # Anemometer
        try:
            result = self._client.read_holding_registers(
                address=0x0000,
                count=2,
                slave=config.MODBUS_ANEMOMETER_UNIT_ID,
            )
            if not result.isError():
                data["wind_speed_ms"] = round(result.registers[0] / 10.0, 1)
                data["wind_direction_deg"] = result.registers[1]
            else:
                logger.warning("Anemometer Modbus read error: %s", result)
        except Exception as exc:
            logger.error("Anemometer read failed: %s", exc)

        # Industrial rain gauge
        try:
            result = self._client.read_holding_registers(
                address=0x0000,
                count=1,
                slave=config.MODBUS_RAIN_GAUGE_UNIT_ID,
            )
            if not result.isError():
                data["modbus_rain_total_mm"] = round(result.registers[0] / 10.0, 1)
            else:
                logger.warning("Rain gauge Modbus read error: %s", result)
        except Exception as exc:
            logger.error("Rain gauge read failed: %s", exc)

        return data

    @staticmethod
    def _read_mock() -> dict:
        return {
            "wind_speed_ms": round(random.uniform(0, 25.0), 1),
            "wind_direction_deg": random.randint(0, 359),
            "modbus_rain_total_mm": round(random.uniform(0, 50.0), 1),
        }

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def cleanup(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
