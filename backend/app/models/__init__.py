"""
DRISHTI Core Database Models Package
Re-exports all 12 core entity models for SQLAlchemy and Alembic.
"""

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User
from app.models.product import (
    Product,
    ProductSource,
    ProductImage,
    ExtractedInformation,
)
from app.models.analysis import (
    AnalysisResult,
    RiskAssessment,
    Finding,
    Evidence,
)
from app.models.case import (
    Case,
    CaseReview,
    AuditLog,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "User",
    "Product",
    "ProductSource",
    "ProductImage",
    "ExtractedInformation",
    "AnalysisResult",
    "RiskAssessment",
    "Finding",
    "Evidence",
    "Case",
    "CaseReview",
    "AuditLog",
]
