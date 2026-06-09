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
            logger.warning(
                "Modbus unavailable (%s). No Modbus readings will be emitted.",
                exc,
            )
            self._available = False

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def read(self) -> dict:
        if self._available:
            return self._read_hardware()
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
                regs = result.registers
                if len(regs) >= 2:
                    data["wind_speed_ms"] = round(regs[0] / 10.0, 1)
                    data["wind_direction_deg"] = regs[1]
                else:
                    logger.warning("Anemometer returned %d registers, expected 2", len(regs))
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
                regs = result.registers
                if len(regs) >= 1:
                    data["modbus_rain_total_mm"] = round(regs[0] / 10.0, 1)
                else:
                    logger.warning("Rain gauge returned empty register list")
            else:
                logger.warning("Rain gauge Modbus read error: %s", result)
        except Exception as exc:
            logger.error("Rain gauge read failed: %s", exc)

        return data

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def cleanup(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except (OSError, RuntimeError):
                logger.debug("Modbus client cleanup failed", exc_info=True)
