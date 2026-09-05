import re
from typing import Any, Dict, List, Tuple
from app.schemas.intelligence import StructuredClaim, StructuredIngredient, StructuredLicense


class EntityDeduplicator:
    """
    Cross-source entity alignment and deduplication.
    Clusters and merges synonymous or repeated ingredients, claims, and licenses
    across URL, OCR, and description sources while preserving all provenance.
    """

    @classmethod
    def _normalize_for_comparison(cls, text: str) -> str:
        """Strip non-alphanumerics and lower case for fuzzy matching."""
        cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", text.lower())
        return " ".join(cleaned.split())

    @classmethod
    def _token_jaccard_similarity(cls, str1: str, str2: str) -> float:
        """Compute Jaccard token overlap between two strings."""
        tokens1 = set(cls._normalize_for_comparison(str1).split())
        tokens2 = set(cls._normalize_for_comparison(str2).split())
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        return len(intersection) / len(union)

    @classmethod
    def deduplicate_ingredients(cls, ingredients: List[StructuredIngredient]) -> Tuple[List[StructuredIngredient], int]:
        """
        Deduplicate ingredient list across multiple evidence sources.
        Preserves sub-components and INS codes from richer sources.
        """
        if not ingredients:
            return [], 0

        unique_ingredients: List[StructuredIngredient] = []
        merged_count = 0

        for ing in ingredients:
            norm_name = cls._normalize_for_comparison(ing.ingredient_name)
            matched_idx = -1

            for idx, existing in enumerate(unique_ingredients):
                existing_norm = cls._normalize_for_comparison(existing.ingredient_name)
                # Check direct match or INS code match
                if norm_name == existing_norm:
                    matched_idx = idx
                    break
                if ing.ins_number and existing.ins_number and ing.ins_number == existing.ins_number:
                    matched_idx = idx
                    break
                # Substring match if one is contained in another
                if len(norm_name) > 3 and (norm_name in existing_norm or existing_norm in norm_name):
                    matched_idx = idx
                    break

            if matched_idx >= 0:
                # Merge into existing item
                existing = unique_ingredients[matched_idx]
                merged_count += 1
                
                # Combine source information
                if ing.source_type not in existing.source_type:
                    existing.source_type = f"{existing.source_type}, {ing.source_type}"
                
                # Take richer INS code / allergen data if available
                if not existing.ins_number and ing.ins_number:
                    existing.ins_number = ing.ins_number
                    existing.is_additive = True
                if not existing.is_allergen and ing.is_allergen:
                    existing.is_allergen = True
                    existing.allergen_category = ing.allergen_category
                
                # Merge sub-components
                for sub in ing.sub_components:
                    if sub not in existing.sub_components:
                        existing.sub_components.append(sub)

                # Keep higher confidence
                existing.confidence = round(max(existing.confidence, ing.confidence), 2)
            else:
                unique_ingredients.append(ing.model_copy())

        return unique_ingredients, merged_count

    @classmethod
    def deduplicate_claims(cls, claims: List[StructuredClaim]) -> Tuple[List[StructuredClaim], int]:
        """
        Deduplicate claims across sources while preserving statutory prohibition flags.
        """
        if not claims:
            return [], 0

        unique_claims: List[StructuredClaim] = []
        merged_count = 0

        for claim in claims:
            matched_idx = -1
            for idx, existing in enumerate(unique_claims):
                sim = cls._token_jaccard_similarity(claim.claim_text, existing.claim_text)
                if sim >= 0.70:
                    matched_idx = idx
                    break

            if matched_idx >= 0:
                existing = unique_claims[matched_idx]
                merged_count += 1

                # Combine sources
                if claim.source_type not in existing.source_type:
                    existing.source_type = f"{existing.source_type}, {claim.source_type}"

                # Prioritize prohibited flag
                if claim.is_potentially_prohibited:
                    existing.is_potentially_prohibited = True
                    existing.statutory_warning_flag = claim.statutory_warning_flag or existing.statutory_warning_flag
                    existing.claim_category = "DISEASE_RISK_REDUCTION_OR_CURE"

                existing.confidence = round(max(existing.confidence, claim.confidence), 2)
            else:
                unique_claims.append(claim.model_copy())

        return unique_claims, merged_count

    @classmethod
    def deduplicate_licenses(cls, licenses: List[StructuredLicense]) -> Tuple[List[StructuredLicense], int]:
        """Deduplicate licenses by 14-digit number."""
        if not licenses:
            return [], 0

        unique_lics: Dict[str, StructuredLicense] = {}
        merged_count = 0

        for lic in licenses:
            num = lic.license_number
            if num in unique_lics:
                merged_count += 1
                existing = unique_lics[num]
                if lic.source_type not in existing.source_type:
                    existing.source_type = f"{existing.source_type}, {lic.source_type}"
                existing.confidence = round(max(existing.confidence, lic.confidence), 2)
            else:
                unique_lics[num] = lic.model_copy()

        return list(unique_lics.values()), merged_count
