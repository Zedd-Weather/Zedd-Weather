"""
Server-side local AI client (Ollama + Gemma).

Provides risk analysis, forecast analysis, and site-map generation via a local
Ollama server for non-cloud deployments.
"""
import json
import logging
import os
import asyncio
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

_DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
_DEFAULT_MODEL = "gemma2:2b"
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=45)

# Mirror of the frontend SECTOR_CONFIG so we can keep this module self-contained.
SECTOR_CONFIG: dict[str, dict[str, str]] = {
    "construction": {
        "label": "Construction",
        "description": "an industrial construction site",
        "focusAreas": (
            "structural risks, worker safety, material integrity, "
            "and construction-specific hazards"
        ),
    },
    "agricultural": {
        "label": "Agricultural",
        "description": "an agricultural farm or plantation",
        "focusAreas": (
            "crop health, irrigation needs, pest/disease risk, "
            "soil conditions, and weather stress on agriculture"
        ),
    },
    "industrial": {
        "label": "Industrial",
        "description": "an industrial manufacturing facility or plant",
        "focusAreas": (
            "equipment safety, process risks, supply chain disruption, "
            "air quality, and worker exposure limits"
        ),
    },
}

def _ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", _DEFAULT_OLLAMA_URL).rstrip("/")


def _ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", _DEFAULT_MODEL)


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or start >= end:
            return {}
        try:
            parsed = json.loads(text[start:end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


def _normalize_risk_level(level: Any) -> str:
    allowed = {"Green", "Amber", "Red", "Black"}
    text = str(level or "").strip().title()
    return text if text in allowed else "Amber"


async def _generate_text(prompt: str) -> str:
    payload = {
        "model": _ollama_model(),
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    url = f"{_ollama_base_url()}/api/generate"
    try:
        async with aiohttp.ClientSession(timeout=_REQUEST_TIMEOUT) as session:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                return str(data.get("response", "")).strip()
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        raise RuntimeError(
            f"Local Ollama request failed at {url}. "
            "Check OLLAMA_BASE_URL and that the Ollama server is running."
        ) from exc


async def analyze_risk(
    telemetry: dict[str, Any], sector: str
) -> dict[str, Any]:
    """
    Run AI-powered risk analysis on live telemetry for the given sector.

    Parameters
    ----------
    telemetry:
        Dict with keys: temp, humidity, pressure, precipitation, uvIndex, aqi, tide.
    sector:
        One of ``construction``, ``agricultural``, ``industrial``.

    Returns
    -------
    Dict with ``riskLevel`` (Green/Amber/Red/Black) and ``report`` (Markdown str).
    """
    cfg = SECTOR_CONFIG.get(sector, SECTOR_CONFIG["construction"])
    prompt = (
        f"You are a Principal Edge AI and IoT Systems Architect monitoring "
        f"{cfg['description']}.\n"
        f"Sector: {cfg['label']}.\n"
        f"Current LIVE micro-climate telemetry:\n"
        f"- Temperature: {telemetry.get('temp', 0):.1f}°C\n"
        f"- Humidity: {telemetry.get('humidity', 0):.1f}%\n"
        f"- Pressure: {telemetry.get('pressure', 0):.1f} hPa\n"
        f"- Precipitation: {telemetry.get('precipitation', 0):.0f}%\n"
        f"- UV Index: {telemetry.get('uvIndex', 0):.1f}\n"
        f"- AQI: {telemetry.get('aqi', 42):.0f}\n\n"
        f"Based purely on this real-time telemetry, identify any environmental "
        f"risks relevant to {cfg['description']}.\n"
        f"Focus on: {cfg['focusAreas']}.\n"
        f"Provide strict mitigation directives that will be cryptographically "
        f"signed to the ledger. Do not ask for images; base your analysis "
        f"solely on the data provided.\n\n"
        "Return only valid JSON with this shape:\n"
        '{"riskLevel":"Green|Amber|Red|Black","report":"Markdown report"}'
    )
    raw = await _generate_text(prompt)
    data = _extract_json_object(raw)
    return {
        "riskLevel": _normalize_risk_level(data.get("riskLevel")),
        "report": str(data.get("report", "")).strip(),
    }


async def analyze_forecast(
    forecast_data: list[dict[str, Any]], sector: str
) -> dict[str, Any]:
    """
    Run AI-powered risk analysis on a 7-day forecast for the given sector.

    Parameters
    ----------
    forecast_data:
        List of ForecastDay dicts (date, tempMax, tempMin, precip, wind, uv).
    sector:
        One of ``construction``, ``agricultural``, ``industrial``.

    Returns
    -------
    Dict with ``riskLevel`` and ``report``.
    """
    cfg = SECTOR_CONFIG.get(sector, SECTOR_CONFIG["construction"])
    prompt = (
        f"You are a Principal Edge AI and IoT Systems Architect monitoring "
        f"{cfg['description']}.\n"
        f"Sector: {cfg['label']}.\n"
        f"Here is the 7-day weather forecast for the site:\n"
        f"{json.dumps(forecast_data, indent=2)}\n\n"
        f"Analyze this forecast for any upcoming risks relevant to "
        f"{cfg['description']}.\n"
        f"Focus on: {cfg['focusAreas']}.\n"
        f"Provide strict mitigation directives that will be cryptographically "
        f"signed to the ledger.\n\n"
        "Return only valid JSON with this shape:\n"
        '{"riskLevel":"Green|Amber|Red|Black","report":"Markdown report"}'
    )
    raw = await _generate_text(prompt)
    data = _extract_json_object(raw)
    return {
        "riskLevel": _normalize_risk_level(data.get("riskLevel")),
        "report": str(data.get("report", "")).strip(),
    }


async def generate_site_map(lat: float, lng: float) -> dict[str, Any]:
    """
    Generate a site logistics report via local LLM.

    Parameters
    ----------
    lat, lng:
        Coordinates of the site.

    Returns
    -------
    Dict with ``report`` (Markdown str) and ``links`` (list of {uri, title}).
    """
    prompt = (
        "You are a site logistics assistant.\n"
        f"Given coordinates latitude={lat}, longitude={lng}, create a concise "
        "operations checklist for emergency access, hardware sourcing, and "
        "route planning assumptions.\n"
        "Do not invent real links. Keep output in Markdown."
    )
    try:
        report = await _generate_text(prompt)
    except RuntimeError as exc:
        logger.error("Local AI site-map generation failed: %s", exc)
        report = "Failed to generate local site logistics report."
    return {"report": report, "links": []}
