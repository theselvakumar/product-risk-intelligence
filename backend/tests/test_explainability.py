import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.database.session import get_db
from app.main import app
from app.models.base import Base
from app.models.user import User

TEST_DB_FILE = "test_explainability.db"
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
                email="officer.explain@drishti.gov.in",
                full_name="Meera Krishnamurthy",
                badge_id="FSO-TN-MDS-011",
                role="AUTHORITY_OFFICER",
                jurisdiction_state="TN",
                jurisdiction_district="TN-MDS",
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
        claims={"role": "AUTHORITY_OFFICER", "badge_id": "FSO-TN-MDS-011"},
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Helper: create a fully-analysed case
# ---------------------------------------------------------------------------
def _create_full_case(client, auth_header, description: str, notes: str = "") -> str:
    payload = {
        "product_name": "TestProduct For Explanation",
        "brand": "TestBrand",
        "category": "HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS",
        "product_description": description,
        "notes": notes,
    }
    res = client.post("/api/v1/cases", data=payload, headers=auth_header)
    assert res.status_code == 201
    case_id = res.json()["case_id"]

    # Run deep analysis to generate findings
    da_res = client.post(f"/api/v1/cases/{case_id}/deep-analysis", headers=auth_header)
    assert da_res.status_code == 200

    # Run risk assessment
    rk_res = client.post(f"/api/v1/cases/{case_id}/risk-assessment", headers=auth_header)
    assert rk_res.status_code == 200

    return case_id


# ---------------------------------------------------------------------------
# 1. Report Structure Completeness
# ---------------------------------------------------------------------------
def test_explanation_report_structure(client, auth_header):
    """GET /explanation returns all required top-level fields."""
    case_id = _create_full_case(
        client, auth_header,
        description=(
            "SlimFast Garcinia Ultra. Clinically proven for rapid weight loss.\n"
            "Ingredients: Garcinia Cambogia, Green Tea Extract, Chromium Picolinate.\n"
            "Manufactured by: SlimFast Labs Pvt. Ltd., Hyderabad.\n"
            "FSSAI Lic. No: 10018022007890."
        )
    )
    res = client.get(f"/api/v1/cases/{case_id}/explanation", headers=auth_header)
    assert res.status_code == 200
    report = res.json()

    # All required top-level fields
    required = [
        "case_id", "case_number", "product", "total_findings",
        "findings_by_severity", "findings", "why_flagged_summary",
        "generated_at", "provenance_note",
    ]
    for field in required:
        assert field in report, f"Missing field: {field}"

    # Product section
    product = report["product"]
    assert "product_id" in product
    assert "product_name" in product

    # Provenance note is non-empty
    assert len(report["provenance_note"]) > 20


# ---------------------------------------------------------------------------
# 2. Evidence Traceability — Every Finding Has a Reason
# ---------------------------------------------------------------------------
def test_evidence_traceability(client, auth_header):
    """Every finding must have finding_title, description, severity, and reason_for_flagging."""
    case_id = _create_full_case(
        client, auth_header,
        description=(
            "BioEnergy Max Capsules. Cures diabetes and hypertension.\n"
            "Ingredients: Rhodamine B dye, Bitter Melon, Cinnamon.\n"
            "FSSAI Lic. No: 10018022007890."
        )
    )
    res = client.get(f"/api/v1/cases/{case_id}/explanation", headers=auth_header)
    assert res.status_code == 200
    report = res.json()

    findings = report["findings"]
    assert isinstance(findings, list)

    for f in findings:
        # Required traceable fields
        assert "finding_id" in f, "finding_id missing"
        assert "finding_title" in f and f["finding_title"], "finding_title empty"
        assert "description" in f and f["description"], "description empty"
        assert "severity" in f
        assert "source" in f
        assert "confidence" in f
        assert "reason_for_flagging" in f and f["reason_for_flagging"], "reason_for_flagging empty"
        assert "evidence" in f
        assert isinstance(f["evidence"], list)
        assert 0.0 <= f["confidence"] <= 1.0
        assert f["severity"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")


# ---------------------------------------------------------------------------
# 3. No Invented Evidence — Only Stored Records Referenced
# ---------------------------------------------------------------------------
def test_no_invented_evidence(client, auth_header):
    """
    Evidence items must reference only stored records.
    raw_text in evidence items must not be empty when discrepancy_details exist.
    """
    case_id = _create_full_case(
        client, auth_header,
        description=(
            "GreenLeaf Detox Tea. Sugar Free. No added preservatives.\n"
            "Ingredients: Senna Leaves (7g), Green Tea, Tulsi.\n"
            "Manufactured by: GreenLeaf Wellness, Pune.\n"
            "FSSAI Lic. No: 10018022007890."
        )
    )
    # Run consistency check to add discrepancy findings
    client.post(f"/api/v1/cases/{case_id}/consistency-check", headers=auth_header)

    res = client.get(f"/api/v1/cases/{case_id}/explanation", headers=auth_header)
    assert res.status_code == 200
    report = res.json()

    # Check that evidence items have non-empty source references
    for finding in report["findings"]:
        if finding["discrepancy_details"]:
            # Discrepancy findings should surface verbatim values as evidence
            disc = finding["discrepancy_details"]
            # If source_a_value exists in details, it should appear somewhere in evidence
            src_a = disc.get("source_a_value", "")
            src_b = disc.get("source_b_value", "")
            evidence_texts = [e["raw_text"] for e in finding["evidence"]]
            if src_a:
                assert any(src_a[:30] in et for et in evidence_texts), \
                    "Source A verbatim text not surfaced in evidence"


# ---------------------------------------------------------------------------
# 4. Findings Sorted by Severity (CRITICAL first)
# ---------------------------------------------------------------------------
def test_findings_sorted_by_severity(client, auth_header):
    """Findings should be ordered CRITICAL → HIGH → MEDIUM → LOW → INFO."""
    case_id = _create_full_case(
        client, auth_header,
        description=(
            "MaxPower Energy Drink. Doctor recommended. Cures fatigue permanently.\n"
            "Ingredients: Sugar (40g), Caffeine (200mg), Rhodamine B Dye, Taurine.\n"
            "Manufactured by: MaxPower Beverages Ltd., Delhi.\n"
            "FSSAI Lic. No: 10018022007890."
        )
    )
    res = client.get(f"/api/v1/cases/{case_id}/explanation", headers=auth_header)
    assert res.status_code == 200
    findings = res.json()["findings"]

    severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    seen_order = [severity_order.index(f["severity"]) for f in findings if f["severity"] in severity_order]
    # Verify non-decreasing order (each item >= previous)
    for i in range(1, len(seen_order)):
        assert seen_order[i] >= seen_order[i - 1], \
            f"Findings not sorted: {findings[i - 1]['severity']} before {findings[i]['severity']}"


# ---------------------------------------------------------------------------
# 5. Risk Assessment Embedded When Available
# ---------------------------------------------------------------------------
def test_risk_assessment_embedded(client, auth_header):
    """When risk assessment exists, it's embedded in the report with disclaimer."""
    case_id = _create_full_case(
        client, auth_header,
        description=(
            "VitaKids Multi-Vitamin Syrup. Clinically proven for child growth.\n"
            "Ingredients: Vitamin A, Vitamin D, Iron, Zinc.\n"
            "Manufactured by: PharmaKids India, Mumbai.\n"
            "FSSAI Lic. No: 10018022007890."
        )
    )
    res = client.get(f"/api/v1/cases/{case_id}/explanation", headers=auth_header)
    assert res.status_code == 200
    report = res.json()

    assert "risk_assessment" in report
    risk = report["risk_assessment"]
    assert risk is not None
    assert 0.0 <= risk["risk_score"] <= 1.0
    assert risk["risk_level"] in ("LOW", "MEDIUM", "HIGH")
    assert 0.0 <= risk["confidence_score"] <= 1.0
    assert len(risk["disclaimer"]) > 50
    assert isinstance(risk["contributing_factors"], list)


# ---------------------------------------------------------------------------
# 6. Why-Flagged Summary Is Actionable
# ---------------------------------------------------------------------------
def test_why_flagged_summary(client, auth_header):
    """why_flagged_summary should list human-readable reasons for flagging."""
    case_id = _create_full_case(
        client, auth_header,
        description=(
            "NatureCure Herbal Immunity Booster. Proven to cure viral infections.\n"
            "Ingredients: Ashwagandha, Tulsi, Giloy, Artificial Color (Rhodamine B).\n"
            "FSSAI Lic. No: 10018022007890."
        )
    )
    res = client.get(f"/api/v1/cases/{case_id}/explanation", headers=auth_header)
    assert res.status_code == 200
    report = res.json()

    why = report["why_flagged_summary"]
    assert isinstance(why, list)
    # If there are HIGH/MEDIUM findings, why_flagged should not be empty
    has_significant = any(
        f["severity"] in ("CRITICAL", "HIGH", "MEDIUM")
        for f in report["findings"]
    )
    if has_significant:
        assert len(why) > 0
        for reason in why:
            assert isinstance(reason, str) and len(reason) > 5
