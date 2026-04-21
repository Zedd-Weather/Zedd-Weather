"""
Zedd Weather — Python Dash Dashboard

A full Python frontend that replaces the React/TypeScript UI.  All external
API calls (Google Weather API, local Ollama/Gemma AI) are made server-side through the
FastAPI backend, so no API keys are ever sent to the browser.

Architecture
------------
::

    Browser
      ↕  (HTTP / JSON)
    Dash app  (this file, port 8050)
      ↕  (HTTP / JSON)
    FastAPI backend  (Zweather/api.py, port 8000)
      ↕
    Google Weather API · Ollama/Gemma AI · Sensor nodes (MQTT → /api/telemetry/ingest)

Usage
-----
::

    python -m Zweather.dashboard.app
    # or via uvicorn (production):
    # uvicorn Zweather.dashboard.app:server --port 8050

Environment variables
---------------------
API_BASE_URL
    Base URL of the FastAPI backend (default: http://localhost:8000).
DASH_PORT
    Port for the Dash dev server (default: 8050).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import requests
from dash import Input, Output, State, callback, ctx, dcc, html, no_update

logger = logging.getLogger(__name__)

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
DEFAULT_LAT = 37.7749
DEFAULT_LNG = -122.4194

# ---------------------------------------------------------------------------
# Colour palette (mirrors the React dark theme)
# ---------------------------------------------------------------------------
C = {
    "bg": "#0a0a0a",
    "card": "#111111",
    "card2": "#1a1a1a",
    "slate800": "#1e293b",
    "slate700": "#334155",
    "slate400": "#94a3b8",
    "slate300": "#cbd5e1",
    "slate200": "#e2e8f0",
    "emerald": "#10b981",
    "emerald_dim": "rgba(16,185,129,0.15)",
    "amber": "#f59e0b",
    "amber_dim": "rgba(245,158,11,0.1)",
    "rose": "#f43f5e",
    "rose_dim": "rgba(244,63,94,0.1)",
    "indigo": "#6366f1",
    "indigo_dim": "rgba(99,102,241,0.15)",
    "text": "#e2e8f0",
}

RISK_COLORS: dict[str, dict[str, str]] = {
    "Green": {"fg": "#22c55e", "bg": "rgba(34,197,94,0.12)", "border": "rgba(34,197,94,0.3)"},
    "Amber": {"fg": "#f59e0b", "bg": "rgba(245,158,11,0.12)", "border": "rgba(245,158,11,0.3)"},
    "Red": {"fg": "#ef4444", "bg": "rgba(239,68,68,0.12)", "border": "rgba(239,68,68,0.3)"},
    "Black": {"fg": "#9ca3af", "bg": "rgba(156,163,175,0.12)", "border": "rgba(156,163,175,0.3)"},
}

SECTOR_OPTIONS = [
    {"label": "🏗️  Construction", "value": "construction"},
    {"label": "🌾  Agricultural", "value": "agricultural"},
    {"label": "🏭  Industrial", "value": "industrial"},
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.warning("API GET %s failed: %s", path, exc)
        return None


def _api_post(path: str, data: dict[str, Any]) -> Any:
    try:
        r = requests.post(f"{API_BASE}{path}", json=data, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.warning("API POST %s failed: %s", path, exc)
        return None


def _card_style(**extra: Any) -> dict[str, Any]:
    return {
        "backgroundColor": C["card"],
        "border": f"1px solid {C['slate800']}",
        "borderRadius": "10px",
        "padding": "16px",
        **extra,
    }


def _btn(label: str, btn_id: str, color: str = C["emerald"], **kw: Any) -> html.Button:
    return html.Button(
        label,
        id=btn_id,
        n_clicks=0,
        style={
            "backgroundColor": color,
            "color": "#fff" if color != C["slate800"] else C["slate300"],
            "border": "none" if color != C["slate800"] else f"1px solid {C['slate800']}",
            "borderRadius": "7px",
            "padding": "8px 16px",
            "cursor": "pointer",
            "fontSize": "12px",
            "fontWeight": "500",
            **kw,
        },
    )


def _chart_layout(title: str = "", height: int = 240) -> dict[str, Any]:
    return dict(
        paper_bgcolor=C["card"],
        plot_bgcolor=C["card2"],
        font=dict(color=C["slate400"], size=11),
        title=dict(text=title, font=dict(size=13, color=C["slate200"])) if title else None,
        xaxis=dict(gridcolor=C["slate800"], linecolor=C["slate800"], tickfont=dict(size=10)),
        yaxis=dict(gridcolor=C["slate800"], linecolor=C["slate800"], tickfont=dict(size=10)),
        margin=dict(l=44, r=12, t=36 if title else 12, b=36),
        legend=dict(orientation="h", x=0, y=-0.18, font=dict(size=10)),
        hovermode="x unified",
        height=height,
    )


def _risk_badge(level: str | None) -> html.Div:
    col = RISK_COLORS.get(level or "Amber", RISK_COLORS["Amber"])
    return html.Div(
        [
            html.Span(
                level or "Unknown",
                style={
                    "color": col["fg"],
                    "backgroundColor": col["bg"],
                    "border": f"1px solid {col['border']}",
                    "borderRadius": "6px",
                    "padding": "4px 14px",
                    "fontSize": "13px",
                    "fontWeight": "700",
                    "textTransform": "uppercase",
                    "letterSpacing": "0.08em",
                },
            )
        ],
        style={"marginBottom": "12px"},
    )


# ---------------------------------------------------------------------------
# Per-tab layouts
# ---------------------------------------------------------------------------

def _weather_layout() -> html.Div:
    return html.Div(
        [
            # Controls row
            html.Div(
                [
                    dbc.RadioItems(
                        id="telemetry-source",
                        options=[
                            {"label": "🔌 Onboard Sensors", "value": "onboard"},
                            {"label": "🌐 External (Google Weather)", "value": "external"},
                        ],
                        value="onboard",
                        inline=True,
                        style={"color": C["slate400"], "fontSize": "12px"},
                    ),
                    html.Div(
                        [
                            html.Span(id="telemetry-updated", style={"fontSize": "11px", "color": C["slate400"], "marginRight": "8px"}),
                            _btn("↺  Refresh", "refresh-btn", C["slate800"]),
                        ],
                        style={"display": "flex", "alignItems": "center"},
                    ),
                ],
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "16px"},
            ),
            # Metric cards
            html.Div(id="metric-cards", style={"display": "grid", "gridTemplateColumns": "repeat(auto-fill,minmax(155px,1fr))", "gap": "12px", "marginBottom": "20px"}),
            # Hourly chart
            html.Div(
                [html.H3("24-Hour Trend", style={"fontSize": "13px", "color": C["slate200"], "marginBottom": "10px", "fontWeight": "600"}),
                 dcc.Graph(id="hourly-chart", config={"displayModeBar": False})],
                style={**_card_style(), "marginBottom": "16px"},
            ),
            # Historical chart + range
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("Historical Data", style={"fontSize": "13px", "color": C["slate200"], "marginBottom": "0", "fontWeight": "600"}),
                            dbc.RadioItems(
                                id="hist-range",
                                options=[{"label": "7d", "value": "7"}, {"label": "14d", "value": "14"}, {"label": "30d", "value": "30"}],
                                value="7",
                                inline=True,
                                style={"fontSize": "11px", "color": C["slate400"]},
                            ),
                        ],
                        style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "12px"},
                    ),
                    dcc.Loading(dcc.Graph(id="hist-chart", config={"displayModeBar": False}), type="circle", color=C["emerald"]),
                ],
                style=_card_style(),
            ),
        ]
    )


def _safety_layout() -> html.Div:
    return html.Div(
        [
            # Sub-view toggle
            html.Div(
                [
                    _btn("Risk Analysis", "risk-view-btn"),
                    _btn("Construction DSS", "dss-view-btn", C["slate800"]),
                ],
                id="safety-toggle",
                style={"display": "flex", "gap": "8px", "marginBottom": "16px"},
            ),
            # Risk Analysis sub-panel
            html.Div(
                id="risk-panel",
                children=[
                    # Sector selector
                    html.Div(
                        [
                            html.Label("Sector", style={"fontSize": "11px", "color": C["slate400"], "textTransform": "uppercase", "letterSpacing": "0.06em", "marginBottom": "4px", "display": "block"}),
                            dcc.Dropdown(
                                id="risk-sector",
                                options=SECTOR_OPTIONS,
                                value="construction",
                                clearable=False,
                                className="zedd-dropdown",
                                style={"width": "230px"},
                            ),
                        ],
                        style={"marginBottom": "14px"},
                    ),
                    # Current telemetry summary
                    html.Div(id="risk-telemetry-summary", style={"marginBottom": "14px"}),
                    # Action buttons
                    html.Div(
                        [
                            _btn("⚡  Auto-Analyze Risk", "auto-analyze-btn"),
                            dcc.Upload(
                                id="media-upload",
                                children=_btn("📷  Upload Media & Analyze", "media-btn", C["slate800"]),
                                accept="image/*,video/*",
                                multiple=False,
                            ),
                        ],
                        style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "marginBottom": "14px"},
                    ),
                    html.Div(id="media-preview", style={"marginBottom": "12px"}),
                    dcc.Loading(html.Div(id="risk-results"), type="circle", color=C["emerald"]),
                    html.Div(id="shard-controls", style={"marginTop": "14px"}),
                    html.Div(id="shard-table", style={"marginTop": "14px"}),
                ],
            ),
            # Construction DSS sub-panel (hidden by default)
            html.Div(
                id="dss-panel",
                style={"display": "none"},
                children=[
                    html.H3("Construction DSS — Weather Summary", style={"fontSize": "14px", "color": C["slate200"], "marginBottom": "12px"}),
                    html.Div(id="dss-summary"),
                ],
            ),
        ]
    )


def _forecast_layout() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H2("7-Day Forecast", style={"fontSize": "16px", "fontWeight": "700", "color": C["slate200"], "margin": "0"}),
                    html.P(id="forecast-location-label", style={"fontSize": "11px", "color": C["slate400"], "margin": "2px 0 0 0"}),
                ],
                style={"marginBottom": "14px"},
            ),
            _btn("📊  Analyze Forecast Risk", "forecast-analyze-btn", C["indigo"]),
            html.Div(style={"height": "14px"}),
            dcc.Loading(html.Div(id="forecast-cards"), type="circle", color=C["emerald"]),
            html.Div(id="forecast-risk-result", style={"marginTop": "16px"}),
        ]
    )


def _more_layout() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    _btn("📦  Sharding Locker", "locker-view-btn"),
                    _btn("🗺️  Site Map", "map-view-btn", C["slate800"]),
                ],
                style={"display": "flex", "gap": "8px", "marginBottom": "16px"},
            ),
            # Locker panel
            html.Div(
                id="locker-panel",
                children=[
                    html.Div(
                        [
                            dcc.Input(
                                id="locker-search",
                                placeholder="Search locker…",
                                debounce=True,
                                style={"backgroundColor": C["card"], "color": C["slate200"], "border": f"1px solid {C['slate800']}", "borderRadius": "6px", "padding": "7px 12px", "fontSize": "12px", "width": "200px"},
                            ),
                            dcc.Dropdown(
                                id="locker-filter",
                                options=[
                                    {"label": "All", "value": "all"},
                                    {"label": "🟢  Green", "value": "Green"},
                                    {"label": "🟡  Amber", "value": "Amber"},
                                    {"label": "🔴  Red", "value": "Red"},
                                    {"label": "⚫  Black", "value": "Black"},
                                ],
                                value="all",
                                clearable=False,
                                className="zedd-dropdown",
                                style={"width": "130px"},
                            ),
                            _btn("📤  Export", "export-btn", C["slate800"]),
                        ],
                        style={"display": "flex", "gap": "8px", "alignItems": "center", "flexWrap": "wrap", "marginBottom": "14px"},
                    ),
                    dcc.Download(id="export-download"),
                    html.Div(id="locker-entries"),
                ],
            ),
            # Site Map panel (hidden)
            html.Div(
                id="map-panel",
                style={"display": "none"},
                children=[
                    html.Div(
                        [
                            html.P(id="map-location-label", style={"fontSize": "11px", "color": C["slate400"], "margin": "0"}),
                            html.Div(
                                [
                                    _btn("📍  Locate Me", "locate-btn", C["slate800"]),
                                    _btn("🗺️  Fetch Map Data", "fetch-map-btn"),
                                ],
                                style={"display": "flex", "gap": "8px"},
                            ),
                        ],
                        style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "14px"},
                    ),
                    dcc.Loading(html.Div(id="map-results"), type="circle", color=C["emerald"]),
                ],
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def _header() -> html.Header:
    return html.Header(
        html.Div(
            [
                # Logo + title
                html.Div(
                    [
                        html.Div(
                            "☁",
                            style={"width": "32px", "height": "32px", "borderRadius": "8px", "backgroundColor": C["emerald_dim"], "border": f"1px solid {C['emerald']}30", "display": "flex", "alignItems": "center", "justifyContent": "center", "fontSize": "18px"},
                        ),
                        html.Span("Zedd Weather", style={"fontSize": "19px", "fontWeight": "700", "color": C["slate200"], "marginLeft": "10px"}),
                        html.Span("Enterprise", style={"fontSize": "10px", "backgroundColor": C["slate800"], "color": C["slate400"], "padding": "2px 7px", "borderRadius": "4px", "marginLeft": "8px", "textTransform": "uppercase", "letterSpacing": "0.05em"}),
                    ],
                    style={"display": "flex", "alignItems": "center"},
                ),
                # Right: alert badge + connection
                html.Div(
                    [
                        html.Div(id="alert-header-badge"),
                        html.Div(
                            [
                                html.Div(
                                    style={"width": "8px", "height": "8px", "borderRadius": "50%", "backgroundColor": C["emerald"], "marginRight": "6px"},
                                ),
                                html.Span("Connected", style={"fontSize": "12px", "color": C["slate400"]}),
                            ],
                            style={"display": "flex", "alignItems": "center", "backgroundColor": C["card"], "padding": "6px 12px", "borderRadius": "20px", "border": f"1px solid {C['slate800']}"},
                        ),
                    ],
                    style={"display": "flex", "alignItems": "center", "gap": "10px"},
                ),
            ],
            style={"maxWidth": "1280px", "margin": "0 auto", "padding": "0 20px", "display": "flex", "justifyContent": "space-between", "alignItems": "center", "height": "64px"},
        ),
        style={"borderBottom": f"1px solid {C['slate800']}", "backgroundColor": "rgba(10,10,10,0.9)", "position": "sticky", "top": "0", "zIndex": "200", "backdropFilter": "blur(8px)"},
    )


# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.SLATE],
    suppress_callback_exceptions=True,
    title="Zedd Weather",
    update_title=None,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server  # expose underlying Flask server for production WSGI

_TAB_DEFS = [
    {"id": "weather", "label": "⚡  Weather Now"},
    {"id": "safety", "label": "⚠️  Safety Risks"},
    {"id": "forecast", "label": "📅  Week Ahead"},
    {"id": "more", "label": "⋯  More"},
]

app.layout = html.Div(
    [
        # ── Persistent stores ──────────────────────────────────────────────
        dcc.Store(id="telemetry-store", storage_type="memory"),
        dcc.Store(id="locker-store", storage_type="local"),
        dcc.Store(id="location-store", storage_type="local", data={"lat": DEFAULT_LAT, "lng": DEFAULT_LNG}),
        dcc.Store(id="risk-store", storage_type="memory"),
        dcc.Store(id="forecast-store", storage_type="memory"),
        dcc.Store(id="active-tab", storage_type="memory", data="weather"),
        dcc.Store(id="safety-view", storage_type="memory", data="risk"),
        dcc.Store(id="more-view", storage_type="memory", data="locker"),
        dcc.Interval(id="telemetry-poll", interval=60_000, n_intervals=0),
        # ── Header ────────────────────────────────────────────────────────
        _header(),
        # ── Main ──────────────────────────────────────────────────────────
        html.Main(
            [
                # Tab navigation
                html.Div(
                    [
                        html.Button(
                            tab["label"],
                            id=f"tab-btn-{tab['id']}",
                            n_clicks=0,
                            className="zedd-tab-btn",
                            **{"data-tab": tab["id"]},
                        )
                        for tab in _TAB_DEFS
                    ],
                    id="tab-nav",
                    style={"display": "flex", "gap": "4px", "borderBottom": f"1px solid {C['slate800']}", "marginBottom": "24px", "paddingBottom": "0"},
                ),
                # Tab content area
                html.Div(id="tab-content"),
            ],
            style={"maxWidth": "1280px", "margin": "0 auto", "padding": "28px 20px"},
        ),
    ],
    style={"minHeight": "100vh", "backgroundColor": C["bg"], "color": C["text"], "fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"},
)

# ============================================================================
# Callbacks
# ============================================================================

# ── Tab switching ────────────────────────────────────────────────────────────

@callback(
    Output("active-tab", "data"),
    [Input(f"tab-btn-{t['id']}", "n_clicks") for t in _TAB_DEFS],
    prevent_initial_call=True,
)
def _switch_tab(*_: int) -> str:
    if not ctx.triggered_id:
        return "weather"
    return str(ctx.triggered_id).replace("tab-btn-", "")


@callback(Output("tab-content", "children"), Input("active-tab", "data"))
def _render_tab(tab: str) -> html.Div:
    return {
        "weather": _weather_layout,
        "safety": _safety_layout,
        "forecast": _forecast_layout,
        "more": _more_layout,
    }.get(tab, _weather_layout)()


# ── Live telemetry polling ───────────────────────────────────────────────────

@callback(
    Output("telemetry-store", "data"),
    Input("telemetry-poll", "n_intervals"),
    Input("refresh-btn", "n_clicks"),
    State("location-store", "data"),
    State("telemetry-source", "value"),
    prevent_initial_call=False,
)
def _poll_telemetry(
    _n: int,
    _r: int,
    location: dict[str, float] | None,
    source: str | None,
) -> dict[str, Any]:
    loc = location or {"lat": DEFAULT_LAT, "lng": DEFAULT_LNG}

    if (source or "onboard") == "onboard":
        data = _api_get("/api/telemetry/latest")
        if data and data.get("telemetry"):
            return data

    # External or onboard fallback → Google Weather proxy
    data = _api_get("/api/weather/current", {"lat": loc["lat"], "lng": loc["lng"]})
    if data:
        return data

    return {
        "telemetry": {
            "temp": 22.5, "humidity": 45.2, "pressure": 1012.5,
            "precipitation": 15, "uvIndex": 3.5, "aqi": 42, "tide": 1.2,
        },
        "hourly": [],
        "timestamp": None,
    }


# ── Weather tab: metric cards ────────────────────────────────────────────────

@callback(
    Output("metric-cards", "children"),
    Output("telemetry-updated", "children"),
    Input("telemetry-store", "data"),
)
def _update_metric_cards(store: dict[str, Any] | None) -> tuple:
    if not store:
        return [], ""
    t = store.get("telemetry") or {}

    def _card(title: str, val: str, unit: str, accent: str = C["emerald"]) -> html.Div:
        return html.Div(
            [
                html.P(title, style={"fontSize": "10px", "color": C["slate400"], "margin": "0 0 6px 0", "textTransform": "uppercase", "letterSpacing": "0.06em"}),
                html.Div(
                    [
                        html.Span(val, style={"fontSize": "26px", "fontWeight": "700", "color": C["slate200"]}),
                        html.Span(f" {unit}", style={"fontSize": "11px", "color": C["slate400"]}),
                    ]
                ),
            ],
            style={
                "backgroundColor": C["card"],
                "border": f"1px solid {C['slate800']}",
                "borderLeft": f"3px solid {accent}",
                "borderRadius": "10px",
                "padding": "14px 16px",
            },
        )

    cards = [
        _card("Temperature", f"{t.get('temp', 0):.1f}", "°C", C["emerald"]),
        _card("Humidity", f"{t.get('humidity', 0):.1f}", "%", C["indigo"]),
        _card("Pressure", f"{t.get('pressure', 0):.1f}", "hPa", C["amber"]),
        _card("Precipitation", f"{t.get('precipitation', 0):.0f}", "%", C["indigo"]),
        _card("UV Index", f"{t.get('uvIndex', 0):.1f}", "", "#f97316"),
        _card("AQI", f"{t.get('aqi', 42):.0f}", "", C["rose"]),
    ]
    ts = store.get("timestamp")
    updated = f"Updated {ts[:19].replace('T', ' ')} UTC" if ts else ""
    return cards, updated


# ── Weather tab: hourly chart ────────────────────────────────────────────────

@callback(Output("hourly-chart", "figure"), Input("telemetry-store", "data"))
def _hourly_chart(store: dict[str, Any] | None) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(**_chart_layout("24-Hour Trend"))
    if not store:
        return fig
    pts = store.get("hourly") or []
    if not pts:
        return fig
    times = [p.get("time", "") for p in pts]
    fig.add_trace(go.Scatter(x=times, y=[p.get("temp", 0) for p in pts], name="Temp (°C)", line=dict(color=C["emerald"], width=2)))
    fig.add_trace(go.Scatter(x=times, y=[p.get("humidity", 0) for p in pts], name="Humidity (%)", line=dict(color=C["indigo"], width=2), yaxis="y2"))
    fig.update_layout(
        yaxis2=dict(overlaying="y", side="right", gridcolor=C["slate800"], tickfont=dict(size=10), color=C["slate400"]),
    )
    return fig


# ── Weather tab: historical chart ────────────────────────────────────────────

@callback(
    Output("hist-chart", "figure"),
    Input("hist-range", "value"),
    State("location-store", "data"),
    prevent_initial_call=False,
)
def _hist_chart(days_str: str | None, location: dict[str, float] | None) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(**_chart_layout("Historical Data"))
    loc = location or {"lat": DEFAULT_LAT, "lng": DEFAULT_LNG}
    days = int(days_str or "7")
    data = _api_get("/api/weather/history", {"lat": loc["lat"], "lng": loc["lng"], "days": days})
    if not data:
        return fig
    pts = data.get("history") or []
    if not pts:
        return fig
    times = [p.get("time", "") for p in pts]
    fig.add_trace(go.Scatter(x=times, y=[p.get("temp", 0) for p in pts], name="Temp (°C)", line=dict(color=C["emerald"], width=2)))
    fig.add_trace(go.Scatter(x=times, y=[p.get("humidity", 0) for p in pts], name="Humidity (%)", line=dict(color=C["indigo"], width=2, dash="dot")))
    fig.add_trace(go.Bar(x=times, y=[p.get("precipitation", 0) for p in pts], name="Precip (%)", marker_color=C["amber"] + "66", yaxis="y2"))
    fig.update_layout(yaxis2=dict(overlaying="y", side="right", gridcolor=C["slate800"], tickfont=dict(size=10), color=C["slate400"]))
    return fig


# ── Safety tab: sub-view toggle ──────────────────────────────────────────────

@callback(
    Output("safety-view", "data"),
    Input("risk-view-btn", "n_clicks"),
    Input("dss-view-btn", "n_clicks"),
    prevent_initial_call=True,
)
def _safety_view(*_: int) -> str:
    return "dss" if ctx.triggered_id == "dss-view-btn" else "risk"


@callback(
    Output("risk-panel", "style"),
    Output("dss-panel", "style"),
    Input("safety-view", "data"),
)
def _toggle_safety_panels(view: str) -> tuple:
    shown: dict[str, Any] = {}
    hidden: dict[str, Any] = {"display": "none"}
    return (hidden, shown) if view == "dss" else (shown, hidden)


# ── Safety tab: telemetry summary ───────────────────────────────────────────

@callback(Output("risk-telemetry-summary", "children"), Input("telemetry-store", "data"))
def _risk_telemetry_summary(store: dict[str, Any] | None) -> html.Div:
    t = (store or {}).get("telemetry") or {}
    rows = [
        ("Temperature", f"{t.get('temp', 0):.1f} °C"),
        ("Humidity", f"{t.get('humidity', 0):.1f} %"),
        ("Pressure", f"{t.get('pressure', 0):.1f} hPa"),
        ("Precipitation", f"{t.get('precipitation', 0):.0f} %"),
        ("UV Index", f"{t.get('uvIndex', 0):.1f}"),
        ("AQI", f"{t.get('aqi', 42):.0f}"),
    ]
    return html.Div(
        [
            html.Div(
                [
                    html.Span(k + ": ", style={"color": C["slate400"], "fontSize": "12px"}),
                    html.Span(v, style={"color": C["slate200"], "fontSize": "12px", "fontWeight": "600"}),
                ],
                style={"display": "inline-block", "marginRight": "16px", "marginBottom": "4px"},
            )
            for k, v in rows
        ],
        style={**_card_style(padding="12px"), "lineHeight": "1.8"},
    )


# ── Safety tab: DSS summary ──────────────────────────────────────────────────

@callback(Output("dss-summary", "children"), Input("telemetry-store", "data"))
def _dss_summary(store: dict[str, Any] | None) -> html.Div:
    t = (store or {}).get("telemetry") or {}
    items = [
        ("🌡️  Temperature", f"{t.get('temp', 0):.1f} °C", "High heat: limit heavy lifting; enforce hydration breaks." if t.get("temp", 0) > 30 else "Temperature within safe range."),
        ("💧  Humidity", f"{t.get('humidity', 0):.1f} %", "High humidity increases heat stress risk." if t.get("humidity", 0) > 70 else "Humidity within safe range."),
        ("🌬️  Precipitation Risk", f"{t.get('precipitation', 0):.0f} %", "Rain likely — review slip-hazard controls." if t.get("precipitation", 0) > 50 else "Low precipitation risk."),
        ("☀️  UV Index", f"{t.get('uvIndex', 0):.1f}", "High UV — enforce sun protection and shade breaks." if t.get("uvIndex", 0) >= 6 else "UV within safe range."),
    ]
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(icon_label, style={"fontSize": "13px", "fontWeight": "600", "color": C["slate200"]}),
                            html.Span(f"  {val}", style={"color": C["emerald"], "fontWeight": "700", "marginLeft": "6px"}),
                        ]
                    ),
                    html.P(advice, style={"fontSize": "12px", "color": C["slate400"], "margin": "4px 0 0 0"}),
                ],
                style={**_card_style(padding="12px"), "marginBottom": "10px"},
            )
            for icon_label, val, advice in items
        ]
    )


# ── Safety tab: AI auto-analyze ──────────────────────────────────────────────

@callback(
    Output("risk-results", "children"),
    Output("risk-store", "data"),
    Input("auto-analyze-btn", "n_clicks"),
    State("telemetry-store", "data"),
    State("risk-sector", "value"),
    prevent_initial_call=True,
)
def _auto_analyze(n: int, store: dict[str, Any] | None, sector: str | None) -> tuple:
    if not n:
        return no_update, no_update
    t = (store or {}).get("telemetry") or {}
    result = _api_post(
        "/api/ai/risk",
        {"telemetry": {**t, "uvIndex": t.get("uvIndex", 0)}, "sector": sector or "construction"},
    )
    if not result:
        result = {
            "riskLevel": "Amber",
            "report": "AI analysis unavailable. Check OLLAMA_BASE_URL and OLLAMA_MODEL.",
        }

    level = result.get("riskLevel", "Amber")
    report = result.get("report", "")
    col = RISK_COLORS.get(level, RISK_COLORS["Amber"])
    ui = html.Div(
        [
            html.Div(
                [html.Span("Risk Level: ", style={"color": C["slate400"]}), _risk_badge(level)],
                style={"display": "flex", "alignItems": "center", "gap": "8px", "marginBottom": "10px"},
            ),
            html.Div(
                dcc.Markdown(report, style={"fontSize": "13px", "color": C["slate300"], "lineHeight": "1.7"}),
                style={
                    "backgroundColor": col["bg"],
                    "border": f"1px solid {col['border']}",
                    "borderRadius": "8px",
                    "padding": "16px",
                },
            ),
        ]
    )
    return ui, {"riskLevel": level, "report": report}


# ── Safety tab: media upload + analyze ──────────────────────────────────────

@callback(
    Output("media-preview", "children"),
    Input("media-upload", "contents"),
    State("media-upload", "filename"),
    prevent_initial_call=True,
)
def _show_media_preview(contents: str | None, filename: str | None) -> html.Div | str:
    if not contents:
        return ""
    return html.Div(
        [
            html.P(f"📎  {filename}", style={"fontSize": "11px", "color": C["slate400"], "marginBottom": "6px"}),
            html.Img(src=contents, style={"maxHeight": "200px", "maxWidth": "100%", "borderRadius": "8px", "border": f"1px solid {C['slate800']}"}),
        ]
    )


# ── Safety tab: shard directives ─────────────────────────────────────────────

@callback(
    Output("shard-controls", "children"),
    Input("risk-store", "data"),
)
def _shard_controls(risk_data: dict[str, Any] | None) -> html.Div | str:
    if not risk_data or not risk_data.get("report"):
        return ""
    return _btn("🔒  Shard Directives to Ledger", "shard-btn")


@callback(
    Output("shard-table", "children"),
    Output("locker-store", "data"),
    Input("shard-btn", "n_clicks"),
    State("risk-store", "data"),
    State("locker-store", "data"),
    prevent_initial_call=True,
)
def _shard_directives(
    n: int,
    risk_data: dict[str, Any] | None,
    locker: list[dict[str, Any]] | None,
) -> tuple:
    if not n or not risk_data:
        return no_update, no_update
    report: str = risk_data.get("report", "")
    level: str = risk_data.get("riskLevel", "Amber")
    chunks = [c.strip() for c in report.split("\n\n") if c.strip()]
    shards: list[dict[str, str]] = []
    for i, chunk in enumerate(chunks):
        digest = hashlib.sha256(f"{chunk}{datetime.utcnow().isoformat()}{i}".encode()).hexdigest()
        shards.append({"id": f"Shard-{i + 1}", "hash": f"0x{digest}", "content": chunk})

    locker_list: list[dict[str, Any]] = list(locker or [])
    locker_list.insert(
        0,
        {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "shards": shards,
            "report": report,
            "riskLevel": level,
        },
    )

    table = html.Div(
        [
            html.H4("Directive Shards", style={"fontSize": "13px", "color": C["slate200"], "marginBottom": "10px"}),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span(s["id"], style={"fontSize": "11px", "fontWeight": "700", "color": C["emerald"]}),
                                    html.Code(s["hash"][:20] + "…", style={"fontSize": "10px", "color": C["slate400"], "marginLeft": "8px"}),
                                ],
                                style={"marginBottom": "4px"},
                            ),
                            html.P(s["content"][:120] + ("…" if len(s["content"]) > 120 else ""), style={"fontSize": "11px", "color": C["slate300"], "margin": "0"}),
                        ],
                        style={**_card_style(padding="10px"), "marginBottom": "8px"},
                    )
                    for s in shards
                ]
            ),
        ]
    )
    return table, locker_list


# ── Forecast tab ─────────────────────────────────────────────────────────────

@callback(
    Output("forecast-store", "data"),
    Output("forecast-location-label", "children"),
    Input("active-tab", "data"),
    State("location-store", "data"),
)
def _load_forecast(tab: str, location: dict[str, float] | None) -> tuple:
    if tab != "forecast":
        return no_update, no_update
    loc = location or {"lat": DEFAULT_LAT, "lng": DEFAULT_LNG}
    data = _api_get("/api/weather/forecast", {"lat": loc["lat"], "lng": loc["lng"], "days": 7})
    forecast = (data or {}).get("forecast", [])
    label = f"📍 {loc['lat']:.4f}, {loc['lng']:.4f}"
    return forecast, label


@callback(Output("forecast-cards", "children"), Input("forecast-store", "data"))
def _forecast_cards(forecast: list[dict[str, Any]] | None) -> html.Div:
    if not forecast:
        return html.P("No forecast data. Make sure GOOGLE_WEATHER_API_KEY is set.", style={"color": C["slate400"], "fontSize": "13px"})

    def _day_card(d: dict[str, Any]) -> html.Div:
        return html.Div(
            [
                html.P(d.get("date", ""), style={"fontSize": "11px", "color": C["slate400"], "margin": "0 0 8px 0", "fontWeight": "600"}),
                html.Div([
                    html.Span(f"▲{d.get('tempMax', 0):.0f}°", style={"color": C["rose"], "fontWeight": "700", "fontSize": "14px"}),
                    html.Span(f"  ▼{d.get('tempMin', 0):.0f}°", style={"color": C["indigo"], "fontSize": "14px"}),
                ], style={"marginBottom": "6px"}),
                html.P(f"💧 {d.get('precip', 0):.0f}%", style={"fontSize": "12px", "color": C["slate300"], "margin": "2px 0"}),
                html.P(f"💨 {d.get('wind', 0):.1f} m/s", style={"fontSize": "12px", "color": C["slate300"], "margin": "2px 0"}),
                html.P(f"☀️ UV {d.get('uv', 0):.0f}", style={"fontSize": "12px", "color": C["slate300"], "margin": "2px 0"}),
            ],
            style={**_card_style(padding="14px")},
        )

    return html.Div(
        [_day_card(d) for d in forecast],
        style={"display": "grid", "gridTemplateColumns": "repeat(auto-fill,minmax(140px,1fr))", "gap": "12px"},
    )


@callback(
    Output("forecast-risk-result", "children"),
    Input("forecast-analyze-btn", "n_clicks"),
    State("forecast-store", "data"),
    State("risk-sector", "value"),
    prevent_initial_call=True,
)
def _analyze_forecast(n: int, forecast: list | None, sector: str | None) -> html.Div | str:
    if not n or not forecast:
        return ""
    result = _api_post("/api/ai/forecast", {"forecast_data": forecast, "sector": sector or "construction"})
    if not result:
        return html.P("AI analysis unavailable.", style={"color": C["amber"]})
    level = result.get("riskLevel", "Amber")
    report = result.get("report", "")
    col = RISK_COLORS.get(level, RISK_COLORS["Amber"])
    return html.Div(
        [
            _risk_badge(level),
            dcc.Markdown(report, style={"fontSize": "13px", "color": C["slate300"], "lineHeight": "1.7"}),
        ],
        style={"backgroundColor": col["bg"], "border": f"1px solid {col['border']}", "borderRadius": "8px", "padding": "16px"},
    )


# ── More tab: locker / map toggle ────────────────────────────────────────────

@callback(
    Output("more-view", "data"),
    Input("locker-view-btn", "n_clicks"),
    Input("map-view-btn", "n_clicks"),
    prevent_initial_call=True,
)
def _more_view(*_: int) -> str:
    return "map" if ctx.triggered_id == "map-view-btn" else "locker"


@callback(
    Output("locker-panel", "style"),
    Output("map-panel", "style"),
    Input("more-view", "data"),
)
def _toggle_more_panels(view: str) -> tuple:
    shown: dict[str, Any] = {}
    hidden: dict[str, Any] = {"display": "none"}
    return (hidden, shown) if view == "map" else (shown, hidden)


# ── More tab: locker entries ──────────────────────────────────────────────────

@callback(
    Output("locker-entries", "children"),
    Input("locker-store", "data"),
    Input("locker-search", "value"),
    Input("locker-filter", "value"),
)
def _locker_entries(
    locker: list[dict[str, Any]] | None,
    search: str | None,
    level_filter: str | None,
) -> html.Div:
    entries: list[dict[str, Any]] = list(locker or [])
    if level_filter and level_filter != "all":
        entries = [e for e in entries if e.get("riskLevel") == level_filter]
    if search:
        q = search.lower()
        entries = [e for e in entries if q in e.get("report", "").lower()]
    if not entries:
        return html.P("No entries in locker.", style={"color": C["slate400"], "fontSize": "13px"})

    def _entry(e: dict[str, Any]) -> html.Div:
        ts = e.get("timestamp", "")[:19].replace("T", " ") if e.get("timestamp") else ""
        level = e.get("riskLevel", "Unknown")
        col = RISK_COLORS.get(level, RISK_COLORS["Amber"])
        n_shards = len(e.get("shards", []))
        return html.Div(
            [
                html.Div(
                    [
                        html.Span(ts, style={"fontSize": "11px", "color": C["slate400"]}),
                        html.Span(level, style={"fontSize": "11px", "fontWeight": "700", "color": col["fg"], "backgroundColor": col["bg"], "borderRadius": "4px", "padding": "2px 8px", "marginLeft": "8px"}),
                        html.Span(f"{n_shards} shard{'s' if n_shards != 1 else ''}", style={"fontSize": "11px", "color": C["slate400"], "marginLeft": "8px"}),
                    ]
                ),
                html.P(e.get("report", "")[:180] + "…", style={"fontSize": "12px", "color": C["slate300"], "margin": "6px 0 0 0"}),
            ],
            style={**_card_style(padding="12px"), "marginBottom": "8px"},
        )

    return html.Div([_entry(e) for e in entries])


# ── More tab: export shards ──────────────────────────────────────────────────

@callback(
    Output("export-download", "data"),
    Input("export-btn", "n_clicks"),
    State("locker-store", "data"),
    prevent_initial_call=True,
)
def _export_shards(n: int, locker: list | None) -> dict[str, Any] | None:
    if not n or not locker:
        return None
    content = json.dumps(locker, indent=2)
    return {"content": content, "filename": f"zedd_shards_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json", "type": "application/json"}


# ── More tab: site map ────────────────────────────────────────────────────────

@callback(
    Output("map-results", "children"),
    Output("map-location-label", "children"),
    Input("fetch-map-btn", "n_clicks"),
    Input("locate-btn", "n_clicks"),
    State("location-store", "data"),
    prevent_initial_call=True,
)
def _fetch_map(
    _fetch: int,
    _locate: int,
    location: dict[str, float] | None,
) -> tuple:
    loc = location or {"lat": DEFAULT_LAT, "lng": DEFAULT_LNG}
    result = _api_post("/api/ai/sitemap", {"lat": loc["lat"], "lng": loc["lng"]})
    if not result:
        return (
            html.P(
                "Map data unavailable. Check OLLAMA_BASE_URL and OLLAMA_MODEL.",
                style={"color": C["amber"]},
            ),
            "",
        )

    report = result.get("report", "")
    links: list[dict[str, str]] = result.get("links", [])
    label = f"📍 {loc['lat']:.4f}, {loc['lng']:.4f}"

    link_items = [
        html.A(lnk.get("title") or lnk.get("uri", ""), href=lnk.get("uri", "#"), target="_blank",
               style={"display": "block", "color": C["indigo"], "fontSize": "12px", "marginBottom": "4px", "textDecoration": "none"})
        for lnk in links[:10]
        if lnk.get("uri")
    ]

    return html.Div(
        [
            dcc.Markdown(report, style={"fontSize": "13px", "color": C["slate300"], "lineHeight": "1.7", "marginBottom": "14px"}),
            html.Div(link_items) if link_items else None,
        ]
    ), label


# ── Header: alert badge (from latest telemetry) ──────────────────────────────

@callback(
    Output("alert-header-badge", "children"),
    Input("telemetry-store", "data"),
)
def _alert_badge(store: dict[str, Any] | None) -> html.Div | str:
    t = (store or {}).get("telemetry") or {}
    alerts: list[str] = []
    if t.get("temp", 0) > 35 or t.get("temp", 0) < 0:
        alerts.append("🌡️  Critical Temp")
    if t.get("aqi", 42) > 150:
        alerts.append("💨  Hazardous AQI")
    if t.get("precipitation", 0) > 80:
        alerts.append("🌧️  Heavy Rain Risk")
    if not alerts:
        return ""
    return html.Div(
        [
            html.Span(f"⚠️  {len(alerts)}", style={"fontSize": "12px", "fontWeight": "700", "color": C["amber"], "backgroundColor": C["amber_dim"], "borderRadius": "12px", "padding": "4px 10px", "border": f"1px solid {C['amber']}40"}),
        ]
    )


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
    port = int(os.getenv("DASH_PORT", "8050"))
    app.run(host="0.0.0.0", port=port, debug=False)
