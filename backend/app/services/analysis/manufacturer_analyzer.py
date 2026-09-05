import re
from typing import Any, Dict, List, Optional
import uuid

from app.schemas.deep_analysis import AnalysisEvidenceDTO, AnalysisFindingDTO, ModuleResultDTO
from app.schemas.intelligence import CanonicalStructuredProduct
from app.services.analysis.base import BaseAnalysisModule


class ManufacturerAnalyzer(BaseAnalysisModule):
    """
    Triangulates manufacturer, packer, and marketer entity names across
    packaging OCR, e-commerce web scrapes, and manual officer submissions.
    Identifies missing data, naming divergences, and potential cross-source discrepancies.
    """

    @property
    def module_name(self) -> str:
        return "MANUFACTURER_ANALYSIS"

    MFR_REGEX = re.compile(
        r"(?:mfd\.?\s*by|manufactured\s*by|marketed\s*by|packed\s*by)[:\s]*([A-Za-z0-9\s,\.&]{3,50})",
        re.IGNORECASE,
    )

    @classmethod
    def _normalize_entity(cls, name: str) -> str:
        """Strip corporate suffixes and non-alphanumerics for comparison."""
        cleaned = re.sub(r"\b(?:pvt|private|ltd|limited|llp|inc|corp|co|company|enterprises|industries)\b", "", name.lower())
        cleaned = re.sub(r"[^a-z0-9 ]+", " ", cleaned)
        return " ".join(cleaned.split())

    def analyze(
        self,
        case_id: uuid.UUID,
        structured_data: CanonicalStructuredProduct,
        raw_sources: Optional[List[Any]] = None,
        ocr_records: Optional[List[Any]] = None,
    ) -> ModuleResultDTO:
        findings: List[AnalysisFindingDTO] = []
        evidence_list: List[AnalysisEvidenceDTO] = []

        mfr_by_source: Dict[str, str] = {}

        # 1. Base Metadata
        base_mfr = structured_data.product_metadata.manufacturer.value if structured_data.product_metadata.manufacturer else None
        if base_mfr:
            mfr_by_source["MANUAL_SUBMISSION"] = base_mfr

        # 2. Extract from Packaging OCR Records
        if ocr_records:
            for r in ocr_records:
                text = getattr(r, "raw_text", "")
                m = self.MFR_REGEX.search(text)
                if m:
                    ocr_mfr = m.group(1).strip()
                    mfr_by_source["PACKAGING_LABEL"] = ocr_mfr
                    evidence_list.append(
                        AnalysisEvidenceDTO(
                            evidence_type="TEXT_SNIPPET",
                            caption="Packaging Label Manufacturer",
                            text_snippet=m.group(0),
                            source_reference="PACKAGING_LABEL",
                        )
                    )
                    break

        # 3. Extract from Web / Description Sources
        if raw_sources:
            for s in raw_sources:
                payload = getattr(s, "raw_payload_json", {}) or {}
                s_type = getattr(s, "source_type", "PRODUCT_URL")
                
                # Check JSON payload
                if isinstance(payload, dict):
                    web_mfr = payload.get("manufacturer") or payload.get("brand") or payload.get("seller_name")
                    if web_mfr:
                        mfr_by_source[s_type] = str(web_mfr)
                        break

                # Check text content
                content = getattr(s, "raw_content", "") or ""
                m = self.MFR_REGEX.search(content)
                if m:
                    mfr_by_source[s_type] = m.group(1).strip()
                    break

        # Analysis 1: Missing Information
        if not mfr_by_source:
            findings.append(
                self.create_finding(
                    title="Manufacturer information missing",
                    description=(
                        "No manufacturer, packer, or marketer name was identified across physical packaging, "
                        "e-commerce listings, or officer submission records. Mandatory disclosure is missing."
                    ),
                    severity="HIGH",
                    confidence=0.92,
                    source="CROSS_SOURCE_COMPARISON",
                    rule_code="FSSAI-MFR-INFO-MISSING",
                    statutory_ref="FSS (Labelling and Display) Regulations, 2020: Regulation 5(6)",
                )
            )
            return ModuleResultDTO(
                module_name=self.module_name,
                status="COMPLETED",
                confidence=0.92,
                severity_suggestion="HIGH",
                findings=findings,
                evidence=[],
                details={"mfr_found": False},
            )

        # Analysis 2: Information Present in only one source
        if len(mfr_by_source) == 1:
            src_name, entity_name = next(iter(mfr_by_source.items()))
            findings.append(
                self.create_finding(
                    title="Manufacturer information detected",
                    description=f"Manufacturer entity '{entity_name}' identified via {src_name}.",
                    severity="INFO",
                    confidence=0.90,
                    source=src_name,
                    rule_code="FSSAI-MFR-INFO-DETECTED",
                )
            )

        # Analysis 3: Cross-Source Comparison (Different Names & Inconsistencies)
        has_divergence = False
        if len(mfr_by_source) >= 2:
            items = list(mfr_by_source.items())
            first_src, first_name = items[0]
            norm_first = self._normalize_entity(first_name)

            for other_src, other_name in items[1:]:
                norm_other = self._normalize_entity(other_name)
                
                # Check divergence
                if norm_first not in norm_other and norm_other not in norm_first:
                    has_divergence = True
                    findings.append(
                        self.create_finding(
                            title="Different manufacturer names across sources",
                            description=(
                                f"Discrepancy detected in manufacturer identity: '{first_name}' reported on {first_src} "
                                f"conflicts with '{other_name}' advertised on {other_src}. "
                                "May indicate deceptive licensing attribution or unapproved contract manufacturing."
                            ),
                            severity="HIGH",
                            confidence=0.88,
                            source="CROSS_SOURCE_COMPARISON",
                            rule_code="FSSAI-MFR-DISCREPANCY-MISMATCH",
                            statutory_ref="Food Safety and Standards Act, 2006: Section 24 (Misleading Representation)",
                            discrepancy={
                                "source_1": first_src,
                                "name_1": first_name,
                                "source_2": other_src,
                                "name_2": other_name,
                            },
                        )
                    )
                else:
                    findings.append(
                        self.create_finding(
                            title="Manufacturer consistency verified",
                            description=f"Manufacturer entity '{first_name}' aligns consistently across {first_src} and {other_src}.",
                            severity="INFO",
                            confidence=0.92,
                            source="CROSS_SOURCE_COMPARISON",
                            rule_code="FSSAI-MFR-CONSISTENCY-CONFIRMED",
                        )
                    )

        severity_sug = "HIGH" if has_divergence else "INFO"

        return ModuleResultDTO(
            module_name=self.module_name,
            status="COMPLETED",
            confidence=0.91,
            severity_suggestion=severity_sug,
            findings=findings,
            evidence=evidence_list,
            details={
                "mfr_by_source": mfr_by_source,
                "has_divergence": has_divergence,
            },
        )
