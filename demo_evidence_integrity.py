"""
AIiTAPP — Evidence Integrity and Conflict Layer Demo
Synthetic Rare Disease Research Scenario

This script demonstrates what happens BEFORE delegation scoring runs —
the evidence bundle itself is examined for contamination, misclassification,
and authority gaps.

Scenario:
  - RarePath Core Lab has two current, trusted, replicated internal studies
  - An external preprint is provisional and 35 days old — being used as support
  - An external commentary is being treated as support evidence
  - A researcher interview statement is being treated as support evidence (the trap)

The system detects contamination and returns BLOCK with a supervisor alert.

No patient data is used. All sources are fictional.

Usage:
    python demo_evidence_integrity.py              # Run full demo (calls local API)
    python demo_evidence_integrity.py --offline    # Pre-calculated values (no API needed)
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

# ── The Scenario ──────────────────────────────────────────────────────────────
# This evidence bundle is what a research agent has assembled to support a
# protocol modification recommendation. It looks complete on the surface.
# The evidence integrity layer finds the contamination the agent missed.

SCENARIO = {
    "agent_id":          "research-agent-rp-001",
    "agent_name":        "RarePath Pattern Analyzer v2.1",
    "action_description": (
        "Surface clinical pattern to lead researcher: ARID1B variant patients "
        "show 34% higher response rate to Protocol X. Recommend consideration "
        "for protocol modification."
    ),
    "weight_profile": "medical",

    "internal_lab_evidence": [
        {
            "source_id":          "internal-rp-core-001",
            "source_type":        "lab_study",
            "claim_text":         (
                "ARID1B variant patients show 34% higher response to Protocol X "
                "(n=120, three-site replication confirmed, p<0.001)"
            ),
            "claim_type":         "validated_fact",
            "evidence_status":    "published",
            "provenance_score":   8.5,
            "authority_score":    8.7,
            "evidence_age_hours": 48.0,
            "replication_status": "replicated",
            "sample_size":        120,
            "included_in_query":  True,
            "intended_use":       "support",
            "source_origin_lab":  "RarePath Core Laboratory"
        },
        {
            "source_id":          "internal-rp-core-002",
            "source_type":        "meta_analysis",
            "claim_text":         (
                "Cross-cohort protocol response analysis confirms ARID1B variant "
                "correlation at p<0.01 across combined n=205"
            ),
            "claim_type":         "validated_fact",
            "evidence_status":    "published",
            "provenance_score":   8.0,
            "authority_score":    8.2,
            "evidence_age_hours": 72.0,
            "replication_status": "replicated",
            "sample_size":        205,
            "included_in_query":  True,
            "intended_use":       "support",
            "source_origin_lab":  "RarePath Core Laboratory"
        }
    ],

    "external_evidence_sources": [
        {
            # Older provisional preprint — being used as support
            "source_id":          "ext-mayo-preprint-001",
            "source_type":        "preprint",
            "claim_text":         (
                "Preliminary analysis suggests ARID1B response pattern "
                "in n=23 pilot cohort (not peer reviewed)"
            ),
            "claim_type":         "provisional_finding",
            "evidence_status":    "preprint",
            "provenance_score":   5.2,
            "authority_score":    4.8,
            "evidence_age_hours": 840.0,    # 35 days old
            "replication_status": "partial",
            "sample_size":        23,
            "included_in_query":  True,
            "intended_use":       "support",   # declared support — will be downgraded
            "source_origin_lab":  "Mayo External Consortium"
        },
        {
            # Editorial commentary used as support — contamination risk HIGH
            "source_id":          "ext-commentary-001",
            "source_type":        "commentary",
            "claim_text":         (
                "The ARID1B–Protocol X relationship appears consistent with "
                "existing literature patterns"
            ),
            "claim_type":         "commentary_opinion",
            "evidence_status":    "published",
            "provenance_score":   3.5,
            "authority_score":    4.2,
            "evidence_age_hours": 2190.0,   # 91 days old
            "replication_status": "not_replicated",
            "sample_size":        None,
            "included_in_query":  True,
            "intended_use":       "support",   # commentary as support — WRONG
            "source_origin_lab":  "External Review Panel"
        },
        {
            # Researcher interview statement used as support — THE TRAP
            # An agent surfaced this as supporting evidence because the researcher
            # expressed high confidence. Confidence is not evidence.
            "source_id":          "ext-interview-dr-chen",
            "source_type":        "interview",
            "claim_text":         (
                "Dr. Chen (lead researcher) believes the Protocol X benefit is "
                "likely stronger in younger ARID1B patients based on clinical intuition"
            ),
            "claim_type":         "interview_supposition",
            "evidence_status":    "informal",
            "provenance_score":   1.5,
            "authority_score":    2.0,
            "evidence_age_hours": 6.0,
            "replication_status": "not_replicated",
            "sample_size":        None,
            "included_in_query":  True,
            "intended_use":       "support",   # interview as support — BLOCKED
            "source_origin_lab":  "Dr. Chen Clinical Interview"
        }
    ]
}

# ── Pre-calculated expected output (for offline mode or verification) ─────────
# Internal consensus: avg_authority=8.45, avg_provenance=8.25, avg_age=60.0h
#
# ext-mayo-preprint-001:
#   authority_gap=3.65, freshness_gap=780h, claim_validity=provisional
#   contamination: risk_score=1 (freshness flag only) → LOW
#   allowed_use: comparison_only (provisional_finding + intended=support → Rule 3)
#
# ext-commentary-001:
#   authority_gap=4.25, freshness_gap=2130h, claim_validity=MISCLASSIFIED
#   contamination: +4(high-risk+support) +2(high-risk+in-query)
#                  +2(auth_gap>=4) +1(freshness) +1(not_rep+support) = 10 → CRITICAL
#   allowed_use: BLOCKED
#
# ext-interview-dr-chen:
#   authority_gap=6.45, freshness_gap=-54h, claim_validity=MISCLASSIFIED
#   contamination: +4(high-risk+support) +2(high-risk+in-query)
#                  +2(auth_gap>=4) +0(freshness<720) +1(not_rep+support) = 9 → CRITICAL
#   allowed_use: BLOCKED
#
# misclassified_count=2 → conflict_state=contaminated → integrity_gate=BLOCK
# supervisor_alert=True

EXPECTED_OUTPUT = {
    "internal_consensus": {
        "source_count":             2,
        "avg_provenance":           8.25,
        "avg_authority":            8.45,
        "avg_age_hours":            60.0,
        "internal_conflict":        False,
        "consensus_strength":       "strong"
    },
    "source_results": [
        {
            "source_id":            "ext-mayo-preprint-001",
            "claim_validity_state": "provisional",
            "contamination_risk":   "low",
            "allowed_use":          "comparison_only",
            "authority_gap":         3.65,
            "freshness_gap":         780.0
        },
        {
            "source_id":            "ext-commentary-001",
            "claim_validity_state": "misclassified",
            "contamination_risk":   "critical",
            "allowed_use":          "blocked",
            "authority_gap":         4.25,
            "freshness_gap":         2130.0
        },
        {
            "source_id":            "ext-interview-dr-chen",
            "claim_validity_state": "misclassified",
            "contamination_risk":   "critical",
            "allowed_use":          "blocked",
            "authority_gap":         6.45,
            "freshness_gap":         -54.0
        }
    ],
    "conflict_state":               "contaminated",
    "overall_contamination_risk":   "critical",
    "integrity_gate":               "BLOCK",
    "supervisor_alert":             True,
    "supervisor_alert_reason": (
        "2 source(s) are misclassified as support evidence. "
        "Interview statements, opinion pieces, and hypothesis material are "
        "positioned to directly influence a downstream recommendation. "
        "Supervisor review is required before this evidence set proceeds."
    ),
    "recommended_action": (
        "BLOCK — Evidence set cannot proceed. Remove or reclassify misclassified "
        "sources. Supervisor review required before this evidence bundle reaches "
        "the recommendation engine."
    )
}


# ── Display Helpers ───────────────────────────────────────────────────────────
def print_separator(char="─", width=62):
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

def print_score_bar(score, max_score=10, width=28):
    filled = int((score / max_score) * width)
    bar    = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {score:.1f}/10"

def gate_label(gate):
    symbols = {
        "PASS":   "✅ PASS   — Evidence integrity confirmed",
        "REVIEW": "🔍 REVIEW — Human validation recommended",
        "PAUSE":  "⏸  PAUSE  — Conflict must be resolved",
        "BLOCK":  "🚫 BLOCK  — Contaminated — do not proceed"
    }
    return symbols.get(gate, gate)

def risk_label(risk):
    symbols = {
        "none":     "  none",
        "low":      "🟡 low",
        "medium":   "🟠 medium",
        "high":     "🔴 high",
        "critical": "🔴 CRITICAL"
    }
    return symbols.get(risk, risk)

def use_label(use):
    symbols = {
        "support":          "✅ support",
        "comparison_only":  "🔍 comparison only",
        "background_only":  "📋 background only",
        "blocked":          "🚫 BLOCKED"
    }
    return symbols.get(use, use)


# ── Demo Sequences ────────────────────────────────────────────────────────────
def demo_without_integrity_layer():
    print_header("SCENARIO A — WITHOUT EVIDENCE INTEGRITY LAYER")
    print()
    print("  Research agent assembles evidence bundle for pattern recommendation.")
    print("  No evidence validation is run.")
    print("  The bundle is submitted directly to the researcher.")
    print()
    time.sleep(1)

    print("  ┌─────────────────────────────────────────────────────────┐")
    print("  │  AGENT EVIDENCE BUNDLE — AS SUBMITTED                  │")
    print("  │                                                         │")
    print("  │  Source 1: RarePath Core Study (internal)               │")
    print("  │            Validated fact — n=120 — replicated          │")
    print("  │            Authority: 8.7 / 10    ████████░░            │")
    print("  │                                                         │")
    print("  │  Source 2: RarePath Meta-Analysis (internal)            │")
    print("  │            Validated fact — n=205 — replicated          │")
    print("  │            Authority: 8.2 / 10    ████████░░            │")
    print("  │                                                         │")
    print("  │  Source 3: Mayo Preprint (external)                     │")
    print("  │            Preliminary — n=23 — 35 days old             │")
    print("  │            Authority: 4.8 / 10    ████░░░░░░   ← weak   │")
    print("  │                                                         │")
    print("  │  Source 4: External Commentary                          │")
    print("  │            'Pattern appears consistent with             │")
    print("  │             existing literature' — editorial            │")
    print("  │            Authority: 4.2 / 10    ████░░░░░░   ← weak   │")
    print("  │                                                         │")
    print("  │  Source 5: Dr. Chen Interview                           │")
    print("  │            'I believe the benefit is likely stronger    │")
    print("  │             in younger patients — clinical intuition'   │")
    print("  │            Captured 6 hours ago  ← very recent         │")
    print("  │                                                         │")
    print("  │  ✅ RECOMMENDATION: Consider Protocol X modification    │")
    print("  └─────────────────────────────────────────────────────────┘")
    print()
    time.sleep(1.5)

    print("  The researcher sees: five sources. Two strong. Three supporting.")
    print("  The bundle looks complete.")
    print()
    print("  The researcher does not see:")
    print()
    print("    ✗  Source 3 (Mayo preprint) is provisional and 35 days old.")
    print("         It cannot be primary support evidence.")
    print()
    print("    ✗  Source 4 (commentary) is editorial opinion, not research.")
    print("         It has no sample size. It is being treated as support evidence.")
    print()
    print("    ✗  Source 5 (Dr. Chen interview) is clinical intuition.")
    print("         An interview statement is not replicable evidence.")
    print("         It is being treated as support evidence.")
    print()
    time.sleep(1)

    print("  Researcher receives the recommendation.")
    print("  Protocol modification process begins.")
    print("  The evidence foundation is contaminated.")
    print()
    print_separator()


def demo_with_integrity_layer(use_api=True):
    print_header("SCENARIO B — WITH EVIDENCE INTEGRITY LAYER")
    print()
    print("  Same agent. Same evidence bundle. Same recommendation.")
    print("  This time the bundle is submitted to the Evidence Integrity")
    print("  Layer before it reaches the researcher.")
    print()
    time.sleep(1.5)

    print("  Evaluating evidence bundle...")
    print()

    if use_api and HAS_REQUESTS:
        result = call_api()
        if result:
            display_api_result(result)
            return

    display_offline_result()


def call_api():
    """Call the live API and return the result."""
    demo_url = f"{API_URL}/v1/evidence/check/demo"
    payload  = SCENARIO.copy()

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
    ic      = result["internal_consensus"]
    sources = {r["source_id"]: r for r in result["source_results"]}
    _display_result(
        gate=result["integrity_gate"],
        conflict_state=result["conflict_state"],
        overall_contamination=result["overall_contamination_risk"],
        supervisor_alert=result["supervisor_alert"],
        supervisor_reason=result.get("supervisor_alert_reason"),
        recommended_action=result["recommended_action"],
        internal_consensus=ic,
        sources=sources
    )


def display_offline_result():
    """Display pre-calculated result — identical layout to live API result."""
    ic      = EXPECTED_OUTPUT["internal_consensus"]
    sources = {r["source_id"]: r for r in EXPECTED_OUTPUT["source_results"]}
    _display_result(
        gate=EXPECTED_OUTPUT["integrity_gate"],
        conflict_state=EXPECTED_OUTPUT["conflict_state"],
        overall_contamination=EXPECTED_OUTPUT["overall_contamination_risk"],
        supervisor_alert=EXPECTED_OUTPUT["supervisor_alert"],
        supervisor_reason=EXPECTED_OUTPUT["supervisor_alert_reason"],
        recommended_action=EXPECTED_OUTPUT["recommended_action"],
        internal_consensus=ic,
        sources=sources
    )


def _display_result(gate, conflict_state, overall_contamination,
                    supervisor_alert, supervisor_reason, recommended_action,
                    internal_consensus, sources):

    # Internal consensus
    print("  INTERNAL EVIDENCE BASELINE")
    print()
    ic_auth = internal_consensus.get("avg_authority", 8.45)
    ic_prov = internal_consensus.get("avg_provenance", 8.25)
    strength = internal_consensus.get("consensus_strength", "strong")
    print(f"  Internal authority  {print_score_bar(ic_auth)}")
    print(f"  Internal provenance {print_score_bar(ic_prov)}")
    print(f"  Consensus strength: {strength.upper()}")
    print()
    print_separator()
    print()

    # Per-source evaluation
    print("  EXTERNAL SOURCE EVALUATION")
    print()

    source_display = [
        (
            "ext-mayo-preprint-001",
            "Mayo Preprint (provisional, 35d old)",
            4.8
        ),
        (
            "ext-commentary-001",
            "External Commentary (editorial opinion)",
            4.2
        ),
        (
            "ext-interview-dr-chen",
            "Dr. Chen Interview (clinical intuition)",
            2.0
        ),
    ]

    for sid, label, authority in source_display:
        r = sources.get(sid, {})
        validity   = r.get("claim_validity_state", "—").upper()
        cont_risk  = r.get("contamination_risk",   "—")
        allowed    = r.get("allowed_use",           "—")
        auth_gap   = r.get("authority_gap",          0.0)

        print(f"  {label}")
        print(f"  Authority {print_score_bar(authority)}")
        print(f"  Claim validity:       {validity}")
        print(f"  Contamination risk:   {risk_label(cont_risk)}")
        print(f"  Authority gap:        {auth_gap:.2f} points below internal baseline")
        print(f"  Allowed use:          {use_label(allowed)}")
        print()
        time.sleep(0.6)

    print_separator()
    print()

    # Overall result
    slow_print(f"  CONFLICT STATE:            {conflict_state.upper().replace('_', ' ')}", delay=0.04)
    slow_print(f"  OVERALL CONTAMINATION:     {overall_contamination.upper()}", delay=0.04)
    print()
    slow_print(f"  INTEGRITY GATE:  {gate_label(gate)}", delay=0.05)
    print()

    if supervisor_alert and supervisor_reason:
        print_separator()
        print()
        print("  ⚠️  SUPERVISOR ALERT")
        print()
        # Word-wrap the reason at 56 chars for clean terminal display
        words = supervisor_reason.split()
        line  = "  "
        for word in words:
            if len(line) + len(word) + 1 > 60:
                print(line)
                line = "  " + word
            else:
                line = line + " " + word if line != "  " else "  " + word
        if line.strip():
            print(line)
        print()

    print_separator()
    print()
    print("  RECOMMENDED ACTION:")
    print()
    words = recommended_action.split()
    line  = "  "
    for word in words:
        if len(line) + len(word) + 1 > 60:
            print(line)
            line = "  " + word
        else:
            line = line + " " + word if line != "  " else "  " + word
    if line.strip():
        print(line)
    print()
    print_separator()
    print()
    print("  The evidence bundle does not reach the researcher.")
    print("  The contaminated sources are flagged for reclassification.")
    print("  The recommendation is paused until clean evidence is assembled.")
    print()


def demo_comparison_close():
    print_header("THE DIFFERENCE")
    print()
    print("  The agent's confidence was the same in both scenarios.")
    print("  The evidence bundle was identical in both scenarios.")
    print()
    print("  Scenario A — without Evidence Integrity Layer:")
    print("    The researcher received five sources.")
    print("    Two were strong. Three contaminated the bundle.")
    print("    A protocol modification was initiated on a flawed foundation.")
    print()
    print("  Scenario B — with Evidence Integrity Layer:")
    print("    The bundle was examined before it reached anyone.")
    print("    The preprint was downgraded to comparison-only.")
    print("    The commentary was blocked — editorial opinion is not evidence.")
    print("    The interview statement was blocked — intuition is not evidence.")
    print("    A supervisor alert was triggered.")
    print("    The recommendation never reached the researcher.")
    print()
    print("  ─────────────────────────────────────────────────────────")
    print()
    print("  The agent did not fabricate anything.")
    print("  The researcher would have acted in good faith.")
    print("  The contamination was already in the evidence bundle —")
    print("  assembled legitimately from real sources.")
    print()
    print("  AIiTAPP does not ask: did the agent lie?")
    print("  AIiTAPP asks: is the evidence behind this action")
    print("  the right type of evidence to act on?")
    print()
    print("  In rare disease research, where expert opinion sounds like")
    print("  data, and a single interview can anchor a recommendation,")
    print("  that question is the one that matters.")
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
    print_header("AIiTAPP — EVIDENCE INTEGRITY LAYER DEMONSTRATION")
    print()
    print("  Evidence Contamination Detection for Federated Research AI")
    print("  Built on Kahneman, Sibony & Sunstein — Noise Theory")
    print()
    print("  Scenario: Rare Disease Protocol Modification Recommendation")
    print("  Agent:    RarePath Pattern Analyzer v2.1")
    print("  Context:  ARID1B variant cohort — Protocol X response pattern")
    print()

    input("  Press ENTER to begin Scenario A (without Evidence Integrity Layer)...")
    print()
    demo_without_integrity_layer()

    print()
    input("  Press ENTER to begin Scenario B (with Evidence Integrity Layer)...")
    print()
    demo_with_integrity_layer(use_api=not offline)

    print()
    input("  Press ENTER to see the comparison and close...")
    print()
    demo_comparison_close()
