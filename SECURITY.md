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

- Never hardcode API keys (`GEMINI_API_KEY`, `INFLUXDB_TOKEN`, `METEOMATICS_USER`/`METEOMATICS_PASS`) or any other secrets in source code.
- Store all secrets in the `.env` file and restrict its permissions: `chmod 600 .env`.
- The `.gitignore` excludes `.env*` files (except `.env.example` and `.env.production.example`) to prevent accidental commits.
- The Gemini API key is passed via the `x-goog-api-key` HTTP header, never as a URL query parameter.
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
- CodeQL runs weekly and on every PR for both JavaScript/TypeScript and Python.
- Dependencies are pinned with lock files (`package-lock.json`, `requirements.txt`).

## Edge Node Security (Raspberry Pi 5)

When deploying on a Raspberry Pi 5 in an industrial or agricultural environment:

1. **Change Default Credentials** — Immediately change the default `pi` user password. Use a strong passphrase.
2. **Disable Unused Services** — Disable SSH if not needed, or configure it for key-based authentication only. Disable Bluetooth and Wi-Fi if using a hardwired Ethernet connection.
3. **Firewall** — Configure `ufw` or `iptables` to allow incoming traffic only on necessary ports (e.g. 1883 for MQTT, 8086 for InfluxDB, 3000 for Grafana).
4. **Physical Security** — Ensure the weatherproof enclosure is physically secured (padlocked or tamper-evident seals) to prevent unauthorized access to the hardware, SD card, or NVMe SSD.
5. **Firmware Updates** — Keep Raspberry Pi OS, Sense HAT firmware, and Hailo runtime up to date.
6. **AI HAT+ Model Integrity** — Store compiled HEF model files on a read-only volume (`/opt/zedd/models:ro`) and verify checksums after deployment.
7. **NVMe Encryption** — If the M.2 NVMe SSD stores sensitive telemetry data, enable LUKS full-disk encryption on the NVMe partition.
