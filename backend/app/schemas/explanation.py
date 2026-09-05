import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    """Verbatim evidence artifact tied to a specific finding."""
    evidence_type: str                # OCR_TEXT, CLAIM_TEXT, INGREDIENT_TEXT, etc.
    raw_text: str                     # Exact text extracted from the source
    source_type: str                  # PACKAGING_OCR, ECOMMERCE_URL, OFFICER_DESCRIPTION, MANUAL_INPUT
    source_reference: Optional[str] = None  # URI or record ID


class FindingExplanation(BaseModel):
    """
    Fully explainable finding record.
    Every field references existing stored data — no inference is introduced.
    """
    finding_id: uuid.UUID
    finding_title: str
    description: str
    severity: str                     # CRITICAL, HIGH, MEDIUM, LOW, INFO
    source: str                       # Analysis source identifier
    confidence: float = Field(..., ge=0.0, le=1.0)
    rule_code: Optional[str] = None
    statutory_reference: Optional[str] = None
    reason_for_flagging: str          # Human-readable why this was flagged
    evidence: List[EvidenceItem] = Field(default_factory=list)
    discrepancy_details: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class RiskScoreExplanation(BaseModel):
    """Structured breakdown of the risk score computation."""
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_level: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    score_explanation: str
    contributing_factors: List[Dict[str, Any]] = Field(default_factory=list)
    data_completeness_ratio: float
    disclaimer: str


class ProductSummary(BaseModel):
    """Essential product identification information."""
    product_id: uuid.UUID
    product_name: Optional[str]
    brand: Optional[str]
    category: Optional[str]
    manufacturer: Optional[str]
    fssai_license_number: Optional[str]


class ExplanationReport(BaseModel):
    """
    Full explainability bundle for a case.
    Aggregates product info, findings with evidence, risk score, and 'why' narrative.
    All explanations reference stored records only.
    """
    case_id: uuid.UUID
    case_number: str
    product: ProductSummary
    total_findings: int
    findings_by_severity: Dict[str, int] = Field(default_factory=dict)
    findings: List[FindingExplanation] = Field(default_factory=list)
    risk_assessment: Optional[RiskScoreExplanation] = None
    why_flagged_summary: List[str] = Field(
        default_factory=list,
        description="Ordered, human-readable reasons this case requires attention.",
    )
    generated_at: datetime
    provenance_note: str = Field(
        default=(
            "All findings and explanations in this report reference stored, "
            "verifiable evidence records. No inferences have been introduced. "
            "Each finding traces directly to its source record."
        )
    )

    model_config = ConfigDict(from_attributes=True)
