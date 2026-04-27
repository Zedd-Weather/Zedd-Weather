"""
Zedd Weather — FastAPI REST API

Exposes the sector-specific heuristic engines, alert rules, server-side
weather data proxying, AI risk analysis, and sensor telemetry ingestion via
HTTP endpoints.

The Python Dash frontend (Zweather/dashboard/app.py) and sensor nodes both
talk to this API, keeping all external API keys server-side.

Usage:
    uvicorn Zweather.api:app --host 0.0.0.0 --port 8000
"""
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from Zweather.construction.engine import ConstructionEngine
from Zweather.agricultural.engine import AgriculturalEngine
from Zweather.industrial.engine import IndustrialEngine
from Zweather.alerting.rules import AlertRulesEngine
from Zweather.sovereign import (
    MAX_DEPTH,
    MAX_PROOF_SIZE,
    PROTOCOL_TAG,
    ComposeTransitionRequest,
    SovereignWeatherEngine,
    WeatherTransition,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Zedd Weather API",
    description="Sector-specific weather risk analysis and alert evaluation",
    version="1.0.0",
)

# Allow the Dash frontend (dev server on :8050 or production deployments)
# to call the API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton engine instances
_construction_engine = ConstructionEngine()
_agricultural_engine = AgriculturalEngine()
_industrial_engine = IndustrialEngine()
_alert_engine = AlertRulesEngine()
_sovereign_engine = SovereignWeatherEngine()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class TelemetryPayload(BaseModel):
    """Weather telemetry data from sensors or Google Weather API."""
    temperature: float = Field(..., description="Temperature in °C")
    humidity: float = Field(..., description="Relative humidity in %")
    pressure: float = Field(..., description="Atmospheric pressure in hPa")
    wind_speed: Optional[float] = Field(None, description="Wind speed in m/s")
    uv_index: Optional[float] = Field(None, description="UV index")
    rainfall_mm: Optional[float] = Field(None, description="Rainfall in mm")
    aqi: Optional[float] = Field(None, description="Air quality index")

class AnalyzeRequest(BaseModel):
    """Request body for the /api/analyze endpoint."""
    telemetry: TelemetryPayload
    sector: str = Field("construction", description="One of: construction, agricultural, industrial")
    activity: Optional[str] = Field(None, description="Sector-specific activity/crop/facility type")

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str


class SovereignProtocolInfo(BaseModel):
    protocol_tag: str
    max_depth: int
    max_proof_size: int
    accepted_phases: list[str]
    compatibility_tooling: bool
    compatibility_endpoints: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse)
def health_check():
    """Service health check."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
    )


@app.get("/api/sovereign/protocol", response_model=SovereignProtocolInfo)
def get_sovereign_protocol():
    """
    Describe the RMPE-2 sovereign weather protocol exposed by compatibility tooling.
    """
    return SovereignProtocolInfo(
        protocol_tag=PROTOCOL_TAG,
        max_depth=MAX_DEPTH,
        max_proof_size=MAX_PROOF_SIZE,
        accepted_phases=["data_entry", "consensus", "distribution", "settlement"],
        compatibility_tooling=True,
        compatibility_endpoints=[
            "/api/telemetry/ingest",
            "/api/telemetry/latest",
            "/api/weather/current",
            "/api/weather/forecast",
            "/api/weather/history",
        ],
    )


@app.post("/api/sovereign/compose")
def compose_sovereign_transition(request: ComposeTransitionRequest):
    """
    Compose an RMPE-2 weather coin transition from operator-tooling inputs.
    """
    transition = _sovereign_engine.compose_transition(request)
    validation = _sovereign_engine.validate_transition(transition)
    return {
        "transition": transition.model_dump(),
        "validation": validation.model_dump(),
    }


@app.post("/api/sovereign/validate")
def validate_sovereign_transition(transition: WeatherTransition):
    """
    Validate a weather coin transition from PREVSTATE and proof inputs alone.
    """
    validation = _sovereign_engine.validate_transition(transition)
    return validation.model_dump()


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest):
    """
    Run sector-specific risk analysis on the provided telemetry data.

    Returns structured analysis results from the appropriate heuristic engine.
    No AI API key required — uses local rule-based engines.
    """
    telemetry_dict = {
        "temperature": request.telemetry.temperature,
        "humidity": request.telemetry.humidity,
        "pressure": request.telemetry.pressure,
    }
    # Add optional fields if present
    if request.telemetry.wind_speed is not None:
        telemetry_dict["wind_speed"] = request.telemetry.wind_speed
    if request.telemetry.uv_index is not None:
        telemetry_dict["uv_index"] = request.telemetry.uv_index
    if request.telemetry.rainfall_mm is not None:
        telemetry_dict["rainfall_mm"] = request.telemetry.rainfall_mm
    if request.telemetry.aqi is not None:
        telemetry_dict["aqi"] = request.telemetry.aqi

    sector = request.sector.lower()
    activity = request.activity

    try:
        if sector == "construction":
            result = _construction_engine.analyze(telemetry_dict, activity or "general")
        elif sector == "agricultural":
            result = _agricultural_engine.analyze(telemetry_dict, activity or "maize")
        elif sector == "industrial":
            result = _industrial_engine.analyze(telemetry_dict, activity or "general")
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown sector: '{sector}'. Must be one of: construction, agricultural, industrial"
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Analysis failed for sector=%s", sector)
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "sector": sector,
        "analysis": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/alerts")
def evaluate_alerts(payload: TelemetryPayload):
    """
    Evaluate alert rules against the provided telemetry data.

    Returns any triggered alerts sorted by severity.
    """
    telemetry_dict = {
        "temperature": payload.temperature,
        "humidity": payload.humidity,
        "pressure": payload.pressure,
    }

    alerts = _alert_engine.evaluate(telemetry_dict)

    return {
        "alerts": [
            {
                "id": alert.id,
                "severity": alert.severity.value,
                "title": alert.title,
                "message": alert.message,
                "metric": alert.metric,
                "value": alert.value,
                "threshold": alert.threshold,
            }
            for alert in alerts
        ],
        "count": len(alerts),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Sensor Telemetry Ingest (Python sensors / MQTT bridge push data here)
# ---------------------------------------------------------------------------

# In-memory store protected by a lock for thread-safe access.
_telemetry_lock = threading.Lock()
_latest_telemetry: dict[str, Any] = {}


class SensorTelemetryPayload(BaseModel):
    """Payload posted by sensor nodes (Sense HAT, Enviro+, Modbus, etc.)."""

    temperature: float = Field(..., description="Temperature in °C")
    humidity: float = Field(..., description="Relative humidity in %")
    pressure: float = Field(..., description="Atmospheric pressure in hPa")
    precipitation: Optional[float] = Field(None, description="Precipitation probability %")
    uv_index: Optional[float] = Field(None, description="UV index")
    aqi: Optional[float] = Field(None, description="Air quality index")
    tide: Optional[float] = Field(None, description="Tide / wave level in m")
    wind_speed: Optional[float] = Field(None, description="Wind speed in m/s")
    node_id: Optional[str] = Field(None, description="Sensor node identifier")


@app.post("/api/telemetry/ingest", status_code=202)
def ingest_telemetry(payload: SensorTelemetryPayload):
    """
    Accept a telemetry snapshot from a sensor node (Node 1 Sense HAT, Enviro+,
    Modbus, or any MQTT-bridged device).

    The stored snapshot is served back by ``GET /api/telemetry/latest`` so the
    Python Dash frontend can display live onboard-sensor readings without
    requiring direct MQTT access.
    """
    reading: dict[str, Any] = {
        "temp": payload.temperature,
        "humidity": payload.humidity,
        "pressure": payload.pressure,
        "precipitation": payload.precipitation or 0.0,
        "uvIndex": payload.uv_index or 0.0,
        "aqi": payload.aqi or 42.0,
        "tide": payload.tide or 1.2,
        "wind_speed": payload.wind_speed,
    }
    with _telemetry_lock:
        _latest_telemetry.update(
            {
                "telemetry": reading,
                "node_id": payload.node_id or "unknown",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "hourly": [],  # sensor push does not include hourly forecast
            }
        )
    return {"accepted": True, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/telemetry/latest")
def get_latest_telemetry():
    """
    Return the most recent telemetry snapshot pushed by a sensor node.

    If no sensor has pushed data yet, returns ``{"telemetry": null}`` so
    the frontend knows to fall back to the external weather API.
    """
    with _telemetry_lock:
        if not _latest_telemetry:
            return {"telemetry": None, "timestamp": None}
        return dict(_latest_telemetry)


# ---------------------------------------------------------------------------
# Server-side Google Weather API proxy
# ---------------------------------------------------------------------------


@app.get("/api/weather/current")
async def weather_current(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
):
    """
    Fetch current conditions + today's hourly forecast from Google Weather API.

    The API key is read server-side from ``GOOGLE_WEATHER_API_KEY`` so it is
    never exposed to the browser.
    """
    try:
        from Zweather.weather_client import get_current_conditions

        return await get_current_conditions(lat, lng)
    except Exception as exc:
        logger.exception("weather_current failed")
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/weather/forecast")
async def weather_forecast(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    days: int = Query(7, ge=1, le=10, description="Number of forecast days"),
):
    """
    Fetch a multi-day daily forecast from Google Weather API.
    """
    try:
        from Zweather.weather_client import get_forecast

        return {"forecast": await get_forecast(lat, lng, days)}
    except Exception as exc:
        logger.exception("weather_forecast failed")
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/weather/history")
async def weather_history(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    days: int = Query(7, ge=1, le=30, description="Number of history days"),
):
    """
    Fetch historical hourly weather data from Google Weather API.
    """
    try:
        from Zweather.weather_client import get_history

        return {"history": await get_history(lat, lng, days)}
    except Exception as exc:
        logger.exception("weather_history failed")
        raise HTTPException(status_code=502, detail=str(exc))


# ---------------------------------------------------------------------------
# Server-side AI endpoints (local Ollama / Gemma)
# ---------------------------------------------------------------------------


class AITelemetryPayload(BaseModel):
    """Telemetry payload for AI risk analysis (uses dashboard field names)."""

    temp: float = Field(..., description="Temperature in °C")
    humidity: float = Field(..., description="Relative humidity in %")
    pressure: float = Field(..., description="Atmospheric pressure in hPa")
    precipitation: float = Field(0.0, description="Precipitation probability %")
    uvIndex: float = Field(0.0, description="UV index")
    aqi: float = Field(42.0, description="Air quality index")
    tide: float = Field(1.2, description="Tide / wave level in m")


class AIRiskRequest(BaseModel):
    """Request body for ``POST /api/ai/risk``."""

    telemetry: AITelemetryPayload
    sector: str = Field(
        "construction",
        description="One of: construction, agricultural, industrial",
    )


@app.post("/api/ai/risk")
async def ai_risk_analysis(request: AIRiskRequest):
    """
    Run local Ollama/Gemma AI risk analysis on live telemetry.

    Requires local Ollama to be reachable via ``OLLAMA_BASE_URL``.
    Returns ``{riskLevel, report, timestamp}``.
    """
    try:
        from Zweather.ai_client import analyze_risk

        result = await analyze_risk(
            telemetry=request.telemetry.model_dump(),
            sector=request.sector.lower(),
        )
        return {**result, "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        logger.exception("ai_risk_analysis failed")
        raise HTTPException(status_code=502, detail=str(exc))


class AIForecastRequest(BaseModel):
    """Request body for ``POST /api/ai/forecast``."""

    forecast_data: list[dict[str, Any]] = Field(
        ..., description="List of ForecastDay objects"
    )
    sector: str = Field(
        "construction",
        description="One of: construction, agricultural, industrial",
    )


@app.post("/api/ai/forecast")
async def ai_forecast_analysis(request: AIForecastRequest):
    """
    Run local Ollama/Gemma AI analysis on a 7-day forecast.

    Returns ``{riskLevel, report, timestamp}``.
    """
    try:
        from Zweather.ai_client import analyze_forecast

        result = await analyze_forecast(
            forecast_data=request.forecast_data,
            sector=request.sector.lower(),
        )
        return {**result, "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        logger.exception("ai_forecast_analysis failed")
        raise HTTPException(status_code=502, detail=str(exc))


class AISiteMapRequest(BaseModel):
    """Request body for ``POST /api/ai/sitemap``."""

    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")


@app.post("/api/ai/sitemap")
async def ai_site_map(request: AISiteMapRequest):
    """
    Generate a site logistics map report via local Ollama/Gemma inference.

    Returns ``{report, links, timestamp}``.
    """
    try:
        from Zweather.ai_client import generate_site_map

        result = await generate_site_map(request.lat, request.lng)
        return {**result, "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        logger.exception("ai_site_map failed")
        raise HTTPException(status_code=502, detail=str(exc))
