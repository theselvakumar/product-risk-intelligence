from typing import Tuple

from app.services.consistency.normalizer import ConsistencyNormalizer


class ConsistencyMatcher:
    """
    Three-tier deterministic similarity matching engine for cross-source evidence comparison.

    Tier 1 – EXACT: Verbatim string equality.
    Tier 2 – NORMALIZED: Post-normalization canonical equality.
    Tier 3 – SEMANTIC: Token Jaccard overlap + trigram character similarity.

    Thresholds:
      >= 0.85  →  CONSISTENT
      0.65-0.85 →  MINOR_WORDING_DIFFERENCE
      < 0.65   →  INCONSISTENT
    """

    CONSISTENT_THRESHOLD = 0.85
    MINOR_DIFF_THRESHOLD = 0.65

    @classmethod
    def _trigram_similarity(cls, a: str, b: str) -> float:
        """Compute character-level trigram overlap (Dice coefficient)."""
        def trigrams(s: str) -> set:
            s = s.lower()
            return {s[i:i+3] for i in range(max(0, len(s) - 2))}

        tg_a = trigrams(a)
        tg_b = trigrams(b)
        if not tg_a or not tg_b:
            return 1.0 if a == b else 0.0
        intersection = len(tg_a & tg_b)
        return (2 * intersection) / (len(tg_a) + len(tg_b))

    @classmethod
    def _token_jaccard(cls, a: str, b: str) -> float:
        """Compute token-level Jaccard similarity."""
        tokens_a = set(a.lower().split())
        tokens_b = set(b.lower().split())
        if not tokens_a or not tokens_b:
            return 0.0
        return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)

    @classmethod
    def compare(
        cls,
        raw_a: str,
        raw_b: str,
        field_name: str = "generic",
    ) -> Tuple[str, str, str, float, float]:
        """
        Compare two field values across three tiers.

        Returns:
            comparison_result: CONSISTENT | MINOR_WORDING_DIFFERENCE | INCONSISTENT | MISSING_IN_SOURCE
            match_method: EXACT | NORMALIZED | SEMANTIC
            detected_difference: Human-readable description
            similarity_score: 0.0–1.0
            confidence: 0.0–1.0
        """
        # Handle missing values
        a_empty = not raw_a or not raw_a.strip()
        b_empty = not raw_b or not raw_b.strip()

        if a_empty and b_empty:
            return "CONSISTENT", "EXACT", "Both sources have no value for this field.", 1.0, 0.70

        if a_empty or b_empty:
            present = raw_b if a_empty else raw_a
            missing_side = "Source A" if a_empty else "Source B"
            return (
                "MISSING_IN_SOURCE",
                "EXACT",
                f"{missing_side} does not contain any value for this field. Present value: \"{present[:80]}\".",
                0.0,
                0.95,
            )

        # Tier 1: Exact Match
        if raw_a.strip() == raw_b.strip():
            return "CONSISTENT", "EXACT", "Values are identical across both sources.", 1.0, 1.0

        # Normalize for Tier 2
        if field_name == "license_number":
            norm_a = ConsistencyNormalizer.normalize_license(raw_a)
            norm_b = ConsistencyNormalizer.normalize_license(raw_b)
        else:
            norm_a = ConsistencyNormalizer.normalize(raw_a)
            norm_b = ConsistencyNormalizer.normalize(raw_b)

        # Tier 2: Normalized Match
        if norm_a == norm_b:
            return (
                "CONSISTENT",
                "NORMALIZED",
                "Values are equivalent after normalization (abbreviation/formatting difference only).",
                1.0,
                0.95,
            )

        # Tier 3: Semantic Similarity
        jaccard = cls._token_jaccard(norm_a, norm_b)
        trigram = cls._trigram_similarity(norm_a, norm_b)
        # Weighted combined score: token overlap is more meaningful for longer texts
        a_words = len(norm_a.split())
        b_words = len(norm_b.split())
        avg_len = (a_words + b_words) / 2
        # Weight trigram more for short values (names), jaccard more for long texts (ingredients)
        if avg_len < 5:
            score = 0.4 * jaccard + 0.6 * trigram
        else:
            score = 0.6 * jaccard + 0.4 * trigram

        score = round(score, 3)

        if score >= cls.CONSISTENT_THRESHOLD:
            result = "CONSISTENT"
            description = f"Values are semantically equivalent (similarity score: {score:.2f})."
            severity = "INFO"
        elif score >= cls.MINOR_DIFF_THRESHOLD:
            result = "MINOR_WORDING_DIFFERENCE"
            description = (
                f"Minor wording difference detected (similarity score: {score:.2f}). "
                f"Source A: \"{raw_a[:80]}\" vs Source B: \"{raw_b[:80]}\"."
            )
            severity = "LOW"
        else:
            result = "INCONSISTENT"
            description = (
                f"Significant inconsistency detected (similarity score: {score:.2f}). "
                f"Source A states: \"{raw_a[:100]}\", while Source B states: \"{raw_b[:100]}\"."
            )
            severity = "HIGH"

        confidence = round(0.70 + (abs(score - 0.5) * 0.50), 2)
        return result, "SEMANTIC", description, score, min(confidence, 0.98)

    @classmethod
    def severity_for_result(cls, comparison_result: str, field_name: str) -> str:
        """Map comparison result and field importance to severity suggestion."""
        HIGH_IMPORTANCE_FIELDS = {"license_number", "ingredients", "manufacturer"}
        MEDIUM_IMPORTANCE_FIELDS = {"product_name", "claims"}

        if comparison_result == "INCONSISTENT":
            if field_name in HIGH_IMPORTANCE_FIELDS:
                return "HIGH"
            elif field_name in MEDIUM_IMPORTANCE_FIELDS:
                return "MEDIUM"
            return "LOW"
        elif comparison_result == "MISSING_IN_SOURCE":
            if field_name in HIGH_IMPORTANCE_FIELDS:
                return "MEDIUM"
            return "LOW"
        elif comparison_result == "MINOR_WORDING_DIFFERENCE":
            return "LOW"
        return "INFO"
