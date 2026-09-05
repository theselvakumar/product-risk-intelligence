"""
Phase 17: Complete End-to-End Regulatory Integration Test Suite.
Verifies the complete 13-stage statutory surveillance lifecycle:
Authority Login -> Dashboard -> Submit Product -> Ingestion & Storage ->
OCR Processing -> Information Structuring -> Deep Analysis -> Consistency ->
Risk Scoring -> Explainability -> Evidence Package & Integrity ->
Priority Queue -> Authority Review -> Report Generation -> Audit Trail Security.
"""

import io
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import hash_password
from app.database.session import get_db
from app.main import app
from app.models.base import Base
from app.models.case import AuditLog
from app.models.user import User

TEST_DB_FILE = "test_e2e_integration.db"
TEST_ASYNC_URL = f"sqlite+aiosqlite:///./{TEST_DB_FILE}"

async_test_engine = create_async_engine(TEST_ASYNC_URL, echo=False)
AsyncTestingSessionLocal = async_sessionmaker(
    bind=async_test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

E2E_OFFICER_ID = uuid.uuid4()
E2E_OFFICER_EMAIL = "e2e.inspector@drishti.gov.in"
E2E_OFFICER_PASSWORD = "StatutoryOfficer2026!"
E2E_OFFICER_BADGE = "FSO-DEL-INTEG-001"


def create_clear_label_image() -> bytes:
    """Create a high-contrast, valid packaging label image for OCR decoding."""
    img = Image.new("RGB", (600, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    text = "INGREDIENTS: Pure Shilajit Extract, Ashwagandha, Gold Vark.\nFSSAI Lic. No: 10020011000543\nBatch: VED-2026"
    draw.text((20, 30), text, fill=(0, 0, 0))
    img.info["text"] = text

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


@pytest.fixture(scope="module", autouse=True)
def setup_e2e_test_db():
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass

    import asyncio

    async def init_tables():
        async with async_test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with AsyncTestingSessionLocal() as session:
            officer = User(
                id=E2E_OFFICER_ID,
                email=E2E_OFFICER_EMAIL,
                full_name="Dr. Shweta Mukherjee",
                badge_id=E2E_OFFICER_BADGE,
                role="AUTHORITY_OFFICER",
                jurisdiction_state="DL",
                jurisdiction_district="DL-CENTRAL",
                is_active=True,
                hashed_password=hash_password(E2E_OFFICER_PASSWORD),
            )
            session.add(officer)
            await session.commit()

    asyncio.run(init_tables())

    yield

    async def drop_tables():
        async with async_test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await async_test_engine.dispose()

    asyncio.run(drop_tables())

    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass


@pytest.fixture
def client():
    async def override_get_db():
        async with AsyncTestingSessionLocal() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_complete_end_to_end_statutory_workflow(client):
    """
    Executes and validates the entire 13-stage regulatory workflow in sequence
    against a live SQLite database with real cryptographic digests and state transitions.
    """

    # -----------------------------------------------------------------------
    # STAGE 1: Authority Login & JWT Issuance
    # -----------------------------------------------------------------------
    login_res = client.post("/auth/login", json={
        "email": E2E_OFFICER_EMAIL,
        "password": E2E_OFFICER_PASSWORD,
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    token = login_data["access_token"]
    assert token is not None
    assert login_data["user"]["badge_id"] == E2E_OFFICER_BADGE

    auth_headers = {"Authorization": f"Bearer {token}"}

    # -----------------------------------------------------------------------
    # STAGE 2: Authority Dashboard & Operational Telemetry
    # -----------------------------------------------------------------------
    metrics_res = client.get(f"{settings.API_V1_STR}/cases/metrics", headers=auth_headers)
    assert metrics_res.status_code == 200
    metrics = metrics_res.json()
    assert "total_cases" in metrics
    assert "pending_review" in metrics

    # -----------------------------------------------------------------------
    # STAGE 3: Product Ingestion & Case Creation (URL + Image + Description)
    # -----------------------------------------------------------------------
    real_img = create_clear_label_image()
    files = [
        ("packaging_images", ("front_pack.jpg", io.BytesIO(real_img), "image/jpeg")),
    ]
    submission_data = {
        "product_name": "Vedic Vitality Pure Shilajit Gold",
        "brand": "VedicHerbs Naturals",
        "category": "HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS",
        "product_url": "https://vedicherbs.in/products/pure-shilajit-resin",
        "product_description": (
            "100% Himalayan Pure Shilajit Resin. Clinically proven to reverse diabetes, "
            "eliminate arthritis pain permanently, and cure all chronic fatigue within 7 days. "
            "Zero sugar, approved by Ayurvedic Ministry."
        ),
        "fssai_license_number": "10020011000543",
        "notes": "Targeted surveillance on egregious therapeutic claims under FSSA 2006 Section 24.",
    }
    sub_res = client.post(
        f"{settings.API_V1_STR}/cases",
        data=submission_data,
        files=files,
        headers=auth_headers,
    )
    assert sub_res.status_code == 201
    sub_json = sub_res.json()
    case_id = sub_json["case_id"]
    case_number = sub_json["case_number"]
    assert sub_json["status"] == "SUBMITTED"
    assert sub_json["sources_count"] >= 3
    assert sub_json["images_count"] >= 1

    # -----------------------------------------------------------------------
    # STAGE 4: Image Retrieval & Multi-Zone OCR Processing
    # -----------------------------------------------------------------------
    case_detail_res = client.get(f"{settings.API_V1_STR}/cases/{case_id}", headers=auth_headers)
    assert case_detail_res.status_code == 200
    images = case_detail_res.json()["images"]
    assert len(images) >= 1
    image_id = images[0]["id"]

    # Trigger OCR on the uploaded packaging image
    ocr_res = client.post(f"{settings.API_V1_STR}/cases/{case_id}/images/{image_id}/ocr", headers=auth_headers)
    assert ocr_res.status_code == 200
    ocr_data = ocr_res.json()
    assert ocr_data["case_id"] == case_id
    assert "confidence_score" in ocr_data

    # Retrieve case consolidated OCR summary
    ocr_summary_res = client.get(f"{settings.API_V1_STR}/cases/{case_id}/ocr", headers=auth_headers)
    assert ocr_summary_res.status_code == 200
    assert ocr_summary_res.json()["total_images_processed"] >= 1

    # -----------------------------------------------------------------------
    # STAGE 5: Product Information Structuring
    # -----------------------------------------------------------------------
    struct_res = client.post(f"{settings.API_V1_STR}/cases/{case_id}/structure-intelligence", headers=auth_headers)
    assert struct_res.status_code == 200
    struct_data = struct_res.json()
    assert struct_data["case_id"] == case_id
    assert "product_metadata" in struct_data
    assert struct_data["product_metadata"]["name"]["value"] == "Vedic Vitality Pure Shilajit Gold"

    # -----------------------------------------------------------------------
    # STAGE 6: Deep Regulatory Analysis & Cross-Source Consistency
    # -----------------------------------------------------------------------
    deep_res = client.post(f"{settings.API_V1_STR}/cases/{case_id}/deep-analysis", headers=auth_headers)
    assert deep_res.status_code == 200
    deep_json = deep_res.json()
    assert deep_json["total_checks"] > 0
    assert deep_json["total_findings"] > 0
    assert "modules" in deep_json

    cons_res = client.post(f"{settings.API_V1_STR}/cases/{case_id}/consistency-check", headers=auth_headers)
    assert cons_res.status_code == 200
    cons_json = cons_res.json()
    assert cons_json["total_sources_analyzed"] >= 1
    assert "comparisons" in cons_json

    # -----------------------------------------------------------------------
    # STAGE 7: Risk Scoring Engine & Explainability Tree
    # -----------------------------------------------------------------------
    risk_res = client.post(f"{settings.API_V1_STR}/cases/{case_id}/risk-assessment", headers=auth_headers)
    assert risk_res.status_code == 200
    risk_json = risk_res.json()
    assert 0.0 <= risk_json["risk_score"] <= 1.0
    assert risk_json["risk_level"] in ("LOW", "MEDIUM", "HIGH")
    assert "contributing_factors" in risk_json

    exp_res = client.get(f"{settings.API_V1_STR}/cases/{case_id}/explanation", headers=auth_headers)
    assert exp_res.status_code == 200
    exp_json = exp_res.json()
    assert "why_flagged_summary" in exp_json
    assert "findings" in exp_json

    # -----------------------------------------------------------------------
    # STAGE 8: Evidence Package Assembly & Cryptographic Integrity Check
    # -----------------------------------------------------------------------
    pkg_res = client.get(f"{settings.API_V1_STR}/cases/{case_id}/evidence-package", headers=auth_headers)
    assert pkg_res.status_code == 200
    pkg_json = pkg_res.json()
    assert "finding_bundles" in pkg_json
    assert len(pkg_json["finding_bundles"]) >= 1

    integ_res = client.post(f"{settings.API_V1_STR}/cases/{case_id}/evidence-package/verify", headers=auth_headers)
    assert integ_res.status_code == 200
    integ_json = integ_res.json()
    assert integ_json["all_findings_linked"] is True
    assert integ_json["ai_separation_verified"] is True
    assert integ_json["hash_verification_passed"] is True

    # -----------------------------------------------------------------------
    # STAGE 9: Priority Review Queue Triage
    # -----------------------------------------------------------------------
    queue_res = client.get(f"{settings.API_V1_STR}/cases/priority-queue?search=Vedic", headers=auth_headers)
    assert queue_res.status_code == 200
    queue_items = queue_res.json()["items"]
    assert any(item["case_id"] == case_id for item in queue_items)

    # -----------------------------------------------------------------------
    # STAGE 10: Authority Review & Section 32 Improvement Notice
    # -----------------------------------------------------------------------
    # Start formal review
    start_res = client.post(f"{settings.API_V1_STR}/cases/{case_id}/start-review", headers=auth_headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "UNDER_REVIEW"

    # Submit statutory determination
    review_res = client.post(
        f"{settings.API_V1_STR}/cases/{case_id}/reviews",
        json={
            "review_action": "ISSUE_SECTION_32_NOTICE",
            "remarks": "Egregious disease cure claims verified. Improvement Notice issued under Section 32.",
            "new_status": "NOTICE_ISSUED_SEC32",
            "action_metadata": {
                "act": "FSSA 2006",
                "section": "32",
                "compliance_days": 14,
            },
        },
        headers=auth_headers,
    )
    assert review_res.status_code == 201
    assert review_res.json()["review_action"] == "ISSUE_SECTION_32_NOTICE"

    # Verify updated case state
    check_case = client.get(f"{settings.API_V1_STR}/cases/{case_id}", headers=auth_headers)
    assert check_case.status_code == 200
    assert check_case.json()["status"] == "NOTICE_ISSUED_SEC32"

    # -----------------------------------------------------------------------
    # STAGE 11: Compliance Report Generation (JSON, HTML & PDF)
    # -----------------------------------------------------------------------
    # 1. JSON
    rep_data_res = client.get(f"{settings.API_V1_STR}/cases/{case_id}/report/data", headers=auth_headers)
    assert rep_data_res.status_code == 200
    rep_json = rep_data_res.json()
    assert rep_json["product_info"]["product_name"] == "Vedic Vitality Pure Shilajit Gold"
    assert "mandatory_statutory_disclaimer" in rep_json
    assert "AI-assisted decision-support assessment" in rep_json["mandatory_statutory_disclaimer"]

    # 2. HTML
    rep_html_res = client.get(f"{settings.API_V1_STR}/cases/{case_id}/report/html", headers=auth_headers)
    assert rep_html_res.status_code == 200
    assert "text/html" in rep_html_res.headers["content-type"]
    assert "PRODUCT COMPLIANCE RISK INTELLIGENCE REPORT" in rep_html_res.text

    # 3. PDF
    rep_pdf_res = client.get(f"{settings.API_V1_STR}/cases/{case_id}/report/pdf", headers=auth_headers)
    assert rep_pdf_res.status_code == 200
    assert rep_pdf_res.headers["content-type"] == "application/pdf"
    assert rep_pdf_res.content[:4] == b"%PDF"
    assert len(rep_pdf_res.content) > 1000

    # -----------------------------------------------------------------------
    # STAGE 12: Chronological Audit Trail & Zero-Exposure Security Audit
    # -----------------------------------------------------------------------
    trail_res = client.get(f"{settings.API_V1_STR}/cases/{case_id}/audit-trail", headers=auth_headers)
    assert trail_res.status_code == 200
    trail_json = trail_res.json()
    assert trail_json["case_id"] == case_id
    assert trail_json["total_events"] >= 5

    logged_actions = [ev["action"] for ev in trail_json["events"]]
    assert "CASE_CREATED" in logged_actions
    assert "PRODUCT_SUBMITTED" in logged_actions
    assert "AUTHORITY_REVIEW_SUBMITTED" in logged_actions
    assert "REPORT_GENERATED_PDF" in logged_actions

    # Direct database audit log inspection: zero sensitive data exposure
    import asyncio

    async def verify_db_audit():
        async with AsyncTestingSessionLocal() as session:
            stmt = select(AuditLog).where(AuditLog.case_id == uuid.UUID(case_id))
            res = await session.execute(stmt)
            logs = res.scalars().all()
            assert len(logs) >= 5
            for l in logs:
                det = l.details_json or {}
                assert "password" not in det
                assert "hashed_password" not in det
                assert "token" not in det
                assert "access_token" not in det
                assert "secret" not in det

    asyncio.run(verify_db_audit())
