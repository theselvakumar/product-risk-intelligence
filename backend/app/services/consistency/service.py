import uuid
from datetime import datetime, timezone
from itertools import combinations
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AnalysisResult, Finding
from app.models.case import AuditLog, Case
from app.models.product import ExtractedInformation, Product, ProductSource
from app.schemas.consistency import (
    ConsistencyReport,
    FieldComparisonRecord,
    SourceFieldEvidence,
)
from app.services.consistency.field_extractor import FieldExtractor
from app.services.consistency.matcher import ConsistencyMatcher


class ConsistencyAnalysisService:
    """
    Cross-source information consistency engine.
    Compares product information across all available evidence streams,
    identifying inconsistencies with verbatim evidence from both sources.
    """

    VERSION = "v1.0-DRISHTI-Consistency"

    @classmethod
    async def run_consistency_check(
        cls,
        case_id: uuid.UUID,
        db: AsyncSession,
        current_user_id: Optional[uuid.UUID] = None,
    ) -> ConsistencyReport:
        now = datetime.now(timezone.utc)

        # 1. Fetch Case & Product
        case_stmt = select(Case).where(Case.id == case_id)
        case_obj = (await db.execute(case_stmt)).scalar_one_or_none()
        if not case_obj:
            raise ValueError(f"Case '{case_id}' not found.")

        prod_stmt = select(Product).where(Product.id == case_obj.product_id)
        prod_obj = (await db.execute(prod_stmt)).scalar_one_or_none()
        if not prod_obj:
            raise ValueError(f"Product '{case_obj.product_id}' not found.")

        # 2. Collect all source field maps
        source_field_maps: List[Dict[str, SourceFieldEvidence]] = []

        # Manual Input (canonical product object)
        manual_fields = FieldExtractor.extract_from_product_object(prod_obj)
        if manual_fields:
            source_field_maps.append(manual_fields)

        # ProductSource records (URLs, descriptions)
        src_stmt = select(ProductSource).where(ProductSource.product_id == prod_obj.id)
        sources = (await db.execute(src_stmt)).scalars().all()
        for src in sources:
            fields = FieldExtractor.extract_from_source_record(src)
            if fields:
                source_field_maps.append(fields)

        # OCR records
        ocr_stmt = select(ExtractedInformation).where(
            ExtractedInformation.product_id == prod_obj.id,
            ExtractedInformation.zone_type == "OCR_FULL_TEXT",
        )
        ocr_records = (await db.execute(ocr_stmt)).scalars().all()
        for ocr in ocr_records:
            if ocr.raw_text:
                fields = FieldExtractor.extract_from_ocr_text(ocr.raw_text, str(ocr.id))
                if fields:
                    source_field_maps.append(fields)

        # 3. Pairwise comparison across all source pairs for each field
        comparisons: List[FieldComparisonRecord] = []
        fields_to_compare = ["product_name", "manufacturer", "ingredients", "claims", "license_number"]

        for field_name in fields_to_compare:
            # Gather all sources that have a value for this field
            field_sources: List[SourceFieldEvidence] = []
            for sm in source_field_maps:
                if field_name in sm:
                    field_sources.append(sm[field_name])

            # If only one or zero sources have the field, note it as MISSING_IN_SOURCE vs the product baseline
            if len(field_sources) == 0:
                continue  # No data at all for this field across any source

            if len(field_sources) == 1:
                # Only one source has data — flag it as missing in other source
                ev = field_sources[0]
                # Create a "phantom" missing source to represent absent data
                missing_ev = SourceFieldEvidence(
                    source_type="OTHER_SOURCES",
                    raw_text="",
                    normalized_value="",
                )
                result, method, diff, sim, conf = ConsistencyMatcher.compare(
                    ev.raw_text, "", field_name=field_name
                )
                severity = ConsistencyMatcher.severity_for_result(result, field_name)
                comparisons.append(
                    FieldComparisonRecord(
                        field_name=field_name,
                        source_a=ev,
                        source_b=missing_ev,
                        comparison_result=result,
                        severity_suggestion=severity,
                        confidence=conf,
                        match_method=method,
                        similarity_score=sim,
                        detected_difference=diff,
                    )
                )
                continue

            # Pairwise comparisons for all source pairs
            for ev_a, ev_b in combinations(field_sources, 2):
                # Skip if same source type (same ocr session, etc.)
                if ev_a.source_type == ev_b.source_type and ev_a.source_id == ev_b.source_id:
                    continue

                result, method, diff, sim, conf = ConsistencyMatcher.compare(
                    ev_a.raw_text, ev_b.raw_text, field_name=field_name
                )
                severity = ConsistencyMatcher.severity_for_result(result, field_name)

                comparisons.append(
                    FieldComparisonRecord(
                        field_name=field_name,
                        source_a=ev_a,
                        source_b=ev_b,
                        comparison_result=result,
                        severity_suggestion=severity,
                        confidence=conf,
                        match_method=method,
                        similarity_score=sim,
                        detected_difference=diff,
                    )
                )

        # 4. Build summary stats
        result_counts = {
            "CONSISTENT": 0,
            "MINOR_WORDING_DIFFERENCE": 0,
            "INCONSISTENT": 0,
            "MISSING_IN_SOURCE": 0,
        }
        for c in comparisons:
            result_counts[c.comparison_result] = result_counts.get(c.comparison_result, 0) + 1

        severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
        all_severities = [c.severity_suggestion for c in comparisons]
        highest_severity = "INFO"
        for sev in severity_order:
            if sev in all_severities:
                highest_severity = sev
                break

        # 5. Persist into analysis_results & findings
        analysis_id = uuid.uuid4()
        analysis_rec = AnalysisResult(
            id=analysis_id,
            product_id=prod_obj.id,
            analysis_type="CROSS_SOURCE_CONSISTENCY",
            status="COMPLETED",
            total_checks=len(comparisons),
            violations_found=result_counts.get("INCONSISTENT", 0) + result_counts.get("MISSING_IN_SOURCE", 0),
            summary=(
                f"Cross-source consistency check complete. "
                f"Inconsistencies: {result_counts['INCONSISTENT']}, "
                f"Minor differences: {result_counts['MINOR_WORDING_DIFFERENCE']}, "
                f"Consistent: {result_counts['CONSISTENT']}."
            ),
            execution_metadata={
                "orchestrator_version": cls.VERSION,
                "case_id": str(case_id),
                "total_sources_analyzed": len(source_field_maps),
                "highest_severity": highest_severity,
            },
            created_at=now,
        )
        db.add(analysis_rec)

        for comp in comparisons:
            if comp.comparison_result in ("INCONSISTENT", "MINOR_WORDING_DIFFERENCE"):
                db_finding = Finding(
                    id=comp.id,
                    analysis_result_id=analysis_id,
                    finding_title=f"Cross-source {comp.comparison_result.lower().replace('_', ' ')}: {comp.field_name}",
                    description=comp.detected_difference,
                    severity=comp.severity_suggestion,
                    confidence=comp.confidence,
                    source="CROSS_SOURCE_COMPARISON",
                    rule_code=f"CONSISTENCY-{comp.field_name.upper()}-{comp.comparison_result}",
                    discrepancy_details={
                        "field": comp.field_name,
                        "source_a_type": comp.source_a.source_type,
                        "source_a_value": comp.source_a.raw_text[:200],
                        "source_b_type": comp.source_b.source_type,
                        "source_b_value": comp.source_b.raw_text[:200],
                        "similarity_score": comp.similarity_score,
                        "match_method": comp.match_method,
                    },
                    created_at=now,
                )
                db.add(db_finding)

        audit = AuditLog(
            case_id=case_id,
            user_id=current_user_id,
            action="CONSISTENCY_CHECK_COMPLETED",
            entity_type="AnalysisResult",
            entity_id=str(analysis_id),
            details_json={
                "inconsistencies": result_counts["INCONSISTENT"],
                "minor_differences": result_counts["MINOR_WORDING_DIFFERENCE"],
                "consistent": result_counts["CONSISTENT"],
                "highest_severity": highest_severity,
            },
            created_at=now,
        )
        db.add(audit)
        await db.commit()

        return ConsistencyReport(
            case_id=case_id,
            product_id=prod_obj.id,
            case_number=case_obj.case_number,
            comparisons=comparisons,
            summary_stats=result_counts,
            total_sources_analyzed=len(source_field_maps),
            total_fields_compared=len(fields_to_compare),
            inconsistency_count=result_counts.get("INCONSISTENT", 0),
            minor_difference_count=result_counts.get("MINOR_WORDING_DIFFERENCE", 0),
            consistent_count=result_counts.get("CONSISTENT", 0),
            missing_in_source_count=result_counts.get("MISSING_IN_SOURCE", 0),
            highest_severity=highest_severity,
            execution_timestamp=now,
        )
