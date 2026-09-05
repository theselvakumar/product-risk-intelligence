"""Tests for Phase 15: Evidence-Backed Case Report Generation (HTML & PDF)."""

import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.database.session import get_db
from app.main import app
from app.models.base import Base
from app.models.case import AuditLog, Case
from app.models.user import User
from app.services.reporting.builder import ComplianceReportBuilder
from app.services.reporting.html_generator import HtmlReportGenerator
from app.services.reporting.pdf_generator import PdfReportGenerator

TEST_DB_FILE = "test_report_generation.db"
TEST_ASYNC_URL = f"sqlite+aiosqlite:///./{TEST_DB_FILE}"

async_test_engine = create_async_engine(TEST_ASYNC_URL, echo=False)
AsyncTestingSessionLocal = async_sessionmaker(
    bind=async_test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
test_officer_id = uuid.uuid4()


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass

    import asyncio

    async def init():
        async with async_test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with AsyncTestingSessionLocal() as session:
            session.add(User(
                id=test_officer_id,
                email="officer.reporting@drishti.gov.in",
                full_name="Rajiv Menon",
                badge_id="FSO-DL-CEN-007",
                role="AUTHORITY_OFFICER",
                jurisdiction_state="DL",
                jurisdiction_district="DL-CEN",
                is_active=True,
                hashed_password=hash_password("Password123!"),
            ))
            await session.commit()

    asyncio.run(init())
    yield

    async def drop():
        async with async_test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await async_test_engine.dispose()

    asyncio.run(drop())
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
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_header():
    token = create_access_token(
        subject=test_officer_id,
        claims={"role": "AUTHORITY_OFFICER", "badge_id": "FSO-DL-CEN-007"},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_case(client, auth_header):
    """Creates a rich test case with deep analysis and risk assessment."""
    payload = {
        "product_name": "AyushShield Miracle Immunity Elixir",
        "brand": "AyushBio",
        "category": "AYURVEDIC_AHAAR",
        "product_description": (
            "Proprietary herbal blend. Ingredients: Ashwagandha, Tulsi, Rhodamine B, Giloy.\n"
            "Claims: 100% Guaranteed Cure for Diabetes and Heart Disease. Anti-cancer action.\n"
            "FSSAI Lic. No: 10019011002345.\n"
            "Manufactured by: BioAyur Laboratories, Haridwar, Uttarakhand."
        ),
        "fssai_license_number": "10019011002345",
        "manufacturer": "BioAyur Laboratories, Haridwar, Uttarakhand",
        "notes": "Suspected Section 24 curative claim violation and toxic synthetic dye",
    }
    submit_res = client.post("/api/v1/cases", data=payload, headers=auth_header)
    assert submit_res.status_code == 201
    case_id = submit_res.json()["case_id"]

    # Run deep analysis
    client.post(f"/api/v1/cases/{case_id}/deep-analysis", headers=auth_header)
    # Run risk assessment
    client.post(f"/api/v1/cases/{case_id}/risk-assessment", headers=auth_header)

    return case_id


# ---------------------------------------------------------------------------
# 1. Test Structured Report Data Extraction (All 8 Sections)
# ---------------------------------------------------------------------------
def test_report_data_structure(client, auth_header, sample_case):
    """Verifies that GET /report/data returns the complete 8-section structured model."""
    res = client.get(f"/api/v1/cases/{sample_case}/report/data", headers=auth_header)
    assert res.status_code == 200
    report = res.json()

    # Document metadata
    assert report["report_title"] == "PRODUCT COMPLIANCE RISK INTELLIGENCE REPORT"
    assert "DRISHTI-REP-" in report["report_identifier"]
    assert report["sha256_report_hash"] is not None

    # Mandatory statutory disclaimer is present
    mandatory_disc = report["mandatory_statutory_disclaimer"]
    assert "AI-assisted decision-support assessment" in mandatory_disc
    assert "human authority review" in mandatory_disc

    # Section 1: Case Information
    c = report["case_info"]
    assert c["case_id"] == sample_case
    assert "CASE-" in c["case_number"]
    assert c["status"] in ("PRIORITY_REVIEW", "STANDARD_REVIEW", "UNDER_REVIEW")
    assert c["priority"] in ("URGENT_P1", "HIGH_P2", "ROUTINE_P3")

    # Section 2: Product Information
    p = report["product_info"]
    assert p["product_name"] == "AyushShield Miracle Immunity Elixir"
    assert p["brand"] == "AyushBio"
    assert p["fssai_license_number"] == "10019011002345"

    # Section 3: Source Information
    s = report["source_info"]
    assert s["submitted_description"] is not None
    assert isinstance(s["submitted_images"], list)

    # Section 4: Risk Assessment
    r = report["risk_assessment"]
    assert 0.0 <= r["risk_score"] <= 1.0
    assert r["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert 0.0 <= r["confidence_score"] <= 1.0
    assert r["total_findings_analyzed"] >= 1
    assert isinstance(r["dimension_breakdown"], list)

    # Section 5: Detected Findings
    findings = report["detected_findings"]
    assert len(findings) >= 1
    for f in findings:
        assert "title" in f
        assert "severity" in f
        assert 0.0 <= f["confidence"] <= 1.0

    # Section 6: Evidence
    ev_items = report["evidence"]
    assert isinstance(ev_items, list)

    # Section 7: Analysis Limitations
    lim = report["analysis_limitations"]
    assert isinstance(lim["missing_information"], list)
    assert isinstance(lim["ocr_limitations"], list)
    assert isinstance(lim["ai_confidence_limitations"], list)
    assert 0.0 <= lim["data_completeness_ratio"] <= 1.0

    # Section 8: Review Recommendation
    rec = report["review_recommendation"]
    assert rec["recommendation"] in ("PRIORITY_REVIEW", "STANDARD_REVIEW", "ADDITIONAL_INFO_REQUIRED")
    assert rec["priority_level"] in ("URGENT_P1", "HIGH_P2", "ROUTINE_P3", "MONITORING_P4")
    assert len(rec["suggested_actions"]) >= 1


# ---------------------------------------------------------------------------
# 2. Test HTML Report Rendering
# ---------------------------------------------------------------------------
def test_html_report_rendering(client, auth_header, sample_case):
    """Verifies that GET /report/html returns valid HTML containing all 8 sections and mandatory disclaimer."""
    res = client.get(f"/api/v1/cases/{sample_case}/report/html", headers=auth_header)
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    html_text = res.text

    # Basic HTML document structure
    assert "<!DOCTYPE html>" in html_text
    assert "<html" in html_text
    assert "PRODUCT COMPLIANCE RISK INTELLIGENCE REPORT" in html_text

    # Mandatory Statutory Disclaimer check
    assert "The analysis is an AI-assisted decision-support assessment." in html_text
    assert "Final regulatory decisions require human authority review." in html_text
    assert "STATUTORY AI DECISION-SUPPORT NOTICE" in html_text

    # All 8 Section Headers check
    assert "1" in html_text and "Case Information" in html_text
    assert "2" in html_text and "Product Information" in html_text
    assert "3" in html_text and "Source Information" in html_text
    assert "4" in html_text and "Risk Assessment" in html_text
    assert "5" in html_text and "Detected Regulatory Findings" in html_text
    assert "6" in html_text and "Corroborating Evidence Records" in html_text
    assert "7" in html_text and "Analysis Limitations &amp; Caveats" in html_text or "Analysis Limitations" in html_text
    assert "8" in html_text and "Authority Review Recommendation" in html_text

    # Product and Case content check
    assert "AyushShield Miracle Immunity Elixir" in html_text
    assert "10019011002345" in html_text


# ---------------------------------------------------------------------------
# 3. Test PDF Report Generation
# ---------------------------------------------------------------------------
def test_pdf_report_generation(client, auth_header, sample_case):
    """Verifies that GET /report/pdf returns a valid, well-formed binary PDF document."""
    res = client.get(f"/api/v1/cases/{sample_case}/report/pdf", headers=auth_header)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "attachment; filename=\"DRISHTI-Report-" in res.headers["content-disposition"]

    pdf_bytes = res.content
    # Standard PDF magic header
    assert pdf_bytes.startswith(b"%PDF-"), "File does not begin with standard PDF header '%PDF-'"
    # Size check: A comprehensive multi-page ReportLab PDF is typically > 8KB
    assert len(pdf_bytes) > 5000, f"PDF file size too small ({len(pdf_bytes)} bytes)"
    # Standard PDF end-of-file marker
    assert b"%%EOF" in pdf_bytes, "File does not contain standard PDF '%%EOF' marker"


# ---------------------------------------------------------------------------
# 4. Test Audit Logging for Report Generations
# ---------------------------------------------------------------------------
def test_report_audit_logging(client, auth_header, sample_case):
    """Verifies that both HTML and PDF generation write immutable audit log records."""
    # 1. Trigger HTML report
    res_html = client.get(f"/api/v1/cases/{sample_case}/report/html", headers=auth_header)
    assert res_html.status_code == 200

    # 2. Trigger PDF report
    res_pdf = client.get(f"/api/v1/cases/{sample_case}/report/pdf", headers=auth_header)
    assert res_pdf.status_code == 200

    # 3. Verify audit log database entries
    import asyncio

    async def check_audit():
        async with AsyncTestingSessionLocal() as session:
            stmt = select(AuditLog).where(AuditLog.case_id == uuid.UUID(sample_case))
            logs = (await session.execute(stmt)).scalars().all()
            actions = [log.action for log in logs]
            assert "REPORT_GENERATED_HTML" in actions, f"Missing REPORT_GENERATED_HTML in {actions}"
            assert "REPORT_GENERATED_PDF" in actions, f"Missing REPORT_GENERATED_PDF in {actions}"

    asyncio.run(check_audit())


# ---------------------------------------------------------------------------
# 5. Security: Unauthenticated Calls Rejected
# ---------------------------------------------------------------------------
def test_unauthenticated_report_rejected(client, sample_case):
    """Verifies that non-authenticated requests to report endpoints receive 401 Unauthorized."""
    data_res = client.get(f"/api/v1/cases/{sample_case}/report/data")
    assert data_res.status_code == 401

    html_res = client.get(f"/api/v1/cases/{sample_case}/report/html")
    assert html_res.status_code == 401

    pdf_res = client.get(f"/api/v1/cases/{sample_case}/report/pdf")
    assert pdf_res.status_code == 401


# ---------------------------------------------------------------------------
# 6. Error Handling: Non-existent Case Returns 404
# ---------------------------------------------------------------------------
def test_nonexistent_case_returns_404(client, auth_header):
    """Verifies that querying a report for an invalid case ID returns 404 Not Found."""
    fake_id = str(uuid.uuid4())
    res = client.get(f"/api/v1/cases/{fake_id}/report/data", headers=auth_header)
    assert res.status_code == 404

    res_html = client.get(f"/api/v1/cases/{fake_id}/report/html", headers=auth_header)
    assert res_html.status_code == 404

    res_pdf = client.get(f"/api/v1/cases/{fake_id}/report/pdf", headers=auth_header)
    assert res_pdf.status_code == 404
