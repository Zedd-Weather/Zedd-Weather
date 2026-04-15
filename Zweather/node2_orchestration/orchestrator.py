"""
Node 2: Inference & Orchestration
Subscribes to Node 1, ingests AccuWeather data, runs inference, and attests data.
"""
import asyncio
import json
import logging
import hashlib
import os
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
import aiohttp

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

MQTT_BROKER = os.environ.get("MQTT_BROKER_HOST", "127.0.0.1")
MQTT_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC = "zedd/telemetry/node1"

ACCUWEATHER_API_KEY = os.environ.get("ACCUWEATHER_API_KEY", "")
ACCUWEATHER_URL = os.environ.get(
    "ACCUWEATHER_URL", "https://dataservice.accuweather.com"
)

# Site coordinates – override with SITE_LATITUDE / SITE_LONGITUDE env vars
_raw_lat = os.environ.get("SITE_LATITUDE")
_raw_lon = os.environ.get("SITE_LONGITUDE")
try:
    SITE_LAT = float(_raw_lat) if _raw_lat is not None else None
    SITE_LON = float(_raw_lon) if _raw_lon is not None else None
    if SITE_LAT is not None and not (-90 <= SITE_LAT <= 90):
        logging.warning("SITE_LATITUDE %.4f out of range [-90, 90].", SITE_LAT)
        SITE_LAT = None
    if SITE_LON is not None and not (-180 <= SITE_LON <= 180):
        logging.warning("SITE_LONGITUDE %.4f out of range [-180, 180].", SITE_LON)
        SITE_LON = None
except ValueError as exc:
    logging.error("Invalid SITE_LATITUDE/SITE_LONGITUDE: %s", exc)
    SITE_LAT = None
    SITE_LON = None

class ZeddOrchestrator:
    def __init__(self):
        self.latest_telemetry = None
        self.mqtt_client = mqtt.Client(client_id="node2_orchestrator")
        self.mqtt_client.username_pw_set(
            os.environ.get("MQTT_USERNAME", ""),
            os.environ.get("MQTT_PASSWORD", ""),
        )
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.session = None

    def on_connect(self, client, userdata, flags, rc):
        logging.info("Connected to MQTT Broker. Subscribing to telemetry...")
        client.subscribe(MQTT_TOPIC, qos=1)

    def on_message(self, client, userdata, msg):
        try:
            self.latest_telemetry = json.loads(msg.payload.decode("utf-8", errors="replace"))
            logging.debug(f"Received telemetry: {self.latest_telemetry}")
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logging.error("Invalid payload received: %s", exc)

    async def _resolve_location_key(self, lat: float, lon: float) -> str | None:
        """Resolve a lat/lon pair to an AccuWeather location key."""
        url = (
            f"{ACCUWEATHER_URL}/locations/v1/cities/geoposition/search"
            f"?apikey={ACCUWEATHER_API_KEY}&q={lat},{lon}"
        )
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("Key")
                body = await resp.text()
                logging.warning("AccuWeather location lookup returned %s: %s", resp.status, body[:200])
                return None
        except Exception as exc:
            logging.error("AccuWeather location lookup failed: %s", exc)
            return None

    async def fetch_macro_forecast(self):
        """Ingests 5-day macro-meteorological forecasts via AccuWeather API."""
        if not ACCUWEATHER_API_KEY:
            logging.warning("AccuWeather API key not configured. Set ACCUWEATHER_API_KEY.")
            return None

        if SITE_LAT is None or SITE_LON is None:
            logging.warning("Site coordinates not configured. Set SITE_LATITUDE and SITE_LONGITUDE.")
            return None

        location_key = await self._resolve_location_key(SITE_LAT, SITE_LON)
        if not location_key:
            return None

        url = (
            f"{ACCUWEATHER_URL}/forecasts/v1/daily/5day/{location_key}"
            f"?apikey={ACCUWEATHER_API_KEY}&details=true&metric=true"
        )

        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if not isinstance(data, dict) or "DailyForecasts" not in data:
                        logging.warning("AccuWeather response missing expected 'DailyForecasts' field.")
                        return None
                    logging.info("Successfully ingested AccuWeather macro forecast.")
                    return data
                else:
                    body = await resp.text()
                    logging.warning("AccuWeather API returned status %s: %s", resp.status, body[:200])
                    return None
        except Exception as e:
            logging.error("Failed to fetch macro forecast: %s", e)
            return None

    def run_inference(self, micro_data, macro_data):
        """Run sector-specific analysis using the heuristic engines."""
        if not micro_data:
            return None

        sector = os.environ.get("ACTIVE_SECTOR", "construction").lower()

        # Map telemetry keys to engine format
        telemetry = {
            "temperature": micro_data.get("temperature_c", micro_data.get("local_temp_c", 20.0)),
            "humidity": micro_data.get("humidity_pct", micro_data.get("local_humidity_pct", 60.0)),
            "pressure": micro_data.get("pressure_hpa", micro_data.get("local_pressure_hpa", 1013.0)),
        }

        # Add optional fields
        for key in ("wind_speed", "uv_index", "rainfall_mm", "aqi"):
            if key in micro_data:
                telemetry[key] = micro_data[key]

        try:
            if sector == "construction":
                from Zweather.construction.engine import ConstructionEngine
                engine = ConstructionEngine()
                result = engine.analyze(telemetry)
            elif sector == "agricultural":
                from Zweather.agricultural.engine import AgriculturalEngine
                engine = AgriculturalEngine()
                result = engine.analyze(telemetry)
            elif sector == "industrial":
                from Zweather.industrial.engine import IndustrialEngine
                engine = IndustrialEngine()
                result = engine.analyze(telemetry)
            else:
                result = {"error": f"Unknown sector: {sector}"}

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sector": sector,
                "analysis": result,
                "directive": result.get("risk_level", "unknown"),
            }
        except Exception as e:
            logging.error("Sector engine analysis failed: %s", e)
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sector": sector,
                "directive": "ANALYSIS_FAILED",
                "error": str(e),
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
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        
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
