"""
Overkube — Services Router
==========================
Defines REST API endpoints for listing tracked services and fetching downsampled history.
"""

from __future__ import annotations

import time
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models import get_db, Service, UsageSample
from app.schemas import ServiceListItem, HistoryResponse, HistoryPoint
from app.recommender import get_recommendation

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[ServiceListItem], summary="List all monitored services")
def list_services(db: Session = Depends(get_db)):
    """
    Returns a list of all tracked services including their configurations,
    last-seen timestamps, and currently assessed waste status ('over' | 'under' | 'optimal').
    """
    services = db.query(Service).all()
    results = []

    for svc in services:
        # Calculate the recommendation to fetch the current waste status classification.
        # This keeps the waste status dynamic and always in sync with history.
        rec = get_recommendation(svc.service_name, lookback_days=7, db_session=db)
        
        status = "optimal"
        if "status" in rec:
            if rec["status"] == "over-provisioned":
                status = "over"
            elif rec["status"] == "under-provisioned":
                status = "under"

        results.append(
            ServiceListItem(
                id=svc.id,
                service_name=svc.service_name,
                namespace=svc.namespace,
                waste_profile=svc.waste_profile,
                last_seen=svc.last_seen,
                cpu_request=svc.cpu_request,
                cpu_limit=svc.cpu_limit,
                mem_request=int(svc.mem_request) if svc.mem_request is not None else None,
                mem_limit=int(svc.mem_limit) if svc.mem_limit is not None else None,
                waste_status=status
            )
        )

    return results


@router.get("/{name}/history", response_model=HistoryResponse, summary="Get historical metrics downsampled for charting")
def get_service_history(
    name: str,
    days: int = Query(7, description="Number of days of history to retrieve", ge=1, le=30),
    db: Session = Depends(get_db)
):
    """
    Retrieves usage sample history for a specific service.
    Outputs up to ~200 downsampled metrics points to avoid overloading frontend charts.
    """
    # Verify the service exists
    svc = db.query(Service).filter(Service.service_name == name).first()
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found.")

    cutoff_time = time.time() - (days * 86400)
    
    # Query history ordered chronologically
    samples = (
        db.query(UsageSample)
        .filter(UsageSample.service_name == name)
        .filter(UsageSample.timestamp >= cutoff_time)
        .order_by(UsageSample.timestamp.asc())
        .all()
    )

    total_points = len(samples)
    
    # Downsample target
    target_points = 200
    
    if total_points <= target_points:
        downsampled = samples
    else:
        # Select every k-th sample to achieve roughly 200 points
        step = total_points // target_points
        downsampled = [samples[i] for i in range(0, total_points, step)]
        # Make sure we include the very latest point
        if (total_points - 1) not in range(0, total_points, step):
            downsampled.append(samples[-1])

    points = [
        HistoryPoint(
            timestamp=s.timestamp,
            cpu_usage_millicores=s.cpu_usage_millicores,
            mem_usage_mb=s.mem_usage_mb,
            cpu_request=s.cpu_request,
            cpu_limit=s.cpu_limit,
            mem_request=s.mem_request,
            mem_limit=s.mem_limit
        )
        for s in downsampled
    ]

    return HistoryResponse(
        service_name=name,
        lookback_days=days,
        points=points
    )
