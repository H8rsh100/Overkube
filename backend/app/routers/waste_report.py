"""
Overkube — Waste Report Router
==============================
Defines REST API endpoints for fetching cluster-wide cost waste summary reports.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models import get_db, Service
from app.schemas import WasteReportResponse, ServiceWasteSummary
from app.recommender import get_recommendation

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=WasteReportResponse, summary="Get cluster-wide cost waste report")
def get_waste_report(db: Session = Depends(get_db)):
    """
    Computes a cluster-wide cost and waste summary.
    Aggregates waste stats and savings potential across all monitored services.
    Lists the top 5 cost-saving offenders (most over-provisioned services).
    """
    services = db.query(Service).all()
    
    total_current_cost = 0.0
    total_recommended_cost = 0.0
    total_monthly_savings = 0.0
    
    service_counts = {
        "over-provisioned": 0,
        "under-provisioned": 0,
        "optimal": 0
    }
    
    summaries = []
    
    for svc in services:
        rec = get_recommendation(svc.service_name, lookback_days=7, db_session=db)
        
        # Skip unregistered/error services
        if "error" in rec or "current" not in rec:
            continue
            
        current_cost = rec["current"]["monthly_cost"]
        recommended_cost = rec["recommended"]["monthly_cost"]
        savings = rec["savings"]["monthly_savings"]
        status = rec["status"]
        
        # Increment service counts
        if status in service_counts:
            service_counts[status] += 1
            
        # Accumulate costs and savings
        total_current_cost += current_cost
        total_recommended_cost += recommended_cost
        
        # Total savings is the sum of positive savings (from over-provisioned services).
        # We ignore negative savings (under-provisioned expansion costs) for the "savings potential".
        # This aligns with the "recoverable/month" description.
        if status == "over-provisioned":
            total_monthly_savings += savings
            
        summaries.append(
            ServiceWasteSummary(
                service_name=svc.service_name,
                namespace=svc.namespace,
                status=status,
                current_cost=current_cost,
                recommended_cost=recommended_cost,
                monthly_savings=savings,
                confidence_score=rec["confidence"]["score"],
                confidence_label=rec["confidence"]["label"]
            )
        )
        
    # Sort services to find the top offenders (highest monthly savings/waste first)
    top_offenders = sorted(
        [s for s in summaries if s.status == "over-provisioned"],
        key=lambda x: x.monthly_savings,
        reverse=True
    )[:5]
    
    return WasteReportResponse(
        total_current_cost=round(total_current_cost, 2),
        total_recommended_cost=round(total_recommended_cost, 2),
        total_monthly_savings=round(total_monthly_savings, 2),
        service_counts=service_counts,
        services=summaries,
        top_offenders=top_offenders
    )
