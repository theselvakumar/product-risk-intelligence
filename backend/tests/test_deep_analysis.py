import datetime
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.database.session import get_db
from app.main import app
from app.models.base import Base
from app.models.user import User
from app.schemas.intelligence import (
    CanonicalStructuredProduct,
    ProvenanceRecord,
    StructuredClaim,
    StructuredField,
    StructuredIngredient,
    StructuredLicense,
    StructuredProductMetadata,
)
from app.services.analysis.claim_analyzer import ClaimAnalyzer
from app.services.analysis.ingredient_analyzer import IngredientAnalyzer
from app.services.analysis.license_analyzer import LicenseAnalyzer
from app.services.analysis.manufacturer_analyzer import ManufacturerAnalyzer
from app.services.analysis.packaging_analyzer import PackagingAnalyzer

TEST_DB_FILE = "test_deep_analysis.db"
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
    import os
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
                email="officer.deepanalysis@drishti.gov.in",
                full_name="Dr. Rajesh Raman",
                badge_id="FSO-MH-MUM-089",
                role="AUTHORITY_OFFICER",
                jurisdiction_state="MH",
                jurisdiction_district="MH-MUM",
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
        claims={"role": "AUTHORITY_OFFICER", "badge_id": "FSO-MH-MUM-089"},
    )
    return {"Authorization": f"Bearer {token}"}


def create_sample_structured_product(
    licenses=None,
    ingredients=None,
    claims=None,
    mfr=None,
) -> CanonicalStructuredProduct:
    """Helper to construct mock canonical product intelligence."""
    meta = StructuredProductMetadata(
        name=StructuredField(
            value="AyurVed Herbal Protein Tonic",
            provenance=ProvenanceRecord(source_type="PACKAGING_LABEL", original_text="AyurVed Herbal Protein Tonic", confidence=0.95),
        ),
        manufacturer=StructuredField(
            value=mfr or "AyurVed Pharmaceuticals Ltd, Haridwar",
            provenance=ProvenanceRecord(source_type="PACKAGING_LABEL", original_text=mfr or "AyurVed Pharmaceuticals Ltd, Haridwar", confidence=0.95),
        ) if mfr else None,
    )
    return CanonicalStructuredProduct(
        case_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        product_metadata=meta,
        ingredients=ingredients or [],
        claims=claims or [],
        license_info=licenses or [],
        extraction_timestamp=datetime.datetime.now(datetime.timezone.utc),
    )


# ---------------------------------------------------------------------------
# 1. Independent License Analysis Tests
# ---------------------------------------------------------------------------
def test_license_analysis_module_independently():
    """Module 1: Checks presence, format inconsistency, source mismatch, and verification mandate."""
    analyzer = LicenseAnalyzer()

    # Case A: Missing license
    p_empty = create_sample_structured_product(licenses=[])
    res_empty = analyzer.analyze(p_empty.case_id, p_empty)
    assert any(f.finding_title == "License information missing" for f in res_empty.findings)
    assert res_empty.severity_suggestion == "HIGH"

    # Case B: Valid license detected
    lic1 = StructuredLicense(
        license_number="10018022007890",
        original_text="FSSAI Lic. No: 10018022007890",
        source_type="PACKAGING_OCR",
        confidence=0.95,
        is_valid_format=True,
    )
    p_valid = create_sample_structured_product(licenses=[lic1])
    res_valid = analyzer.analyze(p_valid.case_id, p_valid)
    assert any("License information detected" in f.finding_title for f in res_valid.findings)
    assert any("Requires verification" in f.finding_title for f in res_valid.findings)

    # Case C: Format inconsistent & Source mismatch
    lic2 = StructuredLicense(
        license_number="999invalid",
        original_text="Lic 999invalid",
        source_type="PRODUCT_URL",
        confidence=0.80,
        is_valid_format=False,
    )
    p_conflict = create_sample_structured_product(licenses=[lic1, lic2])
    res_conflict = analyzer.analyze(p_conflict.case_id, p_conflict)
    assert any("Format appears inconsistent" in f.finding_title for f in res_conflict.findings)
    assert any("Source consistency discrepancy" in f.finding_title for f in res_conflict.findings)


# ---------------------------------------------------------------------------
# 2. Independent Ingredient Analysis Tests
# ---------------------------------------------------------------------------
def test_ingredient_analysis_module_independently():
    """Module 2: Completeness, Knowledge Base prohibited substance match (Rhodamine B) & sweeteners."""
    analyzer = IngredientAnalyzer()

    # Case A: Missing ingredients
    p_empty = create_sample_structured_product(ingredients=[])
    res_empty = analyzer.analyze(p_empty.case_id, p_empty)
    assert any("Ingredient information incomplete" in f.finding_title for f in res_empty.findings)

    # Case B: Normal ingredients + Prohibited substance + Restricted sweetener
    ing1 = StructuredIngredient(
        ingredient_name="Wheat Flour", original_text="Wheat Flour", source_type="PACKAGING_OCR", confidence=0.95
    )
    ing2 = StructuredIngredient(
        ingredient_name="Rhodamine B (Color)", original_text="Rhodamine B", source_type="PACKAGING_OCR", confidence=0.98
    )
    ing3 = StructuredIngredient(
        ingredient_name="Aspartame", original_text="Sweetener (Aspartame)", source_type="PACKAGING_OCR", confidence=0.95
    )
    p_kb = create_sample_structured_product(ingredients=[ing1, ing2, ing3])
    res_kb = analyzer.analyze(p_kb.case_id, p_kb)

    # Must detect prohibited chemical concern with CRITICAL severity
    assert any(f.finding_title == "Potential knowledge base concern" and f.severity == "CRITICAL" for f in res_kb.findings)
    # Must flag sweetener advisory requirement
    assert any("Requires review" in f.finding_title for f in res_kb.findings)
    assert res_kb.severity_suggestion == "CRITICAL"


# ---------------------------------------------------------------------------
# 3. Independent Claim Analysis Tests
# ---------------------------------------------------------------------------
def test_claim_analysis_module_independently():
    """Module 3: Evaluates disease-related, guaranteed, scientific, and promotional claims."""
    analyzer = ClaimAnalyzer()

    claims = [
        StructuredClaim(
            claim_text="Clinically proven to cure diabetes and cancer",
            original_text="Clinically proven to cure diabetes and cancer",
            claim_category="DISEASE_RISK_REDUCTION_OR_CURE",
            source_type="PRODUCT_URL",
            confidence=0.95,
        ),
        StructuredClaim(
            claim_text="Guaranteed results in 7 days",
            original_text="Guaranteed results in 7 days",
            claim_category="SUPERLATIVE_OR_ABSOLUTE",
            source_type="PRODUCT_URL",
            confidence=0.90,
        ),
        StructuredClaim(
            claim_text="Scientifically tested formulation",
            original_text="Scientifically tested formulation",
            claim_category="GENERAL_COMMERCIAL",
            source_type="PACKAGING_OCR",
            confidence=0.88,
        ),
        StructuredClaim(
            claim_text="Doctor recommended for pediatric use",
            original_text="Doctor recommended for pediatric use",
            claim_category="GENERAL_COMMERCIAL",
            source_type="PACKAGING_OCR",
            confidence=0.88,
        ),
    ]

    p_claims = create_sample_structured_product(claims=claims)
    res = analyzer.analyze(p_claims.case_id, p_claims)

    titles = [f.finding_title for f in res.findings]
    assert any("Disease-related claim identified" in t for t in titles)
    assert any("Guaranteed result claim identified" in t for t in titles)
    assert any("Scientific claim identified" in t for t in titles)
    assert any("Promotional endorsement claim identified" in t for t in titles)
    assert res.severity_suggestion == "HIGH"


# ---------------------------------------------------------------------------
# 4. Independent Packaging Analysis Tests
# ---------------------------------------------------------------------------
def test_packaging_analysis_module_independently():
    """Module 4: Evaluates 6 statutory packaging elements (Name, Mfr, Ingredients, Lic, Dates, Warnings)."""
    analyzer = PackagingAnalyzer()

    # Product with ingredients & license, but missing dates and warnings
    lic = StructuredLicense(license_number="10018022007890", original_text="Lic 10018022007890", source_type="PACKAGING_OCR", confidence=0.95)
    ing = [
        StructuredIngredient(ingredient_name="Milk", original_text="Milk", source_type="PACKAGING_OCR", confidence=0.95, is_allergen=True, allergen_category="MILK"),
        StructuredIngredient(ingredient_name="Sugar", original_text="Sugar", source_type="PACKAGING_OCR", confidence=0.95),
    ]
    p_pack = create_sample_structured_product(licenses=[lic], ingredients=ing, mfr="Alpha Foods Ltd")
    p_pack.allergens_detected = ["MILK"]

    res = analyzer.analyze(p_pack.case_id, p_pack)
    status_map = res.details["element_status"]

    assert status_map["Product Name"] == "PRESENT"
    assert status_map["Manufacturer"] == "PRESENT"
    assert status_map["Ingredients"] == "PRESENT"
    assert status_map["License Information"] == "PRESENT"
    assert status_map["Dates"] == "MISSING"
    assert status_map["Warnings"] == "MISSING"  # Missing because allergen is present without warning!

    assert any("Mandatory packaging element missing: Dates" in f.finding_title for f in res.findings)


# ---------------------------------------------------------------------------
# 5. Independent Manufacturer Analysis Tests
# ---------------------------------------------------------------------------
def test_manufacturer_analysis_module_independently():
    """Module 5: Evaluates missing manufacturer and cross-source entity discrepancies."""
    analyzer = ManufacturerAnalyzer()

    # Case A: Missing manufacturer
    p_no_mfr = create_sample_structured_product(mfr=None)
    res_no_mfr = analyzer.analyze(p_no_mfr.case_id, p_no_mfr)
    assert any("Manufacturer information missing" in f.finding_title for f in res_no_mfr.findings)

    # Case B: Cross-source discrepancy (e.g. manual vs web listing)
    class MockSource:
        source_type = "PRODUCT_URL"
        raw_payload_json = {"manufacturer": "Zeta Global Imports Pvt Ltd"}
        raw_content = "Marketed by Zeta Global Imports"

    p_mfr = create_sample_structured_product(mfr="AyurVed Pharmaceuticals Ltd")
    res_mismatch = analyzer.analyze(p_mfr.case_id, p_mfr, raw_sources=[MockSource()])
    assert any("Different manufacturer names across sources" in f.finding_title for f in res_mismatch.findings)
    assert res_mismatch.severity_suggestion == "HIGH"


# ---------------------------------------------------------------------------
# 6. End-to-End API Integration & Database Persistence
# ---------------------------------------------------------------------------
def test_api_deep_analysis_workflow(client, auth_header):
    """Full API execution: POST /cases/{case_id}/deep-analysis & GET /cases/{case_id}/deep-analysis."""
    # 1. Create a case
    payload = {
        "product_name": "Divya Sanjeevani Herbal Cure",
        "brand": "Divya Organics",
        "category": "AYURVEDIC",
        "product_description": (
            "Proprietary formula. Ingredients: Amla, Giloy, Rhodamine B.\n"
            "Claims: Scientifically proven to cure cancer. 100% Guaranteed results.\n"
            "FSSAI Lic No: 10018022007890.\n"
            "Mfg by: Divya Agro Industries, Haridwar."
        ),
    }
    submit_res = client.post("/api/v1/cases", data=payload, headers=auth_header)
    assert submit_res.status_code == 201
    case_id = submit_res.json()["case_id"]

    # 2. Trigger Deep Analysis
    run_res = client.post(f"/api/v1/cases/{case_id}/deep-analysis", headers=auth_header)
    assert run_res.status_code == 200
    report = run_res.json()

    assert report["case_id"] == case_id
    assert report["total_checks"] > 0
    assert report["total_findings"] > 0
    assert "modules" in report
    assert "LICENSE_ANALYSIS" in report["modules"]
    assert "INGREDIENT_ANALYSIS" in report["modules"]
    assert "CLAIM_ANALYSIS" in report["modules"]
    assert "PACKAGING_ANALYSIS" in report["modules"]
    assert "MANUFACTURER_ANALYSIS" in report["modules"]

    # Rhodamine B must trigger critical finding
    assert report["critical_findings_count"] >= 1

    # 3. Retrieve Report via GET /cases/{case_id}/deep-analysis
    get_res = client.get(f"/api/v1/cases/{case_id}/deep-analysis", headers=auth_header)
    assert get_res.status_code == 200
    assert get_res.json()["case_id"] == case_id
