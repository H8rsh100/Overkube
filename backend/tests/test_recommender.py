"""
Overkube — Recommender Engine Unit Tests
========================================
Covers the core statistical calculation logic of recommender.py using an
isolated, in-memory SQLite database.

Test Scenarios:
--------------
1. test_recommendation_normal_overprovisioned:
   Normal workload with high requests vs actual usage. Expects "over-provisioned"
   status, positive savings, and high confidence.
2. test_recommendation_underprovisioned:
   Workload with actual usage exceeding requests. Expects "under-provisioned" status,
   warnings of throttle/OOM risks, and negative savings (cost increase).
3. test_recommendation_high_variance:
   Highly volatile/spiky workload. Coefficient of variation is high. Expects
   lower confidence score.
4. test_recommendation_insufficient_data:
   No usage samples present. Expects 0 confidence, optimal/unchanged recommendation,
   and clean fallback without throwing errors.
"""

from __future__ import annotations

import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Service, UsageSample
from app.recommender import get_recommendation


@pytest.fixture(name="db_session")
def fixture_db_session():
    """Create a clean, in-memory SQLite database for each test run."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_recommendation_normal_overprovisioned(db_session):
    """
    Normal case: Over-provisioned service with steady usage well below its requests.
    Current Requests: 200m CPU / 256Mi Mem.
    Actual usage: ~50m CPU / ~64Mi Mem.
    """
    service_name = "test-gateway"
    namespace = "overkube"
    
    # 1. Register service config
    svc = Service(
        service_name=service_name,
        namespace=namespace,
        cpu_request=200,
        cpu_limit=500,
        mem_request=256,
        mem_limit=512,
        last_seen=time.time()
    )
    db_session.add(svc)
    db_session.commit()

    # 2. Add 7 days of steady, low usage samples (at 4-hour intervals to get enough samples)
    now = time.time()
    num_samples = 1100  # More than target_samples (1008) to get high confidence
    for i in range(num_samples):
        timestamp = now - (i * 300)  # 5-minute intervals
        sample = UsageSample(
            service_name=service_name,
            namespace=namespace,
            timestamp=timestamp,
            cpu_usage_millicores=50 + (i % 5),  # very stable, CV is low
            mem_usage_mb=64.0 + (i % 2),
            cpu_request=200,
            cpu_limit=500,
            mem_request=256,
            mem_limit=512
        )
        db_session.add(sample)
    db_session.commit()

    # 3. Calculate recommendation
    rec = get_recommendation(service_name, lookback_days=7, db_session=db_session)

    assert rec["service_name"] == service_name
    assert rec["status"] == "over-provisioned"
    assert rec["confidence"]["label"] == "high"
    assert rec["confidence"]["score"] > 75
    
    # CPU requests should be right-sized around P90 (~54m)
    assert rec["recommended"]["cpu_request"] < 100
    # CPU limit should follow minimum 1.2x multiplier rule (e.g. 54 * 1.2 = ~65)
    assert rec["recommended"]["cpu_limit"] >= int(rec["recommended"]["cpu_request"] * 1.2)
    
    # Mem request should be around P90 (~65Mi)
    assert rec["recommended"]["mem_request"] < 100
    # Mem limit should include safety buffer (+32MiB)
    assert rec["recommended"]["mem_limit"] >= rec["recommended"]["mem_request"] + 32

    # Savings should be positive
    assert rec["savings"]["cpu_saving_m"] > 0
    assert rec["savings"]["mem_saving_mib"] > 0
    assert rec["savings"]["monthly_savings"] > 0.0


def test_recommendation_underprovisioned(db_session):
    """
    Under-provisioned case: Service requests are 50m CPU / 64Mi Mem,
    but actual usage is around 120m CPU / 150Mi Mem.
    """
    service_name = "test-processor"
    namespace = "overkube"
    
    svc = Service(
        service_name=service_name,
        namespace=namespace,
        cpu_request=50,
        cpu_limit=100,
        mem_request=64,
        mem_limit=128,
        last_seen=time.time()
    )
    db_session.add(svc)
    db_session.commit()

    now = time.time()
    num_samples = 1050
    for i in range(num_samples):
        timestamp = now - (i * 300)
        sample = UsageSample(
            service_name=service_name,
            namespace=namespace,
            timestamp=timestamp,
            cpu_usage_millicores=120 + (i % 10),
            mem_usage_mb=150.0 + (i % 5),
            cpu_request=50,
            cpu_limit=100,
            mem_request=64,
            mem_limit=128
        )
        db_session.add(sample)
    db_session.commit()

    rec = get_recommendation(service_name, lookback_days=7, db_session=db_session)

    assert rec["service_name"] == service_name
    assert rec["status"] == "under-provisioned"
    
    # Recommended resources should increase
    assert rec["recommended"]["cpu_request"] > 100
    assert rec["recommended"]["mem_request"] > 140
    
    # Savings should be negative (increased investment needed for stability)
    assert rec["savings"]["cpu_saving_m"] < 0
    assert rec["savings"]["mem_saving_mib"] < 0
    assert rec["savings"]["monthly_savings"] < 0.0


def test_recommendation_high_variance(db_session):
    """
    High variance case: Spiky CPU workload (0m on idle, 250m on burst).
    Expected: Lower confidence score due to volatility (coefficient of variation).
    """
    service_name = "test-spiky"
    namespace = "overkube"
    
    svc = Service(
        service_name=service_name,
        namespace=namespace,
        cpu_request=100,
        cpu_limit=300,
        mem_request=128,
        mem_limit=256,
        last_seen=time.time()
    )
    db_session.add(svc)
    db_session.commit()

    now = time.time()
    num_samples = 1050
    for i in range(num_samples):
        timestamp = now - (i * 300)
        # Alternate spikes (0m, 200m) to maximize standard deviation / mean ratio (CV)
        cpu_val = 220 if i % 2 == 0 else 5
        mem_val = 180.0 if i % 2 == 0 else 15.0
        
        sample = UsageSample(
            service_name=service_name,
            namespace=namespace,
            timestamp=timestamp,
            cpu_usage_millicores=cpu_val,
            mem_usage_mb=mem_val,
            cpu_request=100,
            cpu_limit=300,
            mem_request=128,
            mem_limit=256
        )
        db_session.add(sample)
    db_session.commit()

    rec = get_recommendation(service_name, lookback_days=7, db_session=db_session)

    # High variance should degrade confidence. Expect medium or low.
    assert rec["confidence"]["label"] in ("medium", "low")
    assert rec["confidence"]["score"] < 75


def test_recommendation_insufficient_data(db_session):
    """
    Insufficient data case: Service is registered, but has no usage samples.
    Expected: Falls back gracefully, status optimal, savings 0, and confidence low.
    """
    service_name = "test-new-svc"
    namespace = "overkube"
    
    svc = Service(
        service_name=service_name,
        namespace=namespace,
        cpu_request=100,
        cpu_limit=200,
        mem_request=128,
        mem_limit=256,
        last_seen=time.time()
    )
    db_session.add(svc)
    db_session.commit()

    rec = get_recommendation(service_name, lookback_days=7, db_session=db_session)

    assert rec["service_name"] == service_name
    assert rec["sample_count"] == 0
    assert rec["confidence"]["label"] == "low"
    assert rec["confidence"]["score"] == 0
    assert rec["status"] == "optimal"
    assert rec["recommended"]["cpu_request"] == 100
    assert rec["recommended"]["mem_request"] == 128
    assert rec["savings"]["monthly_savings"] == 0.0
