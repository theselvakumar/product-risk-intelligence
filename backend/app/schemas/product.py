import uuid
from datetime import datetime
from typing import Optional, Any, List
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# ProductSource Schemas
# ---------------------------------------------------------------------------
class ProductSourceBase(BaseModel):
    source_type: str = Field(..., description="ECOMMERCE_URL, PHYSICAL_RETAIL, DARK_STORE, FOSCOS_REGISTRY")
    source_url: Optional[str] = None
    platform_name: Optional[str] = None
    seller_name: Optional[str] = None
    raw_payload_json: Optional[Any] = None


class ProductSourceCreate(ProductSourceBase):
    product_id: uuid.UUID


class ProductSourceRead(ProductSourceBase):
    id: uuid.UUID
    product_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# ProductImage Schemas
# ---------------------------------------------------------------------------
class ProductImageBase(BaseModel):
    image_type: str = Field(..., description="FRONT_OF_PACK, BACK_OF_PACK, NUTRITION_PANEL, INGREDIENT_LIST")
    storage_uri: str
    sha256_hash: str
    file_size_bytes: Optional[int] = None
    mime_type: str = "image/jpeg"
    resolution_width: Optional[int] = None
    resolution_height: Optional[int] = None


class ProductImageCreate(ProductImageBase):
    product_id: uuid.UUID


class ProductImageRead(ProductImageBase):
    id: uuid.UUID
    product_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# ExtractedInformation Schemas
# ---------------------------------------------------------------------------
class ExtractedInformationBase(BaseModel):
    zone_type: str = Field(..., description="NUTRITION_TABLE, INGREDIENTS, CLAIMS, VEG_NONVEG_LOGO, FSSAI_LICENSE")
    bounding_box: Optional[Any] = None
    raw_text: str
    parsed_data: Optional[Any] = None
    confidence_score: Optional[float] = None
    extractor_version: Optional[str] = None


class ExtractedInformationCreate(ExtractedInformationBase):
    product_id: uuid.UUID
    image_id: Optional[uuid.UUID] = None


class ExtractedInformationRead(ExtractedInformationBase):
    id: uuid.UUID
    product_id: uuid.UUID
    image_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Product Schemas
# ---------------------------------------------------------------------------
class ProductBase(BaseModel):
    product_name: str
    brand: str
    category: str
    manufacturer: Optional[str] = None
    fssai_license_number: Optional[str] = None
    barcode_or_gtin: Optional[str] = None
    net_quantity: Optional[str] = None
    declared_ingredients: Optional[str] = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    product_name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    fssai_license_number: Optional[str] = None
    barcode_or_gtin: Optional[str] = None
    net_quantity: Optional[str] = None
    declared_ingredients: Optional[str] = None


class ProductSimpleRead(ProductBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductRead(ProductBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    sources: List[ProductSourceRead] = []
    images: List[ProductImageRead] = []

    model_config = ConfigDict(from_attributes=True)
