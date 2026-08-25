import pytest


def test_register_success(client):
    payload = {
        "email": "newpatient@example.com",
        "phone": "03009988776",
        "name": "New Patient",
        "password": "SecurePass123!",
        "user_type": "patient"
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newpatient@example.com"
    assert data["name"] == "New Patient"
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user_type"] == "patient"


def test_register_weak_password(client):
    payload = {
        "email": "weak@example.com",
        "name": "Weak Pass User",
        "password": "password",
        "user_type": "patient"
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["error"] is True
    assert data["error_code"] == "WEAK_PASSWORD"


def test_register_duplicate_email(client, seed_data):
    payload = {
        "email": "ali.khan@example.com",
        "name": "Ali Clone",
        "password": "SecurePass123!",
        "user_type": "patient"
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["error"] is True
    assert data["error_code"] == "EMAIL_DUPLICATE"


def test_register_duplicate_phone(client, seed_data):
    payload = {
        "email": "unique@example.com",
        "phone": "03001234567",  # Ali Khan's phone in seed_data
        "name": "Phone Clone",
        "password": "SecurePass123!",
        "user_type": "patient"
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["error"] is True
    assert data["error_code"] == "PHONE_DUPLICATE"


def test_login_success(client, seed_data):
    payload = {
        "email": "ali.khan@example.com",
        "password": "PatientPass123!"
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "ali.khan@example.com"
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_invalid_credentials(client, seed_data):
    payload = {
        "email": "ali.khan@example.com",
        "password": "WrongPassword!"
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401
    data = response.json()
    assert data["error"] is True
    assert data["error_code"] == "INVALID_CREDENTIALS"


def test_login_user_not_found(client):
    payload = {
        "email": "nonexistent@example.com",
        "password": "SecurePass123!"
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401
    data = response.json()
    assert data["error"] is True


def test_refresh_token_success(client, seed_data):
    # First login to get refresh token
    login_res = client.post("/api/auth/login", json={
        "email": "ali.khan@example.com",
        "password": "PatientPass123!"
    })
    refresh_token = login_res.json()["refresh_token"]

    response = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


def test_refresh_token_invalid(client):
    response = client.post("/api/auth/refresh", json={"refresh_token": "invalid.jwt.token"})
    assert response.status_code == 401
    data = response.json()
    assert data["error"] is True


def test_get_me_authenticated(client, seed_data):
    response = client.get("/api/auth/me", headers=seed_data["patient_headers"])
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "ali.khan@example.com"
    assert data["user_type"] == "patient"


def test_get_me_unauthorized(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    data = response.json()
    assert data["error"] is True
    assert data["error_code"] == "UNAUTHORIZED"
