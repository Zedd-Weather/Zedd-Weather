"""
Zedd Weather — Pi Zero 2WH Configuration
==========================================
Hardware-specific configuration for the Raspberry Pi Zero 2WH variant.

Key differences from the standard build:
  - Google Coral USB Accelerator (Edge TPU) replaces Hailo-8L AI HAT+
  - No SSD / NVMe — all buffers use tmpfs (/tmp) to protect SD card
  - Control plane (orchestrator) runs remotely — Pi Zero is pure edge
  - Minimal local storage writes for SD card longevity
  - WiFi-only networking (no Ethernet)
"""
from __future__ import annotations

import os

# ── Hardware detection ────────────────────────────────────────────────────────
IS_PI_ZERO_2W = os.uname().machine in ("armv7l", "aarch64") and os.path.isfile(
    "/proc/device-tree/model"
)
"""Rough heuristic — True when running on a Raspberry Pi with ARM64 kernel."""

# ── Coral Edge TPU ────────────────────────────────────────────────────────────
CORAL_ENABLED = os.getenv("CORAL_ENABLED", "true").lower() == "true"
CORAL_DEVICE_ID = os.getenv("CORAL_DEVICE_ID", "/dev/apex_0")
CORAL_MODEL_PATH = os.getenv(
    "CORAL_MODEL_PATH", "/opt/zedd/models/weather_classify_edgetpu.tflite"
)
CORAL_LABELS_PATH = os.getenv(
    "CORAL_LABELS_PATH", "/opt/zedd/models/weather_labels.txt"
)

# ── Weather HAT PRO (same as standard, always enabled on Pi Zero) ─────────────
WEATHER_HAT_PRO_ENABLED = os.getenv("WEATHER_HAT_PRO_ENABLED", "true").lower() == "true"
WEATHER_HAT_PRO_I2C_BUS = int(os.getenv("WEATHER_HAT_PRO_I2C_BUS", "1"))
WEATHER_HAT_PRO_ANEMOMETER_GPIO_PIN = int(
    os.getenv("WEATHER_HAT_PRO_ANEMOMETER_GPIO_PIN", "5")
)
WEATHER_HAT_PRO_RAIN_GAUGE_GPIO_PIN = int(
    os.getenv("WEATHER_HAT_PRO_RAIN_GAUGE_GPIO_PIN", "6")
)
WEATHER_HAT_PRO_VANE_ADC_CHANNEL = int(
    os.getenv("WEATHER_HAT_PRO_VANE_ADC_CHANNEL", "0")
)
WEATHER_HAT_PRO_RAIN_MM_PER_TIP = 0.2794

# ── SD-card-friendly buffer settings ──────────────────────────────────────────
# Everything goes to tmpfs (/tmp) which is RAM-backed on Pi OS.
# On a read-only rootfs the collector writes zero persistent data to SD.
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "/tmp/zedd_buffer.db")
BUFFER_FLUSH_INTERVAL = int(os.getenv("BUFFER_FLUSH_INTERVAL", "300"))  # 5 min
MAX_BUFFER_ROWS = int(os.getenv("MAX_BUFFER_ROWS", "5000"))
PUBLISH_INTERVAL = float(os.getenv("PUBLISH_INTERVAL", "5.0"))

# ── BC Robotics 16CH ADC HAT (enabled — primary analog input) ─────────────────
BC_ROBOTICS_ADC_ENABLED = os.getenv("BC_ROBOTICS_ADC_ENABLED", "true").lower() == "true"
BC_ROBOTICS_ADC_CHIP_TYPE = os.getenv("BC_ROBOTICS_ADC_CHIP_TYPE", "MCP3008")
BC_ROBOTICS_ADC_SPI_BUS = int(os.getenv("BC_ROBOTICS_ADC_SPI_BUS", "0"))
BC_ROBOTICS_ADC_VREF = float(os.getenv("BC_ROBOTICS_ADC_VREF", "3.3"))

# ── Gravity Capacitive Soil Moisture Sensor ───────────────────────────────────
SOIL_MOISTURE_ENABLED = os.getenv("SOIL_MOISTURE_ENABLED", "true").lower() == "true"
SOIL_MOISTURE_ADC_CHANNEL = int(os.getenv("SOIL_MOISTURE_ADC_CHANNEL", "0"))
SOIL_MOISTURE_DRY_V = float(os.getenv("SOIL_MOISTURE_DRY_V", "2.5"))
SOIL_MOISTURE_WET_V = float(os.getenv("SOIL_MOISTURE_WET_V", "1.0"))

# ── Disabled hardware (not present or not useful on Pi Zero 2WH) ──────────────
SENSE_HAT_ENABLED = False        # physically conflicts with Weather HAT
AI_HAT_ENABLED = False           # Hailo HAT requires PCIe / M.2 Key E
ENVIRO_PLUS_ENABLED = False      # I2C address conflicts with Weather HAT
M2_NVME_ENABLED = False          # no M.2 slot
MODBUS_ENABLED = False           # requires RS485 hat + port

# ── MQTT ──────────────────────────────────────────────────────────────────────
# Pi Zero connects to a REMOTE MQTT broker (not running locally).
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "zedd/telemetry/pizero")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "zedd-pizero-01")

# ── Remote backend (analysis happens server-side) ─────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# ── GPIO ──────────────────────────────────────────────────────────────────────
ALARM_BUZZER_GPIO_PIN = int(os.getenv("ALARM_BUZZER_GPIO_PIN", "17"))
ALARM_LED_GPIO_PIN = int(os.getenv("ALARM_LED_GPIO_PIN", "27"))

# ── Alert thresholds ──────────────────────────────────────────────────────────
ALERT_TEMP_HIGH_C = float(os.getenv("ALERT_TEMP_HIGH_C", "35.0"))
ALERT_TEMP_LOW_C = float(os.getenv("ALERT_TEMP_LOW_C", "0.0"))
ALERT_WIND_SPEED_MS = float(os.getenv("ALERT_WIND_SPEED_MS", "20.0"))
ALERT_UV_INDEX = float(os.getenv("ALERT_UV_INDEX", "8.0"))
ALERT_AQI = float(os.getenv("ALERT_AQI", "150.0"))
