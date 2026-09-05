import uuid
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.case import Case, CaseReview, AuditLog


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    User entity representing regulatory enforcement officers, analysts, and system administrators.
    """
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    badge_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # SUPER_ADMIN, CENTRAL_ANALYST, DESIGNATED_OFFICER, FOOD_SAFETY_OFFICER, LEGAL_AUDITOR
    jurisdiction_state: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    jurisdiction_district: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    assigned_cases: Mapped[List["Case"]] = relationship(
        "Case",
        back_populates="assigned_user",
        foreign_keys="Case.assigned_user_id",
    )
    case_reviews: Mapped[List["CaseReview"]] = relationship(
        "CaseReview",
        back_populates="reviewer",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
    )

    __table_args__ = (
        Index("ix_users_role_jurisdiction", "role", "jurisdiction_state", "jurisdiction_district"),
    )
