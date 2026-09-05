import re
from typing import List, Optional
from app.schemas.intelligence import StructuredClaim


class ClaimClassifier:
    """
    Identifies, segments, and classifies marketing and nutritional claims,
    flagging statutory violations under FSS (Advertising and Claims) Regulations 2018
    and Section 24 of the Food Safety & Standards Act, 2006.
    """

    # Disease cure / risk reduction patterns (Strictly prohibited on foods under Regulation 4(7))
    PROHIBITED_DISEASE_PATTERNS = [
        (r"\b(?:cure|cures|curing|curative)\b.*?\b(?:diabetes|cancer|hypertension|covid|infection|arthritis|fever|disease|asthma|bp)\b", "Curative claim for specific disease"),
        (r"\b(?:reverses?|eliminates?|prevents?)\b.*?\b(?:diabetes|cancer|chronic|tumor|stroke|cardiac|heart disease)\b", "Disease prevention or reversal claim"),
        (r"\b(?:100%|guaranteed)\s*(?:cure|recovery|solution)\b", "Absolute curative guarantee"),
        (r"\b(?:anti[- ]cancer|anti[- ]diabetic|anti[- ]tumor)\b", "Medicinal drug claim on food product"),
        (r"\b(?:regulates?|lowers?)\s*(?:blood sugar|glucose|blood pressure|cholesterol)\s*(?:in \d+ days|permanently|instantly)\b", "Therapeutic metabolic claim"),
    ]

    # Statutory functional / health claim patterns
    HEALTH_FUNCTIONAL_PATTERNS = [
        r"\b(?:boosts?|enhances?|strengthens?)\s*(?:immunity|immune system|stamina|vitality|energy)\b",
        r"\b(?:promotes?|aids?|supports?)\s*(?:weight loss|digestion|gut health|memory|brain health|heart health)\b",
        r"\b(?:detox|detoxification|rejuvenator|anti[- ]aging)\b",
    ]

    # Nutrition content claim patterns (Schedule I & II)
    NUTRITION_CONTENT_PATTERNS = [
        r"\b(?:zero|no|0g?)\s*(?:added\s*)?(?:sugar|sugars|trans[- ]fat|cholesterol|calorie|calories)\b",
        r"\b(?:high|rich in)\s*(?:protein|fiber|calcium|iron|vitamin [a-z0-9]+)\b",
        r"\b(?:low|reduced)\s*(?:fat|calorie|sodium|sugar|carb|carbs)\b",
        r"\b(?:gluten[- ]free|trans[- ]fat free|fat[- ]free)\b",
    ]

    # Superlative / absolute claims (Regulation 4(4) restriction)
    SUPERLATIVE_PATTERNS = [
        r"\b100%\s*(?:pure|natural|organic|authentic|genuine|safe)\b",
        r"\b(?:best|finest|purest|world['’]s best|india['’]s best)\b",
        r"\b(?:miracle|guaranteed results?|authentic original)\b",
    ]

    # Natural / Organic claims
    NATURAL_ORGANIC_PATTERNS = [
        r"\b(?:all[- ]natural|100% natural|certified organic|organically grown)\b",
        r"\b(?:chemical[- ]free|pesticide[- ]free|preservative[- ]free)\b",
        r"\b(?:pure herbal|ayurvedic proprietary|raw and unpasteurized)\b",
    ]

    @classmethod
    def extract_claims_from_text(
        cls,
        text: str,
        source_type: str,
        source_id: Optional[str] = None,
        base_confidence: float = 0.90,
    ) -> List[StructuredClaim]:
        """Scan text and extract all classified product claims with statutory flags."""
        if not text:
            return []

        claims: List[StructuredClaim] = []
        seen_snippets = set()

        # Break text into sentences or meaningful clauses
        clauses = re.split(r"[\n\r•\t;\.\!]+", text)

        for raw_clause in clauses:
            clause = raw_clause.strip(" ,-–\"'#*")
            if len(clause) < 4 or clause.lower() in seen_snippets:
                continue

            lower_clause = clause.lower()

            # 1. Check Prohibited Disease Cure Claims (Highest Priority)
            is_prohibited = False
            warning_flag = None
            category = None

            for pattern, reason in cls.PROHIBITED_DISEASE_PATTERNS:
                if re.search(pattern, lower_clause):
                    is_prohibited = True
                    warning_flag = reason
                    category = "DISEASE_RISK_REDUCTION_OR_CURE"
                    break

            # 2. Check Superlative Claims
            if not category:
                for pattern in cls.SUPERLATIVE_PATTERNS:
                    if re.search(pattern, lower_clause):
                        category = "SUPERLATIVE_OR_ABSOLUTE"
                        break

            # 3. Check Nutrition Content Claims
            if not category:
                for pattern in cls.NUTRITION_CONTENT_PATTERNS:
                    if re.search(pattern, lower_clause):
                        category = "NUTRITION_CONTENT"
                        break

            # 4. Check Health & Functional Claims
            if not category:
                for pattern in cls.HEALTH_FUNCTIONAL_PATTERNS:
                    if re.search(pattern, lower_clause):
                        category = "HEALTH_OR_FUNCTIONAL"
                        break

            # 5. Check Natural / Organic Claims
            if not category:
                for pattern in cls.NATURAL_ORGANIC_PATTERNS:
                    if re.search(pattern, lower_clause):
                        category = "NATURAL_ORGANIC"
                        break

            if category:
                seen_snippets.add(lower_clause)
                claims.append(
                    StructuredClaim(
                        claim_text=clause,
                        original_text=clause,
                        claim_category=category,
                        source_type=source_type,
                        source_id=source_id,
                        confidence=base_confidence,
                        is_potentially_prohibited=is_prohibited,
                        statutory_warning_flag=warning_flag,
                        extraction_method="RULE_BASED",
                    )
                )

        return claims
