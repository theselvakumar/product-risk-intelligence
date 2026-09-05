import uuid
from typing import List, Optional, Any, TYPE_CHECKING
from sqlalchemy import String, Text, Integer, Float, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.product import Product, ExtractedInformation
    from app.models.case import Case


class AnalysisResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Execution run of regulatory compliance and cross-source checks.
    """
    __tablename__ = "analysis_results"

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # LABELLING_COMPLIANCE, ADVERTISING_CLAIMS, ADDITIVES, FOSCOS, CONSISTENCY
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED", nullable=False, index=True)  # PENDING, PROCESSING, COMPLETED, FAILED
    total_checks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    violations_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_metadata: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="analysis_results")
    findings: Mapped[List["Finding"]] = relationship(
        "Finding",
        back_populates="analysis_result",
        cascade="all, delete-orphan",
    )


class RiskAssessment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Multi-dimensional compliance risk score, risk level tier, and severity breakdown.
    """
    __tablename__ = "risk_assessments"

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)  # 0.0 to 100.0
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # CRITICAL, HIGH, MEDIUM, LOW
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 to 1.0
    health_hazard_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    deception_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    licensing_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    vulnerability_multiplier: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    score_breakdown: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="risk_assessments")
    case: Mapped[Optional["Case"]] = relationship("Case", back_populates="risk_assessments")

    __table_args__ = (
        Index("ix_risk_assessments_level_score", "risk_level", "risk_score"),
    )


class Finding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Discrete, legally grounded compliance infraction or cross-source discrepancy.
    """
    __tablename__ = "findings"

    analysis_result_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("analysis_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extracted_info_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_information.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    finding_title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # CRITICAL, HIGH, MEDIUM, LOW
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 to 1.0
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # PACKAGING_LABEL, ECOMMERCE_WEB, FOSCOS_REGISTRY, CROSS_SOURCE_COMPARISON
    statutory_reference: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    rule_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    discrepancy_details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Relationships
    analysis_result: Mapped["AnalysisResult"] = relationship("AnalysisResult", back_populates="findings")
    extracted_info: Mapped[Optional["ExtractedInformation"]] = relationship("ExtractedInformation", back_populates="findings")
    evidence_items: Mapped[List["Evidence"]] = relationship(
        "Evidence",
        back_populates="finding",
        cascade="all, delete-orphan",
    )


class Evidence(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Digital evidentiary artifacts (visual crops, OCR tokens, PDF/A dossiers) supporting findings.
    """
    __tablename__ = "evidence"

    finding_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # IMAGE_CROP, RAW_DOM_SNIPPET, FOSCOS_SNAPSHOT, STATUTORY_DOSSIER_PDF
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    bounding_box: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(64), default="image/jpeg", nullable=False)
    metadata_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Relationship
    finding: Mapped["Finding"] = relationship("Finding", back_populates="evidence_items")
