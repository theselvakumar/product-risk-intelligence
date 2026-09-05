import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CasePipelineResult(BaseModel):
    """
    Structured outcome of the end-to-end statutory compliance analysis pipeline.
    """
    case_id: uuid.UUID
    case_number: str
    product_id: uuid.UUID
    status: str = Field(description="Current case status (e.g., ANALYSIS_COMPLETE, ANALYSIS_FAILED)")
    previous_status: Optional[str] = None
    priority: str = Field(description="Statutory enforcement priority (e.g., URGENT_P1, HIGH_P2, ROUTINE_P3)")
    ocr_processed: bool = False
    images_processed: int = 0
    intelligence_completed: bool = False
    deep_analysis_completed: bool = False
    consistency_completed: bool = False
    risk_assessment_completed: bool = False
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    confidence_score: Optional[float] = None
    total_findings: int = 0
    # Web Intelligence (Phase C2)
    web_collection_attempted: bool = False
    web_sources_found: int = 0
    web_sources_processed: int = 0
    web_collection_success: bool = False
    web_collection_errors: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    execution_timestamp: datetime
    execution_duration_ms: float = 0.0

    model_config = ConfigDict(from_attributes=True)
