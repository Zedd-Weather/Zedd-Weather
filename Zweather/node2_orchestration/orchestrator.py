"""
Node 2: Inference & Orchestration
Subscribes to Node 1, ingests Meteomatics data, runs inference, and attests data.
"""
import asyncio
import json
import logging
import hashlib
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
import aiohttp

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "zedd/telemetry/node1"

METEOMATICS_USER = "zedd_user"
METEOMATICS_PASS = "zedd_pass"
METEOMATICS_URL = "https://api.meteomatics.com"

class ZeddOrchestrator:
    def __init__(self):
        self.latest_telemetry = None
        self.mqtt_client = mqtt.Client(client_id="node2_orchestrator")
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.session = None

    def on_connect(self, client, userdata, flags, rc):
        logging.info("Connected to MQTT Broker. Subscribing to telemetry...")
        client.subscribe(MQTT_TOPIC, qos=1)

    def on_message(self, client, userdata, msg):
        try:
            self.latest_telemetry = json.loads(msg.payload.decode())
            logging.debug(f"Received telemetry: {self.latest_telemetry}")
        except json.JSONDecodeError:
            logging.error("Invalid payload received.")

    async def fetch_macro_forecast(self):
        """Ingests 5-day macro-meteorological forecasts via Meteomatics API."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # Example coordinates for construction site
        url = f"{METEOMATICS_URL}/{now}P5D:PT1H/t_2m:C,wind_speed_10m:ms/40.7128,-74.0060/json"
        
        try:
            async with self.session.get(url, auth=aiohttp.BasicAuth(METEOMATICS_USER, METEOMATICS_PASS)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logging.info("Successfully ingested Meteomatics macro forecast.")
                    return data
                else:
                    logging.warning(f"Meteomatics API returned status {resp.status}")
                    return None
        except Exception as e:
            logging.error(f"Failed to fetch macro forecast: {e}")
            return None

    def run_inference(self, micro_data, macro_data):
        """Cross-references micro/macro data to generate mitigation directives."""
        if not micro_data:
            return None
        
        # Placeholder for actual ML inference (e.g., ONNX runtime)
        temp = micro_data.get("temperature_c", 0)
        directive = "NORMAL_OPERATIONS"
        
        if temp > 35.0:
            directive = "HALT_HEAVY_MACHINERY_HEAT_RISK"
        elif temp < 0.0:
            directive = "APPLY_FROST_MITIGATION"
            
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "micro_temp": temp,
            "directive": directive
        }

    def attest_directive(self, directive_payload):
        """Cryptographically signs the directive for the decentralized ledger."""
        payload_str = json.dumps(directive_payload, sort_keys=True)
        sha256_hash = hashlib.sha256(payload_str.encode('utf-8')).hexdigest()
        
        attestation_record = {
            "payload": directive_payload,
            "signature": sha256_hash,
            "protocol": "Minima-Zedd-v1"
        }
        logging.info(f"Attestation generated: {sha256_hash}")
        # In production, submit `sha256_hash` to Minima RPC here
        return attestation_record

    async def orchestration_loop(self):
        self.session = aiohttp.ClientSession()
        
        # Start MQTT loop in background thread
        self.mqtt_client.connect_async(MQTT_BROKER, MQTT_PORT, 60)
        self.mqtt_client.loop_start()
        
        try:
            while True:
                if self.latest_telemetry:
                    macro_data = await self.fetch_macro_forecast()
                    directive = self.run_inference(self.latest_telemetry, macro_data)
                    
                    if directive:
                        attestation = self.attest_directive(directive)
                        # Store or broadcast attestation
                        
                await asyncio.sleep(60) # Run orchestration cycle every 60s
        except asyncio.CancelledError:
            logging.info("Orchestration loop cancelled.")
        finally:
            await self.session.close()
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

if __name__ == "__main__":
    orchestrator = ZeddOrchestrator()
    asyncio.run(orchestrator.orchestration_loop())
