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
