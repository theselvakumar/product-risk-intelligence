import uuid
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ProvenanceRecord(BaseModel):
    """Immutable provenance tracking original source of an extracted element."""
    source_type: str = Field(..., description="PRODUCT_URL, PACKAGING_OCR, OFFICER_DESCRIPTION, MANUAL_INPUT")
    source_id: Optional[str] = None
    original_text: str = Field(..., description="Exact verbatim text snippet from source")
    confidence: float = Field(..., ge=0.0, le=1.0)
    extraction_method: str = Field(default="RULE_BASED", description="RULE_BASED, PATTERN_REGEX, NLP_HEURISTIC, LLM_STRUCTURED")


class StructuredField(BaseModel, Generic[T]):
    """Generic wrapper maintaining a canonical field value along with its provenance."""
    value: T
    provenance: ProvenanceRecord


class StructuredProductMetadata(BaseModel):
    """Core product identity metadata with full source attribution."""
    name: Optional[StructuredField[str]] = None
    brand: Optional[StructuredField[str]] = None
    category: Optional[StructuredField[str]] = None
    manufacturer: Optional[StructuredField[str]] = None
    net_quantity: Optional[StructuredField[str]] = None


class StructuredIngredient(BaseModel):
    """Individual food ingredient with composition hierarchy, INS additive codes, and allergen status."""
    ingredient_name: str
    original_text: str
    source_type: str
    source_id: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    ins_number: Optional[str] = None  # e.g. "INS 211", "INS 330"
    is_additive: bool = False
    is_allergen: bool = False
    allergen_category: Optional[str] = None  # GLUTEN, CRUSTACEANS, EGGS, FISH, PEANUTS_NUTS, SOY, MILK, SULPHITES
    sub_components: List[str] = Field(default_factory=list)
    extraction_method: str = "RULE_BASED"


class StructuredClaim(BaseModel):
    """Marketing or statutory claim extracted from product labeling or e-commerce listing."""
    claim_text: str
    original_text: str
    claim_category: str = Field(
        ...,
        description="DISEASE_RISK_REDUCTION_OR_CURE, HEALTH_OR_FUNCTIONAL, NUTRITION_CONTENT, SUPERLATIVE_OR_ABSOLUTE, NATURAL_ORGANIC, GENERAL_COMMERCIAL",
    )
    source_type: str
    source_id: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    is_potentially_prohibited: bool = Field(
        default=False,
        description="True if claim violates FSSAI Regulation 4(7) or Section 24 by promising disease cure or mitigation.",
    )
    statutory_warning_flag: Optional[str] = None
    extraction_method: str = "RULE_BASED"


class StructuredLicense(BaseModel):
    """FSSAI statutory licensing information extracted from product evidence."""
    license_number: str = Field(..., description="14-digit FSSAI statutory license or registration number")
    original_text: str
    source_type: str
    source_id: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    is_valid_format: bool = True
    license_type: str = Field(default="STATE_OR_CENTRAL_LICENSE", description="STATE_OR_CENTRAL_LICENSE, REGISTRATION, UNKNOWN")
    state_code: Optional[str] = None
    extraction_method: str = "PATTERN_REGEX"


class CanonicalStructuredProduct(BaseModel):
    """Complete synthesized structured product dossier with multi-source consensus."""
    case_id: uuid.UUID
    product_id: uuid.UUID
    product_metadata: StructuredProductMetadata
    ingredients: List[StructuredIngredient] = Field(default_factory=list)
    claims: List[StructuredClaim] = Field(default_factory=list)
    license_info: List[StructuredLicense] = Field(default_factory=list)
    allergens_detected: List[str] = Field(default_factory=list)
    additives_detected: List[str] = Field(default_factory=list)
    prohibited_claims_count: int = 0
    duplicate_metrics: Dict[str, Any] = Field(default_factory=dict)
    provenance_summary: Dict[str, int] = Field(default_factory=dict)
    extraction_timestamp: datetime
    schema_version: str = "v1.0-FSSAI-Intelligence"

    model_config = ConfigDict(from_attributes=True)
