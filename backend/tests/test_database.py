import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models import (
    Base,
    User,
    Product,
    ProductSource,
    ProductImage,
    ExtractedInformation,
    AnalysisResult,
    RiskAssessment,
    Finding,
    Evidence,
    Case,
    CaseReview,
    AuditLog,
)
from app.schemas import (
    UserCreate,
    UserRead,
    ProductCreate,
    ProductRead,
    CaseCreate,
    CaseRead,
    RiskAssessmentCreate,
    RiskAssessmentRead,
    FindingCreate,
    FindingRead,
)


@pytest.fixture(scope="module")
def db_session():
    """In-memory SQLite session for testing all 12 core models and relationships."""
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(test_engine)
    TestingSessionLocal = sessionmaker(bind=test_engine)
    session = TestingSessionLocal()
    yield session, test_engine
    session.close()
    test_engine.dispose()


def test_all_twelve_tables_exist(db_session):
    _, engine = db_session
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    expected_tables = {
        "users",
        "cases",
        "products",
        "product_sources",
        "product_images",
        "extracted_information",
        "analysis_results",
        "risk_assessments",
        "findings",
        "evidence",
        "case_reviews",
        "audit_logs",
    }

    missing_tables = expected_tables - set(tables)
    assert not missing_tables, f"Missing tables in database: {missing_tables}"
    assert len(expected_tables.intersection(set(tables))) == 12


def test_create_and_link_all_entities(db_session):
    session, _ = db_session

    # 1. Create User
    officer = User(
        email="fso.verma@fssai.gov.in",
        full_name="Vikram Verma",
        badge_id="FSO-KA-BLR-042",
        role="FOOD_SAFETY_OFFICER",
        jurisdiction_state="KA",
        jurisdiction_district="KA-BLR-URBAN",
    )
    session.add(officer)
    session.flush()
    assert officer.id is not None
    assert officer.badge_id == "FSO-KA-BLR-042"

    # 2. Create Product
    product = Product(
        product_name="AyurVital Diabetic Care Shake",
        brand="AyurVital Health",
        category="HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS",
        manufacturer="AyurVital Labs Pvt Ltd",
        fssai_license_number="11221334000567",
        barcode_or_gtin="8901234567890",
        net_quantity="400 g",
        declared_ingredients="Soy Protein Isolate, Maltodextrin, Sucralose (INS 955)",
    )
    session.add(product)
    session.flush()
    assert product.id is not None

    # 3. Create ProductSource
    source = ProductSource(
        product_id=product.id,
        source_type="ECOMMERCE_URL",
        source_url="https://example-grocery.in/p/ayurvital-shake",
        platform_name="QuickCommerce",
        seller_name="HealthKart Retail",
        raw_payload_json={"price": 899, "in_stock": True},
    )
    session.add(source)
    session.flush()

    # 4. Create ProductImage
    image = ProductImage(
        product_id=product.id,
        image_type="FRONT_OF_PACK",
        storage_uri="s3://drishti-raw/prod_01_fop.jpg",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        file_size_bytes=204800,
        resolution_width=1920,
        resolution_height=1080,
    )
    session.add(image)
    session.flush()

    # 5. Create ExtractedInformation
    extracted = ExtractedInformation(
        product_id=product.id,
        image_id=image.id,
        zone_type="CLAIMS",
        bounding_box={"x_min": 100, "y_min": 200, "x_max": 500, "y_max": 350},
        raw_text="Reverses Type 2 Diabetes within 30 Days! Zero Added Sugar.",
        parsed_data={"claim_type": "THERAPEUTIC", "target_disease": "Diabetes"},
        confidence_score=0.96,
        extractor_version="LayoutLMv3-v1.0",
    )
    session.add(extracted)
    session.flush()

    # 6. Create Case
    case = Case(
        case_number="FSSAI-CASE-2026-0042",
        product_id=product.id,
        assigned_user_id=officer.id,
        status="TRIAGED",
        priority="URGENT_P1",
        jurisdiction_district="KA-BLR-URBAN",
        title="Illegal Curative Diabetes Claim on AyurVital Shake",
        description="FOP declares curative reversal of Type 2 Diabetes violating Section 24 FSS Act 2006.",
    )
    session.add(case)
    session.flush()
    assert case.id is not None
    assert case.case_number == "FSSAI-CASE-2026-0042"

    # 7. Create AnalysisResult
    analysis = AnalysisResult(
        product_id=product.id,
        analysis_type="ADVERTISING_CLAIMS",
        status="COMPLETED",
        total_checks=5,
        violations_found=2,
        summary="Product makes illegal therapeutic curative claims prohibited under Advertising Regulations 2018.",
        execution_metadata={"duration_ms": 320},
    )
    session.add(analysis)
    session.flush()

    # 8. Create RiskAssessment
    risk = RiskAssessment(
        product_id=product.id,
        case_id=case.id,
        risk_score=88.5,
        risk_level="CRITICAL",
        confidence_score=0.94,
        health_hazard_score=75.0,
        deception_score=95.0,
        licensing_score=60.0,
        vulnerability_multiplier=1.1,
        score_breakdown={"weights": {"hazard": 0.4, "deception": 0.35, "licensing": 0.25}},
    )
    session.add(risk)
    session.flush()

    # 9. Create Finding
    finding = Finding(
        analysis_result_id=analysis.id,
        extracted_info_id=extracted.id,
        finding_title="Prohibited Curative Disease Claim: Diabetes",
        description="Regulation 4(7) FSS (Advertising and Claims) 2018 prohibits curative disease claims.",
        severity="CRITICAL",
        confidence=0.98,
        source="PACKAGING_LABEL",
        statutory_reference="Section 24, FSS Act 2006 read with Reg 4(7) Advertising Regs 2018",
        rule_code="FSSAI-ADV-2018-R4-DIABETES",
        discrepancy_details={"claim": "Reverses Type 2 Diabetes", "permitted": False},
    )
    session.add(finding)
    session.flush()

    # 10. Create Evidence
    evidence = Evidence(
        finding_id=finding.id,
        evidence_type="IMAGE_CROP",
        storage_uri="s3://drishti-evidence/crop_diabetes_claim.jpg",
        sha256_hash="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        bounding_box={"x_min": 100, "y_min": 200, "x_max": 500, "y_max": 350},
        caption="High-resolution crop of front-of-pack curative diabetes claim",
    )
    session.add(evidence)
    session.flush()

    # 11. Create CaseReview
    review = CaseReview(
        case_id=case.id,
        reviewer_id=officer.id,
        review_action="ISSUE_SECTION_32_NOTICE",
        remarks="Concur with findings. Issue Section 32 Improvement Notice and order field sample collection.",
        action_metadata={"statutory_section": "Section 32", "notice_window_days": 14},
    )
    session.add(review)
    session.flush()

    # 12. Create AuditLog
    audit = AuditLog(
        case_id=case.id,
        user_id=officer.id,
        action="SECTION_32_NOTICE_ISSUED",
        entity_type="Case",
        entity_id=str(case.id),
        details_json={"previous_status": "TRIAGED", "new_status": "NOTICE_ISSUED_SEC32"},
        ip_address="10.252.117.42",
    )
    session.add(audit)
    session.commit()

    # Verify query and cross-entity relationships
    loaded_case = session.query(Case).filter_by(id=case.id).first()
    assert loaded_case is not None
    assert loaded_case.product.product_name == "AyurVital Diabetic Care Shake"
    assert loaded_case.assigned_user.full_name == "Vikram Verma"
    assert len(loaded_case.reviews) == 1
    assert loaded_case.reviews[0].review_action == "ISSUE_SECTION_32_NOTICE"
    assert len(loaded_case.risk_assessments) == 1
    assert loaded_case.risk_assessments[0].risk_level == "CRITICAL"
    assert len(loaded_case.audit_logs) == 1

    loaded_finding = session.query(Finding).filter_by(id=finding.id).first()
    assert loaded_finding is not None
    assert len(loaded_finding.evidence_items) == 1
    assert loaded_finding.evidence_items[0].evidence_type == "IMAGE_CROP"


def test_pydantic_schema_validation():
    # Test User Schema
    user_payload = {
        "id": uuid.uuid4(),
        "email": "do.sharma@fssai.gov.in",
        "full_name": "Dr. Sunita Sharma",
        "badge_id": "DO-DL-CENTRAL-001",
        "role": "DESIGNATED_OFFICER",
        "jurisdiction_state": "DL",
        "jurisdiction_district": "DL-CENTRAL",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    user_schema = UserRead.model_validate(user_payload)
    assert user_schema.badge_id == "DO-DL-CENTRAL-001"

    # Test Product Schema
    product_payload = {
        "id": uuid.uuid4(),
        "product_name": "Pure Honey 100% Organic",
        "brand": "NatureBest",
        "category": "HONEY_AND_PRESERVES",
        "manufacturer": "NatureBest Agro Products",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "sources": [],
        "images": [],
    }
    product_schema = ProductRead.model_validate(product_payload)
    assert product_schema.brand == "NatureBest"

    # Test RiskAssessment Schema
    risk_payload = {
        "id": uuid.uuid4(),
        "product_id": uuid.uuid4(),
        "risk_score": 92.0,
        "risk_level": "CRITICAL",
        "confidence_score": 0.95,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    risk_schema = RiskAssessmentRead.model_validate(risk_payload)
    assert risk_schema.risk_level == "CRITICAL"
    assert risk_schema.risk_score == 92.0
