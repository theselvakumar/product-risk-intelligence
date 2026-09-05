import io
import os
import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
import jwt
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.security import create_access_token, hash_password
from app.database.session import get_db
from app.main import app
from app.models.base import Base
from app.models.case import AuditLog, Case
from app.models.product import Product
from app.models.user import User

TEST_DB_FILE = "test_security.db"
TEST_ASYNC_URL = f"sqlite+aiosqlite:///./{TEST_DB_FILE}"

async_test_engine = create_async_engine(TEST_ASYNC_URL, echo=False)
AsyncTestingSessionLocal = async_sessionmaker(
    bind=async_test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

OFFICER_ID = uuid.uuid4()
OFFICER_EMAIL = "security.officer@drishti.gov.in"
OFFICER_PASSWORD = "ValidGovOfficerPass2026!"

DEACTIVATED_ID = uuid.uuid4()
DEACTIVATED_EMAIL = "deactivated.officer@drishti.gov.in"

REVIEWER_ID = uuid.uuid4()
REVIEWER_EMAIL = "analyst.reviewer@drishti.gov.in"

CASE_ID = uuid.uuid4()
PRODUCT_ID = uuid.uuid4()


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
            # 1. Active Authority Officer
            officer = User(
                id=OFFICER_ID,
                email=OFFICER_EMAIL,
                full_name="Officer Vikram Singh",
                badge_id="FSO-DL-SEC-001",
                role="AUTHORITY_OFFICER",
                jurisdiction_state="DL",
                jurisdiction_district="DL-NEWDELHI",
                is_active=True,
                hashed_password=hash_password(OFFICER_PASSWORD),
            )
            session.add(officer)

            # 2. Deactivated Officer
            deactivated = User(
                id=DEACTIVATED_ID,
                email=DEACTIVATED_EMAIL,
                full_name="Former Officer Anil",
                badge_id="FSO-DL-REVOKED-99",
                role="AUTHORITY_OFFICER",
                jurisdiction_state="DL",
                is_active=False,
                hashed_password=hash_password("OldPassword123!"),
            )
            session.add(deactivated)

            # 3. Restricted Reviewer (Insufficient Role for statutory enforcement)
            reviewer = User(
                id=REVIEWER_ID,
                email=REVIEWER_EMAIL,
                full_name="Analyst Meera",
                badge_id="ANALYST-007",
                role="REVIEWER",
                jurisdiction_state="DL",
                is_active=True,
                hashed_password=hash_password("ReviewerPass2026!"),
            )
            session.add(reviewer)

            # 4. Product & Case for audit trail testing
            product = Product(
                id=PRODUCT_ID,
                product_name="Security Test Herbal Drink",
                brand="TestHerbs",
                category="Beverages",
            )
            session.add(product)

            case = Case(
                id=CASE_ID,
                case_number="CAS-SEC-2026-0001",
                product_id=PRODUCT_ID,
                status="PRIORITY_REVIEW",
                priority="URGENT_P1",
                title="Investigation: Misleading Immunity Claim",
                description="Regulatory audit verification case",
                assigned_user_id=OFFICER_ID,
            )
            session.add(case)

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
def valid_officer_token():
    claims = {
        "email": OFFICER_EMAIL,
        "role": "AUTHORITY_OFFICER",
        "badge_id": "FSO-DL-SEC-001",
        "state": "DL",
        "district": "DL-NEWDELHI",
    }
    return create_access_token(subject=OFFICER_ID, claims=claims)


@pytest.fixture
def reviewer_token():
    claims = {
        "email": REVIEWER_EMAIL,
        "role": "REVIEWER",
        "badge_id": "ANALYST-007",
        "state": "DL",
        "district": "DL-NEWDELHI",
    }
    return create_access_token(subject=REVIEWER_ID, claims=claims)


# ---------------------------------------------------------------------------
# Test 1: Missing Authentication Header Rejection (401)
# ---------------------------------------------------------------------------
def test_missing_auth_header_rejected(client):
    """Protected endpoints must reject requests with missing Authorization header."""
    response = client.get(f"{settings.API_V1_STR}/cases/priority-queue")
    assert response.status_code == 401
    assert "Not authenticated" in response.text or "error_code" in response.json()


# ---------------------------------------------------------------------------
# Test 2: Invalid & Expired Token Rejection (401)
# ---------------------------------------------------------------------------
def test_malformed_token_rejected(client):
    """Malformed bearer tokens must be rejected with 401."""
    headers = {"Authorization": "Bearer not-a-valid-jwt-token-string"}
    response = client.get(f"{settings.API_V1_STR}/cases/priority-queue", headers=headers)
    assert response.status_code == 401


def test_expired_token_rejected(client):
    """Expired JWT tokens must be rejected with 401."""
    expired_payload = {
        "sub": str(OFFICER_ID),
        "iss": "drishti.gov.in",
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "email": OFFICER_EMAIL,
        "role": "AUTHORITY_OFFICER",
    }
    expired_token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get(f"{settings.API_V1_STR}/cases/priority-queue", headers=headers)
    assert response.status_code == 401


def test_invalid_issuer_rejected(client):
    """Tokens with an unauthorized issuer must be rejected."""
    bad_iss_payload = {
        "sub": str(OFFICER_ID),
        "iss": "unauthorized-foreign-entity.org",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "email": OFFICER_EMAIL,
        "role": "AUTHORITY_OFFICER",
    }
    bad_token = jwt.encode(bad_iss_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {"Authorization": f"Bearer {bad_token}"}
    response = client.get(f"{settings.API_V1_STR}/cases/priority-queue", headers=headers)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Test 3: Deactivated Officer Rejection (403)
# ---------------------------------------------------------------------------
def test_deactivated_user_forbidden(client):
    """Tokens belonging to deactivated officers must return 403 Forbidden."""
    deactivated_token = create_access_token(
        subject=DEACTIVATED_ID,
        claims={"email": DEACTIVATED_EMAIL, "role": "AUTHORITY_OFFICER"},
    )
    headers = {"Authorization": f"Bearer {deactivated_token}"}
    response = client.get(f"{settings.API_V1_STR}/cases/priority-queue", headers=headers)
    assert response.status_code == 403
    data = response.json()
    assert "deactivated" in data.get("message", "").lower() or "inactive" in data.get("message", "").lower() or "revoked" in data.get("message", "").lower()


# ---------------------------------------------------------------------------
# Test 4: Role-Based Access Control Rejection (403)
# ---------------------------------------------------------------------------
def test_role_based_access_control_rejection(client, reviewer_token):
    """REVIEWER role cannot execute statutory officer enforcement actions (403)."""
    headers = {"Authorization": f"Bearer {reviewer_token}"}
    review_payload = {
        "review_action": "APPROVE_INSPECTION",
        "remarks": "Reviewer attempting unauthorized statutory action",
    }
    response = client.post(
        f"{settings.API_V1_STR}/cases/{CASE_ID}/reviews",
        json=review_payload,
        headers=headers,
    )
    assert response.status_code == 403
    data = response.json()
    assert "requires one of roles" in data.get("message", "").lower() or "forbidden" in data.get("message", "").lower()


# ---------------------------------------------------------------------------
# Test 5: File Validation - Disallowed MIME Types (400)
# ---------------------------------------------------------------------------
def test_file_disallowed_mime_type(client, valid_officer_token):
    """Non-image / executable uploads must be rejected with 400 Bad Request."""
    headers = {"Authorization": f"Bearer {valid_officer_token}"}
    files = [
        ("product_images", ("exploit.exe", io.BytesIO(b"MZ executable binary data"), "application/x-msdownload")),
    ]
    response = client.post(
        f"{settings.API_V1_STR}/cases",
        data={"product_name": "Test Ingestion", "notes": "MIME test"},
        files=files,
        headers=headers,
    )
    assert response.status_code == 400
    data = response.json()
    assert "allowed image formats" in data.get("message", "").lower() or "invalid file type" in data.get("message", "").lower()


# ---------------------------------------------------------------------------
# Test 6: File Validation - Size Restriction (400)
# ---------------------------------------------------------------------------
def test_file_size_limit_exceeded(client, valid_officer_token):
    """Files exceeding the 15 MB statutory limit must be rejected with 400 Bad Request."""
    headers = {"Authorization": f"Bearer {valid_officer_token}"}
    # 16 MB dummy byte payload
    oversized_bytes = b"0" * (16 * 1024 * 1024)
    files = [
        ("product_images", ("massive_packaging.png", io.BytesIO(oversized_bytes), "image/png")),
    ]
    response = client.post(
        f"{settings.API_V1_STR}/cases",
        data={"product_name": "Test Oversized Ingestion", "notes": "Size test"},
        files=files,
        headers=headers,
    )
    assert response.status_code == 400
    data = response.json()
    assert "maximum permissible size" in data.get("message", "").lower() or "15mb" in data.get("message", "").lower()


# ---------------------------------------------------------------------------
# Test 7: File Validation - Empty File Rejection (400)
# ---------------------------------------------------------------------------
def test_empty_file_rejected(client, valid_officer_token):
    """Zero-byte files must be rejected with 400 Bad Request."""
    headers = {"Authorization": f"Bearer {valid_officer_token}"}
    files = [
        ("product_images", ("empty.jpg", io.BytesIO(b""), "image/jpeg")),
    ]
    response = client.post(
        f"{settings.API_V1_STR}/cases",
        data={"product_name": "Test Empty Ingestion", "notes": "Empty test"},
        files=files,
        headers=headers,
    )
    assert response.status_code == 400
    data = response.json()
    assert "empty" in data.get("message", "").lower()


# ---------------------------------------------------------------------------
# Test 8: Rate Limiting Enforcement (429)
# ---------------------------------------------------------------------------
def test_rate_limiter_unit_enforcement():
    """Unit test SlidingWindowRateLimiter to verify rapid rate limit exhaustion (429)."""
    import asyncio

    async def run():
        limiter = SlidingWindowRateLimiter()
        client_key = "192.168.1.100:test_path"

        # 2 requests allowed
        limited, _ = await limiter.is_rate_limited(client_key, max_requests=2, window_seconds=60)
        assert not limited

        limited, _ = await limiter.is_rate_limited(client_key, max_requests=2, window_seconds=60)
        assert not limited

        # 3rd request in same window must trigger limit
        limited, retry_after = await limiter.is_rate_limited(client_key, max_requests=2, window_seconds=60)
        assert limited
        assert retry_after > 0

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Test 9: Zero Exposure of Secrets & Passwords in Audit Logs
# ---------------------------------------------------------------------------
def test_audit_logs_zero_secrets_exposure(client):
    """Audit logs must never expose plaintext passwords, password hashes, or bearer tokens."""
    login_payload = {
        "email": OFFICER_EMAIL,
        "password": OFFICER_PASSWORD,
    }
    response = client.post("/auth/login", json=login_payload)
    assert response.status_code == 200

    import asyncio

    async def verify_audit_db():
        async with AsyncTestingSessionLocal() as session:
            stmt = select(AuditLog).where(AuditLog.action == "USER_LOGIN").order_by(AuditLog.created_at.desc())
            result = await session.execute(stmt)
            audit_entry = result.scalars().first()

            assert audit_entry is not None
            details = audit_entry.details_json or {}

            # Strictly ensure sensitive fields are absent
            assert "password" not in details
            assert "hashed_password" not in details
            assert "token" not in details
            assert "access_token" not in details
            assert "secret" not in details

            # Allowed metadata only
            assert details.get("email") == OFFICER_EMAIL
            assert details.get("badge_id") == "FSO-DL-SEC-001"

    asyncio.run(verify_audit_db())


# ---------------------------------------------------------------------------
# Test 10: Complete Case Audit Trail Endpoint
# ---------------------------------------------------------------------------
def test_case_audit_trail_endpoint(client, valid_officer_token):
    """Authorized officers can query the complete chronological audit trail of a case."""
    headers = {"Authorization": f"Bearer {valid_officer_token}"}

    # 1. Update status to generate an audit log entry
    update_payload = {
        "status": "UNDER_REVIEW",
        "reason": "Officer initiating formal evidence verification",
        "notes": "Security testing note",
    }
    up_res = client.patch(
        f"{settings.API_V1_STR}/cases/{CASE_ID}/status",
        json=update_payload,
        headers=headers,
    )
    assert up_res.status_code == 200

    # 2. Query case audit trail
    trail_res = client.get(
        f"{settings.API_V1_STR}/cases/{CASE_ID}/audit-trail",
        headers=headers,
    )
    assert trail_res.status_code == 200
    trail_data = trail_res.json()

    assert trail_data["case_id"] == str(CASE_ID)
    assert trail_data["total_events"] >= 1
    assert len(trail_data["events"]) >= 1

    actions = [e["action"] for e in trail_data["events"]]
    assert "CASE_STATUS_UPDATED" in actions

