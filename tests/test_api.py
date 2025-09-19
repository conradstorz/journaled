import pytestimport pytest

from starlette.testclient import TestClientfrom starlette.testclient import TestClient

from journaled_app.app import appfrom journaled_app.app import app



client = TestClient(app)client = TestClient(app)



def get_auth_token():def get_auth_token():

    """Helper function to register and login a test user, return auth token"""    """Helper function to register and login a test user, return auth token"""

    # Register a test user    # Register a test user

    register_response = client.post("/auth/register", json={    register_response = client.post("/auth/register", json={

        "username": "testuser_api",        "username": "testuser_api",

        "email": "testapi@example.com",        "email": "testapi@example.com",

        "password": "testpass"        "password": "testpass"

    })    })

    # Login to get token    # Login to get token

    login_response = client.post("/auth/login", data={    login_response = client.post("/auth/login", data={

        "username": "testuser_api",        "username": "testuser_api",

        "password": "testpass"        "password": "testpass"

    })    })

    return login_response.json()["access_token"]    return login_response.json()["access_token"]



def get_auth_headers():def get_auth_headers():

    """Helper function to get authorization headers"""    """Helper function to get authorization headers"""

    token = get_auth_token()    token = get_auth_token()

    return {"Authorization": f"Bearer {token}"}    return {"Authorization": f"Bearer {token}"}



def test_health_endpoint():def test_health_endpoint():

    client = TestClient(app)    client = TestClient(app)

    response = client.get("/health")    response = client.get("/health")

    assert response.status_code == 200    assert response.status_code == 200

    data = response.json()    data = response.json()

    assert data["status"] == "ok"    assert data["status"] == "ok"

    assert data["database"] == "ok"    assert data["database"] == "ok"



def test_landing_page():def test_landing_page():

    client = TestClient(app)    client = TestClient(app)

    headers = get_auth_headers()    headers = get_auth_headers()

    response = client.get("/", headers=headers)    response = client.get("/", headers=headers)

    assert response.status_code == 200    assert response.status_code == 200

    # TODO need to update the test below to match current landing page    # TODO need to update the test below to match current landing page

    # assert "<h1>Welcome to Journaled</h1>" in response.text    # assert "<h1>Welcome to Journaled</h1>" in response.text



def test_docs_page():def test_docs_page():

    client = TestClient(app)    client = TestClient(app)

    response = client.get("/docs")    response = client.get("/docs")

    assert response.status_code == 200    assert response.status_code == 200

    assert "Swagger UI" in response.text    assert "Swagger UI" in response.text



def test_openapi_json():def test_openapi_json():

    client = TestClient(app)    client = TestClient(app)

    response = client.get("/openapi.json")    response = client.get("/openapi.json")

    assert response.status_code == 200    assert response.status_code == 200

    assert response.headers["content-type"].startswith("application/json")    assert "paths" in response.json()

    assert "paths" in response.json()

def test_health_endpoint_structure():

def test_health_endpoint_structure():    client = TestClient(app)

    client = TestClient(app)    response = client.get("/health")

    response = client.get("/health")    assert response.status_code == 200

    assert response.status_code == 200    data = response.json()

    data = response.json()    assert "status" in data

    assert "status" in data    assert "database" in data

    assert "database" in data

def test_accounts_endpoint():

def test_accounts_endpoint():    client = TestClient(app)

    client = TestClient(app)    headers = get_auth_headers()

    headers = get_auth_headers()    response = client.get("/accounts", headers=headers)

    response = client.get("/accounts", headers=headers)    assert response.status_code in (200, 404)

    assert response.status_code in (200, 404)

def test_create_account():

def test_create_account():    client = TestClient(app)

    client = TestClient(app)    headers = get_auth_headers()

    headers = get_auth_headers()    payload = {

    payload = {        "name": "Test Account",

        "name": "Test Account",        "code": "TST",

        "code": "TST",        "type": "ASSET",

        "type": "ASSET",        "currency": "USD",

        "currency": "USD",        "is_active": True,

        "is_active": True,        "parent_id": None

        "parent_id": None    }

    }    # Create account

    # Create account    response = client.post("/accounts/", json=payload, headers=headers)

    response = client.post("/accounts/", json=payload, headers=headers)    assert response.status_code == 201

    assert response.status_code == 201    data = response.json()

    data = response.json()    assert data["name"] == payload["name"]

    assert data["name"] == payload["name"]    assert data["type"] == payload["type"]

    assert data["type"] == payload["type"]    assert data["currency"] == payload["currency"]

    assert data["currency"] == payload["currency"]    assert data["is_active"] == payload["is_active"]

    assert data["is_active"] == payload["is_active"]

    # Delete the created account

    # Delete the created account    account_id = data["id"]

    account_id = data["id"]    del_response = client.delete(f"/accounts/{account_id}", headers=headers)

    del_response = client.delete(f"/accounts/{account_id}", headers=headers)    assert del_response.status_code == 204

    assert del_response.status_code == 204

def test_delete_account_with_attached_splits():

def test_delete_account_with_attached_splits():    client = TestClient(app)

    client = TestClient(app)    headers = get_auth_headers()

    headers = get_auth_headers()    # Create two accounts

    # Create two accounts    payload1 = {

    payload1 = {        "name": "Split Account 1",

        "name": "Split Account 1",        "code": "SPLT1",

        "code": "SPLT1",        "type": "ASSET",

        "type": "ASSET",        "currency": "USD",

        "currency": "USD",        "is_active": True,

        "is_active": True,        "parent_id": None

        "parent_id": None    }

    }    payload2 = {

    payload2 = {        "name": "Split Account 2",

        "name": "Split Account 2",        "code": "SPLT2",

        "code": "SPLT2",        "type": "ASSET",

        "type": "ASSET",        "currency": "USD",

        "currency": "USD",        "is_active": True,

        "is_active": True,        "parent_id": None

        "parent_id": None    }

    }    response1 = client.post("/accounts/", json=payload1, headers=headers)

    response1 = client.post("/accounts/", json=payload1, headers=headers)    response2 = client.post("/accounts/", json=payload2, headers=headers)

    response2 = client.post("/accounts/", json=payload2, headers=headers)    assert response1.status_code == 201

    assert response1.status_code == 201    assert response2.status_code == 201

    assert response2.status_code == 201    account_id1 = response1.json()["id"]

    account_id1 = response1.json()["id"]    account_id2 = response2.json()["id"]

    account_id2 = response2.json()["id"]    # Create a transaction with splits for both accounts

    # Create a transaction with splits for both accounts    txn_payload = {

    txn_payload = {        "date": "2025-09-15",

        "date": "2025-09-15",        "description": "Test txn",

        "description": "Test txn",        "splits": [

        "splits": [            {"account_id": account_id1, "amount": "100.00"},

            {"account_id": account_id1, "amount": "100.00"},            {"account_id": account_id2, "amount": "-100.00"}

            {"account_id": account_id2, "amount": "-100.00"}        ]

        ]    }

    }    txn_response = client.post("/transactions/", json=txn_payload, headers=headers)

    txn_response = client.post("/transactions/", json=txn_payload, headers=headers)    assert txn_response.status_code == 201

    assert txn_response.status_code == 201    # Try to delete account 1 (should fail)

    # Try to delete account 1 (should fail)    del_response = client.delete(f"/accounts/{account_id1}", headers=headers)

    del_response = client.delete(f"/accounts/{account_id1}", headers=headers)    assert del_response.status_code == 409

    assert del_response.status_code == 409    assert del_response.json()["detail"] == "Account has attached transactions and cannot be deleted"

    assert del_response.json()["detail"] == "Account has attached transactions and cannot be deleted"

def test_delete_account_with_nonzero_balance():

def test_delete_account_with_nonzero_balance():    client = TestClient(app)

    client = TestClient(app)    headers = get_auth_headers()

    headers = get_auth_headers()    # Create two accounts

    # Create two accounts    payload1 = {

    payload1 = {        "name": "Balance Account",

        "name": "Balance Account",        "code": "BAL1",

        "code": "BAL1",        "type": "ASSET",

        "type": "ASSET",        "currency": "USD",

        "currency": "USD",        "is_active": True,

        "is_active": True,        "parent_id": None

        "parent_id": None    }

    }    payload2 = {

    payload2 = {        "name": "Other Account",

        "name": "Other Account",        "code": "BAL2",

        "code": "BAL2",        "type": "ASSET",

        "type": "ASSET",        "currency": "USD",

        "currency": "USD",        "is_active": True,

        "is_active": True,        "parent_id": None

        "parent_id": None    }

    }    response1 = client.post("/accounts/", json=payload1, headers=headers)

    response1 = client.post("/accounts/", json=payload1, headers=headers)    response2 = client.post("/accounts/", json=payload2, headers=headers)

    response2 = client.post("/accounts/", json=payload2, headers=headers)    assert response1.status_code == 201

    assert response1.status_code == 201    assert response2.status_code == 201

    assert response2.status_code == 201    account_id1 = response1.json()["id"]

    account_id1 = response1.json()["id"]    account_id2 = response2.json()["id"]

    account_id2 = response2.json()["id"]    # Create a balanced transaction

    # Create a balanced transaction    txn_payload = {

    txn_payload = {        "date": "2025-09-15",

        "date": "2025-09-15",        "description": "Balanced txn",

        "description": "Balanced txn",        "splits": [

        "splits": [            {"account_id": account_id1, "amount": "100.00"},

            {"account_id": account_id1, "amount": "100.00"},            {"account_id": account_id2, "amount": "-100.00"}

            {"account_id": account_id2, "amount": "-100.00"}        ]

        ]    }

    }    txn_response = client.post("/transactions/", json=txn_payload, headers=headers)

    txn_response = client.post("/transactions/", json=txn_payload, headers=headers)    assert txn_response.status_code == 201

    assert txn_response.status_code == 201    # Try to delete account 1 (should fail)

    # Try to delete account 1 (should fail)    del_response = client.delete(f"/accounts/{account_id1}", headers=headers)

    del_response = client.delete(f"/accounts/{account_id1}", headers=headers)    assert del_response.status_code == 409

    assert del_response.status_code == 409    assert del_response.json()["detail"] == "Account has attached transactions and cannot be deleted"

    assert del_response.json()["detail"] == "Account has attached transactions and cannot be deleted"

def test_delete_nonexistent_account():

def test_delete_nonexistent_account():    client = TestClient(app)

    client = TestClient(app)    headers = get_auth_headers()

    headers = get_auth_headers()    # Try to delete an account that does not exist

    # Try to delete an account that does not exist    del_response = client.delete("/accounts/999999", headers=headers)

    del_response = client.delete("/accounts/999999", headers=headers)    assert del_response.status_code == 404

    assert del_response.status_code == 404    assert del_response.json()["detail"] == "Account not found"

    assert del_response.json()["detail"] == "Account not found"

def test_delete_account_with_no_splits_and_zero_balance():

def test_delete_account_with_no_splits_and_zero_balance():    client = TestClient(app)

    client = TestClient(app)    headers = get_auth_headers()

    headers = get_auth_headers()    # Create account

    # Create account    payload = {

    payload = {        "name": "Empty Account",

        "name": "Empty Account",        "code": "EMPTY",

        "code": "EMPTY",        "type": "ASSET",

        "type": "ASSET",        "currency": "USD",

        "currency": "USD",        "is_active": True,

        "is_active": True,        "parent_id": None

        "parent_id": None    }

    }    response = client.post("/accounts/", json=payload, headers=headers)

    response = client.post("/accounts/", json=payload, headers=headers)    assert response.status_code == 201

    assert response.status_code == 201    account_id = response.json()["id"]

    account_id = response.json()["id"]    # Try to delete account (should succeed)

    # Try to delete account (should succeed)    del_response = client.delete(f"/accounts/{account_id}", headers=headers)

    del_response = client.delete(f"/accounts/{account_id}", headers=headers)    assert del_response.status_code == 204

    assert del_response.status_code == 204
    assert response.status_code == 200    assert data["database"] == "ok"

    # TODO need to update the test below to match current landing page

    # assert "<h1>Welcome to Journaled</h1>" in response.textdef test_landing_page():

    client = TestClient(app)

def test_docs_page():    response = client.get("/")

    client = TestClient(app)    assert response.status_code == 200

    response = client.get("/docs")    # TODO need to update the test below to match current landing page

    assert response.status_code == 200    # import pytest

    assert "Swagger UI" in response.textfrom starlette.testclient import TestClient

from journaled_app.app import app

def test_openapi_json():

    client = TestClient(app)client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200

def get_auth_token():

    assert response.headers["content-type"].startswith("application/json")    """Helper function to register and login a test user, return auth token"""

    assert "paths" in response.json()    # Register a test user

    register_response = client.post("/auth/register", json={

def test_health_endpoint_structure():        "username": "testuser_api",

    client = TestClient(app)        "email": "testapi@example.com",

    response = client.get("/health")        "password": "testpass"

    assert response.status_code == 200    })

    data = response.json()    # Login to get token

    assert "status" in data    login_response = client.post("/auth/login", data={

    assert "database" in data        "username": "testuser_api",

        "password": "testpass"

def test_accounts_endpoint():    })

    client = TestClient(app)    return login_response.json()["access_token"]

    headers = get_auth_headers()

    response = client.get("/accounts", headers=headers)def get_auth_headers():

    assert response.status_code in (200, 404)    """Helper function to get authorization headers"""

    token = get_auth_token()

def test_create_account():    return {"Authorization": f"Bearer {token}"}

    client = TestClient(app)

    headers = get_auth_headers()def test_health_endpoint():

    payload = {    client = TestClient(app)

        "name": "Test Account",    response = client.get("/health")

        "code": "TST",    assert response.status_code == 200

        "type": "ASSET",    data = response.json()

        "currency": "USD",    assert data["status"] == "ok"

        "is_active": True,    assert data["database"] == "ok"

        "parent_id": None

    }def test_landing_page():

    # Create account    client = TestClient(app)

    response = client.post("/accounts/", json=payload, headers=headers)    headers = get_auth_headers()

    assert response.status_code == 201    response = client.get("/", headers=headers)

    data = response.json()    assert response.status_code == 200

    assert data["name"] == payload["name"]    # TODO need to update the test below to match current landing page

    assert data["type"] == payload["type"]    # assert "<h1>Welcome to Journaled</h1>" in response.text

    assert data["currency"] == payload["currency"]

    assert data["is_active"] == payload["is_active"]def test_docs_page():

    client = TestClient(app)

    # Delete the created account    response = client.get("/docs")

    account_id = data["id"]    assert response.status_code == 200

    del_response = client.delete(f"/accounts/{account_id}", headers=headers)    assert "Swagger UI" in response.text

    assert del_response.status_code == 204

def test_openapi_json():

def test_delete_account_with_attached_splits():    client = TestClient(app)

    client = TestClient(app)    response = client.get("/openapi.json")

    headers = get_auth_headers()    assert response.status_code == 200

    # Create two accounts    assert response.headers["content-type"].startswith("application/json")

    payload1 = {    assert "paths" in response.json()

        "name": "Split Account 1",

        "code": "SPLT1",def test_health_endpoint_structure():

        "type": "ASSET",    client = TestClient(app)

        "currency": "USD",    response = client.get("/health")

        "is_active": True,    assert response.status_code == 200

        "parent_id": None    data = response.json()

    }    assert "status" in data

    payload2 = {    assert "database" in data

        "name": "Split Account 2",

        "code": "SPLT2",def test_accounts_endpoint():

        "type": "ASSET",    client = TestClient(app)

        "currency": "USD",    headers = get_auth_headers()

        "is_active": True,    response = client.get("/accounts", headers=headers)

        "parent_id": None    assert response.status_code in (200, 404)

    }

    response1 = client.post("/accounts/", json=payload1, headers=headers)def test_create_account():

    response2 = client.post("/accounts/", json=payload2, headers=headers)    client = TestClient(app)

    assert response1.status_code == 201    headers = get_auth_headers()

    assert response2.status_code == 201    payload = {

    account_id1 = response1.json()["id"]        "name": "Test Account",

    account_id2 = response2.json()["id"]        "code": "TST",

    # Create a transaction with splits for both accounts        "type": "ASSET",

    txn_payload = {        "currency": "USD",

        "date": "2025-09-15",        "is_active": True,

        "description": "Test txn",        "parent_id": None

        "splits": [    

            {"account_id": account_id1, "amount": "100.00"},    # Create account

            {"account_id": account_id2, "amount": "-100.00"}    response = client.post("/accounts/", json=payload, headers=headers)

        ]    assert response.status_code == 201

    }    data = response.json()

    txn_response = client.post("/transactions/", json=txn_payload, headers=headers)    assert data["name"] == payload["name"]

    assert txn_response.status_code == 201    assert data["type"] == payload["type"]

    # Try to delete account 1 (should fail)    assert data["currency"] == payload["currency"]

    del_response = client.delete(f"/accounts/{account_id1}", headers=headers)    assert data["is_active"] == payload["is_active"]

    assert del_response.status_code == 409

    assert del_response.json()["detail"] == "Account has attached transactions and cannot be deleted"    # Delete the created account

    account_id = data["id"]

    del_response = client.delete(f"/accounts/{account_id}", headers=headers)

def test_delete_account_with_nonzero_balance():    assert del_response.status_code == 204

    client = TestClient(app)

    headers = get_auth_headers()def test_delete_account_with_attached_splits():

    # Create two accounts    client = TestClient(app)

    payload1 = {    headers = get_auth_headers()

        "name": "Balance Account",    # Create two accounts

        "code": "BAL1",    payload1 = {

        "type": "ASSET",        "name": "Split Account 1",

        "currency": "USD",        "code": "SPLT1",

        "is_active": True,        "type": "ASSET",

        "parent_id": None        "currency": "USD",

    }        "is_active": True,

    payload2 = {        "name": "Other Account",

        "code": "BAL2",    }

        "type": "ASSET",        "name": "Split Account 2",

        "currency": "USD",        "code": "SPLT2",

        "is_active": True,        "type": "ASSET",

        "parent_id": None        "currency": "USD",

    }        "is_active": True,

    response1 = client.post("/accounts/", json=payload1, headers=headers)        "parent_id": None

    response2 = client.post("/accounts/", json=payload2, headers=headers)    }

    assert response1.status_code == 201    response2 = client.post("/accounts/", json=payload2, headers=headers)

    account_id1 = response1.json()["id"]    assert response1.status_code == 201

    account_id2 = response2.json()["id"]    assert response2.status_code == 201

    # Create a transaction with splits for both accounts    account_id1 = response1.json()["id"]

    txn_payload = {    account_id2 = response2.json()["id"]

        "date": "2025-09-15",    # Create a transaction with splits for both accounts

        "description": "Test txn",    txn_payload = {

        "splits": [        "date": "2025-09-15",

            {"account_id": account_id1, "amount": "100.00"},        "description": "Test txn",

            {"account_id": account_id2, "amount": "-100.00"}        "splits": [

            {"account_id": account_id1, "amount": "100.00"},

            {"account_id": account_id2, "amount": "-100.00"}
        ]
    }

    txn_response = client.post("/transactions/", json=txn_payload, headers=headers)

    assert txn_response.status_code == 201

    # Try to delete account 1 (should fail)    txn_response = client.post("/transactions/", json=txn_payload, headers=headers)

    del_response = client.delete(f"/accounts/{account_id1}", headers=headers)    assert txn_response.status_code == 201

    assert del_response.status_code == 409    # Try to delete account 1 (should fail)

    assert del_response.json()["detail"] == "Account has attached transactions and cannot be deleted"    del_response = client.delete(f"/accounts/{account_id1}", headers=headers)

    assert del_response.status_code == 409

    assert del_response.json()["detail"] == "Account has attached transactions and cannot be deleted"

def test_delete_nonexistent_account():

    client = TestClient(app)

    headers = get_auth_headers()def test_delete_account_with_nonzero_balance():

    # Try to delete an account that does not exist    client = TestClient(app)

    del_response = client.delete("/accounts/999999", headers=headers)    headers = get_auth_headers()

    assert del_response.status_code == 404    # Create two accounts

    assert del_response.json()["detail"] == "Account not found"    payload1 = {

        "name": "Balance Account",

        "code": "BAL1",

def test_delete_account_with_no_splits_and_zero_balance():        "type": "ASSET",

    client = TestClient(app)        "currency": "USD",

    headers = get_auth_headers()        "is_active": True,

    # Create account        "parent_id": None

    payload = {    }

        "name": "Empty Account",    payload2 = {

        "code": "EMPTY",        "name": "Other Account",

        "type": "ASSET",        "code": "BAL2",

        "currency": "USD",        "type": "ASSET",

        "is_active": True,        "currency": "USD",

        "parent_id": None        "is_active": True,

    }        "parent_id": None

    response = client.post("/accounts/", json=payload, headers=headers)    }

    assert response.status_code == 201    response1 = client.post("/accounts/", json=payload1, headers=headers)

    account_id = response.json()["id"]    response2 = client.post("/accounts/", json=payload2, headers=headers)

    # Try to delete account (should succeed)    assert response1.status_code == 201

    del_response = client.delete(f"/accounts/{account_id}", headers=headers)    assert response2.status_code == 201

    assert del_response.status_code == 204

def test_health_endpoint():

    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"

    assert data["database"] == "ok"def test_landing_page():

    client = TestClient(app)

    headers = get_auth_headers()

    response = client.get("/", headers=headers)

    assert response.status_code == 200

    # TODO need to update the test below to match current landing page

    # assert "<h1>Welcome to Journaled</h1>" in response.textdef test_docs_page():

    client = TestClient(app)

    response = client.get("/docs")

    assert response.status_code == 200

    assert "Swagger UI" in response.textfrom starlette.testclient import TestClient

from journaled_app.app import app

def test_openapi_json():

    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200

    assert response.headers["content-type"].startswith("application/json")

    assert "paths" in response.json()def test_health_endpoint_structure():

    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert "status" in data

    assert "database" in data

def test_accounts_endpoint():

    client = TestClient(app)

    headers = get_auth_headers()

    response = client.get("/accounts", headers=headers)

    assert response.status_code in (200, 404)

def test_create_account():

    client = TestClient(app)

    headers = get_auth_headers()

    payload = {

        "name": "Test Account",

        "code": "TST",

        "type": "ASSET",

        "currency": "USD",

        "is_active": True,

        "parent_id": None

    }

    # Create account

    response = client.post("/accounts/", json=payload, headers=headers)

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == payload["name"]

    assert data["type"] == payload["type"]

    assert data["currency"] == payload["currency"]

    assert data["is_active"] == payload["is_active"]

    # Delete the created account

    account_id = data["id"]

    del_response = client.delete(f"/accounts/{account_id}", headers=headers)

    assert del_response.status_code == 204

def test_delete_account_with_attached_splits():

    client = TestClient(app)

    headers = get_auth_headers()

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

    response1 = client.post("/accounts/", json=payload1, headers=headers)

    response2 = client.post("/accounts/", json=payload2, headers=headers)

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

    txn_response = client.post("/transactions/", json=txn_payload, headers=headers)

    assert txn_response.status_code == 201

    # Try to delete account 1 (should fail)

    del_response = client.delete(f"/accounts/{account_id1}", headers=headers)

    assert del_response.status_code == 409

    assert del_response.json()["detail"] == "Account has attached transactions and cannot be deleted"

def test_delete_account_with_nonzero_balance():

    client = TestClient(app)

    headers = get_auth_headers()

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

    response1 = client.post("/accounts/", json=payload1, headers=headers)

    response2 = client.post("/accounts/", json=payload2, headers=headers)

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

    txn_response = client.post("/transactions/", json=txn_payload, headers=headers)

    assert txn_response.status_code == 201

    # Try to delete account 1 (should fail)

    del_response = client.delete(f"/accounts/{account_id1}", headers=headers)

    assert del_response.status_code == 409

    assert del_response.json()["detail"] == "Account has attached transactions and cannot be deleted"

def test_delete_nonexistent_account():

    client = TestClient(app)

    headers = get_auth_headers()

    # Try to delete an account that does not exist

    del_response = client.delete("/accounts/999999", headers=headers)

    assert del_response.status_code == 404

    assert del_response.json()["detail"] == "Account not found"

def test_delete_account_with_no_splits_and_zero_balance():

    client = TestClient(app)

    headers = get_auth_headers()

    # Create account

    payload = {

        "name": "Empty Account",

        "code": "EMPTY",

        "type": "ASSET",

        "currency": "USD",

        "is_active": True,

        "parent_id": None

    }

    response = client.post("/accounts/", json=payload, headers=headers)

    assert response.status_code == 201

    account_id = response.json()["id"]

    # Try to delete account (should succeed)

    del_response = client.delete(f"/accounts/{account_id}", headers=headers)

    assert del_response.status_code == 204

def test_health_endpoint():

    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"

    assert data["database"] == "ok"def test_landing_page():

    client = TestClient(app)

    headers = get_auth_headers()

    response = client.get("/", headers=headers)

    assert response.status_code == 200

    # TODO need to update the test below to match current landing page

    # assert "<h1>Welcome to Journaled</h1>" in response.textdef test_docs_page():

    client = TestClient(app)

    response = client.get("/docs")

    assert response.status_code == 200

    assert "Swagger UI" in response.textfrom starlette.testclient import TestClient

from journaled_app.app import app

def test_openapi_json():

    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200

    assert response.headers["content-type"].startswith("application/json")

    assert "paths" in response.json()def test_health_endpoint_structure():

    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert "status" in data

    assert "database" in data

def test_accounts_endpoint():

    client = TestClient(app)

    headers = get_auth_headers()

    response = client.get("/accounts", headers=headers)

    assert response.status_code in (200, 404)

def test_create_account():

    client = TestClient(app)

    headers = get_auth_headers()

    payload = {

        "name": "Test Account",

        "code": "TST",

        "type": "ASSET",

        "currency": "USD",

        "is_active": True,

        "parent_id": None

    }

    # Create account

    response = client.post("/accounts/", json=payload, headers=headers)

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == payload["name"]

    assert data["type"] == payload["type"]

    assert data["currency"] == payload["currency"]

    assert data["is_active"] == payload["is_active"]

    # Delete the created account

    account_id = data["id"]

    del_response = client.delete(f"/accounts/{account_id}", headers=headers)

    assert del_response.status_code == 204

def test_delete_account_with_attached_splits():

    client = TestClient(app)

    headers = get_auth_headers()

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

    response1 = client.post("/accounts/", json=payload1, headers=headers)

    response2 = client.post("/accounts/", json=payload2, headers=headers)

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

    txn_response = client.post("/transactions/", json=txn_payload, headers=headers)

    assert txn_response.status_code == 201

    # Try to delete account 1 (should fail)

    del_response = client.delete(f"/accounts/{account_id1}", headers=headers)

    assert del_response.status_code == 409

    assert del_response.json()["detail"] == "Account has attached transactions and cannot be deleted"

def test_delete_account_with_nonzero_balance():

    client = TestClient(app)

    headers = get_auth_headers()

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

    response1 = client.post("/accounts/", json=payload1, headers=headers)

    response2 = client.post("/accounts/", json=payload2, headers=headers)

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

    txn_response = client.post("/transactions/", json=txn_payload, headers=headers)

    assert txn_response.status_code == 201

    # Try to delete account 1 (should fail)

    del_response = client.delete(f"/accounts/{account_id1}", headers=headers)

    assert del_response.status_code == 409

    assert del_response.json()["detail"] == "Account has attached transactions and cannot be deleted"

def test_delete_nonexistent_account():

    client = TestClient(app)

    headers = get_auth_headers()

    # Try to delete an account that does not exist

    del_response = client.delete("/accounts/999999", headers=headers)

    assert del_response.status_code == 404

    assert del_response.json()["detail"] == "Account not found"

def test_delete_account_with_no_splits_and_zero_balance():

    client = TestClient(app)

    headers = get_auth_headers()

    # Create account

    payload = {

        "name": "Empty Account",

        "code": "EMPTY",

        "type": "ASSET",

        "currency": "USD",

        "is_active": True,

        "parent_id": None

    }

    response = client.post("/accounts/", json=payload, headers=headers)

    assert response.status_code == 201

    account_id = response.json()["id"]

    # Try to delete account (should succeed)

    del_response = client.delete(f"/accounts/{account_id}", headers=headers)

    assert del_response.status_code == 204
