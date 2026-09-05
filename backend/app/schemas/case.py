import uuid
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Canonical Case States (Phase 14 Statutory Lifecycle)
# ---------------------------------------------------------------------------
class CaseState(str, Enum):
    # Automated pipeline states
    SUBMITTED         = "SUBMITTED"
    EXTRACTING        = "EXTRACTING"
    ANALYZING         = "ANALYZING"
    ANALYSIS_COMPLETE = "ANALYSIS_COMPLETE"

    # Triage and Review states
    STANDARD_REVIEW   = "STANDARD_REVIEW"
    PRIORITY_REVIEW   = "PRIORITY_REVIEW"
    UNDER_REVIEW      = "UNDER_REVIEW"
    REVIEW_COMPLETED  = "REVIEW_COMPLETED"

    # Statutory enforcement extensions
    FIELD_INSPECTION_ORDERED = "FIELD_INSPECTION_ORDERED"
    SAMPLE_DRAWN             = "SAMPLE_DRAWN"
    NOTICE_ISSUED_SEC32      = "NOTICE_ISSUED_SEC32"
    ADJUDICATION_PENDING     = "ADJUDICATION_PENDING"
    RESOLVED                 = "RESOLVED"
    CLOSED                   = "CLOSED"


class CaseReviewAction(str, Enum):
    APPROVE_INSPECTION       = "APPROVE_INSPECTION"
    ISSUE_SECTION_32_NOTICE  = "ISSUE_SECTION_32_NOTICE"
    ORDER_LAB_TESTING        = "ORDER_LAB_TESTING"
    SAMPLE_DRAWN             = "SAMPLE_DRAWN"
    DISMISS_CASE             = "DISMISS_CASE"
    REFER_TO_ADJUDICATION    = "REFER_TO_ADJUDICATION"
    REQUEST_CORRECTION       = "REQUEST_CORRECTION"
    ENDORSE_COMPLIANT        = "ENDORSE_COMPLIANT"


# ---------------------------------------------------------------------------
# CaseReview Schemas
# ---------------------------------------------------------------------------
class CaseReviewBase(BaseModel):
    review_action: str = Field(
        ...,
        description="APPROVE_INSPECTION, ISSUE_SECTION_32_NOTICE, ORDER_LAB_TESTING, SAMPLE_DRAWN, DISMISS_CASE, REFER_TO_ADJUDICATION, REQUEST_CORRECTION, ENDORSE_COMPLIANT",
    )
    remarks: str
    action_metadata: Optional[Any] = None


class CaseReviewCreate(CaseReviewBase):
    case_id: uuid.UUID
    reviewer_id: uuid.UUID


class CaseReviewSubmission(BaseModel):
    review_action: str
    remarks: str
    new_status: Optional[str] = Field(default="REVIEW_COMPLETED")
    action_metadata: Optional[Any] = None


class CaseReviewRead(CaseReviewBase):
    id: uuid.UUID
    case_id: uuid.UUID
    reviewer_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# AuditLog Schemas
# ---------------------------------------------------------------------------
class AuditLogBase(BaseModel):
    action: str
    entity_type: str
    entity_id: str
    details_json: Optional[Any] = None
    ip_address: Optional[str] = None


class AuditLogCreate(AuditLogBase):
    case_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None


class AuditLogRead(AuditLogBase):
    id: uuid.UUID
    case_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseAuditTrailResponse(BaseModel):
    case_id: uuid.UUID
    case_number: str
    total_events: int
    events: List[AuditLogRead]


# ---------------------------------------------------------------------------
# Case Schemas
# ---------------------------------------------------------------------------
class CaseBase(BaseModel):
    case_number: str
    title: str
    status: str = Field(default="SUBMITTED")
    priority: str = Field(default="ROUTINE_P3", description="URGENT_P1, HIGH_P2, ROUTINE_P3, MONITORING_P4")
    jurisdiction_district: Optional[str] = None
    description: Optional[str] = None


class CaseCreate(CaseBase):
    product_id: uuid.UUID
    assigned_user_id: Optional[uuid.UUID] = None


class CaseUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_user_id: Optional[uuid.UUID] = None
    jurisdiction_district: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    closed_at: Optional[datetime] = None


class CaseStatusUpdate(BaseModel):
    status: str = Field(..., description="Target CaseState")
    reason: Optional[str] = None
    notes: Optional[str] = None


class CaseRead(CaseBase):
    id: uuid.UUID
    product_id: uuid.UUID
    assigned_user_id: Optional[uuid.UUID] = None
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseWithReviewsRead(CaseRead):
    reviews: List[CaseReviewRead] = []



# ---------------------------------------------------------------------------
# Phase 14 Priority Review Queue Schemas
# ---------------------------------------------------------------------------
class PriorityQueueItem(BaseModel):
    case_id: uuid.UUID
    case_number: str
    product_id: uuid.UUID
    product_name: str
    brand: str
    category: str
    risk_score: float
    risk_level: str
    confidence: float
    submission_date: datetime
    status: str
    priority: str
    title: str
    assigned_officer: Optional[str] = None
    assigned_user_id: Optional[uuid.UUID] = None
    total_findings: int = 0

    model_config = ConfigDict(from_attributes=True)


class PriorityQueueResponse(BaseModel):
    items: List[PriorityQueueItem]
    total_count: int
    limit: int
    offset: int
