# AIiTAPP — Lab Pilot Protocol
### Sandbox Specification — v1.1.0 | Confidential | AyenaSelf

---

## What This Sandbox Is

A running REST API that intercepts a proposed AI agent action before it
reaches a researcher and returns a delegation score, authority state, and
evidence quality breakdown. No patient data is required. All scoring is
deterministic and explainable at every dimension.

The sandbox has two independent evaluation layers:

**Layer 1 — Delegation Scoring** (`/v1/action/score`)
Scores a proposed agent action across six dimensions and assigns one of
four authority states: GREEN (proceed) / YELLOW (draft only) /
ORANGE (pause for review) / RED (abstain, escalate).

**Layer 2 — Evidence Integrity** (`/v1/evidence/check`)
Examines the evidence bundle an agent assembled before the scoring engine
sees it. Detects misclassified sources (e.g. interview statements being
used as support evidence), authority gaps, staleness, and contamination.
Returns an integrity gate: PASS / REVIEW / PAUSE / BLOCK.

---

## What the Lab Provides to Call the API

**For delegation scoring — minimum required fields:**

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | string | Your agent's identifier |
| `agent_name` | string | Human-readable name |
| `action_type` | string | read / draft / send / commit / escalate |
| `action_description` | string | Plain English description of proposed action |
| `confidence` | float 0-10 | Agent-reported certainty |
| `provenance_score` | float 0-10 | Evidence traceability score |
| `risk_class` | string | low / medium / high / critical |
| `contradiction_count` | int | Number of conflicting signals the agent detected |
| `evidence_age_hours` | float | Age of oldest evidence source in hours |
| `weight_profile` | string | `medical` for research contexts; `default` otherwise |

**For evidence integrity — additionally required:**

- `internal_lab_evidence`: list of your institution's trusted source objects
- `external_evidence_sources`: list of external sources the agent assembled

Each source requires: `source_id`, `source_type`, `claim_text`, `claim_type`,
`evidence_status`, `provenance_score`, `authority_score`, `evidence_age_hours`,
`replication_status`, `included_in_query`, `intended_use`.

---

## What the Lab Gets Back

**Delegation scoring response includes:**
- `delegation_score` — 0.0 to 10.0 (deterministic, no LLM)
- `authority_state` — GREEN / YELLOW / ORANGE / RED
- `dimensions` — per-dimension breakdown with raw inputs and weighted scores
- `evidence_packet` — for non-GREEN states: highest dimension, weakest dimension, flagged dimension, recommended action
- `propagation_risk` — if downstream agents act on this signal
- `source_trust_discount_applied` — if upstream agent calibration was low

**Evidence integrity response includes:**
- `integrity_gate` — PASS / REVIEW / PAUSE / BLOCK
- `internal_consensus` — baseline strength of internal evidence
- `source_results` — per-source: claim validity state, contamination risk, allowed use, authority gap, block reason
- `conflict_state` — aligned / partial_conflict / conflict / contaminated
- `supervisor_alert` — true if misclassified sources found
- `recommended_action` — specific action for the lab reviewer

---

## Pilot Integration Path

**Week 1 — Synthetic validation**
- Lab runs `demo_medical.py` and `demo_evidence_integrity.py` against sandbox
- Lab calls `/v1/action/score/demo` with synthetic scenarios matching their agent types
- Confirm output matches expected authority states and evidence packets

**Week 2 — Live agent integration**
- Lab wraps one existing research agent with a pre-execution call to `/v1/action/score`
- Action proceeds only if `authority_state == "GREEN"` or researcher approves lower state
- All scored actions logged with `session_id` for audit trail

**Week 3 — Evidence integrity layer**
- Lab adds pre-scoring call to `/v1/evidence/check` for evidence bundles before they reach the scoring engine
- Blocked bundles are returned to the agent for reclassification

**Week 4-6 — Calibration loop (optional)**
- Lab logs outcomes of acted-upon recommendations
- Outcome scores feed `trust_history_score` in subsequent scoring calls
- Agent calibration improves with use

---

## Data and Privacy

- The API scores evidence metadata — not patient data
- No PII is required or expected in any field
- The API does not store submitted payloads in the pilot sandbox
- HIPAA-appropriate audit logging is a Week 2 deliverable for any
  healthcare-adjacent integration requiring a full event trail

---

## Authentication

Demo endpoints (`/demo` suffix) require no API key — use for initial
integration and demonstration.

Authenticated endpoints require `X-API-Key` header. Contact
gary@ayenaself.com for a pilot API key.

---

## Contact

Gary Pearl | Founder, AyenaSelf
gary@ayenaself.com
Provisional patent filed April 2026 — DLA Piper LLP
Claims: Multi-factor delegation scoring, outcome recalibration,
inter-agent trust discounting, propagation risk calculation
