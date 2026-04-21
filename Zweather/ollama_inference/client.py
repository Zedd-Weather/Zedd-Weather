"""
Ollama AI client for local inference on pinet-sigma.
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_OLLAMA_URL = "http://10.0.0.20:11434"
_DEFAULT_MODEL = "gemma2:2b"
_REQUEST_TIMEOUT = 30  # seconds


class OllamaClient:
    """
    Thin client for the Ollama local inference server.
    """

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (
            base_url
            or os.environ.get("OLLAMA_BASE_URL", _DEFAULT_OLLAMA_URL)
        ).rstrip("/")

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def is_available(self) -> bool:
        """
        Perform a lightweight health check against the Ollama server.

        Returns
        -------
        True if the server responds with HTTP 200, False otherwise.
        """
        try:
            import requests  # type: ignore
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except (OSError, ValueError) as exc:
            logger.debug("Ollama health check failed: %s", exc)
            return False

    def generate(self, prompt: str, model: str = _DEFAULT_MODEL) -> str:
        """
        Generate a text completion via Ollama.

        Parameters
        ----------
        prompt:
            The text prompt to send to the model.
        model:
            Ollama model tag (e.g. "llama3.2:3b").

        Returns
        -------
        Generated text string, or an error message if Ollama is unavailable.
        """
        if self.is_available():
            return self._ollama_generate(prompt, model)
        return (
            "AI inference unavailable: Ollama server is unreachable."
        )

    def analyze_weather(self, telemetry: dict, crop: str = "general") -> str:
        """
        Generate an AI weather analysis for the given telemetry snapshot.

        Parameters
        ----------
        telemetry:
            Dict with temperature, humidity, pressure, etc.
        crop:
            Crop type for context-specific advice.

        Returns
        -------
        Natural-language weather analysis string.
        """
        temp = telemetry.get("temperature", "N/A")
        humidity = telemetry.get("humidity", "N/A")
        pressure = telemetry.get("pressure", "N/A")
        wind = telemetry.get("wind_speed", "N/A")
        uv = telemetry.get("uv_index", "N/A")
        rainfall = telemetry.get("rainfall_mm", "N/A")

        prompt = f"""You are an agricultural weather analyst. Analyze the following weather sensor
readings and provide a concise assessment suitable for a farmer growing {crop}.

Current Conditions:
- Temperature: {temp}°C
- Relative Humidity: {humidity}%
- Atmospheric Pressure: {pressure} hPa
- Wind Speed: {wind} m/s
- UV Index: {uv}
- Rainfall (last period): {rainfall} mm

Please provide:
1. A brief summary of current conditions (2-3 sentences)
2. Any immediate concerns or risks
3. Short-term outlook

Keep the response practical and under 200 words."""

        return self.generate(prompt)

    def generate_mitigation(
        self,
        telemetry: dict,
        forecast: Optional[dict] = None,
    ) -> str:
        """
        Generate an agricultural mitigation strategy based on telemetry and forecast.

        Parameters
        ----------
        telemetry:
            Current sensor readings dict.
        forecast:
            Optional trend/forecast dict from WeatherForecaster.

        Returns
        -------
        Natural-language mitigation strategy string.
        """
        temp = telemetry.get("temperature", "N/A")
        humidity = telemetry.get("humidity", "N/A")
        pressure = telemetry.get("pressure", "N/A")

        forecast_text = ""
        if forecast:
            forecast_text = f"""
Forecast / Trend Analysis:
- Temperature trend: {forecast.get('temperature_trend', 'unknown')}
- Humidity trend: {forecast.get('humidity_trend', 'unknown')}
- Pressure trend: {forecast.get('pressure_trend', 'unknown')}
- Storm probability: {forecast.get('storm_probability', 0) * 100:.0f}%
- Summary: {forecast.get('summary', '')}"""

        prompt = f"""You are an expert agronomist and precision agriculture advisor.

Current sensor data:
- Temperature: {temp}°C
- Humidity: {humidity}%
- Pressure: {pressure} hPa
{forecast_text}

Provide a concise, actionable mitigation strategy covering:
1. Immediate protective actions (next 6 hours)
2. Irrigation and water management advice
3. Pest and disease prevention steps
4. Equipment or infrastructure precautions

Be specific and practical. Limit response to 250 words."""

        return self.generate(prompt)

    # ---------------------------------------------------------------------------
    # Private backends
    # ---------------------------------------------------------------------------

    def _ollama_generate(self, prompt: str, model: str) -> str:
        """Send a generation request to the local Ollama server."""
        try:
            import requests  # type: ignore
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
            }
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip()
        except (
            OSError,
            ValueError,
            KeyError,
            requests.RequestException,
        ) as exc:
            logger.error("Ollama generation failed: %s", exc)
            return f"Ollama error: {exc}"
