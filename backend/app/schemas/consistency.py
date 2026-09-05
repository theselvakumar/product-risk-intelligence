import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SourceFieldEvidence(BaseModel):
    """Verbatim evidence extracted from a specific source for a given field."""
    source_type: str = Field(..., description="ECOMMERCE_URL, PACKAGING_OCR, OFFICER_DESCRIPTION, MANUAL_INPUT")
    source_id: Optional[str] = None
    raw_text: str = Field(..., description="Verbatim extracted text from this source")
    normalized_value: str = Field(..., description="Normalized canonical value for comparison")


class FieldComparisonRecord(BaseModel):
    """Pairwise cross-source comparison result for a single product information field."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    field_name: str = Field(..., description="product_name, manufacturer, ingredients, claims, license_number")
    source_a: SourceFieldEvidence
    source_b: SourceFieldEvidence
    comparison_result: str = Field(
        ...,
        description="CONSISTENT, MINOR_WORDING_DIFFERENCE, INCONSISTENT, MISSING_IN_SOURCE",
    )
    severity_suggestion: str = Field(
        default="INFO",
        description="INFO, LOW, MEDIUM, HIGH, CRITICAL",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    match_method: str = Field(
        ...,
        description="EXACT, NORMALIZED, SEMANTIC",
    )
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    detected_difference: str = Field(
        ...,
        description="Human-readable description of the identified difference",
    )


class ConsistencyReport(BaseModel):
    """Comprehensive cross-source information consistency analysis report."""
    case_id: uuid.UUID
    product_id: uuid.UUID
    case_number: str
    comparisons: List[FieldComparisonRecord] = Field(default_factory=list)
    summary_stats: Dict[str, int] = Field(default_factory=dict)
    total_sources_analyzed: int = 0
    total_fields_compared: int = 0
    inconsistency_count: int = 0
    minor_difference_count: int = 0
    consistent_count: int = 0
    missing_in_source_count: int = 0
    highest_severity: str = "INFO"
    execution_timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
