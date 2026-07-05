# ─────────────────────────────────────────────────────────────────────────────
# Overkube Backend — Dockerfile
# Multi-stage build: slim final image with no build tools.
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: dependency resolver ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build deps for any packages that need compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="Overkube Backend"
LABEL org.opencontainers.image.description="K8s resource right-sizing API"
LABEL org.opencontainers.image.source="https://github.com/H8rsh100/Overkube"

# Postgres client lib (only needed if using Postgres backend)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN useradd --create-home --shell /bin/bash overkube
WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ ./app/

# SQLite DB lives in a volume-mounted directory
RUN mkdir -p /data && chown overkube:overkube /data
VOLUME ["/data"]

USER overkube

# Environment defaults (override at runtime)
ENV DATABASE_URL="sqlite:////data/overkube.db" \
    OVERKUBE_NAMESPACE="overkube" \
    COLLECTOR_INTERVAL="30" \
    LOG_LEVEL="INFO" \
    APP_ENV="production"

EXPOSE 8000

# Run the FastAPI app with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
