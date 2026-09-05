import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AnalysisResult, Evidence, Finding, RiskAssessment
from app.models.case import Case
from app.models.product import Product
from app.schemas.explanation import (
    EvidenceItem,
    ExplanationReport,
    FindingExplanation,
    ProductSummary,
    RiskScoreExplanation,
)
from app.services.risk_engine.config import LEGAL_DISCLAIMER


_SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]

_REASON_TEMPLATES: Dict[str, str] = {
    "LICENSE": "License information requires verification: {title}",
    "INGREDIENT": "Ingredient-related concern identified: {title}",
    "CLAIM": "Claim requires review: {title}",
    "PACKAGING": "Packaging compliance concern: {title}",
    "MANUFACTURER": "Manufacturer information concern: {title}",
    "CONSISTENCY": "Cross-source information inconsistency detected: {title}",
    "CROSS_SOURCE": "Cross-source information inconsistency detected: {title}",
}


def _build_reason(rule_code: Optional[str], title: str) -> str:
    if rule_code:
        prefix = rule_code.split("-")[0].upper()
        template = _REASON_TEMPLATES.get(prefix)
        if template:
            return template.format(title=title)
    return f"Flagged for review: {title}"


class ExplainabilityService:
    """
    Builds a fully traceable ExplanationReport for a case.

    Design contract:
    - Every FindingExplanation references only stored records (Finding, Evidence tables).
    - No inference is introduced. Evidence.raw_text is quoted verbatim.
    - Risk explanation is drawn from the stored RiskAssessment.score_breakdown.
    """

    @classmethod
    async def explain_case(
        cls,
        case_id: uuid.UUID,
        db: AsyncSession,
    ) -> ExplanationReport:
        now = datetime.now(timezone.utc)

        # 1. Load case
        case_stmt = select(Case).where(Case.id == case_id)
        case_obj = (await db.execute(case_stmt)).scalar_one_or_none()
        if not case_obj:
            raise ValueError(f"Case '{case_id}' not found.")

        # 2. Load product
        prod_stmt = select(Product).where(Product.id == case_obj.product_id)
        prod_obj = (await db.execute(prod_stmt)).scalar_one_or_none()
        if not prod_obj:
            raise ValueError(f"Product '{case_obj.product_id}' not found.")

        product_summary = ProductSummary(
            product_id=prod_obj.id,
            product_name=prod_obj.product_name,
            brand=prod_obj.brand,
            category=prod_obj.category,
            manufacturer=prod_obj.manufacturer,
            fssai_license_number=prod_obj.fssai_license_number,
        )

        # 3. Load all AnalysisResults for this product
        ar_stmt = select(AnalysisResult).where(AnalysisResult.product_id == prod_obj.id)
        analysis_results = (await db.execute(ar_stmt)).scalars().all()

        # 4. Load all Findings for all AnalysisResults + their Evidence
        finding_explanations: List[FindingExplanation] = []
        severity_counts: Dict[str, int] = {}

        for ar in analysis_results:
            f_stmt = select(Finding).where(Finding.analysis_result_id == ar.id)
            findings = (await db.execute(f_stmt)).scalars().all()

            for f in findings:
                # Load evidence items for this finding
                ev_stmt = select(Evidence).where(Evidence.finding_id == f.id)
                evidence_records = (await db.execute(ev_stmt)).scalars().all()

                evidence_items: List[EvidenceItem] = []
                for ev in evidence_records:
                    evidence_items.append(EvidenceItem(
                        evidence_type=ev.evidence_type or "UNKNOWN",
                        raw_text=ev.caption or ev.storage_uri or "",
                        source_type=ar.analysis_type,
                        source_reference=ev.storage_uri,
                    ))

                # Also surface discrepancy_details as inline evidence
                disc = f.discrepancy_details or {}
                if disc and not evidence_items:
                    src_a_val = disc.get("source_a_value", "")
                    src_b_val = disc.get("source_b_value", "")
                    if src_a_val:
                        evidence_items.append(EvidenceItem(
                            evidence_type="SOURCE_A_VERBATIM",
                            raw_text=src_a_val,
                            source_type=disc.get("source_a_type", ar.analysis_type),
                        ))
                    if src_b_val:
                        evidence_items.append(EvidenceItem(
                            evidence_type="SOURCE_B_VERBATIM",
                            raw_text=src_b_val,
                            source_type=disc.get("source_b_type", ar.analysis_type),
                        ))

                reason = _build_reason(f.rule_code, f.finding_title)

                finding_explanations.append(FindingExplanation(
                    finding_id=f.id,
                    finding_title=f.finding_title,
                    description=f.description,
                    severity=f.severity,
                    source=f.source or ar.analysis_type,
                    confidence=float(f.confidence or 0.5),
                    rule_code=f.rule_code,
                    statutory_reference=f.statutory_reference,
                    reason_for_flagging=reason,
                    evidence=evidence_items,
                    discrepancy_details=disc if disc else None,
                ))

                sev = f.severity or "INFO"
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # 5. Sort findings: CRITICAL first → INFO last
        finding_explanations.sort(
            key=lambda fe: _SEVERITY_ORDER.index(fe.severity) if fe.severity in _SEVERITY_ORDER else 99
        )

        # 6. Load latest RiskAssessment
        risk_stmt = (
            select(RiskAssessment)
            .where(RiskAssessment.case_id == case_id)
            .order_by(RiskAssessment.created_at.desc())
        )
        risk_rec = (await db.execute(risk_stmt)).scalar_one_or_none()

        risk_explanation: Optional[RiskScoreExplanation] = None
        if risk_rec:
            breakdown = risk_rec.score_breakdown or {}
            risk_explanation = RiskScoreExplanation(
                risk_score=float(risk_rec.risk_score),
                risk_level=risk_rec.risk_level,
                confidence_score=float(risk_rec.confidence_score),
                score_explanation=breakdown.get("score_explanation", ""),
                contributing_factors=breakdown.get("contributing_factors", []),
                data_completeness_ratio=breakdown.get("data_completeness_ratio", 0.0),
                disclaimer=LEGAL_DISCLAIMER,
            )

        # 7. Build "Why This Case Was Flagged" list (top findings, severity-ordered)
        why_flagged: List[str] = []
        seen_reasons = set()
        for fe in finding_explanations:
            if fe.severity in ("CRITICAL", "HIGH", "MEDIUM") and fe.reason_for_flagging not in seen_reasons:
                why_flagged.append(fe.reason_for_flagging)
                seen_reasons.add(fe.reason_for_flagging)
            if len(why_flagged) >= 8:
                break

        return ExplanationReport(
            case_id=case_id,
            case_number=case_obj.case_number,
            product=product_summary,
            total_findings=len(finding_explanations),
            findings_by_severity=severity_counts,
            findings=finding_explanations,
            risk_assessment=risk_explanation,
            why_flagged_summary=why_flagged,
            generated_at=now,
        )
