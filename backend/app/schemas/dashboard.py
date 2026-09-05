import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class DashboardMetrics(BaseModel):
    """Aggregate regulatory compliance and case intelligence metrics."""
    total_cases: int = Field(..., description="Total active and historical cases")
    cases_under_analysis: int = Field(..., description="Cases in triaging or initial investigation")
    low_risk: int = Field(..., description="Products categorized as Low Risk")
    medium_risk: int = Field(..., description="Products categorized as Medium Risk")
    high_risk: int = Field(..., description="Products categorized as High or Critical Risk")
    pending_review: int = Field(..., description="Cases awaiting officer determination or notice issuance")


class RecentCaseItem(BaseModel):
    """Normalized case item for recent cases table and priority queues."""
    case_id: uuid.UUID
    case_number: str
    product_name: str
    brand: str
    category: str
    submission_date: datetime
    risk_level: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW")
    risk_score: float = Field(..., ge=0.0, le=100.0)
    status: str = Field(..., description="Case lifecycle status")
    priority: str = Field(..., description="URGENT_P1, HIGH_P2, ROUTINE_P3, MONITORING_P4")
    title: str

    model_config = ConfigDict(from_attributes=True)


class ProductSubmissionRequest(BaseModel):
    """Submission payload for authority product surveillance."""
    product_name: str = Field(..., min_length=2, max_length=500)
    brand: str = Field(..., min_length=2, max_length=255)
    category: str = Field(..., min_length=2, max_length=255)
    manufacturer: Optional[str] = None
    fssai_license_number: Optional[str] = None
    source_type: str = Field(default="ECOMMERCE_URL", description="ECOMMERCE_URL, PHYSICAL_RETAIL, DARK_STORE")
    source_url: Optional[str] = None
    notes: Optional[str] = None
