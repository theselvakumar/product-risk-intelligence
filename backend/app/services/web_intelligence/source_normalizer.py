import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.intelligence.claim_classifier import ClaimClassifier
from app.services.intelligence.ingredient_parser import IngredientParser
from app.services.intelligence.license_extractor import LicenseExtractor
from app.services.web_intelligence.scraping_service import ScrapedPageData


@dataclass
class WebExtractedData:
    """
    Normalized data contract for web-derived product intelligence.
    Preserves original source attribution and provides structured fields.
    """
    source_url: str
    source_type: str  # PRODUCT_URL, WEB_SEARCH, WEB_SCRAPED
    title: str
    raw_content: str
    product_name: Optional[str] = None
    brand: Optional[str] = None
    manufacturer: Optional[str] = None
    fssai_license_number: Optional[str] = None
    ingredients: List[str] = field(default_factory=list)
    claims: List[str] = field(default_factory=list)
    relevance_score: float = 1.0
    relevance_reason: str = "Direct authority URL"
    confidence: float = 0.85
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SourceNormalizer:
    """
    Normalizes multi-source scraped web pages into structured product evidence
    while calculating strict relevance thresholds to filter out noisy pages.
    """
    MFR_REGEX = re.compile(
        r"(?:mfd\.?\s*by|manufactured\s*by|marketed\s*by|packed\s*by)[:\s]*([A-Za-z0-9\s,\.&]{3,80})",
        re.IGNORECASE,
    )
    LICENSE_REGEX = re.compile(r"\b([12]\d{13})\b")

    @classmethod
    def compute_relevance(
        cls,
        page_title: str,
        page_text: str,
        target_product_name: str,
        target_brand: Optional[str] = None,
        target_manufacturer: Optional[str] = None,
    ) -> Tuple[float, str]:
        """
        Computes a relevance score between 0.0 and 1.0 based on keyword containment
        and token overlap against product identity.
        """
        score = 0.0
        reasons: List[str] = []

        combined_text = f"{page_title} {page_text}".lower()
        title_lower = page_title.lower()

        # 1. Brand match
        if target_brand and target_brand.strip():
            b_lower = target_brand.strip().lower()
            if b_lower in title_lower:
                score += 0.45
                reasons.append(f"Brand '{target_brand}' in title")
            elif b_lower in combined_text:
                score += 0.25
                reasons.append(f"Brand '{target_brand}' in body")

        # 2. Product Name tokens
        if target_product_name and target_product_name.strip():
            p_tokens = [t.lower() for t in re.findall(r"\w+", target_product_name) if len(t) > 2]
            if p_tokens:
                matched_tokens = [t for t in p_tokens if t in combined_text]
                overlap_ratio = len(matched_tokens) / len(p_tokens)
                score += overlap_ratio * 0.45
                if overlap_ratio >= 0.5:
                    reasons.append(f"Product tokens match ({len(matched_tokens)}/{len(p_tokens)})")

        # 3. Manufacturer match
        if target_manufacturer and target_manufacturer.strip():
            m_lower = target_manufacturer.strip().lower()
            if m_lower in combined_text:
                score += 0.10
                reasons.append("Manufacturer match")

        # Bound score between 0.0 and 1.0
        final_score = min(1.0, max(0.0, score))
        reason_str = "; ".join(reasons) if reasons else "No strong keyword correlation"
        return final_score, reason_str

    @classmethod
    def normalize_scraped_page(
        cls,
        scraped: ScrapedPageData,
        source_type: str = "WEB_SCRAPED",
        target_product_name: str = "",
        target_brand: Optional[str] = None,
        target_manufacturer: Optional[str] = None,
        min_relevance_threshold: float = 0.20,
    ) -> Optional[WebExtractedData]:
        """
        Normalizes a scraped web page, extracts structured entities, and filters by relevance.
        """
        if not scraped.is_success:
            return None

        full_text = f"{scraped.title}\n{scraped.meta_description}\n{scraped.readable_text}"

        # Direct provided URLs bypass relevance filtering
        if source_type == "PRODUCT_URL":
            relevance_score = 1.0
            relevance_reason = "Official product URL provided by authority"
        else:
            relevance_score, relevance_reason = cls.compute_relevance(
                scraped.title,
                full_text,
                target_product_name,
                target_brand,
                target_manufacturer,
            )
            if relevance_score < min_relevance_threshold:
                return None

        # Extract structured entities from JSON-LD first if available
        parsed_name: Optional[str] = None
        parsed_brand: Optional[str] = None
        parsed_mfr: Optional[str] = None
        parsed_ingredients: List[str] = []

        for p_json in scraped.json_ld_products:
            if not parsed_name and p_json.get("name"):
                parsed_name = str(p_json.get("name")).strip()
            if not parsed_brand:
                brand_field = p_json.get("brand")
                if isinstance(brand_field, dict):
                    parsed_brand = brand_field.get("name")
                elif isinstance(brand_field, str):
                    parsed_brand = brand_field
            if not parsed_mfr:
                mfr_field = p_json.get("manufacturer")
                if isinstance(mfr_field, dict):
                    parsed_mfr = mfr_field.get("name")
                elif isinstance(mfr_field, str):
                    parsed_mfr = mfr_field
            if p_json.get("description") and not full_text:
                full_text += f"\n{p_json.get('description')}"

        # Fallback entity extraction via regex and NLP parsers
        if not parsed_mfr:
            mfr_m = cls.MFR_REGEX.search(full_text)
            if mfr_m:
                parsed_mfr = mfr_m.group(1).strip()

        # FSSAI License extraction
        fssai_lic: Optional[str] = None
        lic_matches = LicenseExtractor.extract_licenses(full_text, source_type=source_type)
        if lic_matches:
            fssai_lic = lic_matches[0].license_number
        else:
            raw_lic_m = cls.LICENSE_REGEX.search(full_text)
            if raw_lic_m:
                fssai_lic = raw_lic_m.group(1)

        # Ingredient extraction via existing IngredientParser
        parsed_ings = IngredientParser.parse_ingredients_from_text(
            full_text,
            source_type=source_type,
            source_id=scraped.url,
        )
        ing_names = [ing.ingredient_name for ing in parsed_ings if ing.ingredient_name]

        # Claims extraction via existing ClaimClassifier
        parsed_claims = ClaimClassifier.extract_claims_from_text(
            full_text,
            source_type=source_type,
            source_id=scraped.url,
        )
        claim_texts = [c.claim_text for c in parsed_claims if c.claim_text]

        # Calculate extraction confidence
        confidence = 0.75
        if parsed_name:
            confidence += 0.05
        if ing_names:
            confidence += 0.10
        if fssai_lic:
            confidence += 0.05
        confidence = min(0.95, confidence)

        return WebExtractedData(
            source_url=scraped.url,
            source_type=source_type,
            title=scraped.title or target_product_name,
            raw_content=full_text[:10000],  # Keep reasonable snippet
            product_name=parsed_name or target_product_name,
            brand=parsed_brand or target_brand,
            manufacturer=parsed_mfr or target_manufacturer,
            fssai_license_number=fssai_lic,
            ingredients=ing_names,
            claims=claim_texts,
            relevance_score=relevance_score,
            relevance_reason=relevance_reason,
            confidence=confidence,
            extracted_at=scraped.scraped_at,
        )
