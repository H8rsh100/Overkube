"""
Overkube — SQLAlchemy Database Models
======================================
Two core tables:
  - services       : registry of all tracked K8s deployments
  - usage_samples  : time-series resource metrics per service

Design notes:
  - Integer primary keys keep SQLite happy; UUIDs would be preferred in prod Postgres.
  - Timestamps are stored as UTC epoch seconds (float) for simplicity and portability.
  - Nullable columns on usage fields allow partial rows when only config is known.
"""

from __future__ import annotations

import time
from typing import Optional

from sqlalchemy import (
    Column,
    Float,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


# ── Base ──────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Models ────────────────────────────────────────────────────────────────────

class Service(Base):
    """
    Registry of every Kubernetes Deployment tracked by Overkube.
    One row per (namespace, service_name) pair, upserted each collector run.
    """

    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("namespace", "service_name", name="uq_services_ns_name"),
    )

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    service_name: str = Column(String(128), nullable=False, index=True)
    namespace: str = Column(String(128), nullable=False, default="overkube")
    # ISO-8601 label from the K8s manifest (waste-profile label)
    waste_profile: Optional[str] = Column(String(32), nullable=True)
    # UTC epoch seconds of last successful scrape
    last_seen: float = Column(Float, nullable=False, default=time.time)
    # Current configured requests/limits (millicores / MiB) — refreshed each run
    cpu_request: Optional[int] = Column(Integer, nullable=True)
    cpu_limit: Optional[int] = Column(Integer, nullable=True)
    mem_request: Optional[int] = Column(Integer, nullable=True)
    mem_limit: Optional[int] = Column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<Service {self.namespace}/{self.service_name}>"


class UsageSample(Base):
    """
    One row of resource usage per service, collected every COLLECTOR_INTERVAL seconds.

    Columns
    -------
    service_name        : matches Service.service_name
    namespace           : K8s namespace
    timestamp           : UTC epoch seconds (float)
    cpu_usage_millicores: actual CPU usage in millicores (from metrics-server)
    mem_usage_mb        : actual memory RSS in MiB
    cpu_request         : configured requests.cpu in millicores
    cpu_limit           : configured limits.cpu in millicores (None = unlimited)
    mem_request         : configured requests.memory in MiB
    mem_limit           : configured limits.memory in MiB (None = unlimited)
    """

    __tablename__ = "usage_samples"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    service_name: str = Column(String(128), nullable=False, index=True)
    namespace: str = Column(String(128), nullable=False, default="overkube")
    timestamp: float = Column(Float, nullable=False, index=True)

    # Actual usage (from metrics-server / Prometheus)
    cpu_usage_millicores: Optional[int] = Column(Integer, nullable=True)
    mem_usage_mb: Optional[float] = Column(Float, nullable=True)

    # Configured resource envelope (from Deployment spec)
    cpu_request: Optional[int] = Column(Integer, nullable=True)
    cpu_limit: Optional[int] = Column(Integer, nullable=True)
    mem_request: Optional[int] = Column(Integer, nullable=True)
    mem_limit: Optional[int] = Column(Integer, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<UsageSample {self.service_name} @ {self.timestamp:.0f} "
            f"cpu={self.cpu_usage_millicores}m mem={self.mem_usage_mb:.1f}Mi>"
        )


# ── Engine + Session Factory ──────────────────────────────────────────────────

def _build_engine():
    """
    Build the SQLAlchemy engine from settings.
    Enables WAL mode for SQLite to allow concurrent reads during writes.
    """
    connect_args = {}
    if settings.is_sqlite:
        connect_args["check_same_thread"] = False

    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        echo=(settings.app_env == "development"),
    )

    if settings.is_sqlite:
        # WAL mode: readers don't block writers, essential for the
        # background collector writing while the API is serving.
        @event.listens_for(engine, "connect")
        def _set_wal(dbapi_conn, _record):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def create_tables() -> None:
    """Create all tables if they don't already exist. Idempotent."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI dependency that yields a DB session and guarantees it is closed
    even if the request handler raises an exception.

    Usage:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
