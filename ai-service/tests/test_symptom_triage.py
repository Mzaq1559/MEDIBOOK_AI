from app.symptom_triage import EMERGENCY_ALERT, is_emergency, recommend_specialty, triage


def test_emergency_spec_wording_trigger():
    text = "I'm having severe chest pain and can't breathe"
    assert is_emergency(text) is True
    result = triage(text)
    assert result.is_emergency is True
    assert result.urgency_level == "critical"


def test_chest_pain_and_breathing_combinations_trigger_emergency():
    # Exact case requested: chest pain + shortness of breath (without "severe")
    exact_case = "I have chest pain and shortness of breath"
    assert is_emergency(exact_case) is True
    assert triage(exact_case).is_emergency is True
    assert triage(exact_case).urgency_level == "critical"

    # Variations of chest + breathing distress
    assert is_emergency("I'm having chest pain and difficulty breathing") is True
    assert is_emergency("pain in my chest and trouble breathing") is True
    assert is_emergency("chest tightness and cannot breathe") is True
    assert is_emergency("chest pressure and hard to breathe") is True
    assert is_emergency("seene mein dard aur saans lene me dushwari") is True
    assert is_emergency("seene me dard aur saans phool rahi hai") is True


def test_broad_emergency_categories():
    # Unconsciousness / Fainting
    assert is_emergency("patient is unconscious and unresponsive") is True
    assert is_emergency("he fainted and collapsed") is True
    assert is_emergency("mareez behosh ho gaya hai") is True
    assert is_emergency("hosh nahi aa raha") is True

    # Heavy / Severe Bleeding
    assert is_emergency("heavy bleeding from head injury") is True
    assert is_emergency("bleeding heavily non-stop") is True
    assert is_emergency("coughing up blood") is True
    assert is_emergency("bohot zyada khoon beh raha hai") is True

    # Stroke
    assert is_emergency("suspected stroke with face drooping and slurred speech") is True
    assert is_emergency("falij ka attack hua hai chehra terha ho gaya") is True

    # Seizures
    assert is_emergency("having severe epileptic seizure fits") is True
    assert is_emergency("mareez ko daure par rahe hain") is True

    # Heart Attack
    assert is_emergency("he is having a heart attack") is True
    assert is_emergency("dil ka daura para hai") is True

    # Poison / Overdose
    assert is_emergency("accidental overdose of sleeping pills") is True
    assert is_emergency("bachay ne zehar pee liya") is True


def test_routine_specialty_routing_without_emergency():
    # Routine Cardiology checkup (no breathing distress or emergency modifiers)
    cardio_text = "I want a consultation for high blood pressure and hypertension"
    assert is_emergency(cardio_text) is False
    assert recommend_specialty(cardio_text) == "Cardiologist"

    # Routine Dermatology
    derm_text = "itchy rash on my arm"
    assert is_emergency(derm_text) is False
    assert recommend_specialty(derm_text) == "Dermatologist"

    # Routine ENT
    ent_text = "sore throat and sinus congestion"
    assert is_emergency(ent_text) is False
    assert recommend_specialty(ent_text) == "ENT Specialist"


def test_emergency_alert_matches_spec_exactly():
    assert "PLEASE CALL: 1100 (Emergency) or 15 (Ambulance)" in EMERGENCY_ALERT
    assert EMERGENCY_ALERT.startswith("🚨 EMERGENCY ALERT 🚨")


def test_roman_urdu_emergency_detection():
    # Emergency triggers in Roman Urdu
    assert is_emergency("seene mein shadeed dard ho raha hai") is True
    assert is_emergency("saans lene me dushwari ho rahi hai") is True
    assert is_emergency("saans nahi aa rahi") is True
    assert is_emergency("mareez behosh ho gaya hai") is True
    assert is_emergency("bohot khoon beh raha hai") is True

    # Emergency triage result
    res = triage("seene mein shadeed dard hai")
    assert res.is_emergency is True
    assert res.urgency_level == "critical"


def test_roman_urdu_specialty_routing():
    # Cardiology routing (routine/palpitation, not emergency)
    cardio_res = triage("mujhe blood pressure ka masla hai aur dil ki dharkan check karwani hai")
    assert cardio_res.is_emergency is False
    assert cardio_res.specialty == "Cardiologist"

    # Dermatology routing
    derm_res = triage("chehre par daane aur jild par kharish hai")
    assert derm_res.is_emergency is False
    assert derm_res.specialty == "Dermatologist"

    # ENT routing
    ent_res = triage("gala kharab hai naak band aur khansi hai")
    assert ent_res.is_emergency is False
    assert ent_res.specialty == "ENT Specialist"

