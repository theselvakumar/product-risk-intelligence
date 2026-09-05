"""Report builder service for compiling structured CaseComplianceReportData."""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import RiskAssessment
from app.models.case import Case
from app.models.product import Product
from app.models.user import User
from app.schemas.evidence_package import CaseEvidencePackage
from app.schemas.report import (
    AnalysisLimitationsSection,
    CaseComplianceReportData,
    CaseInfoSection,
    DetectedFindingItem,
    DimensionBreakdownItem,
    EvidenceItem,
    ProductInfoSection,
    ReviewRecommendationSection,
    RiskAssessmentSection,
    SourceInfoSection,
    SubmittedImageItem,
)
from app.services.evidence.package_builder import EvidencePackageBuilder


class ComplianceReportBuilder:
    """Builds a comprehensive, evidence-backed compliance risk report from database models."""

    @classmethod
    async def build_report_data(
        cls,
        case_id: uuid.UUID,
        db: AsyncSession,
    ) -> CaseComplianceReportData:
        """Query database and assemble structured report data."""
        # 1. Fetch Case
        case_stmt = select(Case).where(Case.id == case_id)
        case_res = await db.execute(case_stmt)
        case_obj = case_res.scalar_one_or_none()
        if not case_obj:
            raise ValueError(f"Case with ID '{case_id}' not found")

        # 2. Build full evidence package using Phase 13 builder
        evidence_pkg: CaseEvidencePackage = await EvidencePackageBuilder.build(case_id=case_id, db=db)

        # 3. Fetch Assigned Officer if any
        assigned_officer_name = None
        if case_obj.assigned_user_id:
            u_stmt = select(User).where(User.id == case_obj.assigned_user_id)
            user_obj = (await db.execute(u_stmt)).scalar_one_or_none()
            if user_obj:
                badge = f" ({user_obj.badge_id})" if user_obj.badge_id else ""
                assigned_officer_name = f"{user_obj.full_name}{badge}"

        # 4. Fetch Latest Risk Assessment
        ra_stmt = (
            select(RiskAssessment)
            .where(RiskAssessment.case_id == case_id)
            .order_by(RiskAssessment.created_at.desc())
        )
        ra_res = await db.execute(ra_stmt)
        risk_assessment = ra_res.scalars().first()

        # Build Section 1: Case Info
        case_info = CaseInfoSection(
            case_id=str(case_obj.id),
            case_number=case_obj.case_number or f"CASE-{str(case_obj.id)[:8].upper()}",
            created_at=case_obj.created_at.isoformat() if case_obj.created_at else datetime.now(timezone.utc).isoformat(),
            status=case_obj.status or "SUBMITTED",
            priority=case_obj.priority or "ROUTINE_P3",
            assigned_officer=assigned_officer_name,
            jurisdiction="Central Territorial Jurisdiction (DL-CENTRAL)",
        )

        # 5. Fetch Product model directly if available
        product_model: Optional[Product] = None
        if case_obj.product_id:
            p_stmt = select(Product).where(Product.id == case_obj.product_id)
            product_model = (await db.execute(p_stmt)).scalar_one_or_none()

        submitted_desc = ""
        if evidence_pkg.submitted_text_evidence:
            submitted_desc = "\n".join(e.content_text or "" for e in evidence_pkg.submitted_text_evidence)
        if not submitted_desc:
            submitted_desc = case_obj.description or "No initial submission description provided."

        # Build Section 2: Product Info
        product_info = ProductInfoSection(
            product_name=evidence_pkg.product_name or (product_model.product_name if product_model else "Product Under Surveillance"),
            brand=evidence_pkg.brand or (product_model.brand if product_model else None),
            category=evidence_pkg.category or (product_model.category if product_model else None),
            manufacturer=(product_model.manufacturer if product_model and product_model.manufacturer else "Manufacturer details under FoSCoS verification"),
            fssai_license_number=(product_model.fssai_license_number if product_model else None),
        )

        # Extract FSSAI License & Manufacturer from extracted data or submitted text if available
        if not product_info.fssai_license_number:
            import re
            lic_match = re.search(r'\b(1\d{13})\b', submitted_desc)
            if lic_match:
                product_info.fssai_license_number = lic_match.group(1)
            else:
                for ext in evidence_pkg.extracted_data_evidence:
                    if ext.content_text:
                        ext_match = re.search(r'\b(1\d{13})\b', ext.content_text)
                        if ext_match:
                            product_info.fssai_license_number = ext_match.group(1)
                            break

        # Build Section 3: Source Info
        prod_url = None
        platform = None
        if evidence_pkg.url_evidence:
            first_url = evidence_pkg.url_evidence[0]
            prod_url = first_url.content_uri or first_url.content_text
            platform = first_url.metadata.get("platform_name") if first_url.metadata else "Digital Repository"

        submitted_images: List[SubmittedImageItem] = [
            SubmittedImageItem(
                image_id=str(img.record_id),
                image_type=img.metadata.get("image_type", "PACKAGING") if img.metadata else "PACKAGING",
                image_url=img.content_uri,
                sha256_hash=img.sha256_hash,
                file_name=(img.content_uri or "").split("/")[-1].split("\\")[-1] or "image.jpg",
            )
            for img in evidence_pkg.image_evidence
        ]

        source_info = SourceInfoSection(
            product_url=prod_url,
            platform=platform,
            submitted_description=submitted_desc,
            submitted_images=submitted_images,
            submission_notes=case_obj.description,
        )

        # Build Section 4: Risk Assessment
        dim_breakdowns: List[DimensionBreakdownItem] = []
        breakdown_dict = (
            risk_assessment.score_breakdown
            if risk_assessment and isinstance(risk_assessment.score_breakdown, dict)
            else {}
        )
        contributing_factors = breakdown_dict.get("contributing_factors", [])
        for factor in contributing_factors:
            if isinstance(factor, dict):
                dim_breakdowns.append(
                    DimensionBreakdownItem(
                        dimension=factor.get("dimension", "GENERAL"),
                        finding_count=factor.get("finding_count", 0),
                        max_severity=factor.get("max_severity", "NONE"),
                        weighted_contribution=factor.get("weighted_contribution", 0.0),
                        raw_dimension_score=factor.get("raw_dimension_score", 0.0),
                        confidence=factor.get("confidence", 0.5),
                    )
                )

        raw_score = risk_assessment.risk_score if risk_assessment else 0.15
        raw_level = risk_assessment.risk_level if risk_assessment else "LOW"
        raw_conf = risk_assessment.confidence_score if risk_assessment else 0.75
        completeness = breakdown_dict.get("data_completeness_ratio", 0.50)
        score_expl = breakdown_dict.get(
            "score_explanation",
            f"Automated risk triage score: {raw_score:.2f} ({raw_level}). Findings analyzed: {len(evidence_pkg.finding_bundles)}.",
        )

        risk_section = RiskAssessmentSection(
            risk_score=round(raw_score, 4),
            risk_level=raw_level,
            confidence_score=round(raw_conf, 4),
            total_findings_analyzed=len(evidence_pkg.finding_bundles),
            data_completeness_ratio=round(completeness, 4),
            score_explanation=score_expl,
            dimension_breakdown=dim_breakdowns,
            assessment_timestamp=(
                risk_assessment.created_at.isoformat()
                if risk_assessment and risk_assessment.created_at
                else None
            ),
        )

        # Build Section 5: Detected Findings
        detected_findings: List[DetectedFindingItem] = []
        for b in evidence_pkg.finding_bundles:
            # Check for license in finding text if not found yet
            if not product_info.fssai_license_number:
                for token in b.finding_title.split() + b.why_flagged.split():
                    if len(token) == 14 and token.isdigit():
                        product_info.fssai_license_number = token
                        break

            detected_findings.append(
                DetectedFindingItem(
                    finding_id=str(b.finding_id),
                    title=b.finding_title,
                    description=b.why_flagged,
                    severity=b.severity,
                    confidence=0.88,
                    dimension=b.source,
                    rule_code=b.rule_code,
                    statutory_reference=b.statutory_reference,
                    why_flagged=b.why_flagged,
                )
            )

        # Build Section 6: Evidence
        evidence_items: List[EvidenceItem] = []
        all_records = (
            evidence_pkg.url_evidence
            + evidence_pkg.image_evidence
            + evidence_pkg.ocr_evidence
            + evidence_pkg.submitted_text_evidence
            + evidence_pkg.extracted_data_evidence
        )

        for rec in all_records:
            evidence_items.append(
                EvidenceItem(
                    evidence_id=str(rec.record_id),
                    evidence_type=rec.evidence_type.value if hasattr(rec.evidence_type, "value") else str(rec.evidence_type),
                    source=rec.source_type or "Product Dossier Ingestion",
                    extracted_text=rec.content_text,
                    image_url=rec.content_uri,
                    sha256_hash=rec.sha256_hash,
                    confidence_score=0.92,
                    timestamp=rec.capture_timestamp.isoformat() if rec.capture_timestamp else datetime.now(timezone.utc).isoformat(),
                    linked_finding_ids=[],
                )
            )

        # Build Section 7: Analysis Limitations
        missing_info: List[str] = []
        if not product_info.fssai_license_number:
            missing_info.append("FSSAI 14-digit license number absent or not declared on packaging.")
        if not evidence_pkg.image_evidence:
            missing_info.append("Primary physical packaging images missing; analysis derived solely from digital metadata.")
        if not evidence_pkg.url_evidence:
            missing_info.append("Live e-commerce listing URL not supplied; cross-platform price/claim parity unverified.")

        ocr_limits: List[str] = []
        if evidence_pkg.ocr_evidence:
            ocr_limits.append("OCR token extraction subject to optical distortion, glare, and curved container typography.")
        else:
            ocr_limits.append("Direct high-resolution optical character scanning pending physical container submission.")

        ai_confidence_limits: List[str] = [
            "AI neural extractors utilize statistical NLP models and require verification against latest FSSAI gazette notifications.",
            "Ingredient thresholds evaluated against FSSAI Compendium (2025/2026); novel herbal extracts may require scientific panel referral.",
        ]
        if completeness < 0.60:
            ai_confidence_limits.append(
                f"Data completeness ratio is {completeness*100:.1f}% (< 60%). Score reliability increases when 6-sided pack images are provided."
            )

        completeness_desc = (
            "Comprehensive Data Set (> 75%)"
            if completeness >= 0.75
            else ("Moderate Data Completeness (50-74%)" if completeness >= 0.50 else "Preliminary / Incomplete Data Set (< 50%)")
        )

        limitations = AnalysisLimitationsSection(
            missing_information=missing_info if missing_info else ["No critical statutory data elements missing."],
            ocr_limitations=ocr_limits,
            ai_confidence_limitations=ai_confidence_limits,
            data_completeness_ratio=round(completeness, 4),
            overall_completeness_assessment=completeness_desc,
        )

        # Build Section 8: Review Recommendation
        has_critical = any(f.severity == "CRITICAL" for f in detected_findings)
        has_high = any(f.severity == "HIGH" for f in detected_findings)

        if has_critical or raw_level == "CRITICAL" or raw_score >= 0.65:
            rec = "PRIORITY_REVIEW"
            priority_lvl = "URGENT_P1"
            reason = (
                "Critical regulatory infraction detected (prohibited curative disease claims, unauthorized toxic substances, "
                "or extreme labeling deception). Immediate intervention by Designated Officer required under Section 32 / 38."
            )
            suggested = [
                "Issue Statutory Improvement Notice under Section 32 of FSS Act, 2006",
                "Direct Food Safety Officer (FSO) to conduct field inspection and formal sampling (Form VA)",
                "Refer product sample to NABL-accredited State Food Laboratory under Section 45",
                "Issue urgent advisory to e-commerce marketplaces to delist non-compliant SKU",
            ]
            sec32 = True
            sampling = True
            lab = True
        elif has_high or raw_level == "HIGH" or raw_score >= 0.35:
            rec = "PRIORITY_REVIEW"
            priority_lvl = "HIGH_P2"
            reason = (
                "High regulatory risk identified with material packaging non-compliance, unapproved health claims, or "
                "license validity discrepancies. Fast-track human officer verification warranted."
            )
            suggested = [
                "Assign Designated Officer to evaluate licensee explanations",
                "Issue regulatory query to Manufacturer / FBO requiring substantiation within 14 days",
                "Initiate targeted surveillance sampling in retail distribution hubs",
            ]
            sec32 = True
            sampling = True
            lab = False
        elif completeness < 0.40:
            rec = "ADDITIONAL_INFO_REQUIRED"
            priority_lvl = "ROUTINE_P3"
            reason = (
                "Data completeness is below minimum analytical threshold. Primary packaging images and ingredient lists "
                "must be acquired before rendering final regulatory categorization."
            )
            suggested = [
                "Issue notice to FBO / Submitter to furnish complete 6-sided high-resolution packaging images",
                "Obtain physical sample from market for complete optical character scanning",
            ]
            sec32 = False
            sampling = False
            lab = False
        else:
            rec = "STANDARD_REVIEW"
            priority_lvl = "ROUTINE_P3" if raw_level == "MEDIUM" else "MONITORING_P4"
            reason = (
                "Routine surveillance sample with minor or no statutory non-compliance indicators. "
                "Suitable for standard periodic monitoring registry."
            )
            suggested = [
                "Log docket in Standard Surveillance Register",
                "Retain in automated web scraper monitoring schedule for subsequent batch audits",
            ]
            sec32 = False
            sampling = False
            lab = False

        recommendations = ReviewRecommendationSection(
            recommendation=rec,
            priority_level=priority_lvl,
            recommendation_reason=reason,
            suggested_actions=suggested,
            statutory_notice_recommended=sec32,
            sampling_recommended=sampling,
            lab_referral_recommended=lab,
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        report_id = f"DRISHTI-REP-{case_obj.case_number}-{int(datetime.now(timezone.utc).timestamp())}"
        
        digest_payload = f"{report_id}|{case_obj.case_number}|{raw_score}|{raw_level}|{len(detected_findings)}|{now_iso}"
        report_hash = hashlib.sha256(digest_payload.encode()).hexdigest()

        return CaseComplianceReportData(
            report_identifier=report_id,
            generated_at=now_iso,
            case_info=case_info,
            product_info=product_info,
            source_info=source_info,
            risk_assessment=risk_section,
            detected_findings=detected_findings,
            evidence=evidence_items,
            analysis_limitations=limitations,
            review_recommendation=recommendations,
            sha256_report_hash=report_hash,
        )
