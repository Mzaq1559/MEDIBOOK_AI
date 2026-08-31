import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.tools import tool_retrieve_medical_knowledge

def test_rag_direct():
    session = {"conversation_id": "test-rag-123", "messages": []}
    args = {"symptoms": "I've been having a severe headache and blurred vision for the last two days. It's getting worse."}
    
    print("--- Simulating Agent Tool Call ---")
    print(f"Tool: retrieve_medical_knowledge")
    print(f"Args: {args}")
    
    print("\n--- Executing Tool ---")
    result = tool_retrieve_medical_knowledge(session, args, auth=None)
    
    print("\n--- Tool Result (Grounded Content) ---")
    print(f"Success: {result.get('ok')}")
    print(f"Specialty: {result.get('specialty')}")
    print(f"Urgency: {result.get('urgency_level')}")
    print(f"Needs Emergency Care: {result.get('needs_emergency_care')}")
    print(f"\nGrounded Bot Message:\n{result.get('bot_message')}")

if __name__ == "__main__":
    test_rag_direct()
