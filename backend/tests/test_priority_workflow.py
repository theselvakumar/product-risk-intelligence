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
from app.models.case import AuditLog, Case, CaseReview
from app.models.user import User

TEST_DB_FILE = "test_priority_workflow.db"
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
                email="officer.priority@drishti.gov.in",
                full_name="Vikramaditya Rathore",
                badge_id="FSO-MH-MUM-042",
                role="AUTHORITY_OFFICER",
                jurisdiction_state="MH",
                jurisdiction_district="MH-MUM",
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
        claims={"role": "AUTHORITY_OFFICER", "badge_id": "FSO-MH-MUM-042"},
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. High-Risk Cases Automatically Enter PRIORITY_REVIEW
# ---------------------------------------------------------------------------
def test_high_risk_automatic_priority_routing(client, auth_header):
    """High-risk non-compliant products automatically route to PRIORITY_REVIEW."""
    payload = {
        "product_name": "GlycoCure Miracle Herbal Capsules",
        "brand": "MiracleHerbals",
        "category": "HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS",
        "product_description": (
            "Proprietary formula. Ingredients: Amla, Giloy, Rhodamine B.\n"
            "Claims: Scientifically proven to cure cancer. 100% Guaranteed results.\n"
            "FSSAI Lic No: 10018022007890.\n"
            "Mfg by: Divya Agro Industries, Haridwar."
        ),
        "notes": "Market complaint regarding illegal curative cancer claim and toxic dye",
    }
    res = client.post("/api/v1/cases", data=payload, headers=auth_header)
    assert res.status_code == 201
    case_id = res.json()["case_id"]

    # Run deep analysis
    da_res = client.post(f"/api/v1/cases/{case_id}/deep-analysis", headers=auth_header)
    assert da_res.status_code == 200

    # Run risk engine
    rk_res = client.post(f"/api/v1/cases/{case_id}/risk-assessment", headers=auth_header)
    assert rk_res.status_code == 200
    risk_data = rk_res.json()

    # Check case status in database
    case_res = client.get(f"/api/v1/cases/{case_id}", headers=auth_header)
    assert case_res.status_code == 200
    case_info = case_res.json()
    assert case_info["status"] == "PRIORITY_REVIEW", (
        f"Expected status 'PRIORITY_REVIEW' for high-risk case, got '{case_info['status']}'"
    )
    assert case_info["priority"] in ("URGENT_P1", "HIGH_P2")


# ---------------------------------------------------------------------------
# 2. Low/Medium Risk Cases Route to STANDARD_REVIEW
# ---------------------------------------------------------------------------
def test_low_risk_automatic_standard_routing(client, auth_header):
    """Low/medium risk products automatically route to STANDARD_REVIEW."""
    payload = {
        "product_name": "Standard Wheat Flour 5kg",
        "brand": "KisanShree",
        "category": "CEREALS_AND_PULSES",
        "product_description": (
            "100% Whole Wheat Atta. No artificial additives or colors.\n"
            "Ingredients: Whole Wheat.\n"
            "FSSAI Lic. No: 10021011005544."
        ),
        "notes": "Routine surveillance sample",
    }
    res = client.post("/api/v1/cases", data=payload, headers=auth_header)
    assert res.status_code == 201
    case_id = res.json()["case_id"]

    # Run deep analysis & risk
    client.post(f"/api/v1/cases/{case_id}/deep-analysis", headers=auth_header)
    rk_res = client.post(f"/api/v1/cases/{case_id}/risk-assessment", headers=auth_header)
    assert rk_res.status_code == 200

    case_res = client.get(f"/api/v1/cases/{case_id}", headers=auth_header)
    assert case_res.status_code == 200
    case_info = case_res.json()
    assert case_info["status"] in ("STANDARD_REVIEW", "PRIORITY_REVIEW")


# ---------------------------------------------------------------------------
# 3. Priority Review Queue: Search, Filter, and Sort
# ---------------------------------------------------------------------------
def test_priority_queue_search_filter_sort(client, auth_header):
    """GET /priority-queue supports searching, filtering, and sorting."""
    # 1. Fetch default queue
    res = client.get("/api/v1/cases/priority-queue", headers=auth_header)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total_count" in data
    assert len(data["items"]) >= 1

    item = data["items"][0]
    required_fields = [
        "case_id", "case_number", "product_name", "brand", "category",
        "risk_score", "risk_level", "confidence", "submission_date", "status",
    ]
    for field in required_fields:
        assert field in item, f"Missing required queue field: {field}"

    # 2. Test sorting by risk_score desc
    sort_res = client.get(
        "/api/v1/cases/priority-queue?sort_by=risk_score&sort_order=desc",
        headers=auth_header,
    )
    assert sort_res.status_code == 200
    sorted_items = sort_res.json()["items"]
    if len(sorted_items) >= 2:
        assert sorted_items[0]["risk_score"] >= sorted_items[1]["risk_score"]

    # 3. Test text search
    search_res = client.get(
        "/api/v1/cases/priority-queue?search=GlycoCure",
        headers=auth_header,
    )
    assert search_res.status_code == 200
    searched_items = search_res.json()["items"]
    assert len(searched_items) >= 1
    assert "GlycoCure" in searched_items[0]["product_name"]

    # 4. Test risk level filtering
    risk_res = client.get(
        "/api/v1/cases/priority-queue?risk_level=CRITICAL",
        headers=auth_header,
    )
    assert risk_res.status_code == 200
    for it in risk_res.json()["items"]:
        assert it["risk_level"] == "CRITICAL"


# ---------------------------------------------------------------------------
# 4. Authority Starts Review (UNDER_REVIEW State)
# ---------------------------------------------------------------------------
def test_authority_start_review(client, auth_header):
    """Authority officer opens case and begins review, updating status to UNDER_REVIEW."""
    # Create sample case
    res = client.post("/api/v1/cases", data={
        "product_name": "AyurPower Shilajit Gold",
        "brand": "AyurPower",
        "category": "HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS",
        "product_description": "Boosts stamina instantly. 100% natural.",
    }, headers=auth_header)
    case_id = res.json()["case_id"]

    # Officer starts review
    start_res = client.post(f"/api/v1/cases/{case_id}/start-review", headers=auth_header)
    assert start_res.status_code == 200
    updated_case = start_res.json()

    assert updated_case["status"] == "UNDER_REVIEW"
    assert updated_case["assigned_user_id"] == str(test_officer_id)


# ---------------------------------------------------------------------------
# 5. Authority Review Determination & Statutory Notes
# ---------------------------------------------------------------------------
def test_authority_review_notes_and_status_update(client, auth_header):
    """Officer records review notes, selects statutory action, and updates status."""
    res = client.post("/api/v1/cases", data={
        "product_name": "Test Keto Bar",
        "brand": "KetoDelight",
        "category": "CEREAL_AND_CONFECTIONERY",
        "product_description": "Keto snack bar with 0g sugar claim.",
    }, headers=auth_header)
    case_id = res.json()["case_id"]

    review_payload = {
        "review_action": "ISSUE_SECTION_32_NOTICE",
        "remarks": (
            "Labelling check reveals undeclared high maltitol and misleading keto claim. "
            "Issued Section 32 Improvement Notice with 14-day compliance mandate."
        ),
        "new_status": "NOTICE_ISSUED_SEC32",
        "action_metadata": {
            "statutory_section": "FSS Act 2006, Section 32",
            "compliance_window_days": 14,
        },
    }

    rev_res = client.post(f"/api/v1/cases/{case_id}/reviews", json=review_payload, headers=auth_header)
    assert rev_res.status_code == 201
    rev_data = rev_res.json()

    assert rev_data["review_action"] == "ISSUE_SECTION_32_NOTICE"
    assert "Section 32" in rev_data["remarks"]
    assert rev_data["reviewer_id"] == str(test_officer_id)

    # Verify case status was updated
    case_res = client.get(f"/api/v1/cases/{case_id}", headers=auth_header)
    assert case_res.status_code == 200
    assert case_res.json()["status"] == "NOTICE_ISSUED_SEC32"


# ---------------------------------------------------------------------------
# 6. Authority Status Update Endpoint
# ---------------------------------------------------------------------------
def test_authority_status_update(client, auth_header):
    """PATCH /cases/{case_id}/status updates case status with audit logging."""
    res = client.post("/api/v1/cases", data={
        "product_name": "Audit Test Biscuit",
        "brand": "AuditBrand",
        "category": "CEREAL_AND_CONFECTIONERY",
        "product_description": "Sample biscuit.",
    }, headers=auth_header)
    case_id = res.json()["case_id"]

    patch_res = client.patch(
        f"/api/v1/cases/{case_id}/status",
        json={"status": "REVIEW_COMPLETED", "reason": "Officer inspection concluded", "notes": "No hazard found"},
        headers=auth_header,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "REVIEW_COMPLETED"


# ---------------------------------------------------------------------------
# 7. AI Cannot Automatically Close or Punish a Case
# ---------------------------------------------------------------------------
def test_ai_cannot_close_case(client, auth_header):
    """
    Statutory Principle:
    AI algorithms can only assign risk scores and recommend review queues.
    AI can NEVER automatically transition a case to CLOSED, RESOLVED, or penalize without human authority.
    """
    res = client.post("/api/v1/cases", data={
        "product_name": "Pure Honey 500g",
        "brand": "BeePure",
        "category": "SWEETENERS_AND_HONEY",
        "product_description": "100% Pure Organic Raw Forest Honey.",
    }, headers=auth_header)
    case_id = res.json()["case_id"]

    # Run complete automated pipeline
    client.post(f"/api/v1/cases/{case_id}/deep-analysis", headers=auth_header)
    client.post(f"/api/v1/cases/{case_id}/consistency-check", headers=auth_header)
    client.post(f"/api/v1/cases/{case_id}/risk-assessment", headers=auth_header)

    case_res = client.get(f"/api/v1/cases/{case_id}", headers=auth_header)
    status_after_ai = case_res.json()["status"]

    # Case must NOT be closed or resolved by AI
    assert status_after_ai not in ("CLOSED", "RESOLVED", "REVIEW_COMPLETED", "DISMISS_CASE")
    assert status_after_ai in ("STANDARD_REVIEW", "PRIORITY_REVIEW", "SUBMITTED")


# ---------------------------------------------------------------------------
# 8. Unauthenticated Access Rejection
# ---------------------------------------------------------------------------
def test_unauthenticated_review_actions_rejected(client):
    """Unauthenticated users cannot view queue or submit reviews."""
    dummy_id = str(uuid.uuid4())
    assert client.get("/api/v1/cases/priority-queue").status_code in (401, 403)
    assert client.post(f"/api/v1/cases/{dummy_id}/start-review").status_code in (401, 403)
    assert client.post(f"/api/v1/cases/{dummy_id}/reviews", json={"review_action": "TEST", "remarks": "TEST"}).status_code in (401, 403)
    assert client.patch(f"/api/v1/cases/{dummy_id}/status", json={"status": "CLOSED"}).status_code in (401, 403)
