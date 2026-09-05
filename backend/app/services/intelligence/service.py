import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import AuditLog, Case
from app.models.product import ExtractedInformation, Product, ProductSource
from app.schemas.intelligence import (
    CanonicalStructuredProduct,
    ProvenanceRecord,
    StructuredClaim,
    StructuredField,
    StructuredIngredient,
    StructuredLicense,
    StructuredProductMetadata,
)
from app.services.intelligence.claim_classifier import ClaimClassifier
from app.services.intelligence.deduplicator import EntityDeduplicator
from app.services.intelligence.ingredient_parser import IngredientParser
from app.services.intelligence.license_extractor import LicenseExtractor
from app.services.intelligence.normalizer import TextNormalizer


class ProductIntelligenceService:
    """
    Transforms multi-source unstructured evidence (URL scrapes, packaging OCR,
    manual descriptions) into strongly-typed canonical product intelligence.
    """

    SCHEMA_VERSION = "v1.0-FSSAI-Intelligence"

    @classmethod
    async def structure_case_information(
        cls,
        case_id: uuid.UUID,
        db: AsyncSession,
        current_user_id: Optional[uuid.UUID] = None,
    ) -> CanonicalStructuredProduct:
        """
        Synthesizes structured product intelligence across all available evidence sources for a case.
        """
        now = datetime.now(timezone.utc)

        # 1. Fetch Case & Product
        case_stmt = select(Case).where(Case.id == case_id)
        case_obj = (await db.execute(case_stmt)).scalar_one_or_none()
        if not case_obj:
            raise ValueError(f"Case '{case_id}' not found.")

        prod_stmt = select(Product).where(Product.id == case_obj.product_id)
        prod_obj = (await db.execute(prod_stmt)).scalar_one_or_none()
        if not prod_obj:
            raise ValueError(f"Product '{case_obj.product_id}' not found.")

        # 2. Fetch all raw sources
        src_stmt = select(ProductSource).where(ProductSource.product_id == prod_obj.id)
        sources = (await db.execute(src_stmt)).scalars().all()

        # 3. Fetch all raw OCR records
        ocr_stmt = select(ExtractedInformation).where(
            ExtractedInformation.product_id == prod_obj.id,
            ExtractedInformation.zone_type == "OCR_FULL_TEXT",
        )
        ocr_records = (await db.execute(ocr_stmt)).scalars().all()

        # Containers for all extracted raw elements
        all_ingredients: List[StructuredIngredient] = []
        all_claims: List[StructuredClaim] = []
        all_licenses: List[StructuredLicense] = []
        provenance_counts: Dict[str, int] = {"URL": 0, "OCR": 0, "DESCRIPTION": 0, "METADATA": 0}

        # --- A. Process Basic Product Record ---
        base_name = prod_obj.product_name
        base_brand = prod_obj.brand
        base_category = TextNormalizer.normalize_category(prod_obj.category)
        base_manufacturer = prod_obj.manufacturer
        base_license = prod_obj.fssai_license_number

        metadata = StructuredProductMetadata()

        if base_name:
            metadata.name = StructuredField(
                value=base_name,
                provenance=ProvenanceRecord(
                    source_type="MANUAL_INPUT",
                    original_text=base_name,
                    confidence=0.95,
                    extraction_method="OFFICER_ENTRY",
                ),
            )
            provenance_counts["METADATA"] += 1

        if base_brand:
            metadata.brand = StructuredField(
                value=base_brand,
                provenance=ProvenanceRecord(
                    source_type="MANUAL_INPUT",
                    original_text=base_brand,
                    confidence=0.95,
                    extraction_method="OFFICER_ENTRY",
                ),
            )

        if base_category:
            metadata.category = StructuredField(
                value=base_category,
                provenance=ProvenanceRecord(
                    source_type="MANUAL_INPUT",
                    original_text=prod_obj.category,
                    confidence=0.90,
                    extraction_method="RULE_BASED",
                ),
            )

        if base_manufacturer:
            metadata.manufacturer = StructuredField(
                value=base_manufacturer,
                provenance=ProvenanceRecord(
                    source_type="MANUAL_INPUT",
                    original_text=base_manufacturer,
                    confidence=0.95,
                    extraction_method="OFFICER_ENTRY",
                ),
            )

        if base_license:
            lics = LicenseExtractor.extract_licenses(base_license, source_type="MANUAL_INPUT", base_confidence=0.95)
            all_licenses.extend(lics)

        # --- B. Process Product Sources (URLs & Descriptions) ---
        for src in sources:
            src_type = src.source_type
            src_id_str = str(src.id)
            payload = src.raw_payload_json or {}

            # URL & Public Web Intelligence Sources
            if src_type in ("ECOMMERCE_URL", "PRODUCT_URL", "WEB_SEARCH", "WEB_SCRAPED"):
                provenance_counts["URL"] += 1
                source_text = src.source_url or ""
                resolved_source_type = "WEB_SEARCH" if src_type == "WEB_SEARCH" else "PRODUCT_URL"
                # Check for claims or ingredients in URL payload if present
                if isinstance(payload, dict):
                    raw_text_content = payload.get("raw_content") or payload.get("description") or ""
                    if raw_text_content:
                        all_ingredients.extend(
                            IngredientParser.parse_ingredients_from_text(
                                raw_text_content,
                                source_type=resolved_source_type,
                                source_id=src_id_str,
                            )
                        )
                        all_claims.extend(
                            ClaimClassifier.extract_claims_from_text(
                                raw_text_content,
                                source_type=resolved_source_type,
                                source_id=src_id_str,
                            )
                        )
                        all_licenses.extend(
                            LicenseExtractor.extract_licenses(
                                raw_text_content,
                                source_type=resolved_source_type,
                                source_id=src_id_str,
                            )
                        )

                    # Enrich manufacturer if not present in manual metadata
                    web_mfr = payload.get("manufacturer")
                    if web_mfr and not metadata.manufacturer:
                        metadata.manufacturer = StructuredField(
                            value=web_mfr,
                            provenance=ProvenanceRecord(
                                source_type=resolved_source_type,
                                source_url=src.source_url,
                                original_text=web_mfr,
                                confidence=0.85,
                                extraction_method="WEB_SCRAPED",
                            ),
                        )

            # Product Description Source
            elif src_type == "PRODUCT_DESCRIPTION":
                provenance_counts["DESCRIPTION"] += 1
                desc_text = src.raw_content or ""
                if not desc_text and isinstance(payload, dict):
                    desc_text = payload.get("raw_content") or ""

                if desc_text:
                    cleaned_desc = TextNormalizer.clean_text(desc_text)
                    all_ingredients.extend(
                        IngredientParser.parse_ingredients_from_text(
                            cleaned_desc,
                            source_type="OFFICER_DESCRIPTION",
                            source_id=src_id_str,
                        )
                    )
                    all_claims.extend(
                        ClaimClassifier.extract_claims_from_text(
                            cleaned_desc,
                            source_type="OFFICER_DESCRIPTION",
                            source_id=src_id_str,
                        )
                    )
                    all_licenses.extend(
                        LicenseExtractor.extract_licenses(
                            cleaned_desc,
                            source_type="OFFICER_DESCRIPTION",
                            source_id=src_id_str,
                        )
                    )

        # --- C. Process Packaging OCR Evidence ---
        for ocr_rec in ocr_records:
            provenance_counts["OCR"] += 1
            ocr_id_str = str(ocr_rec.id)
            ocr_text = TextNormalizer.clean_text(ocr_rec.raw_text)
            ocr_conf = ocr_rec.confidence_score or 0.85

            all_ingredients.extend(
                IngredientParser.parse_ingredients_from_text(
                    ocr_text,
                    source_type="PACKAGING_OCR",
                    source_id=ocr_id_str,
                    base_confidence=ocr_conf,
                )
            )
            all_claims.extend(
                ClaimClassifier.extract_claims_from_text(
                    ocr_text,
                    source_type="PACKAGING_OCR",
                    source_id=ocr_id_str,
                    base_confidence=ocr_conf,
                )
            )
            all_licenses.extend(
                LicenseExtractor.extract_licenses(
                    ocr_text,
                    source_type="PACKAGING_OCR",
                    source_id=ocr_id_str,
                    base_confidence=ocr_conf,
                )
            )

        # --- D. Cross-Source Entity Deduplication & Fusion ---
        raw_ing_count = len(all_ingredients)
        raw_claim_count = len(all_claims)
        raw_lic_count = len(all_licenses)

        deduped_ingredients, merged_ing = EntityDeduplicator.deduplicate_ingredients(all_ingredients)
        deduped_claims, merged_claims = EntityDeduplicator.deduplicate_claims(all_claims)
        deduped_licenses, merged_lic = EntityDeduplicator.deduplicate_licenses(all_licenses)

        # Summary statistics
        allergens = list({ing.allergen_category for ing in deduped_ingredients if ing.is_allergen and ing.allergen_category})
        additives = list({ing.ins_number for ing in deduped_ingredients if ing.is_additive and ing.ins_number})
        prohibited_count = sum(1 for c in deduped_claims if c.is_potentially_prohibited)

        dedup_metrics = {
            "ingredients_raw": raw_ing_count,
            "ingredients_deduped": len(deduped_ingredients),
            "ingredients_merged": merged_ing,
            "claims_raw": raw_claim_count,
            "claims_deduped": len(deduped_claims),
            "claims_merged": merged_claims,
            "licenses_raw": raw_lic_count,
            "licenses_deduped": len(deduped_licenses),
            "licenses_merged": merged_lic,
            "total_duplicates_resolved": merged_ing + merged_claims + merged_lic,
        }

        canonical_product = CanonicalStructuredProduct(
            case_id=case_id,
            product_id=prod_obj.id,
            product_metadata=metadata,
            ingredients=deduped_ingredients,
            claims=deduped_claims,
            license_info=deduped_licenses,
            allergens_detected=sorted(allergens),
            additives_detected=sorted(additives),
            prohibited_claims_count=prohibited_count,
            duplicate_metrics=dedup_metrics,
            provenance_summary=provenance_counts,
            extraction_timestamp=now,
            schema_version=cls.SCHEMA_VERSION,
        )

        # --- E. Persist AI Intelligence Separately from Source Evidence ---
        # Stored in extracted_information under zone_type="CANONICAL_STRUCTURED_DATA"
        ai_record = ExtractedInformation(
            id=uuid.uuid4(),
            product_id=prod_obj.id,
            zone_type="CANONICAL_STRUCTURED_DATA",
            raw_text=f"Synthesized Intelligence Dossier for Case {case_obj.case_number}",
            parsed_data=canonical_product.model_dump(mode="json"),
            confidence_score=0.92,
            extractor_version=cls.SCHEMA_VERSION,
            created_at=now,
        )
        db.add(ai_record)

        audit = AuditLog(
            case_id=case_id,
            user_id=current_user_id,
            action="INTELLIGENCE_STRUCTURED",
            entity_type="CanonicalStructuredProduct",
            entity_id=str(ai_record.id),
            details_json={
                "ingredients_found": len(deduped_ingredients),
                "claims_found": len(deduped_claims),
                "prohibited_claims": prohibited_count,
                "allergens": allergens,
                "duplicates_resolved": dedup_metrics["total_duplicates_resolved"],
            },
            created_at=now,
        )
        db.add(audit)
        await db.commit()

        return canonical_product
