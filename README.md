# Zedd Weather

[![CI – Lint, Test & Build](https://github.com/Zedd-Weather/Zedd-Weather/actions/workflows/ci.yml/badge.svg)](https://github.com/Zedd-Weather/Zedd-Weather/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Zedd-Weather/Zedd-Weather/actions/workflows/codeql.yml/badge.svg)](https://github.com/Zedd-Weather/Zedd-Weather/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB.svg?logo=python&logoColor=white)](Zweather/requirements.txt)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](docker-compose.yml)
[![Pi Zero 2WH](https://img.shields.io/badge/Pi%20Zero%202WH-Coral-FF6F00.svg?logo=raspberrypi&logoColor=white)](Dockerfile.pizero)

**Zedd Weather is an edge-native weather telemetry, alerting, and risk-analysis platform for construction, agricultural, industrial, residential, marine, aviation, energy, and transportation operations.** It is built for Raspberry Pi clusters with real weather hardware, sensor-driven buffering, server-side weather APIs, and on-device AI inference (Google Coral Edge TPU or Hailo-8L NPU), so operators can make decisions close to the site without depending on a cloud round trip.

> **No simulators.** Zedd Weather deliberately avoids synthetic sensor data. If hardware is absent, drivers report that they are unavailable and emit no readings instead of inventing values.

## Why Zedd Weather?

- **Real hardware first** — BCRobotics Weather HAT PRO (primary), optional BC Robotics 16CH ADC HAT + Gravity soil moisture sensor, UV, Modbus/RS485, Google Coral USB Accelerator, and Hailo AI HAT+ support.
- **Edge resilient** — local MQTT, InfluxDB, SQLite buffering, Docker Compose deployment, optional three-node Pi cluster topology, and a dedicated Pi Zero 2WH variant with tmpfs-only storage.
- **Risk-aware** — deterministic sector engines for construction, agriculture, industrial, residential, marine, aviation, energy, and transportation plus configurable alerts. All engines support UK regional climate profiles for locally-tuned thresholds.
- **Private by design** — third-party API keys stay in the FastAPI backend; the Dash frontend never receives weather or AI credentials.
- **AI optional, local by default** — Google Coral Edge TPU or Hailo-8L NPU classification and local Ollama/Gemma guidance can run without internet access.
- **Operations-ready** — CI, CodeQL, CLI (`zedd`), email reporting, security policy, support policy, release policy, governance policy, and privacy guidance are included.

## Table of contents

- [System overview](#system-overview)
- [Hardware profile](#hardware-profile)
- [Architecture](#architecture)
- [Repository map](#repository-map)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [CLI reference](#cli-reference)
- [Feature guide](#feature-guide)
- [REST API](#rest-api)
- [Deployment patterns](#deployment-patterns)
- [Pi Zero 2WH variant](#pi-zero-2wh-variant)
- [Development](#development)
- [Testing and CI](#testing-and-ci)
- [Security and operations](#security-and-operations)
- [Troubleshooting](#troubleshooting)
- [Project policies](#project-policies)

## System overview

Zedd Weather is a pure Python stack:

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Dash + Plotly | Operator dashboard on port `8050` |
| Backend | FastAPI | Weather proxy, AI endpoints, telemetry ingest, risk analysis on port `8000` |
| CLI | `zedd` (argparse) | Batch, single-sector, sovereign protocol, and email-report commands |
| Messaging | Mosquitto MQTT | Node-to-node telemetry and alert transport |
| Storage | InfluxDB + SQLite buffer | Time-series persistence and edge outage resilience |
| AI | Google Coral TPU / Hailo-8L NPU + Ollama/Gemma | Local classification and natural-language mitigation guidance |
| Reporting | SMTP (email) | Scheduled or on-demand multi-sector HTML reports |
| Packaging | Docker Compose + multi-arch Dockerfile | Single-host development and Raspberry Pi cluster deployment |
| PiNet | `public/dapp.json` | Python DApp manifest for PiNet deployments |

## Hardware profile

The reference deployment is a Raspberry Pi cluster. The sensory worker is expected to run on a Pi with the BCRobotics Weather HAT PRO attached. For constrained environments a Pi Zero 2WH variant swaps the Hailo HAT (PCIe) for a Google Coral USB Accelerator and replaces NVMe buffering with tmpfs in RAM.

| Component | Required | Role |
|---|---|---|---|
| BCRobotics Weather HAT PRO | Yes | BME280 temperature/pressure/humidity plus RJ12 wind and rain instruments |
| Raspberry Pi 4/5 | Yes (standard) | Edge node runtime; Pi 5 recommended for cluster deployments |
| Raspberry Pi Zero 2WH | Alternative | Ultra-low-cost edge for the Pi Zero variant (512 MB RAM, WiFi, no SSD) |
| Google Coral USB Accelerator | Optional | Edge TPU classification (.tflite models, USB, ~4 TOPS) |
| Hailo AI HAT+ / Hailo-8L | Optional | On-device weather classification and diagnostics (.hef models, PCIe M.2) |
| BC Robotics 16CH ADC HAT | Optional | Dual MCP3008/MCP3208, 16 analog channels via SPI |
| Gravity Capacitive Soil Moisture Sensor | Optional | Analog soil moisture sensor (0–3.0 V) via ADC channel |
| M.2 NVMe SSD | Optional | Fast local buffer and model artefact storage |
| Pimoroni Enviro+ | Optional | Air-quality and particulate readings |
| Adafruit VEML6075 | Optional | UV index, UVA, and UVB readings |
| RS485/CAN HAT + Modbus sensors | Optional | Industrial wind and rain instruments |

Peripherals marked optional are controlled by environment variables in `.env.example` and `.env.production.example`. The Pi Zero variant disables HATs that require PCIe/NVMe or conflict with the Weather HAT PRO.

## Architecture

```text
+--------------------------------------------------------------------+
| Node C - Sensory worker                                             |
| BCRobotics Weather HAT PRO + optional Sense HAT/Enviro+/UV/Modbus   |
| SensorManager.read_all() -> GPIO alarm/LED state -> MQTT publish    |
+------------------------------------+-------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------+
| MQTT broker                                                         |
| Authenticated Mosquitto topic exchange for telemetry and alerts      |
+------------------------------------+-------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------+
| Node B - AI worker                                                   |
| MQTT subscriber -> Hailo/Coral classifier -> Ollama/Gemma guidance   |
| -> enriched telemetry and recommendations                            |
+------------------------------------+-------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------+
| Node A - Control plane (or remote server for Pi Zero variant)        |
| FastAPI REST API + Dash dashboard + InfluxDB + Grafana + Open WebUI  |
| Browser -> Dash -> FastAPI -> storage, risk engines, weather proxy   |
+--------------------------------------------------------------------+
```

Design principles:

1. **Protocol and telemetry integrity** — real readings are never replaced by fake values.
2. **Server-side secrets** — Google Weather, InfluxDB, MQTT, and AI credentials stay out of browser code.
3. **Offline capability** — local risk engines and local AI can continue operating when WAN access is unavailable.
4. **Fail-closed hardware drivers** — missing hardware produces absent keys and warnings, not plausible-looking data.
5. **Least-privilege operations** — CI, containers, MQTT, and edge-node hardening are documented in policy files.

## Repository map

```text
.
├── Zweather/
│   ├── dashboard/                  # Dash + Plotly frontend
│   ├── api.py                      # FastAPI backend
│   ├── app.py                      # Standard edge collector (Sense HAT, InfluxDB)
│   ├── app_pizero.py               # Pi Zero 2WH edge collector (Weather HAT PRO, Coral, MQTT)
│   ├── cli.py                      # CLI: analyze, batch, list, sovereign, report
│   ├── weather_client.py           # Server-side Google Weather API client
│   ├── ai_client.py                # Server-side Ollama/Gemma client
│   ├── utils.py                    # Shared helpers (dew point, fog risk, heat index, wind chill)
│   ├── pizero/                     # Pi Zero 2WH variant config, Coral TPU drivers, inference
│   ├── node1_telemetry/            # Sensory worker, sensor drivers (incl. BC Robotics ADC, soil moisture), GPIO alarm control
│   ├── node2_orchestration/        # AI worker and MQTT orchestration
│   ├── ollama_inference/           # Hailo NPU / Coral TPU and local AI clients
│   ├── global_regions/             # Shared UK region profiles and threshold adjustments
│   ├── construction/               # Construction risk engine (uses global_regions)
│   ├── agricultural/               # Agricultural risk engine and forecasting
│   ├── industrial/                 # Industrial risk engine (uses global_regions)
│   ├── residential/                # Residential property risk engine (uses global_regions)
│   ├── marine/                     # Maritime and offshore risk engine (uses global_regions)
│   ├── aviation/                   # Aviation risk engine (runway, flight, icing)
│   ├── energy/                     # Energy risk engine (grid stability, generation)
│   ├── transportation/             # Transportation risk engine (route, logistics)
│   ├── reporting/                  # Email report builder (SMTP)
│   ├── alerting/                   # Rules engine and notification channels
│   ├── sovereign/                  # RMPE-2 sovereign weather protocol
│   ├── requirements.txt            # Python dependencies
│   ├── requirements.pizero.txt     # Pi Zero variant dependencies (minimal)
│   └── tests/                      # Pytest suite
├── docker-compose.yml              # Local control plane and core services
├── docker-compose.cluster.yml      # Node B / Node C cluster overlay
├── Dockerfile                      # Multi-stage amd64/arm64 image
├── Dockerfile.pizero               # Pi Zero 2WH single-stage arm64 image
├── mosquitto/                      # Authenticated MQTT broker configuration
├── public/dapp.json                # PiNet DApp manifest
├── scripts/                        # Utility scripts (Coral model download)
├── .env.example                    # Local environment template
├── .env.production.example         # Production/cluster environment template
├── .github/workflows/              # CI, build, and CodeQL workflows
├── CONTRIBUTING.md                 # Contributor workflow
├── SECURITY.md                     # Vulnerability disclosure and hardening
├── PRIVACY.md                      # Telemetry, data handling, and retention policy
├── GOVERNANCE.md                   # Maintainer roles and decision process
├── RELEASE_POLICY.md               # Versioning, release, and support policy
├── SUPPORT.md                      # Help channels
└── CODE_OF_CONDUCT.md              # Community standards
```

## Quick start

### 1. Prerequisites

- Python 3.12+
- Docker with Compose v2
- Git
- Optional: Raspberry Pi hardware and attached sensors for real telemetry
- Optional: local Ollama server with `gemma2:2b` for AI guidance
- Optional: Google Coral USB Accelerator (Pi Zero variant)

### 2. Configure the environment

```bash
cp .env.example .env
```

Set at least the values your deployment needs:

| Variable | Required for | Notes |
|---|---|---|
| `INFLUXDB_TOKEN` | Docker control plane and edge collector | Use a strong token; do not commit `.env` |
| `DOCKER_INFLUXDB_INIT_PASSWORD` | First-time InfluxDB setup | Required by `docker-compose.yml` |
| `GF_SECURITY_ADMIN_PASSWORD` | Grafana | Required by `docker-compose.yml` |
| `GOOGLE_WEATHER_API_KEY` | Weather proxy endpoints | Server-side only |
| `OLLAMA_BASE_URL` | AI narrative endpoints | Defaults to local/host Ollama patterns |
| `OLLAMA_MODEL` | AI narrative endpoints | Defaults to `gemma2:2b` |
| `MQTT_BROKER_HOST` / `MQTT_BROKER_PORT` | Cluster workers | Used by sensory and AI workers |
| `SMTP_HOST` / `SMTP_TO` | Email reporting | SMTP server and recipient list |

### 3. Start the local control plane

```bash
docker compose up -d
```

Local services:

| Service | URL |
|---|---|
| Dash dashboard | <http://localhost:8050> |
| FastAPI docs | <http://localhost:8000/docs> |
| InfluxDB | <http://localhost:8086> |
| Grafana | <http://localhost:3000> |
| Open WebUI | <http://localhost:8080> |

### 4. Run the Python app directly

Use this path when developing without containers:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r Zweather/requirements.txt

# Terminal 1 - API
uvicorn Zweather.api:app --host 0.0.0.0 --port 8000

# Terminal 2 - dashboard
python -m Zweather.dashboard.app

# Terminal 3 - CLI example
python -m Zweather.cli analyze construction \
  --temperature 18 --humidity 72 --pressure 1008 \
  --region glasgow --season winter --output summary
```

### 5. Smoke-test telemetry ingest

```bash
curl -X POST http://localhost:8000/api/telemetry/ingest \
  -H 'Content-Type: application/json' \
  -d '{
    "weather_hat_pro_temp_c": 25.3,
    "weather_hat_pro_humidity_pct": 58.0,
    "weather_hat_pro_pressure_hpa": 1013.0,
    "wind_speed_ms": 4.2,
    "rain_mm": 0.0,
    "node_id": "pi-node-c"
  }'
```

The dashboard polls `/api/telemetry/latest` and should display the latest payload after its next refresh.

## Configuration

The complete configuration surface lives in `.env.example` and `.env.production.example`. Common groups are summarized below.

### Sensor toggles

| Variable | Default | Description |
|---|---|---|
| `WEATHER_HAT_PRO_ENABLED` | `true` | Enable the primary BCRobotics Weather HAT PRO driver |
| `SENSE_HAT_ENABLED` | `false` | Enable Sense HAT readings and LED matrix support |
| `AI_HAT_ENABLED` | `true` | Enable Hailo AI HAT+ diagnostics/classification |
| `CORAL_ENABLED` | `true` (Pi Zero) | Enable Google Coral USB Accelerator |
| `ENVIRO_PLUS_ENABLED` | `false` | Enable Pimoroni Enviro+ air-quality readings |
| `UV_SENSOR_ENABLED` | `false` | Enable VEML6075 UV readings |
| `MODBUS_ENABLED` | `false` | Enable RS485/Modbus industrial sensors |
| `BC_ROBOTICS_ADC_ENABLED` | `false` (`true` on Pi Zero) | Enable BC Robotics 16CH ADC HAT (dual MCP3008/MCP3208 via SPI) |
| `SOIL_MOISTURE_ENABLED` | `false` (`true` on Pi Zero) | Enable Gravity capacitive soil moisture sensor via ADC |
| `M2_NVME_ENABLED` | `false` | Use NVMe-backed local buffering/storage paths |

### Weather HAT PRO calibration

| Variable | Default | Description |
|---|---|---|
| `WEATHER_HAT_PRO_TEMP_OFFSET` | `0.8` | Temperature compensation in °C |
| `WEATHER_HAT_PRO_I2C_BUS` | `1` | I²C bus for the onboard BME280 |
| `WEATHER_HAT_PRO_ANEMOMETER_GPIO_PIN` | `5` | BCM GPIO pin for wind speed pulses |
| `WEATHER_HAT_PRO_RAIN_GAUGE_GPIO_PIN` | `6` | BCM GPIO pin for rain-gauge pulses |
| `WEATHER_HAT_PRO_RAIN_MM_PER_TIP` | `0.2794` | Rain depth per tipping-bucket pulse |
| `WEATHER_HAT_PRO_VANE_ADC_CHANNEL` | `0` | ADC channel for wind direction |

### Alerts and alarms

| Variable | Default | Description |
|---|---|---|
| `ALERT_TEMP_HIGH_C` | `35.0` | High temperature threshold |
| `ALERT_TEMP_LOW_C` | `0.0` | Low temperature threshold |
| `ALERT_WIND_SPEED_MS` | `20.0` | High wind threshold |
| `ALERT_UV_INDEX` | `8.0` | UV alert threshold |
| `ALERT_AQI` | `150.0` | Air-quality threshold |
| `ALARM_BUZZER_GPIO_PIN` | `17` | BCM GPIO pin for buzzer output |
| `ALARM_LED_GPIO_PIN` | `27` | BCM GPIO pin for alarm LED output |

### Storage and messaging

| Variable | Default | Description |
|---|---|---|
| `INFLUXDB_URL` | `http://influxdb:8086` | InfluxDB endpoint |
| `INFLUXDB_ORG` | `zedd-weather` | InfluxDB organization |
| `INFLUXDB_BUCKET` | `telemetry` | InfluxDB bucket |
| `INFLUXDB_TOKEN` | required | InfluxDB token |
| `MQTT_BROKER_HOST` | `localhost` / `mqtt-broker` | MQTT broker host |
| `MQTT_BROKER_PORT` | `1883` | MQTT broker port |
| `MQTT_TOPIC` | `weather_station/telemetry` | Telemetry topic |
| `PUBLISH_INTERVAL` | `10.0` | Sensor polling interval in seconds |

### Email reporting

| Variable | Default | Description |
|---|---|---|
| `SMTP_HOST` | `localhost` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | — | SMTP username |
| `SMTP_PASSWORD` | — | SMTP password |
| `SMTP_FROM` | `zedd-weather@localhost` | Sender address |
| `SMTP_TO` | — | Comma-separated recipient list |

## CLI reference

The `zedd` CLI provides five subcommands:

```text
usage: zedd [-h] {analyze,list,batch,sovereign,report} ...

Zedd Weather — multi-sector weather risk analysis CLI
```

### `zedd analyze`

Run single-sector risk analysis:

```bash
# Basic usage
zedd analyze construction --temperature 20 --humidity 60 --pressure 1013

# All options
zedd analyze marine \
  --temperature 15 --humidity 80 --pressure 1008 \
  --wind-speed 10 --precipitation 60 \
  --uv-index 3 --aqi 50 \
  --region glasgow --season winter \
  --activity fishing \
  --output summary
```

### `zedd list`

List available sectors:

```bash
zedd list
```

### `zedd batch`

Analyze all (or selected) sectors at once:

```bash
zedd batch --temperature 18 --humidity 65 --pressure 1015
zedd batch --temperature 18 --humidity 65 --pressure 1015 \
  --sectors construction marine energy
```

### `zedd sovereign`

Compose or validate RMPE-2 sovereign weather transitions:

```bash
# Compose a new weather coin transition
zedd sovereign compose \
  --temperature 20 --humidity 60 --pressure 1013 \
  --station-id my-node

# Validate a transition from stdin
cat transition.json | zedd sovereign validate
```

### `zedd report`

Send an HTML email report for one or all sectors:

```bash
# Report on all 8 sectors
zedd report --temperature 20 --humidity 60 --pressure 1013

# Report on a single sector
zedd report --temperature 20 --humidity 60 --pressure 1013 \
  --sector energy --region london --season summer
```

Requires SMTP environment variables (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TO`, `SMTP_FROM`).

## Feature guide

### Sensor ingestion

`Zweather/node1_telemetry/mqtt_publisher.py` runs the sensory worker:

```bash
python -m Zweather.node1_telemetry.mqtt_publisher
```

Each loop reads enabled sensors, evaluates GPIO alarms, updates the optional LED matrix, and publishes the payload to MQTT with reconnect handling.

### Risk engines

All engines are deterministic, require no AI provider, and optionally accept a UK region (e.g. `"glasgow"`, `"london"`) and season for locally-adjusted thresholds. Common threshold logic is shared via `Zweather/global_regions/`.

| Sector | Package | Coverage |
|---|---|---|
| Construction | `Zweather/construction/` | concrete pouring, crane operations, excavation, roofing, scaffolding, steel erection, demolition, ground works, facade works, general construction |
| Agricultural | `Zweather/agricultural/` | crop profiles (maize, wheat, tomato, rice, potato) and seven-day risk forecasting |
| Industrial | `Zweather/industrial/` | manufacturing, power plant, chemical, warehouse, refinery, general industrial; wind-gust, visibility, and material-risk detection |
| Residential | `Zweather/residential/` | property types (Victorian terrace, modern detached, modern flat, postwar semi, interwar bungalow); building fabric, occupant safety, energy demand, and property hazard assessment |
| Marine | `Zweather/marine/` | vessel types (container ship, fishing vessel, passenger ferry, offshore supply, pleasure craft); Beaufort sea state, icing risk, stability, deck/cargo safety, swell, and fog |
| Aviation | `Zweather/aviation/` | aircraft profiles (commercial jet, regional turboprop, cargo, private, helicopter, military); runway condition, flight risk (gust, wind-shear, visibility, thunderstorm), and icing assessment |
| Energy | `Zweather/energy/` | asset types (solar farm, wind farm, substation, hydro plant, combined-cycle gas turbine, battery storage); grid stability, generation forecasting with solar/wind power curves, and energy hazard detection |
| Transportation | `Zweather/transportation/` | transport modes (road, rail, light rail, ferry, freight); route conditions (surface, fog, flood), logistics risk (black-ice, track buckling, heat, AQI), and travel advisories |

Engines return risk scores, breached rules, and recommended mitigations.

### Alerting

`Zweather/alerting/` includes:

- `rules.py` for threshold-based `INFO`, `WARNING`, and `CRITICAL` alerts.
- `channels.py` for logging, webhook, and MQTT notification channels.

### On-device and local AI

- **Google Coral TPU** (`Zweather/pizero/coral_tpu_driver.py` and `Zweather/pizero/coral_npu_client.py`) — loads a TFLite model for the Edge TPU (USB, `/dev/apex_0`); deterministic fallback when hardware is absent.
- **Hailo-8L NPU** (`Zweather/ollama_inference/hailo_npu.py`) — loads a Hailo HEF model (PCIe M.2, `/dev/hailo0`); same deterministic fallback.
- **Ollama/Gemma** (`Zweather/ollama_inference/client.py` and `Zweather/ai_client.py`) — local LLM endpoints for operator guidance across all 8 sectors.

### Email reporting

`Zweather/reporting/email_reporter.py` sends dark-themed HTML multi-sector reports via SMTP:

```python
from Zweather.reporting import send_report

send_report(results, region="Midlands")
```

Can be triggered via the CLI (`zedd report`) or REST API (`POST /api/report`).

### Dashboard

`Zweather/dashboard/app.py` serves a Dash application with tabs for:

1. Live telemetry and rolling charts
2. Forecasts and AI forecast narrative
3. Sector risk analysis (all 8 sectors with region/season selectors)
4. Site map/logistics guidance

The dashboard talks to the FastAPI backend only; it does not hold third-party API keys.

## REST API

Interactive OpenAPI docs are available at <http://localhost:8000/docs> when the API is running.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health check |
| `POST` | `/api/telemetry/ingest` | Store a sensor snapshot |
| `GET` | `/api/telemetry/latest` | Return the latest ingested snapshot |
| `POST` | `/api/analyze` | Run sector risk analysis (all 8 sectors) |
| `POST` | `/api/alerts` | Evaluate alert rules |
| `POST` | `/api/report` | Run heuristic analysis and email the report |
| `GET` | `/api/weather/current` | Current weather through server-side Google Weather proxy |
| `GET` | `/api/weather/forecast` | Multi-day forecast through server-side Google Weather proxy |
| `GET` | `/api/weather/history` | Historical weather through server-side Google Weather proxy |
| `POST` | `/api/ai/risk` | AI risk narrative (all 8 sectors) |
| `POST` | `/api/ai/forecast` | AI forecast narrative (all 8 sectors) |
| `POST` | `/api/ai/sitemap` | Site logistics guidance |
| `GET` | `/api/sovereign/protocol` | Sovereign protocol description, including RMP/RNPE-2 metadata |
| `POST` | `/api/sovereign/compose` | Compose a deterministic weather-state transition |
| `POST` | `/api/sovereign/validate` | Validate a weather-state transition, optional RMP proof, and optional RNPE-2 exchange |

## Deployment patterns

### Single-host cluster

```bash
docker compose -f docker-compose.yml -f docker-compose.cluster.yml up -d
```

This starts the control plane, MQTT broker, AI worker, and sensory worker on one host.

Useful checks:

```bash
docker compose -f docker-compose.yml -f docker-compose.cluster.yml ps
docker exec zedd-mqtt mosquitto_sub -t 'weather_station/#' -v
docker logs -f zedd-sensory-worker
docker logs -f zedd-ai-worker
```

### Three-node Raspberry Pi cluster

| Node | Role | Main services |
|---|---|---|
| Node A | Control plane and storage | FastAPI, Dash, InfluxDB, Grafana, Open WebUI, shared MQTT broker |
| Node B | AI worker | MQTT subscriber, Hailo/Coral classifier, local Ollama guidance |
| Node C | Sensory worker | Weather HAT PRO and optional peripherals, alarm GPIO, MQTT publisher |

Recommended flow:

1. Start `docker-compose.yml` on Node A.
2. Start the AI worker from `docker-compose.cluster.yml` on Node B with `MQTT_BROKER_HOST=<node-a-ip>`.
3. Start the sensory worker from `docker-compose.cluster.yml` on Node C with `MQTT_BROKER_HOST=<node-a-ip>`.
4. Keep MQTT, InfluxDB, Grafana, and Ollama ports on a trusted network or VPN.

### PiNet DApp

`public/dapp.json` declares the Python DApp entry point as `Zweather/dashboard/app.py` and lists required PiNet permissions for wallet, RPC, notifications, system/cluster reads, sensors, and NPU access.

## Pi Zero 2WH variant

For ultra-low-cost edge deployments the repository includes a dedicated Raspberry Pi Zero 2WH variant that replaces the Hailo-8L AI HAT+ (requires PCIe) with a Google Coral USB Accelerator (Edge TPU via USB).

### Key differences

| Aspect | Standard build | Pi Zero 2WH variant |
|---|---|---|
| Board | Raspberry Pi 4/5 | Raspberry Pi Zero 2WH (quad Cortex-A53@1GHz, 512MB RAM) |
| AI accelerator | Hailo-8L NPU (PCIe M.2) | Google Coral Edge TPU (USB) |
| Model format | `.hef` (Hailo Executable Format) | `.tflite` (TensorFlow Lite) |
| Storage | NVMe SSD optional | tmpfs only — no SSD, no SD card writes |
| InfluxDB | Local or remote | Remote only (disabled when `INFLUXDB_URL` empty) |
| Control plane | Local | Remote server |
| Sensors | Weather HAT PRO + optional BC Robotics ADC + soil moisture | Weather HAT PRO + BC Robotics ADC + soil moisture (enabled by default) |
| Container | `Dockerfile` | `Dockerfile.pizero` |
| Entry point | `python -m Zweather.app` | `python -m Zweather.app_pizero` |
| Dependencies | `requirements.txt` | `requirements.pizero.txt` (minimal) |

### Getting started on Pi Zero

```bash
# 1. Flash Raspberry Pi OS Lite (64-bit) to microSD
# 2. Install Coral dependencies
echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" \
  | sudo tee /etc/apt/sources.list.d/coral-edgetpu.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo apt-get update && sudo apt-get install -y python3-tflite-runtime python3-pycoral

# 3. Clone and install
git clone https://github.com/Zedd-Weather/Zedd-Weather.git
cd Zedd-Weather
pip install -r Zweather/requirements.pizero.txt

# 4. Download Coral model
sudo ./scripts/download_coral_model.sh

# 5. Configure and run
export MQTT_BROKER_HOST=10.0.0.50  # remote broker
export CORAL_ENABLED=true
python -m Zweather.app_pizero
```

### Pi Zero ADC and soil moisture

The Pi Zero variant enables the BC Robotics 16CH ADC HAT and Gravity capacitive soil moisture sensor by default:

- `BC_ROBOTICS_ADC_ENABLED=true` — SPI dual MCP3008 (10-bit) or MCP3208 (12-bit), 16 channels, configurable VREF and SPI bus.
- `SOIL_MOISTURE_ENABLED=true` — reads analog voltage on configurable ADC channel; dry soil ~2.5 V, wet soil ~1.0 V (calibratable via `SOIL_MOISTURE_DRY_V` / `SOIL_MOISTURE_WET_V`).

Both are disabled in the standard build (`"false"`) and enabled in the Pi Zero config (`Zweather/pizero/config.py`).

### Pi Zero buffer management

All buffered data is stored in `/tmp/zedd_buffer.db` (tmpfs, RAM-backed) to avoid SD card wear. The buffer is flushed to MQTT on every successful publish and fully drained on a configurable interval (`BUFFER_FLUSH_INTERVAL`, default 300 seconds). Maximum buffered rows (`MAX_BUFFER_ROWS`, default 5000) prevents memory exhaustion.

## Development

```bash
pip install -r Zweather/requirements.txt
pip install pytest httpx flake8 mypy pytest-asyncio

# API with reload
uvicorn Zweather.api:app --reload --host 0.0.0.0 --port 8000

# Dashboard
python -m Zweather.dashboard.app

# CLI dry-run
python -m Zweather.cli list
```

Contribution basics:

- Keep changes focused and documented.
- Add or update tests for behavior changes.
- Do not commit secrets, `.env`, production credentials, model keys, or device-specific private data.
- Hardware-facing changes should be tested on real hardware when possible.
- Follow `CONTRIBUTING.md`, `SECURITY.md`, and the policy files listed below.

## Testing and CI

Local checks:

```bash
flake8 Zweather/ --select=E9,F63,F7,F82 --show-source --statistics
mypy Zweather/ --ignore-missing-imports
pytest Zweather/tests/ -v --tb=short
docker build .
docker build -f Dockerfile.pizero .
```

GitHub Actions runs Python linting, mypy, pytest, multi-arch Docker builds, and CodeQL security analysis.

Current test coverage: **401+ tests** across 25 test files covering all 8 sector engines, CLI, API endpoints, email reporting, weather client, AI client, sovereign protocol, sensor drivers (Weather HAT PRO, BC Robotics ADC, soil moisture), and the Pi Zero variant.

## Security and operations

Security-sensitive defaults and deployment notes:

- Keep `.env` local and restrict permissions with `chmod 600 .env`.
- Rotate InfluxDB, Grafana, MQTT, weather API, and AI credentials after exposure or operator changes.
- Restrict FastAPI CORS origins before exposing the API outside local development.
- Keep Mosquitto on a private network and enable TLS for production MQTT traffic.
- Avoid exposing Ollama, InfluxDB, Grafana, or hardware control ports directly to the public internet.
- Mount Hailo HEF / Coral TFLite model files read-only and verify checksums before production deployment.
- Use LUKS or equivalent encryption for NVMe telemetry storage when readings could identify sensitive site activity.
- Review `SECURITY.md` and `PRIVACY.md` before production rollout.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `Weather HAT PRO BME280 unavailable` | Enable I²C, confirm bus `1`, check HAT seating, and scan for address `0x76`/`0x77` with `i2cdetect -y 1`. |
| `wind_speed_ms` stays at `0.00` | Check the anemometer cable, RJ12 jack, and `WEATHER_HAT_PRO_ANEMOMETER_GPIO_PIN`. |
| `wind_direction_deg` missing | Wind-vane voltage is outside expected resistor ranges; check cable, ADC channel, and wiring. |
| `rain_mm` never increments | Check rain-gauge cable, GPIO pin, and `WEATHER_HAT_PRO_RAIN_MM_PER_TIP`. |
| `ai_hat_status: unavailable` | Hailo runtime or `/dev/hailo0` is missing; deterministic classification continues until hardware support is restored. |
| `coral_available: False` | Coral runtime (`pycoral`/`tflite-runtime`) or `/dev/apex_0` is missing; heuristic fallback active. |
| Dashboard shows no data | No payload has reached `/api/telemetry/ingest`; inspect sensory-worker and MQTT logs. |
| Weather endpoints fail | Confirm `GOOGLE_WEATHER_API_KEY`, API quota, backend logs, and network access. |
| AI narrative endpoints fail | Confirm `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and that the model is pulled on the Ollama host. |
| InfluxDB container exits | Required secrets may be missing; check `INFLUXDB_TOKEN`, `DOCKER_INFLUXDB_INIT_PASSWORD`, and Compose logs. |
| Email reports not sent | Check `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_TO`. |
| `soil_moisture_pct` stays `None` | ADC or soil moisture sensor not enabled; check `BC_ROBOTICS_ADC_ENABLED`, `SOIL_MOISTURE_ENABLED`, and SPI device `/dev/spidev0.0`. |
| `BC Robotics ADC` errors | Check SPI is enabled (`raspi-config` → Interface Options → SPI), wiring, and chip select pins. |
| Pi Zero SD card wear | Ensure `SQLITE_DB_PATH` points to `/tmp/` (tmpfs) and no persistent logs are writing to the SD card. |

## Project policies

| Policy | Purpose |
|---|---|
| [Code of Conduct](CODE_OF_CONDUCT.md) | Community standards and enforcement |
| [Contributing Guide](CONTRIBUTING.md) | Development setup, PR process, coding standards |
| [Security Policy](SECURITY.md) | Vulnerability reporting, hardening, supply-chain practices |
| [Privacy Policy](PRIVACY.md) | Telemetry handling, retention, operator responsibilities |
| [Governance Policy](GOVERNANCE.md) | Maintainer roles, decisions, and escalation |
| [Release Policy](RELEASE_POLICY.md) | Versioning, release checklist, support window |
| [Support Policy](SUPPORT.md) | Where to ask for help and what information to include |
| [MIT License](LICENSE) | Project license |

## License

Zedd Weather is released under the [MIT License](LICENSE).
