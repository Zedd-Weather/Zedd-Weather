"""
Centralized configuration for the Node 1 telemetry system.
All hardware pins, MQTT settings, thresholds, and sensor toggles live here.

Hardware profile (production Raspberry Pi Weather Node):
    - BCRobotics Weather HAT PRO – primary environmental + wind/rain
        station (BME280 over I²C, anemometer, wind vane, tipping-bucket
        rain gauge wired through the three RJ12 jacks)
    - AI HAT+ (Hailo-8L NPU via M.2 Key E) – on-device edge inference
    - M.2 NVMe SSD   – fast local telemetry buffer and model storage

The legacy Sense HAT v2 is still supported as an optional secondary HAT
(``SENSE_HAT_ENABLED=true``) for sites that need an IMU or the 8×8 LED
matrix, but it is **disabled by default** in favour of the Weather HAT
PRO.
"""
import os

# ---------------------------------------------------------------------------
# MQTT
# ---------------------------------------------------------------------------
MQTT_BROKER = os.getenv("MQTT_BROKER_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "zedd/telemetry/node1")
MQTT_CLIENT_ID = "node1_telemetry"
PUBLISH_INTERVAL = float(os.getenv("PUBLISH_INTERVAL", "5.0"))  # seconds

# ---------------------------------------------------------------------------
# Sense HAT (legacy / optional secondary HAT — disabled by default)
# ---------------------------------------------------------------------------
SENSE_HAT_ENABLED = os.getenv("SENSE_HAT_ENABLED", "false").lower() == "true"
# CPU temperature compensation factor (Sense HAT reads ~2 °C high due to
# proximity to the Pi CPU).  Subtract this from the raw reading.
SENSE_HAT_TEMP_OFFSET = float(os.getenv("SENSE_HAT_TEMP_OFFSET", "2.0"))

# ---------------------------------------------------------------------------
# AI HAT+ (Hailo-8L NPU – M.2 Key E accelerator)
# ---------------------------------------------------------------------------
AI_HAT_ENABLED = os.getenv("AI_HAT_ENABLED", "true").lower() == "true"
# Path to the compiled HEF (Hailo Executable Format) weather-classification model.
AI_HAT_MODEL_PATH = os.getenv(
    "AI_HAT_MODEL_PATH", "/opt/zedd/models/weather_classify.hef"
)
# Hailo device identifier (/dev/hailo0 is default for single-NPU setups).
AI_HAT_DEVICE_ID = os.getenv("AI_HAT_DEVICE_ID", "/dev/hailo0")

# ---------------------------------------------------------------------------
# M.2 NVMe storage
# ---------------------------------------------------------------------------
# When an M.2 NVMe SSD is present, use it for the telemetry buffer and
# model artifacts instead of the SD card.  Falls back to /tmp on non-NVMe
# setups.
M2_NVME_PATH = os.getenv("M2_NVME_PATH", "/mnt/nvme")
M2_NVME_ENABLED = os.getenv("M2_NVME_ENABLED", "false").lower() == "true"

# ---------------------------------------------------------------------------
# GPIO – Rain Gauge (Tipping Bucket)
# ---------------------------------------------------------------------------
RAIN_GAUGE_ENABLED = os.getenv("RAIN_GAUGE_ENABLED", "false").lower() == "true"
RAIN_GAUGE_GPIO_PIN = int(os.getenv("RAIN_GAUGE_GPIO_PIN", "6"))
# Each bucket tip = 0.2794 mm of rainfall (standard for most tipping-bucket gauges)
RAIN_GAUGE_MM_PER_TIP = float(os.getenv("RAIN_GAUGE_MM_PER_TIP", "0.2794"))

# ---------------------------------------------------------------------------
# GPIO – Alarm Outputs
# ---------------------------------------------------------------------------
ALARM_BUZZER_GPIO_PIN = int(os.getenv("ALARM_BUZZER_GPIO_PIN", "17"))
ALARM_LED_GPIO_PIN = int(os.getenv("ALARM_LED_GPIO_PIN", "27"))

# ---------------------------------------------------------------------------
# UV Sensor – Adafruit VEML6075 (I2C)
# ---------------------------------------------------------------------------
UV_SENSOR_ENABLED = os.getenv("UV_SENSOR_ENABLED", "false").lower() == "true"
UV_SENSOR_I2C_BUS = int(os.getenv("UV_SENSOR_I2C_BUS", "1"))
UV_SENSOR_I2C_ADDR = int(os.getenv("UV_SENSOR_I2C_ADDR", "0x10"), 0)

# ---------------------------------------------------------------------------
# Pimoroni Enviro+ (AQI, Gas, Particulate Matter)
# ---------------------------------------------------------------------------
ENVIRO_PLUS_ENABLED = os.getenv("ENVIRO_PLUS_ENABLED", "false").lower() == "true"

# ---------------------------------------------------------------------------
# BCRobotics Weather HAT PRO (BME280 + reed-switch anemometer + wind vane
# + tipping-bucket rain gauge, wired through the three RJ12 jacks).
# Primary sensor HAT for the Zedd sensory worker — enabled by default.
# ---------------------------------------------------------------------------
WEATHER_HAT_PRO_ENABLED = (
    os.getenv("WEATHER_HAT_PRO_ENABLED", "true").lower() == "true"
)
# CPU temperature compensation factor for the on-board BME280
# (the board sits close to the Pi CPU).  0.8 °C is a sensible default.
WEATHER_HAT_PRO_TEMP_OFFSET = float(
    os.getenv("WEATHER_HAT_PRO_TEMP_OFFSET", "0.8")
)
# I²C bus the BME280 lives on (bus 1 on every modern Pi).
WEATHER_HAT_PRO_I2C_BUS = int(os.getenv("WEATHER_HAT_PRO_I2C_BUS", "1"))
# GPIO (BCM numbering) connected to the anemometer reed switch (RJ12 J2).
WEATHER_HAT_PRO_ANEMOMETER_GPIO_PIN = int(
    os.getenv("WEATHER_HAT_PRO_ANEMOMETER_GPIO_PIN", "5")
)
# GPIO (BCM numbering) connected to the rain-gauge reed switch (RJ12 J3).
WEATHER_HAT_PRO_RAIN_GAUGE_GPIO_PIN = int(
    os.getenv("WEATHER_HAT_PRO_RAIN_GAUGE_GPIO_PIN", "6")
)
# Each rain-gauge bucket tip = 0.2794 mm of rainfall (SparkFun /
# Argent Data Systems standard tipping-bucket gauge).
WEATHER_HAT_PRO_RAIN_MM_PER_TIP = float(
    os.getenv("WEATHER_HAT_PRO_RAIN_MM_PER_TIP", "0.2794")
)
# MCP3008 / ADS1015 channel the wind-vane resistor divider is wired to.
WEATHER_HAT_PRO_VANE_ADC_CHANNEL = int(
    os.getenv("WEATHER_HAT_PRO_VANE_ADC_CHANNEL", "0")
)

# ---------------------------------------------------------------------------
# BC Robotics 16-Channel Analog Input HAT (SPI ADC)
# ---------------------------------------------------------------------------
BC_ROBOTICS_ADC_ENABLED = (
    os.getenv("BC_ROBOTICS_ADC_ENABLED", "false").lower() == "true"
)
# ADC chip type: "MCP3008" (10-bit, default) or "MCP3208" (12-bit)
BC_ROBOTICS_ADC_CHIP_TYPE = os.getenv(
    "BC_ROBOTICS_ADC_CHIP_TYPE", "MCP3008"
)
# SPI bus and reference voltage (Volts)
BC_ROBOTICS_ADC_SPI_BUS = int(os.getenv("BC_ROBOTICS_ADC_SPI_BUS", "0"))
BC_ROBOTICS_ADC_VREF = float(os.getenv("BC_ROBOTICS_ADC_VREF", "3.3"))

# ---------------------------------------------------------------------------
# Gravity Analog Capacitive Soil Moisture Sensor (via BC Robotics ADC)
# ---------------------------------------------------------------------------
SOIL_MOISTURE_ENABLED = (
    os.getenv("SOIL_MOISTURE_ENABLED", "false").lower() == "true"
)
# ADC channel the sensor is wired to (0–15)
SOIL_MOISTURE_ADC_CHANNEL = int(
    os.getenv("SOIL_MOISTURE_ADC_CHANNEL", "0")
)
# Calibration voltages: measured when sensor is dry vs fully wet
SOIL_MOISTURE_DRY_V = float(os.getenv("SOIL_MOISTURE_DRY_V", "2.5"))
SOIL_MOISTURE_WET_V = float(os.getenv("SOIL_MOISTURE_WET_V", "1.0"))

# ---------------------------------------------------------------------------
# Modbus / RS485 – Industrial Sensors (via Waveshare RS485 CAN HAT)
# ---------------------------------------------------------------------------
MODBUS_ENABLED = os.getenv("MODBUS_ENABLED", "false").lower() == "true"
MODBUS_PORT = os.getenv("MODBUS_PORT", "/dev/ttyS0")
MODBUS_BAUDRATE = int(os.getenv("MODBUS_BAUDRATE", "9600"))
MODBUS_ANEMOMETER_UNIT_ID = int(os.getenv("MODBUS_ANEMOMETER_UNIT_ID", "1"))
MODBUS_RAIN_GAUGE_UNIT_ID = int(os.getenv("MODBUS_RAIN_GAUGE_UNIT_ID", "2"))

# ---------------------------------------------------------------------------
# Alert Thresholds
# ---------------------------------------------------------------------------
ALERT_TEMP_HIGH_C = float(os.getenv("ALERT_TEMP_HIGH_C", "35.0"))
ALERT_TEMP_LOW_C = float(os.getenv("ALERT_TEMP_LOW_C", "0.0"))
ALERT_WIND_SPEED_MS = float(os.getenv("ALERT_WIND_SPEED_MS", "20.0"))
ALERT_UV_INDEX = float(os.getenv("ALERT_UV_INDEX", "8.0"))
ALERT_AQI = float(os.getenv("ALERT_AQI", "150.0"))
