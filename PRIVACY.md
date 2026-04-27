# Privacy Policy

Zedd Weather is an edge telemetry platform. It is designed to process site weather, hardware, and operational risk data close to the deployment environment and to avoid sending sensor data to third-party services unless an operator explicitly configures those integrations.

## Data Processed

Depending on enabled sensors and services, a deployment may process:

- Weather readings such as temperature, humidity, pressure, wind speed, wind direction, rainfall, UV index, and air-quality values.
- Hardware diagnostics such as node identifier, sensor availability, Hailo AI HAT+ status, and local timestamps.
- Risk-analysis outputs such as sector, profile, risk score, breached rules, alerts, and recommended mitigations.
- Optional site context entered by operators for forecast, risk, or logistics guidance.
- Operational logs from FastAPI, Dash, MQTT, Docker, InfluxDB, Grafana, and worker processes.

## Data Not Intentionally Collected

The project does not intentionally collect payment data, government identifiers, personal contact lists, browser tracking identifiers, or advertising identifiers.

Operators should avoid entering personal data into free-text AI prompts, logs, issue reports, screenshots, or telemetry payloads unless they have a clear operational need and lawful basis to do so.

## Local Storage and Retention

Zedd Weather stores telemetry in operator-controlled infrastructure:

- InfluxDB stores time-series telemetry using the retention configured by the deployment.
- The standalone edge collector can buffer readings in SQLite while InfluxDB is unreachable.
- Docker volumes may retain Grafana, Open WebUI, and InfluxDB state between container restarts.
- MQTT messages may be visible to authenticated subscribers on the broker network.

Default examples are not a substitute for a production retention policy. Operators are responsible for setting retention periods that match their legal, safety, and operational requirements.

## External Services

The following integrations may send data outside the local cluster when enabled:

- Google Weather API requests include configured coordinates and request metadata.
- Webhook alert channels send alert payloads to the configured endpoint.
- Any remote Ollama or AI endpoint receives the prompt and context sent by the backend.
- Grafana, Open WebUI, or infrastructure monitoring plugins may have their own telemetry settings.

Use local services or trusted private networks for sensitive deployments. Review external providers' terms and privacy notices before enabling integrations.

## Secrets and Credentials

Secrets must not be committed to the repository. Store credentials in `.env`, Docker secrets, a vault, or the deployment platform's secret store. Rotate credentials after suspected exposure, operator turnover, or environment migration.

## Location and Site Sensitivity

Weather telemetry and coordinates can reveal operational patterns, site location, equipment uptime, and safety events. Treat production telemetry as operationally sensitive, especially for industrial, agricultural, construction, or critical-infrastructure sites.

Recommended controls:

1. Limit dashboard, MQTT, InfluxDB, Grafana, Open WebUI, and Ollama access to trusted networks.
2. Use TLS or a VPN for remote access.
3. Encrypt disks or NVMe volumes that store production telemetry.
4. Redact coordinates, node names, API keys, and operational details before sharing logs publicly.
5. Define retention, backup, and deletion procedures before production rollout.

## Contributor and Issue Data

Public GitHub issues, pull requests, discussions, logs, and screenshots are visible according to GitHub repository settings. Do not post secrets, private telemetry, exact site coordinates, or sensitive operational details in public channels.

## Operator Responsibilities

Each deployment operator is responsible for:

- Complying with applicable privacy, employment, safety, and data-protection laws.
- Notifying users or workers if site monitoring policies require notice.
- Configuring retention, backups, deletion, and access controls.
- Reviewing enabled integrations and exported data flows.
- Responding to data access, deletion, or disclosure requests where legally required.

## Questions

For security-sensitive privacy concerns, follow the private reporting process in [SECURITY.md](SECURITY.md). For general support, see [SUPPORT.md](SUPPORT.md).
