# AIiTAPP — Delegation Scoring API
### Lab Pilot Sandbox — v1.1.0

Pre-execution scoring layer for AI research agents. Intercepts a proposed
agent action before it reaches a researcher and scores the evidence behind
it across six dimensions. Returns a delegation score, authority state, and
a human insertion packet specifying the weakest evidence dimension.

---

## Quick Start (Local)

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
uvicorn main:app --reload
```

Server runs at: http://127.0.0.1:8000
Interactive API docs: http://127.0.0.1:8000/docs

---

## Run the Demos

Both demos work with the local server or fully offline.

**Medical scenario demo** (delegation scoring — rare disease pattern recommendation):
```bash
python demo_medical.py              # calls local server
python demo_medical.py --offline    # pre-calculated values, no server needed
```
Expected output: delegation_score ~4.5, authority_state ORANGE

**Evidence integrity demo** (contamination detection — misclassified sources):
```bash
python demo_evidence_integrity.py              # calls local server
python demo_evidence_integrity.py --offline    # pre-calculated values, no server needed
```
Expected output: integrity_gate BLOCK, supervisor_alert true

---

## Validate a Deployment

```bash
python validate.py
```

Hits /health, /v1/action/score/demo, and /v1/evidence/check/demo.
Prints PASS or FAIL for each endpoint with the key output values.

---

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health | None | Health check |
| GET / | None | API overview |
| GET | /docs | None | Interactive Swagger docs |
| POST | /v1/action/score | API key | Score a proposed agent action |
| POST | /v1/action/score/demo | None | Score — no key required (demo use only) |
| POST | /v1/evidence/check | API key | Validate an evidence bundle |
| POST | /v1/evidence/check/demo | None | Evidence check — no key required (demo use only) |

See `curl_examples.txt` for formatted request examples.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AITAPP_API_KEY` | `dev-key-change-in-production` | Required for authenticated endpoints |
| `AITAPP_API_URL` | `http://127.0.0.1:8000` | Base URL used by demo scripts and validate.py |

Copy `.env.example` to `.env` and set values before running.
Export before running demos:
```bash
export AITAPP_API_KEY=your-key
export AITAPP_API_URL=https://your-deployed-url
```

---

## Deploy to Railway or Render

See `DEPLOY.md` for step-by-step instructions.

---

## Scoring Formula (Medical Weight Profile)

```
S = (C x 0.15) + (P x 0.30) + (T x 0.20) + (R x 0.25) + (N x 0.07) + (F x 0.03)
```

| Dimension | Input |
|-----------|-------|
| C Confidence | Agent-reported certainty 0-10 |
| P Provenance | Evidence traceability and source quality 0-10 |
| T Trust History | Agent calibration from prior outcomes 0-10 |
| R Risk | Inverted from risk class: critical=1.0 / high=3.0 / medium=5.0 / low=8.0 |
| N Contradiction | Inverted from conflict count: 0=9.0 / 1=6.0 / 2=3.0 / 3+=1.0 |
| F Freshness | Age of oldest evidence: <1h=9.0 / <24h=7.0 / <168h=5.0 / <720h=3.0 / 720h+=1.0 |

**Authority states:** GREEN >=7.5 / YELLOW 5.5-7.4 / ORANGE 3.5-5.4 / RED <3.5

---

## Pilot Contact

Gary Pearl | Founder, AyenaSelf
gary@ayenaself.com
Provisional patent filed April 2026 — DLA Piper LLP
