"""
Centralized configuration for the Node 1 telemetry system.
All hardware pins, MQTT settings, thresholds, and sensor toggles live here.
"""
import os

# ---------------------------------------------------------------------------
# MQTT
# ---------------------------------------------------------------------------
MQTT_BROKER = os.getenv("MQTT_BROKER_HOST", "10.0.0.16")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "zedd/telemetry/node1")
MQTT_CLIENT_ID = "node1_telemetry"
PUBLISH_INTERVAL = float(os.getenv("PUBLISH_INTERVAL", "5.0"))  # seconds

# ---------------------------------------------------------------------------
# Sense HAT
# ---------------------------------------------------------------------------
SENSE_HAT_ENABLED = os.getenv("SENSE_HAT_ENABLED", "true").lower() == "true"
# CPU temperature compensation factor (Sense HAT reads ~2 °C high due to
# proximity to the Pi CPU).  Subtract this from the raw reading.
SENSE_HAT_TEMP_OFFSET = float(os.getenv("SENSE_HAT_TEMP_OFFSET", "2.0"))

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
