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
    # assert "<h1>Welcome to the Journaled API</h1>" in response.text

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
        "is_active": True,
        "parent_id": None
    }
    # Create account
    response = client.post("/accounts/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["type"] == payload["type"]
    assert data["currency"] == payload["currency"]
    assert data["is_active"] == payload["is_active"]

    # Delete the created account
    account_id = data["id"]
    del_response = client.delete(f"/accounts/{account_id}")
    assert del_response.status_code == 204

def test_delete_account_with_attached_splits():
    client = TestClient(app)
    # Create two accounts
    payload1 = {
        "name": "Split Account 1",
        "code": "SPLT1",
        "type": "ASSET",
        "currency": "USD",
        "is_active": True,
        "parent_id": None
    }
    payload2 = {
        "name": "Split Account 2",
        "code": "SPLT2",
        "type": "ASSET",
        "currency": "USD",
        "is_active": True,
        "parent_id": None
    }
    response1 = client.post("/accounts/", json=payload1)
    response2 = client.post("/accounts/", json=payload2)
    assert response1.status_code == 201
    assert response2.status_code == 201
    account_id1 = response1.json()["id"]
    account_id2 = response2.json()["id"]
    # Create a transaction with splits for both accounts
    txn_payload = {
        "date": "2025-09-15",
        "description": "Test txn",
        "splits": [
            {"account_id": account_id1, "amount": "100.00"},
            {"account_id": account_id2, "amount": "-100.00"}
        ]
    }
    txn_response = client.post("/transactions/", json=txn_payload)
    assert txn_response.status_code == 201
    # Try to delete account 1 (should fail)
    del_response = client.delete(f"/accounts/{account_id1}")
    assert del_response.status_code == 409
    assert del_response.json()["detail"] == "Account has attached transactions and cannot be deleted"


def test_delete_account_with_nonzero_balance():
    client = TestClient(app)
    # Create two accounts
    payload1 = {
        "name": "Balance Account",
        "code": "BAL1",
        "type": "ASSET",
        "currency": "USD",
        "is_active": True,
        "parent_id": None
    }
    payload2 = {
        "name": "Other Account",
        "code": "BAL2",
        "type": "ASSET",
        "currency": "USD",
        "is_active": True,
        "parent_id": None
    }
    response1 = client.post("/accounts/", json=payload1)
    response2 = client.post("/accounts/", json=payload2)
    assert response1.status_code == 201
    assert response2.status_code == 201
    account_id1 = response1.json()["id"]
    account_id2 = response2.json()["id"]
    # Create a balanced transaction
    txn_payload = {
        "date": "2025-09-15",
        "description": "Balanced txn",
        "splits": [
            {"account_id": account_id1, "amount": "100.00"},
            {"account_id": account_id2, "amount": "-100.00"}
        ]
    }
    txn_response = client.post("/transactions/", json=txn_payload)
    assert txn_response.status_code == 201
    # Try to delete account 1 (should fail)
    del_response = client.delete(f"/accounts/{account_id1}")
    assert del_response.status_code == 409
    assert del_response.json()["detail"] == "Account has attached transactions and cannot be deleted"


def test_delete_nonexistent_account():
    client = TestClient(app)
    # Try to delete an account that does not exist
    del_response = client.delete("/accounts/999999")
    assert del_response.status_code == 404
    assert del_response.json()["detail"] == "Account not found"


def test_delete_account_with_no_splits_and_zero_balance():
    client = TestClient(app)
    # Create account
    payload = {
        "name": "Empty Account",
        "code": "EMPTY",
        "type": "ASSET",
        "currency": "USD",
        "is_active": True,
        "parent_id": None
    }
    response = client.post("/accounts/", json=payload)
    assert response.status_code == 201
    account_id = response.json()["id"]
    # Try to delete account (should succeed)
    del_response = client.delete(f"/accounts/{account_id}")
    assert del_response.status_code == 204
