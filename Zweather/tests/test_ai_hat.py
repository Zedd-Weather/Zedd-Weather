"""Tests for the AI HAT (Hailo-8L NPU) driver and inference client."""
import os
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# AI HAT Driver (sensor)
# ---------------------------------------------------------------------------

class TestAIHatDriver:
    """Tests for Zweather.node1_telemetry.sensors.ai_hat_driver.AIHatDriver."""

    def test_disabled_returns_empty(self):
        """When AI_HAT_ENABLED is false the driver should return no readings."""
        with patch.dict(os.environ, {"AI_HAT_ENABLED": "false"}):
            # Re-import so the config toggle takes effect
            import importlib
            import Zweather.node1_telemetry.config as cfg
            importlib.reload(cfg)

            from Zweather.node1_telemetry.sensors.ai_hat_driver import AIHatDriver
            driver = AIHatDriver()
            driver.initialize()
            assert driver.read() == {}

    def test_mock_mode_returns_expected_keys(self):
        """When hailo_platform is absent, enabled driver returns mock data."""
        with patch.dict(os.environ, {"AI_HAT_ENABLED": "true"}):
            import importlib
            import Zweather.node1_telemetry.config as cfg
            importlib.reload(cfg)

            from Zweather.node1_telemetry.sensors.ai_hat_driver import AIHatDriver
            driver = AIHatDriver()
            driver.initialize()

            data = driver.read()
            assert "ai_hat_available" in data
            assert "ai_hat_status" in data
            assert "npu_temp_c" in data
            assert "npu_power_w" in data
            assert data["ai_hat_status"] == "standby"

    def test_cleanup_no_error_when_unavailable(self):
        """cleanup() should not raise even when no hardware is present."""
        with patch.dict(os.environ, {"AI_HAT_ENABLED": "true"}):
            import importlib
            import Zweather.node1_telemetry.config as cfg
            importlib.reload(cfg)

            from Zweather.node1_telemetry.sensors.ai_hat_driver import AIHatDriver
            driver = AIHatDriver()
            driver.initialize()
            driver.cleanup()  # should not raise


# ---------------------------------------------------------------------------
# Hailo NPU Inference Client
# ---------------------------------------------------------------------------

class TestHailoNPUClient:
    """Tests for Zweather.ollama_inference.hailo_npu.HailoNPUClient."""

    def test_heuristic_fallback_storm(self):
        """Heuristic classifier should detect storm conditions."""
        from Zweather.ollama_inference.hailo_npu import HailoNPUClient
        client = HailoNPUClient()
        result = client.classify_weather({
            "temperature_c": 15.0,
            "humidity_pct": 95.0,
            "pressure_hpa": 990.0,
        })
        assert result["label"] == "storm"
        assert result["source"] == "heuristic"

    def test_heuristic_fallback_clear(self):
        """Heuristic classifier should detect clear conditions."""
        from Zweather.ollama_inference.hailo_npu import HailoNPUClient
        client = HailoNPUClient()
        result = client.classify_weather({
            "temperature_c": 25.0,
            "humidity_pct": 30.0,
            "pressure_hpa": 1020.0,
        })
        assert result["label"] == "clear"
        assert result["source"] == "heuristic"

    def test_heuristic_fallback_rain(self):
        """Heuristic classifier should detect rain conditions."""
        from Zweather.ollama_inference.hailo_npu import HailoNPUClient
        client = HailoNPUClient()
        result = client.classify_weather({
            "temperature_c": 18.0,
            "humidity_pct": 90.0,
            "pressure_hpa": 1005.0,
        })
        assert result["label"] == "rain"
        assert result["source"] == "heuristic"

    def test_heuristic_fallback_fog(self):
        """Heuristic classifier should detect fog conditions."""
        from Zweather.ollama_inference.hailo_npu import HailoNPUClient
        client = HailoNPUClient()
        result = client.classify_weather({
            "temperature_c": 3.0,
            "humidity_pct": 75.0,
            "pressure_hpa": 1013.0,
        })
        assert result["label"] == "fog"
        assert result["source"] == "heuristic"

    def test_heuristic_fallback_snow(self):
        """Heuristic classifier should detect snow conditions."""
        from Zweather.ollama_inference.hailo_npu import HailoNPUClient
        client = HailoNPUClient()
        result = client.classify_weather({
            "temperature_c": -5.0,
            "humidity_pct": 80.0,
            "pressure_hpa": 1010.0,
        })
        assert result["label"] == "snow"
        assert result["source"] == "heuristic"

    def test_initialize_returns_false_without_hardware(self):
        """initialize() should return False when hailo_platform is absent."""
        with patch.dict(os.environ, {"AI_HAT_ENABLED": "true"}):
            import importlib
            import Zweather.node1_telemetry.config as cfg
            importlib.reload(cfg)

            from Zweather.ollama_inference.hailo_npu import HailoNPUClient
            client = HailoNPUClient()
            assert client.initialize() is False
            assert client.is_available is False

    def test_generate_mitigation_without_npu(self):
        """generate_mitigation should return a string even without NPU."""
        from Zweather.ollama_inference.hailo_npu import HailoNPUClient
        client = HailoNPUClient()
        result = client.generate_mitigation({
            "temperature_c": 25.0,
            "humidity_pct": 50.0,
            "pressure_hpa": 1013.0,
        })
        assert isinstance(result, str)
        assert len(result) > 0
