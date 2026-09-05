import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ContributingFactorSchema(BaseModel):
    """Explainable per-dimension contribution to the risk score."""
    dimension: str
    finding_count: int
    max_severity: str
    weighted_contribution: float = Field(..., ge=0.0, le=1.0)
    raw_dimension_score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)

    model_config = ConfigDict(from_attributes=True)


class RiskAssessmentReport(BaseModel):
    """
    Internal case prioritization risk assessment report.

    IMPORTANT: This is an internal prioritization instrument only.
    See the 'disclaimer' field for the full legal notice.
    """
    case_id: uuid.UUID
    product_id: uuid.UUID
    case_number: str
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Internal prioritization score [0.0–1.0]")
    risk_level: str = Field(..., description="LOW, MEDIUM, or HIGH — internal triage classification")
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    contributing_factors: List[ContributingFactorSchema] = Field(default_factory=list)
    score_explanation: str
    data_completeness_ratio: float = Field(..., ge=0.0, le=1.0)
    total_findings_analyzed: int
    disclaimer: str = Field(
        ...,
        description="Mandatory legal notice — this score is NOT a regulatory determination.",
    )
    engine_version: str
    execution_timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
