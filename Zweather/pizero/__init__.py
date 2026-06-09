"""
Zedd Weather — Raspberry Pi Zero 2WH Variant
=============================================

Hardware profile:
  - BCRobotics Weather HAT PRO – primary environmental + wind/rain station
  - Google Coral USB Accelerator – on-device edge inference (Edge TPU)
  - WiFi network – no Ethernet, no SSD, no NVMe

Packages:
  - :mod:`~Zweather.pizero.config` — Pi Zero specific configuration
  - :mod:`~Zweather.pizero.coral_tpu_driver` — Coral USB Accelerator hardware driver
  - :mod:`~Zweather.pizero.coral_npu_client` — Coral inference client
"""

from Zweather.pizero.config import (
    CORAL_ENABLED,
    CORAL_DEVICE_ID,
    CORAL_MODEL_PATH,
    CORAL_LABELS_PATH,
    IS_PI_ZERO_2W,
)

__all__ = [
    "CORAL_ENABLED",
    "CORAL_DEVICE_ID",
    "CORAL_MODEL_PATH",
    "CORAL_LABELS_PATH",
    "IS_PI_ZERO_2W",
]
