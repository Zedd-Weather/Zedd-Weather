import os
import json
import time
import queue
import logging
import hashlib
import hmac
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

def fetch_accuweather_forecast(lat: float, lon: float) -> dict:
    """
    Fetch a 5-day macro-meteorological forecast from the AccuWeather API.
    Returns a summary dict; falls back to an empty result when the API key
    is not configured or the API is unreachable.
    """
    api_key = os.getenv("ACCUWEATHER_API_KEY")

    if not api_key:
        logger.warning("AccuWeather API key missing (ACCUWEATHER_API_KEY). Forecast unavailable.")
        return {
            "forecast_days": 0,
            "avg_temp_c": None,
            "max_wind_speed_ms": None,
            "precip_probability_pct": None,
            "severe_weather_alerts": [],
            "source": "unavailable",
        }

    base_url = os.getenv("ACCUWEATHER_URL", "https://dataservice.accuweather.com")
    # Conversion factor: km/h → m/s
    kmh_to_ms = 3.6

    try:
        import requests  # type: ignore

        # Step 1: Resolve lat/lon to an AccuWeather location key
        geo_url = (
            f"{base_url}/locations/v1/cities/geoposition/search"
            f"?apikey={api_key}&q={lat},{lon}"
        )
        geo_resp = requests.get(geo_url, timeout=15)
        geo_resp.raise_for_status()
        location_key = geo_resp.json().get("Key")
        if not location_key:
            logger.warning("AccuWeather geoposition lookup returned no location key.")
            return {
                "forecast_days": 0,
                "avg_temp_c": None,
                "max_wind_speed_ms": None,
                "precip_probability_pct": None,
                "severe_weather_alerts": [],
                "source": "error",
            }

        # Step 2: Fetch 5-day daily forecast
        forecast_url = (
            f"{base_url}/forecasts/v1/daily/5day/{location_key}"
            f"?apikey={api_key}&details=true&metric=true"
        )
        resp = requests.get(forecast_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # Extract summary metrics from AccuWeather response
        temps: list[float] = []
        winds: list[float] = []
        precip_probs: list[int] = []
        alerts: list[str] = []

        for day in data.get("DailyForecasts", []):
            temp_obj = day.get("Temperature", {})
            min_temp = temp_obj.get("Minimum", {}).get("Value")
            max_temp = temp_obj.get("Maximum", {}).get("Value")
            if min_temp is not None:
                temps.append(min_temp)
            if max_temp is not None:
                temps.append(max_temp)

            # Wind speed (AccuWeather returns km/h, convert to m/s)
            day_detail = day.get("Day", {})
            wind_obj = day_detail.get("Wind", {}).get("Speed", {})
            wind_kmh = wind_obj.get("Value")
            if wind_kmh is not None:
                winds.append(wind_kmh / kmh_to_ms)  # km/h → m/s

            # Precipitation probability
            precip_prob = day_detail.get("PrecipitationProbability")
            if precip_prob is not None:
                precip_probs.append(precip_prob)

        # Headline alerts
        headline = data.get("Headline", {})
        if headline.get("Text"):
            alerts.append(headline["Text"])

        return {
            "forecast_days": 5,
            "avg_temp_c": round(sum(temps) / len(temps), 1) if temps else None,
            "max_wind_speed_ms": round(max(winds), 1) if winds else None,
            "precip_probability_pct": round(sum(precip_probs) / len(precip_probs)) if precip_probs else None,
            "severe_weather_alerts": alerts,
            "source": "accuweather",
        }
    except Exception as e:
        logger.error("AccuWeather API request failed: %s", e)
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
    
    Macro-Meteorological Forecast (5-Day via AccuWeather):
    {json.dumps(forecast, indent=2)}
    
    Output strictly the mitigation directives.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
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
            raw_lat = os.getenv("SITE_LATITUDE")
            raw_lon = os.getenv("SITE_LONGITUDE")
            if raw_lat is None or raw_lon is None:
                logger.warning("Site coordinates not configured. Set SITE_LATITUDE and SITE_LONGITUDE env vars.")
                forecast = fetch_accuweather_forecast(lat=0, lon=0)
            else:
                forecast = fetch_accuweather_forecast(lat=float(raw_lat), lon=float(raw_lon))
            
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
            
            # Generate HMAC-SHA256 signature for attestation integrity
            signing_key = os.getenv("ATTESTATION_HMAC_KEY", "")
            if not signing_key:
                logger.warning("ATTESTATION_HMAC_KEY not set; skipping attestation signing.")
                attestation_payload["signature"] = None
            else:
                signature = hmac.new(
                    signing_key.encode('utf-8'),
                    stable_json.encode('utf-8'),
                    hashlib.sha256,
                ).hexdigest()
                attestation_payload["signature"] = signature
            
            logger.info("Attestation generated successfully.")
            
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
