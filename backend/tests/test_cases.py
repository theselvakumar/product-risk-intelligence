import io
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.database.session import get_db
from app.main import app
from app.models.base import Base
from app.models.user import User

TEST_DB_FILE = "test_cases.db"
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

    async def init_tables():
        async with async_test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with AsyncTestingSessionLocal() as session:
            officer = User(
                id=test_officer_id,
                email="officer.cases@drishti.gov.in",
                full_name="Rajesh Sharma",
                badge_id="FSO-DL-CENTRAL-099",
                role="AUTHORITY_OFFICER",
                jurisdiction_state="DL",
                jurisdiction_district="DL-CENTRAL",
                is_active=True,
                hashed_password=hash_password("Password123!"),
            )
            session.add(officer)
            await session.commit()

            # Seed demo cases
            from app.database.seed import seed_demonstration_cases
            await seed_demonstration_cases(session, officer)

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


@pytest.fixture
def auth_header():
    token = create_access_token(
        subject=test_officer_id,
        claims={"role": "AUTHORITY_OFFICER", "badge_id": "FSO-DL-CENTRAL-099"},
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Dashboard & Queue Endpoints
# ---------------------------------------------------------------------------
def test_dashboard_metrics_api(client, auth_header):
    """Test GET /api/v1/cases/metrics returns proper counts."""
    response = client.get("/api/v1/cases/metrics", headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert "total_cases" in data
    assert "cases_under_analysis" in data
    assert "low_risk" in data
    assert "medium_risk" in data
    assert "high_risk" in data
    assert "pending_review" in data
    assert data["total_cases"] >= 6


def test_recent_cases_api(client, auth_header):
    """Test GET /api/v1/cases/recent returns recent items with risk data."""
    response = client.get("/api/v1/cases/recent?limit=5", headers=auth_header)
    assert response.status_code == 200
    items = response.json()
    assert len(items) > 0
    first_item = items[0]
    assert "case_id" in first_item
    assert "case_number" in first_item
    assert "product_name" in first_item
    assert "risk_level" in first_item
    assert "status" in first_item
    assert "submission_date" in first_item


# ---------------------------------------------------------------------------
# Phase 5: Submission Workflow Tests
# ---------------------------------------------------------------------------
def test_submission_option_1_url_only(client, auth_header):
    """Option 1: Product URL submission creates Case with status SUBMITTED."""
    payload = {
        "product_url": "https://www.quickmart.in/products/vedika-amla-juice",
        "notes": "Suspected misleading claim regarding diabetes prevention",
    }
    response = client.post("/api/v1/cases", data=payload, headers=auth_header)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "SUBMITTED"
    assert "FSSAI-CASE-2026-" in data["case_number"]
    assert data["sources_count"] == 1
    assert data["images_count"] == 0
    assert "case_id" in data
    assert "product_id" in data


def test_submission_option_3_description_only(client, auth_header):
    """Option 3: Product Description submission creates Case with status SUBMITTED."""
    payload = {
        "product_description": "Pure Herbal Giloy Drops. Ingredients: Giloy extract 90%, preservative 211. Claims: Cures chronic fever in 24 hours.",
        "product_name": "Vedika Pure Giloy Drops",
        "brand": "Vedika Botanicals",
        "category": "AYURVEDIC_PROPRIETARY",
    }
    response = client.post("/api/v1/cases", data=payload, headers=auth_header)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "SUBMITTED"
    assert data["sources_count"] == 1
    assert data["images_count"] == 0
    assert "Vedika" in data["title"]


def test_submission_option_2_images_only(client, auth_header):
    """Option 2: Product & Packaging Images upload creates Case with stored hashes."""
    # Create fake in-memory image bytes
    fake_front_img = io.BytesIO(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00TESTIMAGEBYTES")
    fake_back_img = io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01TESTPNGDATA")

    files = [
        ("product_images", ("front_pack.jpg", fake_front_img, "image/jpeg")),
        ("packaging_images", ("nutrition_table.png", fake_back_img, "image/png")),
    ]
    data = {
        "product_name": "Organic Honey Bottle 250g",
        "brand": "Prakriti Agro",
        "category": "HONEY_AND_PRESERVES",
    }
    response = client.post("/api/v1/cases", data=data, files=files, headers=auth_header)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["status"] == "SUBMITTED"
    assert res_data["images_count"] == 2
    assert res_data["sources_count"] == 1  # PACKAGING_IMAGE source recorded


def test_submission_mixed_inputs(client, auth_header):
    """Mixed Input: Authority provides URL + Description + Packaging Image simultaneously."""
    fake_img = io.BytesIO(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00SAMPLEMIXEDIMAGE")

    files = [
        ("packaging_images", ("side_panel.jpg", fake_img, "image/jpeg")),
    ]
    data = {
        "product_url": "https://supermart.in/ayur-shilajit-resin",
        "product_description": "Himalayan Shilajit Resin 20g. 100% Organic certified. Rejuvenator.",
        "product_name": "Himalayan Shilajit Gold",
        "brand": "MountainHerbs",
        "category": "AYURVEDIC_PROPRIETARY",
        "notes": "Review claim under Section 24 regarding stamina and anti-aging.",
    }
    response = client.post("/api/v1/cases", data=data, files=files, headers=auth_header)
    assert response.status_code == 201
    res = response.json()
    assert res["status"] == "SUBMITTED"
    assert res["sources_count"] == 3  # URL + Description + Image sources
    assert res["images_count"] == 1


def test_submission_invalid_empty(client, auth_header):
    """Fails with 400 Bad Request when no inputs are provided."""
    response = client.post("/api/v1/cases", data={}, headers=auth_header)
    assert response.status_code == 400
    assert "At least one input option must be provided" in response.json()["message"]


def test_submission_invalid_url(client, auth_header):
    """Fails with 400 Bad Request when an invalid URL format is provided."""
    payload = {
        "product_url": "not-a-valid-web-address",
        "product_name": "Invalid URL Product",
    }
    response = client.post("/api/v1/cases", data=payload, headers=auth_header)
    assert response.status_code == 400
    assert "Invalid Product URL" in response.json()["message"]


def test_submission_invalid_file_type(client, auth_header):
    """Fails with 400 Bad Request when an unsupported file type is uploaded."""
    fake_pdf = io.BytesIO(b"%PDF-1.4 Fake document content")
    files = [
        ("product_images", ("lab_report.pdf", fake_pdf, "application/pdf")),
    ]
    response = client.post("/api/v1/cases", data={"notes": "PDF test"}, files=files, headers=auth_header)
    assert response.status_code == 400
    assert "Allowed image formats: JPEG, PNG, WEBP" in response.json()["message"]


def test_get_case_detail_by_id(client, auth_header):
    """Test GET /api/v1/cases/{case_id} retrieves comprehensive details with sources and images."""
    # First create a case
    create_res = client.post(
        "/api/v1/cases",
        data={
            "product_url": "https://testbrand.com/sample-snack",
            "product_description": "Roasted Foxnuts Snack. Ingredients: Makhana, Olive Oil, Pink Salt.",
            "product_name": "Healthy Makhana 100g",
            "brand": "NutriBites",
            "category": "CEREAL_AND_CONFECTIONERY",
        },
        headers=auth_header,
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    # Retrieve case
    detail_res = client.get(f"/api/v1/cases/{case_id}", headers=auth_header)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == case_id
    assert detail["status"] == "SUBMITTED"
    assert detail["product"]["product_name"] == "Healthy Makhana 100g"
    assert len(detail["sources"]) == 2  # URL and Description sources


def test_add_source_to_case(client, auth_header):
    """Test POST /api/v1/cases/{case_id}/sources appends a new source."""
    create_res = client.post(
        "/api/v1/cases",
        data={"product_description": "Initial description of test sample"},
        headers=auth_header,
    )
    case_id = create_res.json()["case_id"]

    source_payload = {
        "source_type": "ECOMMERCE_URL",
        "source_url": "https://amazon.in/dp/B00EXAMPLE",
        "platform_name": "Amazon India",
        "raw_content": "Supplementary web marketplace listing",
    }
    add_res = client.post(f"/api/v1/cases/{case_id}/sources", json=source_payload, headers=auth_header)
    assert add_res.status_code == 201
    src_data = add_res.json()
    assert src_data["source_type"] == "ECOMMERCE_URL"
    assert src_data["source_url"] == "https://amazon.in/dp/B00EXAMPLE"


def test_upload_image_to_case(client, auth_header):
    """Test POST /api/v1/cases/{case_id}/images uploads and associates image asset."""
    create_res = client.post(
        "/api/v1/cases",
        data={"product_description": "Sample for image attachment"},
        headers=auth_header,
    )
    case_id = create_res.json()["case_id"]

    fake_img = io.BytesIO(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00ATTACHEDIMAGE")
    files = {"file": ("attached_fop.jpg", fake_img, "image/jpeg")}
    data = {"image_type": "FRONT_OF_PACK"}

    img_res = client.post(f"/api/v1/cases/{case_id}/images", data=data, files=files, headers=auth_header)
    assert img_res.status_code == 201
    img_data = img_res.json()
    assert img_data["image_type"] == "FRONT_OF_PACK"
    assert "file_hash_sha256" in img_data or "sha256_hash" in img_data
    assert "/uploads/cases/" in img_data["storage_uri"]
