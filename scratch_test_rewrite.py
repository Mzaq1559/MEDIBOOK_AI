import re

with open("ai-service/tests/test_agentic_tools.py", "r") as f:
    content = f.read()

# Fix schemas test
old_schemas = """    assert names == {
        "get_patient_appointments",
        "reschedule_appointment",
        "cancel_appointment",
        "book_appointment",
        "get_doctors_by_specialty",
        "get_availability",
        "get_patient_info",
    }"""
new_schemas = """    assert names == {
        "get_patient_appointments",
        "propose_reschedule_appointment",
        "propose_cancel_appointment",
        "propose_book_appointment",
        "execute_confirmed_action",
        "get_doctors_by_specialty",
        "get_availability",
        "get_patient_info",
    }"""
content = content.replace(old_schemas, new_schemas)

# Fix chest pain booking test
old_book_test = """    groq_confirm = [
        FakeMessage(
            tool_calls=[
                FakeToolCall(
                    "book_appointment",
                    {
                        "patient_id": PATIENT_ID,
                        "doctor_id": DOC_ID,
                        "datetime": SLOT_TS,
                        "symptoms": "chest pain",
                    },
                    "c3",
                )
            ]
        ),
        FakeMessage(content="Your appointment with Dr. Ahmed Malik is confirmed."),
    ]
    with patch("app.backend_client.create_appointment", return_value=created) as mock_create:
        with patch("app.groq_client.complete_with_tools", side_effect=groq_confirm):
            booked = handle_message(
                conversation_id=conv_id,
                patient_id=PATIENT_ID,
                message="Yes, please book it",
                language="english",
                authorization="Bearer test-token",
            )
    mock_create.assert_called_once()
    assert "confirmed" in booked["bot_message"].lower()"""

new_book_test = """    groq_confirm = [
        FakeMessage(
            tool_calls=[
                FakeToolCall(
                    "propose_book_appointment",
                    {
                        "patient_id": PATIENT_ID,
                        "doctor_id": DOC_ID,
                        "datetime": SLOT_TS,
                        "symptoms": "chest pain",
                    },
                    "c3",
                )
            ]
        ),
        FakeMessage(content="Shall I proceed with booking?"),
    ]
    with patch("app.backend_client.create_appointment", return_value=created) as mock_create:
        with patch("app.groq_client.complete_with_tools", side_effect=groq_confirm):
            proposed = handle_message(
                conversation_id=conv_id,
                patient_id=PATIENT_ID,
                message="Yes, please book it",
                language="english",
                authorization="Bearer test-token",
            )
    mock_create.assert_not_called()
    assert "proceed" in proposed["bot_message"].lower()

    from app.tools import _PROPOSALS
    pid = list(_PROPOSALS.keys())[-1]

    groq_exec = [
        FakeMessage(
            tool_calls=[
                FakeToolCall("execute_confirmed_action", {"proposal_id": pid}, "c4")
            ]
        ),
        FakeMessage(content="Your appointment with Dr. Ahmed Malik is confirmed."),
    ]
    with patch("app.backend_client.create_appointment", return_value=created) as mock_create:
        with patch("app.groq_client.complete_with_tools", side_effect=groq_exec):
            booked = handle_message(
                conversation_id=conv_id,
                patient_id=PATIENT_ID,
                message="Yes, do it",
                language="english",
                authorization="Bearer test-token",
            )
    mock_create.assert_called_once()
    assert "confirmed" in booked["bot_message"].lower()"""
content = content.replace(old_book_test, new_book_test)

# Fix reschedule test
old_reschedule_test = """    groq_write = [
        FakeMessage(
            tool_calls=[
                FakeToolCall(
                    "reschedule_appointment",
                    {"appointment_id": APPT_ID, "new_datetime": SLOT_TS},
                    "r2",
                )
            ]
        ),
        FakeMessage(content="Your appointment is rescheduled to 2026-09-01 at 09:00 AM."),
    ]
    with patch("app.backend_client.reschedule_appointment", return_value={"status": "scheduled"}) as mock_rs:
        with patch("app.groq_client.complete_with_tools", side_effect=groq_write):
            done = handle_message(
                conversation_id=conv_id,
                patient_id=PATIENT_ID,
                message="Yes, confirm the new time",
                language="english",
                authorization="Bearer test-token",
            )
    mock_rs.assert_called_once()
    assert "reschedule" in done["bot_message"].lower()"""

new_reschedule_test = """    groq_write = [
        FakeMessage(
            tool_calls=[
                FakeToolCall(
                    "propose_reschedule_appointment",
                    {"appointment_id": APPT_ID, "new_datetime": SLOT_TS},
                    "r2",
                )
            ]
        ),
        FakeMessage(content="Shall I confirm?"),
    ]
    with patch("app.backend_client.reschedule_appointment", return_value={"status": "scheduled"}) as mock_rs:
        with patch("app.groq_client.complete_with_tools", side_effect=groq_write):
            proposed = handle_message(
                conversation_id=conv_id,
                patient_id=PATIENT_ID,
                message="Yes, confirm the new time",
                language="english",
                authorization="Bearer test-token",
            )
    mock_rs.assert_not_called()
    
    from app.tools import _PROPOSALS
    pid = list(_PROPOSALS.keys())[-1]
    
    groq_exec = [
        FakeMessage(
            tool_calls=[
                FakeToolCall("execute_confirmed_action", {"proposal_id": pid}, "r3")
            ]
        ),
        FakeMessage(content="Your appointment is rescheduled to 2026-09-01 at 09:00 AM."),
    ]
    with patch("app.backend_client.reschedule_appointment", return_value={"status": "scheduled"}) as mock_rs:
        with patch("app.groq_client.complete_with_tools", side_effect=groq_exec):
            done = handle_message(
                conversation_id=conv_id,
                patient_id=PATIENT_ID,
                message="Yes",
                language="english",
                authorization="Bearer test-token",
            )
    mock_rs.assert_called_once()
    assert "reschedule" in done["bot_message"].lower()"""
content = content.replace(old_reschedule_test, new_reschedule_test)

# Fix cancel reject test
content = content.replace('"cancel_appointment",', '"propose_cancel_appointment",')

with open("ai-service/tests/test_agentic_tools.py", "w") as f:
    f.write(content)
