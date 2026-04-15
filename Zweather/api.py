"""
Zedd Weather — FastAPI REST API

Exposes the sector-specific heuristic engines and alert rules via HTTP
endpoints. This allows the React frontend to get structured risk analysis
without requiring a Gemini API key.

Usage:
    uvicorn Zweather.api:app --host 0.0.0.0 --port 8000
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from Zweather.construction.engine import ConstructionEngine
from Zweather.agricultural.engine import AgriculturalEngine
from Zweather.industrial.engine import IndustrialEngine
from Zweather.alerting.rules import AlertRulesEngine

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Zedd Weather API",
    description="Sector-specific weather risk analysis and alert evaluation",
    version="1.0.0",
)

# Allow the React frontend (dev server on :5173 or production)
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
