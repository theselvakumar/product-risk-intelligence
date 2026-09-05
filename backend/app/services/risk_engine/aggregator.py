import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AnalysisResult, Finding

logger = logging.getLogger(__name__)

# Canonical analysis dimension keys used for grouping
DIMENSION_ANALYSIS_TYPES = {
    "LICENSE_ANALYSIS":         "LICENSE_ANALYSIS",
    "INGREDIENT_ANALYSIS":      "INGREDIENT_ANALYSIS",
    "CLAIM_ANALYSIS":           "CLAIM_ANALYSIS",
    "PACKAGING_ANALYSIS":       "PACKAGING_ANALYSIS",
    "MANUFACTURER_ANALYSIS":    "MANUFACTURER_ANALYSIS",
    "CROSS_SOURCE_CONSISTENCY": "CROSS_SOURCE_CONSISTENCY",
    "DEEP_PRODUCT_ANALYSIS":    None,  # May cover multiple sub-dims
}

CANONICAL_DIMENSIONS = [
    "LICENSE_ANALYSIS",
    "INGREDIENT_ANALYSIS",
    "CLAIM_ANALYSIS",
    "PACKAGING_ANALYSIS",
    "MANUFACTURER_ANALYSIS",
    "CROSS_SOURCE_CONSISTENCY",
]

# Mapping analysis_type prefixes → canonical dimension (for legacy or direct analysis types)
ANALYSIS_TYPE_TO_DIMENSION = {
    "LICENSE":              "LICENSE_ANALYSIS",
    "INGREDIENT":           "INGREDIENT_ANALYSIS",
    "CLAIM":                "CLAIM_ANALYSIS",
    "PACKAGING":            "PACKAGING_ANALYSIS",
    "MANUFACTURER":         "MANUFACTURER_ANALYSIS",
    "CROSS_SOURCE":         "CROSS_SOURCE_CONSISTENCY",
    "CONSISTENCY":          "CROSS_SOURCE_CONSISTENCY",
    "DEEP_PRODUCT":         None,  # covers multiple sub-dimensions; resolved via findings
}


class DimensionFindingGroup:
    """Aggregated findings for one analysis dimension."""

    def __init__(self, dimension: str) -> None:
        self.dimension = dimension
        self.findings: List[Dict[str, Any]] = []

    def add(self, severity: str, confidence: float, title: str) -> None:
        self.findings.append({
            "severity": severity,
            "confidence": confidence,
            "title": title,
        })

    @property
    def count(self) -> int:
        return len(self.findings)

    @property
    def max_severity(self) -> str:
        order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
        for sev in order:
            if any(f["severity"] == sev for f in self.findings):
                return sev
        return "INFO"

    @property
    def mean_confidence(self) -> float:
        if not self.findings:
            return 0.0
        return sum(f["confidence"] for f in self.findings) / len(self.findings)


def _resolve_dimension(analysis_type: str) -> Optional[str]:
    """
    Map an analysis_type string to its canonical dimension key.
    Preserved for backward compatibility.
    """
    if not analysis_type:
        return None
    upper = analysis_type.upper().strip()
    if upper in DIMENSION_ANALYSIS_TYPES:
        return DIMENSION_ANALYSIS_TYPES[upper]
    for prefix, dim in ANALYSIS_TYPE_TO_DIMENSION.items():
        if upper.startswith(prefix):
            return dim
    return None


def resolve_finding_dimension(
    finding: Finding,
    analysis_type: Optional[str] = None,
) -> Optional[str]:
    """
    Robust regulatory dimension resolver for a statutory Finding.

    Resolution hierarchy:
    1. Explicit metadata in finding.discrepancy_details (if contains 'dimension').
    2. Rule code pattern matching (authoritative statutory regulation prefix/infix).
    3. Enclosing AnalysisResult analysis_type (if specific dimension and not composite).
    4. Fallback keyword heuristic on finding title.
    5. Unknown / unresolved: logs warning and returns None (avoids silent misclassification).

    Source provenance (finding.source) is NOT used as an analysis dimension key.
    """
    # 1. Explicit metadata check
    if isinstance(finding.discrepancy_details, dict):
        explicit_dim = (
            finding.discrepancy_details.get("dimension")
            or finding.discrepancy_details.get("analysis_dimension")
            or finding.discrepancy_details.get("target_dimension")
        )
        if explicit_dim:
            normalized = str(explicit_dim).upper().strip()
            if normalized in CANONICAL_DIMENSIONS:
                return normalized

    # 2. Rule code pattern matching
    code = (finding.rule_code or "").upper().strip()
    if code:
        # A. CROSS_SOURCE_CONSISTENCY
        if (
            code.startswith("CONSISTENCY")
            or code.startswith("CON-")
            or code.startswith("CROSS-")
            or code.startswith("CROSS_SOURCE")
            or "-CONSISTENCY-" in code
            or code.endswith("-CONSISTENCY")
            or "-CROSS-" in code
        ):
            return "CROSS_SOURCE_CONSISTENCY"

        # B. CLAIM_ANALYSIS
        if (
            code.startswith("CLM-")
            or code.startswith("CLAIM")
            or "-CLM-" in code
            or "-CLAIM-" in code
            or code.endswith("-CLAIM")
            or code.startswith("FSSAI-CLAIM-")
            or "ADV-2018" in code
            or "ADVERTISING" in code
            or "PROMOTIONAL" in code
            or "HEALTH_CLAIM" in code
        ):
            return "CLAIM_ANALYSIS"

        # C. INGREDIENT_ANALYSIS
        # Catches standard ING rule codes, banned toxic adulterants (FSSAI-BAN-...),
        # mandatory additive declarations (FSSAI-ADV-SWEETENER-...), allergens, and composite ingredients
        if (
            code.startswith("ING-")
            or code.startswith("INGREDIENT")
            or "-ING-" in code
            or "-ING" in code
            or "-INGREDIENT-" in code
            or code.endswith("-INGREDIENT")
            or code.startswith("FSSAI-ING-")
            or "SWEETENER" in code
            or "ALLERGEN" in code
            or "ADDITIVE" in code
            or "ADULTERANT" in code
            or code.startswith("FSSAI-BAN-")
            or "-BAN-" in code
            or code.startswith("BAN-")
        ):
            return "INGREDIENT_ANALYSIS"

        # D. LICENSE_ANALYSIS
        if (
            code.startswith("LIC-")
            or code.startswith("LICENSE")
            or "-LIC-" in code
            or "-LIC" in code
            or "-LICENSE-" in code
            or code.endswith("-LICENSE")
            or "FOSCOS" in code
            or "SEC-31" in code
            or code.startswith("FSSAI-LIC-")
        ):
            return "LICENSE_ANALYSIS"

        # E. MANUFACTURER_ANALYSIS
        if (
            code.startswith("MFG-")
            or code.startswith("MFR-")
            or code.startswith("MANUFACTURER")
            or "-MFR-" in code
            or code.endswith("-MFR")
            or "-MFG-" in code
            or code.endswith("-MFG")
            or code.startswith("FSSAI-MFR-")
            or ("MANUFACTURER" in code and not code.startswith("FSSAI-LABEL-"))
        ):
            return "MANUFACTURER_ANALYSIS"

        # F. PACKAGING_ANALYSIS
        # Catches PKG codes and all FSS (Labelling and Display) Regulations 2020 label evaluation codes
        if (
            code.startswith("PKG-")
            or code.startswith("PACKAGING")
            or "-PKG-" in code
            or code.endswith("-PKG")
            or "-PACKAGING-" in code
            or code.startswith("FSSAI-LABEL-")
            or "LABEL-2020" in code
            or "LABEL-EVAL" in code
            or "PACKAGING_LABEL" in code
        ):
            return "PACKAGING_ANALYSIS"

    # 3. Fallback: Enclosing AnalysisResult analysis_type (if specific single-dimension analysis)
    if analysis_type and analysis_type.upper().strip() != "DEEP_PRODUCT_ANALYSIS":
        at_upper = analysis_type.upper().strip()
        if at_upper in CANONICAL_DIMENSIONS:
            return at_upper
        for prefix, dim in ANALYSIS_TYPE_TO_DIMENSION.items():
            if dim and at_upper.startswith(prefix):
                return dim

    # 4. Fallback: Finding title keyword heuristics
    title_upper = (finding.finding_title or "").upper()
    if any(w in title_upper for w in ["LICENSE", "FOSCOS", "SEC 31", "SECTION 31"]):
        return "LICENSE_ANALYSIS"
    if any(w in title_upper for w in ["INGREDIENT", "ADDITIVE", "ALLERGEN", "SWEETENER", "ADULTERANT", "RHODAMINE", "MELAMINE", "AURAMINE"]):
        return "INGREDIENT_ANALYSIS"
    if any(w in title_upper for w in ["CLAIM", "DISEASE", "CURE", "GUARANTEE", "SUPERLATIVE", "THERAPEUTIC"]):
        return "CLAIM_ANALYSIS"
    if any(w in title_upper for w in ["PACKAGING", "LABEL", "EXPIRY DATE", "BEST BEFORE", "NET WEIGHT", "NET QUANTITY"]):
        return "PACKAGING_ANALYSIS"
    if any(w in title_upper for w in ["MANUFACTURER", "PACKER", "MARKETER", "PREMISE", "MFR"]):
        return "MANUFACTURER_ANALYSIS"
    if any(w in title_upper for w in ["CONSISTENCY", "DISCREPANCY", "MISMATCH", "CROSS-SOURCE"]):
        return "CROSS_SOURCE_CONSISTENCY"

    # 5. Unknown / Unresolvable: Log warning and return None (never silently misclassify)
    logger.warning(
        "Finding could not be resolved to any regulatory risk dimension: "
        "title='%s', id=%s, rule_code='%s', source='%s', analysis_type='%s'",
        finding.finding_title,
        getattr(finding, "id", None),
        finding.rule_code,
        finding.source,
        analysis_type,
    )
    return None


class FindingAggregator:
    """
    Loads all findings from the database for a given product,
    groups them by analysis dimension, and computes data completeness.
    """

    EXPECTED_DIMENSIONS = CANONICAL_DIMENSIONS

    @classmethod
    def resolve_dimension(
        cls,
        finding: Finding,
        analysis_type: Optional[str] = None,
    ) -> Optional[str]:
        """Convenience classmethod delegating to resolve_finding_dimension."""
        return resolve_finding_dimension(finding, analysis_type)

    @classmethod
    async def aggregate(
        cls,
        product_id: uuid.UUID,
        db: AsyncSession,
    ) -> Tuple[Dict[str, DimensionFindingGroup], float]:
        """
        Returns:
            groups: dimension → DimensionFindingGroup
            data_completeness_ratio: 0.0–1.0
        """
        # Fetch all analysis results for this product
        ar_stmt = select(AnalysisResult).where(AnalysisResult.product_id == product_id)
        analysis_results = (await db.execute(ar_stmt)).scalars().all()

        # Initialise empty groups for all known dimensions
        groups: Dict[str, DimensionFindingGroup] = {
            dim: DimensionFindingGroup(dim)
            for dim in cls.EXPECTED_DIMENSIONS
        }

        for ar in analysis_results:
            # Load findings for this analysis result
            f_stmt = select(Finding).where(Finding.analysis_result_id == ar.id)
            findings = (await db.execute(f_stmt)).scalars().all()
            for f in findings:
                target_dim = cls.resolve_dimension(f, ar.analysis_type)
                if target_dim and target_dim in groups:
                    groups[target_dim].add(
                        severity=f.severity or "INFO",
                        confidence=float(f.confidence or 0.5),
                        title=f.finding_title or "",
                    )

        # Data completeness: fraction of expected dimensions that have active findings or analysis coverage
        dimensions_with_data = sum(1 for g in groups.values() if len(g.findings) > 0)
        expected = len(groups)
        data_completeness = min(dimensions_with_data / expected, 1.0) if expected > 0 else 0.0

        return groups, data_completeness

