import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.database.session import get_db
from app.main import app
from app.models.base import Base
from app.models.user import User
from app.services.intelligence.claim_classifier import ClaimClassifier
from app.services.intelligence.deduplicator import EntityDeduplicator
from app.services.intelligence.ingredient_parser import IngredientParser
from app.services.intelligence.license_extractor import LicenseExtractor
from app.services.intelligence.normalizer import TextNormalizer
from app.services.intelligence.service import ProductIntelligenceService

TEST_DB_FILE = "test_intelligence.db"
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
                email="officer.intelligence@drishti.gov.in",
                full_name="Dr. Kavita Nair",
                badge_id="FSO-DL-NORTH-044",
                role="AUTHORITY_OFFICER",
                jurisdiction_state="DL",
                jurisdiction_district="DL-NORTH",
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
        claims={"role": "AUTHORITY_OFFICER", "badge_id": "FSO-DL-NORTH-044"},
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Ingredient Parser & Allergen Tests
# ---------------------------------------------------------------------------
def test_ingredient_parser_nested_and_ins():
    """Parses nested sub-components, resolves INS additive codes, and flags allergens."""
    raw_text = (
        "Ingredients: Milk Solids (Whole Milk Powder, Whey Protein), Sugar, "
        "Wheat Flour, Emulsifier (INS 322), Acidity Regulator (INS 330), Preservative (211)."
    )
    parsed = IngredientParser.parse_ingredients_from_text(raw_text, source_type="PACKAGING_OCR")

    assert len(parsed) >= 5

    # Check INS resolution
    ins_items = [i for i in parsed if i.ins_number]
    assert any("INS 322" in i.ins_number for i in ins_items)
    assert any("INS 330" in i.ins_number for i in ins_items)
    assert any("INS 211" in i.ins_number for i in ins_items)

    # Check Allergen detection
    allergens = [i.allergen_category for i in parsed if i.is_allergen]
    assert "MILK" in allergens
    assert "GLUTEN" in allergens

    # Verify source and original text preservation
    first_item = parsed[0]
    assert first_item.source_type == "PACKAGING_OCR"
    assert len(first_item.original_text) > 0
    assert first_item.confidence > 0.0


# ---------------------------------------------------------------------------
# 2. Claim Classification Tests
# ---------------------------------------------------------------------------
def test_claim_classifier_prohibited_and_statutory():
    """Identifies statutory claims and flags prohibited Section 24 curative claims."""
    raw_text = (
        "100% Pure Organic Ayurvedic Elixir.\n"
        "Guaranteed cure for diabetes and hypertension in 30 days.\n"
        "Zero Added Sugar and High Protein.\n"
        "Boosts immunity and vitality naturally."
    )
    claims = ClaimClassifier.extract_claims_from_text(raw_text, source_type="PRODUCT_URL")

    assert len(claims) >= 3

    # Check prohibited disease claim
    prohibited = [c for c in claims if c.is_potentially_prohibited]
    assert len(prohibited) >= 1
    assert prohibited[0].claim_category == "DISEASE_RISK_REDUCTION_OR_CURE"
    assert "cure for diabetes" in prohibited[0].original_text.lower()
    assert prohibited[0].source_type == "PRODUCT_URL"

    # Check superlative & nutrition claims
    categories = [c.claim_category for c in claims]
    assert "SUPERLATIVE_OR_ABSOLUTE" in categories
    assert "NUTRITION_CONTENT" in categories
    assert "HEALTH_OR_FUNCTIONAL" in categories


# ---------------------------------------------------------------------------
# 3. License Extraction Tests
# ---------------------------------------------------------------------------
def test_license_extractor_fssai_validation():
    """Extracts 14-digit FSSAI licenses, analyzes state code and license type."""
    sample_text = (
        "Manufactured by Vedic Labs Ltd. FSSAI Lic No: 10018022007890.\n"
        "Marketed by Agro Retail. Registration No. 20721012000555."
    )
    lics = LicenseExtractor.extract_licenses(sample_text, source_type="OFFICER_DESCRIPTION")

    assert len(lics) == 2

    # Check Central/State license
    lic1 = next(l for l in lics if l.license_number == "10018022007890")
    assert lic1.license_type == "STATE_OR_CENTRAL_LICENSE"
    assert lic1.is_valid_format is True
    assert lic1.source_type == "OFFICER_DESCRIPTION"

    # Check Registration
    lic2 = next(l for l in lics if l.license_number == "20721012000555")
    assert lic2.license_type == "REGISTRATION"
    assert "Delhi" in lic2.state_code


# ---------------------------------------------------------------------------
# 4. Deduplication & Cross-Source Fusion Tests
# ---------------------------------------------------------------------------
def test_entity_deduplication():
    """Fuses entities from multiple sources and combines source provenance."""
    # Two identical claims from different sources
    c1 = ClaimClassifier.extract_claims_from_text("100% Pure Cold-Pressed Honey", source_type="PRODUCT_URL")[0]
    c2 = ClaimClassifier.extract_claims_from_text("100% pure cold-pressed honey", source_type="PACKAGING_OCR")[0]

    deduped_claims, merged_c = EntityDeduplicator.deduplicate_claims([c1, c2])
    assert len(deduped_claims) == 1
    assert merged_c == 1
    assert "PRODUCT_URL" in deduped_claims[0].source_type
    assert "PACKAGING_OCR" in deduped_claims[0].source_type

    # Overlapping ingredients
    i1 = IngredientParser.parse_single_ingredient("Sugar", source_type="PRODUCT_URL")
    i2 = IngredientParser.parse_single_ingredient("Cane Sugar (Refined)", source_type="PACKAGING_OCR")

    deduped_ing, merged_i = EntityDeduplicator.deduplicate_ingredients([i1, i2])
    assert len(deduped_ing) == 1
    assert merged_i == 1
    assert "PRODUCT_URL" in deduped_ing[0].source_type


# ---------------------------------------------------------------------------
# 5. End-to-End Case Intelligence Structuring API Tests
# ---------------------------------------------------------------------------
def test_api_structure_intelligence_workflow(client, auth_header):
    """
    Test comprehensive intelligence structuring from mixed sources:
    1. Submit product with Description & URL.
    2. Post structured intelligence endpoint.
    3. Verify canonical product structure, ingredients, claims, and separate storage.
    """
    # 1. Create a case with rich input sources
    payload = {
        "product_name": "AyurVital Diabetic Balance Shake 400g",
        "brand": "AyurVital Health",
        "category": "HEALTH_SUPPLEMENTS",
        "product_url": "https://quickmart.in/products/ayurvital-shake",
        "product_description": (
            "Proprietary Diabetic Formula. Ingredients: Whole Milk Powder, Whey Protein Concentrate, "
            "Garcinia extract, Emulsifier (INS 322), Preservative (211).\n"
            "Claims: 100% Pure Natural Herbal Care. Clinically proven to reverse diabetes.\n"
            "FSSAI Lic. No: 10018022007890."
        ),
        "notes": "Surveillance initiated on suspect Section 24 curative claim.",
    }
    submit_res = client.post("/api/v1/cases", data=payload, headers=auth_header)
    assert submit_res.status_code == 201
    case_id = submit_res.json()["case_id"]

    # 2. Trigger structure intelligence via POST /cases/{case_id}/structure-intelligence
    struct_res = client.post(f"/api/v1/cases/{case_id}/structure-intelligence", headers=auth_header)
    assert struct_res.status_code == 200
    dossier = struct_res.json()

    # Verify Product Identity
    assert dossier["case_id"] == case_id
    assert dossier["product_metadata"]["name"]["value"] == "AyurVital Diabetic Balance Shake 400g"
    assert dossier["product_metadata"]["category"]["value"] == "HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS"

    # Verify Ingredients
    ingredients = dossier["ingredients"]
    assert len(ingredients) >= 3
    assert any("Milk" in i["ingredient_name"] for i in ingredients)
    assert any("INS 322" in (i["ins_number"] or "") for i in ingredients)
    assert "MILK" in dossier["allergens_detected"]

    # Verify Claims
    claims = dossier["claims"]
    assert len(claims) >= 2
    prohibited_claims = [c for c in claims if c["is_potentially_prohibited"]]
    assert len(prohibited_claims) >= 1
    assert "reverse diabetes" in prohibited_claims[0]["original_text"].lower()

    # Verify License Info
    licenses = dossier["license_info"]
    assert len(licenses) >= 1
    assert licenses[0]["license_number"] == "10018022007890"

    # Verify Deduplication & Provenance Summary
    assert "duplicate_metrics" in dossier
    assert "provenance_summary" in dossier

    # 3. Retrieve via GET /cases/{case_id}/structure-intelligence
    get_res = client.get(f"/api/v1/cases/{case_id}/structure-intelligence", headers=auth_header)
    assert get_res.status_code == 200
    assert get_res.json()["schema_version"] == "v1.0-FSSAI-Intelligence"
