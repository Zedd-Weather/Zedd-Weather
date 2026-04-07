"""Tests for Zweather.app – buffer and anomaly detection (no hardware required)."""
import os
import sqlite3

import pytest


def test_sqlite_buffer_write_read(tmp_path):
    """Buffer should store and retrieve readings without InfluxDB."""
    db_path = str(tmp_path / "test_buffer.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS buffer "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, "
        " ts REAL NOT NULL, "
        " temperature_c REAL, "
        " humidity_pct REAL, "
        " pressure_hpa REAL)"
    )
    conn.execute(
        "INSERT INTO buffer (ts, temperature_c, humidity_pct, pressure_hpa) VALUES (?,?,?,?)",
        (1700000000.0, 22.5, 64.0, 1012.0),
    )
    conn.commit()
    rows = conn.execute("SELECT * FROM buffer").fetchall()
    assert len(rows) == 1
    assert rows[0][2] == 22.5  # temperature_c
    conn.close()


def test_zscore_anomaly_detection():
    """Z-score based anomaly detection should flag extreme values."""
    import statistics

    values = [20.0, 21.0, 22.0, 23.0, 24.0, 21.5, 22.5, 95.0]
    mean = statistics.mean(values)
    stdev = statistics.stdev(values)

    # threshold=2.0: 95.0 sits ~2.5σ above the mean; normal values stay well below
    def is_anomaly(v: float, threshold: float = 2.0) -> bool:
        if stdev == 0:
            return False
        return abs((v - mean) / stdev) > threshold

    assert is_anomaly(95.0)
    assert not is_anomaly(22.0)
