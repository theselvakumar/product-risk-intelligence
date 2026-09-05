from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AnalysisResult, Evidence, Finding
from app.models.case import AuditLog, Case
from app.models.product import ExtractedInformation, Product, ProductSource
from app.schemas.deep_analysis import (
    AnalysisFindingDTO,
    DeepAnalysisReportResponse,
    ModuleResultDTO,
)
from app.schemas.intelligence import CanonicalStructuredProduct
from app.services.analysis.claim_analyzer import ClaimAnalyzer
from app.services.analysis.ingredient_analyzer import IngredientAnalyzer
from app.services.analysis.license_analyzer import LicenseAnalyzer
from app.services.analysis.manufacturer_analyzer import ManufacturerAnalyzer
from app.services.analysis.packaging_analyzer import PackagingAnalyzer
from app.services.intelligence.service import ProductIntelligenceService


class DeepAnalysisOrchestrator:
    """
    Coordinates modular regulatory analysis across all five dimensions:
    License, Ingredient, Claim, Packaging, and Manufacturer Analysis.
    Persists findings and evidence into statutory database tables.
    """

    VERSION = "v1.0-DRISHTI-DeepAnalysis"

    @classmethod
    async def run_analysis(
        cls,
        case_id: uuid.UUID,
        db: AsyncSession,
        current_user_id: Optional[uuid.UUID] = None,
    ) -> DeepAnalysisReportResponse:
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

        # 2. Get Structured Intelligence (run on-demand if needed)
        structured_data = await ProductIntelligenceService.structure_case_information(
            case_id=case_id,
            db=db,
            current_user_id=current_user_id,
        )

        # 3. Fetch raw sources & OCR records
        src_stmt = select(ProductSource).where(ProductSource.product_id == prod_obj.id)
        sources = (await db.execute(src_stmt)).scalars().all()

        ocr_stmt = select(ExtractedInformation).where(
            ExtractedInformation.product_id == prod_obj.id,
            ExtractedInformation.zone_type == "OCR_FULL_TEXT",
        )
        ocr_records = (await db.execute(ocr_stmt)).scalars().all()

        # 4. Instantiate modules
        modules = [
            LicenseAnalyzer(),
            IngredientAnalyzer(),
            ClaimAnalyzer(),
            PackagingAnalyzer(),
            ManufacturerAnalyzer(),
        ]

        module_results: Dict[str, ModuleResultDTO] = {}
        all_findings: List[AnalysisFindingDTO] = []

        for m in modules:
            res = m.analyze(
                case_id=case_id,
                structured_data=structured_data,
                raw_sources=sources,
                ocr_records=ocr_records,
            )
            module_results[m.module_name] = res
            all_findings.extend(res.findings)

        # Calculate counts
        critical_count = sum(1 for f in all_findings if f.severity == "CRITICAL")
        high_count = sum(1 for f in all_findings if f.severity == "HIGH")
        medium_count = sum(1 for f in all_findings if f.severity == "MEDIUM")
        low_count = sum(1 for f in all_findings if f.severity == "LOW")
        info_count = sum(1 for f in all_findings if f.severity == "INFO")

        # 5. Persist into analysis_results and findings tables
        analysis_run_id = uuid.uuid4()
        analysis_record = AnalysisResult(
            id=analysis_run_id,
            product_id=prod_obj.id,
            analysis_type="DEEP_PRODUCT_ANALYSIS",
            status="COMPLETED",
            total_checks=len(all_findings),
            violations_found=critical_count + high_count,
            summary=(
                f"Deep modular analysis completed across 5 domains. "
                f"Total findings: {len(all_findings)} (Critical: {critical_count}, High: {high_count}, Medium: {medium_count})."
            ),
            execution_metadata={
                "orchestrator_version": cls.VERSION,
                "case_id": str(case_id),
                "case_number": case_obj.case_number,
                "module_severities": {name: res.severity_suggestion for name, res in module_results.items()},
            },
            created_at=now,
        )
        db.add(analysis_record)

        # Persist discrete findings
        for f_dto in all_findings:
            db_finding = Finding(
                id=f_dto.id,
                analysis_result_id=analysis_run_id,
                finding_title=f_dto.finding_title,
                description=f_dto.description,
                severity=f_dto.severity,
                confidence=f_dto.confidence,
                source=f_dto.source,
                statutory_reference=f_dto.statutory_reference,
                rule_code=f_dto.rule_code,
                discrepancy_details=f_dto.discrepancy_details,
                created_at=now,
            )
            db.add(db_finding)

            for ev_dto in f_dto.evidence_items:
                db_ev = Evidence(
                    id=uuid.uuid4(),
                    finding_id=db_finding.id,
                    evidence_type=ev_dto.evidence_type,
                    storage_uri="text://in-memory-corpus",
                    sha256_hash="0" * 64,
                    caption=ev_dto.caption,
                    mime_type="text/plain",
                    metadata_json={
                        "snippet": ev_dto.text_snippet,
                        "source": ev_dto.source_reference,
                    },
                    created_at=now,
                )
                db.add(db_ev)

        # Statutory Audit Log
        audit = AuditLog(
            case_id=case_id,
            user_id=current_user_id,
            action="DEEP_ANALYSIS_COMPLETED",
            entity_type="AnalysisResult",
            entity_id=str(analysis_run_id),
            details_json={
                "total_findings": len(all_findings),
                "critical": critical_count,
                "high": high_count,
                "medium": medium_count,
                "modules": list(module_results.keys()),
            },
            created_at=now,
        )
        db.add(audit)
        await db.commit()

        return DeepAnalysisReportResponse(
            case_id=case_id,
            product_id=prod_obj.id,
            case_number=case_obj.case_number,
            total_checks=len(all_findings),
            total_findings=len(all_findings),
            critical_findings_count=critical_count,
            high_findings_count=high_count,
            medium_findings_count=medium_count,
            low_findings_count=low_count,
            info_findings_count=info_count,
            modules=module_results,
            execution_timestamp=now,
            orchestrator_version=cls.VERSION,
        )
