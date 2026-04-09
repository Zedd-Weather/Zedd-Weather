import os
import json
import time
import queue
import logging
import hashlib
import threading
from datetime import datetime, timezone
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
from google import genai

# Configure logging for headless edge deployment
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ZeddOrchestrator")

# Initialize thread-safe queue for non-blocking MQTT ingestion
telemetry_queue = queue.Queue()

def fetch_meteomatics_forecast(lat: float, lon: float) -> dict:
    """
    Fetch a 5-day macro-meteorological forecast from the Meteomatics API.
    Returns a summary dict; falls back to an empty result when credentials
    are not configured or the API is unreachable.
    """
    user = os.getenv("METEOMATICS_USER")
    password = os.getenv("METEOMATICS_PASS")
    
    if not user or not password:
        logger.warning("Meteomatics credentials missing (METEOMATICS_USER / METEOMATICS_PASS). Forecast unavailable.")
        return {
            "forecast_days": 0,
            "avg_temp_c": None,
            "max_wind_speed_ms": None,
            "precip_probability_pct": None,
            "severe_weather_alerts": [],
            "source": "unavailable",
        }

    base_url = os.getenv("METEOMATICS_URL", "https://api.meteomatics.com")
    from datetime import datetime as _dt, timezone as _tz
    now = _dt.now(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"{base_url}/{now}P5D:PT1H/t_2m:C,wind_speed_10m:ms/{lat},{lon}/json"

    try:
        import requests  # type: ignore
        resp = requests.get(url, auth=(user, password), timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # Extract summary metrics from the Meteomatics response
        temps = []
        winds = []
        for param in data.get("data", []):
            for coord in param.get("coordinates", []):
                for date_entry in coord.get("dates", []):
                    val = date_entry.get("value")
                    if val is not None:
                        if "t_2m" in param.get("parameter", ""):
                            temps.append(val)
                        elif "wind_speed" in param.get("parameter", ""):
                            winds.append(val)

        return {
            "forecast_days": 5,
            "avg_temp_c": round(sum(temps) / len(temps), 1) if temps else None,
            "max_wind_speed_ms": round(max(winds), 1) if winds else None,
            "precip_probability_pct": None,  # not available in this Meteomatics query
            "severe_weather_alerts": [],
            "source": "meteomatics",
        }
    except Exception as e:
        logger.error(f"Meteomatics API request failed: {e}")
        return {
            "forecast_days": 0,
            "avg_temp_c": None,
            "max_wind_speed_ms": None,
            "precip_probability_pct": None,
            "severe_weather_alerts": [],
            "source": "error",
        }

def generate_mitigation_strategy(telemetry: dict, forecast: dict) -> str:
    """
    Uses Gemini AI to cross-reference micro-climate telemetry with macro forecasts
    to generate a concise, actionable construction site mitigation strategy.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are a Principal Edge AI and IoT Systems Architect for Zedd Weather.
    Analyze the following environmental data for an industrial construction site and provide a concise, actionable mitigation strategy.
    
    Local Micro-Climate Telemetry (Sense HAT):
    {json.dumps(telemetry, indent=2)}
    
    Macro-Meteorological Forecast (5-Day):
    {json.dumps(forecast, indent=2)}
    
    Output strictly the mitigation directives.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-preview',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"AI Inference failed: {e}")
        return "ERROR: Mitigation strategy generation failed due to inference error."

def inference_worker():
    """
    Daemon thread worker that processes telemetry payloads from the queue,
    fetches forecasts, runs AI inference, and creates cryptographic attestations.
    """
    logger.info("Inference worker thread started.")
    while True:
        try:
            # Block until a payload is available
            payload = telemetry_queue.get()
            if payload is None:
                break
            
            logger.info("Processing new telemetry payload...")
            
            # 1. Fetch Macro-Forecast using configured site coordinates
            site_lat = float(os.getenv("SITE_LATITUDE", "0"))
            site_lon = float(os.getenv("SITE_LONGITUDE", "0"))
            if site_lat == 0 and site_lon == 0:
                logger.warning("Site coordinates not configured. Set SITE_LATITUDE and SITE_LONGITUDE env vars.")
            forecast = fetch_meteomatics_forecast(lat=site_lat, lon=site_lon)
            
            # 2. Edge AI Inference
            strategy = generate_mitigation_strategy(telemetry=payload, forecast=forecast)
            
            # 3. Cryptographic Attestation
            attestation_payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "telemetry": payload,
                "forecast": forecast,
                "mitigation_strategy": strategy
            }
            
            # Convert to stable JSON string (sort_keys=True, no spaces)
            stable_json = json.dumps(attestation_payload, sort_keys=True, separators=(',', ':'))
            
            # Generate SHA-256 signature
            signature = hashlib.sha256(stable_json.encode('utf-8')).hexdigest()
            attestation_payload["signature"] = signature
            
            logger.info(f"Attestation generated successfully. Signature: {signature}")
            logger.debug(f"Final Payload: {json.dumps(attestation_payload, indent=2)}")
            
            # Signal task completion to the queue
            telemetry_queue.task_done()
            
        except Exception as e:
            logger.error(f"Error in inference worker pipeline: {e}")

def on_connect(client, userdata, flags, rc):
    """MQTT on_connect callback."""
    if rc == 0:
        logger.info("Successfully connected to MQTT broker.")
        client.subscribe("weather_station/telemetry")
        logger.info("Subscribed to topic: weather_station/telemetry")
    else:
        logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")

def on_message(client, userdata, msg):
    """
    MQTT on_message callback.
    Immediately offloads the payload to the queue to prevent blocking the network loop.
    """
    try:
        payload_str = msg.payload.decode('utf-8')
        payload = json.loads(payload_str)
        
        # Validate expected keys
        expected_keys = {"local_temp_c", "local_pressure_hpa", "local_humidity_pct"}
        if expected_keys.issubset(payload.keys()):
            telemetry_queue.put(payload)
            logger.debug("Payload queued for inference.")
        else:
            logger.warning(f"Malformed payload received (missing keys): {payload_str}")
            
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON from MQTT payload.")
    except Exception as e:
        logger.error(f"Unexpected error in on_message: {e}")

def main():
    """Main application entry point."""
    load_dotenv()
    
    # Start the daemonized inference worker thread
    worker = threading.Thread(target=inference_worker, daemon=True)
    worker.start()
    
    # Configure and start the MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
    broker_port = int(os.getenv("MQTT_BROKER_PORT", 1883))
    
    try:
        logger.info(f"Connecting to MQTT broker at {broker_host}:{broker_port}...")
        client.connect(broker_host, broker_port, 60)
        
        # Start the non-blocking network loop
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("Shutdown signal received. Exiting...")
    except Exception as e:
        logger.critical(f"Fatal MQTT error: {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
