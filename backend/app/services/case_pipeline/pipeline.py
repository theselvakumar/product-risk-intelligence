import logging
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AnalysisResult, Evidence, Finding, RiskAssessment
from app.models.case import AuditLog, Case
from app.models.product import ExtractedInformation, Product, ProductImage, ProductSource
from app.schemas.case_pipeline import CasePipelineResult
from app.services.analysis.orchestrator import DeepAnalysisOrchestrator
from app.services.consistency.service import ConsistencyAnalysisService
from app.services.intelligence.service import ProductIntelligenceService
from app.services.ocr.service import OCRService
from app.services.risk_engine.service import RiskIntelligenceService
from app.services.web_intelligence import WebIntelligenceOrchestrator, WebIntelligenceSummary

logger = logging.getLogger(__name__)


class CasePipelineService:
    """
    Orchestrates the end-to-end statutory compliance analysis pipeline:
    SUBMITTED -> EXTRACTING (OCR) -> STRUCTURING -> ANALYZING (Deep Analysis + Consistency)
    -> RISK_ASSESSMENT -> ANALYSIS_COMPLETE.

    Features:
    - Idempotent execution (safe to rerun without duplicating findings or scores)
    - Resilient error handling (isolated non-fatal module failures with error capture)
    - Full transaction & audit trail integrity
    """

    VERSION = "v1.0-DRISHTI-Pipeline"

    @classmethod
    async def cleanup_prior_analysis_run(
        cls,
        case_id: uuid.UUID,
        product_id: uuid.UUID,
        db: AsyncSession,
    ) -> None:
        """
        Removes previous derived analysis records (AnalysisResults, Findings,
        Evidence, RiskAssessments, and Canonical Structured Data) to ensure idempotency.
        Does NOT remove primary sources, images, or raw OCR extractions.
        """
        # 1. Delete prior risk assessments for this case
        await db.execute(
            delete(RiskAssessment).where(RiskAssessment.case_id == case_id)
        )

        # 2. Find and delete prior AnalysisResults, Findings, and Evidence
        ar_stmt = select(AnalysisResult.id).where(
            AnalysisResult.product_id == product_id,
            AnalysisResult.analysis_type.in_(["DEEP_PRODUCT_ANALYSIS", "CROSS_SOURCE_CONSISTENCY"]),
        )
        prior_ar_ids = (await db.execute(ar_stmt)).scalars().all()

        if prior_ar_ids:
            # Find associated findings
            f_stmt = select(Finding.id).where(Finding.analysis_result_id.in_(prior_ar_ids))
            prior_finding_ids = (await db.execute(f_stmt)).scalars().all()

            if prior_finding_ids:
                # Delete evidence linked to findings
                await db.execute(
                    delete(Evidence).where(Evidence.finding_id.in_(prior_finding_ids))
                )
                # Delete findings
                await db.execute(
                    delete(Finding).where(Finding.id.in_(prior_finding_ids))
                )

            # Delete analysis results
            await db.execute(
                delete(AnalysisResult).where(AnalysisResult.id.in_(prior_ar_ids))
            )

        # 3. Clean up prior synthesized canonical structured records
        await db.execute(
            delete(ExtractedInformation).where(
                ExtractedInformation.product_id == product_id,
                ExtractedInformation.zone_type == "CANONICAL_STRUCTURED_DATA",
            )
        )

        # 4. Clean up prior dynamically discovered web search sources and web extracted text
        await db.execute(
            delete(ProductSource).where(
                ProductSource.product_id == product_id,
                ProductSource.source_type.in_(["WEB_SEARCH", "WEB_SCRAPED"]),
            )
        )
        await db.execute(
            delete(ExtractedInformation).where(
                ExtractedInformation.product_id == product_id,
                ExtractedInformation.zone_type.in_(["WEB_PAGE_TEXT", "WEB_METADATA"]),
            )
        )
        await db.commit()

    @classmethod
    async def run_pipeline(
        cls,
        case_id: uuid.UUID,
        db: AsyncSession,
        current_user_id: Optional[uuid.UUID] = None,
    ) -> CasePipelineResult:
        start_time = time.perf_counter()
        now = datetime.now(timezone.utc)
        errors: List[str] = []

        # -------------------------------------------------------------------
        # Step 0: Resolve Case & Product
        # -------------------------------------------------------------------
        case_stmt = select(Case).where(Case.id == case_id)
        case_obj = (await db.execute(case_stmt)).scalar_one_or_none()
        if not case_obj:
            raise ValueError(f"Case with ID '{case_id}' not found.")

        prod_stmt = select(Product).where(Product.id == case_obj.product_id)
        prod_obj = (await db.execute(prod_stmt)).scalar_one_or_none()
        if not prod_obj:
            raise ValueError(f"Product '{case_obj.product_id}' not found for case '{case_id}'.")

        previous_status = case_obj.status

        # Ensure idempotency by purging stale prior runs
        await cls.cleanup_prior_analysis_run(
            case_id=case_id,
            product_id=prod_obj.id,
            db=db,
        )

        ocr_processed = False
        images_processed = 0
        intelligence_completed = False
        deep_analysis_completed = False
        consistency_completed = False
        risk_assessment_completed = False
        total_findings = 0
        risk_score: Optional[float] = None
        risk_level: Optional[str] = None
        confidence_score: Optional[float] = None

        # -------------------------------------------------------------------
        # Step 0b: WEB INTELLIGENCE — Product URL & Targeted Public Search
        # -------------------------------------------------------------------
        web_intel_summary = WebIntelligenceSummary()
        try:
            web_intel_summary = await WebIntelligenceOrchestrator.collect_case_web_intelligence(
                case_id=case_id,
                product_id=prod_obj.id,
                db=db,
                current_user_id=current_user_id,
            )
            if web_intel_summary.web_collection_errors:
                errors.extend(web_intel_summary.web_collection_errors)
        except Exception as web_err:
            logger.warning("Web intelligence collection non-fatal error for case '%s': %s", case_id, web_err)
            errors.append(f"Web intelligence non-fatal error: {web_err}")

        # -------------------------------------------------------------------
        # Step 1: EXTRACTING — Process Product Images via OCR
        # -------------------------------------------------------------------
        try:
            case_obj.status = "EXTRACTING"
            await db.commit()

            # Query all stored images for this product
            img_stmt = select(ProductImage).where(ProductImage.product_id == prod_obj.id)
            product_images = (await db.execute(img_stmt)).scalars().all()

            for img in product_images:
                # Check if this image already has an OCR extraction
                existing_ocr_stmt = select(ExtractedInformation).where(
                    ExtractedInformation.product_id == prod_obj.id,
                    ExtractedInformation.image_id == img.id,
                    ExtractedInformation.zone_type == "OCR_FULL_TEXT",
                )
                existing_ocr = (await db.execute(existing_ocr_stmt)).scalar_one_or_none()

                if existing_ocr:
                    images_processed += 1
                    ocr_processed = True
                    continue

                try:
                    await OCRService.process_case_image(
                        case_id=case_id,
                        image_id=img.id,
                        db=db,
                        current_user_id=current_user_id,
                    )
                    images_processed += 1
                    ocr_processed = True
                except Exception as ocr_err:
                    logger.warning(
                        "OCR extraction failed for image '%s' in case '%s': %s",
                        img.id,
                        case_id,
                        ocr_err,
                    )
                    errors.append(f"OCR failed for image {img.id}: {ocr_err}")

        except Exception as step1_err:
            logger.error("Extracting step failed for case '%s': %s", case_id, step1_err)
            errors.append(f"Extracting phase error: {step1_err}")

        # -------------------------------------------------------------------
        # Step 2: STRUCTURING — Structure Product Intelligence
        # -------------------------------------------------------------------
        try:
            case_obj.status = "STRUCTURING"
            await db.commit()

            await ProductIntelligenceService.structure_case_information(
                case_id=case_id,
                db=db,
                current_user_id=current_user_id,
            )
            intelligence_completed = True
        except Exception as step2_err:
            logger.error("Structuring step failed for case '%s': %s", case_id, step2_err)
            errors.append(f"Structuring phase error: {step2_err}")

        # -------------------------------------------------------------------
        # Step 3: ANALYZING — Deep Modular Analysis & Consistency Analysis
        # -------------------------------------------------------------------
        try:
            case_obj.status = "ANALYZING"
            await db.commit()

            # A. Deep Regulatory Analysis
            try:
                deep_res = await DeepAnalysisOrchestrator.run_analysis(
                    case_id=case_id,
                    db=db,
                    current_user_id=current_user_id,
                )
                deep_analysis_completed = True
                total_findings += deep_res.total_findings
            except Exception as deep_err:
                logger.error("Deep analysis failed for case '%s': %s", case_id, deep_err)
                errors.append(f"Deep analysis error: {deep_err}")

            # B. Cross-Source Consistency Analysis
            try:
                cons_res = await ConsistencyAnalysisService.run_consistency_check(
                    case_id=case_id,
                    db=db,
                    current_user_id=current_user_id,
                )
                consistency_completed = True
                total_findings += (cons_res.inconsistency_count + cons_res.minor_difference_count)
            except Exception as cons_err:
                logger.error("Consistency analysis failed for case '%s': %s", case_id, cons_err)
                errors.append(f"Consistency analysis error: {cons_err}")

        except Exception as step3_err:
            logger.error("Analyzing step failed for case '%s': %s", case_id, step3_err)
            errors.append(f"Analyzing phase error: {step3_err}")

        # -------------------------------------------------------------------
        # Step 4: RISK_ASSESSMENT — Compute Risk Intelligence Score
        # -------------------------------------------------------------------
        try:
            case_obj.status = "RISK_ASSESSMENT"
            await db.commit()

            risk_report = await RiskIntelligenceService.compute_risk(
                case_id=case_id,
                db=db,
                current_user_id=current_user_id,
            )
            risk_assessment_completed = True
            risk_score = risk_report.risk_score
            risk_level = risk_report.risk_level
            confidence_score = risk_report.confidence_score

            # ---------------------------------------------------------------
            # Step 5: Final Status — ANALYSIS_COMPLETE
            # ---------------------------------------------------------------
            case_obj.status = "ANALYSIS_COMPLETE"
            await db.commit()
            await db.refresh(case_obj)

        except Exception as step4_err:
            logger.error("Risk assessment failed for case '%s': %s", case_id, step4_err)
            errors.append(f"Risk assessment error: {step4_err}")
            # Case must NOT be marked ANALYSIS_COMPLETE on risk calculation failure
            case_obj.status = "ANALYSIS_FAILED"
            await db.commit()
            await db.refresh(case_obj)

        # Record Pipeline Completion Audit Log
        pipeline_audit = AuditLog(
            case_id=case_id,
            user_id=current_user_id,
            action="PIPELINE_ANALYSIS_EXECUTED" if risk_assessment_completed else "PIPELINE_ANALYSIS_FAILED",
            entity_type="Case",
            entity_id=str(case_id),
            details_json={
                "previous_status": previous_status,
                "final_status": case_obj.status,
                "priority": case_obj.priority,
                "ocr_processed": ocr_processed,
                "images_processed": images_processed,
                "intelligence_completed": intelligence_completed,
                "deep_analysis_completed": deep_analysis_completed,
                "consistency_completed": consistency_completed,
                "risk_assessment_completed": risk_assessment_completed,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "web_sources_found": web_intel_summary.web_sources_found,
                "web_sources_processed": web_intel_summary.web_sources_processed,
                "web_collection_success": web_intel_summary.web_collection_success,
                "errors": errors,
            },
            created_at=datetime.now(timezone.utc),
        )
        db.add(pipeline_audit)
        await db.commit()

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return CasePipelineResult(
            case_id=case_id,
            case_number=case_obj.case_number,
            product_id=prod_obj.id,
            status=case_obj.status,
            previous_status=previous_status,
            priority=case_obj.priority,
            ocr_processed=ocr_processed,
            images_processed=images_processed,
            intelligence_completed=intelligence_completed,
            deep_analysis_completed=deep_analysis_completed,
            consistency_completed=consistency_completed,
            risk_assessment_completed=risk_assessment_completed,
            risk_score=risk_score,
            risk_level=risk_level,
            confidence_score=confidence_score,
            total_findings=total_findings,
            web_collection_attempted=web_intel_summary.web_collection_attempted,
            web_sources_found=web_intel_summary.web_sources_found,
            web_sources_processed=web_intel_summary.web_sources_processed,
            web_collection_success=web_intel_summary.web_collection_success,
            web_collection_errors=web_intel_summary.web_collection_errors,
            errors=errors,
            execution_timestamp=now,
            execution_duration_ms=duration_ms,
        )
