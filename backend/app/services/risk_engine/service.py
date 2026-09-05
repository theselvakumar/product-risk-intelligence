import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import RiskAssessment
from app.models.case import AuditLog, Case
from app.models.product import Product
from app.schemas.risk import ContributingFactorSchema, RiskAssessmentReport
from app.services.risk_engine.aggregator import FindingAggregator
from app.services.risk_engine.config import LEGAL_DISCLAIMER, RiskEngineConfig
from app.services.risk_engine.scorer import RiskScorer


class RiskIntelligenceService:
    """
    Orchestrates the full Risk Intelligence pipeline:
    FindingAggregator → RiskScorer → Persist → AuditLog → RiskAssessmentReport.
    """

    VERSION = "v1.0-DRISHTI-RiskEngine"

    @classmethod
    async def compute_risk(
        cls,
        case_id: uuid.UUID,
        db: AsyncSession,
        current_user_id: Optional[uuid.UUID] = None,
        config: Optional[RiskEngineConfig] = None,
    ) -> RiskAssessmentReport:
        now = datetime.now(timezone.utc)
        cfg = config or RiskEngineConfig.default()

        # 1. Resolve case & product
        case_stmt = select(Case).where(Case.id == case_id)
        case_obj = (await db.execute(case_stmt)).scalar_one_or_none()
        if not case_obj:
            raise ValueError(f"Case '{case_id}' not found.")

        prod_stmt = select(Product).where(Product.id == case_obj.product_id)
        prod_obj = (await db.execute(prod_stmt)).scalar_one_or_none()
        if not prod_obj:
            raise ValueError(f"Product '{case_obj.product_id}' not found.")

        # 2. Aggregate findings by dimension
        groups, data_completeness = await FindingAggregator.aggregate(
            product_id=prod_obj.id,
            db=db,
        )

        # 3. Score
        scorer = RiskScorer(config=cfg)
        result = scorer.compute(groups=groups, data_completeness=data_completeness)

        # 4. Persist RiskAssessment
        assessment_id = uuid.uuid4()
        assessment = RiskAssessment(
            id=assessment_id,
            product_id=prod_obj.id,
            case_id=case_id,
            risk_score=result.risk_score,
            risk_level=result.risk_level,
            confidence_score=result.confidence_score,
            score_breakdown={
                "contributing_factors": [
                    {
                        "dimension": f.dimension,
                        "finding_count": f.finding_count,
                        "max_severity": f.max_severity,
                        "raw_dimension_score": f.raw_dimension_score,
                        "weighted_contribution": f.weighted_contribution,
                        "confidence": f.confidence,
                    }
                    for f in result.contributing_factors
                ],
                "data_completeness_ratio": result.data_completeness_ratio,
                "total_findings_analyzed": result.total_findings_analyzed,
                "score_explanation": result.score_explanation,
                "engine_version": cls.VERSION,
                "disclaimer": LEGAL_DISCLAIMER,
            },
            created_at=now,
        )
        db.add(assessment)

        # 5. Statutory Triage Routing (Phase 14)
        # High and Critical risk cases automatically route to PRIORITY_REVIEW
        # Medium and Low risk cases route to STANDARD_REVIEW
        prev_status = case_obj.status
        has_critical = any(f.max_severity == "CRITICAL" for f in result.contributing_factors)
        has_high = any(f.max_severity == "HIGH" for f in result.contributing_factors)

        if has_critical or has_high or result.risk_level in ("HIGH", "CRITICAL") or result.risk_score >= 0.35:
            case_obj.status = "PRIORITY_REVIEW"
            case_obj.priority = "URGENT_P1" if (has_critical or result.risk_level == "CRITICAL") else "HIGH_P2"
        else:
            case_obj.status = "STANDARD_REVIEW"
            case_obj.priority = "ROUTINE_P3" if result.risk_level == "MEDIUM" else "MONITORING_P4"

        # 6. Audit logs (Assessment completed & statutory triage routing)
        audit = AuditLog(
            case_id=case_id,
            user_id=current_user_id,
            action="RISK_ASSESSMENT_COMPLETED",
            entity_type="RiskAssessment",
            entity_id=str(assessment_id),
            details_json={
                "risk_score": result.risk_score,
                "risk_level": result.risk_level,
                "confidence_score": result.confidence_score,
                "total_findings": result.total_findings_analyzed,
                "engine_version": cls.VERSION,
                "previous_status": prev_status,
                "routed_status": case_obj.status,
            },
            created_at=now,
        )
        db.add(audit)

        triage_audit = AuditLog(
            case_id=case_id,
            user_id=current_user_id,
            action="CASE_TRIAGED_ROUTING",
            entity_type="Case",
            entity_id=str(case_id),
            details_json={
                "previous_status": prev_status,
                "new_status": case_obj.status,
                "risk_level": result.risk_level,
                "risk_score": result.risk_score,
                "routing_reason": (
                    "Automatic priority escalation due to critical/high non-compliance risk"
                    if case_obj.status == "PRIORITY_REVIEW"
                    else "Standard surveillance review workflow assignment"
                ),
            },
            created_at=now,
        )
        db.add(triage_audit)

        await db.commit()

        # 6. Build report
        factor_schemas = [
            ContributingFactorSchema(
                dimension=f.dimension,
                finding_count=f.finding_count,
                max_severity=f.max_severity,
                weighted_contribution=f.weighted_contribution,
                raw_dimension_score=f.raw_dimension_score,
                confidence=f.confidence,
            )
            for f in result.contributing_factors
        ]

        return RiskAssessmentReport(
            case_id=case_id,
            product_id=prod_obj.id,
            case_number=case_obj.case_number,
            risk_score=result.risk_score,
            risk_level=result.risk_level,
            confidence_score=result.confidence_score,
            contributing_factors=factor_schemas,
            score_explanation=result.score_explanation,
            data_completeness_ratio=result.data_completeness_ratio,
            total_findings_analyzed=result.total_findings_analyzed,
            disclaimer=LEGAL_DISCLAIMER,
            engine_version=cls.VERSION,
            execution_timestamp=now,
        )
