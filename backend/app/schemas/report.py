"""Pydantic schemas for Phase 15: Product Compliance Risk Intelligence Report."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CaseInfoSection(BaseModel):
    """Section 1: Case Information."""
    case_id: str
    case_number: str
    created_at: str
    status: str
    priority: str
    assigned_officer: Optional[str] = None
    jurisdiction: Optional[str] = None


class ProductInfoSection(BaseModel):
    """Section 2: Product Information."""
    product_name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    fssai_license_number: Optional[str] = None


class SubmittedImageItem(BaseModel):
    """Metadata for submitted evidence images."""
    image_id: Optional[str] = None
    image_type: str
    image_url: Optional[str] = None
    sha256_hash: Optional[str] = None
    file_name: Optional[str] = None


class SourceInfoSection(BaseModel):
    """Section 3: Source Information."""
    product_url: Optional[str] = None
    platform: Optional[str] = None
    submitted_description: Optional[str] = None
    submitted_images: List[SubmittedImageItem] = Field(default_factory=list)
    submission_notes: Optional[str] = None


class DimensionBreakdownItem(BaseModel):
    """Component dimension contribution to risk score."""
    dimension: str
    finding_count: int
    max_severity: str
    weighted_contribution: float
    raw_dimension_score: float
    confidence: float


class RiskAssessmentSection(BaseModel):
    """Section 4: Risk Assessment."""
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    total_findings_analyzed: int
    data_completeness_ratio: float
    score_explanation: Optional[str] = None
    dimension_breakdown: List[DimensionBreakdownItem] = Field(default_factory=list)
    assessment_timestamp: Optional[str] = None


class DetectedFindingItem(BaseModel):
    """Section 5: Detected Findings."""
    finding_id: str
    title: str
    description: str
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"
    confidence: float
    dimension: str
    rule_code: Optional[str] = None
    statutory_reference: Optional[str] = None
    why_flagged: Optional[str] = None


class EvidenceItem(BaseModel):
    """Section 6: Evidence item."""
    evidence_id: str
    evidence_type: str  # "URL", "IMAGE", "OCR_TEXT", "SUBMITTED_TEXT", "EXTRACTED_DATA"
    source: str
    extracted_text: Optional[str] = None
    image_url: Optional[str] = None
    sha256_hash: Optional[str] = None
    confidence_score: Optional[float] = None
    timestamp: str
    linked_finding_ids: List[str] = Field(default_factory=list)


class AnalysisLimitationsSection(BaseModel):
    """Section 7: Analysis Limitations."""
    missing_information: List[str] = Field(default_factory=list)
    ocr_limitations: List[str] = Field(default_factory=list)
    ai_confidence_limitations: List[str] = Field(default_factory=list)
    data_completeness_ratio: float = 0.0
    overall_completeness_assessment: str = ""


class ReviewRecommendationSection(BaseModel):
    """Section 8: Review Recommendation."""
    recommendation: str  # "PRIORITY_REVIEW", "STANDARD_REVIEW", "ADDITIONAL_INFO_REQUIRED"
    priority_level: str  # "URGENT_P1", "HIGH_P2", "ROUTINE_P3", "MONITORING_P4"
    recommendation_reason: str
    suggested_actions: List[str] = Field(default_factory=list)
    statutory_notice_recommended: bool = False
    sampling_recommended: bool = False
    lab_referral_recommended: bool = False


class CaseComplianceReportData(BaseModel):
    """Composite Structured Product Compliance Risk Intelligence Report."""
    report_title: str = "PRODUCT COMPLIANCE RISK INTELLIGENCE REPORT"
    report_identifier: str
    generated_at: str
    generating_system: str = "DRISHTI Regulatory Intelligence System v1.0"
    
    # 8 Structured Sections
    case_info: CaseInfoSection
    product_info: ProductInfoSection
    source_info: SourceInfoSection
    risk_assessment: RiskAssessmentSection
    detected_findings: List[DetectedFindingItem] = Field(default_factory=list)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    analysis_limitations: AnalysisLimitationsSection
    review_recommendation: ReviewRecommendationSection

    # Statutory Governance Disclaimers
    mandatory_statutory_disclaimer: str = (
        "The analysis is an AI-assisted decision-support assessment. "
        "Final regulatory decisions require human authority review."
    )
    legal_framework_notice: str = (
        "Generated under statutory surveillance provisions of the Food Safety and Standards Act, 2006. "
        "This dossier constitutes internal regulatory decision support and does not replace statutory "
        "adjudication, lab analysis certificates under Section 45/46, or judicial proceedings."
    )
    sha256_report_hash: Optional[str] = None
