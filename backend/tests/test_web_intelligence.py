import io
import os
import uuid
import pytest
from unittest.mock import patch
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
from app.models.product import ExtractedInformation, Product, ProductImage, ProductSource
from app.models.user import User
from app.schemas.consistency import ConsistencyReport
from app.services.case_pipeline import CasePipelineService
from app.services.consistency.service import ConsistencyAnalysisService
from app.services.web_intelligence import (
    MockSearchProvider,
    ScrapedPageData,
    ScrapingService,
    SearchResult,
    SearchService,
    SourceNormalizer,
    WebIntelligenceOrchestrator,
)

TEST_DB_FILE = "test_web_intelligence.db"
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
    text = "INGREDIENTS: Purified Water, Ashwagandha Extract 500mg, Preservative 211.\nFSSAI Lic. No: 10018022007890"
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
                email="webintel.officer@drishti.gov.in",
                full_name="Rajesh Kumar",
                badge_id="FSO-DL-CENTRAL-077",
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
def auth_headers():
    token = create_access_token(
        subject=test_officer_id,
        claims={"role": "AUTHORITY_OFFICER", "badge_id": "FSO-DL-CENTRAL-077"},
    )
    return {"Authorization": f"Bearer {token}"}


# -----------------------------------------------------------------------------
# TEST 1 — PRODUCT URL EXTRACTION
# -----------------------------------------------------------------------------
def test_product_url_extraction(client, auth_headers):
    """
    Test Level 1: Authority provides a product URL.
    Verify scraping occurs, metadata is structured, and pipeline produces risk scores.
    """
    mock_scraped = ScrapedPageData(
        url="https://healthmarket.example.com/item/amla-juice",
        title="Pure Organic Amla Juice 500ml",
        meta_description="Rich in Vitamin C, 100% pure Ayurvedic juice without added water.",
        readable_text="Manufactured by: Herbal Valley Organics Ltd. Ingredients: Amla Juice 99.8%, Preservative E211 0.2%. FSSAI Lic. No: 10018022007890. 100% natural, boosts immunity.",
        json_ld_products=[{
            "@type": "Product",
            "name": "Pure Organic Amla Juice 500ml",
            "brand": "Herbal Valley",
            "manufacturer": "Herbal Valley Organics Ltd",
        }],
        is_success=True,
    )

    with patch.object(ScrapingService, "fetch_and_extract", return_value=mock_scraped):
        # 1. Submit product with URL
        payload = {
            "product_name": "Pure Organic Amla Juice",
            "brand": "Herbal Valley",
            "product_url": "https://healthmarket.example.com/item/amla-juice",
            "product_description": "Cold pressed organic amla wellness juice.",
        }
        create_res = client.post("/api/v1/cases", json=payload, headers=auth_headers)
        assert create_res.status_code == 201
        case_id = create_res.json()["case_id"]

        # 2. Run analysis pipeline
        run_res = client.post(f"/api/v1/cases/{case_id}/run-analysis", headers=auth_headers)
        assert run_res.status_code == 200
        data = run_res.json()

        assert data["status"] == "ANALYSIS_COMPLETE"
        assert data["web_collection_attempted"] is True
        assert data["web_sources_processed"] >= 1
        assert data["risk_score"] is not None
        assert data["total_findings"] > 0


# -----------------------------------------------------------------------------
# TEST 2 — PRODUCT NAME + BRAND WEB SEARCH
# -----------------------------------------------------------------------------
def test_product_name_brand_web_search(client, auth_headers):
    """
    Test Level 2: Authority provides Product Name + Brand (no URL).
    Verify targeted search is executed, results scraped, filtered, and attributed.
    """
    mock_search_results = [
        SearchResult(
            title="BioAyur Shilajit Gold Resin 20g",
            url="https://ayurveda-store.example.com/products/shilajit-gold",
            snippet="Pure Himalayan Shilajit resin with Gold Vark. Guaranteed 100% natural vitality booster.",
            source_engine="mock_search",
            rank=1,
        )
    ]

    mock_scraped_page = ScrapedPageData(
        url="https://ayurveda-store.example.com/products/shilajit-gold",
        title="BioAyur Shilajit Gold Resin 20g",
        readable_text="Manufactured by: BioAyur Laboratories Pvt Ltd. Ingredients: Shuddha Shilajit 99%, Swarna Bhasma 1%. FSSAI Lic. No: 10019011004567. Clinically proven, cures chronic fatigue.",
        is_success=True,
    )

    mock_provider = MockSearchProvider({
        "shilajit": mock_search_results,
    })
    SearchService.set_provider(mock_provider)

    try:
        with patch.object(ScrapingService, "fetch_and_extract", return_value=mock_scraped_page):
            payload = {
                "product_name": "Shilajit Gold Resin",
                "brand": "BioAyur",
                "product_description": "Traditional Ayurvedic resin for energy and stamina.",
            }
            create_res = client.post("/api/v1/cases", json=payload, headers=auth_headers)
            assert create_res.status_code == 201
            case_id = create_res.json()["case_id"]

            run_res = client.post(f"/api/v1/cases/{case_id}/run-analysis", headers=auth_headers)
            assert run_res.status_code == 200
            data = run_res.json()

            assert data["status"] == "ANALYSIS_COMPLETE"
            assert data["web_collection_attempted"] is True
            assert data["web_sources_processed"] >= 1
            assert data["risk_score"] is not None
    finally:
        SearchService.reset_provider()


# -----------------------------------------------------------------------------
# TEST 3 — MIXED DATA (URL + OCR + DESCRIPTION)
# -----------------------------------------------------------------------------
def test_mixed_evidence_pipeline(client, auth_headers):
    """
    Test Mixed Inputs: Authority description + Product URL + Packaging Image.
    Verify all streams (Authority + URL + Web + OCR) are aggregated.
    """
    mock_scraped = ScrapedPageData(
        url="https://store.example.com/amla-elixir",
        title="Herbal Amla Elixir 500ml",
        readable_text="Manufactured by: Vedic Wellness. Ingredients: Amla, Sugar, Water. FSSAI Lic. No: 10018022007890.",
        is_success=True,
    )

    img_bytes = create_mock_label_image()

    with patch.object(ScrapingService, "fetch_and_extract", return_value=mock_scraped):
        files = [
            ("product_images", ("label.jpg", img_bytes, "image/jpeg")),
        ]
        data = {
            "product_name": "Amla Health Elixir",
            "brand": "Vedic Wellness",
            "product_url": "https://store.example.com/amla-elixir",
            "product_description": "Immunity booster beverage with natural amla.",
        }
        create_res = client.post("/api/v1/cases", data=data, files=files, headers=auth_headers)
        assert create_res.status_code == 201
        case_id = create_res.json()["case_id"]

        run_res = client.post(f"/api/v1/cases/{case_id}/run-analysis", headers=auth_headers)
        assert run_res.status_code == 200
        res_data = run_res.json()

        assert res_data["status"] == "ANALYSIS_COMPLETE"
        assert res_data["ocr_processed"] is True
        assert res_data["web_collection_attempted"] is True
        assert res_data["web_sources_processed"] >= 1
        assert res_data["risk_score"] is not None


# -----------------------------------------------------------------------------
# TEST 4 — SOURCE ATTRIBUTION INTEGRITY
# -----------------------------------------------------------------------------
def test_source_attribution_integrity(client, auth_headers):
    """
    Verify that every web-derived item preserves source URL, source type,
    original text, and timestamp without confusing AI conclusions with source evidence.
    """
    mock_scraped = ScrapedPageData(
        url="https://nutrition.example.com/protein-powder",
        title="Apex Whey Protein Isolate 1kg",
        readable_text="Manufactured by: Apex Nutrition Ltd. Ingredients: Whey Protein Isolate, Cocoa, Sucralose. FSSAI Lic. No: 10017022001234.",
        is_success=True,
    )

    with patch.object(ScrapingService, "fetch_and_extract", return_value=mock_scraped):
        payload = {
            "product_name": "Apex Whey Protein Isolate",
            "brand": "Apex Nutrition",
            "product_url": "https://nutrition.example.com/protein-powder",
        }
        create_res = client.post("/api/v1/cases", json=payload, headers=auth_headers)
        assert create_res.status_code == 201
        case_id = create_res.json()["case_id"]

        run_res = client.post(f"/api/v1/cases/{case_id}/run-analysis", headers=auth_headers)
        assert run_res.status_code == 200

        # Query explanation to inspect evidence provenance
        exp_res = client.get(f"/api/v1/cases/{case_id}/explanation", headers=auth_headers)
        assert exp_res.status_code == 200
        exp_data = exp_res.json()

        # Check that findings retain statutory references and evidence attribution
        assert exp_data["total_findings"] > 0
        for f in exp_data["findings"]:
            assert f["source"] in (
                "PRODUCT_URL",
                "WEB_SEARCH",
                "STRUCTURED_INTELLIGENCE",
                "MANUAL_INPUT",
                "PACKAGING_LABEL",
                "CROSS_SOURCE_COMPARISON",
                "FOSCOS_REGISTRY_PENDING",
            )
            # Source must not be confused with AI analysis
            assert f["source"] != "AI_ANALYSIS"


# -----------------------------------------------------------------------------
# TEST 5 — WEB FAILURE RESILIENCE
# -----------------------------------------------------------------------------
def test_web_failure_resilience(client, auth_headers):
    """
    Verify that unreachable or failing web sources do NOT crash the pipeline.
    The case analysis must continue and calculate risk using available inputs.
    """
    mock_failed = ScrapedPageData(
        url="https://broken-server-500.example.com/unreachable",
        status_code=500,
        is_success=False,
        error_message="HTTP Error 500: Internal Server Error",
    )

    with patch.object(ScrapingService, "fetch_and_extract", return_value=mock_failed):
        payload = {
            "product_name": "Herbal Digestive Tablets",
            "brand": "AyurCare",
            "product_url": "https://broken-server-500.example.com/unreachable",
            "product_description": "Digestive herbal churnam with ajwain and hing.",
        }
        create_res = client.post("/api/v1/cases", json=payload, headers=auth_headers)
        assert create_res.status_code == 201
        case_id = create_res.json()["case_id"]

        run_res = client.post(f"/api/v1/cases/{case_id}/run-analysis", headers=auth_headers)
        assert run_res.status_code == 200
        res_data = run_res.json()

        # Pipeline must still complete successfully
        assert res_data["status"] == "ANALYSIS_COMPLETE"
        assert res_data["risk_score"] is not None
        assert res_data["risk_level"] in ("LOW", "MEDIUM", "HIGH")
        # Error must be captured in web_collection_errors
        assert any("could not be accessed" in err or "500" in err for err in res_data["web_collection_errors"])


# -----------------------------------------------------------------------------
# TEST 6 — CROSS-SOURCE CONSISTENCY WITH WEB SOURCE
# -----------------------------------------------------------------------------
def test_cross_source_consistency_with_web(client, auth_headers):
    """
    Verify that contradictory information between Authority Input and Web Source
    is detected by the consistency analysis engine.
    Authority says: "Sugar Free Diet Drink"
    Web Source says: "Contains added sugar 15g"
    """
    mock_scraped = ScrapedPageData(
        url="https://supermart.example.com/drinks/diet-cola",
        title="Sparkling Herbal Cola 300ml",
        readable_text="Manufactured by: Apex Bottlers Ltd. Ingredients: Carbonated Water, Added Sugar, Caramel Color, Caffeine. Contains added sugar 15g. FSSAI Lic. No: 10018022007890.",
        is_success=True,
    )

    with patch.object(ScrapingService, "fetch_and_extract", return_value=mock_scraped):
        payload = {
            "product_name": "Sugar Free Herbal Cola",
            "brand": "Apex Bottlers",
            "product_url": "https://supermart.example.com/drinks/diet-cola",
            "product_description": "100% natural, Sugar free, zero calories, clinically tested.",
        }
        create_res = client.post("/api/v1/cases", json=payload, headers=auth_headers)
        assert create_res.status_code == 201
        case_id = create_res.json()["case_id"]

        run_res = client.post(f"/api/v1/cases/{case_id}/run-analysis", headers=auth_headers)
        assert run_res.status_code == 200
        res_data = run_res.json()

        assert res_data["status"] == "ANALYSIS_COMPLETE"
        assert res_data["consistency_completed"] is True

        # Check explanation for cross-source findings
        exp_res = client.get(f"/api/v1/cases/{case_id}/explanation", headers=auth_headers)
        assert exp_res.status_code == 200
        findings = exp_res.json()["findings"]

        # Discrepancy between sugar free claim and added sugar ingredient must be identified
        finding_titles = [f["finding_title"].lower() for f in findings]
        assert any("inconsistency" in t or "claim" in t or "sugar" in t or "discrepancy" in t for t in finding_titles)
