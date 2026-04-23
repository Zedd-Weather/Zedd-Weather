"""
Server-side Google Weather API client.

All calls are made server-side so the API key is never exposed to the browser.
Reads the key from the GOOGLE_WEATHER_API_KEY environment variable.
"""
import logging
import os
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

GOOGLE_WEATHER_BASE = "https://weather.googleapis.com/v1"
_DEFAULT_AQI = 42
_DEFAULT_TIDE = 1.2
_KMH_TO_MS_DIVISOR = 3.6  # divide km/h by this to get m/s


def _api_key() -> str:
    """Return the Google Weather API key from environment variables."""
    return os.getenv("GOOGLE_WEATHER_API_KEY", "")


async def get_current_conditions(lat: float, lng: float) -> dict[str, Any]:
    """
    Fetch current weather conditions and today's hourly forecast.

    Returns a dict with:
      - ``telemetry``  : TelemetryData-compatible dict
      - ``hourly``     : list of HourlyWeatherPoint-compatible dicts
    """
    key = _api_key()
    current_url = f"{GOOGLE_WEATHER_BASE}/currentConditions:lookup?key={key}"
    hourly_url = f"{GOOGLE_WEATHER_BASE}/forecast:lookup?key={key}"
    loc_body = {"location": {"latitude": lat, "longitude": lng}}

    async with aiohttp.ClientSession() as session:
        async with session.post(current_url, json=loc_body) as current_resp:
            current = await current_resp.json()
        async with session.post(
            hourly_url,
            json={**loc_body, "days": 1, "hourlyForHours": 24},
        ) as hourly_resp:
            hourly_raw = await hourly_resp.json()

    telemetry: dict[str, Any] = {
        "temp": (current.get("temperature") or {}).get("degrees", 0.0),
        "humidity": (current.get("humidity") or {}).get("percent", 0.0),
        "pressure": (current.get("pressure") or {}).get("meanSeaLevelMillibars", 0.0),
        "precipitation": (
            (current.get("precipitation") or {})
            .get("probability", {})
            .get("percent", 0.0)
        ),
        "uvIndex": current.get("uvIndex", 0.0),
        "aqi": (current.get("airQuality") or {}).get("aqi", _DEFAULT_AQI),
        "tide": _DEFAULT_TIDE,
    }

    hourly: list[dict[str, Any]] = [
        {
            "time": h.get("displayDateTime", ""),
            "temp": (h.get("temperature") or {}).get("degrees", 0.0),
            "humidity": (h.get("humidity") or {}).get("percent", 0.0),
            "pressure": (h.get("pressure") or {}).get("meanSeaLevelMillibars", 0.0),
        }
        for h in hourly_raw.get("forecastHours", [])
    ]

    return {"telemetry": telemetry, "hourly": hourly}


async def get_forecast(lat: float, lng: float, days: int = 7) -> list[dict[str, Any]]:
    """
    Fetch a multi-day daily forecast.

    Returns a list of ForecastDay-compatible dicts:
      date, tempMax, tempMin, precip (%), wind (m/s), uv.
    """
    key = _api_key()
    url = f"{GOOGLE_WEATHER_BASE}/forecast:lookup?key={key}"

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json={
                "location": {"latitude": lat, "longitude": lng},
                "days": days,
            },
        ) as resp:
            data = await resp.json()

    result: list[dict[str, Any]] = []
    for day in data.get("forecastDays", []):
        daytime = day.get("daytimeForecast") or {}
        overnight = day.get("overnightForecast") or {}
        wind_kmh = (daytime.get("wind") or {}).get("speed", {}).get("value", 0.0) or 0.0
        result.append(
            {
                "date": day.get("displayDate", ""),
                "tempMax": (daytime.get("temperature") or {}).get("degrees", 0.0),
                "tempMin": (overnight.get("temperature") or {}).get("degrees", 0.0),
                "precip": (
                    (daytime.get("precipitation") or {})
                    .get("probability", {})
                    .get("percent", 0.0)
                ),
                "wind": wind_kmh / _KMH_TO_MS_DIVISOR,
                "uv": daytime.get("uvIndex", 0.0),
            }
        )
    return result


async def get_history(
    lat: float, lng: float, days: int = 7
) -> list[dict[str, Any]]:
    """
    Fetch historical hourly weather data, sampled by day range.

    Returns a list of HistoricalDataPoint-compatible dicts:
      time, temp, humidity, pressure, precipitation (%).
    """
    key = _api_key()
    url = f"{GOOGLE_WEATHER_BASE}/history:lookup?key={key}"

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json={
                "location": {"latitude": lat, "longitude": lng},
                "days": days,
                "hourly": True,
            },
        ) as resp:
            data = await resp.json()

    step = 6 if days <= 7 else (12 if days <= 14 else 24)
    result: list[dict[str, Any]] = []
    for i, h in enumerate(data.get("historyHours", [])):
        if i % step != 0:
            continue
        result.append(
            {
                "time": h.get("displayDateTime", ""),
                "temp": (h.get("temperature") or {}).get("degrees", 0.0),
                "humidity": (h.get("humidity") or {}).get("percent", 0.0),
                "pressure": (h.get("pressure") or {}).get("meanSeaLevelMillibars", 0.0),
                "precipitation": (
                    (h.get("precipitation") or {})
                    .get("probability", {})
                    .get("percent", 0.0)
                ),
            }
        )
    return result
