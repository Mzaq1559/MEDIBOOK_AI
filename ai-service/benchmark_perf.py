import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("benchmark")

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import backend_client, groq_client, tools, chatbot
from app.chatbot import handle_message, new_session, get_session
from app.symptom_triage import is_emergency

# Generate auth token dynamically with correct SECRET_KEY
import jwt
SECRET_KEY = "medibook-demo-secret-key-change-in-production-32chars!"
payload = {
    "sub": "33333333-3333-4333-a333-333333333333",
    "email": "ali.khan@example.com",
    "user_type": "patient",
    "token_type": "access",
    "iss": "medibook-api",
    "iat": int(time.time()),
    "exp": int(time.time()) + 86400
}
AUTH_TOKEN = "Bearer " + jwt.encode(payload, SECRET_KEY, algorithm="HS256")

TEST_CASES = [
    {
        "id": "1_emergency",
        "name": "1. Emergency Alert (Guard Check)",
        "message": "I have severe chest pain radiating down my left arm and I cannot breathe!",
        "auth": AUTH_TOKEN,
        "patient_id": "a3333333-3333-4333-a333-333333333333"
    },
    {
        "id": "2_plain_faq",
        "name": "2. Plain FAQ (No Tool Call)",
        "message": "What are your clinic opening hours and address?",
        "auth": AUTH_TOKEN,
        "patient_id": "a3333333-3333-4333-a333-333333333333"
    },
    {
        "id": "3_single_tool_appointments",
        "name": "3. Single-Tool Lookup (Appointments)",
        "message": "What upcoming appointments do I have scheduled?",
        "auth": AUTH_TOKEN,
        "patient_id": "a3333333-3333-4333-a333-333333333333"
    },
    {
        "id": "4_single_tool_doctors",
        "name": "4. Single-Tool Lookup (Doctors)",
        "message": "Can you list all the General Physicians available at the clinic?",
        "auth": AUTH_TOKEN,
        "patient_id": "a3333333-3333-4333-a333-333333333333"
    },
    {
        "id": "5_rag_symptom_triage",
        "name": "5. Symptom / RAG Conversation",
        "message": "I've had a persistent dry cough, sore throat, and mild fever for 3 days. What specialist should I see?",
        "auth": AUTH_TOKEN,
        "patient_id": "a3333333-3333-4333-a333-333333333333"
    },
    {
        "id": "6_multi_tool_booking",
        "name": "6. Multi-Tool Booking Flow",
        "message": "I need to book an appointment with a Cardiologist tomorrow for chest tightness.",
        "auth": AUTH_TOKEN,
        "patient_id": "a3333333-3333-4333-a333-333333333333"
    },
    {
        "id": "7_multi_tool_reschedule",
        "name": "7. Multi-Tool Reschedule Flow",
        "message": "Please reschedule my appointment with Dr. Tariq to next Tuesday.",
        "auth": AUTH_TOKEN,
        "patient_id": "a3333333-3333-4333-a333-333333333333"
    }
]

def run_benchmark():
    print("=" * 80)
    print(f"MEDIBOOK AI - PERFORMANCE BENCHMARK (GROQ_MODEL={os.getenv('GROQ_MODEL', 'default')})")
    print("=" * 80)

    # Warmup sentence transformer/RAG pipeline first to eliminate cold-start download artifact from measurement
    print("Warming up RAG embeddings & models...")
    try:
        from app.rag.pipeline import get_rag_pipeline
        get_rag_pipeline().triage_symptoms("warmup test")
    except Exception as e:
        print("Warmup warning:", e)

    results = []

    for test in TEST_CASES:
        conv_id = f"bench-{test['id']}-{int(time.time())}"
        session = new_session(conv_id, test["patient_id"])
        
        # Turn metrics storage
        groq_calls = []
        tool_calls = []
        
        # Monkey patch groq client for this turn
        orig_complete_with_tools = groq_client.complete_with_tools
        def traced_complete_with_tools(*args, **kwargs):
            t0 = time.perf_counter()
            res = orig_complete_with_tools(*args, **kwargs)
            dur = (time.perf_counter() - t0) * 1000
            t_calls = getattr(res, "tool_calls", None) or []
            tool_names = [getattr(tc.function, "name", "") for tc in t_calls] if t_calls else []
            groq_calls.append({"dur_ms": dur, "tools_returned": tool_names})
            return res
        groq_client.complete_with_tools = traced_complete_with_tools

        # Monkey patch execute_tool for this turn
        orig_execute_tool = tools.execute_tool
        def traced_execute_tool(name, arguments, sess, auth):
            t0 = time.perf_counter()
            backend_client.reset_turn_http_metrics()
            res = orig_execute_tool(name, arguments, sess, auth)
            dur = (time.perf_counter() - t0) * 1000
            http_dur = backend_client.last_http_calls_total_ms
            http_count = backend_client.last_http_call_count
            local_dur = max(0.0, dur - http_dur)
            tool_calls.append({
                "name": name,
                "total_ms": dur,
                "http_ms": http_dur,
                "http_calls": http_count,
                "local_ms": local_dur
            })
            return res
        tools.execute_tool = traced_execute_tool

        # Measure turn start
        t_start = time.perf_counter()
        
        # Measure emergency check time
        t_em0 = time.perf_counter()
        em_res = is_emergency(test["message"])
        em_dur = (time.perf_counter() - t_em0) * 1000
        
        # Run agent loop via handle_message
        res_payload = handle_message(
            conversation_id=conv_id,
            patient_id=test["patient_id"],
            message=test["message"],
            language="english",
            authorization=test["auth"]
        )
        
        total_turn_ms = (time.perf_counter() - t_start) * 1000
        
        # Restore monkey patches
        groq_client.complete_with_tools = orig_complete_with_tools
        tools.execute_tool = orig_execute_tool

        total_groq_ms = sum(c["dur_ms"] for c in groq_calls)
        total_tool_ms = sum(c["total_ms"] for c in tool_calls)
        total_http_ms = sum(c["http_ms"] for c in tool_calls)
        total_local_ms = sum(c["local_ms"] for c in tool_calls)

        res_summary = {
            "id": test["id"],
            "name": test["name"],
            "message": test["message"],
            "emergency_check_ms": em_dur,
            "groq_round_trips": len(groq_calls),
            "groq_calls": groq_calls,
            "total_groq_ms": total_groq_ms,
            "tool_calls": tool_calls,
            "total_tool_ms": total_tool_ms,
            "total_http_ms": total_http_ms,
            "total_local_ms": total_local_ms,
            "total_turn_ms": total_turn_ms,
            "bot_message": res_payload.get("bot_message", "")[:100]
        }
        results.append(res_summary)
        
        print(f"\n--- {test['name']} ---")
        print(f"User: '{test['message']}'")
        print(f"Total Turn Time: {total_turn_ms:.2f} ms")
        print(f"Emergency Check: {em_dur:.2f} ms")
        print(f"Groq Round Trips: {len(groq_calls)} (Total Groq Time: {total_groq_ms:.2f} ms)")
        for idx, gc in enumerate(groq_calls, 1):
            print(f"  - Groq Round {idx}: {gc['dur_ms']:.2f} ms -> Tools: {gc['tools_returned']}")
        print(f"Tool Calls: {len(tool_calls)} (Total Tool Time: {total_tool_ms:.2f} ms | HTTP: {total_http_ms:.2f} ms | Local: {total_local_ms:.2f} ms)")
        for tc in tool_calls:
            print(f"  - Tool '{tc['name']}': Total {tc['total_ms']:.2f} ms (HTTP {tc['http_ms']:.2f} ms [{tc['http_calls']} calls], Local {tc['local_ms']:.2f} ms)")
        print(f"Bot Message Snippet: {res_payload.get('bot_message', '')[:80]}...")
        
        # Pace requests slightly to avoid Groq rate limit spikes during benchmark
        time.sleep(2)

    print("\n" + "=" * 85)
    print("SUMMARY TABLE (LATENCY BREAKDOWN BY CONVERSATION TEST CASE)")
    print("=" * 85)
    header = f"{'Test Case':<32} | {'Total (s)':<9} | {'Groq Rounds':<11} | {'Groq (ms)':<10} | {'Tools (ms)':<10} | {'HTTP (ms)':<10}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(f"{r['name']:<32} | {r['total_turn_ms']/1000:<9.2f} | {r['groq_round_trips']:<11} | {r['total_groq_ms']:<10.1f} | {r['total_tool_ms']:<10.1f} | {r['total_http_ms']:<10.1f}")
    print("=" * 85)

    with open("/app/benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_benchmark()
