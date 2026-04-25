"""
AIiTAPP — Medical Conference Demo
Synthetic Rare Disease Research Scenario

This script demonstrates the WITH vs WITHOUT AIiTAPP comparison live on stage.
Run this from Terminal. No patient data is used — all data is fictional.

BEFORE RUNNING: Make sure your API is deployed and AITAPP_API_URL is set.
See DEPLOY.md for deployment instructions.

Usage:
    python demo_medical.py              # Run full demo sequence
    python demo_medical.py --offline    # Run with pre-calculated values (no API needed)
"""

import json
import sys
import time
import os
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ── Configuration ─────────────────────────────────────────────────────────────
API_URL = os.environ.get("AITAPP_API_URL", "http://127.0.0.1:8000")
API_KEY = os.environ.get("AITAPP_API_KEY", "dev-key-change-in-production")

# ── The Scenario ──────────────────────────────────────────────────────────────
# Three fictional institution datasets. One research agent. One pattern recommendation.
# This scenario is designed to score ORANGE — the most instructive state for a demo.

SCENARIO = {
    "title": "RarePath Research Network — Federated Pattern Analysis",
    "agent_id": "research-agent-rp-001",
    "agent_name": "RarePath Pattern Analyzer v2.1",
    "action_type": "send",
    "action_description": (
        "Surface clinical pattern to lead researcher: Patients with ARID1B variant "
        "show 34% higher response rate to Protocol X across three institution cohorts "
        "(n=47 combined). Recommend consideration for protocol modification."
    ),
    
    # The AI reports high confidence — this is the trap
    "confidence": 8.2,
    
    # Provenance is weak — Dataset 3 is 47 days old
    # Realistic score: 4.1 (one of three sources has stale provenance)
    "provenance_score": 4.1,
    
    # Trust history is low — this agent has made 2 incorrect pattern calls in last 6 actions
    # Calibration score: (10+7+3+3+10+7) / 6 = 6.67 → rounded to 4.0 after incorrect weighting
    "trust_history_score": 4.0,
    
    # Risk: high — this feeds a protocol modification recommendation
    "risk_class": "high",
    
    # Contradiction: Dataset 4 (not included in this query) contradicts the pattern
    "contradiction_count": 1,
    
    # Freshness: Dataset 3 is 47 days old
    "evidence_age_hours": 1128.0,  # 47 days × 24 hours
    
    # No upstream agent in this scenario
    "source_agent_id": None,
    "source_agent_calibration": None,
    "downstream_action_count": 2,  # researcher + protocol team
    
    "weight_profile": "medical"
}

# Pre-calculated expected output (for offline mode or verification)
# Medical weights: C=0.15, P=0.30, T=0.20, R=0.25, N=0.07, F=0.03
EXPECTED_OUTPUT = {
    "dimensions": {
        "confidence":    {"raw": 8.2,  "weight": 0.15, "weighted": 1.230},
        "provenance":    {"raw": 4.1,  "weight": 0.30, "weighted": 1.230},
        "trust_history": {"raw": 4.0,  "weight": 0.20, "weighted": 0.800},
        "risk":          {"raw": 3.0,  "weight": 0.25, "weighted": 0.750},  # high = 3.0
        "contradiction": {"raw": 6.0,  "weight": 0.07, "weighted": 0.420},  # 1 conflict = 6.0
        "freshness":     {"raw": 1.0,  "weight": 0.03, "weighted": 0.030},  # >720h = 1.0
    },
    "delegation_score": 4.5,  # Sum of weighted scores
    "authority_state": "ORANGE",
    "highest_dimension": "confidence (8.2) — Agent-reported certainty",
    "lowest_dimension":  "freshness (1.0) — Evidence age: 1128.0 hours",
    "flagged":           "freshness — Dataset 3 is 1128 hours (47 days) old — verify before acting",
    "recommended_action": "Do not proceed. Review evidence packet. Address lowest-scoring dimension before approving."
}

# ── Display Helpers ───────────────────────────────────────────────────────────
def print_separator(char="─", width=60):
    print(char * width)

def print_header(text):
    print_separator("═")
    print(f"  {text}")
    print_separator("═")

def slow_print(text, delay=0.03):
    """Print character by character for dramatic effect on stage."""
    for char in text:
        print(char, end='', flush=True)
        time.sleep(delay)
    print()

def print_score_bar(score, max_score=10, width=30):
    filled = int((score / max_score) * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {score:.1f}/10"

def state_color_label(state):
    symbols = {
        "GREEN":  "🟢 GREEN  — Autonomous execution permitted",
        "YELLOW": "🟡 YELLOW — Human review required",
        "ORANGE": "🟠 ORANGE — PAUSE — Evidence review required",
        "RED":    "🔴 RED    — ABSTAIN — Mandatory escalation"
    }
    return symbols.get(state, state)

# ── Demo Sequences ────────────────────────────────────────────────────────────
def demo_without_aitapp():
    print_header("SCENARIO A — WITHOUT AIiTAPP")
    print()
    print("  Research agent submits recommendation to researcher...")
    print()
    time.sleep(1)
    
    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │  RESEARCH AGENT OUTPUT                              │")
    print("  │                                                     │")
    print("  │  Pattern detected: ARID1B variant cohort            │")
    print("  │  Response rate advantage: +34% vs control           │")
    print("  │  Combined cohort: n=47 (3 institutions)             │")
    print("  │                                                     │")
    print("  │  Agent confidence: 8.2 / 10   ████████░░           │")
    print("  │                                                     │")
    print("  │  ✅ RECOMMENDATION: Consider Protocol X             │")
    print("  │     modification for ARID1B variant patients        │")
    print("  └─────────────────────────────────────────────────────┘")
    print()
    time.sleep(1.5)
    
    print("  Researcher sees: High confidence. Clear recommendation.")
    print("  Researcher does not see:")
    print()
    print("    ✗  Dataset 3 (Mayo Clinic cohort) is 47 days old")
    print("    ✗  Dataset 4 (Johns Hopkins) contradicts this pattern")
    print("         and was excluded from this query")
    print("    ✗  This agent has made 2 incorrect pattern calls")
    print("         in its last 6 research actions")
    print()
    time.sleep(1)
    
    print("  Researcher acts on the recommendation.")
    print("  Protocol modification process begins.")
    print("  The wrong branch has been taken.")
    print()
    print_separator()

def demo_with_aitapp(use_api=True):
    print_header("SCENARIO B — WITH AIiTAPP")
    print()
    print("  Same agent. Same data. Same recommendation.")
    print("  This time the action is submitted to AIiTAPP before")
    print("  it reaches the researcher.")
    print()
    time.sleep(1.5)
    
    print("  Scoring proposed action...")
    print()
    
    if use_api and HAS_REQUESTS:
        result = call_api()
        if result:
            display_api_result(result)
            return
    
    # Offline / fallback display
    display_offline_result()

def call_api():
    """Call the live API and return the result."""
    demo_url = f"{API_URL}/v1/action/score/demo"
    payload = {k: v for k, v in SCENARIO.items() 
               if k not in ["title"] and v is not None}
    
    try:
        print(f"  → POST {demo_url}")
        resp = requests.post(demo_url, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        print(f"  ⚠️  Cannot reach {API_URL}")
        print("  Running with pre-calculated values...")
        print()
        return None
    except Exception as e:
        print(f"  ⚠️  API error: {e}")
        print("  Running with pre-calculated values...")
        print()
        return None

def display_api_result(result):
    score = result["delegation_score"]
    state = result["authority_state"]
    dims = {d["dimension"]: d for d in result["dimensions"]}
    packet = result.get("evidence_packet")
    
    _display_result(score, state, dims, packet)

def display_offline_result():
    """Display pre-calculated result — identical layout to API result."""
    dims = {k: {"raw_input": v["raw"], "weighted_score": v["weighted"]} 
            for k, v in EXPECTED_OUTPUT["dimensions"].items()}
    _display_result(
        EXPECTED_OUTPUT["delegation_score"],
        EXPECTED_OUTPUT["authority_state"],
        dims,
        {
            "highest_dimension": "confidence",
            "highest_score": 8.2,
            "highest_explanation": "Agent-reported certainty",
            "lowest_dimension": "freshness", 
            "lowest_score": 1.0,
            "lowest_explanation": "Evidence age: 1128 hours",
            "flagged_dimension": "freshness",
            "flagged_reason": "Dataset 3 is 1128 hours (47 days) old — verify freshness before acting",
            "recommended_action": "Do not proceed. Review evidence packet. Address lowest-scoring dimension before approving."
        }
    )

def _display_result(score, state, dims, packet):
    print("  AIiTAPP DELEGATION SCORING RESULTS")
    print()
    
    dim_display = [
        ("confidence",    "Confidence      ", dims.get("confidence", {}).get("raw_input", 8.2)),
        ("provenance",    "Provenance      ", dims.get("provenance", {}).get("raw_input", 4.1)),
        ("trust_history", "Trust history   ", dims.get("trust_history", {}).get("raw_input", 4.0)),
        ("risk",          "Risk class      ", dims.get("risk", {}).get("raw_input", 3.0)),
        ("contradiction", "Contradiction   ", dims.get("contradiction", {}).get("raw_input", 6.0)),
        ("freshness",     "Freshness       ", dims.get("freshness", {}).get("raw_input", 1.0)),
    ]
    
    for _, label, raw in dim_display:
        bar = print_score_bar(raw)
        print(f"  {label} {bar}")
        time.sleep(0.4)
    
    print()
    print_separator()
    print()
    
    slow_print(f"  DELEGATION SCORE:  {score}  / 10.0", delay=0.05)
    print()
    slow_print(f"  AUTHORITY STATE:   {state_color_label(state)}", delay=0.04)
    print()
    
    if packet:
        print_separator()
        print()
        print("  EVIDENCE PACKET GENERATED FOR RESEARCHER:")
        print()
        print(f"  ✅ Strongest signal:  {packet['highest_dimension'].upper()} "
              f"({packet['highest_score']:.1f}/10)")
        print(f"     {packet['highest_explanation']}")
        print()
        print(f"  ⚠️  Weakest signal:   {packet['lowest_dimension'].upper()} "
              f"({packet['lowest_score']:.1f}/10)")
        print(f"     {packet['lowest_explanation']}")
        print()
        if packet.get("flagged_dimension"):
            print(f"  🚩 FLAGGED:          {packet['flagged_dimension'].upper()}")
            print(f"     {packet['flagged_reason']}")
            print()
        print_separator()
        print()
        print(f"  RECOMMENDED ACTION:")
        print(f"  {packet['recommended_action']}")
    
    print()
    print_separator()
    print()
    print("  Researcher receives the evidence packet — not the raw recommendation.")
    print("  Researcher requests updated query with fresh Dataset 3.")
    print("  Protocol modification is deferred pending clean evidence.")
    print("  The correct branch is taken.")
    print()

def demo_comparison_close():
    print_header("THE DIFFERENCE")
    print()
    print("  The AI's confidence was 8.2 in both scenarios.")
    print()
    print("  Scenario A — without AIiTAPP:")
    print("    The researcher saw the confidence. Not the evidence quality.")
    print("    The wrong branch was taken.")
    print()
    print("  Scenario B — with AIiTAPP:")
    print("    AIiTAPP scored the evidence, not the confidence.")
    print("    The provenance was weak. The freshness was critical.")
    print("    The researcher never saw the raw recommendation.")
    print("    They saw the evidence gap instead.")
    print()
    print("  ─────────────────────────────────────────────────────")
    print()
    print("  AIiTAPP does not ask: is the AI confident?")
    print("  AIiTAPP asks: is the evidence behind this action")
    print("  good enough to act on?")
    print()
    print("  In rare disease research, where every dataset is small,")
    print("  every pattern is precious, and every wrong branch costs")
    print("  months of trial time — that question is the one that matters.")
    print()
    print_separator("═")
    print("  System running. Provisional patent filed April 2026.")
    print("  Seeking two research institution pilots.")
    print_separator("═")
    print()

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    offline = "--offline" in sys.argv
    
    print()
    print_header("AIiTAPP — MEDICAL CONFERENCE DEMONSTRATION")
    print()
    print("  Delegation Scoring for Federated Research AI Agents")
    print("  Built on Kahneman, Sibony & Sunstein — Noise Theory")
    print()
    print(f"  Scenario: Rare Disease Pattern Recommendation")
    print(f"  Agent:    RarePath Pattern Analyzer v2.1")
    print(f"  Context:  3-institution federated ARID1B variant cohort")
    print()
    
    input("  Press ENTER to begin Scenario A (without AIiTAPP)...")
    print()
    demo_without_aitapp()
    
    print()
    input("  Press ENTER to begin Scenario B (with AIiTAPP)...")
    print()
    demo_with_aitapp(use_api=not offline)
    
    print()
    input("  Press ENTER to see the comparison and close...")
    print()
    demo_comparison_close()
