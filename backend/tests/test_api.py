"""
Overkube — API Integration Tests
================================
Tests all FastAPI REST endpoints using FastAPI's TestClient
against an isolated in-memory SQLite database.
"""

from __future__ import annotations

import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models import Base, get_db, Service, UsageSample


# Setup in-memory SQLite engine for API testing with StaticPool to share connection
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="db_session")
def fixture_db_session():
    """Creates schema and seeds initial test data before each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        # Seed test services
        svc1 = Service(
            service_name="api-gateway",
            namespace="overkube",
            cpu_request=200,
            cpu_limit=400,
            mem_request=256,
            mem_limit=512,
            last_seen=time.time(),
            waste_profile="steady"
        )
        svc2 = Service(
            service_name="payment-service",
            namespace="overkube",
            cpu_request=50,
            cpu_limit=100,
            mem_request=64,
            mem_limit=128,
            last_seen=time.time(),
            waste_profile="steady"
        )
        db.add(svc1)
        db.add(svc2)
        db.commit()

        # Seed metrics samples (enough to calculate recommendations)
        now = time.time()
        for i in range(100):
            timestamp = now - (i * 300)
            
            # svc1: Over-provisioned (actual usage ~40m / 64Mi)
            s1 = UsageSample(
                service_name="api-gateway",
                namespace="overkube",
                timestamp=timestamp,
                cpu_usage_millicores=40 + (i % 3),
                mem_usage_mb=64.0 + (i % 2),
                cpu_request=200,
                cpu_limit=400,
                mem_request=256,
                mem_limit=512
            )
            # svc2: Under-provisioned (actual usage ~90m / 150Mi)
            s2 = UsageSample(
                service_name="payment-service",
                namespace="overkube",
                timestamp=timestamp,
                cpu_usage_millicores=90 + (i % 3),
                mem_usage_mb=150.0 + (i % 2),
                cpu_request=50,
                cpu_limit=100,
                mem_request=64,
                mem_limit=128
            )
            db.add(s1)
            db.add(s2)
        db.commit()

        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(name="client", autouse=True)
def fixture_client(db_session):
    """Overrides the get_db dependency in FastAPI app with testing database session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── API Endpoint Tests ────────────────────────────────────────────────────────

def test_health_endpoint(client):
    """Test the /health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_list_services(client):
    """Test GET /services endpoint."""
    response = client.get("/services")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Check that services contain required fields
    service_names = [s["service_name"] for s in data]
    assert "api-gateway" in service_names
    assert "payment-service" in service_names

    # Check status classifications
    for svc in data:
        if svc["service_name"] == "api-gateway":
            assert svc["waste_status"] == "over"
        elif svc["service_name"] == "payment-service":
            assert svc["waste_status"] == "under"


def test_get_service_recommendation(client):
    """Test GET /services/{name}/recommendation."""
    # Test valid service
    response = client.get("/services/api-gateway/recommendation")
    assert response.status_code == 200
    data = response.json()
    assert data["service_name"] == "api-gateway"
    assert data["status"] == "over-provisioned"
    assert data["savings"]["monthly_savings"] > 0
    
    # Test non-existent service
    response = client.get("/services/non-existent-svc/recommendation")
    assert response.status_code == 404


def test_get_service_history(client):
    """Test GET /services/{name}/history."""
    response = client.get("/services/api-gateway/history?days=1")
    assert response.status_code == 200
    data = response.json()
    assert data["service_name"] == "api-gateway"
    assert len(data["points"]) > 0
    assert "cpu_usage_millicores" in data["points"][0]


def test_get_waste_report(client):
    """Test GET /waste-report."""
    response = client.get("/waste-report")
    assert response.status_code == 200
    data = response.json()
    
    assert "total_current_cost" in data
    assert "total_recommended_cost" in data
    assert "total_monthly_savings" in data
    assert data["service_counts"]["over-provisioned"] == 1
    assert data["service_counts"]["under-provisioned"] == 1
    assert len(data["services"]) == 2
    assert len(data["top_offenders"]) == 1
    assert data["top_offenders"][0]["service_name"] == "api-gateway"


def test_apply_recommendation(client):
    """Test POST /services/{name}/recommendation/apply."""
    payload = {"reason": "Over-provisioning cost right-sizing"}
    response = client.post("/services/api-gateway/recommendation/apply", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["service_name"] == "api-gateway"
    assert data["status"] == "dry_run"
    assert "applied_at" in data
