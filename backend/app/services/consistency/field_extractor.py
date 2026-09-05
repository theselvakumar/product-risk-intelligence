import re
from typing import Any, Dict, List, Optional

from app.schemas.consistency import SourceFieldEvidence
from app.services.consistency.normalizer import ConsistencyNormalizer


class FieldExtractor:
    """
    Extracts per-field canonical values from each evidence source.
    Each extraction preserves the original verbatim text alongside its normalized form.
    """

    FIELDS = ["product_name", "manufacturer", "ingredients", "claims", "license_number"]

    MFR_REGEX = re.compile(
        r"(?:mfd\.?\s*by|manufactured\s*by|marketed\s*by|packed\s*by)[:\s]*([A-Za-z0-9\s,\.&]{3,60})",
        re.IGNORECASE,
    )
    INGREDIENT_BLOCK_REGEX = re.compile(
        r"(?:ingredients?|contents?|composition)[:\s]*(.+?)(?=(?:nutrition|mfg|exp|net wt|fssai|marketed|best before|\Z))",
        re.IGNORECASE | re.DOTALL,
    )
    CLAIM_KEYWORDS = [
        r"\b100%\s*\w+\b",
        r"\b(?:zero|no|free)\s+\w+\b",
        r"\b(?:boosts?|enhances?|supports?)\s+\w+\b",
        r"\b(?:clinically|scientifically)\s+(?:proven|tested)\b",
        r"\b(?:guaranteed|doctor\s+recommended)\b",
        r"\b(?:sugar\s*free|gluten\s*free|fat\s*free|trans\s*fat\s*free)\b",
        r"\b(?:high|rich)\s+in\s+\w+\b",
        r"\b(?:low|reduced)\s+\w+\b",
        r"\b(?:contains\s+added\s+\w+)\b",
    ]
    LICENSE_REGEX = re.compile(r"[12]\d{13}", re.IGNORECASE)

    @classmethod
    def _extract_claims_from_text(cls, text: str) -> str:
        """Find claim-like statements in raw text and return them concatenated."""
        found = []
        for p in cls.CLAIM_KEYWORDS:
            for m in re.finditer(p, text, re.IGNORECASE):
                snippet = m.group(0).strip()
                if snippet not in found:
                    found.append(snippet)
        return "; ".join(found) if found else ""

    @classmethod
    def extract_from_product_object(cls, product: Any) -> Dict[str, SourceFieldEvidence]:
        """Extract fields from the canonical Product ORM object (manual input)."""
        source_type = "MANUAL_INPUT"
        source_id = str(product.id)
        fields: Dict[str, SourceFieldEvidence] = {}

        if product.product_name:
            fields["product_name"] = SourceFieldEvidence(
                source_type=source_type,
                source_id=source_id,
                raw_text=product.product_name,
                normalized_value=ConsistencyNormalizer.normalize(product.product_name),
            )
        if product.manufacturer:
            fields["manufacturer"] = SourceFieldEvidence(
                source_type=source_type,
                source_id=source_id,
                raw_text=product.manufacturer,
                normalized_value=ConsistencyNormalizer.normalize(product.manufacturer),
            )
        if product.fssai_license_number:
            fields["license_number"] = SourceFieldEvidence(
                source_type=source_type,
                source_id=source_id,
                raw_text=product.fssai_license_number,
                normalized_value=ConsistencyNormalizer.normalize_license(product.fssai_license_number),
            )
        return fields

    @classmethod
    def extract_from_ocr_text(cls, ocr_text: str, source_id: str) -> Dict[str, SourceFieldEvidence]:
        """Extract fields from OCR-extracted packaging text."""
        source_type = "PACKAGING_OCR"
        fields: Dict[str, SourceFieldEvidence] = {}

        # Manufacturer
        mfr_m = cls.MFR_REGEX.search(ocr_text)
        if mfr_m:
            raw = mfr_m.group(1).strip()
            fields["manufacturer"] = SourceFieldEvidence(
                source_type=source_type,
                source_id=source_id,
                raw_text=raw,
                normalized_value=ConsistencyNormalizer.normalize(raw),
            )

        # Ingredients block
        ing_m = cls.INGREDIENT_BLOCK_REGEX.search(ocr_text)
        if ing_m:
            raw_ing = ing_m.group(1).strip()[:500]
            fields["ingredients"] = SourceFieldEvidence(
                source_type=source_type,
                source_id=source_id,
                raw_text=raw_ing,
                normalized_value=ConsistencyNormalizer.normalize(raw_ing),
            )

        # License number
        lic_m = cls.LICENSE_REGEX.search(ocr_text)
        if lic_m:
            raw_lic = lic_m.group(0)
            fields["license_number"] = SourceFieldEvidence(
                source_type=source_type,
                source_id=source_id,
                raw_text=raw_lic,
                normalized_value=raw_lic,  # 14-digit number needs no further normalization
            )

        # Claims
        claims_raw = cls._extract_claims_from_text(ocr_text)
        if claims_raw:
            fields["claims"] = SourceFieldEvidence(
                source_type=source_type,
                source_id=source_id,
                raw_text=claims_raw,
                normalized_value=ConsistencyNormalizer.normalize(claims_raw),
            )

        return fields

    @classmethod
    def extract_from_source_record(cls, source: Any) -> Dict[str, SourceFieldEvidence]:
        """Extract fields from ProductSource record (URL descriptions, officer descriptions)."""
        source_type = getattr(source, "source_type", "PRODUCT_URL")
        source_id = str(getattr(source, "id", ""))

        # Get raw text content
        text = getattr(source, "raw_content", "") or ""
        payload = getattr(source, "raw_payload_json", {}) or {}
        if isinstance(payload, dict):
            text = text or payload.get("description", "") or payload.get("raw_content", "")

        if not text:
            return {}

        fields: Dict[str, SourceFieldEvidence] = {}

        # Product Name
        prod_name = payload.get("product_name") or payload.get("title")
        if prod_name:
            fields["product_name"] = SourceFieldEvidence(
                source_type=source_type,
                source_id=source_id,
                raw_text=prod_name,
                normalized_value=ConsistencyNormalizer.normalize(prod_name),
            )

        # Manufacturer
        mfr_val = payload.get("manufacturer")
        mfr_m = cls.MFR_REGEX.search(text)
        raw_mfr = mfr_m.group(1).strip() if mfr_m else (mfr_val.strip() if mfr_val else "")
        if raw_mfr:
            fields["manufacturer"] = SourceFieldEvidence(
                source_type=source_type,
                source_id=source_id,
                raw_text=raw_mfr,
                normalized_value=ConsistencyNormalizer.normalize(raw_mfr),
            )

        # Ingredients
        ing_m = cls.INGREDIENT_BLOCK_REGEX.search(text)
        raw_ing = ""
        if ing_m:
            raw_ing = ing_m.group(1).strip()[:500]
        elif isinstance(payload.get("ingredients"), list) and payload["ingredients"]:
            raw_ing = ", ".join(str(i) for i in payload["ingredients"])[:500]
        elif isinstance(payload.get("ingredients"), str) and payload["ingredients"]:
            raw_ing = payload["ingredients"][:500]

        if raw_ing:
            fields["ingredients"] = SourceFieldEvidence(
                source_type=source_type,
                source_id=source_id,
                raw_text=raw_ing,
                normalized_value=ConsistencyNormalizer.normalize(raw_ing),
            )

        # License
        lic_m = cls.LICENSE_REGEX.search(text)
        raw_lic = lic_m.group(0) if lic_m else (payload.get("fssai_license_number") or "")
        if raw_lic:
            fields["license_number"] = SourceFieldEvidence(
                source_type=source_type,
                source_id=source_id,
                raw_text=raw_lic,
                normalized_value=raw_lic,
            )

        # Claims
        claims_raw = cls._extract_claims_from_text(text)
        if not claims_raw and isinstance(payload.get("claims"), list) and payload["claims"]:
            claims_raw = "; ".join(str(c) for c in payload["claims"])
        elif not claims_raw and isinstance(payload.get("claims"), str) and payload["claims"]:
            claims_raw = payload["claims"]

        if claims_raw:
            fields["claims"] = SourceFieldEvidence(
                source_type=source_type,
                source_id=source_id,
                raw_text=claims_raw,
                normalized_value=ConsistencyNormalizer.normalize(claims_raw),
            )

        return fields
