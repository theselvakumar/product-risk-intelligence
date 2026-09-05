import re
import unicodedata
from typing import Optional


class TextNormalizer:
    """
    Sanitizes raw text, resolves OCR typographical glitches,
    and maps product categories to FSSAI standardized Food Category Systems.
    """

    OCR_GLITCH_MAP = {
        r"\b[lI]00%": "100%",
        r"\bIngred[il1]ents?\b": "Ingredients",
        r"\bNutr[il1]t[il1]on\b": "Nutrition",
        r"\bFSSA[l1I]\b": "FSSAI",
        r"\bL[il1]c\.?\s*No\.?": "Lic No:",
        r"\bNet\s*Wt\.?": "Net Weight:",
        r"\bMfg\.?\s*Date": "Mfg Date:",
        r"\bExp\.?\s*Date": "Exp Date:",
    }

    CATEGORY_MAPPING = {
        "HEALTH_SUPPLEMENTS": "HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS",
        "SUPPLEMENT": "HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS",
        "NUTRACEUTICAL": "HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS",
        "AYURVEDIC": "AYURVEDIC_PROPRIETARY",
        "HERBAL": "AYURVEDIC_PROPRIETARY",
        "INFANT": "INFANT_FOODS_AND_FORMULA",
        "BABY": "INFANT_FOODS_AND_FORMULA",
        "OIL": "EDIBLE_OILS_AND_FATS",
        "GHEE": "EDIBLE_OILS_AND_FATS",
        "FAT": "EDIBLE_OILS_AND_FATS",
        "CEREAL": "CEREAL_AND_CONFECTIONERY",
        "SNACK": "CEREAL_AND_CONFECTIONERY",
        "BISCUIT": "CEREAL_AND_CONFECTIONERY",
        "CHOCOLATE": "CEREAL_AND_CONFECTIONERY",
        "BEVERAGE": "BEVERAGES_TEA_AND_COFFEE",
        "TEA": "BEVERAGES_TEA_AND_COFFEE",
        "COFFEE": "BEVERAGES_TEA_AND_COFFEE",
        "JUICE": "BEVERAGES_TEA_AND_COFFEE",
        "DAIRY": "DAIRY_AND_ANALOGUES",
        "MILK": "DAIRY_AND_ANALOGUES",
        "CHEESE": "DAIRY_AND_ANALOGUES",
        "HONEY": "HONEY_AND_PRESERVES",
    }

    @classmethod
    def clean_text(cls, text: Optional[str]) -> str:
        """Strip control characters, normalize Unicode, and repair OCR glitches."""
        if not text:
            return ""

        # Normalize unicode (NFKC)
        normalized = unicodedata.normalize("NFKC", text)

        # Replace excessive whitespace and newlines
        cleaned = re.sub(r"[\r\t\f\v]+", " ", normalized)
        cleaned = re.sub(r" +", " ", cleaned)

        # Repair common OCR token glitches
        for pattern, replacement in cls.OCR_GLITCH_MAP.items():
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

        return cleaned.strip()

    @classmethod
    def normalize_category(cls, raw_category: Optional[str]) -> str:
        """Map raw category to standardized FSSAI food category."""
        if not raw_category:
            return "GENERAL_FOOD_PRODUCTS"

        upper = raw_category.upper().strip()

        # Check direct mapping
        for keyword, mapped_val in cls.CATEGORY_MAPPING.items():
            if keyword in upper:
                return mapped_val

        return upper.replace(" ", "_").replace("-", "_")

    @classmethod
    def extract_net_quantity(cls, text: str) -> Optional[str]:
        """Extract net weight or volume declaration (e.g. 500g, 1 kg, 250 ml, 1 L)."""
        pattern = r"\b(\d+(?:\.\d+)?\s*(?:kg|g|gm|gms|ml|l|ltr|litres|capsules|tablets|tabs))\b"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
