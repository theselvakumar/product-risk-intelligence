import re
from typing import Any, Dict, List, Optional
import uuid

from app.schemas.deep_analysis import AnalysisEvidenceDTO, AnalysisFindingDTO, ModuleResultDTO
from app.schemas.intelligence import CanonicalStructuredProduct
from app.services.analysis.base import BaseAnalysisModule


class ClaimAnalyzer(BaseAnalysisModule):
    """
    Identifies, tags, and evaluates marketing claims across six analytical categories:
    - Health claims
    - Disease-related claims
    - Absolute claims
    - Guaranteed results
    - Scientific claims
    - Promotional claims
    Strictly flags potentially relevant claims without making premature legal conclusions.
    """

    @property
    def module_name(self) -> str:
        return "CLAIM_ANALYSIS"

    # Specific analytical regex patterns
    PATTERNS = {
        "DISEASE_RELATED": [
            r"\b(?:cures?|curing|curative)\b",
            r"\b(?:treats?|treatment|remedy)\b.*?\b(?:diabetes|cancer|hypertension|arthritis|disease|infection)\b",
            r"\b(?:prevents?|reverses?)\b.*?\b(?:diabetes|cancer|heart disease|stroke)\b",
            r"\b(?:anti[- ]cancer|anti[- ]diabetic)\b",
        ],
        "GUARANTEED_RESULTS": [
            r"\b(?:guaranteed|guarantee)\s*(?:results?|cure|weight loss|solution|relief)\b",
            r"\b(?:100%|complete|permanent)\s*(?:cure|recovery|relief)\b",
            r"\bresults?\s*(?:in \d+ days|instantly|guaranteed)\b",
        ],
        "ABSOLUTE_CLAIMS": [
            r"\b100%\s*(?:pure|natural|organic|authentic|safe|effective)\b",
            r"\b(?:best|finest|purest|world['’]s best|india['’]s best)\b",
            r"\b(?:miracle|zero defect)\b",
        ],
        "SCIENTIFIC_CLAIMS": [
            r"\b(?:scientifically|clinically)\s*(?:proven|tested|validated|verified|backed)\b",
            r"\b(?:clinical\s*trials?|laboratory\s*certified|evidence[- ]based)\b",
            r"\bresearch[- ]backed\b",
        ],
        "PROMOTIONAL_CLAIMS": [
            r"\b(?:doctor|physician|pediatrician|expert|dentist)\s*(?:recommended|approved|certified|prescribed)\b",
            r"\b(?:celebrity|endorsed|india['’]s #1|no\.?\s*1 brand)\b",
        ],
        "HEALTH_CLAIMS": [
            r"\b(?:boosts?|enhances?)\s*(?:immunity|energy|stamina)\b",
            r"\b(?:promotes?|supports?)\s*(?:weight loss|digestion|gut health|vitality)\b",
        ],
    }

    def analyze(
        self,
        case_id: uuid.UUID,
        structured_data: CanonicalStructuredProduct,
        raw_sources: Optional[List[Any]] = None,
        ocr_records: Optional[List[Any]] = None,
    ) -> ModuleResultDTO:
        findings: List[AnalysisFindingDTO] = []
        evidence_list: List[AnalysisEvidenceDTO] = []
        claims = structured_data.claims

        if not claims:
            return ModuleResultDTO(
                module_name=self.module_name,
                status="COMPLETED",
                confidence=0.90,
                severity_suggestion="INFO",
                findings=[
                    self.create_finding(
                        title="No explicit claims detected",
                        description="No overt marketing, health, or nutritional claims were extracted from the available evidence.",
                        severity="INFO",
                        confidence=0.90,
                        source="STRUCTURED_INTELLIGENCE",
                        rule_code="FSSAI-CLAIM-NONE",
                    )
                ],
                evidence=[],
                details={"total_claims": 0},
            )

        # Track categories identified
        categorized_counts: Dict[str, int] = {
            "DISEASE_RELATED": 0,
            "GUARANTEED_RESULTS": 0,
            "ABSOLUTE_CLAIMS": 0,
            "SCIENTIFIC_CLAIMS": 0,
            "PROMOTIONAL_CLAIMS": 0,
            "HEALTH_CLAIMS": 0,
        }

        for claim in claims:
            text = claim.claim_text
            lower_text = text.lower()
            matched_any = False

            # 1. Disease-related claims
            for p in self.PATTERNS["DISEASE_RELATED"]:
                if re.search(p, lower_text):
                    categorized_counts["DISEASE_RELATED"] += 1
                    matched_any = True
                    ev = AnalysisEvidenceDTO(
                        evidence_type="TEXT_SNIPPET",
                        caption="Disease-related claim snippet",
                        text_snippet=claim.original_text,
                        source_reference=claim.source_type,
                    )
                    evidence_list.append(ev)
                    findings.append(
                        self.create_finding(
                            title="Disease-related claim identified",
                            description=(
                                f"Claim \"{claim.claim_text}\" refers to disease treatment, cure, or mitigation. "
                                "Flagged for authoritative statutory review under Regulation 4(7); "
                                "claims of disease cure are prohibited on food products without prior Central Approval."
                            ),
                            severity="HIGH",
                            confidence=0.94,
                            source=claim.source_type,
                            rule_code="FSSAI-CLAIM-DISEASE-CURE-FLAG",
                            statutory_ref="FSS (Advertising and Claims) Regulations, 2018: Regulation 4(7) & FSS Act Section 24",
                            evidence=[ev],
                        )
                    )
                    break

            # 2. Guaranteed results
            for p in self.PATTERNS["GUARANTEED_RESULTS"]:
                if re.search(p, lower_text):
                    categorized_counts["GUARANTEED_RESULTS"] += 1
                    matched_any = True
                    findings.append(
                        self.create_finding(
                            title="Guaranteed result claim identified",
                            description=(
                                f"Claim \"{claim.claim_text}\" promises absolute or guaranteed health outcomes. "
                                "Flagged for documentation substantiating guaranteed efficacy."
                            ),
                            severity="MEDIUM",
                            confidence=0.90,
                            source=claim.source_type,
                            rule_code="FSSAI-CLAIM-GUARANTEE-FLAG",
                            statutory_ref="FSS (Advertising and Claims) Regulations, 2018: Regulation 4(4)",
                        )
                    )
                    break

            # 3. Scientific claims
            for p in self.PATTERNS["SCIENTIFIC_CLAIMS"]:
                if re.search(p, lower_text):
                    categorized_counts["SCIENTIFIC_CLAIMS"] += 1
                    matched_any = True
                    findings.append(
                        self.create_finding(
                            title="Scientific claim identified",
                            description=(
                                f"Claim \"{claim.claim_text}\" asserts scientific or clinical validation. "
                                "Flagged for clinical substantiation review upon statutory enquiry."
                            ),
                            severity="LOW",
                            confidence=0.88,
                            source=claim.source_type,
                            rule_code="FSSAI-CLAIM-SCIENTIFIC-FLAG",
                            statutory_ref="FSS (Advertising and Claims) Regulations, 2018: Regulation 5",
                        )
                    )
                    break

            # 4. Promotional claims (Endorsements)
            for p in self.PATTERNS["PROMOTIONAL_CLAIMS"]:
                if re.search(p, lower_text):
                    categorized_counts["PROMOTIONAL_CLAIMS"] += 1
                    matched_any = True
                    findings.append(
                        self.create_finding(
                            title="Promotional endorsement claim identified",
                            description=(
                                f"Claim \"{claim.claim_text}\" implies medical or professional endorsement. "
                                "Requires verification against statutory advertising restrictions."
                            ),
                            severity="LOW",
                            confidence=0.88,
                            source=claim.source_type,
                            rule_code="FSSAI-CLAIM-ENDORSEMENT-FLAG",
                            statutory_ref="FSS (Advertising and Claims) Regulations, 2018: Regulation 4(8)",
                        )
                    )
                    break

            # 5. Absolute claims
            for p in self.PATTERNS["ABSOLUTE_CLAIMS"]:
                if re.search(p, lower_text):
                    categorized_counts["ABSOLUTE_CLAIMS"] += 1
                    matched_any = True
                    findings.append(
                        self.create_finding(
                            title="Absolute superlative claim identified",
                            description=(
                                f"Claim \"{claim.claim_text}\" uses superlative terminology (\"100% pure / best\"). "
                                "Requires evidence proving absolute purity under Schedule I guidelines."
                            ),
                            severity="LOW",
                            confidence=0.88,
                            source=claim.source_type,
                            rule_code="FSSAI-CLAIM-SUPERLATIVE-FLAG",
                            statutory_ref="FSS (Advertising and Claims) Regulations, 2018: Schedule I",
                        )
                    )
                    break

            # 6. General Health claims
            if not matched_any:
                for p in self.PATTERNS["HEALTH_CLAIMS"]:
                    if re.search(p, lower_text):
                        categorized_counts["HEALTH_CLAIMS"] += 1
                        findings.append(
                            self.create_finding(
                                title="Health or functional claim identified",
                                description=f"General health/functional claim identified: \"{claim.claim_text}\".",
                                severity="INFO",
                                confidence=0.85,
                                source=claim.source_type,
                                rule_code="FSSAI-CLAIM-FUNCTIONAL-INFO",
                                statutory_ref="FSS (Advertising and Claims) Regulations, 2018: Regulation 6",
                            )
                        )
                        break

        # Suggest overall severity
        if categorized_counts["DISEASE_RELATED"] > 0:
            severity_sug = "HIGH"
        elif categorized_counts["GUARANTEED_RESULTS"] > 0:
            severity_sug = "MEDIUM"
        elif categorized_counts["SCIENTIFIC_CLAIMS"] > 0 or categorized_counts["PROMOTIONAL_CLAIMS"] > 0:
            severity_sug = "LOW"
        else:
            severity_sug = "INFO"

        return ModuleResultDTO(
            module_name=self.module_name,
            status="COMPLETED",
            confidence=0.92,
            severity_suggestion=severity_sug,
            findings=findings,
            evidence=evidence_list,
            details={
                "total_claims_analyzed": len(claims),
                "categorized_counts": categorized_counts,
            },
        )
