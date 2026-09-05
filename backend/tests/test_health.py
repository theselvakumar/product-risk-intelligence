import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_root_health_endpoint(client):
    response = client.get("/health?check_db=false")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "DRISHTI" in data["project"]
    assert data["version"] == "0.1.0"
    assert "timestamp" in data


def test_api_v1_health_endpoint(client):
    response = client.get("/api/v1/health?check_db=false")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_cors_headers(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_nonexistent_route_rfc7807_error(client):
    response = client.get("/nonexistent-endpoint")
    assert response.status_code == 404
    data = response.json()
    assert data["status"] == 404
    assert data["error_code"] == "HTTP_404"
    assert "path" in data
