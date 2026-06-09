"""
Google Coral USB Accelerator inference client for Raspberry Pi Zero 2WH.

Replaces the Hailo-8L NPU inference client for the Pi Zero variant.

Provides on-device weather-pattern classification and anomaly scoring
without cloud connectivity. The client loads a TensorFlow Lite model
at startup and runs inference on the Edge TPU.

Falls back to a deterministic heuristic when the Coral is unavailable.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from Zweather.pizero import config as pz_config

logger = logging.getLogger(__name__)

_DEFAULT_LABELS = ["clear", "cloudy", "rain", "storm", "fog", "snow"]


class CoralNPUClient:
    """
    On-device inference client backed by the Google Coral Edge TPU.

    If ``pycoral`` / ``tflite-runtime`` is not importable the client
    falls back to a deterministic heuristic.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        labels_path: Optional[str] = None,
    ) -> None:
        self._model_path = model_path or pz_config.CORAL_MODEL_PATH
        self._labels_path = labels_path or pz_config.CORAL_LABELS_PATH
        self._interpreter = None
        self._labels: list[str] = list(_DEFAULT_LABELS)
        self._available = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> bool:
        """Load the TFLite model onto the Edge TPU.  Returns *True* on success."""
        if not pz_config.CORAL_ENABLED:
            logger.info("Coral TPU disabled in configuration.")
            return False

        try:
            from pycoral.utils.edgetpu import make_interpreter

            if not os.path.isfile(self._model_path):
                logger.warning(
                    "Coral model file not found at %s — TPU available but "
                    "no model loaded.  Raw diagnostics only.",
                    self._model_path,
                )
                self._available = True  # hardware is available
                return True

            self._interpreter = make_interpreter(self._model_path)
            assert self._interpreter is not None
            self._interpreter.allocate_tensors()

            if os.path.isfile(self._labels_path):
                with open(self._labels_path) as f:
                    self._labels = [line.strip() for line in f if line.strip()]
            else:
                self._labels = list(_DEFAULT_LABELS)

            self._available = True
            logger.info("Coral NPU model loaded from %s", self._model_path)
            return True

        except (ImportError, OSError, RuntimeError) as exc:
            logger.warning("Coral TPU unavailable (%s). Using fallback.", exc)
            self._available = False
            return False

    @property
    def is_available(self) -> bool:
        return self._available

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def classify_weather(self, telemetry: dict) -> dict[str, Any]:
        """
        Run a lightweight weather-classification inference on the Edge TPU.

        Parameters
        ----------
        telemetry : dict
            Current sensor readings (temperature, humidity, pressure, etc.).

        Returns
        -------
        dict with ``label``, ``confidence``, and ``source`` keys.
        """
        if not self._available or self._interpreter is None:
            return self._classify_heuristic(telemetry)

        try:
            import numpy as np

            temp = float(telemetry.get("temperature_c", telemetry.get("temperature", 20.0)))
            humidity = float(telemetry.get("humidity_pct", telemetry.get("humidity", 50.0)))
            pressure = float(telemetry.get("pressure_hpa", telemetry.get("pressure", 1013.25)))

            input_details = self._interpreter.get_input_details()
            output_details = self._interpreter.get_output_details()

            features = np.array([[temp, humidity, pressure]], dtype=np.float32)

            self._interpreter.set_tensor(input_details[0]["index"], features)
            self._interpreter.invoke()
            result = self._interpreter.get_tensor(output_details[0]["index"])

            label_idx = int(np.argmax(result))
            label = (
                self._labels[label_idx]
                if 0 <= label_idx < len(self._labels)
                else "unknown"
            )
            confidence = round(float(np.max(result)), 3)

            return {
                "label": label,
                "confidence": confidence,
                "source": "coral_tpu",
            }

        except (OSError, RuntimeError, ValueError) as exc:
            logger.error("Coral inference failed: %s — fallback", exc)
            return self._classify_heuristic(telemetry)

    @staticmethod
    def _classify_heuristic(telemetry: dict) -> dict[str, Any]:
        """Deterministic rule-based fallback when the Edge TPU is unavailable."""
        temp = float(telemetry.get("temperature_c", telemetry.get("temperature", 20.0)))
        humidity = float(telemetry.get("humidity_pct", telemetry.get("humidity", 50.0)))
        pressure = float(telemetry.get("pressure_hpa", telemetry.get("pressure", 1013.25)))

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

    def generate_mitigation(
        self, telemetry: dict, forecast: Optional[dict] = None
    ) -> str:
        """
        Generate an edge mitigation summary using Coral classification.

        Falls back to heuristic when the Edge TPU is not available.
        """
        classification = self.classify_weather(telemetry)

        if classification["source"] == "coral_tpu":
            label = classification["label"]
            try:
                raw_conf = float(classification.get("confidence", 0.0))
            except (TypeError, ValueError):
                raw_conf = 0.0
            conf = max(0.0, min(1.0, raw_conf))
            temp = telemetry.get("temperature_c", telemetry.get("temperature", "N/A"))
            return (
                f"[Edge TPU] Weather: {label} (confidence {conf:.1%}). "
                f"Temp: {temp}°C. "
                f"Action: {'Monitor closely' if label in ('storm', 'rain', 'snow') else 'Normal operations'}."
            )

        # Fallback to heuristic
        return (
            f"[Heuristic] Classification: {classification['label']}. "
            f"No Edge TPU available."
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        if self._interpreter is not None:
            try:
                del self._interpreter
            except Exception:
                logger.debug("Coral NPU cleanup failed", exc_info=True)
            self._interpreter = None
            self._available = False
