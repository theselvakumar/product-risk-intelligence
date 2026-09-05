import uuid
from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.services.risk_engine.aggregator import DimensionFindingGroup
from app.services.risk_engine.config import RiskEngineConfig


@dataclass
class ContributingFactor:
    """Explainable per-dimension risk contribution."""
    dimension: str
    finding_count: int
    max_severity: str
    weighted_contribution: float   # Final contribution to risk_score after weighting
    raw_dimension_score: float     # Pre-weight dimension score [0,1]
    confidence: float


@dataclass
class ScoringResult:
    risk_score: float
    risk_level: str
    confidence_score: float
    contributing_factors: List[ContributingFactor]
    score_explanation: str
    data_completeness_ratio: float
    total_findings_analyzed: int


class RiskScorer:
    """
    Implements the four-stage scoring pipeline:
    1. Severity Assessment  — maps each finding severity to a numeric impact value.
    2. Weight Assignment    — applies configured dimension weights.
    3. Confidence Adjustment — scales by mean finding confidence.
    4. Risk Aggregation     — weighted sum, classification, explanation.
    """

    def __init__(self, config: RiskEngineConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Stage 1: Severity Assessment
    # ------------------------------------------------------------------
    def _dimension_raw_score(self, group: DimensionFindingGroup) -> float:
        """
        Compute a raw [0,1] score for one dimension based on its findings.
        Uses the peak-severity approach: the worst finding dominates,
        with a count-based amplifier (capped to prevent extreme inflation).
        """
        if group.count == 0:
            return 0.0

        impact_values = self.config.severity_impact
        max_impact = impact_values.get(group.max_severity, 0.05)

        # Count amplifier: each additional finding adds a diminishing fraction.
        # log-like scaling: f(n) = 1 + log2(n) / 5, capped at 1.5
        import math
        count_amplifier = min(1.0 + math.log2(group.count) / 5, 1.5)

        return min(max_impact * count_amplifier, 1.0)

    # ------------------------------------------------------------------
    # Stage 2 + 3: Weight Assignment + Confidence Adjustment
    # ------------------------------------------------------------------
    def _weighted_contribution(
        self,
        dimension: str,
        raw_score: float,
        confidence: float,
    ) -> float:
        """Apply dimension weight and a soft confidence scaling.

        A hard linear confidence multiplier over-penalises moderate-confidence
        findings (e.g. 0.70 confidence × HIGH severity → score drops 30%).
        Instead we use a soft floor so that even the lowest-confidence finding
        still contributes at least 55% of its unscaled weight:
            soft_confidence = 0.5 + 0.5 × confidence  → range [0.55, 1.0]
        """
        weight = self.config.dimension_weights.get(dimension, 0.0)
        soft_confidence = 0.5 + 0.5 * max(confidence, 0.10)
        return raw_score * weight * soft_confidence


    # ------------------------------------------------------------------
    # Stage 4: Aggregation + Explanation
    # ------------------------------------------------------------------
    def compute(
        self,
        groups: Dict[str, DimensionFindingGroup],
        data_completeness: float,
    ) -> ScoringResult:

        factors: List[ContributingFactor] = []
        total_weighted = 0.0
        total_findings = 0
        all_confidences: List[float] = []

        for dimension, group in groups.items():
            raw_score = self._dimension_raw_score(group)
            confidence = group.mean_confidence if group.count > 0 else 0.5
            contribution = self._weighted_contribution(dimension, raw_score, confidence)

            factors.append(ContributingFactor(
                dimension=dimension,
                finding_count=group.count,
                max_severity=group.max_severity if group.count > 0 else "NONE",
                weighted_contribution=round(contribution, 4),
                raw_dimension_score=round(raw_score, 4),
                confidence=round(confidence, 4),
            ))
            total_weighted += contribution
            total_findings += group.count
            if group.count > 0:
                all_confidences.append(confidence)

        # Data completeness contribution (low completeness adds a minor penalty)
        completeness_penalty = (1.0 - data_completeness) * self.config.dimension_weights.get("DATA_COMPLETENESS", 0.05)
        total_weighted += completeness_penalty

        # Overall confidence: mean of per-dimension confidences; penalise low completeness
        if all_confidences:
            overall_confidence = round(
                (sum(all_confidences) / len(all_confidences)) * (0.85 + 0.15 * data_completeness), 4
            )
        else:
            overall_confidence = round(0.25 * data_completeness, 4)  # Minimal confidence

        # Clamp final score
        risk_score = round(min(total_weighted, 1.0), 4)

        # Classify
        risk_level = self.config.classify_risk_level(risk_score)

        # Downgrade if overall confidence is too low to be reliable
        if overall_confidence < self.config.confidence_floor and risk_level == "HIGH":
            risk_level = "MEDIUM"

        # Build human-readable explanation
        explanation = self._build_explanation(factors, risk_score, risk_level, overall_confidence, data_completeness)

        return ScoringResult(
            risk_score=risk_score,
            risk_level=risk_level,
            confidence_score=overall_confidence,
            contributing_factors=factors,
            score_explanation=explanation,
            data_completeness_ratio=round(data_completeness, 4),
            total_findings_analyzed=total_findings,
        )

    @staticmethod
    def _build_explanation(
        factors: List[ContributingFactor],
        score: float,
        level: str,
        confidence: float,
        completeness: float,
    ) -> str:
        dominant = sorted(
            [f for f in factors if f.finding_count > 0],
            key=lambda f: f.weighted_contribution,
            reverse=True,
        )[:3]

        parts = [
            f"Internal Prioritization Risk Score: {score:.2f} ({level}). "
            f"Overall confidence: {confidence:.0%}. "
            f"Data completeness: {completeness:.0%}. "
            f"Total findings analyzed: {sum(f.finding_count for f in factors)}."
        ]

        if dominant:
            top_dims = ", ".join(
                f"{f.dimension} ({f.finding_count} finding(s), max severity: {f.max_severity})"
                for f in dominant
            )
            parts.append(f"Primary contributing dimensions: {top_dims}.")

        if completeness < 0.60:
            parts.append(
                "Note: Data completeness is below 60%. "
                "Score reliability is reduced. Additional analysis is recommended."
            )

        return " ".join(parts)
