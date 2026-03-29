"""
Node 1: Telemetry Publisher
Acquires micro-climate telemetry via Sense HAT and publishes to MQTT.
"""
import time
import json
import logging
import socket
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

MQTT_BROKER = "10.0.0.16" # Node 2 IP
MQTT_PORT = 1883
MQTT_TOPIC = "zedd/telemetry/node1"
PUBLISH_INTERVAL = 5.0 # seconds

try:
    from sense_hat import SenseHat
    sense = SenseHat()
except ImportError:
    logging.warning("Sense HAT not found. Using mock data generator.")
    class MockSenseHat:
        def get_temperature(self): return 24.5
        def get_pressure(self): return 1012.1
        def get_humidity(self): return 45.2
    sense = MockSenseHat()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to MQTT Broker.")
    else:
        logging.error(f"Failed to connect, return code {rc}")

def on_disconnect(client, userdata, rc):
    logging.warning("Disconnected from MQTT Broker. Attempting reconnect...")

def main():
    client = mqtt.Client(client_id="node1_telemetry", clean_session=False)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.loop_start()
            break
        except (socket.error, ConnectionRefusedError) as e:
            logging.error(f"MQTT connection failed: {e}. Retrying in 5s...")
            time.sleep(5)

    try:
        while True:
            payload = {
                "timestamp": time.time(),
                "temperature_c": round(sense.get_temperature(), 2),
                "pressure_hpa": round(sense.get_pressure(), 2),
                "humidity_pct": round(sense.get_humidity(), 2)
            }
            
            result = client.publish(MQTT_TOPIC, json.dumps(payload), qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logging.debug(f"Published: {payload}")
            else:
                logging.error("Failed to publish telemetry.")
            
            time.sleep(PUBLISH_INTERVAL)
    except KeyboardInterrupt:
        logging.info("Shutting down telemetry node.")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
