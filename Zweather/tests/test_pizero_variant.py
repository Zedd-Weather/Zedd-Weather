"""
Tests for the Zedd Weather Raspberry Pi Zero 2WH variant.

Covers Coral TPU driver, Coral NPU client, and Pi Zero configuration.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from Zweather.pizero import config as pz_config


# =========================================================================
# Configuration tests
# =========================================================================

class TestPiZeroConfig:
    def test_default_coral_enabled(self):
        assert pz_config.CORAL_ENABLED is True

    def test_default_weather_hat_enabled(self):
        assert pz_config.WEATHER_HAT_PRO_ENABLED is True

    def test_sense_hat_disabled(self):
        assert pz_config.SENSE_HAT_ENABLED is False

    def test_ai_hat_disabled(self):
        assert pz_config.AI_HAT_ENABLED is False

    def test_enviro_plus_disabled(self):
        assert pz_config.ENVIRO_PLUS_ENABLED is False

    def test_m2_nvme_disabled(self):
        assert pz_config.M2_NVME_ENABLED is False

    def test_modbus_disabled(self):
        assert pz_config.MODBUS_ENABLED is False

    def test_sqlite_db_path_default_tmp(self):
        assert pz_config.SQLITE_DB_PATH == "/tmp/zedd_buffer.db"

    def test_buffer_flush_interval(self):
        assert pz_config.BUFFER_FLUSH_INTERVAL == 300

    def test_publish_interval(self):
        assert pz_config.PUBLISH_INTERVAL == 5.0

    @patch.dict(os.environ, {"CORAL_ENABLED": "false"})
    def test_coral_disabled_via_env(self):
        # Re-import triggers re-read of env
        import importlib
        import Zweather.pizero.config as cfg
        importlib.reload(cfg)
        assert cfg.CORAL_ENABLED is False
        importlib.reload(pz_config)  # restore


# =========================================================================
# CoralTPUDriver tests
# =========================================================================

class TestCoralTPUDriver:
    @patch.dict(os.environ, {"CORAL_ENABLED": "false"})
    def test_initialize_skipped_when_disabled(self):
        from Zweather.pizero.coral_tpu_driver import CoralTPUDriver

        driver = CoralTPUDriver()
        driver.initialize()
        assert driver.available is False
        driver.cleanup()

    def test_initialize_without_pycoral(self):
        from Zweather.pizero.coral_tpu_driver import CoralTPUDriver

        driver = CoralTPUDriver(model_path="/nonexistent/model.tflite")
        driver.initialize()
        # Without pycoral installed, it gracefully reports unavailable
        assert driver.available is False
        driver.cleanup()

    def test_read_unavailable(self):
        from Zweather.pizero.coral_tpu_driver import CoralTPUDriver

        driver = CoralTPUDriver()
        driver._available = False
        readings = driver.read()
        assert readings["coral_available"] is False
        assert readings["coral_status"] == "unavailable"

    def test_classify_fallback_heuristic_storm(self):
        from Zweather.pizero.coral_tpu_driver import CoralTPUDriver

        driver = CoralTPUDriver()
        result = driver.classify({"temperature_c": 20.0, "humidity_pct": 90.0, "pressure_hpa": 990.0})
        assert result["label"] == "storm"
        assert result["source"] == "heuristic"

    def test_classify_fallback_heuristic_snow(self):
        from Zweather.pizero.coral_tpu_driver import CoralTPUDriver

        driver = CoralTPUDriver()
        result = driver.classify({"temperature_c": -5.0, "humidity_pct": 70.0, "pressure_hpa": 1020.0})
        assert result["label"] == "snow"
        assert result["source"] == "heuristic"

    def test_classify_fallback_heuristic_rain(self):
        from Zweather.pizero.coral_tpu_driver import CoralTPUDriver

        driver = CoralTPUDriver()
        result = driver.classify({"temperature_c": 15.0, "humidity_pct": 90.0, "pressure_hpa": 1010.0})
        assert result["label"] == "rain"
        assert result["source"] == "heuristic"

    def test_classify_fallback_heuristic_fog(self):
        from Zweather.pizero.coral_tpu_driver import CoralTPUDriver

        driver = CoralTPUDriver()
        result = driver.classify({"temperature_c": 2.0, "humidity_pct": 75.0, "pressure_hpa": 1025.0})
        assert result["label"] == "fog"
        assert result["source"] == "heuristic"

    def test_classify_fallback_heuristic_clear(self):
        from Zweather.pizero.coral_tpu_driver import CoralTPUDriver

        driver = CoralTPUDriver()
        result = driver.classify({"temperature_c": 25.0, "humidity_pct": 30.0, "pressure_hpa": 1020.0})
        assert result["label"] == "clear"
        assert result["source"] == "heuristic"

    def test_classify_fallback_heuristic_cloudy(self):
        from Zweather.pizero.coral_tpu_driver import CoralTPUDriver

        driver = CoralTPUDriver()
        result = driver.classify({"temperature_c": 18.0, "humidity_pct": 55.0, "pressure_hpa": 1015.0})
        assert result["label"] == "cloudy"
        assert result["source"] == "heuristic"

    def test_classify_with_empty_telemetry(self):
        from Zweather.pizero.coral_tpu_driver import CoralTPUDriver

        driver = CoralTPUDriver()
        result = driver.classify({})
        # Defaults: temp=20, humidity=50, pressure=1013.25 -> cloudy
        assert result["label"] in ("cloudy", "clear")
        assert result["source"] == "heuristic"


# =========================================================================
# CoralNPUClient tests
# =========================================================================

class TestCoralNPUClient:
    @patch.dict(os.environ, {"CORAL_ENABLED": "false"})
    def test_initialize_disabled(self):
        from Zweather.pizero.coral_npu_client import CoralNPUClient

        client = CoralNPUClient()
        result = client.initialize()
        assert result is False
        assert client.is_available is False
        client.cleanup()

    def test_initialize_without_pycoral(self):
        from Zweather.pizero.coral_npu_client import CoralNPUClient

        client = CoralNPUClient(model_path="/nonexistent/model.tflite")
        result = client.initialize()
        # Without pycoral, init fails gracefully
        assert result is False
        client.cleanup()

    def test_classify_fallback_heuristic(self):
        from Zweather.pizero.coral_npu_client import CoralNPUClient

        client = CoralNPUClient()
        # Trigger fallback when not initialised
        result = client.classify_weather({"temperature_c": 20.0, "humidity_pct": 90.0, "pressure_hpa": 990.0})
        assert result["label"] == "storm"
        assert result["source"] == "heuristic"

    def test_generate_mitigation_fallback(self):
        from Zweather.pizero.coral_npu_client import CoralNPUClient

        client = CoralNPUClient()
        msg = client.generate_mitigation({"temperature_c": 30.0, "humidity_pct": 35.0, "pressure_hpa": 1018.0})
        assert "Heuristic" in msg or "Edge TPU" in msg

    def test_generate_mitigation_storm(self):
        from Zweather.pizero.coral_npu_client import CoralNPUClient

        client = CoralNPUClient()
        msg = client.generate_mitigation({"temperature_c": 20.0, "humidity_pct": 90.0, "pressure_hpa": 990.0})
        assert "storm" in msg

    def test_classify_fallback_all_defaults(self):
        from Zweather.pizero.coral_npu_client import CoralNPUClient

        client = CoralNPUClient()
        result = client.classify_weather({})
        assert result["source"] == "heuristic"


# =========================================================================
# Pi Zero app integration tests (no hardware)
# =========================================================================

class TestAppPiZero:
    def test_telemetry_reading_to_dict(self):
        from Zweather.app_pizero import TelemetryReading
        from datetime import datetime, timezone

        ts = datetime.now(tz=timezone.utc)
        reading = TelemetryReading(
            timestamp=ts,
            temperature_c=22.5,
            humidity_pct=60.0,
            pressure_hpa=1015.0,
            wind_speed_ms=5.2,
            wind_direction_deg=180.0,
            rain_mm=0.0,
        )
        d = reading.to_dict()
        assert d["temperature_c"] == 22.5
        assert d["humidity_pct"] == 60.0
        assert d["pressure_hpa"] == 1015.0
        assert d["wind_speed_ms"] == 5.2
        assert d["wind_direction_deg"] == 180.0
        assert d["node"] == "pizero-01"
        assert d["anomaly"] is False

    def test_anomaly_detector_physical_bounds(self):
        from Zweather.app_pizero import AnomalyDetector, TelemetryReading
        from datetime import datetime, timezone

        detector = AnomalyDetector()
        ts = datetime.now(tz=timezone.utc)

        # Out of bounds temp
        reading = TelemetryReading(timestamp=ts, temperature_c=200.0, humidity_pct=50.0, pressure_hpa=1013.0)
        validated = detector.validate(reading)
        assert validated.anomaly is True
        assert "temp" in validated.anomaly_reason

    def test_anomaly_detector_normal(self):
        from Zweather.app_pizero import AnomalyDetector, TelemetryReading
        from datetime import datetime, timezone

        detector = AnomalyDetector()
        ts = datetime.now(tz=timezone.utc)

        reading = TelemetryReading(timestamp=ts, temperature_c=20.0, humidity_pct=55.0, pressure_hpa=1015.0)
        validated = detector.validate(reading)
        assert validated.anomaly is False
        assert validated.anomaly_reason == ""

    def test_sqlite_buffer_roundtrip(self, tmp_path):
        from Zweather.app_pizero import _init_db, buffer_reading, pop_buffered, TelemetryReading
        from datetime import datetime, timezone

        db_path = str(tmp_path / "test_buffer.db")
        conn = _init_db(db_path)

        ts = datetime.now(tz=timezone.utc)
        reading = TelemetryReading(timestamp=ts, temperature_c=21.0, humidity_pct=50.0, pressure_hpa=1018.0)

        buffer_reading(conn, reading)
        records = pop_buffered(conn)
        assert len(records) == 1
        assert records[0]["temperature_c"] == 21.0
        assert records[0]["humidity_pct"] == 50.0

        # Should be empty after pop
        assert pop_buffered(conn) == []

        conn.close()

    def test_mqtt_publisher_disconnected(self):
        from Zweather.app_pizero import MQTTPublisher

        pub = MQTTPublisher()
        result = pub.publish({"test": "data"})
        assert result is False

    def test_coral_inference_engine_no_hardware(self):
        from Zweather.app_pizero import CoralInferenceEngine

        engine = CoralInferenceEngine()
        engine.initialize()
        result = engine.classify({"temperature_c": 20.0, "humidity_pct": 85.0, "pressure_hpa": 1005.0})
        assert "label" in result
        assert "source" in result
        engine.cleanup()

    @patch.dict(os.environ, {"MQTT_BROKER_HOST": "192.0.2.1"})
    def test_mqtt_publisher_connect_fails(self):
        from Zweather.app_pizero import MQTTPublisher

        pub = MQTTPublisher()
        result = pub.connect()
        # Connection to 192.0.2.1 should fail quickly
        assert result is False
