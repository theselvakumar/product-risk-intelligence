import re
from typing import List, Optional
from app.schemas.intelligence import StructuredLicense


class LicenseExtractor:
    """
    Extracts, validates, and analyzes 14-digit FSSAI statutory licenses and registrations.
    """

    STATE_CODE_MAP = {
        "00": "Central License",
        "01": "Jammu & Kashmir",
        "02": "Himachal Pradesh",
        "03": "Punjab",
        "04": "Chandigarh",
        "05": "Uttarakhand",
        "06": "Haryana",
        "07": "Delhi",
        "08": "Rajasthan",
        "09": "Uttar Pradesh",
        "10": "Bihar",
        "19": "West Bengal",
        "24": "Gujarat",
        "27": "Maharashtra",
        "29": "Karnataka",
        "33": "Tamil Nadu",
        "36": "Telangana",
    }

    FSSAI_REGEX = re.compile(
        r"(?:fssai\s*(?:lic(?:ense)?\.?\s*(?:no\.?)?|registration\s*no\.?)?[:\s]*)?([12]\d{13})\b",
        re.IGNORECASE,
    )

    @classmethod
    def extract_licenses(
        cls,
        text: str,
        source_type: str,
        source_id: Optional[str] = None,
        base_confidence: float = 0.95,
    ) -> List[StructuredLicense]:
        """Extract all 14-digit FSSAI licenses from text with statutory validation."""
        if not text:
            return []

        licenses: List[StructuredLicense] = []
        seen_numbers = set()

        # Find all occurrences of 14-digit numbers starting with 1 or 2
        for match in cls.FSSAI_REGEX.finditer(text):
            num = match.group(1).strip()
            if num in seen_numbers:
                continue

            seen_numbers.add(num)
            full_snippet = match.group(0).strip()

            # Analyze statutory structure
            leading_digit = num[0]
            lic_type = "STATE_OR_CENTRAL_LICENSE" if leading_digit == "1" else "REGISTRATION"
            state_digits = num[1:3]
            state_name = cls.STATE_CODE_MAP.get(state_digits, f"State Code {state_digits}")

            licenses.append(
                StructuredLicense(
                    license_number=num,
                    original_text=full_snippet,
                    source_type=source_type,
                    source_id=source_id,
                    confidence=base_confidence,
                    is_valid_format=True,
                    license_type=lic_type,
                    state_code=state_name,
                    extraction_method="PATTERN_REGEX",
                )
            )

        return licenses
