import re

with open("ai-service/app/tools.py", "r") as f:
    content = f.read()

# Replace tool definitions names
content = content.replace('"name": "reschedule_appointment"', '"name": "propose_reschedule_appointment"')
content = content.replace('"name": "cancel_appointment"', '"name": "propose_cancel_appointment"')
content = content.replace('"name": "book_appointment"', '"name": "propose_book_appointment"')

# Add execute_confirmed_action definition
EXECUTE_TOOL = """    {
        "type": "function",
        "function": {
            "name": "execute_confirmed_action",
            "description": (
                "Executes a previously proposed action. Call this ONLY after the user explicitly "
                "confirms the proposal summary."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "proposal_id": {
                        "type": "string",
                        "description": "The ID of the proposal to execute",
                    }
                },
                "required": ["proposal_id"],
            },
        },
    },"""
content = content.replace('    {\n        "type": "function",\n        "function": {\n            "name": "get_doctors_by_specialty"', EXECUTE_TOOL + '\n    {\n        "type": "function",\n        "function": {\n            "name": "get_doctors_by_specialty"')

# Replace REQUIRED_PARAMS
content = content.replace('"reschedule_appointment": ["appointment_id", "new_datetime"],', '"propose_reschedule_appointment": ["appointment_id", "new_datetime"],\n    "execute_confirmed_action": ["proposal_id"],')
content = content.replace('"cancel_appointment": ["appointment_id"],', '"propose_cancel_appointment": ["appointment_id"],')
content = content.replace('"book_appointment": ["patient_id", "doctor_id", "datetime", "symptoms"],', '"propose_book_appointment": ["patient_id", "doctor_id", "datetime", "symptoms"],')

# Replace WRITE_TOOLS
content = content.replace('WRITE_TOOLS = frozenset({"book_appointment", "reschedule_appointment", "cancel_appointment"})', 'WRITE_TOOLS = frozenset({"propose_book_appointment", "propose_reschedule_appointment", "propose_cancel_appointment", "execute_confirmed_action"})')

# Modify build_system_prompt
old_prompt_rule = '"- For booking, reschedule, and cancel: confirm in one short sentence, then wait for "\n        "a clear yes before calling the write tool.\\n"'
new_prompt_rule = '"- For booking, reschedule, and cancel: call propose_X first, state the summary, wait for "\n        "explicit affirmative text, then call execute_confirmed_action.\\n"'
content = content.replace(old_prompt_rule, new_prompt_rule)

# Add Proposal Storage
PROPOSAL_CODE = """
import time
import uuid

_PROPOSALS = {}

def _create_proposal(session: dict[str, Any], p_type: str, patient_id: str, data: dict[str, Any], summary: str) -> str:
    pid = str(uuid.uuid4())
    _PROPOSALS[pid] = {
        "id": pid,
        "type": p_type,
        "patient_id": patient_id,
        "session_id": session.get("conversation_id"),
        "data": data,
        "summary": summary,
        "created_at": time.time(),
        "used": False
    }
    return pid
"""
content = content.replace('logger = logging.getLogger("medibook.ai.tools")', 'logger = logging.getLogger("medibook.ai.tools")\n' + PROPOSAL_CODE)

with open("ai-service/app/tools.py", "w") as f:
    f.write(content)
