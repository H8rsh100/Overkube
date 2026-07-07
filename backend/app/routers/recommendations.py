"""
Overkube — Recommendations Router
=================================
Defines REST API endpoints for fetching recommendations and applying them.
"""

from __future__ import annotations

import time
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models import get_db, Service
from app.schemas import RecommendationResponse, ApplyRecommendationRequest, ApplyRecommendationResponse
from app.recommender import get_recommendation

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{name}/recommendation", response_model=RecommendationResponse, summary="Get resource recommendation for a service")
def get_service_recommendation(
    name: str,
    days: int = Query(7, description="Historical lookback window in days", ge=1, le=30),
    db: Session = Depends(get_db)
):
    """
    Computes and returns resource right-sizing recommendations for the specified service.
    Analyzes historical CPU/memory usage samples to suggest optimal requests and limits.
    """
    # Verify the service exists
    svc = db.query(Service).filter(Service.service_name == name).first()
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found.")

    rec = get_recommendation(name, lookback_days=days, db_session=db)
    if "error" in rec:
        raise HTTPException(status_code=500, detail=rec["error"])

    return rec


@router.post("/{name}/recommendation/apply", response_model=ApplyRecommendationResponse, summary="Apply resource recommendation")
def apply_service_recommendation(
    name: str,
    payload: ApplyRecommendationRequest,
    db: Session = Depends(get_db)
):
    """
    Triggers the GitOps pipeline to apply the recommended resource changes.
    Currently acts as a stub logging the request and returning dry-run metadata.
    Will be wired up to open GitHub Pull Requests in Day 6.
    """
    # Verify the service exists
    svc = db.query(Service).filter(Service.service_name == name).first()
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found.")

    logger.info(f"Applying recommendation for service '{name}'. Reason: {payload.reason or 'Not specified'}")

    # For now, return a successful stub response
    return ApplyRecommendationResponse(
        service_name=name,
        status="dry_run",
        applied_at=time.time(),
        pull_request_url=None,
        message=f"Recommendation for service '{name}' received successfully. (GitOps pipeline stubbed until Day 6)"
    )
