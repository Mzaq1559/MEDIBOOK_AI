import pytest
import uuid


def test_standard_404_error(client):
    non_existent_uuid = str(uuid.uuid4())
    response = client.get(f"/api/doctors/{non_existent_uuid}")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] is True
    assert data["status_code"] == 404
    assert data["error_code"] == "NOT_FOUND"
    assert "timestamp" in data
    assert "request_id" in data


def test_standard_422_validation_error(client):
    # Invalid email format and missing fields
    response = client.post("/api/auth/register", json={"email": "not-an-email"})
    assert response.status_code == 422
    data = response.json()
    assert data["error"] is True
    assert data["status_code"] == 422
    assert data["error_code"] == "INVALID_INPUT"
    assert "errors" in data["details"]


def test_security_headers_present(client):
    response = client.get("/health")
    assert response.status_code == 200
    headers = response.headers
    assert "x-request-id" in headers or "X-Request-ID" in headers
    assert headers.get("x-content-type-options") == "nosniff" or headers.get("X-Content-Type-Options") == "nosniff"
    assert "x-frame-options" in headers or "X-Frame-Options" in headers


def test_chat_endpoints(client, seed_data):
    # 1. Regular appointment query
    res = client.post("/api/chat/message", json={"message": "I want to book an appointment with a cardiologist"})
    assert res.status_code == 200
    data = res.json()
    assert "conversation_id" in data
    assert "bot_message" in data
    assert len(data["options"]) > 0

    conv_id = data["conversation_id"]

    # 2. Emergency triage query
    res_em = client.post("/api/chat/message", json={
        "conversation_id": conv_id,
        "message": "I am having severe chest pain and cannot breathe"
    })
    assert res_em.status_code == 200
    data_em = res_em.json()
    assert "EMERGENCY ALERT" in data_em["bot_message"]

    # 3. Retrieve conversation history
    res_hist = client.get(f"/api/chat/history/{conv_id}")
    assert res_hist.status_code == 200
    hist_data = res_hist.json()
    assert len(hist_data["messages"]) >= 4
