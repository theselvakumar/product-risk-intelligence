import re
import unicodedata


class ConsistencyNormalizer:
    """
    Text normalization pipeline for cross-source field comparison.
    Expands common abbreviations, strips noise characters, and produces
    a canonical comparison form that is independent of formatting quirks.
    """

    ABBREVIATION_MAP = {
        r"\bpvt\.?\s*ltd\.?\b": "private limited",
        r"\bltd\.?\b": "limited",
        r"\bco\.?\b": "company",
        r"\bcorp\.?\b": "corporation",
        r"\binc\.?\b": "incorporated",
        r"\bllp\.?\b": "limited liability partnership",
        r"\bmfg\.?\b": "manufacturing",
        r"\bmfd\.?\s*by\b": "manufactured by",
        r"\bpkd\.?\s*by\b": "packed by",
        r"\bmktd\.?\s*by\b": "marketed by",
        r"\bmfr\.?\b": "manufacturer",
        r"\bno\.?\b": "number",
        r"\blicen[sc]e?\s*no\.?\b": "license number",
        r"\bfssai\s*lic\.?\b": "fssai license",
        r"\b&\b": "and",
        r"\b(\d+)\s*gms?\b": r"\1 gram",
        r"\b(\d+)\s*kgs?\b": r"\1 kilogram",
        r"\b(\d+)\s*mls?\b": r"\1 milliliter",
        r"\bfree\s*sugar\b": "sugar free",
        r"\bzero\s*sugar\b": "sugar free",
        r"\bno\s*added\s*sugar\b": "no added sugar",
    }

    @classmethod
    def normalize(cls, text: str) -> str:
        """Produce normalized canonical text for deterministic comparison."""
        if not text:
            return ""

        # 1. Unicode NFKC normalization
        result = unicodedata.normalize("NFKC", text)

        # 2. Lowercase
        result = result.lower()

        # 3. Expand abbreviations
        for pattern, expansion in cls.ABBREVIATION_MAP.items():
            result = re.sub(pattern, expansion, result, flags=re.IGNORECASE)

        # 4. Strip punctuation (keep alphanumeric and spaces)
        result = re.sub(r"[^\w\s]", " ", result)

        # 5. Collapse whitespace
        result = " ".join(result.split())

        return result.strip()

    @classmethod
    def normalize_ingredient_list(cls, text: str) -> set:
        """Normalize ingredient list text into a canonical token set for set-comparison."""
        if not text:
            return set()

        cleaned = cls.normalize(text)
        # Split on common delimiters after normalization
        tokens = re.split(r"[,;•\n]+", cleaned)
        return {t.strip() for t in tokens if len(t.strip()) > 2}

    @classmethod
    def normalize_license(cls, text: str) -> str:
        """Extract only the 14-digit FSSAI number from surrounding text."""
        if not text:
            return ""
        m = re.search(r"[12]\d{13}", text)
        return m.group(0) if m else cls.normalize(text)
