import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class OCRLine(BaseModel):
    """Extracted text line with bounding coordinates and confidence."""
    text: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    bounding_box: Optional[List[int]] = None  # [x1, y1, x2, y2]


class ImageQualityAssessment(BaseModel):
    """Quality and sharpness evaluation for uploaded packaging images."""
    is_blurry: bool = False
    sharpness_score: float
    width: int
    height: int
    aspect_ratio: float
    channels: int
    quality_grade: str = Field(default="ACCEPTABLE", description="EXCELLENT, ACCEPTABLE, DEGRADED, POOR")
    warnings: List[str] = Field(default_factory=list)


class OCRResultResponse(BaseModel):
    """Structured OCR extraction response."""
    extracted_info_id: uuid.UUID
    case_id: uuid.UUID
    image_id: Optional[uuid.UUID] = None
    product_id: uuid.UUID
    zone_type: str = "OCR_FULL_TEXT"
    raw_text: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    quality_assessment: ImageQualityAssessment
    lines: List[OCRLine] = Field(default_factory=list)
    word_count: int
    character_count: int
    extractor_version: str
    status: str = Field(default="SUCCESS", description="SUCCESS, LOW_QUALITY_WARNING, FAILED")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseOCRSummaryResponse(BaseModel):
    """Summary of all OCR processing across images in an investigation case."""
    case_id: uuid.UUID
    case_number: str
    total_images: int
    total_images_processed: int
    average_confidence: float
    aggregated_text: str
    results: List[OCRResultResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
