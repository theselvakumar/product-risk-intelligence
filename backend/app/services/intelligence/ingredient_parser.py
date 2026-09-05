import re
from typing import List, Optional, Tuple
from app.schemas.intelligence import StructuredIngredient


class IngredientParser:
    """
    Parses unstructured ingredient declarations, resolves sub-components,
    detects INS/E-number food additives, and identifies statutory allergens.
    """

    ALLERGEN_TAXONOMY = {
        "GLUTEN": ["wheat", "atta", "maida", "barley", "rye", "oat", "gluten", "semolina", "suji"],
        "MILK": ["milk", "dairy", "whey", "casein", "lactose", "butter", "cheese", "cream", "ghee", "curd"],
        "SOY": ["soy", "soya", "soybean", "tofu", "edamame"],
        "PEANUTS_NUTS": [
            "peanut", "groundnut", "almond", "cashew", "walnut", "pistachio",
            "hazelnut", "pecan", "macadamia", "nut",
        ],
        "EGGS": ["egg", "albumin", "yolk", "ovalbumin"],
        "FISH": ["fish", "tuna", "salmon", "cod", "anchovy"],
        "CRUSTACEANS": ["prawn", "crab", "lobster", "shrimp", "crustacean"],
        "SULPHITES": ["sulphite", "sulfite", "sulphur dioxide", "sulfur dioxide", "ins 220", "ins 221"],
    }

    INS_ADDITIVE_PATTERNS = [
        (r"\b(?:ins|e)\s*[-:]?\s*(\d{3,4}[a-z]?)\b", "INS {}"),
        (r"\b(?:preservative|acidity\s*regulator|emulsifier|stabilizer|color|antioxidant|flavour|flavor)\s*(?:\((?:ins\s*)?)?[-:]?\s*(\d{3,4})\)?\b", "INS {}"),
        (r"\((?:ins\s*)?(\d{3,4}[a-z]?)\)", "INS {}"),
    ]

    COMMON_INS_NAMES = {
        "INS 211": "Sodium Benzoate",
        "INS 330": "Citric Acid",
        "INS 322": "Lecithin",
        "INS 300": "Ascorbic Acid (Vitamin C)",
        "INS 202": "Potassium Sorbate",
        "INS 150D": "Caramel IV",
        "INS 412": "Guar Gum",
        "INS 415": "Xanthan Gum",
        "INS 955": "Sucralose",
        "INS 950": "Acesulfame Potassium",
    }

    @classmethod
    def find_ingredient_block(cls, text: str) -> Optional[str]:
        """Locate the ingredients section within unstructured text or OCR lines."""
        if not text:
            return None

        patterns = [
            r"(?:ingredients|ingredlents|contents|composition)\s*[:\-]\s*(.+?)(?=(?:nutr(?:ition|itional)|mfg|exp|net wt|fssai|marketed by|mfd by|\Z))",
            r"(?:ingredients|ingredlents)\s*(.+?)(?=(?:nutr(?:ition|itional)|mfg|exp|net wt|fssai|\Z))",
        ]

        for p in patterns:
            match = re.search(p, text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                block = match.group(1).strip()
                if len(block) > 5:
                    return block

        return None

    @classmethod
    def split_ingredients_parentheses_aware(cls, text: str) -> List[str]:
        """
        Split ingredients on commas or semicolons while keeping nested parentheses intact.
        e.g. 'Whole Milk, Emulsifier (INS 322, INS 471), Sugar'
        """
        items: List[str] = []
        current: List[str] = []
        depth = 0

        for char in text:
            if char in "([{":
                depth += 1
                current.append(char)
            elif char in ")]}":
                depth = max(0, depth - 1)
                current.append(char)
            elif char in ",;\n" and depth == 0:
                item = "".join(current).strip(" .•-–\t\r\n")
                if item:
                    items.append(item)
                current = []
            else:
                current.append(char)

        last_item = "".join(current).strip(" .•-–\t\r\n")
        if last_item:
            items.append(last_item)

        return items

    @classmethod
    def parse_single_ingredient(
        cls,
        raw_token: str,
        source_type: str,
        source_id: Optional[str] = None,
        base_confidence: float = 0.90,
    ) -> Optional[StructuredIngredient]:
        """Analyze a single raw ingredient string into a strongly-typed StructuredIngredient."""
        cleaned = raw_token.strip(" .•-–\t\r\n")
        if not cleaned or len(cleaned) < 2:
            return None

        # 1. Extract sub-components if parentheses exist
        sub_components = []
        paren_match = re.search(r"\((.+?)\)", cleaned)
        if paren_match:
            sub_content = paren_match.group(1)
            sub_components = [s.strip() for s in sub_content.split(",") if s.strip()]

        # 2. Detect INS / E-number additive codes
        ins_code = None
        for pattern, template in cls.INS_ADDITIVE_PATTERNS:
            m = re.search(pattern, cleaned, flags=re.IGNORECASE)
            if m:
                ins_code = template.format(m.group(1).upper())
                break

        is_additive = bool(ins_code) or any(
            w in cleaned.lower()
            for w in ["preservative", "acidity regulator", "emulsifier", "stabilizer", "color", "flavor", "sweetener"]
        )

        # 3. Detect statutory allergens
        is_allergen = False
        allergen_cat = None
        lower_token = cleaned.lower()

        for cat, keywords in cls.ALLERGEN_TAXONOMY.items():
            if any(re.search(r"\b" + re.escape(kw) + r"\b", lower_token) for kw in keywords):
                is_allergen = True
                allergen_cat = cat
                break

        # 4. Standardize ingredient name
        # If parentheses present, primary name is text before parentheses
        primary_name = cleaned
        if paren_match:
            primary_name = cleaned[: paren_match.start()].strip()
            if not primary_name and ins_code:
                primary_name = cls.COMMON_INS_NAMES.get(ins_code, ins_code)

        if not primary_name:
            primary_name = cleaned

        return StructuredIngredient(
            ingredient_name=primary_name,
            original_text=cleaned,
            source_type=source_type,
            source_id=source_id,
            confidence=base_confidence,
            ins_number=ins_code,
            is_additive=is_additive,
            is_allergen=is_allergen,
            allergen_category=allergen_cat,
            sub_components=sub_components,
            extraction_method="RULE_BASED",
        )

    @classmethod
    def parse_ingredients_from_text(
        cls,
        text: str,
        source_type: str,
        source_id: Optional[str] = None,
        base_confidence: float = 0.88,
    ) -> List[StructuredIngredient]:
        """Extract all structured ingredients from an unstructured text or OCR block."""
        block = cls.find_ingredient_block(text) or text
        raw_items = cls.split_ingredients_parentheses_aware(block)

        results: List[StructuredIngredient] = []
        for raw_item in raw_items:
            # Filter out non-ingredient artifacts (e.g. "Contains added flavor", "Allergen advice")
            if any(raw_item.lower().startswith(x) for x in ["contains added", "allergen advice", "allergy info", "store in a cool"]):
                continue

            parsed = cls.parse_single_ingredient(
                raw_token=raw_item,
                source_type=source_type,
                source_id=source_id,
                base_confidence=base_confidence,
            )
            if parsed:
                results.append(parsed)

        return results
