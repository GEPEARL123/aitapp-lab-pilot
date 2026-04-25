"""
AIiTAPP — Deployment Validation Script

Verifies that a running API instance (local or remote) returns correct
results for all three core checks: health, delegation scoring, and
evidence integrity.

Usage:
    python validate.py                          # tests http://127.0.0.1:8000
    AITAPP_API_URL=https://your-url python validate.py
"""

import os
import sys
import json

try:
    import requests
except ImportError:
    print("ERROR: 'requests' is not installed. Run: pip install requests")
    sys.exit(1)

BASE_URL = os.environ.get("AITAPP_API_URL", "http://127.0.0.1:8000").rstrip("/")
PASS = "PASS"
FAIL = "FAIL"

results = []


def check(label, passed, detail=""):
    status = PASS if passed else FAIL
    results.append((label, status, detail))
    marker = "  [PASS]" if passed else "  [FAIL]"
    print(f"{marker}  {label}")
    if detail:
        print(f"         {detail}")


def run_check(label, fn):
    try:
        fn()
    except Exception as e:
        check(label, False, f"Exception: {e}")


# ── 1. Health check ───────────────────────────────────────────────────────────
def check_health():
    resp = requests.get(f"{BASE_URL}/health", timeout=10)
    resp.raise_for_status()
    data = resp.json()
    ok = data.get("status") == "healthy"
    check("Health endpoint", ok, f"status={data.get('status')}")

# ── 2. Delegation scoring (demo endpoint — no key required) ───────────────────
SCORE_PAYLOAD = {
    "agent_id":           "validate-agent-001",
    "agent_name":         "Validation Agent",
    "action_type":        "send",
    "action_description": "Surface ARID1B variant pattern to lead researcher",
    "confidence":          8.2,
    "provenance_score":    4.1,
    "trust_history_score": 4.0,
    "risk_class":          "high",
    "contradiction_count": 1,
    "evidence_age_hours":  1128.0,
    "weight_profile":      "medical",
}

def check_scoring():
    resp = requests.post(f"{BASE_URL}/v1/action/score/demo", json=SCORE_PAYLOAD, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    score = data.get("delegation_score")
    state = data.get("authority_state")
    # Expected: score ~4.5, state ORANGE
    score_ok = score is not None and 4.0 <= score <= 5.0
    state_ok = state == "ORANGE"
    ok = score_ok and state_ok
    check(
        "Delegation scoring — ORANGE medical scenario",
        ok,
        f"delegation_score={score}, authority_state={state}  (expected ~4.5, ORANGE)"
    )

# ── 3. Evidence integrity (demo endpoint — no key required) ───────────────────
EVIDENCE_PAYLOAD = {
    "agent_id":           "validate-agent-001",
    "agent_name":         "Validation Agent",
    "action_description": "Surface ARID1B variant pattern",
    "weight_profile":     "medical",
    "internal_lab_evidence": [
        {
            "source_id":          "internal-core-001",
            "source_type":        "lab_study",
            "claim_text":         "ARID1B variant patients show 34% higher response (n=120, replicated)",
            "claim_type":         "validated_fact",
            "evidence_status":    "published",
            "provenance_score":   8.5,
            "authority_score":    8.7,
            "evidence_age_hours": 48.0,
            "replication_status": "replicated",
            "included_in_query":  True,
            "intended_use":       "support",
        }
    ],
    "external_evidence_sources": [
        {
            "source_id":          "ext-interview-001",
            "source_type":        "interview",
            "claim_text":         "Researcher believes benefit is stronger in younger patients",
            "claim_type":         "interview_supposition",
            "evidence_status":    "informal",
            "provenance_score":   1.5,
            "authority_score":    2.0,
            "evidence_age_hours": 6.0,
            "replication_status": "not_replicated",
            "included_in_query":  True,
            "intended_use":       "support",
        }
    ],
}

def check_evidence():
    resp = requests.post(f"{BASE_URL}/v1/evidence/check/demo", json=EVIDENCE_PAYLOAD, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    gate = data.get("integrity_gate")
    alert = data.get("supervisor_alert")
    # Expected: BLOCK, supervisor_alert True
    ok = gate == "BLOCK" and alert is True
    check(
        "Evidence integrity — BLOCK on misclassified interview source",
        ok,
        f"integrity_gate={gate}, supervisor_alert={alert}  (expected BLOCK, true)"
    )


# ── Run ───────────────────────────────────────────────────────────────────────
print()
print(f"  AIiTAPP Validation — {BASE_URL}")
print("  " + "─" * 54)

run_check("Health endpoint", check_health)
run_check("Delegation scoring — ORANGE medical scenario", check_scoring)
run_check("Evidence integrity — BLOCK on misclassified interview source", check_evidence)

print("  " + "─" * 54)

passed = sum(1 for _, s, _ in results if s == PASS)
failed = sum(1 for _, s, _ in results if s == FAIL)
print(f"  {passed} passed  {failed} failed")
print()

if failed > 0:
    sys.exit(1)
