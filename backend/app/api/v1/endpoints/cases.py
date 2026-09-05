import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import HTMLResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_authority_officer
from app.core.storage import ALLOWED_MIME_TYPES, save_uploaded_image, validate_url
from app.database.session import get_db
from app.models.analysis import RiskAssessment
from app.models.case import AuditLog, Case, CaseReview
from app.models.product import Product, ProductImage, ProductSource
from app.models.user import User
from app.schemas.case import (
    CaseAuditTrailResponse,
    CaseRead,
    CaseReviewRead,
    CaseReviewSubmission,
    CaseStatusUpdate,
    PriorityQueueItem,
    PriorityQueueResponse,
)
from app.schemas.dashboard import DashboardMetrics, RecentCaseItem
from app.schemas.product import ProductRead, ProductSimpleRead
from app.schemas.consistency import ConsistencyReport
from app.schemas.explanation import ExplanationReport
from app.schemas.risk import RiskAssessmentReport
from app.schemas.deep_analysis import DeepAnalysisReportResponse
from app.schemas.evidence_package import CaseEvidencePackage, EvidenceIntegrityCheckResult
from app.schemas.report import CaseComplianceReportData
from app.schemas.intelligence import CanonicalStructuredProduct
from app.schemas.ocr import CaseOCRSummaryResponse, OCRResultResponse
from app.schemas.case_pipeline import CasePipelineResult
from app.schemas.submission import (
    CaseDetailResponse,
    CaseSubmissionResponse,
    ProductImageResponse,
    SourceAddRequest,
    SourceResponse,
)


router = APIRouter(prefix="/cases", tags=["Regulatory Cases & Submissions"])


# ---------------------------------------------------------------------------
# 1. Product Submission & Case Creation Workflow (Phase 5)
# ---------------------------------------------------------------------------
async def _handle_submission(
    request: Request,
    current_user: User,
    db: AsyncSession,
) -> CaseSubmissionResponse:
    content_type = (request.headers.get("content-type") or "").lower()
    client_ip = request.client.host if request.client else None

    product_url: Optional[str] = None
    product_description: Optional[str] = None
    product_name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    fssai_license_number: Optional[str] = None
    notes: Optional[str] = None
    valid_product_images: List[UploadFile] = []
    valid_packaging_images: List[UploadFile] = []

    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed JSON body.",
            )
        if not isinstance(body, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="JSON body must be an object.",
            )

        product_url = body.get("product_url") or body.get("source_url")
        product_description = body.get("product_description") or body.get("description")
        product_name = body.get("product_name")
        brand = body.get("brand")
        category = body.get("category")
        manufacturer = body.get("manufacturer")
        fssai_license_number = body.get("fssai_license_number")
        notes = body.get("notes")
    else:
        form = await request.form()
        product_url = form.get("product_url") or form.get("source_url")  # type: ignore
        product_description = form.get("product_description") or form.get("description")  # type: ignore
        product_name = form.get("product_name")  # type: ignore
        brand = form.get("brand")  # type: ignore
        category = form.get("category")  # type: ignore
        manufacturer = form.get("manufacturer")  # type: ignore
        fssai_license_number = form.get("fssai_license_number")  # type: ignore
        notes = form.get("notes")  # type: ignore

        for f in form.getlist("product_images"):
            if hasattr(f, "filename") and f.filename:
                valid_product_images.append(f)

        for f in form.getlist("packaging_images"):
            if hasattr(f, "filename") and f.filename:
                valid_packaging_images.append(f)

    # Clean string inputs
    clean_url = str(product_url).strip() if product_url else ""
    clean_desc = str(product_description).strip() if product_description else ""
    clean_notes = str(notes).strip() if notes else ""
    clean_name = str(product_name).strip() if product_name else ""
    clean_brand = str(brand).strip() if brand else ""
    clean_category = str(category).strip() if category else ""
    clean_manufacturer = str(manufacturer).strip() if manufacturer else ""
    clean_license = str(fssai_license_number).strip() if fssai_license_number else ""

    all_images = valid_product_images + valid_packaging_images
    has_url = bool(clean_url)
    has_desc = bool(clean_desc)
    has_images = len(all_images) > 0

    # 1. Validation: At least one input option must be provided
    if not (has_url or has_desc or has_images):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "At least one input option must be provided: "
                "Option 1 (Product URL), Option 2 (Product/Packaging Images), "
                "or Option 3 (Product Description)."
            ),
        )

    # 1b. Validate all uploaded image file formats upfront
    for img_f in all_images:
        ct = (img_f.content_type or "application/octet-stream").lower()
        ext = os.path.splitext(img_f.filename or "")[1].lower()
        if ct in ("application/octet-stream", "", "binary/octet-stream"):
            if ext in (".jpg", ".jpeg"):
                ct = "image/jpeg"
            elif ext == ".png":
                ct = "image/png"
            elif ext == ".webp":
                ct = "image/webp"
        if ct not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type '{ct}'. Allowed image formats: JPEG, PNG, WEBP.",
            )

    # 2. Validate URL format if provided
    if has_url:
        if not validate_url(clean_url):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid Product URL '{clean_url}'. URL must start with http:// or https:// with a valid domain.",
            )

    # 3. Derive sensible product names & attributes if omitted
    now = datetime.now(timezone.utc)
    case_serial = str(uuid.uuid4().hex[:6]).upper()
    case_number = f"FSSAI-CASE-2026-{case_serial}"

    resolved_product_name = clean_name
    if not resolved_product_name:
        if has_desc:
            first_line = clean_desc.split("\n")[0][:80]
            resolved_product_name = f"Sample: {first_line}"
        elif has_url:
            parsed = urlparse(clean_url)
            resolved_product_name = f"Product Listing from {parsed.netloc}"
        else:
            resolved_product_name = f"Packaging Evidence ({case_number})"

    resolved_brand = clean_brand or "Brand Under Surveillance"
    resolved_category = clean_category or "GENERAL_FOOD_PRODUCTS"

    # 4. Create Product Entity
    prod = Product(
        product_name=resolved_product_name,
        brand=resolved_brand,
        category=resolved_category,
        manufacturer=clean_manufacturer or None,
        fssai_license_number=clean_license or None,
    )
    db.add(prod)
    await db.flush()

    # 5. Create Case Entity with initial status = "SUBMITTED"
    case_title = f"Surveillance Docket: {resolved_product_name[:120]}"
    case_desc = clean_notes or clean_desc or f"Product submitted for compliance surveillance under {clean_url or 'packaging evidence'}."

    case_obj = Case(
        case_number=case_number,
        product_id=prod.id,
        assigned_user_id=current_user.id,
        status="SUBMITTED",
        priority="ROUTINE_P3",
        jurisdiction_district=current_user.jurisdiction_district or "DL-CENTRAL",
        title=case_title,
        description=case_desc,
        created_at=now,
    )
    db.add(case_obj)
    await db.flush()

    # 6. Record Product Sources
    sources_count = 0

    # 6a. Option 1: URL Source
    if has_url:
        parsed_domain = urlparse(clean_url).netloc
        src_url = ProductSource(
            product_id=prod.id,
            source_type="ECOMMERCE_URL",
            source_url=clean_url,
            platform_name=f"Web Market ({parsed_domain})",
            raw_payload_json={
                "source_type": "ECOMMERCE_URL",
                "source_url": clean_url,
                "domain": parsed_domain,
                "submitted_at": now.isoformat(),
                "submitted_by": current_user.email,
            },
        )
        db.add(src_url)
        sources_count += 1

    # 6b. Option 3: Description Source
    if has_desc:
        src_desc = ProductSource(
            product_id=prod.id,
            source_type="PRODUCT_DESCRIPTION",
            platform_name="Officer Input Description",
            raw_payload_json={
                "source_type": "PRODUCT_DESCRIPTION",
                "raw_content": clean_desc,
                "submitted_at": now.isoformat(),
                "submitted_by": current_user.email,
            },
        )
        db.add(src_desc)
        sources_count += 1

    # 6c. Option 2: Image Source marker
    if has_images:
        src_img = ProductSource(
            product_id=prod.id,
            source_type="PACKAGING_IMAGE",
            platform_name="Authority Image Upload",
            raw_payload_json={
                "source_type": "PACKAGING_IMAGE",
                "image_count": len(all_images),
                "submitted_at": now.isoformat(),
                "submitted_by": current_user.email,
            },
        )
        db.add(src_img)
        sources_count += 1

    # 7. Store uploaded images and compute SHA-256 hashes
    saved_images_count = 0
    for img_file in valid_product_images:
        meta = await save_uploaded_image(img_file, case_obj.id, image_type="PRODUCT_IMAGE")
        img_record = ProductImage(
            product_id=prod.id,
            image_type="PRODUCT_IMAGE",
            storage_uri=meta["storage_uri"],
            sha256_hash=meta["file_hash_sha256"],
            file_size_bytes=meta["file_size_bytes"],
            mime_type=meta["mime_type"],
        )
        db.add(img_record)
        saved_images_count += 1

    for pkg_file in valid_packaging_images:
        meta = await save_uploaded_image(pkg_file, case_obj.id, image_type="PACKAGING_FOP")
        img_record = ProductImage(
            product_id=prod.id,
            image_type="PACKAGING_FOP",
            storage_uri=meta["storage_uri"],
            sha256_hash=meta["file_hash_sha256"],
            file_size_bytes=meta["file_size_bytes"],
            mime_type=meta["mime_type"],
        )
        db.add(img_record)
        saved_images_count += 1

    # 8. Create Audit Log
    audit = AuditLog(
        case_id=case_obj.id,
        user_id=current_user.id,
        action="CASE_CREATED",
        entity_type="Case",
        entity_id=str(case_obj.id),
        details_json={
            "case_number": case_number,
            "status": "SUBMITTED",
            "has_url": has_url,
            "has_description": has_desc,
            "images_saved": saved_images_count,
            "sources_count": sources_count,
            "officer_badge": current_user.badge_id,
        },
        ip_address=client_ip,
        created_at=now,
    )
    db.add(audit)

    prod_audit = AuditLog(
        case_id=case_obj.id,
        user_id=current_user.id,
        action="PRODUCT_SUBMITTED",
        entity_type="Product",
        entity_id=str(prod.id),
        details_json={
            "product_name": prod.product_name,
            "brand": prod.brand,
            "category": prod.category,
            "fssai_license": prod.fssai_license_number,
            "officer_badge": current_user.badge_id,
        },
        ip_address=client_ip,
        created_at=now,
    )
    db.add(prod_audit)

    await db.commit()
    await db.refresh(case_obj)

    return CaseSubmissionResponse(
        case_id=case_obj.id,
        case_number=case_number,
        product_id=prod.id,
        status=case_obj.status,
        title=case_obj.title,
        sources_count=sources_count,
        images_count=saved_images_count,
        created_at=case_obj.created_at,
        message=f"Case {case_number} created with status 'SUBMITTED' and queued for compliance analysis.",
    )


@router.post(
    "",
    response_model=CaseSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Product & Create Investigation Case",
    description="Accepts Option 1 (URL), Option 2 (Images), Option 3 (Description), or Mixed inputs.",
)
async def submit_case_endpoint(
    request: Request,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    return await _handle_submission(request, current_user, db)


@router.post(
    "/submit",
    response_model=CaseSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Product Surveillance Alias",
    include_in_schema=False,
)
async def submit_case_alias_endpoint(
    request: Request,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    return await _handle_submission(request, current_user, db)


# ---------------------------------------------------------------------------
# 2. Specific Static Routes (Placed BEFORE /{case_id} to avoid UUID conflicts)
# ---------------------------------------------------------------------------
@router.get(
    "/metrics",
    response_model=DashboardMetrics,
    summary="Aggregate Dashboard Metrics",
)
async def get_dashboard_metrics(
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    total_cases = (await db.execute(select(func.count(Case.id)))).scalar() or 0
    under_analysis = (
        await db.execute(
            select(func.count(Case.id)).where(Case.status.in_(["SUBMITTED", "TRIAGED", "ASSIGNED"]))
        )
    ).scalar() or 0

    pending_review = (
        await db.execute(
            select(func.count(Case.id)).where(
                Case.status.in_(["FIELD_INSPECTION_ORDERED", "SAMPLE_DRAWN", "NOTICE_ISSUED_SEC32"])
            )
        )
    ).scalar() or 0

    low_risk = (await db.execute(select(func.count(RiskAssessment.id)).where(RiskAssessment.risk_level == "LOW"))).scalar() or 0
    med_risk = (await db.execute(select(func.count(RiskAssessment.id)).where(RiskAssessment.risk_level == "MEDIUM"))).scalar() or 0
    high_risk = (
        await db.execute(
            select(func.count(RiskAssessment.id)).where(RiskAssessment.risk_level.in_(["HIGH", "CRITICAL"]))
        )
    ).scalar() or 0

    return DashboardMetrics(
        total_cases=total_cases,
        cases_under_analysis=under_analysis,
        low_risk=low_risk,
        medium_risk=med_risk,
        high_risk=high_risk,
        pending_review=pending_review,
    )


@router.get(
    "/recent",
    response_model=List[RecentCaseItem],
    summary="Recent Surveillance Cases Table",
)
async def get_recent_cases(
    limit: int = Query(default=10, ge=1, le=50),
    risk_level: Optional[str] = Query(default=None),
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Case, Product, RiskAssessment)
        .join(Product, Case.product_id == Product.id)
        .outerjoin(RiskAssessment, RiskAssessment.case_id == Case.id)
        .order_by(desc(Case.created_at))
        .limit(limit)
    )

    if risk_level:
        stmt = stmt.where(RiskAssessment.risk_level == risk_level.upper())

    results = (await db.execute(stmt)).all()

    items: List[RecentCaseItem] = []
    for case_obj, prod_obj, risk_obj in results:
        items.append(
            RecentCaseItem(
                case_id=case_obj.id,
                case_number=case_obj.case_number,
                product_name=prod_obj.product_name,
                brand=prod_obj.brand,
                category=prod_obj.category,
                submission_date=case_obj.created_at,
                risk_level=risk_obj.risk_level if risk_obj else "LOW",
                risk_score=risk_obj.risk_score if risk_obj else 0.0,
                status=case_obj.status,
                priority=case_obj.priority,
                title=case_obj.title,
            )
        )
    return items


@router.get(
    "/triage",
    response_model=List[CaseRead],
    summary="Priority Investigation Triage Queue",
)
async def get_triage_queue(
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Case)
        .where(Case.status.in_(["SUBMITTED", "TRIAGED", "ASSIGNED"]))
        .order_by(desc(Case.created_at))
        .limit(20)
    )
    result = await db.execute(stmt)
    cases = result.scalars().all()
    return [CaseRead.model_validate(c) for c in cases]


# ---------------------------------------------------------------------------
# Phase 14: Priority Review Queue Endpoint
# ---------------------------------------------------------------------------
@router.get(
    "/priority-queue",
    response_model=PriorityQueueResponse,
    summary="Priority Review Queue",
    description=(
        "Retrieves the priority review queue with multi-field searching, "
        "filtering by risk tier and statutory case status, and sorting by risk score, "
        "submission date, or confidence."
    ),
)
async def get_priority_review_queue(
    search: Optional[str] = Query(default=None, description="Search term for case number, product name, brand, category, title"),
    risk_level: Optional[str] = Query(default=None, description="Filter by risk tier: CRITICAL, HIGH, MEDIUM, LOW, or ALL"),
    status: Optional[str] = Query(default=None, description="Filter by case status or ALL"),
    sort_by: str = Query(default="risk_score", description="Sort field: risk_score, submission_date, confidence"),
    sort_order: str = Query(default="desc", description="Sort direction: desc or asc"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Case, Product, RiskAssessment, User)
        .join(Product, Case.product_id == Product.id)
        .outerjoin(RiskAssessment, RiskAssessment.case_id == Case.id)
        .outerjoin(User, Case.assigned_user_id == User.id)
    )

    # Status filter
    if status and status != "ALL":
        stmt = stmt.where(Case.status == status)
    elif status is None:
        stmt = stmt.where(
            Case.status.in_([
                "PRIORITY_REVIEW",
                "UNDER_REVIEW",
                "STANDARD_REVIEW",
                "ANALYSIS_COMPLETE",
                "REVIEW_COMPLETED",
                "FIELD_INSPECTION_ORDERED",
                "SAMPLE_DRAWN",
                "NOTICE_ISSUED_SEC32",
                "ASSIGNED",
                "TRIAGED",
                "SUBMITTED",
            ])
        )


    # Risk level filter
    if risk_level and risk_level != "ALL":
        stmt = stmt.where(RiskAssessment.risk_level == risk_level.upper())

    # Search filter
    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            (Case.case_number.ilike(term))
            | (Product.product_name.ilike(term))
            | (Product.brand.ilike(term))
            | (Product.category.ilike(term))
            | (Case.title.ilike(term))
        )

    # Sorting
    is_asc = sort_order.lower() == "asc"
    if sort_by == "submission_date":
        stmt = stmt.order_by(Case.created_at.asc() if is_asc else Case.created_at.desc())
    elif sort_by == "confidence":
        col = RiskAssessment.confidence_score
        stmt = stmt.order_by(col.asc().nulls_last() if is_asc else col.desc().nulls_last())
    else:  # default: risk_score
        col = RiskAssessment.risk_score
        stmt = stmt.order_by(col.asc().nulls_last() if is_asc else col.desc().nulls_last())

    # Execute
    results = (await db.execute(stmt)).all()
    total_count = len(results)
    sliced_results = results[offset : offset + limit]

    items: List[PriorityQueueItem] = []
    for case_obj, prod_obj, risk_obj, user_obj in sliced_results:
        findings_count = 0
        if risk_obj and risk_obj.score_breakdown and isinstance(risk_obj.score_breakdown, dict):
            factors = risk_obj.score_breakdown.get("contributing_factors", [])
            findings_count = sum(f.get("finding_count", 0) for f in factors if isinstance(f, dict))

        items.append(
            PriorityQueueItem(
                case_id=case_obj.id,
                case_number=case_obj.case_number,
                product_id=prod_obj.id,
                product_name=prod_obj.product_name,
                brand=prod_obj.brand,
                category=prod_obj.category,
                risk_score=float(risk_obj.risk_score) if risk_obj else 0.0,
                risk_level=risk_obj.risk_level if risk_obj else "LOW",
                confidence=float(risk_obj.confidence_score) if risk_obj else 0.5,
                submission_date=case_obj.created_at,
                status=case_obj.status,
                priority=case_obj.priority,
                title=case_obj.title,
                assigned_officer=user_obj.full_name if user_obj else None,
                assigned_user_id=case_obj.assigned_user_id,
                total_findings=findings_count,
            )
        )

    return PriorityQueueResponse(
        items=items,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )



# ---------------------------------------------------------------------------
# 3. General List Cases Endpoint
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=List[RecentCaseItem],
    summary="List Regulatory Cases",
    description="Retrieve all surveillance cases with optional status, priority, and risk tier filters.",
)
async def list_cases(
    limit: int = Query(default=30, ge=1, le=100),
    case_status: Optional[str] = Query(default=None, alias="status"),
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Case, Product, RiskAssessment)
        .join(Product, Case.product_id == Product.id)
        .outerjoin(RiskAssessment, RiskAssessment.case_id == Case.id)
        .order_by(desc(Case.created_at))
        .limit(limit)
    )

    if case_status:
        stmt = stmt.where(Case.status == case_status.upper())

    results = (await db.execute(stmt)).all()

    items: List[RecentCaseItem] = []
    for case_obj, prod_obj, risk_obj in results:
        items.append(
            RecentCaseItem(
                case_id=case_obj.id,
                case_number=case_obj.case_number,
                product_name=prod_obj.product_name,
                brand=prod_obj.brand,
                category=prod_obj.category,
                submission_date=case_obj.created_at,
                risk_level=risk_obj.risk_level if risk_obj else "LOW",
                risk_score=risk_obj.risk_score if risk_obj else 0.0,
                status=case_obj.status,
                priority=case_obj.priority,
                title=case_obj.title,
            )
        )
    return items


# ---------------------------------------------------------------------------
# 4. Dynamic Parameterized Routes (/{case_id})
# ---------------------------------------------------------------------------
@router.get(
    "/{case_id}",
    response_model=CaseDetailResponse,
    summary="Get Case Details by ID",
    description="Retrieves comprehensive case details with linked product, sources, and stored image evidence.",
)
async def get_case_by_id(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Case).where(Case.id == case_id)
    result = await db.execute(stmt)
    case_obj = result.scalar_one_or_none()

    if not case_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )

    # Load product
    prod_stmt = select(Product).where(Product.id == case_obj.product_id)
    prod_res = await db.execute(prod_stmt)
    product_obj = prod_res.scalar_one_or_none()

    # Load sources
    src_stmt = (
        select(ProductSource)
        .where(ProductSource.product_id == case_obj.product_id)
        .order_by(desc(ProductSource.created_at))
    )
    sources = (await db.execute(src_stmt)).scalars().all()

    # Load images
    img_stmt = (
        select(ProductImage)
        .where(ProductImage.product_id == case_obj.product_id)
        .order_by(desc(ProductImage.created_at))
    )
    images = (await db.execute(img_stmt)).scalars().all()

    # Transform sources to guarantee raw_content is populated from payload json
    source_responses: List[SourceResponse] = []
    for s in sources:
        raw_c = s.raw_content
        if not raw_c and isinstance(s.raw_payload_json, dict):
            raw_c = s.raw_payload_json.get("raw_content")
        source_responses.append(
            SourceResponse(
                id=s.id,
                source_type=s.source_type,
                source_url=s.source_url,
                platform_name=s.platform_name,
                raw_content=raw_c,
                created_at=s.created_at,
            )
        )

    image_responses: List[ProductImageResponse] = []
    for i in images:
        image_responses.append(
            ProductImageResponse(
                id=i.id,
                image_type=i.image_type,
                storage_uri=i.storage_uri,
                sha256_hash=i.sha256_hash,
                file_size_bytes=i.file_size_bytes,
                mime_type=i.mime_type,
                created_at=i.created_at,
            )
        )

    return CaseDetailResponse(
        id=case_obj.id,
        case_number=case_obj.case_number,
        status=case_obj.status,
        priority=case_obj.priority,
        title=case_obj.title,
        description=case_obj.description,
        jurisdiction_district=case_obj.jurisdiction_district,
        created_at=case_obj.created_at,
        updated_at=case_obj.updated_at,
        product=ProductSimpleRead.model_validate(product_obj) if product_obj else None,
        sources=source_responses,
        images=image_responses,
    )


@router.post(
    "/{case_id}/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Product Source to Existing Case",
    description="Appends a new product source (URL, Description, Market record) to an existing case.",
)
async def add_source_to_case(
    case_id: uuid.UUID,
    payload: SourceAddRequest,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Case).where(Case.id == case_id)
    case_obj = (await db.execute(stmt)).scalar_one_or_none()

    if not case_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )

    if payload.source_url and not validate_url(payload.source_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid URL '{payload.source_url}'.",
        )

    source = ProductSource(
        product_id=case_obj.product_id,
        source_type=payload.source_type,
        source_url=payload.source_url,
        platform_name=payload.platform_name or "Officer Supplementary Source",
        raw_payload_json={
            "raw_content": payload.raw_content,
            **(payload.source_metadata or {}),
        },
    )
    db.add(source)

    audit = AuditLog(
        case_id=case_obj.id,
        user_id=current_user.id,
        action="SOURCE_ADDED",
        entity_type="ProductSource",
        entity_id=str(source.id),
        details_json={"source_type": payload.source_type},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(source)

    return SourceResponse(
        id=source.id,
        source_type=source.source_type,
        source_url=source.source_url,
        platform_name=source.platform_name,
        raw_content=payload.raw_content,
        created_at=source.created_at,
    )


@router.post(
    "/{case_id}/images",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Image to Existing Case",
    description="Uploads and stores an image with SHA-256 digest linked to the case's product.",
)
async def upload_image_to_case(
    case_id: uuid.UUID,
    file: UploadFile = File(...),
    image_type: str = Form(default="PRODUCT_IMAGE"),
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Case).where(Case.id == case_id)
    case_obj = (await db.execute(stmt)).scalar_one_or_none()

    if not case_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )

    meta = await save_uploaded_image(file, case_obj.id, image_type=image_type)

    img_record = ProductImage(
        product_id=case_obj.product_id,
        image_type=image_type,
        storage_uri=meta["storage_uri"],
        sha256_hash=meta["file_hash_sha256"],
        file_size_bytes=meta["file_size_bytes"],
        mime_type=meta["mime_type"],
    )
    db.add(img_record)

    audit = AuditLog(
        case_id=case_obj.id,
        user_id=current_user.id,
        action="IMAGE_ADDED",
        entity_type="ProductImage",
        entity_id=str(img_record.id),
        details_json={"image_type": image_type, "sha256": meta["file_hash_sha256"]},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(img_record)

    return ProductImageResponse(
        id=img_record.id,
        image_type=img_record.image_type,
        storage_uri=img_record.storage_uri,
        sha256_hash=img_record.sha256_hash,
        file_size_bytes=img_record.file_size_bytes,
        mime_type=img_record.mime_type,
        created_at=img_record.created_at,
    )


# ---------------------------------------------------------------------------
# 5. Phase 7: Image Processing and OCR Pipeline Endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/{case_id}/images/{image_id}/ocr",
    response_model=OCRResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger OCR on Case Image",
    description="Processes packaging/product image through the preprocessing and OCR pipeline, extracting text and storing results.",
)
async def process_image_ocr(
    case_id: uuid.UUID,
    image_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.services.ocr.service import OCRService

    try:
        res = await OCRService.process_case_image(
            case_id=case_id,
            image_id=image_id,
            db=db,
            current_user_id=current_user.id,
        )
        return res
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{case_id}/images/{image_id}/ocr",
    response_model=OCRResultResponse,
    summary="Get OCR Results for Image",
    description="Retrieves the stored OCR extraction record and confidence score for a specific product image.",
)
async def get_image_ocr(
    case_id: uuid.UUID,
    image_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.models.product import ExtractedInformation
    from app.schemas.ocr import ImageQualityAssessment, OCRLine, OCRResultResponse

    # Verify case
    case_stmt = select(Case).where(Case.id == case_id)
    case_obj = (await db.execute(case_stmt)).scalar_one_or_none()
    if not case_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found.",
        )

    # Fetch latest OCR extraction for image
    stmt = (
        select(ExtractedInformation)
        .where(
            ExtractedInformation.product_id == case_obj.product_id,
            ExtractedInformation.image_id == image_id,
            ExtractedInformation.zone_type == "OCR_FULL_TEXT",
        )
        .order_by(desc(ExtractedInformation.created_at))
    )
    record = (await db.execute(stmt)).scalars().first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No OCR record found for image '{image_id}'. Please trigger OCR first via POST /{case_id}/images/{image_id}/ocr.",
        )

    parsed = record.parsed_data or {}
    q_data = parsed.get("quality_assessment") or {}
    quality = ImageQualityAssessment(
        is_blurry=q_data.get("is_blurry", False),
        sharpness_score=q_data.get("sharpness_score", 0.0),
        width=q_data.get("width", 0),
        height=q_data.get("height", 0),
        aspect_ratio=q_data.get("aspect_ratio", 1.0),
        channels=q_data.get("channels", 3),
        quality_grade=q_data.get("quality_grade", "ACCEPTABLE"),
        warnings=q_data.get("warnings", []),
    )

    lines = [OCRLine(**l) for l in parsed.get("lines", [])]

    return OCRResultResponse(
        extracted_info_id=record.id,
        case_id=case_id,
        image_id=image_id,
        product_id=case_obj.product_id,
        zone_type=record.zone_type,
        raw_text=record.raw_text,
        confidence_score=record.confidence_score or 0.0,
        quality_assessment=quality,
        lines=lines,
        word_count=parsed.get("word_count", len(record.raw_text.split())),
        character_count=parsed.get("character_count", len(record.raw_text)),
        extractor_version=record.extractor_version or "DRISHTI-OCR",
        status=parsed.get("processing_status", "SUCCESS"),
        created_at=record.created_at,
    )


@router.get(
    "/{case_id}/ocr",
    response_model=CaseOCRSummaryResponse,
    summary="Get All OCR Results for Case",
    description="Aggregates all extracted packaging text and confidence scores across images linked to the case.",
)
async def get_case_ocr_summary(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.models.product import ExtractedInformation
    from app.schemas.ocr import CaseOCRSummaryResponse, ImageQualityAssessment, OCRLine, OCRResultResponse

    case_stmt = select(Case).where(Case.id == case_id)
    case_obj = (await db.execute(case_stmt)).scalar_one_or_none()
    if not case_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found.",
        )

    # Count total images linked to product
    img_count_stmt = select(func.count(ProductImage.id)).where(ProductImage.product_id == case_obj.product_id)
    total_images = (await db.execute(img_count_stmt)).scalar() or 0

    # Fetch all OCR extractions
    stmt = (
        select(ExtractedInformation)
        .where(
            ExtractedInformation.product_id == case_obj.product_id,
            ExtractedInformation.zone_type == "OCR_FULL_TEXT",
        )
        .order_by(desc(ExtractedInformation.created_at))
    )
    records = (await db.execute(stmt)).scalars().all()

    results: List[OCRResultResponse] = []
    text_blocks: List[str] = []
    confs: List[float] = []

    for r in records:
        parsed = r.parsed_data or {}
        q_data = parsed.get("quality_assessment") or {}
        quality = ImageQualityAssessment(
            is_blurry=q_data.get("is_blurry", False),
            sharpness_score=q_data.get("sharpness_score", 0.0),
            width=q_data.get("width", 0),
            height=q_data.get("height", 0),
            aspect_ratio=q_data.get("aspect_ratio", 1.0),
            channels=q_data.get("channels", 3),
            quality_grade=q_data.get("quality_grade", "ACCEPTABLE"),
            warnings=q_data.get("warnings", []),
        )
        lines = [OCRLine(**l) for l in parsed.get("lines", [])]

        results.append(
            OCRResultResponse(
                extracted_info_id=r.id,
                case_id=case_id,
                image_id=r.image_id,
                product_id=case_obj.product_id,
                zone_type=r.zone_type,
                raw_text=r.raw_text,
                confidence_score=r.confidence_score or 0.0,
                quality_assessment=quality,
                lines=lines,
                word_count=parsed.get("word_count", len(r.raw_text.split())),
                character_count=parsed.get("character_count", len(r.raw_text)),
                extractor_version=r.extractor_version or "DRISHTI-OCR",
                status=parsed.get("processing_status", "SUCCESS"),
                created_at=r.created_at,
            )
        )
        if r.raw_text.strip():
            text_blocks.append(r.raw_text.strip())
        if r.confidence_score is not None:
            confs.append(r.confidence_score)

    avg_conf = round(sum(confs) / max(len(confs), 1), 2) if confs else 0.0
    agg_text = "\n\n--- NEXT IMAGE ---\n\n".join(text_blocks)

    return CaseOCRSummaryResponse(
        case_id=case_id,
        case_number=case_obj.case_number,
        total_images=total_images,
        total_images_processed=len(results),
        average_confidence=avg_conf,
        aggregated_text=agg_text,
        results=results,
    )


# ---------------------------------------------------------------------------
# 6. Phase 8: Product Information Structuring and Intelligence Endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/{case_id}/structure-intelligence",
    response_model=CanonicalStructuredProduct,
    status_code=status.HTTP_200_OK,
    summary="Structure Case Product Intelligence",
    description="Transforms multi-source evidence (URL, packaging OCR, descriptions) into canonical structured data with source tracking and deduplication.",
)
async def structure_product_intelligence(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.services.intelligence.service import ProductIntelligenceService

    try:
        canonical_product = await ProductIntelligenceService.structure_case_information(
            case_id=case_id,
            db=db,
            current_user_id=current_user.id,
        )
        return canonical_product
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{case_id}/structure-intelligence",
    response_model=CanonicalStructuredProduct,
    summary="Get Structured Product Intelligence Dossier",
    description="Retrieves the latest structured canonical product intelligence dossier for a regulatory case.",
)
async def get_structured_product_intelligence(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.models.product import ExtractedInformation
    from app.services.intelligence.service import ProductIntelligenceService

    # Check case
    case_stmt = select(Case).where(Case.id == case_id)
    case_obj = (await db.execute(case_stmt)).scalar_one_or_none()
    if not case_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found.",
        )

    # Fetch latest canonical structured record
    stmt = (
        select(ExtractedInformation)
        .where(
            ExtractedInformation.product_id == case_obj.product_id,
            ExtractedInformation.zone_type == "CANONICAL_STRUCTURED_DATA",
        )
        .order_by(desc(ExtractedInformation.created_at))
    )
    record = (await db.execute(stmt)).scalars().first()

    if not record or not record.parsed_data:
        # If not structured yet, run the structuring pipeline on-demand
        return await ProductIntelligenceService.structure_case_information(
            case_id=case_id,
            db=db,
            current_user_id=current_user.id,
        )

    return CanonicalStructuredProduct.model_validate(record.parsed_data)


# ---------------------------------------------------------------------------
# 7. Phase 9: Deep Product Analysis Modules Endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/{case_id}/deep-analysis",
    response_model=DeepAnalysisReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Deep Modular Product Analysis",
    description="Runs all 5 deep analysis modules (License, Ingredient, Claim, Packaging, Manufacturer) and stores structured findings.",
)
async def run_deep_analysis(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.services.analysis.orchestrator import DeepAnalysisOrchestrator

    try:
        report = await DeepAnalysisOrchestrator.run_analysis(
            case_id=case_id,
            db=db,
            current_user_id=current_user.id,
        )
        return report
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{case_id}/deep-analysis",
    response_model=DeepAnalysisReportResponse,
    summary="Get Deep Product Analysis Report",
    description="Retrieves the latest deep modular compliance report across all 5 analytical dimensions.",
)
async def get_deep_analysis_report(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.services.analysis.orchestrator import DeepAnalysisOrchestrator

    # Case existence check
    case_stmt = select(Case).where(Case.id == case_id)
    case_obj = (await db.execute(case_stmt)).scalar_one_or_none()
    if not case_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found.",
        )

    # Trigger or retrieve deep analysis
    try:
        report = await DeepAnalysisOrchestrator.run_analysis(
            case_id=case_id,
            db=db,
            current_user_id=current_user.id,
        )
        return report
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# 8. Phase 10: Cross-Source Consistency Intelligence Endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/{case_id}/consistency-check",
    response_model=ConsistencyReport,
    status_code=status.HTTP_200_OK,
    summary="Run Cross-Source Consistency Analysis",
    description="Compares product information across all evidence sources to detect inconsistencies.",
)
async def run_consistency_check(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.services.consistency.service import ConsistencyAnalysisService

    try:
        report = await ConsistencyAnalysisService.run_consistency_check(
            case_id=case_id,
            db=db,
            current_user_id=current_user.id,
        )
        return report
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{case_id}/consistency-check",
    response_model=ConsistencyReport,
    summary="Get Cross-Source Consistency Report",
    description="Retrieves the latest cross-source consistency analysis report for a case.",
)
async def get_consistency_report(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.services.consistency.service import ConsistencyAnalysisService

    try:
        report = await ConsistencyAnalysisService.run_consistency_check(
            case_id=case_id,
            db=db,
            current_user_id=current_user.id,
        )
        return report
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# 9. Phase 11: Risk Intelligence Engine Endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/{case_id}/risk-assessment",
    response_model=RiskAssessmentReport,
    status_code=status.HTTP_200_OK,
    summary="Compute Product Compliance Risk Score",
    description=(
        "Runs the Risk Intelligence Engine to produce an internal case prioritization score. "
        "This is NOT a legal compliance determination or official government score."
    ),
)
async def run_risk_assessment(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.services.risk_engine.service import RiskIntelligenceService

    try:
        report = await RiskIntelligenceService.compute_risk(
            case_id=case_id,
            db=db,
            current_user_id=current_user.id,
        )
        return report
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{case_id}/risk-assessment",
    response_model=RiskAssessmentReport,
    summary="Get Risk Assessment Report",
    description="Retrieves the latest risk assessment for a case.",
)
async def get_risk_assessment(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.services.risk_engine.service import RiskIntelligenceService

    try:
        report = await RiskIntelligenceService.compute_risk(
            case_id=case_id,
            db=db,
            current_user_id=current_user.id,
        )
        return report
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# 9b. Phase B2: End-to-End Regulatory Analysis Pipeline Endpoint
# ---------------------------------------------------------------------------
@router.post(
    "/{case_id}/run-analysis",
    response_model=CasePipelineResult,
    status_code=status.HTTP_200_OK,
    summary="Execute Complete End-to-End Statutory Analysis Pipeline",
    description=(
        "Orchestrates full automated statutory surveillance: "
        "SUBMITTED -> EXTRACTING (OCR) -> STRUCTURING -> ANALYZING (Deep Analysis + Consistency) "
        "-> RISK_ASSESSMENT -> ANALYSIS_COMPLETE. Idempotent and safely rerunnable."
    ),
)
async def run_case_analysis_pipeline(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.services.case_pipeline import CasePipelineService

    try:
        result = await CasePipelineService.run_pipeline(
            case_id=case_id,
            db=db,
            current_user_id=current_user.id,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# 10. Phase 12: Explainability Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/{case_id}/explanation",
    response_model=ExplanationReport,
    summary="Get Case Explainability Report",
    description=(
        "Returns a fully traceable explanation report: product info, detected findings "
        "with verbatim evidence, risk score breakdown, and why-flagged summary. "
        "All explanations reference stored evidence records only."
    ),
)
async def get_case_explanation(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.services.explainability.service import ExplainabilityService

    try:
        report = await ExplainabilityService.explain_case(
            case_id=case_id,
            db=db,
        )
        return report
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# 11. Phase 13: Evidence Management System Endpoints
# ---------------------------------------------------------------------------
@router.get(
    "/{case_id}/evidence-package",
    response_model=CaseEvidencePackage,
    summary="Get Case Evidence Package",
    description=(
        "Returns the complete statutory Evidence Package for a case: Product URLs, "
        "Product & Packaging Images (with SHA-256 hashes), OCR text, Product description, "
        "Extracted claims, Extracted data, Analysis results, Source metadata, and Timestamps. "
        "Every finding is linked to primary evidence with strict segregation of AI analysis notes."
    ),
)
async def get_case_evidence_package(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.services.evidence import EvidencePackageBuilder

    try:
        package = await EvidencePackageBuilder.build(case_id=case_id, db=db)
        return package
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/{case_id}/evidence-package/verify",
    response_model=EvidenceIntegrityCheckResult,
    summary="Verify Evidence Cryptographic & Statutory Integrity",
    description=(
        "Executes automated cryptographic and statutory integrity checks: "
        "verifies SHA-256 image hashes, finding-to-evidence linkage (100% coverage), "
        "strict absence of AI statements in primary evidence, and timestamp monotonicity."
    ),
)
async def verify_evidence_integrity(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.services.evidence import EvidencePackageBuilder, EvidenceIntegrityChecker

    try:
        package = await EvidencePackageBuilder.build(case_id=case_id, db=db)
        verification = EvidenceIntegrityChecker.verify(package)
        return verification
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# 12. Phase 14: Authority Review & Case Management Endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/{case_id}/start-review",
    response_model=CaseRead,
    summary="Start Authority Case Review",
    description="Transitions case status to UNDER_REVIEW and assigns it to the authenticated authority officer.",
)
async def start_case_review(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    case_stmt = select(Case).where(Case.id == case_id)
    case_obj = (await db.execute(case_stmt)).scalar_one_or_none()
    if not case_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )

    prev_status = case_obj.status
    case_obj.status = "UNDER_REVIEW"
    case_obj.assigned_user_id = current_user.id
    now = datetime.now(timezone.utc)

    audit = AuditLog(
        case_id=case_obj.id,
        user_id=current_user.id,
        action="CASE_REVIEW_STARTED",
        entity_type="Case",
        entity_id=str(case_obj.id),
        details_json={
            "previous_status": prev_status,
            "new_status": "UNDER_REVIEW",
            "assigned_officer": current_user.full_name,
            "badge_id": current_user.badge_id,
        },
        created_at=now,
    )
    db.add(audit)
    await db.commit()
    await db.refresh(case_obj)
    return CaseRead.model_validate(case_obj)


@router.post(
    "/{case_id}/reviews",
    response_model=CaseReviewRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Authority Review Determination & Notes",
    description=(
        "Records statutory officer review notes and regulatory determination "
        "(e.g., Section 32 Notice, Inspection Order, Dismissal). "
        "Separates human authority decisions from automated AI findings with audit logging."
    ),
)
async def submit_case_review(
    case_id: uuid.UUID,
    payload: CaseReviewSubmission,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    case_stmt = select(Case).where(Case.id == case_id)
    case_obj = (await db.execute(case_stmt)).scalar_one_or_none()
    if not case_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )

    now = datetime.now(timezone.utc)
    prev_status = case_obj.status

    # Create immutable CaseReview record
    review = CaseReview(
        id=uuid.uuid4(),
        case_id=case_obj.id,
        reviewer_id=current_user.id,
        review_action=payload.review_action,
        remarks=payload.remarks,
        action_metadata=payload.action_metadata,
        created_at=now,
        updated_at=now,
    )
    db.add(review)

    # Update case status based on determination
    new_status = payload.new_status or "REVIEW_COMPLETED"
    case_obj.status = new_status
    if new_status in ("RESOLVED", "CLOSED", "DISMISS_CASE"):
        case_obj.closed_at = now

    audit = AuditLog(
        case_id=case_obj.id,
        user_id=current_user.id,
        action="AUTHORITY_REVIEW_SUBMITTED",
        entity_type="CaseReview",
        entity_id=str(review.id),
        details_json={
            "review_action": payload.review_action,
            "remarks": payload.remarks,
            "previous_case_status": prev_status,
            "new_case_status": new_status,
            "reviewer_name": current_user.full_name,
            "reviewer_badge": current_user.badge_id,
        },
        created_at=now,
    )
    db.add(audit)
    await db.commit()
    await db.refresh(review)

    return CaseReviewRead.model_validate(review)


@router.patch(
    "/{case_id}/status",
    response_model=CaseRead,
    summary="Update Case Lifecycle Status",
    description="Statutory case status transition exclusively callable by authorized officers with audit logging.",
)
async def update_case_status(
    case_id: uuid.UUID,
    payload: CaseStatusUpdate,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    case_stmt = select(Case).where(Case.id == case_id)
    case_obj = (await db.execute(case_stmt)).scalar_one_or_none()
    if not case_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )

    prev_status = case_obj.status
    case_obj.status = payload.status
    now = datetime.now(timezone.utc)
    if payload.status in ("RESOLVED", "CLOSED"):
        case_obj.closed_at = now

    audit = AuditLog(
        case_id=case_obj.id,
        user_id=current_user.id,
        action="CASE_STATUS_UPDATED",
        entity_type="Case",
        entity_id=str(case_obj.id),
        details_json={
            "previous_status": prev_status,
            "new_status": payload.status,
            "reason": payload.reason,
            "notes": payload.notes,
            "officer_badge": current_user.badge_id,
        },
        created_at=now,
    )
    db.add(audit)
    await db.commit()
    await db.refresh(case_obj)
    return CaseRead.model_validate(case_obj)


# ---------------------------------------------------------------------------
# 13. Phase 15: Evidence-Backed Compliance Case Report Generation
# ---------------------------------------------------------------------------
@router.get(
    "/{case_id}/report/data",
    response_model=CaseComplianceReportData,
    summary="Get Structured Product Compliance Risk Intelligence Report Data",
    description="Returns the full 8-section evidence-backed compliance report model in JSON format.",
)
async def get_compliance_report_data(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.services.reporting.builder import ComplianceReportBuilder

    try:
        report_data = await ComplianceReportBuilder.build_report_data(case_id=case_id, db=db)
        return report_data
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{case_id}/report/html",
    response_class=HTMLResponse,
    summary="Generate HTML Product Compliance Risk Intelligence Report",
    description="Renders official styled HTML compliance dossier with mandatory statutory disclaimer.",
)
async def get_compliance_report_html(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.services.reporting.builder import ComplianceReportBuilder
    from app.services.reporting.html_generator import HtmlReportGenerator

    try:
        report_data = await ComplianceReportBuilder.build_report_data(case_id=case_id, db=db)
        html_content = HtmlReportGenerator.generate_html(report_data)

        # Audit log entry
        audit = AuditLog(
            case_id=case_id,
            user_id=current_user.id,
            action="REPORT_GENERATED_HTML",
            entity_type="Report",
            entity_id=report_data.report_identifier,
            details_json={
                "report_id": report_data.report_identifier,
                "case_number": report_data.case_info.case_number,
                "risk_score": report_data.risk_assessment.risk_score,
                "risk_level": report_data.risk_assessment.risk_level,
                "findings_count": len(report_data.detected_findings),
                "officer_badge": current_user.badge_id,
            },
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit)
        await db.commit()

        return HTMLResponse(content=html_content)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{case_id}/report/pdf",
    summary="Download Official PDF Product Compliance Risk Intelligence Report",
    description="Streams publication-quality binary PDF compliance report generated via ReportLab.",
)
async def download_compliance_report_pdf(
    case_id: uuid.UUID,
    current_user: User = Depends(require_authority_officer),
    db: AsyncSession = Depends(get_db),
):
    from app.services.reporting.builder import ComplianceReportBuilder
    from app.services.reporting.pdf_generator import PdfReportGenerator

    try:
        report_data = await ComplianceReportBuilder.build_report_data(case_id=case_id, db=db)
        pdf_bytes = PdfReportGenerator.generate_pdf(report_data)

        # Audit log entry
        audit = AuditLog(
            case_id=case_id,
            user_id=current_user.id,
            action="REPORT_GENERATED_PDF",
            entity_type="Report",
            entity_id=report_data.report_identifier,
            details_json={
                "report_id": report_data.report_identifier,
                "case_number": report_data.case_info.case_number,
                "risk_score": report_data.risk_assessment.risk_score,
                "risk_level": report_data.risk_assessment.risk_level,
                "findings_count": len(report_data.detected_findings),
                "pdf_byte_size": len(pdf_bytes),
                "officer_badge": current_user.badge_id,
            },
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit)
        await db.commit()

        filename = f"DRISHTI-Report-{report_data.case_info.case_number}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "application/pdf",
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{case_id}/audit-trail",
    response_model=CaseAuditTrailResponse,
    summary="Get chronological case audit trail",
    description="Retrieve complete, tamper-evident audit history of all regulatory actions, status transitions, triage events, and report downloads for a case. Requires AUTHORITY_OFFICER or higher.",
)
async def get_case_audit_trail(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_authority_officer),
) -> CaseAuditTrailResponse:
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )

    stmt = (
        select(AuditLog)
        .where(AuditLog.case_id == case_id)
        .order_by(AuditLog.created_at.asc())
    )
    result = await db.execute(stmt)
    audit_logs = result.scalars().all()

    return CaseAuditTrailResponse(
        case_id=case.id,
        case_number=case.case_number,
        total_events=len(audit_logs),
        events=audit_logs,
    )




