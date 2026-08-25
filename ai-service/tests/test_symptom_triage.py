from app.symptom_triage import EMERGENCY_ALERT, is_emergency, recommend_specialty, triage


def test_emergency_spec_wording_trigger():
    text = "I'm having severe chest pain and can't breathe"
    assert is_emergency(text)
    result = triage(text)
    assert result.is_emergency is True
    assert result.urgency_level == "critical"


def test_booking_flow_chest_pain_is_not_emergency():
    text = "I have chest pain and shortness of breath"
    assert is_emergency(text) is False
    assert recommend_specialty(text) == "Cardiologist"
    assert triage(text).urgency_level == "high"


def test_dermatology_and_ent_routing():
    assert recommend_specialty("itchy rash on my arm") == "Dermatologist"
    assert recommend_specialty("sore throat and sinus congestion") == "ENT Specialist"


def test_emergency_alert_matches_spec_exactly():
    assert "PLEASE CALL: 1100 (Emergency) or 15 (Ambulance)" in EMERGENCY_ALERT
    assert EMERGENCY_ALERT.startswith("🚨 EMERGENCY ALERT 🚨")
