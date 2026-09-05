from typing import Any, Dict, List, Optional
import uuid

from app.schemas.deep_analysis import AnalysisEvidenceDTO, AnalysisFindingDTO, ModuleResultDTO
from app.schemas.intelligence import CanonicalStructuredProduct
from app.services.analysis.base import BaseAnalysisModule


class LicenseAnalyzer(BaseAnalysisModule):
    """
    Analyzes presence, extracted format, and cross-source consistency of FSSAI licenses.
    Strictly adheres to regulatory neutrality: does NOT declare validity without authoritative FoSCoS data.
    """

    @property
    def module_name(self) -> str:
        return "LICENSE_ANALYSIS"

    def analyze(
        self,
        case_id: uuid.UUID,
        structured_data: CanonicalStructuredProduct,
        raw_sources: Optional[List[Any]] = None,
        ocr_records: Optional[List[Any]] = None,
    ) -> ModuleResultDTO:
        findings: List[AnalysisFindingDTO] = []
        evidence_list: List[AnalysisEvidenceDTO] = []
        licenses = structured_data.license_info

        # 1. Check Presence
        if not licenses:
            finding = self.create_finding(
                title="License information missing",
                description=(
                    "No 14-digit FSSAI statutory license or registration number was detected "
                    "across physical packaging labels, e-commerce listings, or officer submission data."
                ),
                severity="HIGH",
                confidence=0.92,
                source="CROSS_SOURCE_COMPARISON",
                rule_code="FSSAI-SEC-31-LIC-MISSING",
                statutory_ref="Food Safety and Standards Act, 2006: Section 31 (Licensing and Registration)",
            )
            findings.append(finding)
            return ModuleResultDTO(
                module_name=self.module_name,
                status="COMPLETED",
                confidence=0.92,
                severity_suggestion="HIGH",
                findings=findings,
                evidence=[],
                details={"license_present": False, "license_count": 0},
            )

        # 2. License Information Detected
        detected_nums = [l.license_number for l in licenses]
        for lic in licenses:
            ev = AnalysisEvidenceDTO(
                evidence_type="TEXT_SNIPPET",
                caption=f"Extracted FSSAI License: {lic.license_number}",
                text_snippet=lic.original_text,
                source_reference=lic.source_type,
                metadata_json={"state_code": lic.state_code, "license_type": lic.license_type},
            )
            evidence_list.append(ev)

        findings.append(
            self.create_finding(
                title="License information detected",
                description=f"Statutory license numbers detected: {', '.join(detected_nums)}.",
                severity="INFO",
                confidence=0.95,
                source=licenses[0].source_type,
                rule_code="FSSAI-FOSCOS-DETECTED",
                statutory_ref="FSS (Licensing and Registration of Food Businesses) Regulations, 2011",
                evidence=[evidence_list[0]] if evidence_list else [],
            )
        )

        # 3. Format Verification Check
        format_inconsistent = False
        for lic in licenses:
            num = lic.license_number
            if len(num) != 14 or not num.isdigit() or num[0] not in ("1", "2"):
                format_inconsistent = True
                findings.append(
                    self.create_finding(
                        title="Format appears inconsistent",
                        description=(
                            f"Extracted license token '{num}' does not adhere to standard 14-digit "
                            "FSSAI syntax (must be 14 digits starting with 1 for State/Central License or 2 for Registration)."
                        ),
                        severity="MEDIUM",
                        confidence=0.90,
                        source=lic.source_type,
                        rule_code="FSSAI-LIC-FORMAT-INCONSISTENT",
                        statutory_ref="FSS (Licensing and Registration) Regulation 2.1.2",
                    )
                )

        # 4. Source Consistency Check (if multiple licenses found across different sources)
        unique_numbers = list({l.license_number for l in licenses})
        if len(unique_numbers) > 1:
            sources_by_lic = {l.license_number: l.source_type for l in licenses}
            findings.append(
                self.create_finding(
                    title="Source consistency discrepancy",
                    description=(
                        f"Multiple distinct FSSAI numbers detected across evidence streams: {sources_by_lic}. "
                        "Packaging label and digital listing advertise conflicting license identities."
                    ),
                    severity="HIGH",
                    confidence=0.92,
                    source="CROSS_SOURCE_COMPARISON",
                    rule_code="FSSAI-LIC-SOURCE-MISMATCH",
                    statutory_ref="FSS (Labelling and Display) Regulations, 2020: Chapter 2",
                    discrepancy={"licenses_by_source": sources_by_lic},
                )
            )

        # 5. Requires Verification (Authoritative mandate)
        findings.append(
            self.create_finding(
                title="Requires verification",
                description=(
                    f"FSSAI license(s) {', '.join(unique_numbers)} requires authoritative verification "
                    "against the FoSCoS registry to confirm operational validity, category scope, and registered entity name."
                ),
                severity="INFO",
                confidence=0.95,
                source="FOSCOS_REGISTRY_PENDING",
                rule_code="FSSAI-FOSCOS-VERIFICATION-REQUIRED",
                statutory_ref="FSSAI Operational Mandate for Surveillance Verification",
            )
        )

        severity_sug = "HIGH" if any(f.severity == "HIGH" for f in findings) else ("MEDIUM" if format_inconsistent else "INFO")

        return ModuleResultDTO(
            module_name=self.module_name,
            status="COMPLETED",
            confidence=0.94,
            severity_suggestion=severity_sug,
            findings=findings,
            evidence=evidence_list,
            details={
                "license_present": True,
                "detected_licenses": detected_nums,
                "unique_license_count": len(unique_numbers),
                "format_inconsistent": format_inconsistent,
            },
        )
