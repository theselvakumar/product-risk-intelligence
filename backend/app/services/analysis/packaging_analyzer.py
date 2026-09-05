import re
from typing import Any, Dict, List, Optional
import uuid

from app.schemas.deep_analysis import AnalysisEvidenceDTO, AnalysisFindingDTO, ModuleResultDTO
from app.schemas.intelligence import CanonicalStructuredProduct
from app.services.analysis.base import BaseAnalysisModule


class PackagingAnalyzer(BaseAnalysisModule):
    """
    Evaluates mandatory statutory packaging declarations under FSS (Labelling and Display) Regulations, 2020.
    Checks the presence of six statutory labeling elements and reports status as:
    PRESENT, MISSING, or UNCLEAR.
    """

    @property
    def module_name(self) -> str:
        return "PACKAGING_ANALYSIS"

    DATE_PATTERNS = [
        r"\b(?:mfg|mfd|manufactured|packed)\s*(?:date|on)?[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\b[a-z]{3}\s*\d{2,4})\b",
        r"\b(?:exp|expiry|use\s*by|best\s*before)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d+\s*months?|\b[a-z]{3}\s*\d{2,4})\b",
        r"\bbest\s*before\s*\d+\s*(?:months|days)\s*from\b",
    ]

    WARNING_PATTERNS = [
        r"\b(?:contains?\s*(?:artificial\s*sweetener|added\s*flavor|preservative|caffeine))\b",
        r"\b(?:allergen\s*advice|allergen\s*warning|contains?\s*(?:milk|wheat|gluten|soy|nuts?|eggs?))\b",
        r"\b(?:not\s*recommended\s*for\s*children|not\s*for\s*medicinal\s*use)\b",
    ]

    def analyze(
        self,
        case_id: uuid.UUID,
        structured_data: CanonicalStructuredProduct,
        raw_sources: Optional[List[Any]] = None,
        ocr_records: Optional[List[Any]] = None,
    ) -> ModuleResultDTO:
        findings: List[AnalysisFindingDTO] = []
        evidence_list: List[AnalysisEvidenceDTO] = []

        # Combine text across OCR records and descriptions for packaging analysis
        full_text_corpus = ""
        if ocr_records:
            full_text_corpus += " ".join(getattr(r, "raw_text", "") for r in ocr_records) + " "
        if raw_sources:
            for s in raw_sources:
                full_text_corpus += (getattr(s, "raw_content", "") or "") + " "

        element_status: Dict[str, str] = {}

        # 1. Product Name
        prod_name = structured_data.product_metadata.name.value if structured_data.product_metadata.name else None
        if prod_name and len(prod_name.strip()) > 2:
            element_status["Product Name"] = "PRESENT"
        elif prod_name:
            element_status["Product Name"] = "UNCLEAR"
        else:
            element_status["Product Name"] = "MISSING"

        # 2. Manufacturer
        mfr = structured_data.product_metadata.manufacturer.value if structured_data.product_metadata.manufacturer else None
        if not mfr and re.search(r"\b(?:mfd|manufactured|marketed|packed)\s*by[:\s]*([a-zA-Z0-9\s,\.]+)", full_text_corpus, re.I):
            mfr = "Detected in raw label text"

        if mfr and len(mfr.strip()) > 3:
            element_status["Manufacturer"] = "PRESENT"
        elif mfr:
            element_status["Manufacturer"] = "UNCLEAR"
        else:
            element_status["Manufacturer"] = "MISSING"

        # 3. Ingredients
        ing_count = len(structured_data.ingredients)
        if ing_count >= 2:
            element_status["Ingredients"] = "PRESENT"
        elif ing_count == 1:
            element_status["Ingredients"] = "UNCLEAR"
        else:
            element_status["Ingredients"] = "MISSING"

        # 4. License Information
        lic_count = len(structured_data.license_info)
        if lic_count > 0:
            if all(l.is_valid_format for l in structured_data.license_info):
                element_status["License Information"] = "PRESENT"
            else:
                element_status["License Information"] = "UNCLEAR"
        else:
            element_status["License Information"] = "MISSING"

        # 5. Dates (Mfg / Expiry / Best Before)
        date_detected = False
        date_snippet = None
        for p in self.DATE_PATTERNS:
            m = re.search(p, full_text_corpus, re.I)
            if m:
                date_detected = True
                date_snippet = m.group(0)
                break

        if date_detected:
            element_status["Dates"] = "PRESENT"
            evidence_list.append(
                AnalysisEvidenceDTO(
                    evidence_type="TEXT_SNIPPET",
                    caption="Extracted Date Declaration",
                    text_snippet=date_snippet,
                    source_reference="PACKAGING_LABEL",
                )
            )
        elif "date" in full_text_corpus.lower() or "mfg" in full_text_corpus.lower():
            element_status["Dates"] = "UNCLEAR"
        else:
            element_status["Dates"] = "MISSING"

        # 6. Warnings & Advisories
        warning_detected = False
        warning_snippet = None
        for p in self.WARNING_PATTERNS:
            m = re.search(p, full_text_corpus, re.I)
            if m:
                warning_detected = True
                warning_snippet = m.group(0)
                break

        # If product contains known allergens or additives, warning presence is required
        has_allergens = len(structured_data.allergens_detected) > 0
        if warning_detected:
            element_status["Warnings"] = "PRESENT"
            evidence_list.append(
                AnalysisEvidenceDTO(
                    evidence_type="TEXT_SNIPPET",
                    caption="Extracted Warning / Advisory Declaration",
                    text_snippet=warning_snippet,
                    source_reference="PACKAGING_LABEL",
                )
            )
        elif has_allergens:
            element_status["Warnings"] = "MISSING"
        else:
            element_status["Warnings"] = "UNCLEAR"

        # Generate findings for missing or unclear statutory declarations
        for element, st in element_status.items():
            if st == "MISSING":
                findings.append(
                    self.create_finding(
                        title=f"Mandatory packaging element missing: {element}",
                        description=f"Mandatory labeling declaration for '{element}' was not found in physical packaging evidence.",
                        severity="HIGH" if element in ("Ingredients", "License Information", "Dates") else "MEDIUM",
                        confidence=0.88,
                        source="PACKAGING_LABEL",
                        rule_code=f"FSSAI-LABEL-2020-{element.upper().replace(' ', '_')}-MISSING",
                        statutory_ref="FSS (Labelling and Display) Regulations, 2020: Regulation 5",
                    )
                )
            elif st == "UNCLEAR":
                findings.append(
                    self.create_finding(
                        title=f"Mandatory packaging element unclear: {element}",
                        description=f"Declaration for '{element}' is partially present, distorted, or ambiguously disclosed.",
                        severity="LOW",
                        confidence=0.82,
                        source="PACKAGING_LABEL",
                        rule_code=f"FSSAI-LABEL-2020-{element.upper().replace(' ', '_')}-UNCLEAR",
                        statutory_ref="FSS (Labelling and Display) Regulations, 2020: Regulation 5",
                    )
                )

        if not any(f.severity in ("HIGH", "CRITICAL") for f in findings):
            findings.insert(
                0,
                self.create_finding(
                    title="Packaging statutory elements evaluated",
                    description=f"Evaluated 6 statutory elements: {element_status}.",
                    severity="INFO",
                    confidence=0.92,
                    source="PACKAGING_LABEL",
                    rule_code="FSSAI-LABEL-EVAL-SUMMARY",
                ),
            )

        severity_sug = "HIGH" if any(f.severity == "HIGH" for f in findings) else ("MEDIUM" if any(f.severity == "MEDIUM" for f in findings) else "INFO")

        return ModuleResultDTO(
            module_name=self.module_name,
            status="COMPLETED",
            confidence=0.90,
            severity_suggestion=severity_sug,
            findings=findings,
            evidence=evidence_list,
            details={"element_status": element_status},
        )
