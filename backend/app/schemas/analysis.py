import uuid
from datetime import datetime
from typing import Optional, Any, List
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Evidence Schemas
# ---------------------------------------------------------------------------
class EvidenceBase(BaseModel):
    evidence_type: str = Field(..., description="IMAGE_CROP, RAW_DOM_SNIPPET, FOSCOS_SNAPSHOT, STATUTORY_DOSSIER_PDF")
    storage_uri: str
    sha256_hash: str
    bounding_box: Optional[Any] = None
    caption: Optional[str] = None
    mime_type: str = "image/jpeg"
    metadata_json: Optional[Any] = None


class EvidenceCreate(EvidenceBase):
    finding_id: uuid.UUID


class EvidenceRead(EvidenceBase):
    id: uuid.UUID
    finding_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Finding Schemas
# ---------------------------------------------------------------------------
class FindingBase(BaseModel):
    finding_title: str
    description: str
    severity: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW")
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: str = Field(..., description="PACKAGING_LABEL, ECOMMERCE_WEB, FOSCOS_REGISTRY, CROSS_SOURCE_COMPARISON")
    statutory_reference: Optional[str] = None
    rule_code: Optional[str] = None
    discrepancy_details: Optional[Any] = None


class FindingCreate(FindingBase):
    analysis_result_id: uuid.UUID
    extracted_info_id: Optional[uuid.UUID] = None


class FindingRead(FindingBase):
    id: uuid.UUID
    analysis_result_id: uuid.UUID
    extracted_info_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    evidence_items: List[EvidenceRead] = []

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# AnalysisResult Schemas
# ---------------------------------------------------------------------------
class AnalysisResultBase(BaseModel):
    analysis_type: str = Field(..., description="LABELLING_COMPLIANCE, ADVERTISING_CLAIMS, ADDITIVES, FOSCOS, CONSISTENCY")
    status: str = "COMPLETED"
    total_checks: int = 0
    violations_found: int = 0
    summary: Optional[str] = None
    execution_metadata: Optional[Any] = None


class AnalysisResultCreate(AnalysisResultBase):
    product_id: uuid.UUID


class AnalysisResultRead(AnalysisResultBase):
    id: uuid.UUID
    product_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    findings: List[FindingRead] = []

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# RiskAssessment Schemas
# ---------------------------------------------------------------------------
class RiskAssessmentBase(BaseModel):
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Risk score on 0 to 100 scale")
    risk_level: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Model confidence 0 to 1")
    health_hazard_score: Optional[float] = None
    deception_score: Optional[float] = None
    licensing_score: Optional[float] = None
    vulnerability_multiplier: float = 1.0
    score_breakdown: Optional[Any] = None


class RiskAssessmentCreate(RiskAssessmentBase):
    product_id: uuid.UUID
    case_id: Optional[uuid.UUID] = None


class RiskAssessmentRead(RiskAssessmentBase):
    id: uuid.UUID
    product_id: uuid.UUID
    case_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
