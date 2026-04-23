# Zedd Weather Dashboard

[![CI – Lint, Test & Build](https://github.com/WilliamMajanja/Zedd-Weather/actions/workflows/ci.yml/badge.svg)](https://github.com/WilliamMajanja/Zedd-Weather/actions/workflows/ci.yml)
[![CodeQL](https://github.com/WilliamMajanja/Zedd-Weather/actions/workflows/codeql.yml/badge.svg)](https://github.com/WilliamMajanja/Zedd-Weather/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Zedd Weather is an **edge telemetry and risk-analysis platform** for industrial,
agricultural, and construction monitoring. It is designed to run as a
**PiNet DApp** on a small Raspberry Pi cluster equipped with real
weather instrumentation and an on-device AI accelerator, so weather data
can be collected, classified, and acted on **without depending on a
cloud round-trip**.

The repository contains:

- a **Python Dash + Plotly frontend** (`Zweather/dashboard/`)
- a **FastAPI REST backend** (`Zweather/api.py`)
- a set of **Raspberry Pi sensor drivers** for the BCRobotics Weather
  HAT PRO and several optional peripherals (`Zweather/node1_telemetry/`)
- **on-device AI inference** clients for the Hailo-8L NPU (AI HAT+) and a
  local Ollama / Gemma model (`Zweather/ollama_inference/`)
- three **sector-specific risk engines** (construction, agricultural,
  industrial) plus a configurable **alert engine**
  (`Zweather/construction/`, `agricultural/`, `industrial/`,
  `alerting/`)
- a **Docker Compose** stack and **multi-arch Dockerfile** for both
  single-host development and three-node cluster deployment
- a **PiNet DApp manifest** (`public/dapp.json`)

> **No simulators.** This project deliberately ships **no synthetic /
> mock sensor data**. Every sensor driver either returns real readings
> from real hardware or returns nothing at all (so downstream services
> can detect a missing instrument instead of silently consuming fake
> values).

---

## Table of contents

- [Hardware profile](#hardware-profile)
- [Three-node cluster topology](#three-node-cluster-topology)
- [Architecture](#architecture)
- [Repository structure](#repository-structure)
- [Feature reference](#feature-reference)
  - [Sensor drivers (Node C)](#sensor-drivers-node-c)
  - [HAT control (LED matrix &amp; alarm GPIO)](#hat-control-led-matrix--alarm-gpio)
  - [MQTT telemetry pipeline](#mqtt-telemetry-pipeline)
  - [Sector risk engines](#sector-risk-engines)
  - [Alert engine and notification channels](#alert-engine-and-notification-channels)
  - [On-device AI (Hailo-8L NPU + Ollama / Gemma)](#on-device-ai-hailo-8l-npu--ollama--gemma)
  - [Weather data sources](#weather-data-sources)
  - [Dashboard (Dash / Plotly)](#dashboard-dash--plotly)
  - [REST API surface](#rest-api-surface)
  - [Edge buffering and anomaly detection](#edge-buffering-and-anomaly-detection)
- [Quick start](#quick-start)
- [Configuration reference](#configuration-reference)
- [Three-node cluster deployment](#three-node-cluster-deployment)
- [Development workflow](#development-workflow)
- [Testing &amp; CI](#testing--ci)
- [Troubleshooting](#troubleshooting)
- [Contributing, security, license](#contributing-security-license)

---

## Hardware profile

The reference deployment is a small Raspberry Pi cluster (typically
three Pi 5 nodes). So far the cluster uses three HATs, one per node —
the **Weather HAT PRO** on the sensory worker, the **AI HAT+** on the
AI worker, and an **M.2 NVMe HAT** on the control-plane / storage node:

| Component | Role |
|---|---|
| **BCRobotics Weather HAT PRO** | Sensory worker (Node C) primary sensor HAT. On-board BME280 (temperature, pressure, humidity) plus three RJ12 jacks that break out a SparkFun-style anemometer, wind vane, and tipping-bucket rain gauge. |
| **AI HAT+ (Hailo-8L NPU)** | AI worker (Node B) on-device edge AI inference via the M.2 Key E accelerator slot — runs the weather-classification model without cloud calls. |
| **M.2 NVMe HAT** | Control-plane / storage node (Node A) fast local telemetry buffer and storage for the compiled HEF model artefacts. |
| **Sense HAT v2** *(optional)* | Legacy / secondary HAT for sites that still need an IMU or the 8×8 LED matrix. Disabled by default. |
| **Pimoroni Enviro+** *(optional)* | Air-quality add-on (BME280, LTR559, MICS6814 gas, PMS5003 PM). Off by default. |
| **Adafruit VEML6075 UV sensor** *(optional, I²C)* | UVA / UVB irradiance and UV index. Off by default. |
| **Waveshare RS485 CAN HAT + Modbus instruments** *(optional)* | Industrial anemometer / rain-gauge over Modbus-RTU. Off by default. |

Every optional sensor is feature-flagged through environment variables
(see [Configuration reference](#configuration-reference)) and can be
mixed and matched depending on what is physically wired to the node.

## Three-node cluster topology

| Node | Role | Main workloads |
|---|---|---|
| **Node A** | Control plane + storage worker | InfluxDB, Grafana, Open WebUI, FastAPI backend, Dash dashboard |
| **Node B** | AI worker (Hailo-8L NPU) | Node 2 orchestration: subscribes to MQTT telemetry, runs on-device weather classification, and consults a local Ollama / Gemma model for mitigation guidance |
| **Node C** | Sensory worker (BCRobotics Weather HAT PRO) | Node 1 telemetry publisher: reads from the Weather HAT PRO and any other enabled peripherals, optionally drives the Sense HAT LED matrix and GPIO alarm outputs, and publishes to MQTT |

The cluster can also be collapsed onto a single host for development —
see [Quick start](#quick-start).

## Architecture

```
+-------------------------------------------------------------------+
|                       Node C  – Sensory worker                    |
|                                                                   |
|   BCRobotics Weather HAT PRO  Sense HAT (opt)  Enviro+/UV/Modbus  |
|              \                   |                 /              |
|               +-> SensorManager.read_all() -> publish payload     |
|                              |                                    |
|                              v                                    |
|                       MQTT (Mosquitto)                            |
+-------------------------------------------------------------------+
                                |
                                v
+-------------------------------------------------------------------+
|                        Node B  – AI worker                        |
|                                                                   |
|   MQTT subscriber  ->  Hailo-8L NPU classifier (HEF model)        |
|                    ->  Ollama / Gemma local mitigation guidance   |
|                    ->  Re-publish enriched payload                |
+-------------------------------------------------------------------+
                                |
                                v
+-------------------------------------------------------------------+
|             Node A  – Control plane + storage + UI                |
|                                                                   |
|   FastAPI (port 8000)                                             |
|     /api/telemetry/ingest        /api/weather/{current,forecast,  |
|     /api/telemetry/latest         history}        (Google Weather)|
|     /api/analyze /api/alerts     /api/ai/{risk,forecast,sitemap}  |
|                                                                   |
|   Dash + Plotly dashboard (port 8050)  ---->  user browser        |
|   InfluxDB (port 8086)  Grafana (3000)  Open WebUI (8080)         |
+-------------------------------------------------------------------+
```

Key design properties:

- **All third-party API keys (Google Weather, etc.) are server-side**:
  the Dash frontend never sees them. The browser only ever talks to the
  FastAPI proxy.
- **The AI worker does not require an internet connection.** Inference
  is performed on the Hailo-8L NPU and/or against a local Ollama
  instance (default model `gemma2:2b`).
- **The sensory worker fails closed.** If a sensor is missing, the
  driver logs a warning and emits no readings — it never invents
  numbers. Downstream alerts and engines are only ever fed real data.
- **Pure Python stack.** No Node.js / npm runtime is required to deploy
  the application — the entire UI is rendered by Dash.

## Repository structure

```text
.
├── Zweather/                       # Python application
│   ├── dashboard/                  #   Dash + Plotly frontend (port 8050)
│   │   └── app.py
│   ├── api.py                      #   FastAPI REST backend (port 8000)
│   ├── app.py                      #   Standalone edge collector (Sense HAT)
│   ├── weather_client.py           #   Server-side Google Weather API client
│   ├── ai_client.py                #   Server-side Ollama / Gemma client
│   ├── node1_telemetry/            # Node C – sensory worker
│   │   ├── config.py               #   All env-var driven configuration
│   │   ├── mqtt_publisher.py       #   Sensor read loop + MQTT publisher
│   │   ├── hat_control/            #     LED matrix + GPIO alarm controllers
│   │   └── sensors/                #     One driver per HAT / peripheral
│   │       ├── weather_hat_pro.py  #       BCRobotics Weather HAT PRO (primary)
│   │       ├── sense_hat_driver.py #       Sense HAT v2 (optional)
│   │       ├── ai_hat_driver.py    #       Hailo-8L NPU diagnostics
│   │       ├── enviro_plus.py      #       Pimoroni Enviro+ AQI
│   │       ├── uv_sensor.py        #       VEML6075 UV
│   │       ├── gpio_sensors.py     #       Generic tipping-bucket rain gauge
│   │       ├── modbus_sensors.py   #       RS485 Modbus instruments
│   │       └── sensor_manager.py   #     Aggregates every enabled driver
│   ├── node2_orchestration/        # Node B – AI worker (MQTT subscriber)
│   ├── ollama_inference/           # Hailo NPU + Ollama / Gemma clients
│   ├── construction/               # Construction sector risk engine
│   ├── agricultural/               # Agricultural sector risk engine + forecasting
│   ├── industrial/                 # Industrial sector risk engine
│   ├── alerting/                   # Alert rules engine + notification channels
│   ├── requirements.txt
│   └── tests/                      # Pytest suite (~106 tests)
├── docker-compose.yml              # Core stack (control plane + storage + collector)
├── docker-compose.cluster.yml      # Three-node cluster overlay (MQTT + workers)
├── Dockerfile                      # Multi-stage arm64 + amd64 image
├── mosquitto/                      # Mosquitto MQTT broker config (auth required)
├── public/                         # Static assets including the PiNet DApp manifest
├── .env.example                    # Local development env template
├── .env.production.example         # Production / cluster env template
└── .github/workflows/              # CI: lint, tests, multi-arch build, CodeQL
```

---

## Feature reference

This section walks through every onboarded feature so a new operator
can quickly find what each part of the system does and how to enable it.

### Sensor drivers (Node C)

All drivers implement the same `BaseSensor` interface
(`Zweather/node1_telemetry/sensors/base.py`):

| Driver | Module | Default | Telemetry keys |
|---|---|---|---|
| **BCRobotics Weather HAT PRO** | `weather_hat_pro.py` | **enabled** | `weather_hat_pro_temp_c`, `weather_hat_pro_pressure_hpa`, `weather_hat_pro_humidity_pct`, `wind_speed_ms`, `rain_mm`, `rain_total_mm`, `wind_direction_deg`, `wind_direction_cardinal` |
| Sense HAT v2 (optional) | `sense_hat_driver.py` | disabled | `temperature_c`, `pressure_hpa`, `humidity_pct`, `orientation`, `accelerometer`, `gyroscope`, `magnetometer` |
| AI HAT+ (Hailo-8L NPU) | `ai_hat_driver.py` | enabled | `ai_hat_available`, `ai_hat_status`, `npu_temp_c`, `npu_power_w`, `npu_utilization_pct` |
| Generic tipping-bucket rain gauge | `gpio_sensors.py` | disabled | `rain_interval_mm`, `rain_rate_mm_h`, `rain_total_mm` |
| Adafruit VEML6075 UV sensor | `uv_sensor.py` | disabled | `uv_index`, `uva_raw`, `uvb_raw` |
| Pimoroni Enviro+ | `enviro_plus.py` | disabled | `enviro_temp_c`, `enviro_pressure_hpa`, `enviro_humidity_pct`, `light_lux`, `proximity`, `gas_*_kohm`, `pm1_0_ug_m3`, `pm2_5_ug_m3`, `pm10_ug_m3` |
| Modbus / RS485 industrial sensors | `modbus_sensors.py` | disabled | `wind_speed_ms`, `wind_direction_deg`, `modbus_rain_total_mm` |

If the underlying hardware library or device is not present at start-up,
the driver logs a single warning and reports `available = False`. From
that point on `read()` returns an empty dict and the corresponding
telemetry keys are simply absent from the payload — no synthetic values
are ever produced.

### HAT control (LED matrix & alarm GPIO)

`Zweather/node1_telemetry/hat_control/` contains two helper modules:

- **`led_display.py`** — high-level wrapper around the Sense HAT 8×8 LED
  matrix with `show_risk_level("green"|"amber"|"red"|"black")`,
  `scroll_message`, `show_bar`, and `show_icon` primitives. When the
  Sense HAT is disabled (the default with the Weather HAT PRO profile)
  every method becomes a safe no-op so the publisher loop is unaffected.
- **`alarm.py`** — drives a buzzer and an external alarm LED through
  GPIO (`ALARM_BUZZER_GPIO_PIN`, `ALARM_LED_GPIO_PIN`). It evaluates
  the latest telemetry payload against the `ALERT_*` thresholds and
  raises / clears the GPIO pins accordingly.

### MQTT telemetry pipeline

`Zweather/node1_telemetry/mqtt_publisher.py` is the entry point for the
sensory worker:

```
python -m Zweather.node1_telemetry.mqtt_publisher
```

It performs the following steps each `PUBLISH_INTERVAL` seconds:

1. `SensorManager.read_all()` aggregates every enabled driver into a
   single dict and prepends a UNIX timestamp.
2. `AlarmController.evaluate()` raises GPIO buzzer / LED pins when any
   threshold is breached.
3. A `green` / `amber` / `red` risk level is derived from the payload
   and pushed to the LED matrix (only if the Sense HAT is enabled).
4. The payload is published to `MQTT_TOPIC` with QoS 1 and an
   exponential-backoff reconnect loop covers transient broker failures.

### Sector risk engines

Three heuristic engines evaluate live telemetry against sector-specific
thresholds — they require **no AI key** and run entirely on the edge.

| Sector | Module | Profiles |
|---|---|---|
| **Construction** | `Zweather/construction/` | 7 activity profiles: concrete pouring, crane operations, excavation, roofing, painting, masonry, general construction |
| **Agricultural** | `Zweather/agricultural/` | 5 crop profiles (e.g. maize, wheat, vegetables) plus a built-in 7-day **forecasting engine** |
| **Industrial** | `Zweather/industrial/` | 6 facility profiles: manufacturing, power_plant, chemical, warehouse, refinery, general |

Each engine returns a deterministic risk report (`risk_score`, per-rule
breakdown, recommended mitigations) that the dashboard renders alongside
the corresponding live readings.

### Alert engine and notification channels

`Zweather/alerting/` provides:

- **`rules.py`** — a small rules engine. Each alert carries a `severity`
  (`INFO` / `WARNING` / `CRITICAL`), the breached `metric`, the observed
  value and the threshold. Thresholds come from environment variables
  (`ALERT_TEMP_HIGH_C`, `ALERT_TEMP_LOW_C`, `ALERT_WIND_SPEED_MS`,
  `ALERT_UV_INDEX`, `ALERT_AQI`).
- **`channels.py`** — pluggable notification channels. Out of the box
  the application supports:
  - `LoggingChannel` — writes alerts to the standard Python logger.
  - `WebhookChannel` — POSTs alerts as JSON to an HTTP webhook
    (Slack-compatible payload structure).
  - `MqttChannel` — re-publishes alerts on a dedicated MQTT topic so
    other cluster services can react.

### On-device AI (Hailo-8L NPU + Ollama / Gemma)

`Zweather/ollama_inference/` contains two clients:

- **`hailo_npu.py`** — `HailoNPUClient` loads the compiled HEF model
  pointed to by `AI_HAT_MODEL_PATH` and runs weather classification
  (`clear`, `rain`, `storm`, `fog`, `snow`) on the AI HAT+. When the
  Hailo runtime is unavailable the client falls back to a deterministic
  **heuristic** classifier (no synthetic telemetry — it labels real
  values using physical thresholds) so downstream consumers still get a
  category to act on. It also exposes `generate_mitigation()` for short
  textual recommendations.
- **`client.py`** — `OllamaClient` talks to a local Ollama server
  (default `OLLAMA_BASE_URL=http://localhost:11434`,
  `OLLAMA_MODEL=gemma2:2b`) for richer natural-language guidance such as
  the AI risk explainer, the 7-day forecast narrative, and the site
  logistics report.

### Weather data sources

The FastAPI backend proxies the **Google Weather API**
(`weather.googleapis.com/v1/`) for current conditions, multi-day
forecasts, and historical data. The `GOOGLE_WEATHER_API_KEY` is held
server-side only.

### Dashboard (Dash / Plotly)

`Zweather/dashboard/app.py` is a single-page Dash application served on
port 8050 with four tabs:

- **Live telemetry** — current Weather HAT PRO readings plus rolling
  Plotly charts.
- **Forecast** — 7-day daily forecast from the Google Weather API,
  optionally enriched with an AI narrative.
- **Risk analysis** — sector switch (construction / agricultural /
  industrial) backed by the heuristic engines and the AI risk endpoint.
- **Site map / logistics** — site-specific guidance generated by the
  AI client.

All API calls go through the FastAPI backend; the browser never holds
any third-party credentials.

### REST API surface

`Zweather/api.py` exposes the following endpoints (interactive Swagger
UI at `http://localhost:8000/docs`):

| Method | Endpoint | Description |
|---|---|---|
| `GET`  | `/api/health` | Service health check |
| `POST` | `/api/analyze` | Run a sector-specific risk analysis on a telemetry payload |
| `POST` | `/api/alerts` | Evaluate alert rules against telemetry and return ordered alerts |
| `POST` | `/api/telemetry/ingest` | Accept a sensor reading from any Node 1 worker |
| `GET`  | `/api/telemetry/latest` | Return the most recent ingested sensor snapshot |
| `GET`  | `/api/weather/current?lat=…&lng=…` | Current conditions + today's hourly forecast |
| `GET`  | `/api/weather/forecast?lat=…&lng=…&days=7` | Multi-day daily forecast |
| `GET`  | `/api/weather/history?lat=…&lng=…&days=7` | Historical hourly data |
| `POST` | `/api/ai/risk` | AI risk analysis on live telemetry for a sector |
| `POST` | `/api/ai/forecast` | AI risk narrative on a multi-day forecast |
| `POST` | `/api/ai/sitemap` | Site logistics report via local Ollama / Gemma |

### Edge buffering and anomaly detection

`Zweather/app.py` is a self-contained edge collector designed for
deployment alongside InfluxDB on the storage node. It reads from the
Sense HAT, runs a two-stage anomaly detector (physical-bounds check +
rolling Z-score), batches points to InfluxDB, and **buffers to a local
SQLite file** when the InfluxDB endpoint is unreachable, replaying the
buffer once connectivity is restored. It refuses to start when no Sense
HAT hardware is present — there is no built-in simulator.

---

## Quick start

### 1) Prerequisites

- Docker with Compose v2
- Python 3.12+ (for running the API and Dash app outside containers)
- (Production) a Raspberry Pi 4 or 5 with the BCRobotics Weather HAT
  PRO connected to I²C bus 1 and the SparkFun-style anemometer / vane /
  rain gauge plugged into the three RJ12 jacks.

### 2) Configure

```bash
cp .env.example .env
```

At minimum set:

- `INFLUXDB_TOKEN` — InfluxDB write token
- `OLLAMA_BASE_URL` — base URL of your Ollama server (required for AI
  endpoints; the default `gemma2:2b` model is small enough to run on
  modest hardware)
- `GOOGLE_WEATHER_API_KEY` — only required if you want the live
  weather / forecast / history endpoints

### 3) Start the control plane + storage workloads

```bash
docker compose up -d
```

Services exposed on `localhost`:

- InfluxDB — http://localhost:8086
- Grafana — http://localhost:3000
- Open WebUI — http://localhost:8080

### 4) Add the AI worker + sensory worker (single-host development)

```bash
docker compose -f docker-compose.yml -f docker-compose.cluster.yml up -d
```

This adds:

- `mqtt-broker` — Mosquitto on port 1883 (authenticated)
- `zedd-ai-worker` — Node B; subscribes to MQTT, runs Hailo NPU /
  Ollama inference
- `zedd-sensory-worker` — Node C; reads the BCRobotics Weather HAT PRO
  (and any other enabled peripherals) and publishes telemetry over MQTT.
  When run on a host without the hardware, the worker simply logs that
  the HAT is unavailable and publishes empty payloads — it does **not**
  fabricate sensor data.

Use `--build` only after local code or Dockerfile changes:

```bash
docker compose -f docker-compose.yml -f docker-compose.cluster.yml up -d --build
```

### 5) Run the FastAPI backend + Dash dashboard outside containers

```bash
pip install -r Zweather/requirements.txt

# Terminal 1 – FastAPI backend (weather proxy + AI endpoints)
uvicorn Zweather.api:app --host 0.0.0.0 --port 8000

# Terminal 2 – Dash frontend
python -m Zweather.dashboard.app
```

The dashboard is then available on **http://localhost:8050**. Set these
environment variables before starting:

```
GOOGLE_WEATHER_API_KEY=...   # Google Weather API key (server-side)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma2:2b
API_BASE_URL=http://localhost:8000
```

### 6) Push sensor data manually (smoke test)

```bash
curl -X POST http://localhost:8000/api/telemetry/ingest \
  -H 'Content-Type: application/json' \
  -d '{"weather_hat_pro_temp_c": 25.3, "weather_hat_pro_humidity_pct": 58.0, "weather_hat_pro_pressure_hpa": 1013.0, "wind_speed_ms": 4.2, "rain_mm": 0.0, "node_id": "pi-node-c"}'
```

The Dash dashboard polls `/api/telemetry/latest` and will show the
payload within one refresh tick.

---

## Configuration reference

All configuration is driven through environment variables. The full list
is documented in `.env.example` and `.env.production.example`; the most
commonly tuned values are summarised here.

### MQTT

| Variable | Default | Description |
|---|---|---|
| `MQTT_BROKER_HOST` | `mqtt-broker` (compose) / `localhost` (bare-metal) | Broker hostname / IP |
| `MQTT_BROKER_PORT` | `1883` | Broker port |
| `MQTT_TOPIC` | `weather_station/telemetry` | Telemetry topic |
| `PUBLISH_INTERVAL` | `10.0` | Seconds between sensor reads |

### BCRobotics Weather HAT PRO (primary sensor HAT)

| Variable | Default | Description |
|---|---|---|
| `WEATHER_HAT_PRO_ENABLED` | `true` | Enable the Weather HAT PRO driver |
| `WEATHER_HAT_PRO_TEMP_OFFSET` | `0.8` | CPU-proximity temperature compensation in °C |
| `WEATHER_HAT_PRO_I2C_BUS` | `1` | I²C bus the on-board BME280 lives on |
| `WEATHER_HAT_PRO_ANEMOMETER_GPIO_PIN` | `5` | BCM GPIO pin connected to the anemometer reed switch (RJ12 J2) |
| `WEATHER_HAT_PRO_RAIN_GAUGE_GPIO_PIN` | `6` | BCM GPIO pin connected to the rain-gauge reed switch (RJ12 J3) |
| `WEATHER_HAT_PRO_RAIN_MM_PER_TIP` | `0.2794` | Millimetres of rainfall per tipping-bucket pulse |
| `WEATHER_HAT_PRO_VANE_ADC_CHANNEL` | `0` | MCP3008 / ADS1015 channel the wind-vane resistor divider is wired to |

### Sense HAT (optional secondary)

| Variable | Default | Description |
|---|---|---|
| `SENSE_HAT_ENABLED` | `false` | Enable the Sense HAT v2 driver and LED matrix |
| `SENSE_HAT_TEMP_OFFSET` | `2.0` | CPU-proximity temperature compensation in °C |

### AI HAT+ (Hailo-8L NPU)

| Variable | Default | Description |
|---|---|---|
| `AI_HAT_ENABLED` | `true` | Enable the AI HAT+ driver |
| `AI_HAT_MODEL_PATH` | `/opt/zedd/models/weather_classify.hef` | Path to the compiled HEF weather-classification model |
| `AI_HAT_DEVICE_ID` | `/dev/hailo0` | Hailo device path |

### Local AI inference (Ollama / Gemma)

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama server URL |
| `OLLAMA_MODEL` | `gemma2:2b` | Model tag to use for AI endpoints |

### Optional peripherals

| Variable | Default | Description |
|---|---|---|
| `ENVIRO_PLUS_ENABLED` | `false` | Enable the Pimoroni Enviro+ board |
| `UV_SENSOR_ENABLED` | `false` | Enable the VEML6075 UV sensor |
| `UV_SENSOR_I2C_BUS` | `1` | I²C bus for the UV sensor |
| `UV_SENSOR_I2C_ADDR` | `0x10` | I²C address for the UV sensor |
| `RAIN_GAUGE_ENABLED` | `false` | Enable a generic GPIO tipping-bucket rain gauge (separate from the Weather HAT PRO gauge) |
| `RAIN_GAUGE_GPIO_PIN` | `6` | BCM GPIO pin for the generic rain gauge |
| `RAIN_GAUGE_MM_PER_TIP` | `0.2794` | mm of rainfall per generic-gauge tip |
| `MODBUS_ENABLED` | `false` | Enable RS485 / Modbus industrial sensors |
| `MODBUS_PORT` | `/dev/ttyS0` | Serial device for the Modbus link |
| `MODBUS_BAUDRATE` | `9600` | Modbus baud rate |
| `MODBUS_ANEMOMETER_UNIT_ID` | `1` | Modbus unit ID for the anemometer |
| `MODBUS_RAIN_GAUGE_UNIT_ID` | `2` | Modbus unit ID for the rain gauge |

### Storage

| Variable | Default | Description |
|---|---|---|
| `M2_NVME_ENABLED` | `false` | Use the M.2 NVMe SSD for telemetry buffering |
| `M2_NVME_PATH` | `/mnt/nvme` | Mount point for the NVMe drive |
| `INFLUXDB_URL` | `http://influxdb:8086` | InfluxDB endpoint |
| `INFLUXDB_TOKEN` | _required_ | InfluxDB write token |
| `INFLUXDB_ORG` | `zedd-weather` | InfluxDB organisation |
| `INFLUXDB_BUCKET` | `telemetry` | InfluxDB bucket |

### GPIO alarm outputs

| Variable | Default | Description |
|---|---|---|
| `ALARM_BUZZER_GPIO_PIN` | `17` | BCM GPIO pin for the buzzer |
| `ALARM_LED_GPIO_PIN` | `27` | BCM GPIO pin for the alarm LED |

### Alert thresholds

| Variable | Default | Description |
|---|---|---|
| `ALERT_TEMP_HIGH_C` | `35.0` | High temperature alert (°C) |
| `ALERT_TEMP_LOW_C`  | `0.0`  | Low temperature alert (°C) |
| `ALERT_WIND_SPEED_MS` | `20.0` | High wind speed alert (m/s) |
| `ALERT_UV_INDEX` | `8.0` | UV index alert |
| `ALERT_AQI` | `150.0` | Air quality index alert |

---

## Three-node cluster deployment

### Single-host cluster

Run all services on one machine using both Compose files:

```bash
docker compose -f docker-compose.yml -f docker-compose.cluster.yml up -d
```

Verify the cluster:

```bash
docker compose -f docker-compose.yml -f docker-compose.cluster.yml ps

# Watch MQTT traffic between nodes
docker exec zedd-mqtt mosquitto_sub -t 'weather_station/#' -v

# Sensory worker logs (Node C)
docker logs -f zedd-sensory-worker

# AI worker logs (Node B)
docker logs -f zedd-ai-worker

# Confirm InfluxDB is receiving data (Node A)
docker exec zedd-influxdb influx query \
  'from(bucket:"telemetry") |> range(start: -5m) |> limit(n:5)' \
  --org zedd-weather
```

### Multi-host cluster (real three-node)

Across three physical hosts (typically Raspberry Pi 4 / 5):

1. **Node A** (control plane + storage)
   ```bash
   docker compose up -d
   ```
2. **Node B** (AI worker)
   ```bash
   MQTT_BROKER_HOST=<node-a-ip> \
     docker compose -f docker-compose.cluster.yml up -d ai-worker mqtt-broker
   ```
3. **Node C** (sensory worker — must have the Weather HAT PRO physically
   attached)
   ```bash
   MQTT_BROKER_HOST=<node-a-ip> \
     docker compose -f docker-compose.cluster.yml up -d sensory-worker mqtt-broker
   ```

Alternatively, run a shared MQTT broker on Node A and point both
workers at it via `MQTT_BROKER_HOST`.

---

## Development workflow

The recommended local loop is:

```bash
# Install dependencies
pip install -r Zweather/requirements.txt
pip install pytest httpx flake8

# Run the tests
pytest Zweather/tests/ -v --tb=short

# Lint for unused imports / variables and fatal Python errors
flake8 --select=E9,F63,F7,F82,F401,F841 Zweather/

# Iterate on the dashboard
python -m Zweather.dashboard.app
```

The Dash app supports hot-reload during development and the FastAPI
backend can be served with `uvicorn --reload Zweather.api:app`.

## Testing & CI

The GitHub Actions workflows run:

- Python lint (`flake8`) and type checking (`mypy`)
- Pytest suite (`pytest Zweather/tests/`)
- Multi-arch Docker build (`linux/amd64`, `linux/arm64`)
- CodeQL security analysis (Python) — weekly and on every PR

Run the same checks locally with the commands above. The current suite
contains 106 tests covering sector engines, the alert rules engine, the
sensor manager, the Weather HAT PRO driver, the AI HAT+ driver, the
SQLite buffer, and the FastAPI endpoints.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `Weather HAT PRO BME280 unavailable (...)` in the sensory-worker logs and no `weather_hat_pro_*` keys in MQTT payloads | I²C bus disabled or no HAT detected. Run `i2cdetect -y 1` and confirm address `0x76` / `0x77`. Check `WEATHER_HAT_PRO_I2C_BUS` and ribbon-cable seating. |
| `wind_speed_ms` is always `0.00` even on windy days | The anemometer is not pulsing. Verify the cable in the RJ12 J2 jack and that `WEATHER_HAT_PRO_ANEMOMETER_GPIO_PIN` matches the board. |
| `wind_direction_deg` is missing from the payload | The vane voltage is more than ±0.30 V from any expected resistor value (treated as a wiring fault). Check the J2 cable and `WEATHER_HAT_PRO_VANE_ADC_CHANNEL`. |
| `rain_mm` is always `0.000` during real rain | Check the J3 cable, `WEATHER_HAT_PRO_RAIN_GAUGE_GPIO_PIN`, and that `WEATHER_HAT_PRO_RAIN_MM_PER_TIP` matches the gauge's spec sheet. |
| AI HAT+ reports `ai_hat_status: "unavailable"` | The Hailo runtime / `hailo_platform` Python package is not installed or `/dev/hailo0` is missing. Inference falls back to the heuristic classifier in `hailo_npu.py` until the runtime is restored. |
| Dash dashboard shows "no data" | The FastAPI backend has never received a `/api/telemetry/ingest` POST. Check the sensory-worker logs and that the broker connection succeeded. |
| `sense_hat package is not installed. ... this collector requires real hardware` from `Zweather/app.py` | The standalone edge collector does not include a simulator. Either install the Sense HAT and library, or use the MQTT publisher path instead. |

---

## Contributing, security, license

- **Contributing** — see [CONTRIBUTING.md](CONTRIBUTING.md) for development
  setup, coding standards, and the pull-request process.
- **Security** — see [SECURITY.md](SECURITY.md) for the responsible
  disclosure policy and edge-node hardening guidance.
- **Code of conduct** — this project follows the Contributor Covenant
  ([CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)).
- **Support** — see [SUPPORT.md](SUPPORT.md) for help channels.
- **License** — [MIT](LICENSE).
