"""
Overkube — Pydantic Response & Request Schemas
==============================================
Defines typed structures for API requests and response validation.
These ensure consistent serialization formats and generate correct OpenAPI specs.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


# ── Resource Specs ────────────────────────────────────────────────────────────

class ResourceSpec(BaseModel):
    """CPU and memory limits or requests."""
    cpu_request: int = Field(..., description="CPU request in millicores (m)")
    cpu_limit: int = Field(..., description="CPU limit in millicores (m)")
    mem_request: int = Field(..., description="Memory request in MiB")
    mem_limit: int = Field(..., description="Memory limit in MiB")
    monthly_cost: float = Field(..., description="Estimated monthly cost in USD")


# ── Service Schemas ───────────────────────────────────────────────────────────

class ServiceListItem(BaseModel):
    """Brief details of a service for list displays."""
    id: int
    service_name: str
    namespace: str
    waste_profile: Optional[str] = Field(None, description="Initial synthetic profile pattern classification")
    last_seen: float = Field(..., description="UTC epoch seconds of last metrics scrape")
    cpu_request: Optional[int] = Field(None, description="Currently configured CPU request in millicores")
    cpu_limit: Optional[int] = Field(None, description="Currently configured CPU limit in millicores")
    mem_request: Optional[int] = Field(None, description="Currently configured Memory request in MiB")
    mem_limit: Optional[int] = Field(None, description="Currently configured Memory limit in MiB")
    waste_status: str = Field(..., description="Waste category classification ('over' | 'under' | 'optimal')")

    class Config:
        from_attributes = True


# ── Recommendation Schemas ────────────────────────────────────────────────────

class ConfidenceInfo(BaseModel):
    """Metric confidence scoring components."""
    score: int = Field(..., description="Confidence score from 0 to 100")
    label: str = Field(..., description="Confidence category: 'high' | 'medium' | 'low'")
    reason: str = Field(..., description="Text description of the confidence justification")


class SavingsInfo(BaseModel):
    """Estimated resource and spend savings."""
    cpu_saving_m: int = Field(..., description="Difference between current and recommended CPU request in millicores")
    mem_saving_mib: float = Field(..., description="Difference between current and recommended Memory request in MiB")
    monthly_savings: float = Field(..., description="Estimated monthly savings in USD ($/month)")


class RecommendationResponse(BaseModel):
    """Full detail of resource recommendations and savings analysis."""
    service_name: str
    namespace: str
    lookback_days: int
    sample_count: int
    current: ResourceSpec
    recommended: ResourceSpec
    confidence: ConfidenceInfo
    savings: SavingsInfo
    status: str = Field(..., description="Waste categorization: 'over-provisioned' | 'under-provisioned' | 'optimal'")
    reasoning: str = Field(..., description="Human-friendly explanation of findings and action steps")


# ── History/Chart Schemas ─────────────────────────────────────────────────────

class HistoryPoint(BaseModel):
    """A single downsampled time-series usage metrics point for charting."""
    timestamp: float = Field(..., description="UTC epoch seconds")
    cpu_usage_millicores: Optional[int] = Field(None, description="Actual CPU usage in millicores")
    mem_usage_mb: Optional[float] = Field(None, description="Actual memory usage in MiB")
    cpu_request: Optional[int] = Field(None, description="Configured CPU request in millicores")
    cpu_limit: Optional[int] = Field(None, description="Configured CPU limit in millicores")
    mem_request: Optional[int] = Field(None, description="Configured memory request in MiB")
    mem_limit: Optional[int] = Field(None, description="Configured memory limit in MiB")


class HistoryResponse(BaseModel):
    """Time-series usage data payload for a service."""
    service_name: str
    lookback_days: int
    points: List[HistoryPoint]


# ── Waste Report Schemas ──────────────────────────────────────────────────────

class ServiceWasteSummary(BaseModel):
    """Waste summary for an individual service."""
    service_name: str
    namespace: str
    status: str
    current_cost: float
    recommended_cost: float
    monthly_savings: float
    confidence_score: int
    confidence_label: str


class WasteReportResponse(BaseModel):
    """Cluster-wide cost waste summary report."""
    total_current_cost: float = Field(..., description="Total monthly spend on current requests")
    total_recommended_cost: float = Field(..., description="Total monthly spend under recommended requests")
    total_monthly_savings: float = Field(..., description="Total potential savings per month across all services")
    service_counts: dict[str, int] = Field(..., description="Count of services by waste status classification")
    services: List[ServiceWasteSummary] = Field(..., description="Cost optimization summary details per service")
    top_offenders: List[ServiceWasteSummary] = Field(..., description="Top 5 services with the most potential savings")


# ── Action / Apply Schemas ────────────────────────────────────────────────────

class ApplyRecommendationRequest(BaseModel):
    """Payload to apply a recommendation (unused for stubs but required for schema validation)."""
    reason: Optional[str] = Field(None, description="Optional developer comments / justification")


class ApplyRecommendationResponse(BaseModel):
    """Result of applying a resource recommendation."""
    service_name: str
    status: str = Field(..., description="Status of the application ('applied' | 'dry_run')")
    applied_at: float = Field(..., description="UTC epoch timestamp of when application was logged")
    pull_request_url: Optional[str] = Field(None, description="GitHub pull request URL if GitOps tracking is enabled")
    message: str = Field(..., description="Details regarding GitOps outcome or stub confirmation")
