# Security Policy

## Supported Versions

Only the latest release on the `main` branch is actively supported with security patches.

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |
| older   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability within Zedd Weather, please send an email to the security team at **security@zeddweather.local**. All security vulnerabilities will be promptly addressed.

**Do not** report security vulnerabilities through public GitHub issues.

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Affected component(s) (frontend, backend, Docker, hardware driver, etc.)
- Potential impact

We aim to acknowledge reports within **48 hours** and provide an initial assessment within **5 business days**.

## Security Practices

### Secrets and Credential Management

- Never hardcode API keys (`INFLUXDB_TOKEN`, `GOOGLE_WEATHER_API_KEY`, `ACCUWEATHER_API_KEY`) or any other secrets in source code.
- Store all secrets in the `.env` file and restrict its permissions: `chmod 600 .env`.
- The `.gitignore` excludes `.env*` files (except `.env.example` and `.env.production.example`) to prevent accidental commits.
- Keep local AI traffic on trusted networks when using `OLLAMA_BASE_URL`; avoid exposing the Ollama port publicly.
- Docker Compose uses the `${VAR:?msg}` syntax for mandatory secrets so that containers fail fast when secrets are missing.

### MQTT Broker Security

- The Mosquitto MQTT broker requires password-based authentication (`password_file`).
- Restrict broker access to the cluster network; do not expose port 1883 to the public internet.
- Use TLS for MQTT traffic in production environments.

### Docker and Container Security

- The Docker image runs as a non-root `appuser` (UID 1001) by default.
- Only override with `privileged: true` when I2C or GPIO hardware access is required on the host.
- Pin base images to specific versions to avoid supply-chain drift.
- Use `docker compose` secrets or a vault integration for production deployments instead of `.env` files.

### FastAPI / REST API

- The API currently allows all CORS origins (`allow_origins=["*"]`) for local development. Restrict this to your frontend origin in production.
- Validate and sanitise all input via Pydantic models.

### CI / Supply Chain

- GitHub Actions workflows follow least-privilege permissions (`contents: read` by default).
- CodeQL runs weekly and on every PR for Python.
- Python dependencies are pinned in `Zweather/requirements.txt`.

## Edge Node Security (Raspberry Pi 4/5)

When deploying on a Raspberry Pi 4/5 in an industrial or agricultural environment:

1. **Change Default Credentials** — Immediately change the default `pi` user password. Use a strong passphrase.
2. **Disable Unused Services** — Disable SSH if not needed, or configure it for key-based authentication only. Disable Bluetooth and Wi-Fi if using a hardwired Ethernet connection.
3. **Firewall** — Configure `ufw` or `iptables` to allow incoming traffic only on necessary ports (e.g. 1883 for MQTT, 8086 for InfluxDB, 3000 for Grafana).
4. **Physical Security** — Ensure the weatherproof enclosure is physically secured (padlocked or tamper-evident seals) to prevent unauthorized access to the hardware, SD card, or NVMe SSD.
5. **Firmware Updates** — Keep Raspberry Pi OS, Weather HAT PRO firmware, and Hailo runtime up to date.
6. **AI HAT+ Model Integrity** — Store compiled HEF model files on a read-only volume (`/opt/zedd/models:ro`) and verify checksums after deployment.
7. **NVMe Encryption** — If the M.2 NVMe SSD stores sensitive telemetry data, enable LUKS full-disk encryption on the NVMe partition.

## Edge Node Security (Raspberry Pi Zero 2WH)

When deploying the Pi Zero 2WH variant:

1. **Change Default Credentials** — Change the default `pi` user password and disable root login over SSH.
2. **Wi-Fi Security** — Connect to a WPA2/WPA3-encrypted network. Use a dedicated IoT VLAN if available. Disable Wi-Fi and Bluetooth if using Ethernet.
3. **Minimal Attack Surface** — Disable unnecessary services (Avahi, Bluetooth, triggerhappy). The Pi Zero runs only `app_pizero.py` — no InfluxDB, Grafana, or Ollama locally.
4. **Physical Security** — Secure the enclosure with tamper-evident seals. The Pi Zero has no hardware encryption module; microSD extraction grants full data access.
5. **SD Card Hardening** — Use tmpfs for SQLite buffer (`/tmp/zedd_buffer.db`) and enable `overlayroot` or `read-only` root filesystem to prevent SD card corruption and limit persistence of malicious writes.
6. **Coral Model Integrity** — Store Coral TFLite model files on a read-only volume and verify checksums after deployment.
7. **Network Egress** — Restrict outbound traffic from the Pi Zero to only the MQTT broker IP and NTP servers. Do not expose the Pi Zero directly to the public internet.
8. **Firmware Updates** — Keep Raspberry Pi OS and the Coral Edge TPU runtime (`libedgetpu`) up to date.
