# =============================================================================
# Zedd-Weather Edge Collector – Multi-Stage Dockerfile
# Target architecture: linux/arm64 (Raspberry Pi 4/5 via QEMU in CI)
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1 – Builder
# Install Python dependencies, skipping hardware-only RPi libraries that
# cannot be built outside of a Raspberry Pi environment.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# System build tools needed for some pure-Python C-extension packages
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY Zweather/requirements.txt requirements.txt

# Install all deps except RPi-specific hardware packages that only build on Pi.
# These are excluded via --ignore with pip; the app guards their import at
# runtime so the container still starts correctly on non-Pi hosts.
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir \
        $(grep -v -E \
            '^\s*(sense-hat|RPi\.GPIO|gpiozero|enviroplus|pimoroni-bme280|pimoroni-ltr559|pms5003)' \
            requirements.txt \
          | grep -v '^\s*#' \
          | grep -v '^\s*$')

# ---------------------------------------------------------------------------
# Stage 2 – Runtime
# Lean image that only contains application code + installed packages.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Metadata labels (OCI standard)
LABEL org.opencontainers.image.title="zedd-weather-edge"
LABEL org.opencontainers.image.description="Zedd-Weather edge telemetry collector"
LABEL org.opencontainers.image.source="https://github.com/WilliamLuke/Zedd-Weather"

# Runtime-only system libraries (smbus2 needs libi2c, sqlite3 is built-in)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libi2c-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from the builder stage
COPY --from=builder /install /usr/local

# Create a non-root application user for security
RUN useradd --system --uid 1001 --gid 0 --no-create-home appuser

WORKDIR /app

# Copy application source
COPY Zweather/ ./Zweather/

# Ensure the package is importable
RUN touch Zweather/__init__.py 2>/dev/null || true

# SQLite buffer and liveness probe live under /tmp (world-writable at runtime)
# The liveness probe touches /tmp/zedd-alive; K3s mounts an emptyDir there.
VOLUME ["/tmp"]

# Switch to non-root user (overridden to root in the edge K3s pod which
# needs privileged I2C access; see k3s/zedd-weather-edge-deployment.yaml)
USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SQLITE_DB_PATH=/tmp/zedd_buffer.db

ENTRYPOINT ["python", "-m", "Zweather.app"]
