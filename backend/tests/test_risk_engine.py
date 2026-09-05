import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.database.session import get_db
from app.main import app
from app.models.base import Base
from app.models.user import User
from app.services.risk_engine.config import RiskEngineConfig, LEGAL_DISCLAIMER
from app.services.risk_engine.aggregator import DimensionFindingGroup
from app.services.risk_engine.scorer import RiskScorer

TEST_DB_FILE = "test_risk.db"
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
                email="officer.risk@drishti.gov.in",
                full_name="Rajesh Pillai",
                badge_id="FSO-KL-TVM-009",
                role="AUTHORITY_OFFICER",
                jurisdiction_state="KL",
                jurisdiction_district="KL-TVM",
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
        claims={"role": "AUTHORITY_OFFICER", "badge_id": "FSO-KL-TVM-009"},
    )
    return {"Authorization": f"Bearer {token}"}


def _make_groups(*specs) -> dict:
    """
    Helper: build a groups dict for RiskScorer.compute().
    specs = list of (dimension, findings_list)
    findings_list = list of (severity, confidence)
    """
    from app.services.risk_engine.aggregator import DimensionFindingGroup, DIMENSION_ANALYSIS_TYPES
    groups = {
        dim: DimensionFindingGroup(dim)
        for dim in DIMENSION_ANALYSIS_TYPES
        if dim != "DEEP_PRODUCT_ANALYSIS"
    }
    for dimension, findings in specs:
        for severity, confidence in findings:
            groups[dimension].add(severity, confidence, f"Test finding: {severity}")
    return groups


# ---------------------------------------------------------------------------
# 1. Config Validation
# ---------------------------------------------------------------------------
def test_config_weight_validation():
    """Weights not summing to 1.0 raise ValueError."""
    with pytest.raises(ValueError, match="sum to 1.0"):
        RiskEngineConfig(dimension_weights={
            "LICENSE_ANALYSIS": 0.50,
            "INGREDIENT_ANALYSIS": 0.50,
            "CLAIM_ANALYSIS": 0.50,  # Over 1.0
            "PACKAGING_ANALYSIS": 0.10,
            "MANUFACTURER_ANALYSIS": 0.10,
            "CROSS_SOURCE_CONSISTENCY": 0.10,
            "DATA_COMPLETENESS": 0.05,
        })


def test_config_default_weights_valid():
    """Default config is self-consistent (weights sum to 1.0)."""
    cfg = RiskEngineConfig.default()
    total = sum(cfg.dimension_weights.values())
    assert abs(total - 1.0) < 0.01


# ---------------------------------------------------------------------------
# 2. Low-Risk Sample
# ---------------------------------------------------------------------------
def test_low_risk_sample():
    """Only INFO/LOW severity findings → LOW risk level."""
    cfg = RiskEngineConfig.default()
    scorer = RiskScorer(cfg)

    groups = _make_groups(
        ("LICENSE_ANALYSIS",        [("INFO", 0.80), ("LOW", 0.75)]),
        ("INGREDIENT_ANALYSIS",     [("LOW", 0.70)]),
    )
    result = scorer.compute(groups, data_completeness=0.80)

    assert result.risk_level == "LOW"
    assert result.risk_score < cfg.medium_threshold
    assert result.confidence_score > 0.0
    assert result.total_findings_analyzed == 3
    assert "LOW" in result.score_explanation or "0." in result.score_explanation


# ---------------------------------------------------------------------------
# 3. Medium-Risk Sample
# ---------------------------------------------------------------------------
def test_medium_risk_sample():
    """Mix of MEDIUM findings across dimensions → MEDIUM risk level."""
    cfg = RiskEngineConfig.default()
    scorer = RiskScorer(cfg)

    groups = _make_groups(
        ("LICENSE_ANALYSIS",        [("MEDIUM", 0.75), ("MEDIUM", 0.80)]),
        ("INGREDIENT_ANALYSIS",     [("MEDIUM", 0.70)]),
        ("CLAIM_ANALYSIS",          [("MEDIUM", 0.65), ("LOW", 0.60)]),
        ("PACKAGING_ANALYSIS",      [("MEDIUM", 0.70)]),
        ("CROSS_SOURCE_CONSISTENCY",[("LOW", 0.55)]),
    )
    result = scorer.compute(groups, data_completeness=0.85)

    assert result.risk_level == "MEDIUM"
    assert cfg.medium_threshold <= result.risk_score < cfg.high_threshold


# ---------------------------------------------------------------------------
# 4. High-Risk Sample
# ---------------------------------------------------------------------------
def test_high_risk_sample():
    """CRITICAL/HIGH findings (banned ingredient + no license) → HIGH risk level."""
    cfg = RiskEngineConfig.default()
    scorer = RiskScorer(cfg)

    groups = _make_groups(
        ("LICENSE_ANALYSIS",        [("CRITICAL", 0.95)]),   # No valid license
        ("INGREDIENT_ANALYSIS",     [("CRITICAL", 0.90), ("HIGH", 0.85)]),  # Banned substance
        ("CLAIM_ANALYSIS",          [("HIGH", 0.80), ("MEDIUM", 0.75)]),
        ("PACKAGING_ANALYSIS",      [("HIGH", 0.80)]),
        ("MANUFACTURER_ANALYSIS",   [("MEDIUM", 0.70)]),
        ("CROSS_SOURCE_CONSISTENCY",[("HIGH", 0.85)]),
    )
    result = scorer.compute(groups, data_completeness=1.0)

    assert result.risk_level == "HIGH"
    assert result.risk_score >= cfg.high_threshold
    assert result.confidence_score >= 0.60


# ---------------------------------------------------------------------------
# 5. Missing Data Penalty
# ---------------------------------------------------------------------------
def test_missing_data_penalty():
    """No findings at all → low confidence, data completeness near 0."""
    cfg = RiskEngineConfig.default()
    scorer = RiskScorer(cfg)

    groups = _make_groups()  # All empty
    result = scorer.compute(groups, data_completeness=0.0)

    assert result.risk_level == "LOW"
    assert result.risk_score < cfg.medium_threshold
    assert result.confidence_score < 0.40
    assert result.total_findings_analyzed == 0
    assert "completeness" in result.score_explanation.lower() or "0%" in result.score_explanation


# ---------------------------------------------------------------------------
# 6. Conflicting Findings
# ---------------------------------------------------------------------------
def test_conflicting_findings():
    """Consistency INCONSISTENT + claim conflicts → elevated risk vs baseline."""
    cfg = RiskEngineConfig.default()
    scorer = RiskScorer(cfg)

    # Baseline: clean case
    baseline_groups = _make_groups(
        ("LICENSE_ANALYSIS", [("INFO", 0.90)]),
    )
    baseline = scorer.compute(baseline_groups, data_completeness=0.50)

    # Conflicting: add HIGH consistency and claim findings
    conflict_groups = _make_groups(
        ("LICENSE_ANALYSIS",        [("INFO", 0.90)]),
        ("CLAIM_ANALYSIS",          [("HIGH", 0.85), ("MEDIUM", 0.80)]),
        ("CROSS_SOURCE_CONSISTENCY",[("HIGH", 0.90), ("HIGH", 0.85)]),
    )
    conflict = scorer.compute(conflict_groups, data_completeness=0.70)

    assert conflict.risk_score > baseline.risk_score
    assert conflict.total_findings_analyzed > baseline.total_findings_analyzed


# ---------------------------------------------------------------------------
# 7. Score Is Explainable (Factor Sum Traces to Final Score)
# ---------------------------------------------------------------------------
def test_score_is_explainable():
    """Every contributing_factor.weighted_contribution is traceable and > 0 for non-empty dims."""
    cfg = RiskEngineConfig.default()
    scorer = RiskScorer(cfg)

    groups = _make_groups(
        ("LICENSE_ANALYSIS",    [("HIGH", 0.85)]),
        ("INGREDIENT_ANALYSIS", [("CRITICAL", 0.90)]),
    )
    result = scorer.compute(groups, data_completeness=0.80)

    active_factors = [f for f in result.contributing_factors if f.finding_count > 0]
    assert len(active_factors) >= 2

    for f in active_factors:
        assert f.weighted_contribution > 0.0
        assert 0.0 <= f.weighted_contribution <= 1.0
        assert f.confidence > 0.0
        assert f.max_severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")

    # Approx sum of contributions should be close to (but not necessarily equal to)
    # the risk_score (data completeness penalty is separate)
    factor_sum = sum(f.weighted_contribution for f in result.contributing_factors)
    assert abs(factor_sum - result.risk_score) < 0.10  # within 10% of final score


# ---------------------------------------------------------------------------
# 8. End-to-End API Integration Test
# ---------------------------------------------------------------------------
def test_api_risk_workflow(client, auth_header):
    """
    Full risk workflow:
    1. Submit case.
    2. Run deep analysis to generate findings.
    3. POST /risk-assessment → verify report structure.
    4. GET /risk-assessment → report returned.
    5. Disclaimer is present and non-empty.
    """
    # Step 1: Submit a case with rich data
    payload = {
        "product_name": "PowerMax Energy Drink 330ml",
        "brand": "PowerMax Beverages",
        "category": "BEVERAGES_TEA_AND_COFFEE",
        "product_description": (
            "PowerMax Energy Drink. Clinically proven to boost energy.\n"
            "Ingredients: Water, Sugar (38g), Caffeine (150mg), Taurine, Ginseng.\n"
            "Guaranteed to enhance performance in 30 minutes.\n"
            "Manufactured by: PowerMax Beverages Pvt. Ltd., Pune.\n"
            "FSSAI Lic. No: 10018022007890."
        ),
        "notes": "High sugar + aggressive health claims. No ingredients on label front.",
    }
    submit_res = client.post("/api/v1/cases", data=payload, headers=auth_header)
    assert submit_res.status_code == 201
    case_id = submit_res.json()["case_id"]

    # Step 2: Run deep analysis to create findings
    deep_res = client.post(f"/api/v1/cases/{case_id}/deep-analysis", headers=auth_header)
    assert deep_res.status_code == 200

    # Step 3: Run risk assessment
    risk_res = client.post(f"/api/v1/cases/{case_id}/risk-assessment", headers=auth_header)
    assert risk_res.status_code == 200
    report = risk_res.json()

    # Structural validation
    assert report["case_id"] == case_id
    assert "risk_score" in report
    assert "risk_level" in report
    assert "confidence_score" in report
    assert "contributing_factors" in report
    assert "score_explanation" in report
    assert "data_completeness_ratio" in report
    assert "total_findings_analyzed" in report
    assert "disclaimer" in report
    assert "engine_version" in report
    assert "execution_timestamp" in report

    # Type and range validation
    assert 0.0 <= report["risk_score"] <= 1.0
    assert report["risk_level"] in ("LOW", "MEDIUM", "HIGH")
    assert 0.0 <= report["confidence_score"] <= 1.0

    # Disclaimer is mandatory and non-empty
    assert len(report["disclaimer"]) > 50
    assert "NOT" in report["disclaimer"] or "internal" in report["disclaimer"].lower()

    # Contributing factors structure
    factors = report["contributing_factors"]
    assert isinstance(factors, list)
    for f in factors:
        assert "dimension" in f
        assert "finding_count" in f
        assert "max_severity" in f
        assert "weighted_contribution" in f
        assert 0.0 <= f["weighted_contribution"] <= 1.0

    # Step 4: GET endpoint returns valid report
    get_res = client.get(f"/api/v1/cases/{case_id}/risk-assessment", headers=auth_header)
    assert get_res.status_code == 200
    assert get_res.json()["case_id"] == case_id

    # Step 5: Disclaimer check
    assert get_res.json()["disclaimer"] == report["disclaimer"]


# ---------------------------------------------------------------------------
# 9. Phase B1: FindingAggregator Regulatory Dimension Resolution Tests
# ---------------------------------------------------------------------------
def test_dimension_resolution_all_canonical_dimensions():
    """
    Validates that each statutory finding is accurately resolved to its canonical
    regulatory dimension regardless of its evidence source provenance.
    """
    from app.models.analysis import Finding
    from app.services.risk_engine.aggregator import FindingAggregator

    test_cases = [
        # 1. License findings (LIC, LICENSE, FOSCOS, SEC-31) with varied evidence sources
        (Finding(finding_title="License missing", rule_code="FSSAI-SEC-31-LIC-MISSING", source="MANUAL_INPUT", severity="CRITICAL", confidence=0.95, description="d"), "LICENSE_ANALYSIS"),
        (Finding(finding_title="FOSCOS status", rule_code="FSSAI-FOSCOS-DETECTED", source="FOSCOS_REGISTRY_PENDING", severity="INFO", confidence=0.90, description="d"), "LICENSE_ANALYSIS"),
        (Finding(finding_title="License mismatch", rule_code="FSSAI-LIC-SOURCE-MISMATCH", source="PRODUCT_URL", severity="HIGH", confidence=0.90, description="d"), "LICENSE_ANALYSIS"),
        (Finding(finding_title="Direct license rule", rule_code="LIC-INVALID-FORMAT", source="OFFICER_DESCRIPTION", severity="MEDIUM", confidence=0.85, description="d"), "LICENSE_ANALYSIS"),

        # 2. Ingredient findings (ING, INGREDIENT, BAN-, SWEETENER) with varied sources
        (Finding(finding_title="Ingredient available", rule_code="FSSAI-ING-AVAILABLE", source="STRUCTURED_INTELLIGENCE", severity="INFO", confidence=0.90, description="d"), "INGREDIENT_ANALYSIS"),
        (Finding(finding_title="Banned dye Rhodamine B", rule_code="FSSAI-BAN-RHODAMINE-B", source="OFFICER_DESCRIPTION", severity="CRITICAL", confidence=0.98, description="d"), "INGREDIENT_ANALYSIS"),
        (Finding(finding_title="Sweetener advisory", rule_code="FSSAI-ADV-SWEETENER-ASPARTAME", source="PRODUCT_URL", severity="MEDIUM", confidence=0.92, description="d"), "INGREDIENT_ANALYSIS"),
        (Finding(finding_title="Composite ingredient", rule_code="FSSAI-LABEL-2020-COMPOSITE-ING", source="PACKAGING_LABEL", severity="LOW", confidence=0.85, description="d"), "INGREDIENT_ANALYSIS"),

        # 3. Claim findings (CLM, CLAIM, ADV-2018) with varied sources
        (Finding(finding_title="Disease cure claim", rule_code="FSSAI-CLAIM-DISEASE-CURE-FLAG", source="STRUCTURED_INTELLIGENCE", severity="HIGH", confidence=0.94, description="d"), "CLAIM_ANALYSIS"),
        (Finding(finding_title="Guarantee claim", rule_code="FSSAI-CLAIM-GUARANTEE-FLAG", source="OFFICER_DESCRIPTION", severity="MEDIUM", confidence=0.90, description="d"), "CLAIM_ANALYSIS"),
        (Finding(finding_title="Advertising Regs 2018", rule_code="FSSAI-ADV-2018-R4-DIABETES", source="PRODUCT_URL", severity="CRITICAL", confidence=0.98, description="d"), "CLAIM_ANALYSIS"),
        (Finding(finding_title="Direct claim rule", rule_code="CLM-PROHIBITED-THERAPEUTIC", source="MANUAL_INPUT", severity="HIGH", confidence=0.90, description="d"), "CLAIM_ANALYSIS"),

        # 4. Packaging findings (PKG, PACKAGING, LABEL-2020, LABEL-EVAL) with varied sources
        (Finding(finding_title="Mandatory packaging element missing", rule_code="FSSAI-LABEL-2020-PRODUCT_NAME-MISSING", source="PACKAGING_LABEL", severity="MEDIUM", confidence=0.88, description="d"), "PACKAGING_ANALYSIS"),
        (Finding(finding_title="Dates unclear", rule_code="FSSAI-LABEL-2020-DATES-UNCLEAR", source="PACKAGING_LABEL", severity="LOW", confidence=0.82, description="d"), "PACKAGING_ANALYSIS"),
        (Finding(finding_title="Packaging eval summary", rule_code="FSSAI-LABEL-EVAL-SUMMARY", source="PACKAGING_LABEL", severity="INFO", confidence=0.92, description="d"), "PACKAGING_ANALYSIS"),
        (Finding(finding_title="Direct packaging rule", rule_code="PKG-NET-QUANTITY-DEFECT", source="MANUAL_INPUT", severity="LOW", confidence=0.80, description="d"), "PACKAGING_ANALYSIS"),

        # 5. Manufacturer findings (MFG, MFR, MANUFACTURER) with varied sources
        (Finding(finding_title="Manufacturer info missing", rule_code="FSSAI-MFR-INFO-MISSING", source="CROSS_SOURCE_COMPARISON", severity="HIGH", confidence=0.90, description="d"), "MANUFACTURER_ANALYSIS"),
        (Finding(finding_title="Manufacturer mismatch", rule_code="FSSAI-MFR-DISCREPANCY-MISMATCH", source="CROSS_SOURCE_COMPARISON", severity="MEDIUM", confidence=0.88, description="d"), "MANUFACTURER_ANALYSIS"),
        (Finding(finding_title="Direct manufacturer rule", rule_code="MFG-PREMISE-UNREGISTERED", source="OFFICER_DESCRIPTION", severity="HIGH", confidence=0.92, description="d"), "MANUFACTURER_ANALYSIS"),

        # 6. Consistency findings (CON, CONSISTENCY, CROSS) with varied sources
        (Finding(finding_title="Cross-source name diff", rule_code="CONSISTENCY-PRODUCT_NAME-INCONSISTENT", source="CROSS_SOURCE_COMPARISON", severity="HIGH", confidence=0.89, description="d"), "CROSS_SOURCE_CONSISTENCY"),
        (Finding(finding_title="Direct consistency rule", rule_code="CON-CLAIMS-DISCREPANCY", source="CROSS_SOURCE_COMPARISON", severity="MEDIUM", confidence=0.85, description="d"), "CROSS_SOURCE_CONSISTENCY"),
    ]

    for finding, expected_dim in test_cases:
        resolved = FindingAggregator.resolve_dimension(finding, analysis_type="DEEP_PRODUCT_ANALYSIS")
        assert resolved == expected_dim, (
            f"Failed for rule_code '{finding.rule_code}': expected '{expected_dim}', got '{resolved}'"
        )


def test_findings_not_discarded_due_to_provenance_source():
    """
    Verifies that findings are NOT discarded simply because finding.source is
    an evidence provenance marker (MANUAL_INPUT, OFFICER_DESCRIPTION, STRUCTURED_INTELLIGENCE, etc.).
    """
    from app.models.analysis import Finding
    from app.services.risk_engine.aggregator import DimensionFindingGroup, FindingAggregator

    provenance_sources = [
        "STRUCTURED_INTELLIGENCE",
        "MANUAL_INPUT",
        "OFFICER_DESCRIPTION",
        "FOSCOS_REGISTRY_PENDING",
        "PRODUCT_URL",
        "PACKAGING_IMAGE",
        "OCR_ZONE_PANEL",
    ]

    groups = {
        dim: DimensionFindingGroup(dim)
        for dim in FindingAggregator.EXPECTED_DIMENSIONS
    }

    # Add ingredient findings with each provenance type
    for i, prov in enumerate(provenance_sources):
        f = Finding(
            finding_title=f"Sample finding from {prov}",
            rule_code="ING-UNAPPROVED-ADDITIVE",
            source=prov,
            severity="HIGH",
            confidence=0.90,
            description="Test finding description",
        )
        target_dim = FindingAggregator.resolve_dimension(f, analysis_type="DEEP_PRODUCT_ANALYSIS")
        assert target_dim == "INGREDIENT_ANALYSIS", f"Provenance '{prov}' was incorrectly resolved to '{target_dim}'"
        groups[target_dim].add(f.severity, f.confidence, f.finding_title)

    assert groups["INGREDIENT_ANALYSIS"].count == len(provenance_sources)
    assert groups["INGREDIENT_ANALYSIS"].max_severity == "HIGH"


def test_explicit_metadata_dimension_override():
    """
    Verifies that explicit dimension metadata in discrepancy_details takes precedence.
    """
    from app.models.analysis import Finding
    from app.services.risk_engine.aggregator import FindingAggregator

    f = Finding(
        finding_title="Overridden finding",
        rule_code="GENERIC-RULE-001",
        source="MANUAL_INPUT",
        severity="HIGH",
        confidence=0.88,
        description="Explicit metadata test",
        discrepancy_details={"dimension": "MANUFACTURER_ANALYSIS"},
    )
    dim = FindingAggregator.resolve_dimension(f, analysis_type="DEEP_PRODUCT_ANALYSIS")
    assert dim == "MANUFACTURER_ANALYSIS"


def test_unknown_rule_code_not_silently_misclassified(caplog):
    """
    Verifies that truly unresolvable/unknown rule codes return None and log a warning,
    ensuring they are NOT silently misclassified into an arbitrary dimension.
    """
    import logging
    from app.models.analysis import Finding
    from app.services.risk_engine.aggregator import FindingAggregator

    f = Finding(
        finding_title="Arbitrary Custom Third Party Check",
        rule_code="CUSTOM-THIRD-PARTY-NO-MATCH-999",
        source="EXTERNAL_AUDIT_TOOL",
        severity="LOW",
        confidence=0.50,
        description="Unknown rule code",
    )

    with caplog.at_level(logging.WARNING):
        dim = FindingAggregator.resolve_dimension(f, analysis_type="DEEP_PRODUCT_ANALYSIS")
        assert dim is None, f"Unknown rule code should resolve to None, got '{dim}'"

    # Confirm warning log was emitted
    assert any("could not be resolved" in record.message for record in caplog.records)

