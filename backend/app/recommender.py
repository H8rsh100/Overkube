"""
Overkube — Recommendation Engine (The Brain)
===========================================
Calculates optimal CPU and Memory resources for services based on historical usage metrics.

Key Logic:
----------
1. recommended_cpu_request = P90 of cpu_usage_millicores
2. recommended_cpu_limit   = P99 of cpu_usage_millicores
   - Enforces a minimum multiplier of 1.2x over the recommended CPU request.
3. recommended_mem_request = P90 of mem_usage_mb
4. recommended_mem_limit   = P99 of mem_usage_mb
   - Enforces a minimum safety buffer of 32 MiB over the recommended Memory request,
     since memory OOMs cause pod death, whereas CPU throttling just slows down execution.
5. confidence_score (0-100) calculated as a weighted average of:
   - Sample count (30%): target of 1008 samples (3.5 days of 5-min intervals) for full score.
   - Coefficient of Variation / predictability (50%): lower CV (standard deviation / mean)
     leads to higher confidence.
   - Recency (20%): decays if the last seen metric is old.
6. waste_status classification:
   - "optimal"           : current request is within ±15% of recommended.
   - "over-provisioned"  : current request > recommended request by > 15%.
   - "under-provisioned" : current request < recommended request by > 15% (under-provisioning risk).
"""

from __future__ import annotations

import time
import logging
from typing import Dict, Any, List, Optional
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import Service, UsageSample, SessionLocal
from app.pricing import calculate_waste_cost, calculate_monthly_cost

logger = logging.getLogger(__name__)

# Constants for recommendation calculations
CPU_LIMIT_MIN_MULTIPLIER = 1.2
MEM_LIMIT_MIN_BUFFER_MIB = 32.0

# Multipliers/bounds for status categorization
OPTIMAL_THRESHOLD_PCT = 0.15  # within 15% of recommended is considered optimal


def calculate_confidence(
    sample_count: int,
    cpu_usages: List[int],
    mem_usages: List[float],
    last_sample_time: float
) -> dict[str, Any]:
    """
    Computes a confidence score from 0 to 100 based on sample count,
    predictability (coefficient of variation), and data recency.
    Returns the score and its categorical label.
    """
    if sample_count == 0:
        return {"score": 0, "label": "low", "reason": "No metrics data found"}

    # 1. Sample Count Score (40% weight)
    # Target: 1008 samples (equivalent to 3.5 days at 5-minute intervals)
    target_samples = 1008
    count_score = min(100.0, (sample_count / target_samples) * 100.0)

    # 2. Predictability / CV Score (40% weight)
    # CV = std_dev / mean. If mean is 0, we treat it as 0 CV (very predictable/idle).
    # Higher coefficient of variation means spiky usage, resulting in lower confidence.
    predictability_scores = []
    for usages in [cpu_usages, mem_usages]:
        if not usages or len(usages) < 2:
            predictability_scores.append(50.0)
            continue
        arr = np.array(usages, dtype=float)
        mean = np.mean(arr)
        std = np.std(arr)
        
        if mean <= 0.01:
            cv = 0.0
        else:
            cv = std / mean
            
        # CV <= 0.2: 100 score. CV >= 1.5: 0 score. Linear interpolation in between.
        if cv <= 0.2:
            score = 100.0
        elif cv >= 1.5:
            score = 0.0
        else:
            score = 100.0 - ((cv - 0.2) / 1.3) * 100.0
        predictability_scores.append(score)
        
    predictability_score = sum(predictability_scores) / len(predictability_scores)

    # 3. Recency Score (20% weight)
    # Full score if data is within 1 hour. Decays to 0 over 7 days.
    now = time.time()
    age_seconds = max(0.0, now - last_sample_time)
    one_hour = 3600.0
    seven_days = 7 * 86400.0

    if age_seconds <= one_hour:
        recency_score = 100.0
    elif age_seconds >= seven_days:
        recency_score = 0.0
    else:
        # Linear decay from 100 (at 1 hour) to 0 (at 7 days)
        recency_score = 100.0 - ((age_seconds - one_hour) / (seven_days - one_hour)) * 100.0

    # Weighted combination: predictability (volatility) is key for cost optimization sizing
    final_score = (count_score * 0.30) + (predictability_score * 0.50) + (recency_score * 0.20)
    final_score = max(0.0, min(100.0, final_score))
    final_score_rounded = int(round(final_score))

    # Categorize label
    if final_score_rounded > 75:
        label = "high"
    elif final_score_rounded >= 40:
        label = "medium"
    else:
        label = "low"

    # Compile brief reason
    reasons = []
    if count_score < 50:
        reasons.append("small sample window")
    if predictability_score < 50:
        reasons.append("high resource usage volatility")
    if recency_score < 50:
        reasons.append("stale data")
        
    reason_str = ", ".join(reasons) if reasons else "sufficient stable historical data"

    return {
        "score": final_score_rounded,
        "label": label,
        "reason": f"Confidence is {label} due to {reason_str}."
    }


def get_recommendation(service_name: str, lookback_days: int = 7, db_session: Optional[Session] = None) -> Dict[str, Any]:
    """
    Computes resource recommendations for the specified service.
    
    Returns a dictionary structured as follows:
    {
        "service_name": str,
        "namespace": str,
        "lookback_days": int,
        "sample_count": int,
        "current": {
            "cpu_request": int, "cpu_limit": int,
            "mem_request": int, "mem_limit": int,
            "monthly_cost": float
        },
        "recommended": {
            "cpu_request": int, "cpu_limit": int,
            "mem_request": int, "mem_limit": int,
            "monthly_cost": float
        },
        "confidence": {
            "score": int, "label": str, "reason": str
        },
        "savings": {
            "cpu_saving_m": int, "mem_saving_mib": float,
            "monthly_savings": float
        },
        "status": str,  # "optimal" | "over-provisioned" | "under-provisioned"
        "reasoning": str
    }
    """
    db = db_session if db_session else SessionLocal()
    try:
        # 1. Fetch Service config
        service = db.query(Service).filter(Service.service_name == service_name).first()
        if not service:
            return {
                "error": f"Service '{service_name}' not found in registry.",
                "service_name": service_name,
                "status": "unknown"
            }

        # 2. Query historical usage samples in the lookback window
        cutoff_time = time.time() - (lookback_days * 86400)
        samples = (
            db.query(UsageSample)
            .filter(UsageSample.service_name == service_name)
            .filter(UsageSample.timestamp >= cutoff_time)
            .order_by(UsageSample.timestamp.desc())
            .all()
        )

        sample_count = len(samples)
        
        # Current specs from the service definition
        curr_cpu_req = service.cpu_request or 0
        curr_cpu_lim = service.cpu_limit or 0
        curr_mem_req = service.mem_request or 0.0
        curr_mem_lim = service.mem_limit or 0.0

        current_monthly_cost = calculate_monthly_cost(curr_cpu_req, curr_mem_req)

        # Handle case with no samples
        if sample_count == 0:
            return {
                "service_name": service_name,
                "namespace": service.namespace,
                "lookback_days": lookback_days,
                "sample_count": 0,
                "current": {
                    "cpu_request": curr_cpu_req,
                    "cpu_limit": curr_cpu_lim,
                    "mem_request": int(curr_mem_req),
                    "mem_limit": int(curr_mem_lim),
                    "monthly_cost": current_monthly_cost
                },
                "recommended": {
                    "cpu_request": curr_cpu_req,
                    "cpu_limit": curr_cpu_lim,
                    "mem_request": int(curr_mem_req),
                    "mem_limit": int(curr_mem_lim),
                    "monthly_cost": current_monthly_cost
                },
                "confidence": {
                    "score": 0,
                    "label": "low",
                    "reason": "No historical usage metrics found for this service in the lookback window."
                },
                "savings": {
                    "cpu_saving_m": 0,
                    "mem_saving_mib": 0.0,
                    "monthly_savings": 0.0
                },
                "status": "optimal",
                "reasoning": "No recommendations can be generated due to lack of metrics data."
            }

        # Extract metric arrays
        cpu_usages = [s.cpu_usage_millicores for s in samples if s.cpu_usage_millicores is not None]
        mem_usages = [s.mem_usage_mb for s in samples if s.mem_usage_mb is not None]
        last_sample_time = max(s.timestamp for s in samples)

        # Handle partial data cases
        if not cpu_usages or not mem_usages:
            return {
                "service_name": service_name,
                "namespace": service.namespace,
                "lookback_days": lookback_days,
                "sample_count": sample_count,
                "current": {
                    "cpu_request": curr_cpu_req,
                    "cpu_limit": curr_cpu_lim,
                    "mem_request": int(curr_mem_req),
                    "mem_limit": int(curr_mem_lim),
                    "monthly_cost": current_monthly_cost
                },
                "recommended": {
                    "cpu_request": curr_cpu_req,
                    "cpu_limit": curr_cpu_lim,
                    "mem_request": int(curr_mem_req),
                    "mem_limit": int(curr_mem_lim),
                    "monthly_cost": current_monthly_cost
                },
                "confidence": {
                    "score": 0,
                    "label": "low",
                    "reason": "Insufficient numeric CPU/Memory usage metrics found."
                },
                "savings": {
                    "cpu_saving_m": 0,
                    "mem_saving_mib": 0.0,
                    "monthly_savings": 0.0
                },
                "status": "optimal",
                "reasoning": "Usage samples exist but do not contain numeric resource measurements."
            }

        # Calculate Percentiles (P90 and P99)
        cpu_arr = np.array(cpu_usages)
        mem_arr = np.array(mem_usages)

        p90_cpu = np.percentile(cpu_arr, 90)
        p99_cpu = np.percentile(cpu_arr, 99)
        p90_mem = np.percentile(mem_arr, 90)
        p99_mem = np.percentile(mem_arr, 99)

        # Compute recommended CPU values
        rec_cpu_req = max(1, int(round(p90_cpu)))
        # Limit must be at least 1.2x recommended request
        rec_cpu_lim = max(1, int(round(p99_cpu)))
        min_cpu_lim = int(round(rec_cpu_req * CPU_LIMIT_MIN_MULTIPLIER))
        rec_cpu_lim = max(rec_cpu_lim, min_cpu_lim)

        # Compute recommended Memory values
        rec_mem_req = max(1, int(round(p90_mem)))
        # Limit must be at least P99 + 32MB safety buffer
        rec_mem_lim = max(1, int(round(p99_mem + MEM_LIMIT_MIN_BUFFER_MIB)))
        # Make sure limit is not less than recommended request + safety buffer
        rec_mem_lim = max(rec_mem_lim, rec_mem_req + int(MEM_LIMIT_MIN_BUFFER_MIB))

        recommended_monthly_cost = calculate_monthly_cost(rec_cpu_req, rec_mem_req)

        # Compute Savings (only positive difference represents saving/waste)
        cpu_saving = curr_cpu_req - rec_cpu_req
        mem_saving = curr_mem_req - rec_mem_req
        
        # Savings are calculated based on waste reduction (when over-provisioned).
        # If under-provisioned, we will suggest upgrading, resulting in negative savings (costs increase).
        monthly_savings = calculate_waste_cost(curr_cpu_req, rec_cpu_req, curr_mem_req, rec_mem_req)
        
        # If we are under-provisioned, let's represent savings accurately (costs will go up)
        if curr_cpu_req < rec_cpu_req or curr_mem_req < rec_mem_req:
            # We are under-provisioned; recommendations will cost MORE.
            # Set monthly_savings to a negative value representing increased cost needed.
            extra_cpu = max(0.0, rec_cpu_req - curr_cpu_req)
            extra_mem = max(0.0, rec_mem_req - curr_mem_req)
            monthly_savings = -calculate_monthly_cost(extra_cpu, extra_mem)

        # Determine waste / provisioning status
        # Compare recommended requests to current requests
        cpu_diff_pct = (curr_cpu_req - rec_cpu_req) / max(1.0, float(rec_cpu_req))
        mem_diff_pct = (curr_mem_req - rec_mem_req) / max(1.0, float(rec_mem_req))

        # We take the maximum deviation. If CPU is heavily over-provisioned or Mem is over-provisioned,
        # we mark as over-provisioned. If either is under-provisioned, we prioritize "under-provisioned" (risk warning).
        if cpu_diff_pct < -OPTIMAL_THRESHOLD_PCT or mem_diff_pct < -OPTIMAL_THRESHOLD_PCT:
            status = "under-provisioned"
            status_desc = "under-provisioned (at risk of CPU throttling or Memory OOM)."
        elif cpu_diff_pct > OPTIMAL_THRESHOLD_PCT or mem_diff_pct > OPTIMAL_THRESHOLD_PCT:
            status = "over-provisioned"
            status_desc = "over-provisioned (wasting resources and capital)."
        else:
            status = "optimal"
            status_desc = "optimally sized relative to actual historical workload requirements."

        # Generate human-friendly reasoning explanation
        confidence = calculate_confidence(sample_count, cpu_usages, mem_usages, last_sample_time)
        
        reasoning = (
            f"Service '{service_name}' is currently {status_desc} "
            f"Based on {sample_count} metrics samples over the last {lookback_days} days: "
            f"CPU usage peak (P90) is {int(p90_cpu)}m (current request: {curr_cpu_req}m). "
            f"Memory usage peak (P90) is {int(p90_mem)}Mi (current request: {curr_mem_req}Mi). "
        )
        
        if status == "over-provisioned":
            reasoning += f"Right-sizing requests to recommended levels can save around ${abs(monthly_savings):.2f}/month."
        elif status == "under-provisioned":
            reasoning += f"Increasing resource allocations to recommended levels will raise monthly cost by ${abs(monthly_savings):.2f}/month, but will mitigate service stability risks."
        else:
            reasoning += "No changes recommended at this time."

        return {
            "service_name": service_name,
            "namespace": service.namespace,
            "lookback_days": lookback_days,
            "sample_count": sample_count,
            "current": {
                "cpu_request": curr_cpu_req,
                "cpu_limit": curr_cpu_lim,
                "mem_request": int(curr_mem_req),
                "mem_limit": int(curr_mem_lim),
                "monthly_cost": current_monthly_cost
            },
            "recommended": {
                "cpu_request": rec_cpu_req,
                "cpu_limit": rec_cpu_lim,
                "mem_request": rec_mem_req,
                "mem_limit": rec_mem_lim,
                "monthly_cost": recommended_monthly_cost
            },
            "confidence": confidence,
            "savings": {
                "cpu_saving_m": int(cpu_saving),
                "mem_saving_mib": round(mem_saving, 2),
                "monthly_savings": round(monthly_savings, 2)
            },
            "status": status,
            "reasoning": reasoning
        }

    finally:
        if not db_session:
            db.close()
