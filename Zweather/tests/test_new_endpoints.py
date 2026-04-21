"""
Tests for the new Python-frontend API endpoints added in the refactor:
  POST /api/telemetry/ingest
  GET  /api/telemetry/latest
  GET  /api/weather/current  (mocked)
  GET  /api/weather/forecast (mocked)
  GET  /api/weather/history  (mocked)
  POST /api/ai/risk          (mocked)
  POST /api/ai/forecast      (mocked)
  POST /api/ai/sitemap       (mocked)
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import Zweather.api as api_module
from Zweather.api import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_telemetry_store():
    """Ensure the in-memory telemetry store is empty before every test."""
    with api_module._telemetry_lock:
        api_module._latest_telemetry.clear()
    yield
    with api_module._telemetry_lock:
        api_module._latest_telemetry.clear()

# ---------------------------------------------------------------------------
# Sensor Telemetry Ingest / Latest
# ---------------------------------------------------------------------------

class TestTelemetryIngest:
    def _payload(self, **kwargs):
        base = {
            "temperature": 24.5,
            "humidity": 55.0,
            "pressure": 1010.5,
        }
        base.update(kwargs)
        return base

    def test_latest_returns_null_before_any_ingest(self):
        resp = client.get("/api/telemetry/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["telemetry"] is None
        assert data["timestamp"] is None

    def test_ingest_returns_202(self):
        resp = client.post("/api/telemetry/ingest", json=self._payload())
        assert resp.status_code == 202
        data = resp.json()
        assert data["accepted"] is True
        assert "timestamp" in data

    def test_ingest_optional_fields(self):
        payload = self._payload(
            precipitation=30.0,
            uv_index=4.5,
            aqi=60.0,
            tide=1.1,
            wind_speed=5.2,
            node_id="node1-sensehat",
        )
        resp = client.post("/api/telemetry/ingest", json=payload)
        assert resp.status_code == 202

    def test_latest_after_ingest(self):
        client.post("/api/telemetry/ingest", json=self._payload(temperature=30.0, humidity=70.0, pressure=1005.0))
        resp = client.get("/api/telemetry/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["telemetry"] is not None
        assert data["telemetry"]["temp"] == pytest.approx(30.0)
        assert data["telemetry"]["humidity"] == pytest.approx(70.0)

    def test_latest_node_id_stored(self):
        client.post("/api/telemetry/ingest", json=self._payload(node_id="pi-node-c"))
        resp = client.get("/api/telemetry/latest")
        assert resp.json()["node_id"] == "pi-node-c"


# ---------------------------------------------------------------------------
# Weather proxy endpoints (mocked — no real API key in tests)
# ---------------------------------------------------------------------------

_MOCK_CURRENT = {
    "telemetry": {"temp": 21.0, "humidity": 50.0, "pressure": 1013.0, "precipitation": 10.0, "uvIndex": 3.0, "aqi": 42.0, "tide": 1.2},
    "hourly": [{"time": "00:00", "temp": 20.0, "humidity": 52.0, "pressure": 1012.0}],
}
_MOCK_FORECAST = [{"date": "Mon", "tempMax": 25.0, "tempMin": 15.0, "precip": 20.0, "wind": 3.5, "uv": 4.0}]
_MOCK_HISTORY = [{"time": "2025-01-01", "temp": 18.0, "humidity": 60.0, "pressure": 1011.0, "precipitation": 5.0}]


class TestWeatherProxy:
    def test_current_success(self):
        with patch("Zweather.weather_client.get_current_conditions", new_callable=AsyncMock, return_value=_MOCK_CURRENT):
            resp = client.get("/api/weather/current", params={"lat": 37.77, "lng": -122.41})
        assert resp.status_code == 200
        data = resp.json()
        assert "telemetry" in data
        assert "hourly" in data

    def test_forecast_success(self):
        with patch("Zweather.weather_client.get_forecast", new_callable=AsyncMock, return_value=_MOCK_FORECAST):
            resp = client.get("/api/weather/forecast", params={"lat": 37.77, "lng": -122.41, "days": 7})
        assert resp.status_code == 200
        assert "forecast" in resp.json()

    def test_history_success(self):
        with patch("Zweather.weather_client.get_history", new_callable=AsyncMock, return_value=_MOCK_HISTORY):
            resp = client.get("/api/weather/history", params={"lat": 37.77, "lng": -122.41, "days": 7})
        assert resp.status_code == 200
        assert "history" in resp.json()

    def test_current_missing_lat_returns_422(self):
        resp = client.get("/api/weather/current", params={"lng": -122.41})
        assert resp.status_code == 422

    def test_forecast_days_out_of_range_returns_422(self):
        resp = client.get("/api/weather/forecast", params={"lat": 37.77, "lng": -122.41, "days": 99})
        assert resp.status_code == 422

    def test_history_days_out_of_range_returns_422(self):
        resp = client.get("/api/weather/history", params={"lat": 37.77, "lng": -122.41, "days": 31})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# AI endpoints (mocked — no real local model call in tests)
# ---------------------------------------------------------------------------

_MOCK_RISK = {"riskLevel": "Amber", "report": "## Risk Report\nModerate risk detected.", "timestamp": "2025-01-01T00:00:00+00:00"}
_MOCK_FORECAST_AI = {"riskLevel": "Green", "report": "## Forecast Risk\nLow risk over next 7 days.", "timestamp": "2025-01-01T00:00:00+00:00"}
_MOCK_SITEMAP = {"report": "## Site Map\nNearby: Fire Station 5 (0.8 km)", "links": [{"uri": "https://maps.example.com/1", "title": "Fire Station 5"}], "timestamp": "2025-01-01T00:00:00+00:00"}


class TestAIEndpoints:
    def _telemetry_body(self):
        return {"temp": 25.0, "humidity": 60.0, "pressure": 1013.0}

    def test_ai_risk_construction(self):
        with patch("Zweather.ai_client.analyze_risk", new_callable=AsyncMock, return_value=_MOCK_RISK):
            resp = client.post("/api/ai/risk", json={"telemetry": self._telemetry_body(), "sector": "construction"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["riskLevel"] in ("Green", "Amber", "Red", "Black")
        assert "report" in data

    def test_ai_risk_agricultural(self):
        with patch("Zweather.ai_client.analyze_risk", new_callable=AsyncMock, return_value=_MOCK_RISK):
            resp = client.post("/api/ai/risk", json={"telemetry": self._telemetry_body(), "sector": "agricultural"})
        assert resp.status_code == 200

    def test_ai_risk_industrial(self):
        with patch("Zweather.ai_client.analyze_risk", new_callable=AsyncMock, return_value=_MOCK_RISK):
            resp = client.post("/api/ai/risk", json={"telemetry": self._telemetry_body(), "sector": "industrial"})
        assert resp.status_code == 200

    def test_ai_forecast_analysis(self):
        with patch("Zweather.ai_client.analyze_forecast", new_callable=AsyncMock, return_value=_MOCK_FORECAST_AI):
            resp = client.post(
                "/api/ai/forecast",
                json={"forecast_data": _MOCK_FORECAST, "sector": "construction"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "riskLevel" in data and "report" in data

    def test_ai_sitemap(self):
        with patch("Zweather.ai_client.generate_site_map", new_callable=AsyncMock, return_value=_MOCK_SITEMAP):
            resp = client.post("/api/ai/sitemap", json={"lat": 37.77, "lng": -122.41})
        assert resp.status_code == 200
        data = resp.json()
        assert "report" in data and "links" in data

    def test_ai_risk_missing_telemetry_returns_422(self):
        resp = client.post("/api/ai/risk", json={"sector": "construction"})
        assert resp.status_code == 422
