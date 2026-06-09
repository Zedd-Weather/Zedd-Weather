"""
Tests for the Google Weather API client.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from Zweather.weather_client import (
    GoogleWeatherAPIError,
    get_current_conditions,
    get_forecast,
    get_history,
)


pytestmark = pytest.mark.asyncio


def _resp_mock(status: int = 200, json_data: dict | None = None) -> AsyncMock:
    """Build an async context manager mock for an HTTP response."""
    resp = AsyncMock()
    resp.status = status
    resp.json.return_value = json_data or {}
    # async with resp as r:  →  r = await resp.__aenter__()  →  return resp
    resp.__aenter__.return_value = resp
    return resp


class TestWeatherClient:
    @patch("Zweather.weather_client._get_session")
    async def test_get_current_conditions_success(self, mock_session_factory):
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session

        current = _resp_mock(200, {
            "temperature": {"degrees": 22.5},
            "humidity": {"percent": 60.0},
            "pressure": {"meanSeaLevelMillibars": 1015.0},
            "precipitation": {"probability": {"percent": 10.0}},
            "uvIndex": 3.0,
            "airQuality": {"aqi": 42},
        })
        hourly = _resp_mock(200, {
            "forecastHours": [
                {
                    "displayDateTime": "2025-01-01T12:00:00Z",
                    "temperature": {"degrees": 23.0},
                    "humidity": {"percent": 55.0},
                    "pressure": {"meanSeaLevelMillibars": 1014.0},
                }
            ]
        })
        mock_session.post.side_effect = [current, hourly]

        result = await get_current_conditions(51.5, -0.1)
        assert result["telemetry"]["temp"] == 22.5
        assert result["telemetry"]["humidity"] == 60.0
        assert result["telemetry"]["pressure"] == 1015.0
        assert result["telemetry"]["precipitation"] == 10.0
        assert len(result["hourly"]) == 1
        assert result["hourly"][0]["temp"] == 23.0

    @patch("Zweather.weather_client._get_session")
    async def test_get_current_conditions_api_error(self, mock_session_factory):
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session
        mock_session.post.return_value = _resp_mock(403)
        with pytest.raises(GoogleWeatherAPIError, match="Current conditions returned 403"):
            await get_current_conditions(51.5, -0.1)

    @patch("Zweather.weather_client._get_session")
    async def test_get_forecast_success(self, mock_session_factory):
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session
        mock_session.post.return_value = _resp_mock(200, {
            "forecastDays": [
                {
                    "displayDate": "2025-01-01",
                    "daytimeForecast": {
                        "temperature": {"degrees": 20.0},
                        "precipitation": {"probability": {"percent": 30.0}},
                        "wind": {"speed": {"value": 18.0}},
                        "uvIndex": 2.0,
                    },
                    "overnightForecast": {
                        "temperature": {"degrees": 10.0},
                    },
                }
            ]
        })
        result = await get_forecast(51.5, -0.1, days=3)
        assert len(result) == 1
        assert result[0]["date"] == "2025-01-01"
        assert result[0]["tempMax"] == 20.0
        assert result[0]["tempMin"] == 10.0
        assert result[0]["precip"] == 30.0
        assert result[0]["wind"] == 5.0

    @patch("Zweather.weather_client._get_session")
    async def test_get_forecast_api_error(self, mock_session_factory):
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session
        mock_session.post.return_value = _resp_mock(500)
        with pytest.raises(GoogleWeatherAPIError, match="Forecast returned 500"):
            await get_forecast(51.5, -0.1, days=7)

    @patch("Zweather.weather_client._get_session")
    async def test_get_history_success(self, mock_session_factory):
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session
        mock_session.post.return_value = _resp_mock(200, {
            "historyHours": [
                {
                    "displayDateTime": "2025-01-01T00:00:00Z",
                    "temperature": {"degrees": 5.0},
                    "humidity": {"percent": 80.0},
                    "pressure": {"meanSeaLevelMillibars": 1020.0},
                    "precipitation": {"probability": {"percent": 20.0}},
                },
                {
                    "displayDateTime": "2025-01-01T01:00:00Z",
                    "temperature": {"degrees": 4.5},
                    "humidity": {"percent": 82.0},
                    "pressure": {"meanSeaLevelMillibars": 1019.0},
                    "precipitation": {"probability": {"percent": 25.0}},
                },
            ]
        })
        result = await get_history(51.5, -0.1, days=1)
        assert len(result) == 1
        assert result[0]["temp"] == 5.0

    @patch("Zweather.weather_client._get_session")
    async def test_get_history_api_error(self, mock_session_factory):
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session
        mock_session.post.return_value = _resp_mock(401)
        with pytest.raises(GoogleWeatherAPIError, match="History returned 401"):
            await get_history(51.5, -0.1, days=7)

    @patch("Zweather.weather_client._get_session")
    async def test_get_current_conditions_defaults_on_missing_fields(self, mock_session_factory):
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session

        current = _resp_mock(200, {})
        hourly = _resp_mock(200, {"forecastHours": []})
        mock_session.post.side_effect = [current, hourly]

        result = await get_current_conditions(51.5, -0.1)
        assert result["telemetry"]["temp"] == 0.0
        assert result["telemetry"]["humidity"] == 0.0
        assert result["telemetry"]["aqi"] == 42
        assert result["hourly"] == []

    @patch("Zweather.weather_client._get_session")
    async def test_get_forecast_empty(self, mock_session_factory):
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session
        mock_session.post.return_value = _resp_mock(200, {"forecastDays": []})
        result = await get_forecast(51.5, -0.1)
        assert result == []

    @patch("Zweather.weather_client._get_session")
    async def test_get_history_empty(self, mock_session_factory):
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session
        mock_session.post.return_value = _resp_mock(200, {"historyHours": []})
        result = await get_history(51.5, -0.1, days=7)
        assert result == []
