"""
Hailo-8L NPU inference client for the Raspberry Pi AI HAT+.

Provides on-device weather-pattern classification and anomaly scoring
without cloud connectivity.  Falls back to the existing OllamaClient
(remote LLM) or Gemini API when the NPU is unavailable.

The client loads a pre-compiled HEF (Hailo Executable Format) model at
startup and keeps it resident on the NPU for low-latency inference.
"""
import json
import logging
import os
from typing import Optional

from Zweather.node1_telemetry import config

logger = logging.getLogger(__name__)


class HailoNPUClient:
    """
    On-device inference client backed by the Hailo-8L NPU.

    If the Hailo runtime (``hailo_platform``) is not importable (e.g. CI
    or non-Pi hosts) the client falls back to the ``OllamaClient``.
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self._model_path = model_path or config.AI_HAT_MODEL_PATH
        self._hef = None
        self._device = None
        self._available = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def initialize(self) -> bool:
        """Load the HEF model onto the NPU.  Returns *True* on success."""
        if not config.AI_HAT_ENABLED:
            logger.info("AI HAT NPU inference disabled in configuration.")
            return False

        try:
            from hailo_platform import (  # type: ignore[import-untyped]
                HEF,
                HailoRTDevice,
                ConfigureParams,
            )

            self._device = HailoRTDevice()

            if os.path.isfile(self._model_path):
                self._hef = HEF(self._model_path)
                assert self._device is not None
                params = self._device.create_configure_params(self._hef)
                self._device.configure(self._hef, params)
                logger.info(
                    "Hailo NPU model loaded from %s", self._model_path
                )
            else:
                logger.warning(
                    "HEF model file not found at %s — NPU available but "
                    "no model loaded.  Raw diagnostics only.",
                    self._model_path,
                )

            self._available = True
            return True

        except (ImportError, OSError, RuntimeError) as exc:
            logger.warning("Hailo NPU unavailable (%s). Using fallback.", exc)
            self._available = False
            return False

    @property
    def is_available(self) -> bool:
        return self._available

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def classify_weather(self, telemetry: dict) -> dict:
        """
        Run a lightweight weather-classification inference on the NPU.

        Parameters
        ----------
        telemetry : dict
            Current sensor readings (temperature, humidity, pressure, etc.).

        Returns
        -------
        dict with ``label``, ``confidence``, and ``source`` keys.
        """
        if not self._available or self._hef is None:
            return self._classify_heuristic(telemetry)

        try:
            import numpy as np  # type: ignore[import-untyped]

            # Build a feature vector from available telemetry
            features = np.array(
                [
                    telemetry.get("temperature_c", 20.0),
                    telemetry.get("humidity_pct", 50.0),
                    telemetry.get("pressure_hpa", 1013.25),
                ],
                dtype=np.float32,
            ).reshape(1, -1)

            # Run synchronous inference on the NPU
            input_vstreams = self._device.create_input_vstreams(self._hef)
            output_vstreams = self._device.create_output_vstreams(self._hef)

            input_vstreams[0].send(features)
            result = output_vstreams[0].recv()

            label_idx = int(np.argmax(result))
            labels = ["clear", "cloudy", "rain", "storm", "fog", "snow"]
            label = labels[label_idx] if label_idx < len(labels) else "unknown"
            confidence = round(float(np.max(result)), 3)

            return {
                "label": label,
                "confidence": confidence,
                "source": "hailo_npu",
            }

        except Exception as exc:
            logger.error("NPU inference failed: %s — falling back to heuristic", exc)
            return self._classify_heuristic(telemetry)

    @staticmethod
    def _classify_heuristic(telemetry: dict) -> dict:
        """Deterministic rule-based fallback when the NPU is unavailable."""
        temp = telemetry.get("temperature_c", 20.0)
        humidity = telemetry.get("humidity_pct", 50.0)
        pressure = telemetry.get("pressure_hpa", 1013.25)

        if pressure < 1000 and humidity > 80:
            label = "storm"
        elif temp < 0 and humidity > 60:
            label = "snow"
        elif humidity > 85:
            label = "rain"
        elif humidity > 70 and temp < 5:
            label = "fog"
        elif humidity < 40:
            label = "clear"
        else:
            label = "cloudy"

        return {"label": label, "confidence": 0.0, "source": "heuristic"}

    def generate_mitigation(self, telemetry: dict, forecast: Optional[dict] = None) -> str:
        """
        Generate an edge mitigation summary using NPU classification.

        Falls back to the OllamaClient for full natural-language generation
        when the NPU is not available.
        """
        classification = self.classify_weather(telemetry)

        if classification["source"] == "hailo_npu":
            # Structured edge response — no LLM needed
            label = classification["label"]
            conf = classification["confidence"]
            temp = telemetry.get("temperature_c", "N/A")
            return (
                f"[Edge NPU] Weather: {label} (confidence {conf:.1%}). "
                f"Temp: {temp}°C. "
                f"Action: {'Monitor closely' if label in ('storm', 'rain', 'snow') else 'Normal operations'}."
            )

        # Fallback to OllamaClient
        try:
            from Zweather.ollama_inference.client import OllamaClient
            client = OllamaClient()
            return client.generate_mitigation(telemetry, forecast)
        except Exception as exc:
            logger.error("Fallback inference also failed: %s", exc)
            return f"Edge inference unavailable: {exc}"

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def cleanup(self) -> None:
        if self._device is not None:
            try:
                self._device.release()
            except Exception:
                pass
