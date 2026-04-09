# Zedd Weather Dashboard

Zedd Weather is an edge telemetry and risk-analysis platform for industrial and agricultural monitoring.  
This repository contains a React frontend, Python telemetry services, and Docker-based local deployment assets.

It runs as a **PiNet DApp** on a Raspberry Pi Weather Node cluster with real hardware:

| Component | Role |
|---|---|
| **Sense HAT v2** | Environmental + IMU sensors (temperature, humidity, pressure, orientation) and 8×8 LED matrix |
| **AI HAT+ (Hailo-8L NPU)** | On-device edge AI inference via M.2 Key E accelerator — weather classification without cloud |
| **M.2 NVMe SSD** | Fast local telemetry buffer and model artifact storage |

## Features

- **Hardware-first** — reads from real Sense HAT sensors (falls back to simulation when hardware is absent)
- **On-device AI** — Hailo-8L NPU runs weather-classification inference at the edge
- Live telemetry ingestion and visualization
- AI-assisted mitigation guidance (NPU → Ollama → Gemini fallback chain)
- InfluxDB time-series storage
- Grafana dashboards
- Open WebUI integration
- PiNet OS DApp with blockchain attestation

## Three-Node Local Cluster Roles

| Node | Role | Main workloads |
|---|---|---|
| Node A | Control plane + storage worker | InfluxDB, Grafana, Open WebUI |
| Node B | AI worker (Hailo-8L NPU) | Node2 orchestration + on-device inference |
| Node C | Sensory worker (Sense HAT + AI HAT) | Node1 telemetry publisher + NVMe buffer |

## Repository Structure

```text
.
├── docker-compose.yml             # Core local stack (control plane + storage workloads)
├── docker-compose.cluster.yml     # Local three-node role simulation (AI + sensory workers + MQTT)
├── Zweather/                      # Python telemetry + orchestration services
├── src/                           # React frontend (Vite + React 19 + TypeScript)
├── mosquitto/                     # Mosquitto MQTT broker config
└── .github/workflows/             # CI workflows (lint, test, build)
```

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
- `GEMINI_API_KEY` (optional for non-AI smoke testing)

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
- `zedd-ai-worker` (Node B – subscribes to MQTT, runs Gemini AI inference)
- `zedd-sensory-worker` (Node C – publishes simulated telemetry over MQTT)

Use `--build` only after local code or Dockerfile changes:

```bash
docker compose -f docker-compose.yml -f docker-compose.cluster.yml up -d --build
```

### 5) Frontend development

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

The GitHub workflows run:
- Python lint (flake8, mypy)
- Python tests (pytest)
- TypeScript lint (`tsc --noEmit`)
- Vite production build
- Multi-arch Docker build

## License

MIT
