from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import uuid

from app.schemas.deep_analysis import (
    AnalysisEvidenceDTO,
    AnalysisFindingDTO,
    ModuleResultDTO,
)
from app.schemas.intelligence import CanonicalStructuredProduct


class BaseAnalysisModule(ABC):
    """
    Abstract base class for deep regulatory analysis modules.
    Every module analyzes structured intelligence and raw evidence,
    returning structured findings, evidence items, and severity suggestions.
    """

    @property
    @abstractmethod
    def module_name(self) -> str:
        """Identifier of the analysis module."""
        pass

    @abstractmethod
    def analyze(
        self,
        case_id: uuid.UUID,
        structured_data: CanonicalStructuredProduct,
        raw_sources: Optional[List[Any]] = None,
        ocr_records: Optional[List[Any]] = None,
    ) -> ModuleResultDTO:
        """
        Execute analytical logic for this domain.
        Returns a strongly-typed ModuleResultDTO with findings and evidence.
        """
        pass

    @classmethod
    def create_finding(
        cls,
        title: str,
        description: str,
        severity: str,
        confidence: float,
        source: str,
        rule_code: Optional[str] = None,
        statutory_ref: Optional[str] = None,
        discrepancy: Optional[Dict[str, Any]] = None,
        evidence: Optional[List[AnalysisEvidenceDTO]] = None,
    ) -> AnalysisFindingDTO:
        """Helper to construct a standard AnalysisFindingDTO."""
        return AnalysisFindingDTO(
            id=uuid.uuid4(),
            finding_title=title,
            description=description,
            severity=severity,
            confidence=round(confidence, 2),
            source=source,
            rule_code=rule_code,
            statutory_reference=statutory_ref,
            discrepancy_details=discrepancy,
            evidence_items=evidence or [],
        )
