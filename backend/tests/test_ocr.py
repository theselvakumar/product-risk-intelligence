import io
import os
import uuid
import pytest
from PIL import Image, ImageDraw, ImageFilter
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.database.session import get_db
from app.main import app
from app.models.base import Base
from app.models.user import User
from app.services.ocr.engine import OCREngine
from app.services.ocr.preprocessor import ImagePreprocessor
from app.services.ocr.service import OCRService

TEST_DB_FILE = "test_ocr.db"
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
                email="officer.ocr@drishti.gov.in",
                full_name="Sunil Verma",
                badge_id="FSO-DL-SOUTH-101",
                role="AUTHORITY_OFFICER",
                jurisdiction_state="DL",
                jurisdiction_district="DL-SOUTH",
                is_active=True,
                hashed_password=hash_password("Password123!"),
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


@pytest.fixture
def auth_header():
    token = create_access_token(
        subject=test_officer_id,
        claims={"role": "AUTHORITY_OFFICER", "badge_id": "FSO-DL-SOUTH-101"},
    )
    return {"Authorization": f"Bearer {token}"}


# Helper functions to create test images
def create_clear_label_image() -> bytes:
    """Create a high-contrast, sharp packaging label image."""
    img = Image.new("RGB", (600, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    text = "INGREDIENTS: Organic Wheat Flour, Sugar, Palm Oil, Salt.\nFSSAI Lic. No: 10018022007890\nNet Weight: 250g"
    draw.text((20, 30), text, fill=(0, 0, 0))
    img.info["text"] = text

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def create_blurry_label_image() -> bytes:
    """Create an intentionally blurred image simulating out-of-focus phone photography."""
    img = Image.new("RGB", (500, 250), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "Blurred Unreadable Label Text", fill=(100, 100, 100))
    # Apply severe blur
    blurred = img.filter(ImageFilter.GaussianBlur(radius=15))

    buf = io.BytesIO()
    blurred.save(buf, format="JPEG", quality=75)
    return buf.getvalue()


def create_sparse_text_image() -> bytes:
    """Create an image with negligible / sparse text."""
    img = Image.new("RGB", (200, 200), color=(250, 250, 250))
    draw = ImageDraw.Draw(img)
    draw.rectangle([90, 90, 110, 110], fill=(20, 20, 20))  # tiny box

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Unit & Pipeline Tests
# ---------------------------------------------------------------------------
def test_ocr_clear_image():
    """Test 1: Clear image processes with high sharpness and extracted text."""
    clear_bytes = create_clear_label_image()
    img = ImagePreprocessor.load_image(clear_bytes)
    enhanced, assessment = ImagePreprocessor.preprocess(img)

    assert not assessment.is_blurry
    assert assessment.quality_grade in ("EXCELLENT", "ACCEPTABLE")
    assert assessment.width == 600
    assert assessment.height == 300

    raw_text, conf, lines = OCREngine.extract_text(enhanced, sharpness_score=assessment.sharpness_score)
    assert len(raw_text) > 0
    assert conf >= 0.50
    assert "INGREDIENTS" in raw_text or "Wheat" in raw_text or "FSSAI" in raw_text


def test_ocr_blurry_image():
    """Test 2: Blurry image is detected, evaluated, and flagged as low quality."""
    blurry_bytes = create_blurry_label_image()
    img = ImagePreprocessor.load_image(blurry_bytes)
    enhanced, assessment = ImagePreprocessor.preprocess(img)

    assert assessment.is_blurry is True
    assert assessment.quality_grade in ("DEGRADED", "POOR")
    assert any("blurriness" in w.lower() for w in assessment.warnings)


def test_ocr_image_little_text():
    """Test 3: Image with negligible text is processed gracefully without crash."""
    sparse_bytes = create_sparse_text_image()
    img = ImagePreprocessor.load_image(sparse_bytes)
    enhanced, assessment = ImagePreprocessor.preprocess(img)

    raw_text, conf, lines = OCREngine.extract_text(enhanced, sharpness_score=assessment.sharpness_score)
    # Handles cleanly without errors
    assert isinstance(raw_text, str)
    assert isinstance(lines, list)


def test_ocr_invalid_file():
    """Test 4: Corrupted or non-image file raises ValueError."""
    corrupt_bytes = b"CORRUPTED_DATA_NOT_A_VALID_IMAGE_HEADER"
    with pytest.raises(ValueError) as exc_info:
        ImagePreprocessor.load_image(corrupt_bytes)
    assert "Invalid or corrupted image format" in str(exc_info.value)


# ---------------------------------------------------------------------------
# API Integration Tests
# ---------------------------------------------------------------------------
def test_api_trigger_and_get_ocr(client, auth_header):
    """Test 5: Full workflow: Submit case with image -> Trigger OCR -> Fetch OCR results."""
    # 1. Create a case with packaging image
    clear_img_bytes = create_clear_label_image()
    files = [
        ("packaging_images", ("label_pack.jpg", io.BytesIO(clear_img_bytes), "image/jpeg")),
    ]
    data = {
        "product_name": "AyurOrganic Pure Amla Juice 500ml",
        "brand": "AyurOrganic",
        "category": "BEVERAGES_TEA_AND_COFFEE",
    }
    submit_res = client.post("/api/v1/cases", data=data, files=files, headers=auth_header)
    assert submit_res.status_code == 201
    case_data = submit_res.json()
    case_id = case_data["case_id"]

    # 2. Get case details to get image_id
    detail_res = client.get(f"/api/v1/cases/{case_id}", headers=auth_header)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert len(detail["images"]) >= 1
    image_id = detail["images"][0]["id"]

    # 3. Trigger OCR via POST /cases/{case_id}/images/{image_id}/ocr
    ocr_res = client.post(f"/api/v1/cases/{case_id}/images/{image_id}/ocr", headers=auth_header)
    assert ocr_res.status_code == 200
    ocr_data = ocr_res.json()
    assert ocr_data["case_id"] == case_id
    assert ocr_data["image_id"] == image_id
    assert "confidence_score" in ocr_data
    assert "quality_assessment" in ocr_data
    assert ocr_data["status"] in ("SUCCESS", "LOW_QUALITY_WARNING")

    # 4. Fetch specific image OCR via GET /cases/{case_id}/images/{image_id}/ocr
    get_img_ocr = client.get(f"/api/v1/cases/{case_id}/images/{image_id}/ocr", headers=auth_header)
    assert get_img_ocr.status_code == 200
    assert get_img_ocr.json()["extracted_info_id"] == ocr_data["extracted_info_id"]

    # 5. Fetch case summary via GET /cases/{case_id}/ocr
    summary_res = client.get(f"/api/v1/cases/{case_id}/ocr", headers=auth_header)
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["case_id"] == case_id
    assert summary["total_images_processed"] >= 1
    assert len(summary["results"]) >= 1
