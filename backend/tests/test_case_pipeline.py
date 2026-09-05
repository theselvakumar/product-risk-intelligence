import io
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.database.session import get_db
from app.main import app
from app.models.analysis import AnalysisResult, Finding, RiskAssessment
from app.models.base import Base
from app.models.case import AuditLog, Case
from app.models.user import User
from app.services.case_pipeline import CasePipelineService

TEST_DB_FILE = "test_case_pipeline.db"
TEST_ASYNC_URL = f"sqlite+aiosqlite:///./{TEST_DB_FILE}"

async_test_engine = create_async_engine(TEST_ASYNC_URL, echo=False)
AsyncTestingSessionLocal = async_sessionmaker(
    bind=async_test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
test_officer_id = uuid.uuid4()


def create_mock_label_image() -> bytes:
    img = Image.new("RGB", (500, 250), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    text = "INGREDIENTS: Water, Sugar, Ashwagandha 500mg, Preservative 211.\nFSSAI Lic. No: 10018022007890\nBatch: B-2026"
    draw.text((20, 30), text, fill=(0, 0, 0))
    img.info["text"] = text

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


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
                email="pipeline.officer@drishti.gov.in",
                full_name="Ananya Sharma",
                badge_id="FSO-DL-CENTRAL-088",
                role="AUTHORITY_OFFICER",
                jurisdiction_state="DL",
                jurisdiction_district="DL-CENTRAL",
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
        claims={"role": "AUTHORITY_OFFICER", "badge_id": "FSO-DL-CENTRAL-088"},
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Test 1: Case with Description -> Full Pipeline Execution
# ---------------------------------------------------------------------------
def test_pipeline_case_with_description(client, auth_header):
    """
    Submits a case with rich product description, triggers the pipeline via
    POST /api/v1/cases/{case_id}/run-analysis, and asserts complete execution.
    """
    submit_payload = {
        "product_name": "Vedika Herbal Diabetic Elixir 500ml",
        "brand": "Vedika Botanicals",
        "category": "HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS",
        "product_description": (
            "Proprietary herbal diabetic elixir. Contains: Gurmar extract, Jamun seed, Fenugreek.\n"
            "Guaranteed 100% cure for Type 2 Diabetes within 14 days without insulin.\n"
            "Manufactured by: Vedika Herbal Labs, Haridwar.\n"
            "FSSAI Lic. No: 10018022007890."
        ),
        "notes": "Targeted surveillance on egregious therapeutic curative claim.",
    }

    sub_res = client.post("/api/v1/cases", data=submit_payload, headers=auth_header)
    assert sub_res.status_code == 201
    case_id = sub_res.json()["case_id"]

    # Trigger end-to-end pipeline
    pipe_res = client.post(f"/api/v1/cases/{case_id}/run-analysis", headers=auth_header)
    assert pipe_res.status_code == 200
    res_data = pipe_res.json()

    assert res_data["case_id"] == case_id
    assert res_data["status"] == "ANALYSIS_COMPLETE"
    assert res_data["intelligence_completed"] is True
    assert res_data["deep_analysis_completed"] is True
    assert res_data["consistency_completed"] is True
    assert res_data["risk_assessment_completed"] is True
    assert res_data["risk_score"] is not None
    assert 0.0 <= res_data["risk_score"] <= 1.0
    assert res_data["risk_level"] in ("LOW", "MEDIUM", "HIGH")
    assert res_data["total_findings"] > 0
    assert len(res_data["errors"]) == 0
    assert res_data["execution_duration_ms"] > 0


# ---------------------------------------------------------------------------
# Test 2: Case with Image -> OCR and Full Pipeline
# ---------------------------------------------------------------------------
def test_pipeline_case_with_image(client, auth_header):
    """
    Submits a case with packaging image, triggers pipeline, asserts OCR runs,
    extracts packaging declarations, and completes risk assessment.
    """
    img_bytes = create_mock_label_image()
    files = [
        ("packaging_images", ("label_pack.jpg", io.BytesIO(img_bytes), "image/jpeg")),
    ]
    data = {
        "product_name": "AshwaMax Energy Bar",
        "brand": "NutriMax",
        "category": "HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS",
    }

    sub_res = client.post("/api/v1/cases", data=data, files=files, headers=auth_header)
    assert sub_res.status_code == 201
    case_id = sub_res.json()["case_id"]

    # Trigger pipeline
    pipe_res = client.post(f"/api/v1/cases/{case_id}/run-analysis", headers=auth_header)
    assert pipe_res.status_code == 200
    res_data = pipe_res.json()

    assert res_data["case_id"] == case_id
    assert res_data["status"] == "ANALYSIS_COMPLETE"
    assert res_data["ocr_processed"] is True
    assert res_data["images_processed"] >= 1
    assert res_data["intelligence_completed"] is True
    assert res_data["deep_analysis_completed"] is True
    assert res_data["risk_assessment_completed"] is True


# ---------------------------------------------------------------------------
# Test 3: Case with Mixed Input (URL + Image + Description)
# ---------------------------------------------------------------------------
def test_pipeline_case_with_mixed_input(client, auth_header):
    """
    Submits a case with all three evidence modalities, triggers pipeline,
    and asserts multi-source structuring, consistency comparison, and risk scoring.
    """
    img_bytes = create_mock_label_image()
    files = [
        ("packaging_images", ("mixed_pack.jpg", io.BytesIO(img_bytes), "image/jpeg")),
    ]
    data = {
        "product_name": "SuperShilajit Gold Resin",
        "brand": "HimalayanPure",
        "category": "AYURVEDIC_PROPRIETARY",
        "product_url": "https://himalayanpure.in/products/resin",
        "product_description": "Pure Himalayan Shilajit 20g. Contains 80% Fulvic Acid. Enhances athletic stamina.",
        "fssai_license_number": "10018022007890",
    }

    sub_res = client.post("/api/v1/cases", data=data, files=files, headers=auth_header)
    assert sub_res.status_code == 201
    case_id = sub_res.json()["case_id"]

    pipe_res = client.post(f"/api/v1/cases/{case_id}/run-analysis", headers=auth_header)
    assert pipe_res.status_code == 200
    res_data = pipe_res.json()

    assert res_data["status"] == "ANALYSIS_COMPLETE"
    assert res_data["ocr_processed"] is True
    assert res_data["consistency_completed"] is True
    assert res_data["deep_analysis_completed"] is True
    assert res_data["risk_assessment_completed"] is True
    assert res_data["total_findings"] > 0


# ---------------------------------------------------------------------------
# Test 4: Idempotency & Rerunnability
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_pipeline_idempotency_rerun(client, auth_header):
    """
    Verifies that executing run-analysis twice on the same case does NOT create
    duplicate AnalysisResults, Findings, or RiskAssessments in the database.
    """
    data = {
        "product_name": "Idempotent Sample Bar",
        "brand": "IdempoBrands",
        "category": "CEREAL_AND_CONFECTIONERY",
        "product_description": "Cereal bar with oats, almonds, and honey. FSSAI Lic. No: 10018022007890.",
    }

    sub_res = client.post("/api/v1/cases", data=data, headers=auth_header)
    assert sub_res.status_code == 201
    case_id = sub_res.json()["case_id"]

    # Run 1
    pipe_res_1 = client.post(f"/api/v1/cases/{case_id}/run-analysis", headers=auth_header)
    assert pipe_res_1.status_code == 200
    first_findings = pipe_res_1.json()["total_findings"]
    first_score = pipe_res_1.json()["risk_score"]

    # Run 2 (Rerun on same case)
    pipe_res_2 = client.post(f"/api/v1/cases/{case_id}/run-analysis", headers=auth_header)
    assert pipe_res_2.status_code == 200
    second_findings = pipe_res_2.json()["total_findings"]
    second_score = pipe_res_2.json()["risk_score"]

    assert first_findings == second_findings
    assert first_score == second_score

    # Check database records directly for duplication
    async with AsyncTestingSessionLocal() as db:
        case_uuid = uuid.UUID(case_id)
        # Risk assessment count should be exactly 1
        ra_count = (await db.execute(
            select(RiskAssessment).where(RiskAssessment.case_id == case_uuid)
        )).scalars().all()
        assert len(ra_count) == 1, f"Expected exactly 1 RiskAssessment, found {len(ra_count)}"

        # AnalysisResult count should be exactly 2 (DEEP_PRODUCT_ANALYSIS and CROSS_SOURCE_CONSISTENCY)
        case_obj = (await db.execute(select(Case).where(Case.id == case_uuid))).scalar_one()
        ar_count = (await db.execute(
            select(AnalysisResult).where(AnalysisResult.product_id == case_obj.product_id)
        )).scalars().all()
        assert len(ar_count) == 2, f"Expected 2 AnalysisResults (Deep + Consistency), found {len(ar_count)}"


# ---------------------------------------------------------------------------
# Test 5: Failure Scenarios
# ---------------------------------------------------------------------------
def test_pipeline_nonexistent_case(client, auth_header):
    """Nonexistent case ID returns HTTP 404."""
    fake_id = str(uuid.uuid4())
    res = client.post(f"/api/v1/cases/{fake_id}/run-analysis", headers=auth_header)
    assert res.status_code == 404
    data = res.json()
    msg = data.get("message", data.get("detail", "")).lower()
    assert "not found" in msg
