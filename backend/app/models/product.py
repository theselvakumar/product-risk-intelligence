import uuid
from typing import List, Optional, Any, TYPE_CHECKING
from sqlalchemy import String, Text, Integer, Float, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis import AnalysisResult, RiskAssessment, Finding
    from app.models.case import Case


class Product(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Canonical representation of a food product SKU subject to surveillance.
    """
    __tablename__ = "products"

    product_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    brand: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    fssai_license_number: Mapped[str | None] = mapped_column(String(14), nullable=True, index=True)
    barcode_or_gtin: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    net_quantity: Mapped[str | None] = mapped_column(String(128), nullable=True)
    declared_ingredients: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    sources: Mapped[List["ProductSource"]] = relationship(
        "ProductSource",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    images: Mapped[List["ProductImage"]] = relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    extracted_info: Mapped[List["ExtractedInformation"]] = relationship(
        "ExtractedInformation",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    analysis_results: Mapped[List["AnalysisResult"]] = relationship(
        "AnalysisResult",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    risk_assessments: Mapped[List["RiskAssessment"]] = relationship(
        "RiskAssessment",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    cases: Mapped[List["Case"]] = relationship(
        "Case",
        back_populates="product",
    )

    __table_args__ = (
        Index("ix_products_brand_category", "brand", "category"),
    )


class ProductSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Tracks the origin channel where the product was identified (Web URL, physical retail, quick-commerce).
    """
    __tablename__ = "product_sources"

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # ECOMMERCE_URL, PHYSICAL_RETAIL, DARK_STORE, FOSCOS_REGISTRY
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    seller_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_payload_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Relationship
    product: Mapped["Product"] = relationship("Product", back_populates="sources")

    @property
    def raw_content(self) -> Optional[str]:
        if isinstance(self.raw_payload_json, dict):
            return self.raw_payload_json.get("raw_content")
        return None


class ProductImage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Master packaging image assets with cryptographic integrity hashes.
    """
    __tablename__ = "product_images"

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # FRONT_OF_PACK, BACK_OF_PACK, NUTRITION_PANEL, INGREDIENT_LIST
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(64), default="image/jpeg", nullable=False)
    resolution_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution_height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="images")
    extracted_zones: Mapped[List["ExtractedInformation"]] = relationship(
        "ExtractedInformation",
        back_populates="image",
    )

    @property
    def file_hash_sha256(self) -> str:
        return self.sha256_hash


class ExtractedInformation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Structured information extracted from product images and scraped metadata.
    """
    __tablename__ = "extracted_information"

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_images.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    zone_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # NUTRITION_TABLE, INGREDIENTS, CLAIMS, VEG_NONVEG_LOGO, FSSAI_LICENSE
    bounding_box: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_data: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    extractor_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="extracted_info")
    image: Mapped[Optional["ProductImage"]] = relationship("ProductImage", back_populates="extracted_zones")
    findings: Mapped[List["Finding"]] = relationship(
        "Finding",
        back_populates="extracted_info",
    )
