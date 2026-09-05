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
from app.models.product import ProductImage, ProductSource
from app.schemas.evidence_package import EvidenceOrigin, EvidenceType

TEST_DB_FILE = "test_evidence.db"
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
                email="officer.evidence@drishti.gov.in",
                full_name="Rajesh Sharma",
                badge_id="FSO-DL-ND-007",
                role="AUTHORITY_OFFICER",
                jurisdiction_state="DL",
                jurisdiction_district="DL-ND",
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
        claims={"role": "AUTHORITY_OFFICER", "badge_id": "FSO-DL-ND-007"},
    )
    return {"Authorization": f"Bearer {token}"}


def _create_sample_case(client, auth_header, description: str, notes: str = "Surveillance sample") -> str:
    payload = {
        "product_name": "AyurPure Diabetic Shield Powder",
        "brand": "AyurPure Naturals",
        "category": "HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS",
        "product_description": description,
        "product_url": "https://quickcommerce.example.com/item/ayurpure-diabetic-shield",
        "notes": notes,
    }
    res = client.post("/api/v1/cases", data=payload, headers=auth_header)
    assert res.status_code == 201
    case_id = res.json()["case_id"]

    # Run deep analysis to generate findings
    da_res = client.post(f"/api/v1/cases/{case_id}/deep-analysis", headers=auth_header)
    assert da_res.status_code == 200

    return case_id


# ---------------------------------------------------------------------------
# 1. Evidence Package Structure Completeness
# ---------------------------------------------------------------------------
def test_evidence_package_structure(client, auth_header):
    """GET /evidence-package returns all required fields for statutory compliance."""
    case_id = _create_sample_case(
        client, auth_header,
        description=(
            "AyurPure Diabetic Shield Powder. Cures Type 2 Diabetes within 30 days.\n"
            "Contains Gymnema Sylvestre, Vijaysar, Karela extract, and Jamun seed.\n"
            "Manufactured by: AyurPure Health Corp, Haridwar, Uttarakhand.\n"
            "FSSAI Lic. No: 10019011005432."
        )
    )

    res = client.get(f"/api/v1/cases/{case_id}/evidence-package", headers=auth_header)
    assert res.status_code == 200
    pkg = res.json()

    # Core identification fields
    assert pkg["case_id"] == case_id
    assert "case_number" in pkg
    assert "product_id" in pkg
    assert "product_name" in pkg
    assert pkg["submission_timestamp"] is not None

    # Categorized evidence repositories
    for repo in [
        "url_evidence", "image_evidence", "ocr_evidence",
        "submitted_text_evidence", "extracted_data_evidence",
        "finding_bundles"
    ]:
        assert repo in pkg, f"Missing evidence repository: {repo}"
        assert isinstance(pkg[repo], list)

    # Statutory metadata & notes
    assert pkg["total_evidence_records"] >= 1
    assert pkg["coverage_percentage"] >= 0.0
    assert "Primary source evidence" in pkg["integrity_note"]


# ---------------------------------------------------------------------------
# 2. Every Finding Linked to Evidence (Chain of Custody)
# ---------------------------------------------------------------------------
def test_every_finding_linked_to_evidence(client, auth_header):
    """
    Statutory Requirement:
    Every single finding must link to original primary evidence.
    Authority officer sees: FINDING -> WHY FLAGGED -> SOURCE -> ORIGINAL EVIDENCE.
    """
    case_id = _create_sample_case(
        client, auth_header,
        description=(
            "AyurPure Diabetic Shield Powder. Clinically proven 100% cure for diabetes.\n"
            "Ingredients: Gymnema, Vijaysar, Undeclared Glibenclamide.\n"
            "FSSAI Lic. No: 10019011005432."
        )
    )

    res = client.get(f"/api/v1/cases/{case_id}/evidence-package", headers=auth_header)
    assert res.status_code == 200
    pkg = res.json()

    bundles = pkg["finding_bundles"]
    assert len(bundles) > 0, "Expected at least 1 finding bundle."

    for bundle in bundles:
        # Step 1: FINDING
        assert bundle["finding_title"], "Finding must have a title"
        assert bundle["severity"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]

        # Step 2: WHY FLAGGED
        assert bundle["why_flagged"], "Finding must provide a statutory why_flagged explanation"
        assert len(bundle["why_flagged"]) > 5

        # Step 3: SOURCE
        assert bundle["source"], "Finding must specify its source channel"
        assert "source_metadata" in bundle
        assert isinstance(bundle["source_metadata"], dict)

        # Step 4: ORIGINAL EVIDENCE
        primary_ev = bundle["primary_evidence"]
        assert len(primary_ev) > 0, (
            f"Statutory breach: finding '{bundle['finding_title']}' has no linked primary evidence!"
        )
        for ev in primary_ev:
            assert ev["ai_generated"] is False, "Primary evidence must not be AI-generated"
            assert ev["evidence_origin"] != EvidenceOrigin.AI_ANALYSIS
            assert ev["content_text"] or ev["content_uri"], "Evidence must have content text or URI"


# ---------------------------------------------------------------------------
# 3. Strict AI Segregation Contract
# ---------------------------------------------------------------------------
def test_strict_ai_segregation_contract(client, auth_header):
    """
    Statutory Requirement:
    Do not allow AI-generated statements to appear as source evidence without
    clearly marking them as AI analysis.
    """
    case_id = _create_sample_case(
        client, auth_header,
        description="High protein snack bar with 0g sugar claims."
    )

    res = client.get(f"/api/v1/cases/{case_id}/evidence-package", headers=auth_header)
    assert res.status_code == 200
    pkg = res.json()

    # Verify all primary repositories contain ZERO AI statements
    all_primary_items = (
        pkg["url_evidence"] + pkg["image_evidence"] + pkg["ocr_evidence"]
        + pkg["submitted_text_evidence"] + pkg["extracted_data_evidence"]
    )
    for b in pkg["finding_bundles"]:
        all_primary_items.extend(b["primary_evidence"])

    for item in all_primary_items:
        assert item["ai_generated"] is False, f"Primary evidence record '{item['record_id']}' marked as AI generated!"
        assert item["evidence_origin"] != "AI_ANALYSIS", f"Primary evidence record '{item['record_id']}' has AI_ANALYSIS origin!"

    # Verify that AI notes in finding bundles are strictly marked with ai_generated=True
    total_ai_notes = 0
    for b in pkg["finding_bundles"]:
        for note in b["ai_analysis_notes"]:
            total_ai_notes += 1
            assert note["ai_generated"] is True, "AI analysis note must be marked ai_generated=True"
            assert note["evidence_origin"] == "AI_ANALYSIS", "AI note must have AI_ANALYSIS origin"
            assert "metadata" in note
            assert "ai_label" in note["metadata"]

    assert total_ai_notes >= len(pkg["finding_bundles"]), "Expected each finding to have an AI analysis note"


# ---------------------------------------------------------------------------
# 4. Evidence Types & Timestamps
# ---------------------------------------------------------------------------
def test_evidence_types_and_timestamps(client, auth_header):
    """Verify supported evidence types (URL, Image, OCR, Submitted Text) with timestamp tracking."""
    case_id = _create_sample_case(
        client, auth_header,
        description="Organic cold-pressed sesame oil. FSSAI Lic. No: 10020011009876."
    )

    res = client.get(f"/api/v1/cases/{case_id}/evidence-package", headers=auth_header)
    assert res.status_code == 200
    pkg = res.json()

    # URL evidence
    assert len(pkg["url_evidence"]) >= 1
    url_item = pkg["url_evidence"][0]
    assert url_item["evidence_type"] == EvidenceType.URL
    assert url_item["content_uri"].startswith("http")
    assert url_item["capture_timestamp"] is not None

    # Submitted text evidence
    assert len(pkg["submitted_text_evidence"]) >= 1
    sub_item = pkg["submitted_text_evidence"][0]
    assert sub_item["evidence_type"] == EvidenceType.SUBMITTED_TEXT
    assert sub_item["content_text"] is not None
    assert sub_item["capture_timestamp"] is not None


# ---------------------------------------------------------------------------
# 5. Cryptographic & Statutory Integrity Verification Endpoint
# ---------------------------------------------------------------------------
def test_evidence_integrity_verification_endpoint(client, auth_header):
    """POST /evidence-package/verify performs automated statutory integrity audits."""
    case_id = _create_sample_case(
        client, auth_header,
        description="Premium Shilajit resin. Boosts immunity and vigor. FSSAI Lic. No: 10022011001234."
    )

    res = client.post(f"/api/v1/cases/{case_id}/evidence-package/verify", headers=auth_header)
    assert res.status_code == 200
    verif = res.json()

    assert verif["case_id"] == case_id
    assert verif["all_findings_linked"] is True
    assert verif["ai_separation_verified"] is True
    assert verif["unmarked_ai_items_found"] == 0
    assert verif["hash_verification_passed"] is True
    assert verif["timestamps_valid"] is True
    assert verif["integrity_score"] >= 95.0
    assert len(verif["verification_details"]) >= 3
    assert verif["verified_at"] is not None


# ---------------------------------------------------------------------------
# 6. Unauthenticated Access Rejection
# ---------------------------------------------------------------------------
def test_unauthenticated_access_rejected(client):
    """Ensure non-authenticated users cannot access evidence packages."""
    dummy_id = str(uuid.uuid4())
    res_get = client.get(f"/api/v1/cases/{dummy_id}/evidence-package")
    assert res_get.status_code in [401, 403]

    res_post = client.post(f"/api/v1/cases/{dummy_id}/evidence-package/verify")
    assert res_post.status_code in [401, 403]
