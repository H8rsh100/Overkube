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


@router.post("/{name}/recommendation/apply", response_model=ApplyRecommendationResponse, summary="Apply resource recommendation via GitHub PR")
def apply_service_recommendation(
    name: str,
    payload: ApplyRecommendationRequest,
    db: Session = Depends(get_db)
):
    """
    Triggers the GitOps pipeline: computes the recommendation, then calls
    the GitHub PR engine to open a pull request patching the resource manifest.

    Gracefully degrades to dry-run mode when GITHUB_TOKEN is not configured
    or GITHUB_DRY_RUN=true — always returns a valid response, never 500s.
    """
    # Verify the service exists
    svc = db.query(Service).filter(Service.service_name == name).first()
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found.")

    # Fetch the recommendation for this service
    rec = get_recommendation(name, lookback_days=7, db_session=db)
    if "error" in rec:
        raise HTTPException(status_code=500, detail=rec["error"])

    logger.info("Applying recommendation for '%s' (status=%s). Reason: %s",
                name, rec.get("status"), payload.reason or "not specified")

    # Call the GitHub PR engine
    from app.github_pr import open_right_sizing_pr
    result = open_right_sizing_pr(name, rec)

    status = "applied" if not result["dry_run"] else "dry_run"

    return ApplyRecommendationResponse(
        service_name=name,
        status=status,
        applied_at=time.time(),
        pull_request_url=result.get("pr_url"),
        message=result["message"],
    )

