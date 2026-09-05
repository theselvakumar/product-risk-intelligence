import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.database.session import get_db
from app.main import app
from app.models.base import Base
from app.models.case import AuditLog
from app.models.user import User

TEST_DB_FILE = "test_auth.db"
TEST_ASYNC_URL = f"sqlite+aiosqlite:///./{TEST_DB_FILE}"

async_test_engine = create_async_engine(TEST_ASYNC_URL, echo=False)
AsyncTestingSessionLocal = async_sessionmaker(
    bind=async_test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    # Remove old test database file if exists
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
            # Seed active test authority officer
            officer = User(
                id=uuid.uuid4(),
                email="officer@drishti.gov.in",
                full_name="Rajesh Sharma",
                badge_id="FSO-DL-CENTRAL-012",
                role="AUTHORITY_OFFICER",
                jurisdiction_state="DL",
                jurisdiction_district="DL-CENTRAL",
                is_active=True,
                hashed_password=hash_password("AuthorityOfficer2026!"),
            )
            session.add(officer)

            # Seed deactivated officer
            deactivated = User(
                id=uuid.uuid4(),
                email="revoked@drishti.gov.in",
                full_name="Revoked Officer",
                badge_id="FSO-REVOKED-999",
                role="AUTHORITY_OFFICER",
                is_active=False,
                hashed_password=hash_password("RevokedPassword123!"),
            )
            session.add(deactivated)
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


def test_login_success(client):
    """Test 1: Authority officer logs in successfully with valid credentials."""
    response = client.post(
        "/auth/login",
        json={"email": "officer@drishti.gov.in", "password": "AuthorityOfficer2026!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert data["user"]["email"] == "officer@drishti.gov.in"
    assert data["user"]["role"] == "AUTHORITY_OFFICER"
    assert data["user"]["badge_id"] == "FSO-DL-CENTRAL-012"


def test_login_invalid_password(client):
    """Test 2: Invalid password returns 401 Unauthorized."""
    response = client.post(
        "/auth/login",
        json={"email": "officer@drishti.gov.in", "password": "WrongPassword123!"},
    )
    assert response.status_code == 401
    assert "Invalid" in response.json()["message"]


def test_login_nonexistent_email(client):
    """Test 3: Non-existent email returns 401 Unauthorized."""
    response = client.post(
        "/auth/login",
        json={"email": "unknown@drishti.gov.in", "password": "Password123!"},
    )
    assert response.status_code == 401


def test_login_deactivated_account(client):
    """Test 4: Revoked authority account returns 403 Forbidden."""
    response = client.post(
        "/auth/login",
        json={"email": "revoked@drishti.gov.in", "password": "RevokedPassword123!"},
    )
    assert response.status_code == 403
    assert "inactive" in response.json()["message"].lower()


def test_unauthorized_access_to_protected_routes(client):
    """Test 5: Requesting protected routes without token returns 401."""
    # /auth/me
    response = client.get("/auth/me")
    assert response.status_code == 401

    # /api/v1/cases/triage
    response = client.get("/api/v1/cases/triage")
    assert response.status_code == 401


def test_authorized_access_to_current_user_and_protected_route(client):
    """Test 6: Valid bearer token grants access to /auth/me and protected business routes."""
    login_resp = client.post(
        "/auth/login",
        json={"email": "officer@drishti.gov.in", "password": "AuthorityOfficer2026!"},
    )
    token = login_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Access current user profile
    me_resp = client.get("/auth/me", headers=auth_headers)
    assert me_resp.status_code == 200
    user_data = me_resp.json()["user"]
    assert user_data["email"] == "officer@drishti.gov.in"
    assert user_data["badge_id"] == "FSO-DL-CENTRAL-012"
    assert user_data["role"] == "AUTHORITY_OFFICER"

    # Access protected business route
    triage_resp = client.get("/api/v1/cases/triage", headers=auth_headers)
    assert triage_resp.status_code == 200
    assert isinstance(triage_resp.json(), list)


def test_logout_and_audit_log(client):
    """Test 7: Logout endpoint logs out officer successfully."""
    login_resp = client.post(
        "/auth/login",
        json={"email": "officer@drishti.gov.in", "password": "AuthorityOfficer2026!"},
    )
    token = login_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    logout_resp = client.post("/auth/logout", headers=auth_headers)
    assert logout_resp.status_code == 200
    assert logout_resp.json()["status"] == "success"
    assert "logged out" in logout_resp.json()["message"]
