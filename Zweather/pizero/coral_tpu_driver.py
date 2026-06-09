"""
Google Coral USB Accelerator driver for Raspberry Pi Zero 2WH.

Provides on-device edge inference using the Coral Edge TPU connected via USB.
Replaces the Hailo-8L AI HAT+ driver for the Pi Zero variant.

When the Coral runtime (pycoral / tflite-runtime) is not installed, reports
``coral_available=False`` so the pipeline routes around it gracefully.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from Zweather.node1_telemetry.sensors.base import BaseSensor

logger = logging.getLogger(__name__)

# Pre-compiled labels for the weather classification model
_DEFAULT_LABELS = ["clear", "cloudy", "rain", "storm", "fog", "snow"]


class CoralTPUDriver(BaseSensor):
    """Driver for the Google Coral USB Accelerator (Edge TPU)."""

    def __init__(self, model_path: str = "", labels_path: str = "") -> None:
        super().__init__("coral_tpu")
        self._model_path = model_path or "/opt/zedd/models/weather_classify_edgetpu.tflite"
        self._labels_path = labels_path or "/opt/zedd/models/weather_labels.txt"
        self._interpreter = None
        self._labels: list[str] = list(_DEFAULT_LABELS)
        self._lock = threading.Lock()
        self._last_inference_temp = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        if not self._enabled():
            logger.info("Coral TPU disabled in configuration.")
            return

        try:
            import pycoral.adapters.common  # noqa: F401
            from pycoral.utils.edgetpu import make_interpreter

            if not os.path.isfile(self._model_path):
                logger.warning(
                    "Coral model not found at %s — TPU diagnostics only.",
                    self._model_path,
                )
                self._available = False
                return

            self._interpreter = make_interpreter(self._model_path)
            assert self._interpreter is not None
            self._interpreter.allocate_tensors()

            if os.path.isfile(self._labels_path):
                with open(self._labels_path) as f:
                    self._labels = [line.strip() for line in f if line.strip()]
            else:
                self._labels = list(_DEFAULT_LABELS)

            self._available = True
            logger.info(
                "Google Coral TPU initialised — model: %s",
                self._model_path,
            )

        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            logger.warning(
                "Coral TPU unavailable (%s). Reporting coral_available=False.",
                exc,
            )
            self._available = False

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read(self) -> dict[str, Any]:
        if not self._available:
            return self._status_unavailable()
        return self._read_hardware()

    def _read_hardware(self) -> dict[str, Any]:
        return {
            "coral_available": True,
            "coral_status": "active",
            "coral_model": os.path.basename(self._model_path),
        }

    @staticmethod
    def _status_unavailable() -> dict[str, Any]:
        return {
            "coral_available": False,
            "coral_status": "unavailable",
            "coral_model": "",
        }

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def classify(self, telemetry: dict) -> dict[str, Any]:
        """
        Run on-device classification via the Coral Edge TPU.

        Returns dict with ``label``, ``confidence``, and ``source`` keys.
        Falls back to a deterministic heuristic if the TPU is offline.
        """
        if not self._available or self._interpreter is None:
            return self._classify_heuristic(telemetry)

        with self._lock:
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
                output = self._interpreter.get_tensor(output_details[0]["index"])

                label_idx = int(np.argmax(output))
                label = self._labels[label_idx] if label_idx < len(self._labels) else "unknown"
                confidence = round(float(np.max(output)), 3)

                self._last_inference_temp = temp

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
        """Rule-based fallback when the Edge TPU is unavailable."""
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

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def interpreter(self):
        """Return the raw pycoral interpreter handle (or ``None``)."""
        return self._interpreter

    @property
    def model_path(self) -> str:
        return self._model_path

    @staticmethod
    def _enabled() -> bool:
        try:
            from Zweather.pizero import config as pz_config
            return pz_config.CORAL_ENABLED
        except ImportError:
            return os.getenv("CORAL_ENABLED", "true").lower() == "true"

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        with self._lock:
            if self._interpreter is not None:
                try:
                    del self._interpreter
                except Exception:
                    logger.debug("Coral cleanup issue", exc_info=True)
                self._interpreter = None
                self._available = False
