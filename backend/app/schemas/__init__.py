"""DRISHTI Pydantic Schemas Package"""

from app.schemas.health import DatabaseHealth, HealthResponse
from app.schemas.user import UserBase, UserCreate, UserUpdate, UserRead
from app.schemas.product import (
    ProductBase, ProductCreate, ProductUpdate, ProductRead,
    ProductSourceBase, ProductSourceCreate, ProductSourceRead,
    ProductImageBase, ProductImageCreate, ProductImageRead,
    ExtractedInformationBase, ExtractedInformationCreate, ExtractedInformationRead,
)
from app.schemas.analysis import (
    AnalysisResultBase, AnalysisResultCreate, AnalysisResultRead,
    FindingBase, FindingCreate, FindingRead,
    EvidenceBase, EvidenceCreate, EvidenceRead,
    RiskAssessmentBase, RiskAssessmentCreate, RiskAssessmentRead,
)
from app.schemas.case import (
    CaseBase, CaseCreate, CaseUpdate, CaseRead,
    CaseReviewBase, CaseReviewCreate, CaseReviewRead,
    AuditLogBase, AuditLogCreate, AuditLogRead,
)
from app.schemas.auth import (
    LoginRequest, TokenResponse, LogoutResponse, CurrentUserResponse,
)
from app.schemas.submission import (
    SourceAddRequest, SourceResponse, ProductImageResponse,
    CaseDetailResponse, CaseSubmissionResponse,
)

__all__ = [
    "DatabaseHealth", "HealthResponse",
    "LoginRequest", "TokenResponse", "LogoutResponse", "CurrentUserResponse",
    "DashboardMetrics", "RecentCaseItem", "ProductSubmissionRequest",
    "SourceAddRequest", "SourceResponse", "ProductImageResponse",
    "CaseDetailResponse", "CaseSubmissionResponse",
    "UserBase", "UserCreate", "UserUpdate", "UserRead",
    "ProductBase", "ProductCreate", "ProductUpdate", "ProductRead",
    "ProductSourceBase", "ProductSourceCreate", "ProductSourceRead",
    "ProductImageBase", "ProductImageCreate", "ProductImageRead",
    "ExtractedInformationBase", "ExtractedInformationCreate", "ExtractedInformationRead",
    "AnalysisResultBase", "AnalysisResultCreate", "AnalysisResultRead",
    "FindingBase", "FindingCreate", "FindingRead",
    "EvidenceBase", "EvidenceCreate", "EvidenceRead",
    "RiskAssessmentBase", "RiskAssessmentCreate", "RiskAssessmentRead",
    "CaseBase", "CaseCreate", "CaseUpdate", "CaseRead",
    "CaseReviewBase", "CaseReviewCreate", "CaseReviewRead",
    "AuditLogBase", "AuditLogCreate", "AuditLogRead",
]
