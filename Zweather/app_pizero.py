"""
Zedd-Weather Edge Collector — Pi Zero 2WH Variant
==================================================
Standalone edge data-collection script for a Raspberry Pi Zero 2WH running
a BCRobotics Weather HAT PRO and a Google Coral USB Accelerator.

Key differences from the standard ``app.py``:
  - Weather HAT PRO is the primary sensor (NOT Sense HAT)
  - Google Coral Edge TPU replaces Hailo-8L for on-device inference
  - All data is pushed via MQTT to a remote broker (no local InfluxDB)
  - SQLite buffer lives on tmpfs (/tmp) to avoid SD card wear
  - Minimal logging and no heavy dependencies

Environment variables (all optional – sensible defaults provided):
  MQTT_BROKER_HOST         Remote MQTT broker address  (default: localhost)
  MQTT_BROKER_PORT         MQTT broker port            (default: 1883)
  MQTT_TOPIC               MQTT topic path             (default: zedd/telemetry/pizero)
  MQTT_CLIENT_ID           MQTT client identifier      (default: zedd-pizero-01)
  PUBLISH_INTERVAL         Seconds between readings    (default: 5.0)
  SQLITE_DB_PATH           SQLite buffer file path     (default: /tmp/zedd_buffer.db)
  BUFFER_FLUSH_INTERVAL    Seconds between buffer flushes (default: 300)
  MAX_BUFFER_ROWS          Max buffered rows before forced flush (default: 5000)
  CORAL_ENABLED            Use Coral Edge TPU          (default: true)
  CORAL_MODEL_PATH         Path to .tflite model       (default: /opt/zedd/models/...)
  WEATHER_HAT_PRO_ENABLED  Use Weather HAT PRO         (default: true)
  LOG_LEVEL                Python logging level        (default: INFO)
"""
from __future__ import annotations

import json
import logging
import math
import os
import pathlib
import sqlite3
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Generator, Optional

from Zweather.pizero import config as pz_config

# ---------------------------------------------------------------------------
# Optional imports – gracefully handle non-Pi / dev environments
# ---------------------------------------------------------------------------
try:
    from Zweather.node1_telemetry.sensors.weather_hat_pro import (
        WeatherHatProDriver,
    )
    _WEATHER_HAT_AVAILABLE = True
except ImportError:
    _WEATHER_HAT_AVAILABLE = False

try:
    from Zweather.node1_telemetry.sensors.bc_robotics_adc import (
        BCRobotics16CHADC,
    )
    _BC_ADC_AVAILABLE = True
except ImportError:
    _BC_ADC_AVAILABLE = False

try:
    from Zweather.node1_telemetry.sensors.soil_moisture import (
        SoilMoistureSensor,
    )
    _SOIL_MOISTURE_AVAILABLE = True
except ImportError:
    _SOIL_MOISTURE_AVAILABLE = False

try:
    from Zweather.pizero.coral_tpu_driver import CoralTPUDriver
    _CORAL_DRIVER_AVAILABLE = True
except ImportError:
    _CORAL_DRIVER_AVAILABLE = False

try:
    from Zweather.pizero.coral_npu_client import CoralNPUClient
    _CORAL_NPU_AVAILABLE = True
except ImportError:
    _CORAL_NPU_AVAILABLE = False

try:
    import paho.mqtt.client as mqtt  # type: ignore[import-untyped]
    _MQTT_AVAILABLE = True
except ImportError:
    _MQTT_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PUBLISH_INTERVAL = pz_config.PUBLISH_INTERVAL
SQLITE_DB_PATH = pz_config.SQLITE_DB_PATH
BUFFER_FLUSH_INTERVAL = pz_config.BUFFER_FLUSH_INTERVAL
MAX_BUFFER_ROWS = pz_config.MAX_BUFFER_ROWS
NODE_NAME = os.getenv("NODE_NAME", "pizero-01")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LIVENESS_FILE = pathlib.Path("/tmp/zedd-alive")

# Physical sanity bounds
TEMP_MIN_C = -50.0
TEMP_MAX_C = 85.0
HUMIDITY_MIN = 0.0
HUMIDITY_MAX = 100.0
PRESSURE_MIN_HPA = 870.0
PRESSURE_MAX_HPA = 1085.0

# Z-score anomaly detection
ZSCORE_WINDOW = 20
ZSCORE_THRESHOLD = 4.0

log = logging.getLogger("zedd.pizero.edge")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class TelemetryReading:
    timestamp: datetime
    temperature_c: float
    humidity_pct: float
    pressure_hpa: float
    wind_speed_ms: float = 0.0
    wind_direction_deg: float = 0.0
    rain_mm: float = 0.0
    soil_moisture_pct: float = -1.0
    anomaly: bool = False
    anomaly_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "node": NODE_NAME,
            "temperature_c": self.temperature_c,
            "humidity_pct": self.humidity_pct,
            "pressure_hpa": self.pressure_hpa,
            "wind_speed_ms": self.wind_speed_ms,
            "wind_direction_deg": self.wind_direction_deg,
            "rain_mm": self.rain_mm,
            "anomaly": self.anomaly,
            "anomaly_reason": self.anomaly_reason,
        }
        if self.soil_moisture_pct >= 0:
            d["soil_moisture_pct"] = self.soil_moisture_pct
        return d


# ---------------------------------------------------------------------------
# SQLite offline buffer (stored in tmpfs — /tmp — to protect SD card)
# ---------------------------------------------------------------------------
def _init_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS buffer (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          INTEGER NOT NULL,
            temperature REAL    NOT NULL,
            humidity    REAL    NOT NULL,
            pressure    REAL    NOT NULL,
            wind_speed  REAL    NOT NULL DEFAULT 0.0,
            wind_dir    REAL    NOT NULL DEFAULT 0.0,
            rain_mm     REAL    NOT NULL DEFAULT 0.0,
            anomaly     INTEGER NOT NULL DEFAULT 0,
            reason      TEXT    NOT NULL DEFAULT ''
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON buffer(ts)")
    # Add optional columns that may not exist on databases created before
    # the soil moisture sensor was introduced.
    for col in ("soil_moisture REAL NOT NULL DEFAULT -1.0",):
        try:
            conn.execute(f"ALTER TABLE buffer ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    return conn


@contextmanager
def _db_cursor(conn: sqlite3.Connection) -> Generator[sqlite3.Cursor, None, None]:
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        cur.close()


def buffer_reading(conn: sqlite3.Connection, reading: TelemetryReading) -> None:
    with _db_cursor(conn) as cur:
        cur.execute(
            "INSERT INTO buffer (ts, temperature, humidity, pressure, "
            "wind_speed, wind_dir, rain_mm, soil_moisture, anomaly, reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                int(reading.timestamp.timestamp()),
                reading.temperature_c,
                reading.humidity_pct,
                reading.pressure_hpa,
                reading.wind_speed_ms,
                reading.wind_direction_deg,
                reading.rain_mm,
                reading.soil_moisture_pct,
                int(reading.anomaly),
                reading.anomaly_reason,
            ),
        )
    log.debug("Buffered reading (ts=%s)", reading.timestamp.isoformat())


def pop_buffered(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Fetch and delete all buffered readings, returning them as dicts."""
    with _db_cursor(conn) as cur:
        cur.execute(
            "SELECT id, ts, temperature, humidity, pressure, "
            "wind_speed, wind_dir, rain_mm, soil_moisture, anomaly, reason "
            "FROM buffer ORDER BY ts ASC"
        )
        rows = cur.fetchall()

    if not rows:
        return []

    records = []
    ids = []
    for row in rows:
        (
            row_id, ts, temp, hum, pres,
            wind_speed, wind_dir, rain_mm, soil_moisture, anom, reason,
        ) = row
        rec: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
            "node": NODE_NAME,
            "temperature_c": temp,
            "humidity_pct": hum,
            "pressure_hpa": pres,
            "wind_speed_ms": wind_speed,
            "wind_direction_deg": wind_dir,
            "rain_mm": rain_mm,
            "anomaly": bool(anom),
            "anomaly_reason": reason,
        }
        if soil_moisture >= 0:
            rec["soil_moisture_pct"] = soil_moisture
        records.append(rec)
        ids.append(row_id)

    with _db_cursor(conn) as cur:
        cur.executemany("DELETE FROM buffer WHERE id = ?", [(i,) for i in ids])

    log.info("Popped %d buffered readings for MQTT publish", len(ids))
    return records


# ---------------------------------------------------------------------------
# Sensor reading
# ---------------------------------------------------------------------------
class WeatherHatProReader:
    """Reads from the BCRobotics Weather HAT PRO (primary sensor)."""

    def __init__(self) -> None:
        if not _WEATHER_HAT_AVAILABLE:
            raise RuntimeError(
                "Weather HAT PRO driver is not installed. "
                "Install it with: pip install Zweather[node1]"
            )
        self._hat = WeatherHatProDriver()
        self._hat.initialize()

    def read(self) -> TelemetryReading:
        data = self._hat.read()
        temp = data.get("temperature_c", 20.0)
        humidity = data.get("humidity_pct", 50.0)
        pressure = data.get("pressure_hpa", 1013.25)
        wind_speed = data.get("wind_speed_ms", 0.0)
        wind_dir = data.get("wind_direction_deg", 0.0)
        rain_mm = data.get("rain_mm", 0.0)

        return TelemetryReading(
            timestamp=datetime.now(tz=timezone.utc),
            temperature_c=round(temp, 2),
            humidity_pct=round(humidity, 2),
            pressure_hpa=round(pressure, 2),
            wind_speed_ms=round(wind_speed, 2),
            wind_direction_deg=round(wind_dir, 1),
            rain_mm=round(rain_mm, 4),
        )


class SoilMoistureReader:
    """Reads from the Gravity Capacitive Soil Moisture Sensor via BC Robotics ADC."""

    def __init__(self) -> None:
        self._sensor: Optional[SoilMoistureSensor] = None
        if not _SOIL_MOISTURE_AVAILABLE or not _BC_ADC_AVAILABLE:
            log.info("Soil moisture or ADC driver not available — disabled.")
            return
        try:
            self._sensor = SoilMoistureSensor()
            self._sensor.initialize()
            if self._sensor.available:
                log.info("Soil moisture sensor initialised.")
        except Exception as exc:
            log.warning("Soil moisture sensor init failed: %s", exc)

    def read_moisture(self) -> float:
        if self._sensor is None or not self._sensor.available:
            return -1.0
        try:
            data = self._sensor.read()
            return float(data.get("soil_moisture_pct", -1.0))
        except Exception as exc:
            log.warning("Soil moisture read failed: %s", exc)
            return -1.0

    def cleanup(self) -> None:
        if self._sensor is not None:
            self._sensor.cleanup()


# ---------------------------------------------------------------------------
# Validation & anomaly detection
# ---------------------------------------------------------------------------
class AnomalyDetector:
    """Two-stage anomaly detection: physical bounds + Z-score."""

    def __init__(self, window: int = ZSCORE_WINDOW, threshold: float = ZSCORE_THRESHOLD) -> None:
        self._window = window
        self._threshold = threshold
        self._temps: list[float] = []
        self._humidities: list[float] = []
        self._pressures: list[float] = []

    def _update_window(self, lst: list[float], value: float) -> None:
        lst.append(value)
        if len(lst) > self._window:
            lst.pop(0)

    @staticmethod
    def _zscore(value: float, history: list[float]) -> Optional[float]:
        if len(history) < 5:
            return None
        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        std = math.sqrt(variance)
        if std < 1e-9:
            return 0.0
        return abs(value - mean) / std

    def validate(self, reading: TelemetryReading) -> TelemetryReading:
        reasons: list[str] = []

        if not (TEMP_MIN_C <= reading.temperature_c <= TEMP_MAX_C):
            reasons.append(
                f"temp {reading.temperature_c}°C out of range [{TEMP_MIN_C}, {TEMP_MAX_C}]"
            )
        if not (HUMIDITY_MIN <= reading.humidity_pct <= HUMIDITY_MAX):
            reasons.append(
                f"humidity {reading.humidity_pct}% out of range [{HUMIDITY_MIN}, {HUMIDITY_MAX}]"
            )
        if not (PRESSURE_MIN_HPA <= reading.pressure_hpa <= PRESSURE_MAX_HPA):
            reasons.append(
                f"pressure {reading.pressure_hpa} hPa out of range [{PRESSURE_MIN_HPA}, {PRESSURE_MAX_HPA}]"
            )

        for value, history, name in (
            (reading.temperature_c, self._temps, "temp"),
            (reading.humidity_pct, self._humidities, "humidity"),
            (reading.pressure_hpa, self._pressures, "pressure"),
        ):
            z = self._zscore(value, history)
            if z is not None and z > self._threshold:
                reasons.append(f"{name} Z-score={z:.1f} > {self._threshold}")

        self._update_window(self._temps, reading.temperature_c)
        self._update_window(self._humidities, reading.humidity_pct)
        self._update_window(self._pressures, reading.pressure_hpa)

        if reasons:
            reading.anomaly = True
            reading.anomaly_reason = "; ".join(reasons)
            log.warning("Anomaly detected: %s", reading.anomaly_reason)
        return reading


# ---------------------------------------------------------------------------
# MQTT publisher
# ---------------------------------------------------------------------------
class MQTTPublisher:
    """Thin wrapper for publishing telemetry to a remote MQTT broker."""

    def __init__(self) -> None:
        self._client: Optional[mqtt.Client] = None
        self._connected = False

    def connect(self) -> bool:
        if not _MQTT_AVAILABLE:
            log.warning("paho-mqtt not installed — MQTT publishing disabled.")
            return False

        try:
            self._client = mqtt.Client(
                client_id=pz_config.MQTT_CLIENT_ID,
                protocol=mqtt.MQTTv311,
            )
            self._client.connect(
                pz_config.MQTT_BROKER_HOST,
                pz_config.MQTT_BROKER_PORT,
                keepalive=60,
            )
            self._client.loop_start()
            self._connected = True
            log.info(
                "Connected to MQTT broker at %s:%d",
                pz_config.MQTT_BROKER_HOST,
                pz_config.MQTT_BROKER_PORT,
            )
            return True
        except (OSError, RuntimeError, ValueError) as exc:
            log.warning("MQTT connection failed: %s", exc)
            return False

    def publish(self, payload: dict) -> bool:
        if not self._connected or self._client is None:
            return False
        try:
            topic = pz_config.MQTT_TOPIC
            msg = json.dumps(payload, default=str)
            result = self._client.publish(topic, msg, qos=1)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                log.warning("MQTT publish returned rc=%d", result.rc)
                return False
            return True
        except (OSError, RuntimeError) as exc:
            log.warning("MQTT publish failed: %s", exc)
            return False

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except (OSError, RuntimeError):
                log.debug("MQTT disconnect issue", exc_info=True)
            self._client = None
            self._connected = False


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------
class CoralInferenceEngine:
    """Manages Coral Edge TPU inference and fallback."""

    def __init__(self) -> None:
        self._driver: Optional[CoralTPUDriver] = None
        self._client: Optional[CoralNPUClient] = None
        self._available = False

    def initialize(self) -> None:
        if _CORAL_DRIVER_AVAILABLE and pz_config.CORAL_ENABLED:
            try:
                self._driver = CoralTPUDriver()
                self._driver.initialize()
                if self._driver.available:
                    log.info("Coral TPU driver initialised")
            except Exception as exc:
                log.warning("Coral TPU driver init failed: %s", exc)

        if _CORAL_NPU_AVAILABLE and pz_config.CORAL_ENABLED:
            try:
                self._client = CoralNPUClient()
                self._client.initialize()
                self._available = self._client.is_available
            except Exception as exc:
                log.warning("Coral NPU client init failed: %s", exc)

    def classify(self, telemetry: dict) -> dict[str, Any]:
        if self._client is not None and self._available:
            return self._client.classify_weather(telemetry)
        if self._driver is not None:
            return self._driver.classify(telemetry)
        return {"label": "unknown", "confidence": 0.0, "source": "none"}

    def cleanup(self) -> None:
        if self._driver is not None:
            self._driver.cleanup()
        if self._client is not None:
            self._client.cleanup()


# ---------------------------------------------------------------------------
# Liveness probe
# ---------------------------------------------------------------------------
def touch_liveness() -> None:
    try:
        LIVENESS_FILE.touch()
    except OSError as exc:
        log.debug("Could not touch liveness file: %s", exc)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def run() -> None:
    log.info(
        "Zedd-Weather Pi Zero 2WH edge collector starting (node=%s, interval=%.1fs)",
        NODE_NAME, PUBLISH_INTERVAL,
    )

    # Initialise sensor
    if not _WEATHER_HAT_AVAILABLE or not pz_config.WEATHER_HAT_PRO_ENABLED:
        log.error(
            "Weather HAT PRO is required for Pi Zero edge collector. "
            "Set WEATHER_HAT_PRO_ENABLED=true and install the driver."
        )
        sys.exit(1)
    reader = WeatherHatProReader()

    # Initialise SQLite buffer (tmpfs)
    db_conn = _init_db(SQLITE_DB_PATH)
    log.info("SQLite buffer at %s (tmpfs)", SQLITE_DB_PATH)

    # Initialise MQTT publisher
    mqtt_pub = MQTTPublisher()
    mqtt_connected = mqtt_pub.connect()

    # Initialise anomaly detector
    detector = AnomalyDetector()

    # Initialise Coral inference engine
    coral = CoralInferenceEngine()
    coral.initialize()

    # Initialise soil moisture sensor
    soil_reader = SoilMoistureReader()

    # Track buffer flush timing
    last_flush = time.monotonic()

    while True:
        cycle_start = time.monotonic()

        try:
            # 1. Read sensors
            reading = reader.read()
            soil_moisture = soil_reader.read_moisture()
            if soil_moisture >= 0:
                reading.soil_moisture_pct = soil_moisture
            log.debug(
                "Read: temp=%.2f°C  humidity=%.2f%%  pressure=%.2f hPa  "
                "wind=%.1f m/s  rain=%.4f mm  soil=%.1f%%",
                reading.temperature_c,
                reading.humidity_pct,
                reading.pressure_hpa,
                reading.wind_speed_ms,
                reading.rain_mm,
                soil_moisture if soil_moisture >= 0 else -1.0,
            )

            # 2. Validate
            reading = detector.validate(reading)

            # 3. Run Coral inference
            telemetry_dict = reading.to_dict()
            classification = coral.classify(telemetry_dict)
            telemetry_dict["classification"] = classification

            # 4. Publish via MQTT
            if mqtt_connected:
                published = mqtt_pub.publish(telemetry_dict)
                if not published:
                    buffer_reading(db_conn, reading)
                    log.warning("MQTT publish failed — buffered locally")
            else:
                buffer_reading(db_conn, reading)

            # 5. Flush buffer periodically
            elapsed = time.monotonic() - last_flush
            if elapsed >= BUFFER_FLUSH_INTERVAL:
                if mqtt_connected:
                    records = pop_buffered(db_conn)
                    for rec in records:
                        mqtt_pub.publish(rec)
                last_flush = time.monotonic()

            touch_liveness()

        except KeyboardInterrupt:
            log.info("Interrupted – shutting down")
            break
        except Exception as exc:
            log.exception("Unexpected error in main loop: %s", exc)

        elapsed = time.monotonic() - cycle_start
        time.sleep(max(0.0, PUBLISH_INTERVAL - elapsed))

    # Cleanup
    log.info("Closing resources…")
    coral.cleanup()
    soil_reader.cleanup()
    mqtt_pub.disconnect()
    db_conn.close()
    log.info("Pi Zero edge collector stopped")


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    run()
