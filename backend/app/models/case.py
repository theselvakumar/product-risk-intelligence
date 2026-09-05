import uuid
from datetime import datetime
from typing import List, Optional, Any, TYPE_CHECKING
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User
    from app.models.analysis import RiskAssessment


class Case(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Regulatory investigation case container supporting inspection lifecycle and enforcement tracking.
    """
    __tablename__ = "cases"

    case_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assigned_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="TRIAGED",
        nullable=False,
        index=True,
    )  # TRIAGED, ASSIGNED, FIELD_INSPECTION_ORDERED, SAMPLE_DRAWN, NOTICE_ISSUED_SEC32, ADJUDICATION_PENDING, RESOLVED, CLOSED
    priority: Mapped[str] = mapped_column(
        String(32),
        default="ROUTINE_P3",
        nullable=False,
        index=True,
    )  # URGENT_P1, HIGH_P2, ROUTINE_P3, MONITORING_P4
    jurisdiction_district: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="cases")
    assigned_user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="assigned_cases",
        foreign_keys=[assigned_user_id],
    )
    reviews: Mapped[List["CaseReview"]] = relationship(
        "CaseReview",
        back_populates="case",
        cascade="all, delete-orphan",
    )
    risk_assessments: Mapped[List["RiskAssessment"]] = relationship(
        "RiskAssessment",
        back_populates="case",
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="case",
    )

    __table_args__ = (
        Index("ix_cases_status_priority", "status", "priority"),
    )


class CaseReview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Officer reviews, Section 32 Improvement Notice endorsements, and enforcement determinations.
    """
    __tablename__ = "case_reviews"

    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    review_action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )  # APPROVE_INSPECTION, ISSUE_SECTION_32_NOTICE, REQUEST_RETEST, DISMISS_CASE, ESCALATE_TO_TRIBUNAL
    remarks: Mapped[str] = mapped_column(Text, nullable=False)
    action_metadata: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="reviews")
    reviewer: Mapped["User"] = relationship("User", back_populates="case_reviews")


class AuditLog(Base, UUIDPrimaryKeyMixin):
    """
    Immutable statutory audit log tracking all regulatory actions, status shifts, and access events.
    """
    __tablename__ = "audit_logs"

    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    details_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    case: Mapped[Optional["Case"]] = relationship("Case", back_populates="audit_logs")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")
