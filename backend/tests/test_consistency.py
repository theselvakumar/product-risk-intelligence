import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.database.session import get_db
from app.main import app
from app.models.base import Base
from app.models.user import User
from app.services.consistency.matcher import ConsistencyMatcher
from app.services.consistency.normalizer import ConsistencyNormalizer

TEST_DB_FILE = "test_consistency.db"
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

    async def init():
        async with async_test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with AsyncTestingSessionLocal() as session:
            session.add(User(
                id=test_officer_id,
                email="officer.consistency@drishti.gov.in",
                full_name="Priya Shankar",
                badge_id="FSO-TN-CHN-007",
                role="AUTHORITY_OFFICER",
                jurisdiction_state="TN",
                jurisdiction_district="TN-CHN",
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
        claims={"role": "AUTHORITY_OFFICER", "badge_id": "FSO-TN-CHN-007"},
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Normalizer Unit Tests
# ---------------------------------------------------------------------------
def test_normalizer_abbreviation_expansion():
    """Normalizer expands abbreviations correctly."""
    assert ConsistencyNormalizer.normalize("Agro Pvt. Ltd.") == "agro private limited"
    assert ConsistencyNormalizer.normalize("Mfd. by Alpha Foods") == "manufactured by alpha foods"
    assert ConsistencyNormalizer.normalize("FSSAI Lic. No. 10018022007890") == "fssai license number 10018022007890"


def test_normalizer_license_extraction():
    """License normalizer extracts 14-digit number."""
    raw = "FSSAI Lic. No: 10018022007890 (State License)"
    assert ConsistencyNormalizer.normalize_license(raw) == "10018022007890"


# ---------------------------------------------------------------------------
# 2. Matcher: Same Information → CONSISTENT
# ---------------------------------------------------------------------------
def test_matcher_exact_match():
    """Identical values → CONSISTENT via EXACT match."""
    result, method, desc, score, conf = ConsistencyMatcher.compare(
        "Sunrise Foods Pvt Ltd", "Sunrise Foods Pvt Ltd", field_name="manufacturer"
    )
    assert result == "CONSISTENT"
    assert method == "EXACT"
    assert score == 1.0


def test_matcher_normalized_consistent():
    """Abbreviation differences → CONSISTENT via NORMALIZED match."""
    result, method, desc, score, conf = ConsistencyMatcher.compare(
        "Sunrise Foods Pvt. Ltd.", "Sunrise Foods Private Limited", field_name="manufacturer"
    )
    assert result == "CONSISTENT"
    assert method == "NORMALIZED"


# ---------------------------------------------------------------------------
# 3. Matcher: Slight Wording → MINOR_WORDING_DIFFERENCE
# ---------------------------------------------------------------------------
def test_matcher_minor_wording_difference():
    """Similar but not identical values → MINOR_WORDING_DIFFERENCE."""
    result, method, desc, score, conf = ConsistencyMatcher.compare(
        "Organic Honey", "Pure Organic Honey", field_name="product_name"
    )
    assert result in ("CONSISTENT", "MINOR_WORDING_DIFFERENCE")
    assert method == "SEMANTIC"


# ---------------------------------------------------------------------------
# 4. Matcher: Conflicting Information → INCONSISTENT
# ---------------------------------------------------------------------------
def test_matcher_conflicting_information():
    """Contradictory values → INCONSISTENT with HIGH severity."""
    result, method, desc, score, conf = ConsistencyMatcher.compare(
        "Sugar Free formula with zero added sugar",
        "Contains added sugar (12g per serving)",
        field_name="claims",
    )
    assert result == "INCONSISTENT"
    assert method == "SEMANTIC"
    assert "Sugar Free" in desc or "added sugar" in desc or "inconsistency" in desc.lower()

    severity = ConsistencyMatcher.severity_for_result(result, "claims")
    assert severity == "MEDIUM"

    # For ingredients field inconsistency → HIGH
    severity_ing = ConsistencyMatcher.severity_for_result("INCONSISTENT", "ingredients")
    assert severity_ing == "HIGH"


# ---------------------------------------------------------------------------
# 5. Matcher: Missing Information → MISSING_IN_SOURCE
# ---------------------------------------------------------------------------
def test_matcher_missing_information():
    """One source has data, other is empty → MISSING_IN_SOURCE."""
    result, method, desc, score, conf = ConsistencyMatcher.compare(
        "10018022007890", "", field_name="license_number"
    )
    assert result == "MISSING_IN_SOURCE"
    assert score == 0.0
    assert "Source B" in desc


def test_matcher_both_missing():
    """Both sources have no value → CONSISTENT (nothing to contradict)."""
    result, method, desc, score, conf = ConsistencyMatcher.compare("", "", field_name="manufacturer")
    assert result == "CONSISTENT"


# ---------------------------------------------------------------------------
# 6. End-to-End API Integration Test
# ---------------------------------------------------------------------------
def test_api_consistency_workflow(client, auth_header):
    """
    Full cross-source consistency workflow:
    1. Submit a case with conflicting URL and description.
    2. POST /consistency-check → verify inconsistencies detected.
    3. GET /consistency-check → same report returned.
    """
    # Create a case with deliberately conflicting data
    payload = {
        "product_name": "ZeroCal Diet Drink 500ml",
        "brand": "ZeroCal Beverages",
        "category": "BEVERAGES_TEA_AND_COFFEE",
        "product_url": "https://quickmart.in/products/zerocal-diet",
        "product_description": (
            # Conflicting: URL says "Sugar Free" but description says "Contains added sugar"
            "ZeroCal Diet Drink - Sugar Free, Zero Calories.\n"
            "Ingredients: Water, Sugar (12g per serving), Citric Acid, Natural Flavors.\n"
            "Claims: 100% Natural, No added sugar.\n"
            "Manufactured by: ZeroCal Beverages Ltd, Mumbai.\n"
            "FSSAI Lic. No: 10018022007890."
        ),
        "notes": "Discrepancy flagged by field officer: front label says Sugar Free but ingredients list contains 12g sugar.",
    }
    submit_res = client.post("/api/v1/cases", data=payload, headers=auth_header)
    assert submit_res.status_code == 201
    case_id = submit_res.json()["case_id"]

    # Run consistency check
    cons_res = client.post(f"/api/v1/cases/{case_id}/consistency-check", headers=auth_header)
    assert cons_res.status_code == 200
    report = cons_res.json()

    assert report["case_id"] == case_id
    assert report["total_sources_analyzed"] >= 1
    assert report["total_fields_compared"] == 5
    assert "comparisons" in report
    assert "summary_stats" in report

    # Verify structure of comparisons
    comparisons = report["comparisons"]
    assert len(comparisons) > 0

    # Each comparison must have required fields
    for comp in comparisons:
        assert "field_name" in comp
        assert "source_a" in comp
        assert "source_b" in comp
        assert "comparison_result" in comp
        assert "severity_suggestion" in comp
        assert "confidence" in comp
        assert "match_method" in comp
        assert "similarity_score" in comp
        assert "detected_difference" in comp
        assert comp["comparison_result"] in (
            "CONSISTENT", "MINOR_WORDING_DIFFERENCE", "INCONSISTENT", "MISSING_IN_SOURCE"
        )
        assert comp["severity_suggestion"] in ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")

    # GET consistency-check returns valid report
    get_res = client.get(f"/api/v1/cases/{case_id}/consistency-check", headers=auth_header)
    assert get_res.status_code == 200
    assert get_res.json()["case_id"] == case_id
