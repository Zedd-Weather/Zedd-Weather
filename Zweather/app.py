"""
Zedd-Weather Edge Collector
===========================
Standalone edge data-collection script for a Raspberry Pi running a Sense HAT.

Responsibilities:
  1. Read temperature, humidity, and pressure from the Sense HAT (with CPU
     temperature compensation).
  2. Validate readings and flag anomalies.
  3. Write batched data points to InfluxDB.
  4. Buffer data locally in SQLite when InfluxDB is unreachable, and flush
     the buffer once connectivity is restored.
  5. Touch /tmp/zedd-alive after every successful cycle so the K3s
     liveness probe can detect hangs.

Environment variables (all optional – sensible defaults provided):
  INFLUXDB_URL            InfluxDB base URL              (default: http://localhost:8086)
  INFLUXDB_TOKEN          InfluxDB API token             (default: "")
  INFLUXDB_ORG            InfluxDB organisation          (default: zedd-weather)
  INFLUXDB_BUCKET         InfluxDB bucket name           (default: telemetry)
  PUBLISH_INTERVAL        Seconds between readings       (default: 10.0)
  SENSE_HAT_ENABLED       Use real hardware              (default: true)
  SENSE_HAT_TEMP_OFFSET   CPU heat compensation °C       (default: 2.0)
  NODE_NAME               Logical node identifier        (default: edge-node-1)
  SQLITE_DB_PATH          SQLite buffer file path        (default: /tmp/zedd_buffer.db)
  LOG_LEVEL               Python logging level           (default: INFO)
"""

from __future__ import annotations

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
from typing import Any, Generator, List, Optional

# ---------------------------------------------------------------------------
# Optional heavy imports – guarded so the module loads on non-Pi hosts too
# ---------------------------------------------------------------------------
try:
    from sense_hat import SenseHat  # type: ignore
    _SENSE_HAT_AVAILABLE = True
except ImportError:
    _SENSE_HAT_AVAILABLE = False

try:
    from influxdb_client import InfluxDBClient, Point, WritePrecision  # type: ignore
    from influxdb_client.client.write_api import SYNCHRONOUS, WriteApi  # type: ignore
    _INFLUXDB_AVAILABLE = True
except ImportError:
    _INFLUXDB_AVAILABLE = False
    WriteApi = Any  # type: ignore[misc,assignment]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INFLUXDB_URL      = os.getenv("INFLUXDB_URL",           "http://localhost:8086")
INFLUXDB_TOKEN    = os.getenv("INFLUXDB_TOKEN",          "")
INFLUXDB_ORG      = os.getenv("INFLUXDB_ORG",            "zedd-weather")
INFLUXDB_BUCKET   = os.getenv("INFLUXDB_BUCKET",         "telemetry")
PUBLISH_INTERVAL  = float(os.getenv("PUBLISH_INTERVAL",  "10.0"))
SENSE_HAT_ENABLED = os.getenv("SENSE_HAT_ENABLED",       "true").strip().lower() == "true"
TEMP_OFFSET       = float(os.getenv("SENSE_HAT_TEMP_OFFSET", "2.0"))
NODE_NAME         = os.getenv("NODE_NAME",               "edge-node-1")
SQLITE_DB_PATH    = os.getenv("SQLITE_DB_PATH",          "/tmp/zedd_buffer.db")
LOG_LEVEL         = os.getenv("LOG_LEVEL",               "INFO").upper()
LIVENESS_FILE     = pathlib.Path("/tmp/zedd-alive")

# Physical sanity bounds (flag readings outside these ranges as anomalies)
TEMP_MIN_C        = -50.0
TEMP_MAX_C        =  85.0
HUMIDITY_MIN      =   0.0
HUMIDITY_MAX      = 100.0
PRESSURE_MIN_HPA  = 870.0   # record low ~870 hPa
PRESSURE_MAX_HPA  = 1085.0  # record high ~1085 hPa

# Statistical anomaly detection – Z-score window
ZSCORE_WINDOW     = 20      # number of recent readings to keep
ZSCORE_THRESHOLD  = 4.0     # flag if > 4 standard deviations from the mean

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("zedd.edge")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TelemetryReading:
    timestamp: datetime
    temperature_c: float
    humidity_pct: float
    pressure_hpa: float
    anomaly: bool = False
    anomaly_reason: str = ""

    def to_influx_point(self, node_name: str) -> "Point":
        """Convert to an InfluxDB Point for the write API."""
        return (
            Point("environment")
            .tag("node", node_name)
            .field("temperature_c",  self.temperature_c)
            .field("humidity_pct",   self.humidity_pct)
            .field("pressure_hpa",   self.pressure_hpa)
            .field("anomaly",        int(self.anomaly))
            .time(self.timestamp, WritePrecision.S)
        )

# ---------------------------------------------------------------------------
# SQLite offline buffer
# ---------------------------------------------------------------------------

def _init_db(path: str) -> sqlite3.Connection:
    """Create or open the SQLite buffer database."""
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS buffer (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          INTEGER NOT NULL,
            temperature REAL    NOT NULL,
            humidity    REAL    NOT NULL,
            pressure    REAL    NOT NULL,
            anomaly     INTEGER NOT NULL DEFAULT 0,
            reason      TEXT    NOT NULL DEFAULT ''
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON buffer(ts)")
    conn.commit()
    return conn


@contextmanager
def _db_cursor(conn: sqlite3.Connection) -> Generator[sqlite3.Cursor, None, None]:
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def buffer_reading(conn: sqlite3.Connection, reading: TelemetryReading) -> None:
    """Insert a reading into the local SQLite buffer."""
    with _db_cursor(conn) as cur:
        cur.execute(
            "INSERT INTO buffer (ts, temperature, humidity, pressure, anomaly, reason) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                int(reading.timestamp.timestamp()),
                reading.temperature_c,
                reading.humidity_pct,
                reading.pressure_hpa,
                int(reading.anomaly),
                reading.anomaly_reason,
            ),
        )
    log.debug("Buffered reading to SQLite (ts=%s)", reading.timestamp.isoformat())


def flush_buffer(
    conn: sqlite3.Connection,
    write_api: WriteApi,
    node_name: str,
) -> int:
    """
    Attempt to flush all buffered readings to InfluxDB.
    Returns the number of rows successfully flushed.
    """
    with _db_cursor(conn) as cur:
        cur.execute(
            "SELECT id, ts, temperature, humidity, pressure, anomaly, reason "
            "FROM buffer ORDER BY ts ASC"
        )
        rows = cur.fetchall()

    if not rows:
        return 0

    points = []
    ids    = []
    for row_id, ts, temp, hum, pres, anom, reason in rows:
        reading = TelemetryReading(
            timestamp     = datetime.fromtimestamp(ts, tz=timezone.utc),
            temperature_c = temp,
            humidity_pct  = hum,
            pressure_hpa  = pres,
            anomaly       = bool(anom),
            anomaly_reason= reason,
        )
        points.append(reading.to_influx_point(node_name))
        ids.append(row_id)

    write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=points)

    # Delete flushed rows
    with _db_cursor(conn) as cur:
        cur.executemany("DELETE FROM buffer WHERE id = ?", [(i,) for i in ids])

    log.info("Flushed %d buffered readings to InfluxDB", len(ids))
    return len(ids)

# ---------------------------------------------------------------------------
# Sensor reading
# ---------------------------------------------------------------------------

class SenseHatReader:
    """Thin wrapper around the Sense HAT library."""

    def __init__(self, temp_offset: float = 2.0) -> None:
        if not _SENSE_HAT_AVAILABLE:
            raise RuntimeError(
                "sense_hat package is not installed. "
                "Set SENSE_HAT_ENABLED=false to use the simulator instead."
            )
        self._hat = SenseHat()
        self._hat.set_imu_config(False, False, False)  # disable IMU to save power
        self._offset = temp_offset
        log.info("Sense HAT initialised (temp_offset=%.1f°C)", temp_offset)

    def read(self) -> TelemetryReading:
        temp     = self._hat.get_temperature() - self._offset
        humidity = self._hat.get_humidity()
        pressure = self._hat.get_pressure()
        return TelemetryReading(
            timestamp     = datetime.now(tz=timezone.utc),
            temperature_c = round(temp,     2),
            humidity_pct  = round(humidity, 2),
            pressure_hpa  = round(pressure, 2),
        )


class SimulatedReader:
    """
    Deterministic fake sensor for development / CI environments without
    physical hardware.  Values slowly oscillate around typical conditions.
    """

    def __init__(self) -> None:
        log.warning(
            "SENSE_HAT_ENABLED is false or hardware unavailable – "
            "using simulated sensor data."
        )
        self._t = 0

    def read(self) -> TelemetryReading:
        self._t += 1
        temp     = 20.0 + 5.0 * math.sin(self._t / 10.0)
        humidity = 55.0 + 10.0 * math.cos(self._t / 15.0)
        pressure = 1013.25 + 3.0 * math.sin(self._t / 20.0)
        return TelemetryReading(
            timestamp     = datetime.now(tz=timezone.utc),
            temperature_c = round(temp,     2),
            humidity_pct  = round(humidity, 2),
            pressure_hpa  = round(pressure, 2),
        )

# ---------------------------------------------------------------------------
# Validation & anomaly detection
# ---------------------------------------------------------------------------

class AnomalyDetector:
    """
    Two-stage anomaly detection:
      1. Physical bounds check (impossible values).
      2. Statistical Z-score check against a rolling window.
    """

    def __init__(self, window: int = ZSCORE_WINDOW, threshold: float = ZSCORE_THRESHOLD) -> None:
        self._window    = window
        self._threshold = threshold
        self._temps:     List[float] = []
        self._humidities: List[float] = []
        self._pressures: List[float] = []

    def _update_window(self, lst: List[float], value: float) -> None:
        lst.append(value)
        if len(lst) > self._window:
            lst.pop(0)

    @staticmethod
    def _zscore(value: float, history: List[float]) -> Optional[float]:
        if len(history) < 5:
            return None
        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        std = math.sqrt(variance)
        if std < 1e-9:
            return 0.0
        return abs(value - mean) / std

    def validate(self, reading: TelemetryReading) -> TelemetryReading:
        reasons: List[str] = []

        # --- Physical bounds ---
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
                f"pressure {reading.pressure_hpa} hPa out of range "
                f"[{PRESSURE_MIN_HPA}, {PRESSURE_MAX_HPA}]"
            )

        # --- Statistical Z-score ---
        for value, history, name in (
            (reading.temperature_c, self._temps,      "temp"),
            (reading.humidity_pct,  self._humidities, "humidity"),
            (reading.pressure_hpa,  self._pressures,  "pressure"),
        ):
            z = self._zscore(value, history)
            if z is not None and z > self._threshold:
                reasons.append(f"{name} Z-score={z:.1f} > {self._threshold}")

        # Update rolling windows with the raw (possibly anomalous) value
        self._update_window(self._temps,      reading.temperature_c)
        self._update_window(self._humidities, reading.humidity_pct)
        self._update_window(self._pressures,  reading.pressure_hpa)

        if reasons:
            reading.anomaly        = True
            reading.anomaly_reason = "; ".join(reasons)
            log.warning("Anomaly detected: %s", reading.anomaly_reason)
        return reading

# ---------------------------------------------------------------------------
# InfluxDB client helpers
# ---------------------------------------------------------------------------

def _build_write_api():
    """Return a synchronous InfluxDB write API client."""
    if not _INFLUXDB_AVAILABLE:
        raise RuntimeError(
            "influxdb-client package is not installed. "
            "Install it with: pip install influxdb-client"
        )
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    return client, client.write_api(write_options=SYNCHRONOUS)

# ---------------------------------------------------------------------------
# Liveness probe
# ---------------------------------------------------------------------------

def touch_liveness() -> None:
    """Touch /tmp/zedd-alive so the K3s liveness probe knows we're healthy."""
    try:
        LIVENESS_FILE.touch()
    except OSError as exc:
        log.debug("Could not touch liveness file: %s", exc)

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def _write_with_retry(
    reading: TelemetryReading,
    write_api: WriteApi,
    db_conn: sqlite3.Connection,
    node_name: str,
    consecutive_failures: int,
    max_failures: int,
) -> tuple[int, WriteApi]:
    """
    Attempt to write a single reading to InfluxDB.
    On failure: buffer locally and potentially reconnect.
    Returns (updated_failure_count, write_api).
    """
    try:
        try:
            flush_buffer(db_conn, write_api, node_name)
        except Exception as flush_exc:
            log.debug("Buffer flush failed: %s", flush_exc)

        write_api.write(
            bucket=INFLUXDB_BUCKET,
            org=INFLUXDB_ORG,
            record=reading.to_influx_point(node_name),
        )
        log.info(
            "Written: temp=%.2f°C  humidity=%.2f%%  pressure=%.2f hPa%s",
            reading.temperature_c,
            reading.humidity_pct,
            reading.pressure_hpa,
            "  [ANOMALY]" if reading.anomaly else "",
        )
        return 0, write_api

    except Exception as write_exc:
        consecutive_failures += 1
        log.warning(
            "InfluxDB write failed (%d/%d): %s",
            consecutive_failures, max_failures, write_exc,
        )
        buffer_reading(db_conn, reading)

        if consecutive_failures >= max_failures:
            log.error("Too many consecutive failures – attempting to reconnect")
            try:
                _, write_api = _build_write_api()
                consecutive_failures = 0
                log.info("Reconnected to InfluxDB")
            except Exception as reconnect_exc:
                log.error("Reconnect failed: %s", reconnect_exc)

        return consecutive_failures, write_api


def run() -> None:
    log.info(
        "Zedd-Weather edge collector starting (node=%s, interval=%.1fs)",
        NODE_NAME, PUBLISH_INTERVAL,
    )

    # --- Initialise sensor ---
    if SENSE_HAT_ENABLED and _SENSE_HAT_AVAILABLE:
        reader: SenseHatReader | SimulatedReader = SenseHatReader(TEMP_OFFSET)
    else:
        reader = SimulatedReader()

    # --- Initialise SQLite buffer ---
    db_conn = _init_db(SQLITE_DB_PATH)
    log.info("SQLite buffer at %s", SQLITE_DB_PATH)

    # --- Initialise InfluxDB client ---
    influx_client = None
    write_api     = None
    if _INFLUXDB_AVAILABLE and INFLUXDB_TOKEN:
        try:
            influx_client, write_api = _build_write_api()
            log.info("Connected to InfluxDB at %s", INFLUXDB_URL)
        except Exception as exc:
            log.warning("Initial InfluxDB connection failed: %s", exc)
    else:
        log.warning(
            "InfluxDB client unavailable (package installed: %s, token set: %s). "
            "All data will be buffered locally.",
            _INFLUXDB_AVAILABLE, bool(INFLUXDB_TOKEN),
        )

    # --- Anomaly detector ---
    detector = AnomalyDetector()

    consecutive_failures = 0
    MAX_FAILURES         = 5

    while True:
        cycle_start = time.monotonic()

        try:
            reading = reader.read()
            log.debug(
                "Read: temp=%.2f°C  humidity=%.2f%%  pressure=%.2f hPa",
                reading.temperature_c, reading.humidity_pct, reading.pressure_hpa,
            )

            reading = detector.validate(reading)

            if write_api is not None:
                consecutive_failures, write_api = _write_with_retry(
                    reading, write_api, db_conn, NODE_NAME,
                    consecutive_failures, MAX_FAILURES,
                )
            else:
                buffer_reading(db_conn, reading)

            touch_liveness()

        except KeyboardInterrupt:
            log.info("Interrupted – shutting down")
            break
        except Exception as exc:
            log.exception("Unexpected error in main loop: %s", exc)

        elapsed  = time.monotonic() - cycle_start
        time.sleep(max(0.0, PUBLISH_INTERVAL - elapsed))

    # Graceful shutdown
    log.info("Closing resources…")
    if influx_client:
        try:
            influx_client.close()
        except Exception:
            pass
    db_conn.close()
    log.info("Edge collector stopped")


if __name__ == "__main__":
    run()
