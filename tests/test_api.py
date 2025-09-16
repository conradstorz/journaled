import pytest
from starlette.testclient import TestClient
from journaled_app.app import app

def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"

def test_landing_page():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "<h1>Welcome to the Journaled API</h1>" in response.text

def test_docs_page():
    client = TestClient(app)
    response = client.get("/docs")
    assert response.status_code == 200
    assert "Swagger UI" in response.text

def test_openapi_json():
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "paths" in response.json()

def test_health_endpoint_structure():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data

def test_accounts_endpoint():
    client = TestClient(app)
    response = client.get("/accounts")
    assert response.status_code in (200, 404)

def test_create_account():
    client = TestClient(app)
    payload = {
        "name": "Test Account",
        "code": "TST",
        "type": "ASSET",
        "currency": "USD",
        "active": True,
        "parent_id": None
    }
    # Create account
    response = client.post("/accounts/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["type"] == payload["type"]
    assert data["currency"] == payload["currency"]
    assert data["active"] == payload["active"]

    # Try to create duplicate account
    response_dup = client.post("/accounts/", json=payload)
    assert response_dup.status_code == 409
    assert "Account name already exists" in response_dup.text
