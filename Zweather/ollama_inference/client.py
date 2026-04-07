"""
Ollama AI client for local inference on pinet-sigma.
Falls back to Google Gemini if Ollama is unavailable and GEMINI_API_KEY is set.
"""
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_OLLAMA_URL = "http://10.0.0.20:11434"
_DEFAULT_MODEL = "llama3.2:3b"
_REQUEST_TIMEOUT = 30  # seconds


class OllamaClient:
    """
    Thin client for the Ollama local inference server.

    If Ollama is unreachable and GEMINI_API_KEY is present in the environment,
    requests are transparently forwarded to the Google Gemini API.
    """

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (
            base_url
            or os.environ.get("OLLAMA_BASE_URL", _DEFAULT_OLLAMA_URL)
        ).rstrip("/")
        self._gemini_key: Optional[str] = os.environ.get("GEMINI_API_KEY")

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
        except Exception as exc:  # noqa: BLE001
            logger.debug("Ollama health check failed: %s", exc)
            return False

    def generate(self, prompt: str, model: str = _DEFAULT_MODEL) -> str:
        """
        Generate a text completion via Ollama.

        Falls back to Gemini if Ollama is unavailable.

        Parameters
        ----------
        prompt:
            The text prompt to send to the model.
        model:
            Ollama model tag (e.g. "llama3.2:3b").

        Returns
        -------
        Generated text string, or an error message if both backends fail.
        """
        if self.is_available():
            return self._ollama_generate(prompt, model)
        if self._gemini_key:
            logger.info("Ollama unavailable — falling back to Gemini.")
            return self._gemini_generate(prompt)
        return (
            "AI inference unavailable: Ollama server is unreachable and no "
            "GEMINI_API_KEY is configured."
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
        except Exception as exc:  # noqa: BLE001
            logger.error("Ollama generation failed: %s", exc)
            return f"Ollama error: {exc}"

    def _gemini_generate(self, prompt: str) -> str:
        """Forward the prompt to Google Gemini as a fallback."""
        try:
            import requests  # type: ignore
            model = "gemini-1.5-flash"
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={self._gemini_key}"
            )
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            resp = requests.post(url, json=payload, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                return " ".join(p.get("text", "") for p in parts).strip()
            return "Gemini returned no candidates."
        except Exception as exc:  # noqa: BLE001
            logger.error("Gemini fallback failed: %s", exc)
            return f"Gemini error: {exc}"
