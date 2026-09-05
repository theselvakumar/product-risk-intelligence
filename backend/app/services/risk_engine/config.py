from dataclasses import dataclass, field
from typing import Dict


LEGAL_DISCLAIMER = (
    "INTERNAL PRIORITIZATION INSTRUMENT ONLY. "
    "This risk score is generated for internal case triage and prioritization purposes. "
    "It is NOT an official government score, statutory compliance verdict, legal finding, "
    "safety declaration, or a determination that any product is compliant or non-compliant "
    "with applicable regulations. No enforcement or legal action should be taken solely "
    "on the basis of this score without independent verification by an authorized officer."
)


@dataclass
class RiskEngineConfig:
    """
    Fully configurable parameters for the Risk Intelligence Engine.
    All values are internal calibration settings, not regulatory thresholds.
    """

    # --- Severity impact scores (0.0–1.0) ---
    # These are relative internal weights, not statutory severity classifications.
    severity_impact: Dict[str, float] = field(default_factory=lambda: {
        "CRITICAL": 1.00,
        "HIGH":     0.75,
        "MEDIUM":   0.50,
        "LOW":      0.25,
        "INFO":     0.05,
    })

    # --- Per-dimension contribution weights ---
    # Must sum to 1.0. Validated on construction.
    dimension_weights: Dict[str, float] = field(default_factory=lambda: {
        "LICENSE_ANALYSIS":              0.25,
        "INGREDIENT_ANALYSIS":           0.25,
        "CLAIM_ANALYSIS":                0.15,
        "PACKAGING_ANALYSIS":            0.10,
        "MANUFACTURER_ANALYSIS":         0.10,
        "CROSS_SOURCE_CONSISTENCY":      0.10,
        "DATA_COMPLETENESS":             0.05,
    })

    # --- Risk level classification thresholds ---
    # Configurable bucket boundaries [0.0–1.0].
    # LOW < medium_threshold <= MEDIUM < high_threshold <= HIGH
    medium_threshold: float = 0.35
    high_threshold: float = 0.65

    # --- Confidence floor ---
    # If overall confidence is below this, downgrade risk level one tier.
    confidence_floor: float = 0.40

    def __post_init__(self) -> None:
        total = sum(self.dimension_weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"RiskEngineConfig dimension_weights must sum to 1.0, got {total:.4f}. "
                "Adjust weights before instantiating the engine."
            )

    @classmethod
    def default(cls) -> "RiskEngineConfig":
        return cls()

    def classify_risk_level(self, score: float) -> str:
        """Map a [0,1] score to a risk level string using configured thresholds."""
        if score >= self.high_threshold:
            return "HIGH"
        elif score >= self.medium_threshold:
            return "MEDIUM"
        return "LOW"
