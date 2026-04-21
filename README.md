# Zedd Weather Dashboard

[![CI – Lint, Test & Build](https://github.com/WilliamMajanja/Zedd-Weather/actions/workflows/ci.yml/badge.svg)](https://github.com/WilliamMajanja/Zedd-Weather/actions/workflows/ci.yml)
[![CodeQL](https://github.com/WilliamMajanja/Zedd-Weather/actions/workflows/codeql.yml/badge.svg)](https://github.com/WilliamMajanja/Zedd-Weather/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Zedd Weather is an edge telemetry and risk-analysis platform for industrial, agricultural, and construction monitoring.  
This repository contains a React frontend, Python telemetry services, a FastAPI REST API, and Docker-based local deployment assets.

It runs as a **PiNet DApp** on a Raspberry Pi Weather Node cluster with real hardware:

| Component | Role |
|---|---|
| **Sense HAT v2** | Environmental + IMU sensors (temperature, humidity, pressure, orientation) and 8×8 LED matrix |
| **AI HAT+ (Hailo-8L NPU)** | On-device edge AI inference via M.2 Key E accelerator — weather classification without cloud |
| **M.2 NVMe SSD** | Fast local telemetry buffer and model artifact storage |

## Features

- **Hardware-first** — reads from real Sense HAT sensors (falls back to simulation when hardware is absent)
- **On-device AI** — Hailo-8L NPU runs weather-classification inference at the edge
- **Sector-specific risk analysis** — construction, agricultural, and industrial heuristic engines
- **Configurable alert system** — rule-based alerts with severity levels and threshold tuning
- Live telemetry ingestion and visualization
- AI-assisted mitigation guidance (NPU → Ollama/Gemma local inference)
- Local developer workflow support with Copilot CLI (non-cloud AI setup)
- InfluxDB time-series storage
- Grafana dashboards
- Open WebUI integration
- PiNet OS DApp with blockchain attestation
- FastAPI REST API for headless / programmatic access

## Three-Node Local Cluster Roles

| Node | Role | Main workloads |
|---|---|---|
| Node A | Control plane + storage worker | InfluxDB, Grafana, Open WebUI |
| Node B | AI worker (Hailo-8L NPU) | Node2 orchestration + on-device inference |
| Node C | Sensory worker (Sense HAT + AI HAT) | Node1 telemetry publisher + NVMe buffer |

## Repository Structure

```text
.
├── src/                           # React 19 + TypeScript frontend (Vite) — legacy
│   ├── components/                #   Page components and shared UI
│   ├── hooks/                     #   Custom React hooks (telemetry, alerts, forecast, …)
│   ├── types/                     #   TypeScript type definitions
│   └── lib/                       #   RAG pipeline, evaluation metrics, utilities
├── Zweather/                      # Python backend + Python Dash frontend
│   ├── dashboard/                 #   ★ Python Dash frontend (replaces React)
│   │   └── app.py                 #     Dash app: 4 tabs, Plotly charts, all callbacks
│   ├── node1_telemetry/           #   Sensor drivers, MQTT publisher, config
│   ├── node2_orchestration/       #   MQTT subscriber, AI inference, attestation
│   ├── ollama_inference/          #   Ollama / Gemma / Hailo NPU inference clients
│   ├── construction/              #   Construction sector risk engine
│   ├── agricultural/              #   Agricultural sector risk engine (+ forecasting)
│   ├── industrial/                #   Industrial sector risk engine
│   ├── alerting/                  #   Rule-based alert engine + notification channels
│   ├── weather_client.py          #   ★ Server-side Google Weather API async client
│   ├── ai_client.py               #   ★ Server-side Ollama/Gemma AI client (risk, forecast, map)
│   ├── api.py                     #   FastAPI REST API (extended with weather/AI/telemetry endpoints)
│   ├── app.py                     #   Edge collector entry point
│   └── tests/                     #   Pytest test suite
├── docker-compose.yml             # Core local stack (control plane + storage)
├── docker-compose.cluster.yml     # Three-node cluster simulation (AI + sensory workers + MQTT)
├── Dockerfile                     # Multi-stage Docker image (arm64 + amd64)
├── mosquitto/                     # Mosquitto MQTT broker config
├── public/                        # Static assets incl. PiNet DApp manifest
└── .github/workflows/             # CI workflows (lint, test, build, CodeQL)
```

## Python Frontend + Backend Architecture

The application now runs as a **fully Python stack**:

```
Sensors (Sense HAT / Enviro+ / Modbus)
    │  MQTT
    ▼
Node1 telemetry publisher  →  POST /api/telemetry/ingest  →  FastAPI (port 8000)
                                                                    │
Google Weather API  ←── GET /api/weather/{current,forecast,history} ┤
Ollama (Gemma)      ←── POST /api/ai/{risk,forecast,sitemap}        │
                                                                    │
                                      Dash frontend (port 8050) ◄──┘
                                           │ browser
                                         User
```

**Key benefits:**
- All API keys (`GOOGLE_WEATHER_API_KEY`) stay server-side — never sent to the browser
- Sensor nodes push readings to `/api/telemetry/ingest` over HTTP; the Dash UI polls `/api/telemetry/latest`
- Pure Python stack: easier deployment on Raspberry Pi, no Node.js required for the frontend
- Plotly charts in Dash provide equivalent visualisation to the React/Recharts UI

## Quick Start (Local)

### 1) Prerequisites

- Docker with Compose v2
- Node.js 20+

### 2) Configure

```bash
cp .env.example .env
```

Set at minimum:
- `INFLUXDB_TOKEN`
- `OLLAMA_BASE_URL` (required for AI features)

### 3) Start control plane + storage node workloads

```bash
docker compose up -d
```

Services:
- InfluxDB: http://localhost:8086
- Grafana: http://localhost:3000
- Open WebUI: http://localhost:8080

### 4) Start AI worker + sensory worker simulation

```bash
docker compose -f docker-compose.yml -f docker-compose.cluster.yml up -d
```

This starts:
- `mqtt-broker` (Mosquitto on port 1883)
- `zedd-ai-worker` (Node B – subscribes to MQTT, runs local Ollama/Gemma AI inference)
- `zedd-sensory-worker` (Node C – publishes simulated telemetry over MQTT)

Use `--build` only after local code or Dockerfile changes:

```bash
docker compose -f docker-compose.yml -f docker-compose.cluster.yml up -d --build
```

### 5) Python dashboard (recommended) and legacy React frontend

**Python Dash dashboard** (no Node.js required):

```bash
pip install -r Zweather/requirements.txt

# Terminal 1 – FastAPI backend (weather proxy + AI endpoints)
uvicorn Zweather.api:app --host 0.0.0.0 --port 8000

# Terminal 2 – Dash frontend
python -m Zweather.dashboard.app
```

The Dash dashboard runs on **http://localhost:8050**.

Set these environment variables before starting:
```
GOOGLE_WEATHER_API_KEY=...   # Google Weather API key (server-side)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma2:2b
API_BASE_URL=http://localhost:8000
```

**Push sensor data** from any Node 1 sensor directly to the API:

```bash
curl -X POST http://localhost:8000/api/telemetry/ingest \
  -H 'Content-Type: application/json' \
  -d '{"temperature": 25.3, "humidity": 58.0, "pressure": 1013.0, "node_id": "pi-node-c"}'
```

**Legacy React frontend** (requires Node.js 20+):

```bash
npm install
npm run dev
```

The Vite dev server runs on **http://localhost:5173** (separate from Grafana on port 3000).

## Three-Node Cluster Test

### Single-Host Simulation

Run all services on one machine using both compose files:

```bash
docker compose -f docker-compose.yml -f docker-compose.cluster.yml up -d
```

Verify the cluster:

```bash
# Check all containers are running
docker compose -f docker-compose.yml -f docker-compose.cluster.yml ps

# Watch MQTT traffic between nodes
docker exec zedd-mqtt mosquitto_sub -t 'weather_station/#' -v

# Check sensory worker logs (Node C)
docker logs -f zedd-sensory-worker

# Check AI worker logs (Node B)
docker logs -f zedd-ai-worker

# Verify InfluxDB is receiving data (Node A)
docker exec zedd-influxdb influx query 'from(bucket:"telemetry") |> range(start: -5m) |> limit(n:5)' --org zedd-weather
```

### Multi-Host (Real Three-Node) Testing

For testing across three physical hosts (e.g. Raspberry Pi cluster):

1. **Node A** (control plane + storage): Run services from `docker-compose.yml`
   ```bash
   docker compose up -d
   ```

2. **Node B** (AI worker): Run the AI worker with the broker pointed at Node A
   ```bash
   MQTT_BROKER_HOST=<node-a-ip> docker compose -f docker-compose.cluster.yml up -d ai-worker mqtt-broker
   ```

3. **Node C** (sensory worker): Run the sensory worker with the broker pointed at Node A
   ```bash
   MQTT_BROKER_HOST=<node-a-ip> docker compose -f docker-compose.cluster.yml up -d sensory-worker mqtt-broker
   ```

Alternatively, run a shared MQTT broker on Node A and point both workers at it by setting `MQTT_BROKER_HOST` in `.env`.

### Environment Variables for Cluster Testing

| Variable | Default | Description |
|---|---|---|
| `MQTT_BROKER_HOST` | `mqtt-broker` (compose) / `localhost` (bare-metal) | MQTT broker hostname / IP |
| `MQTT_BROKER_PORT` | `1883` | MQTT broker port |
| `MQTT_TOPIC` | `weather_station/telemetry` | MQTT topic for telemetry data |
| `SENSE_HAT_ENABLED` | `true` | Enable real Sense HAT hardware |
| `AI_HAT_ENABLED` | `true` | Enable Hailo-8L NPU (AI HAT+) |
| `AI_HAT_MODEL_PATH` | `/opt/zedd/models/weather_classify.hef` | Path to compiled HEF model |
| `M2_NVME_ENABLED` | `false` | Use M.2 NVMe SSD for telemetry buffer |
| `M2_NVME_PATH` | `/mnt/nvme` | Mount point for the NVMe drive |
| `ENVIRO_PLUS_ENABLED` | `false` | Enable Enviro+ sensor board |
| `PUBLISH_INTERVAL` | `10.0` | Seconds between sensor readings |

Set sensor toggles in `.env` (`SENSE_HAT_ENABLED`, `ENVIRO_PLUS_ENABLED`, etc.) based on hardware availability.

## CI

The GitHub Actions workflows run:
- Python lint (flake8, mypy)
- Python tests (pytest)
- TypeScript type-check (`tsc --noEmit`)
- Vite production build
- Multi-arch Docker build (arm64 + amd64)
- CodeQL security analysis (JavaScript/TypeScript + Python) — weekly and on every PR

## REST API

The FastAPI backend (`Zweather/api.py`) exposes these endpoints:

### Core endpoints (heuristic engines)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health check |
| `POST` | `/api/analyze` | Run sector-specific risk analysis on telemetry data |
| `POST` | `/api/alerts` | Evaluate alert rules against telemetry data |

### Sensor telemetry (Python frontend / sensor nodes)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/telemetry/ingest` | Accept a sensor reading (Sense HAT, Enviro+, Modbus, etc.) |
| `GET` | `/api/telemetry/latest` | Return the most recent ingested sensor snapshot |

### Google Weather API proxy (server-side key)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/weather/current?lat=…&lng=…` | Current conditions + today's hourly forecast |
| `GET` | `/api/weather/forecast?lat=…&lng=…&days=7` | Multi-day daily forecast |
| `GET` | `/api/weather/history?lat=…&lng=…&days=7` | Historical hourly data |

### Local Ollama/Gemma AI (server-side)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/ai/risk` | AI risk analysis on live telemetry for a sector |
| `POST` | `/api/ai/forecast` | AI risk analysis on a 7-day forecast |
| `POST` | `/api/ai/sitemap` | Site logistics report via local Ollama/Gemma |

Start the API server locally:

```bash
uvicorn Zweather.api:app --host 0.0.0.0 --port 8000
```

Interactive docs are available at `http://localhost:8000/docs` (Swagger UI).

## Sector Risk Engines

Zedd Weather includes three heuristic risk-analysis engines that evaluate weather telemetry against sector-specific thresholds — no AI API key required.

| Sector | Module | Activities / Profiles |
|---|---|---|
| **Construction** | `Zweather/construction/` | 7 activity profiles (e.g. concrete pouring, crane operations, excavation) |
| **Agricultural** | `Zweather/agricultural/` | 5 crop profiles (e.g. maize, wheat, vegetables) + forecasting |
| **Industrial** | `Zweather/industrial/` | 6 facility profiles (manufacturing, power plant, chemical, warehouse, refinery, general) |

## Alert System

The rule-based alert engine (`Zweather/alerting/`) evaluates telemetry against configurable thresholds and returns alerts sorted by severity. Thresholds can be tuned via environment variables:

| Variable | Default | Description |
|---|---|---|
| `ALERT_TEMP_HIGH_C` | `35.0` | High temperature alert (°C) |
| `ALERT_TEMP_LOW_C` | `0.0` | Low temperature alert (°C) |
| `ALERT_WIND_SPEED_MS` | `20.0` | High wind speed alert (m/s) |
| `ALERT_UV_INDEX` | `8.0` | UV index alert |
| `ALERT_AQI` | `150.0` | Air quality index alert |

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and the pull request process.

## Security

See [SECURITY.md](SECURITY.md) for our security policy, responsible disclosure process, and edge node hardening guidance.

## Code of Conduct

This project follows the Contributor Covenant. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE)
