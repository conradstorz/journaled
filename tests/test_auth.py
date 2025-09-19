# tests/test_auth.py
import pytest
from starlette.testclient import TestClient
from journaled_app.app import app
from journaled_app.db import SessionLocal
from journaled_app.models import User

client = TestClient(app)

def test_register_user():
    response = client.post("/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"

def test_login_user():
    # First register
    client.post("/auth/register", json={
        "username": "testuser2",
        "email": "test2@example.com",
        "password": "testpass"
    })
    # Then login
    response = client.post("/auth/login", data={
        "username": "testuser2",
        "password": "testpass"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_get_current_user():
    # Register and login
    client.post("/auth/register", json={
        "username": "testuser3",
        "email": "test3@example.com",
        "password": "testpass"
    })
    login_response = client.post("/auth/login", data={
        "username": "testuser3",
        "password": "testpass"
    })
    token = login_response.json()["access_token"]
    
    # Access protected route
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser3"

def test_invalid_login():
    response = client.post("/auth/login", data={
        "username": "nonexistent",
        "password": "wrongpass"
    })
    assert response.status_code == 401