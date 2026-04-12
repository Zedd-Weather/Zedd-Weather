"""
Node 1: Telemetry Publisher
Acquires micro-climate telemetry from all enabled sensors (Sense HAT, GPIO
rain gauge, VEML6075 UV, Enviro+, Modbus RS485) and publishes the aggregated
payload to MQTT.  Also drives the Sense HAT LED display and GPIO alarm
outputs based on configurable thresholds.

Usage:
    python -m Zweather.node1_telemetry.mqtt_publisher
"""
import time
import json
import logging
import socket

import paho.mqtt.client as mqtt

from Zweather.node1_telemetry import config
from Zweather.node1_telemetry.sensors.sensor_manager import SensorManager
from Zweather.node1_telemetry.hat_control.led_display import LEDDisplay
from Zweather.node1_telemetry.hat_control.alarm import AlarmController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ── MQTT callbacks ────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT Broker.")
    else:
        logger.error("Failed to connect, return code %d", rc)


def on_disconnect(client, userdata, rc):
    logger.warning("Disconnected from MQTT Broker. Attempting reconnect …")


# ── Risk level helper ─────────────────────────────────────────────────
def _compute_risk_level(telemetry: dict) -> str:
    """Derive a simple risk colour from the telemetry payload."""
    temp = telemetry.get("temperature_c")
    wind = telemetry.get("wind_speed_ms")
    uv = telemetry.get("uv_index")
    pm25 = telemetry.get("pm2_5_ug_m3")

    if temp is not None and (temp > 40 or temp < -5):
        return "red"
    if wind is not None and wind > 25:
        return "red"
    if temp is not None and (temp > config.ALERT_TEMP_HIGH_C or temp < config.ALERT_TEMP_LOW_C):
        return "amber"
    if wind is not None and wind > config.ALERT_WIND_SPEED_MS:
        return "amber"
    if uv is not None and uv > config.ALERT_UV_INDEX:
        return "amber"
    if pm25 is not None and pm25 > config.ALERT_AQI:
        return "amber"
    return "green"


# ── Main entry point ──────────────────────────────────────────────────
def main():
    # 1. Initialise sensors
    sensor_mgr = SensorManager()
    sensor_mgr.initialize()

    # 2. Initialise HAT display and alarm
    led = LEDDisplay(sensor_mgr.sense_hat)
    alarm = AlarmController()
    alarm.initialize()

    # Show startup colour
    led.show_risk_level("green")

    # 3. Connect to MQTT broker
    client = mqtt.Client(client_id=config.MQTT_CLIENT_ID, clean_session=False)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    max_retries = 30
    retry_count = 0
    while True:
        try:
            client.connect(config.MQTT_BROKER, config.MQTT_PORT, keepalive=60)
            client.loop_start()
            break
        except (socket.error, ConnectionRefusedError) as exc:
            retry_count += 1
            if retry_count >= max_retries:
                logger.critical("MQTT connection failed after %d retries. Exiting.", max_retries)
                sensor_mgr.cleanup()
                return
            backoff = min(5 * retry_count, 60)
            logger.error("MQTT connection failed (%d/%d): %s. Retrying in %d s …", retry_count, max_retries, exc, backoff)
            time.sleep(backoff)

    # 4. Publish loop
    try:
        while True:
            payload = sensor_mgr.read_all()

            # Evaluate alarms
            alarm.evaluate(payload)

            # Update LED risk display
            risk = _compute_risk_level(payload)
            led.show_risk_level(risk)

            # Publish
            result = client.publish(
                config.MQTT_TOPIC, json.dumps(payload), qos=1
            )
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug("Published: %s", payload)
            else:
                logger.error("Failed to publish telemetry.")

            time.sleep(config.PUBLISH_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Shutting down telemetry node.")
    finally:
        led.clear()
        alarm.cleanup()
        sensor_mgr.cleanup()
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
