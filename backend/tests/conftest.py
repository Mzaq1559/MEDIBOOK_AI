import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="session")
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as c:
        yield c

@pytest.fixture
def auth_headers_factory(client):
    """Factory fixture that returns Authorization headers for a given role.

    Supported roles: "admin", "doctor", "patient". Uses seeded credentials from README.
    """
    credentials = {
        "admin": {"email": "admin@medibook.com", "password": "Admin@123"},
        "doctor": {"email": "ahmed.khan@primecare.pk", "password": "PatientPass123!"},
        "patient": {"email": "ali.khan@example.com", "password": "PatientPass123!"},
    }

    def _factory(role: str):
        cred = credentials.get(role)
        if not cred:
            raise ValueError(f"Unsupported role '{role}'. Choose from admin, doctor, patient.")
        resp = client.post("/api/auth/login", json=cred)
        assert resp.status_code == 200, f"Login failed for role {role}: {resp.text}"
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _factory
