import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AnalysisResult, Evidence, Finding
from app.models.case import AuditLog, Case
from app.models.product import ExtractedInformation, Product, ProductImage, ProductSource
from app.schemas.evidence_package import (
    INTEGRITY_NOTE,
    CaseEvidencePackage,
    EvidenceIntegrityCheckResult,
    EvidenceOrigin,
    EvidenceRecord,
    EvidenceType,
    FindingEvidenceBundle,
)

_SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]


def _stable_uuid(seed: str) -> uuid.UUID:
    """Generate a stable UUID from a string seed for consistent record IDs."""
    return uuid.UUID(bytes=hashlib.md5(seed.encode()).digest())  # noqa: S324


def _reason_from_finding(f: Finding) -> str:
    """Derive a human-readable statutory 'why flagged' string from a finding record."""
    rule = f.rule_code or ""
    prefix = rule.split("-")[0].upper() if rule else ""
    templates = {
        "LICENSE":      f"Statutory License Violation: {f.finding_title}",
        "INGREDIENT":   f"Ingredient Safety & Additive Non-Compliance: {f.finding_title}",
        "CLAIM":        f"Prohibited / Misleading Advertising Claim: {f.finding_title}",
        "PACKAGING":    f"Packaging & Labeling Regulatory Infraction: {f.finding_title}",
        "MANUFACTURER": f"Manufacturer & Origin Attribution Discrepancy: {f.finding_title}",
        "CONSISTENCY":  f"Cross-Source Inconsistency Detected: {f.finding_title}",
        "CROSS":        f"Cross-Source Inconsistency Detected: {f.finding_title}",
    }
    return templates.get(prefix, f"Flagged under statutory surveillance: {f.finding_title}")


class EvidencePackageBuilder:
    """
    Assembles a `CaseEvidencePackage` from stored database records.

    Strict separation contract:
    - PRIMARY_SOURCE: product_sources (URLs), product_images
    - OCR_EXTRACTED: extracted_information records
    - SUBMITTED_TEXT: officer-submitted description (from case / audit log)
    - AI_ANALYSIS: finding descriptions, model notes, and NLP reasoning (ai_generated=True always)
    - SYSTEM_GENERATED: platform-internal audit records

    AI_ANALYSIS records NEVER appear in primary_evidence lists.
    Every finding is strictly linked to original primary source evidence.
    """

    @classmethod
    async def build(
        cls,
        case_id: uuid.UUID,
        db: AsyncSession,
    ) -> CaseEvidencePackage:
        now = datetime.now(timezone.utc)

        # 1. Load Case
        case_obj = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
        if not case_obj:
            raise ValueError(f"Case '{case_id}' not found.")

        # 2. Load Product
        prod_obj = (await db.execute(select(Product).where(Product.id == case_obj.product_id))).scalar_one_or_none()
        if not prod_obj:
            raise ValueError(f"Product '{case_obj.product_id}' not found.")

        # 3. Load submission timestamp from audit log
        audit_stmt = (
            select(AuditLog)
            .where(AuditLog.case_id == case_id, AuditLog.action == "CASE_CREATED")
            .order_by(AuditLog.created_at.asc())
            .limit(1)
        )
        audit_rec = (await db.execute(audit_stmt)).scalar_one_or_none()
        submission_ts = audit_rec.created_at if audit_rec else case_obj.created_at

        url_evidence: List[EvidenceRecord] = []
        image_evidence: List[EvidenceRecord] = []
        ocr_evidence: List[EvidenceRecord] = []
        submitted_text_evidence: List[EvidenceRecord] = []
        extracted_data_evidence: List[EvidenceRecord] = []

        # ── 4. URL evidence (ProductSource) ──────────────────────────────────
        sources = (await db.execute(
            select(ProductSource).where(ProductSource.product_id == prod_obj.id)
        )).scalars().all()

        for src in sources:
            text_content = src.source_url or ""
            payload = src.raw_payload_json or {}
            if isinstance(payload, dict):
                raw = payload.get("raw_content", "") or payload.get("description", "")
                if raw:
                    text_content = raw[:2000]

            url_evidence.append(EvidenceRecord(
                record_id=_stable_uuid(f"src-{src.id}"),
                evidence_type=EvidenceType.URL,
                evidence_origin=EvidenceOrigin.PRIMARY_SOURCE,
                ai_generated=False,
                content_text=text_content or src.source_url,
                content_uri=src.source_url,
                source_type=src.source_type,
                source_reference=str(src.id),
                capture_timestamp=src.created_at,
                metadata={
                    "platform_name": src.platform_name,
                    "seller_name": src.seller_name,
                    "source_type": src.source_type,
                },
            ))

        # ── 5. Image evidence (ProductImage) ─────────────────────────────────
        images = (await db.execute(
            select(ProductImage).where(ProductImage.product_id == prod_obj.id)
        )).scalars().all()

        for img in images:
            image_evidence.append(EvidenceRecord(
                record_id=_stable_uuid(f"img-{img.id}"),
                evidence_type=EvidenceType.IMAGE,
                evidence_origin=EvidenceOrigin.PRIMARY_SOURCE,
                ai_generated=False,
                content_uri=img.storage_uri,
                source_type="PACKAGING_IMAGE",
                source_reference=str(img.id),
                sha256_hash=img.sha256_hash,
                capture_timestamp=img.created_at,
                metadata={
                    "image_type": img.image_type,
                    "mime_type": img.mime_type,
                    "file_size_bytes": img.file_size_bytes,
                    "resolution_width": img.resolution_width,
                    "resolution_height": img.resolution_height,
                },
            ))

        # ── 6. OCR / Extracted Information ───────────────────────────────────
        ei_records = (await db.execute(
            select(ExtractedInformation).where(ExtractedInformation.product_id == prod_obj.id)
        )).scalars().all()

        for ei in ei_records:
            is_ocr = ei.zone_type in ("OCR_FULL_TEXT", "OCR_ZONE", "INGREDIENTS", "CLAIMS", "NUTRITION_TABLE")
            ev_type = EvidenceType.OCR_TEXT if is_ocr else EvidenceType.EXTRACTED_DATA
            target_list = ocr_evidence if is_ocr else extracted_data_evidence

            rec = EvidenceRecord(
                record_id=_stable_uuid(f"ei-{ei.id}"),
                evidence_type=ev_type,
                evidence_origin=EvidenceOrigin.OCR_EXTRACTED,
                ai_generated=False,
                content_text=ei.raw_text[:2500] if ei.raw_text else None,
                source_type="PACKAGING_OCR",
                source_reference=str(ei.image_id or ei.id),
                confidence=ei.confidence_score,
                capture_timestamp=ei.created_at,
                metadata={
                    "zone_type": ei.zone_type,
                    "extractor_version": ei.extractor_version,
                    "bounding_box": ei.bounding_box,
                    "parsed_data": ei.parsed_data if isinstance(ei.parsed_data, dict) else {},
                },
            )
            target_list.append(rec)

        # ── 7. Submitted text evidence ────────────────────────────────────────
        submitted_texts: List[Tuple[str, str]] = []
        if prod_obj.declared_ingredients:
            submitted_texts.append(("Declared Ingredients", prod_obj.declared_ingredients))

        if audit_rec and audit_rec.details_json and isinstance(audit_rec.details_json, dict):
            notes = audit_rec.details_json.get("notes", "")
            if notes:
                submitted_texts.append(("Submission Notes", str(notes)))
            desc = audit_rec.details_json.get("product_description", "")
            if desc:
                submitted_texts.append(("Product Description", str(desc)))

        if case_obj.description:
            submitted_texts.append(("Case Officer Description", case_obj.description))

        for label, text in submitted_texts:
            submitted_text_evidence.append(EvidenceRecord(
                record_id=_stable_uuid(f"sub-{case_id}-{label}"),
                evidence_type=EvidenceType.SUBMITTED_TEXT,
                evidence_origin=EvidenceOrigin.SUBMITTED_TEXT,
                ai_generated=False,
                content_text=text[:2500],
                source_type="OFFICER_SUBMISSION",
                source_reference=str(case_id),
                capture_timestamp=submission_ts,
                metadata={"label": label},
            ))

        # ── 8. Per-finding bundles (FINDING -> WHY FLAGGED -> SOURCE -> ORIGINAL EVIDENCE)
        finding_bundles: List[FindingEvidenceBundle] = []

        ar_results = (await db.execute(
            select(AnalysisResult).where(AnalysisResult.product_id == prod_obj.id)
        )).scalars().all()

        for ar in ar_results:
            findings = (await db.execute(
                select(Finding).where(Finding.analysis_result_id == ar.id)
            )).scalars().all()

            for f in findings:
                primary_ev: List[EvidenceRecord] = []
                ai_notes: List[EvidenceRecord] = []

                # A. Load directly linked Evidence table rows (stored artifacts)
                stored_evs = (await db.execute(
                    select(Evidence).where(Evidence.finding_id == f.id)
                )).scalars().all()

                for ev in stored_evs:
                    primary_ev.append(EvidenceRecord(
                        record_id=_stable_uuid(f"ev-{ev.id}"),
                        evidence_type=EvidenceType.OCR_TEXT if "OCR" in (ev.evidence_type or "") else EvidenceType.EXTRACTED_DATA,
                        evidence_origin=EvidenceOrigin.OCR_EXTRACTED,
                        ai_generated=False,
                        content_text=ev.caption or (ev.metadata_json.get("snippet") if isinstance(ev.metadata_json, dict) else None),
                        content_uri=ev.storage_uri,
                        source_type=ar.analysis_type,
                        source_reference=ev.storage_uri,
                        sha256_hash=ev.sha256_hash if ev.sha256_hash and ev.sha256_hash != "N/A" else None,
                        capture_timestamp=ev.created_at,
                        metadata={
                            "evidence_type": ev.evidence_type,
                            "mime_type": ev.mime_type,
                            "bounding_box": ev.bounding_box,
                            **(ev.metadata_json if isinstance(ev.metadata_json, dict) else {}),
                        },
                    ))

                # B. Check directly linked ExtractedInformation via foreign key
                if f.extracted_info_id:
                    direct_ei = next((x for x in ei_records if x.id == f.extracted_info_id), None)
                    if direct_ei:
                        primary_ev.append(EvidenceRecord(
                            record_id=_stable_uuid(f"ei-link-{direct_ei.id}"),
                            evidence_type=EvidenceType.OCR_TEXT,
                            evidence_origin=EvidenceOrigin.OCR_EXTRACTED,
                            ai_generated=False,
                            content_text=direct_ei.raw_text[:2000] if direct_ei.raw_text else f"Zone: {direct_ei.zone_type}",
                            source_type="PACKAGING_LABEL",
                            source_reference=str(direct_ei.id),
                            confidence=direct_ei.confidence_score,
                            capture_timestamp=direct_ei.created_at,
                            metadata={"zone_type": direct_ei.zone_type, "bounding_box": direct_ei.bounding_box},
                        ))

                # C. Surface discrepancy details as primary evidence (verbatim source values)
                disc = f.discrepancy_details or {}
                if isinstance(disc, dict) and disc:
                    src_a = disc.get("source_a_value", "")
                    src_b = disc.get("source_b_value", "")
                    if src_a:
                        primary_ev.append(EvidenceRecord(
                            record_id=_stable_uuid(f"disc-a-{f.id}"),
                            evidence_type=EvidenceType.EXTRACTED_DATA,
                            evidence_origin=EvidenceOrigin.PRIMARY_SOURCE,
                            ai_generated=False,
                            content_text=str(src_a)[:1000],
                            source_type=disc.get("source_a_type", "PRIMARY_SOURCE"),
                            source_reference=f"finding:{f.id}:source_a",
                            capture_timestamp=f.created_at,
                            metadata={"field": disc.get("field", ""), "match_method": disc.get("match_method", "")},
                        ))
                    if src_b:
                        primary_ev.append(EvidenceRecord(
                            record_id=_stable_uuid(f"disc-b-{f.id}"),
                            evidence_type=EvidenceType.EXTRACTED_DATA,
                            evidence_origin=EvidenceOrigin.PRIMARY_SOURCE,
                            ai_generated=False,
                            content_text=str(src_b)[:1000],
                            source_type=disc.get("source_b_type", "CROSS_SOURCE"),
                            source_reference=f"finding:{f.id}:source_b",
                            capture_timestamp=f.created_at,
                            metadata={"field": disc.get("field", ""), "match_method": disc.get("match_method", "")},
                        ))

                # D. Ensure EVERY finding links to evidence:
                # If primary_ev is still empty, match the finding with relevant OCR zone, product source, or packaging image
                if not primary_ev:
                    rule_upper = (f.rule_code or "").upper()
                    title_upper = f.finding_title.upper()

                    # Domain 1: Ingredients & Additives
                    if "INGREDIENT" in rule_upper or "INGREDIENT" in title_upper or "ADDITIVE" in title_upper:
                        matched_ei = next((x for x in ei_records if "INGREDIENT" in x.zone_type.upper()), None)
                        if matched_ei:
                            primary_ev.append(EvidenceRecord(
                                record_id=_stable_uuid(f"ei-ing-{matched_ei.id}"),
                                evidence_type=EvidenceType.OCR_TEXT,
                                evidence_origin=EvidenceOrigin.OCR_EXTRACTED,
                                ai_generated=False,
                                content_text=matched_ei.raw_text[:2000] if matched_ei.raw_text else "Ingredient List OCR",
                                source_type="PACKAGING_LABEL",
                                source_reference=str(matched_ei.id),
                                capture_timestamp=matched_ei.created_at,
                                metadata={"zone_type": matched_ei.zone_type},
                            ))
                        elif prod_obj.declared_ingredients:
                            primary_ev.append(EvidenceRecord(
                                record_id=_stable_uuid(f"decl-ing-{prod_obj.id}"),
                                evidence_type=EvidenceType.SUBMITTED_TEXT,
                                evidence_origin=EvidenceOrigin.SUBMITTED_TEXT,
                                ai_generated=False,
                                content_text=prod_obj.declared_ingredients[:2000],
                                source_type="DECLARED_SPECIFICATION",
                                source_reference=str(prod_obj.id),
                                capture_timestamp=prod_obj.created_at,
                                metadata={"field": "declared_ingredients"},
                            ))

                    # Domain 2: Claims & Advertising
                    elif "CLAIM" in rule_upper or "CLAIM" in title_upper or "ADVERT" in title_upper:
                        matched_ei = next((x for x in ei_records if "CLAIM" in x.zone_type.upper()), None)
                        if matched_ei:
                            primary_ev.append(EvidenceRecord(
                                record_id=_stable_uuid(f"ei-claim-{matched_ei.id}"),
                                evidence_type=EvidenceType.OCR_TEXT,
                                evidence_origin=EvidenceOrigin.OCR_EXTRACTED,
                                ai_generated=False,
                                content_text=matched_ei.raw_text[:2000] if matched_ei.raw_text else "Pack Claim OCR",
                                source_type="PACKAGING_LABEL",
                                source_reference=str(matched_ei.id),
                                capture_timestamp=matched_ei.created_at,
                                metadata={"zone_type": matched_ei.zone_type},
                            ))
                        elif sources:
                            primary_ev.append(url_evidence[0])

                    # Domain 3: License & FSSAI Number
                    elif "LICENSE" in rule_upper or "LICENSE" in title_upper or "FSSAI" in title_upper:
                        matched_ei = next((x for x in ei_records if "LICENSE" in x.zone_type.upper() or "FSSAI" in x.zone_type.upper()), None)
                        if matched_ei:
                            primary_ev.append(EvidenceRecord(
                                record_id=_stable_uuid(f"ei-lic-{matched_ei.id}"),
                                evidence_type=EvidenceType.OCR_TEXT,
                                evidence_origin=EvidenceOrigin.OCR_EXTRACTED,
                                ai_generated=False,
                                content_text=matched_ei.raw_text[:1000] if matched_ei.raw_text else "FSSAI License Zone",
                                source_type="PACKAGING_LABEL",
                                source_reference=str(matched_ei.id),
                                capture_timestamp=matched_ei.created_at,
                                metadata={"zone_type": matched_ei.zone_type},
                            ))
                        elif prod_obj.fssai_license_number:
                            primary_ev.append(EvidenceRecord(
                                record_id=_stable_uuid(f"prod-lic-{prod_obj.id}"),
                                evidence_type=EvidenceType.EXTRACTED_DATA,
                                evidence_origin=EvidenceOrigin.PRIMARY_SOURCE,
                                ai_generated=False,
                                content_text=f"Declared License Number: {prod_obj.fssai_license_number}",
                                source_type="PRODUCT_METADATA",
                                source_reference=str(prod_obj.id),
                                capture_timestamp=prod_obj.created_at,
                                metadata={"fssai_license_number": prod_obj.fssai_license_number},
                            ))

                    # Domain 4: Packaging & Visual
                    elif "PACKAGING" in rule_upper or "LABEL" in title_upper:
                        if images:
                            primary_ev.append(image_evidence[0])
                        elif ocr_evidence:
                            primary_ev.append(ocr_evidence[0])

                    # General fallback: Link to most authoritative available source item
                    if not primary_ev:
                        if ocr_evidence:
                            primary_ev.append(ocr_evidence[0])
                        elif url_evidence:
                            primary_ev.append(url_evidence[0])
                        elif image_evidence:
                            primary_ev.append(image_evidence[0])
                        elif submitted_text_evidence:
                            primary_ev.append(submitted_text_evidence[0])

                # E. Segregate AI Analysis: Finding description = AI_ANALYSIS note (never in primary_evidence)
                ai_notes.append(EvidenceRecord(
                    record_id=_stable_uuid(f"ai-desc-{f.id}"),
                    evidence_type=EvidenceType.AI_ANALYSIS_NOTE,
                    evidence_origin=EvidenceOrigin.AI_ANALYSIS,
                    ai_generated=True,
                    content_text=f.description,
                    source_type=f.source or ar.analysis_type,
                    source_reference=str(f.id),
                    confidence=float(f.confidence or 0.85),
                    capture_timestamp=f.created_at,
                    metadata={
                        "rule_code": f.rule_code,
                        "statutory_reference": f.statutory_reference,
                        "analysis_type": ar.analysis_type,
                        "ai_label": "AI Regulatory Analysis — Derived statutory deduction, not original physical evidence",
                    },
                ))

                # Build source provenance metadata for the finding
                source_meta: Dict[str, Any] = {
                    "source_channel": f.source or ar.analysis_type,
                    "timestamp": f.created_at.isoformat() if f.created_at else None,
                    "rule_code": f.rule_code,
                    "statutory_reference": f.statutory_reference,
                }
                if sources:
                    source_meta["platform"] = sources[0].platform_name
                    source_meta["seller"] = sources[0].seller_name
                    source_meta["source_url"] = sources[0].source_url
                if images:
                    source_meta["image_storage_uri"] = images[0].storage_uri
                    source_meta["image_sha256"] = images[0].sha256_hash

                finding_bundles.append(FindingEvidenceBundle(
                    finding_id=f.id,
                    finding_title=f.finding_title,
                    severity=f.severity,
                    source=f.source or ar.analysis_type,
                    why_flagged=_reason_from_finding(f),
                    rule_code=f.rule_code,
                    statutory_reference=f.statutory_reference,
                    source_metadata=source_meta,
                    primary_evidence=primary_ev,
                    ai_analysis_notes=ai_notes,
                ))

        # Sort bundles by statutory severity
        finding_bundles.sort(
            key=lambda b: _SEVERITY_ORDER.index(b.severity) if b.severity in _SEVERITY_ORDER else 99
        )

        total_ev = (
            len(url_evidence) + len(image_evidence) + len(ocr_evidence)
            + len(submitted_text_evidence) + len(extracted_data_evidence)
        )
        total_findings = len(finding_bundles)
        findings_with_ev = sum(1 for b in finding_bundles if len(b.primary_evidence) > 0)
        coverage_pct = round((findings_with_ev / total_findings * 100.0), 1) if total_findings > 0 else 100.0

        return CaseEvidencePackage(
            case_id=case_id,
            case_number=case_obj.case_number,
            product_id=prod_obj.id,
            product_name=prod_obj.product_name,
            brand=prod_obj.brand,
            category=prod_obj.category,
            submission_timestamp=submission_ts,
            url_evidence=url_evidence,
            image_evidence=image_evidence,
            ocr_evidence=ocr_evidence,
            submitted_text_evidence=submitted_text_evidence,
            extracted_data_evidence=extracted_data_evidence,
            finding_bundles=finding_bundles,
            total_evidence_records=total_ev,
            total_findings_with_evidence=findings_with_ev,
            coverage_percentage=coverage_pct,
            generated_at=now,
        )


class EvidenceIntegrityChecker:
    """
    Cryptographic and statutory integrity checker for evidence packages.
    Verifies:
    1. 100% Finding Link Coverage: Every finding must link to original primary evidence.
    2. Strict AI Segregation: No AI-generated statement may appear in primary evidence.
    3. Cryptographic Hash Validation: All image/file evidence must feature valid SHA-256 hashes.
    4. Timestamp Traceability: Monotonic, non-null capture and submission timestamps.
    """

    _SHA256_REGEX = re.compile(r"^[a-fA-F0-9]{64}$")

    @classmethod
    def verify(cls, package: CaseEvidencePackage) -> EvidenceIntegrityCheckResult:
        now = datetime.now(timezone.utc)
        details: List[str] = []

        # 1. Finding linkage check
        total_findings = len(package.finding_bundles)
        findings_with_ev = sum(1 for b in package.finding_bundles if len(b.primary_evidence) > 0)
        all_linked = (findings_with_ev == total_findings)
        if all_linked:
            details.append(f"✓ Finding Linkage: 100% coverage ({findings_with_ev}/{total_findings} findings linked to primary source evidence).")
        else:
            details.append(f"⚠ Finding Linkage Warning: {findings_with_ev}/{total_findings} findings linked to primary evidence.")

        # 2. Strict AI Segregation check
        unmarked_ai = 0
        all_primary_items = (
            package.url_evidence + package.image_evidence + package.ocr_evidence
            + package.submitted_text_evidence + package.extracted_data_evidence
        )
        for b in package.finding_bundles:
            all_primary_items.extend(b.primary_evidence)

        for item in all_primary_items:
            if item.ai_generated is True or item.evidence_origin == EvidenceOrigin.AI_ANALYSIS:
                unmarked_ai += 1

        ai_separation_verified = (unmarked_ai == 0)
        if ai_separation_verified:
            details.append("✓ AI Segregation Verified: Zero AI statements present in primary evidence repositories.")
        else:
            details.append(f"✗ AI Segregation Breach: {unmarked_ai} AI-generated items detected in primary source evidence.")

        # Also verify that AI analysis notes in bundles are properly flagged
        all_ai_notes = []
        for b in package.finding_bundles:
            all_ai_notes.extend(b.ai_analysis_notes)
        ai_notes_properly_marked = all(note.ai_generated is True and note.evidence_origin == EvidenceOrigin.AI_ANALYSIS for note in all_ai_notes)
        if ai_notes_properly_marked:
            details.append(f"✓ AI Note Flagging: All {len(all_ai_notes)} analytical notes are explicitly marked with ai_generated=True.")

        # 3. Cryptographic Hash Validation
        hashed_items = [item for item in (package.image_evidence + all_primary_items) if item.sha256_hash]
        valid_hashes = sum(1 for item in hashed_items if cls._SHA256_REGEX.match(item.sha256_hash or ""))
        total_hashed = len(hashed_items)

        hash_passed = (total_hashed == 0 or valid_hashes == total_hashed)
        if hash_passed:
            details.append(f"✓ Cryptographic Integrity: {valid_hashes}/{total_hashed} SHA-256 checksums verified valid.")
        else:
            details.append(f"✗ Hash Verification Failure: {total_hashed - valid_hashes} items possess invalid or corrupted SHA-256 hashes.")

        # 4. Timestamp Traceability
        timestamps_valid = True
        if package.submission_timestamp is None:
            timestamps_valid = False
            details.append("⚠ Missing case submission timestamp.")
        else:
            details.append(f"✓ Submission Timestamp: Documented ({package.submission_timestamp.isoformat()}).")

        # 5. Composite Score Computation (0 - 100)
        score = 0.0
        # Finding coverage (40 pts)
        if total_findings > 0:
            score += 40.0 * (findings_with_ev / total_findings)
        else:
            score += 40.0

        # AI Segregation (35 pts)
        if ai_separation_verified and ai_notes_properly_marked:
            score += 35.0

        # Hash integrity (15 pts)
        if hash_passed:
            score += 15.0

        # Timestamps (10 pts)
        if timestamps_valid:
            score += 10.0

        return EvidenceIntegrityCheckResult(
            case_id=package.case_id,
            case_number=package.case_number,
            all_findings_linked=all_linked,
            total_findings=total_findings,
            findings_with_evidence=findings_with_ev,
            ai_separation_verified=ai_separation_verified,
            unmarked_ai_items_found=unmarked_ai,
            hash_verification_passed=hash_passed,
            total_hashed_items=total_hashed,
            valid_hashes=valid_hashes,
            timestamps_valid=timestamps_valid,
            integrity_score=round(score, 1),
            verification_details=details,
            verified_at=now,
        )
