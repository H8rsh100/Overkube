"""
Overkube — FastAPI Application Entrypoint
==========================================
Wires together:
  - Application lifespan (startup: create tables, launch collector)
  - CORS middleware (configured from env)
  - API routers (services, recommendations, waste report)
  - Health endpoint
  - OpenAPI docs at /docs

Run locally:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.collector import collector
from app.config import settings
from app.models import create_tables

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s  %(name)-30s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: initialise DB tables and launch the background collector.
    Shutdown: cancel the collector task gracefully.
    """
    logger.info("Overkube backend starting up (env=%s)", settings.app_env)

    # Ensure DB schema exists
    create_tables()
    logger.info("Database tables ready (url=%s)", settings.database_url)

    # Launch the metrics collector as a background asyncio task
    collector_task = asyncio.create_task(collector.run(), name="overkube-collector")
    logger.info("Collector task started")

    yield   # ← application is live here

    # Shutdown
    logger.info("Shutting down collector...")
    collector_task.cancel()
    try:
        await asyncio.wait_for(asyncio.shield(collector_task), timeout=5.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass
    logger.info("Overkube backend shut down cleanly")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Overkube API",
    description=(
        "Kubernetes resource right-sizing and cost optimization engine. "
        "Collects real-time CPU/memory metrics, computes P90/P99 recommendations "
        "with confidence scoring, and quantifies waste in $/month."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
# Imported here so they register their routes on the app instance.
# Routers are defined in app/routers/ (built in Day 4).

from app.routers import services, recommendations, waste_report
app.include_router(services.router,        prefix="/services",    tags=["Services"])
app.include_router(recommendations.router, prefix="/services",    tags=["Recommendations"])
app.include_router(waste_report.router,    prefix="/waste-report", tags=["Waste Report"])

# ── Core Endpoints ────────────────────────────────────────────────────────────

@app.get("/health", tags=["Meta"], summary="Health check")
def health():
    """
    Returns 200 OK when the backend is running.
    Used by docker-compose healthcheck and load balancers.
    """
    return {"status": "ok", "version": app.version}


@app.get("/", tags=["Meta"], include_in_schema=False)
def root():
    return {
        "name": "Overkube API",
        "docs": "/docs",
        "health": "/health",
    }
