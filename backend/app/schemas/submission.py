import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.product import ProductRead, ProductSimpleRead


class SourceAddRequest(BaseModel):
    """Payload to add a source to an existing case."""
    source_type: str = Field(..., description="ECOMMERCE_URL, PACKAGING_IMAGE, PRODUCT_DESCRIPTION, PHYSICAL_SAMPLE")
    source_url: Optional[str] = None
    platform_name: Optional[str] = None
    raw_content: Optional[str] = None
    source_metadata: Optional[Dict[str, Any]] = None


class SourceResponse(BaseModel):
    """Source response model."""
    id: uuid.UUID
    source_type: str
    source_url: Optional[str] = None
    platform_name: Optional[str] = None
    raw_content: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductImageResponse(BaseModel):
    """Uploaded image response model."""
    id: uuid.UUID
    image_type: str
    storage_uri: str
    file_hash_sha256: str = Field(default="", alias="sha256_hash")
    file_size_bytes: Optional[int] = None
    mime_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ProductJsonSubmissionRequest(BaseModel):
    """JSON submission payload for programmatic or automated case creation."""
    product_url: Optional[str] = None
    product_description: Optional[str] = None
    product_name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    fssai_license_number: Optional[str] = None
    notes: Optional[str] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None


class CaseDetailResponse(BaseModel):
    """Detailed case response including product, sources, and images."""
    id: uuid.UUID
    case_number: str
    status: str
    priority: str
    title: str
    description: Optional[str] = None
    jurisdiction_district: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    product: Optional[ProductSimpleRead] = None
    sources: List[SourceResponse] = Field(default_factory=list)
    images: List[ProductImageResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class CaseSubmissionResponse(BaseModel):
    """Case creation response confirmation."""
    case_id: uuid.UUID
    case_number: str
    product_id: uuid.UUID
    status: str = "SUBMITTED"
    title: str
    sources_count: int
    images_count: int
    created_at: datetime
    message: str
