from typing import Any, Dict, List, Optional
import uuid

from app.schemas.deep_analysis import AnalysisEvidenceDTO, AnalysisFindingDTO, ModuleResultDTO
from app.schemas.intelligence import CanonicalStructuredProduct
from app.services.analysis.base import BaseAnalysisModule


class RegulatoryKnowledgeBase:
    """
    Authoritative statutory food standards and additive knowledge base
    grounded in FSS (Food Products Standards and Food Additives) Regulations, 2011
    and FSS (Prohibition and Restrictions on Sales) Regulations, 2011.
    """

    # Prohibited toxic adulterants & banned chemical substances (Section 26 / Central Gazettes)
    PROHIBITED_SUBSTANCES = {
        "rhodamine b": {
            "title": "Banned Industrial Dye (Rhodamine B)",
            "severity": "CRITICAL",
            "statutory_ref": "FSS (Prohibition and Restrictions on Sales) Regulations, 2011: Regulation 2.1.1",
            "rule_code": "FSSAI-BAN-RHODAMINE-B",
            "reason": "Rhodamine B is a non-permitted toxic industrial dye strictly prohibited in all food commodities due to severe carcinogenic risk.",
        },
        "potassium bromate": {
            "title": "Prohibited Food Additive (Potassium Bromate)",
            "severity": "CRITICAL",
            "statutory_ref": "FSSAI Gazette Notification No. 1-100/SP(IM-Nutraceuticals)/FSSAI-2016",
            "rule_code": "FSSAI-BAN-POTASSIUM-BROMATE",
            "reason": "Potassium bromate is completely prohibited as a flour treatment agent under Central Gazette directives.",
        },
        "melamine": {
            "title": "Banned Chemical Adulterant (Melamine)",
            "severity": "CRITICAL",
            "statutory_ref": "FSS (Contaminants, Toxins and Residues) Regulations, 2011: Regulation 2.3.2",
            "rule_code": "FSSAI-BAN-MELAMINE",
            "reason": "Melamine addition in dairy or proteinaceous foods constitutes statutory adulteration with acute nephrotoxic hazard.",
        },
        "auramine": {
            "title": "Non-Permitted Coal Tar Dye (Auramine)",
            "severity": "CRITICAL",
            "statutory_ref": "FSS (Food Products Standards and Food Additives) Regulations: Regulation 3.1.2",
            "rule_code": "FSSAI-BAN-AURAMINE",
            "reason": "Non-permitted synthetic coloring matter prohibited under statutory standards.",
        },
    }

    # Restricted food additives requiring statutory advisory declarations
    RESTRICTED_ADDITIVES = {
        "aspartame": {
            "title": "Mandatory Advisory for Artificial Sweetener (Aspartame)",
            "statutory_ref": "FSS (Labelling and Display) Regulations, 2020: Schedule II, Clause 1",
            "rule_code": "FSSAI-ADV-SWEETENER-ASPARTAME",
            "advisory_required": "Contains Artificial Sweetener and for Calorie Conscious - Not recommended for children.",
        },
        "sucralose": {
            "title": "Mandatory Advisory for Artificial Sweetener (Sucralose)",
            "statutory_ref": "FSS (Labelling and Display) Regulations, 2020: Schedule II, Clause 1",
            "rule_code": "FSSAI-ADV-SWEETENER-SUCRALOSE",
            "advisory_required": "Contains Artificial Sweetener Sucralose.",
        },
        "acesulfame potassium": {
            "title": "Mandatory Advisory for Artificial Sweetener (Acesulfame K)",
            "statutory_ref": "FSS (Labelling and Display) Regulations, 2020: Schedule II, Clause 1",
            "rule_code": "FSSAI-ADV-SWEETENER-ACE-K",
            "advisory_required": "Contains Artificial Sweetener (Acesulfame Potassium).",
        },
        "monosodium glutamate": {
            "title": "Mandatory Declaration for Added MSG",
            "statutory_ref": "FSS (Labelling and Display) Regulations, 2020: Regulation 2.4.5",
            "rule_code": "FSSAI-DEC-MSG",
            "advisory_required": "This package contains added MONOSODIUM GLUTAMATE - Not recommended for infants below 12 months.",
        },
    }


class IngredientAnalyzer(BaseAnalysisModule):
    """
    Analyzes ingredient list presence, completeness, normalization, and statutory knowledge base matches.
    """

    @property
    def module_name(self) -> str:
        return "INGREDIENT_ANALYSIS"

    def analyze(
        self,
        case_id: uuid.UUID,
        structured_data: CanonicalStructuredProduct,
        raw_sources: Optional[List[Any]] = None,
        ocr_records: Optional[List[Any]] = None,
    ) -> ModuleResultDTO:
        findings: List[AnalysisFindingDTO] = []
        evidence_list: List[AnalysisEvidenceDTO] = []
        ingredients = structured_data.ingredients

        # 1. Presence Check
        if not ingredients:
            findings.append(
                self.create_finding(
                    title="Ingredient information incomplete",
                    description=(
                        "No structured ingredient declaration was identified in the available packaging "
                        "or e-commerce listing evidence. Mandatory ingredient sequence disclosure is missing."
                    ),
                    severity="HIGH",
                    confidence=0.90,
                    source="CROSS_SOURCE_COMPARISON",
                    rule_code="FSSAI-LABEL-2020-ING-MISSING",
                    statutory_ref="FSS (Labelling and Display) Regulations, 2020: Regulation 5(2)",
                )
            )
            return ModuleResultDTO(
                module_name=self.module_name,
                status="COMPLETED",
                confidence=0.90,
                severity_suggestion="HIGH",
                findings=findings,
                evidence=[],
                details={"ingredients_present": False, "count": 0},
            )

        # 2. Information Available
        ing_names = [i.ingredient_name for i in ingredients]
        findings.append(
            self.create_finding(
                title="Ingredient information available",
                description=f"Identified {len(ingredients)} normalized ingredients: {', '.join(ing_names[:10])}{'...' if len(ing_names) > 10 else ''}.",
                severity="INFO",
                confidence=0.95,
                source="STRUCTURED_INTELLIGENCE",
                rule_code="FSSAI-ING-AVAILABLE",
                statutory_ref="FSS (Labelling and Display) Regulations, 2020: Regulation 5(2)",
            )
        )

        for ing in ingredients[:5]:
            evidence_list.append(
                AnalysisEvidenceDTO(
                    evidence_type="TEXT_SNIPPET",
                    caption=f"Ingredient: {ing.ingredient_name}",
                    text_snippet=ing.original_text,
                    source_reference=ing.source_type,
                    metadata_json={"ins_number": ing.ins_number, "is_allergen": ing.is_allergen},
                )
            )

        # 3. Completeness & Proprietary Mix Check
        has_vague_terms = False
        vague_terms = ["proprietary blend", "herbal extract", "active ingredients", "special formulation", "natural herbs"]
        for ing in ingredients:
            lower_name = ing.ingredient_name.lower()
            if any(v in lower_name for v in vague_terms) and not ing.sub_components:
                has_vague_terms = True
                findings.append(
                    self.create_finding(
                        title="Requires review",
                        description=(
                            f"Ingredient '{ing.ingredient_name}' uses composite or proprietary terminology "
                            "without mandatory breakdown of specific constituent ingredients."
                        ),
                        severity="MEDIUM",
                        confidence=0.88,
                        source=ing.source_type,
                        rule_code="FSSAI-LABEL-2020-COMPOSITE-ING",
                        statutory_ref="FSS (Labelling and Display) Regulations, 2020: Regulation 5(2)(b)",
                    )
                )

        # 4. Authoritative Knowledge Base Matches (Banned / Restricted Substances)
        kb_concern_found = False
        for ing in ingredients:
            lower_name = ing.ingredient_name.lower()
            lower_orig = ing.original_text.lower()

            # Check Prohibited Substances
            for banned_substance, meta in RegulatoryKnowledgeBase.PROHIBITED_SUBSTANCES.items():
                if banned_substance in lower_name or banned_substance in lower_orig:
                    kb_concern_found = True
                    findings.append(
                        self.create_finding(
                            title="Potential knowledge base concern",
                            description=(
                                f"Ingredient token '{ing.ingredient_name}' matches prohibited substance: {meta['title']}. "
                                f"{meta['reason']}"
                            ),
                            severity=meta["severity"],
                            confidence=0.96,
                            source=ing.source_type,
                            rule_code=meta["rule_code"],
                            statutory_ref=meta["statutory_ref"],
                        )
                    )

            # Check Restricted Additives requiring statutory advisory
            for restricted_substance, meta in RegulatoryKnowledgeBase.RESTRICTED_ADDITIVES.items():
                if restricted_substance in lower_name or restricted_substance in lower_orig:
                    findings.append(
                        self.create_finding(
                            title="Requires review",
                            description=(
                                f"Restricted additive '{ing.ingredient_name}' identified. "
                                f"Packaging must display mandatory statutory advisory: \"{meta['advisory_required']}\"."
                            ),
                            severity="MEDIUM",
                            confidence=0.92,
                            source=ing.source_type,
                            rule_code=meta["rule_code"],
                            statutory_ref=meta["statutory_ref"],
                        )
                    )

        # Determine severity suggestion
        if any(f.severity == "CRITICAL" for f in findings):
            severity_sug = "CRITICAL"
        elif any(f.severity == "HIGH" for f in findings):
            severity_sug = "HIGH"
        elif any(f.severity == "MEDIUM" for f in findings):
            severity_sug = "MEDIUM"
        else:
            severity_sug = "INFO"

        return ModuleResultDTO(
            module_name=self.module_name,
            status="COMPLETED",
            confidence=0.93,
            severity_suggestion=severity_sug,
            findings=findings,
            evidence=evidence_list,
            details={
                "ingredients_count": len(ingredients),
                "has_vague_terms": has_vague_terms,
                "kb_concern_found": kb_concern_found,
                "allergens_detected": structured_data.allergens_detected,
                "additives_detected": structured_data.additives_detected,
            },
        )
