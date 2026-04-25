"""
AIiTAPP — Delegation Scoring API
Version: 1.0.0
Deploy to: Railway or Render (see DEPLOY.md for exact steps)

This is the server-side implementation of the six-factor delegation
scoring engine from DelegationScoringEngine.swift, translated to Python.
All weights, thresholds, and state logic match the iOS implementation exactly.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import os
import math

from evidence_integrity import (
    EvidenceIntegrityRequest,
    EvidenceIntegrityResponse,
    evaluate_evidence_integrity,
)

app = FastAPI(
    title="AIiTAPP Delegation Scoring API",
    description="Pre-execution confidence gating and evidence integrity validation for AI agent actions",
    version="1.1.0"
)

# ── API Key Auth ──────────────────────────────────────────────────────────────
API_KEY = os.environ.get("AITAPP_API_KEY", "dev-key-change-in-production")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(key: str = Depends(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return key

# ── Enums (matching Swift exactly) ───────────────────────────────────────────
RISK_SCORES = {
    "low": 8.0,
    "medium": 5.0,
    "high": 3.0,
    "critical": 1.0
}

CONTRADICTION_SCORES = {
    0: 9.0,
    1: 6.0,
    2: 3.0
}

def freshness_score(evidence_age_hours: float) -> float:
    if evidence_age_hours < 1:
        return 9.0
    elif evidence_age_hours < 24:
        return 7.0
    elif evidence_age_hours < 168:   # 7 days
        return 5.0
    elif evidence_age_hours < 720:   # 30 days
        return 3.0
    else:
        return 1.0

def contradiction_score(conflict_count: int) -> float:
    if conflict_count >= 3:
        return 1.0
    return CONTRADICTION_SCORES.get(conflict_count, 1.0)

def authority_state(score: float) -> str:
    if score >= 7.5:
        return "GREEN"
    elif score >= 5.5:
        return "YELLOW"
    elif score >= 3.5:
        return "ORANGE"
    else:
        return "RED"

def authority_description(state: str) -> str:
    descriptions = {
        "GREEN":  "Autonomous execution within policy — human observes only",
        "YELLOW": "Draft only / no commit / no send — quick human review required",
        "ORANGE": "Pause — evidence packet generated — decision maker must act before agent proceeds",
        "RED":    "Abstain or escalate — mandatory human approval — agent cannot proceed"
    }
    return descriptions.get(state, "Unknown state")

# ── Scoring Weights ───────────────────────────────────────────────────────────
# Default weights — can be overridden per deployment context
DEFAULT_WEIGHTS = {
    "confidence":    0.25,
    "provenance":    0.20,
    "trust_history": 0.20,
    "risk":          0.20,
    "contradiction": 0.10,
    "freshness":     0.05
}

# Medical/research context weights — elevated provenance and risk
MEDICAL_WEIGHTS = {
    "confidence":    0.15,
    "provenance":    0.30,   # Elevated — source quality critical in research
    "trust_history": 0.20,
    "risk":          0.25,   # Elevated — patient data actions are critical risk
    "contradiction": 0.07,
    "freshness":     0.03
}

WEIGHT_PROFILES = {
    "default": DEFAULT_WEIGHTS,
    "medical": MEDICAL_WEIGHTS
}

# ── Request / Response Models ─────────────────────────────────────────────────
class AgentActionRequest(BaseModel):
    # Required fields
    agent_id: str = Field(..., description="Unique identifier for the agent")
    agent_name: str = Field(..., description="Human-readable agent name")
    action_type: str = Field(..., description="Type: read, draft, send, commit, escalate")
    action_description: str = Field(..., description="Plain English description of proposed action")
    
    # Scoring inputs
    confidence: float = Field(..., ge=0, le=10, description="Agent-reported certainty 0-10")
    provenance_score: float = Field(..., ge=0, le=10, description="Evidence traceability 0-10")
    trust_history_score: float = Field(5.0, ge=0, le=10, description="Agent calibration from prior outcomes 0-10")
    risk_class: str = Field(..., description="low / medium / high / critical")
    contradiction_count: int = Field(0, ge=0, description="Number of conflicting signals detected")
    evidence_age_hours: float = Field(..., ge=0, description="Age of oldest evidence source in hours")
    
    # Optional — for agent-to-agent scenarios
    source_agent_id: Optional[str] = Field(None, description="Upstream agent ID if action comes from agent chain")
    source_agent_calibration: Optional[float] = Field(None, ge=0, le=10, description="Upstream agent calibration score")
    downstream_action_count: Optional[int] = Field(0, description="Number of downstream agents that will act on this signal")
    
    # Context
    weight_profile: str = Field("default", description="Scoring weight profile: default / medical")
    principal_id: Optional[str] = Field(None, description="ID of the human principal this agent acts for")
    session_id: Optional[str] = Field(None, description="Optional session identifier for audit grouping")

class DimensionScore(BaseModel):
    dimension: str
    raw_input: float
    weighted_score: float
    weight: float
    label: str

class EvidencePacket(BaseModel):
    highest_dimension: str
    highest_score: float
    highest_explanation: str
    lowest_dimension: str
    lowest_score: float
    lowest_explanation: str
    flagged_dimension: Optional[str]
    flagged_reason: Optional[str]
    recommended_action: str

class PropagationRisk(BaseModel):
    score: float
    authority_weight: int
    downstream_action_count: int
    source_calibration: float
    interpretation: str

class AgentActionResponse(BaseModel):
    # Core output
    delegation_score: float
    authority_state: str
    authority_description: str
    
    # Dimension breakdown
    dimensions: List[DimensionScore]
    
    # Human insertion packet (generated when state is YELLOW, ORANGE, or RED)
    evidence_packet: Optional[EvidencePacket]
    
    # Agent-to-agent
    source_trust_discount_applied: bool
    propagation_risk: Optional[PropagationRisk]
    
    # Metadata
    scored_at: str
    weight_profile: str
    agent_id: str
    action_type: str

# ── Authority weights for propagation risk ────────────────────────────────────
AUTHORITY_WEIGHTS = {
    "read": 1,
    "draft": 3,
    "send": 6,
    "commit": 8,
    "escalate": 10
}

# ── Core Scoring Engine ───────────────────────────────────────────────────────
def compute_delegation_score(req: AgentActionRequest) -> AgentActionResponse:
    weights = WEIGHT_PROFILES.get(req.weight_profile, DEFAULT_WEIGHTS)
    
    # Compute raw dimension scores
    r_score = RISK_SCORES.get(req.risk_class.lower(), 5.0)
    n_score = contradiction_score(req.contradiction_count)
    f_score = freshness_score(req.evidence_age_hours)
    
    # Apply inter-agent trust discount to provenance if upstream agent is low-calibration
    provenance = req.provenance_score
    source_discount_applied = False
    if req.source_agent_calibration is not None and req.source_agent_calibration < 5.0:
        discount = (5.0 - req.source_agent_calibration) * 0.4
        provenance = max(1.0, provenance - discount)
        source_discount_applied = True
    
    # Compute weighted scores
    raw_scores = {
        "confidence":    req.confidence,
        "provenance":    provenance,
        "trust_history": req.trust_history_score,
        "risk":          r_score,
        "contradiction": n_score,
        "freshness":     f_score
    }
    
    weighted = {k: v * weights[k] for k, v in raw_scores.items()}
    total = round(sum(weighted.values()), 1)
    total = max(0.0, min(10.0, total))  # Clamp to 0-10
    
    state = authority_state(total)
    
    # Build dimension list
    dim_labels = {
        "confidence":    "Agent-reported certainty",
        "provenance":    "Evidence traceability and source quality",
        "trust_history": "Agent calibration from prior outcomes",
        "risk":          f"Risk class: {req.risk_class}",
        "contradiction": f"Contradiction count: {req.contradiction_count}",
        "freshness":     f"Evidence age: {req.evidence_age_hours:.1f} hours"
    }
    
    dimensions = [
        DimensionScore(
            dimension=k,
            raw_input=raw_scores[k],
            weighted_score=round(weighted[k], 3),
            weight=weights[k],
            label=dim_labels[k]
        )
        for k in ["confidence", "provenance", "trust_history", "risk", "contradiction", "freshness"]
    ]
    
    # Build evidence packet for non-GREEN states
    evidence_packet = None
    if state != "GREEN":
        sorted_dims = sorted(dimensions, key=lambda d: d.raw_input, reverse=True)
        highest = sorted_dims[0]
        lowest = sorted_dims[-1]
        
        # Find flagged dimension (contradiction or freshness below 4.0)
        flagged = None
        flagged_reason = None
        for d in dimensions:
            if d.dimension in ("contradiction", "freshness") and d.raw_input < 4.0:
                flagged = d.dimension
                if d.dimension == "contradiction":
                    flagged_reason = f"{req.contradiction_count} conflicting signals detected — resolve before proceeding"
                else:
                    flagged_reason = f"Oldest evidence source is {req.evidence_age_hours:.0f} hours old — verify freshness"
                break
        
        recommended_actions = {
            "YELLOW": "Review proposed action and approve or reject before agent proceeds",
            "ORANGE": "Do not proceed. Review evidence packet. Address lowest-scoring dimension before approving.",
            "RED":    "Mandatory escalation. Agent cannot proceed. Human decision required."
        }
        
        evidence_packet = EvidencePacket(
            highest_dimension=highest.dimension,
            highest_score=highest.raw_input,
            highest_explanation=highest.label,
            lowest_dimension=lowest.dimension,
            lowest_score=lowest.raw_input,
            lowest_explanation=lowest.label,
            flagged_dimension=flagged,
            flagged_reason=flagged_reason,
            recommended_action=recommended_actions.get(state, "Review required")
        )
    
    # Propagation risk
    prop_risk = None
    if req.downstream_action_count and req.downstream_action_count > 0:
        auth_weight = AUTHORITY_WEIGHTS.get(req.action_type.lower(), 3)
        source_cal = req.source_agent_calibration if req.source_agent_calibration is not None else 7.0
        pr = (auth_weight * req.downstream_action_count * (10 - source_cal)) / 10
        pr = min(10.0, round(pr, 1))
        
        if pr >= 7.0:
            interp = "HIGH — acting on this signal will cascade into high-authority downstream actions"
        elif pr >= 4.0:
            interp = "MEDIUM — downstream impact is significant, review upstream source quality"
        else:
            interp = "LOW — downstream propagation risk is manageable"
        
        prop_risk = PropagationRisk(
            score=pr,
            authority_weight=auth_weight,
            downstream_action_count=req.downstream_action_count,
            source_calibration=source_cal,
            interpretation=interp
        )
    
    return AgentActionResponse(
        delegation_score=total,
        authority_state=state,
        authority_description=authority_description(state),
        dimensions=dimensions,
        evidence_packet=evidence_packet,
        source_trust_discount_applied=source_discount_applied,
        propagation_risk=prop_risk,
        scored_at=datetime.utcnow().isoformat() + "Z",
        weight_profile=req.weight_profile,
        agent_id=req.agent_id,
        action_type=req.action_type
    )

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "product": "AIiTAPP Delegation Scoring API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "score": "POST /v1/action/score",
            "health": "GET /health",
            "docs": "GET /docs"
        }
    }

@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat() + "Z"}

@app.post("/v1/action/score", response_model=AgentActionResponse)
def score_action(req: AgentActionRequest, _: str = Depends(verify_api_key)):
    """
    Score a proposed agent action and return a delegation score,
    authority state, and human insertion packet if review is required.
    """
    return compute_delegation_score(req)

@app.post("/v1/action/score/demo")
def score_demo(req: AgentActionRequest):
    """
    Demo endpoint — no API key required.
    Use this for conference demonstrations only.
    Remove or disable in production.
    """
    return compute_delegation_score(req)


# ── Evidence Integrity Routes ─────────────────────────────────────────────────
@app.post("/v1/evidence/check", response_model=EvidenceIntegrityResponse)
def check_evidence(req: EvidenceIntegrityRequest, _: str = Depends(verify_api_key)):
    """
    Validate an evidence bundle before it reaches the delegation scoring engine.
    Compares internal lab evidence against external sources, classifies each source
    by claim type, and returns an integrity gate: PASS, REVIEW, PAUSE, or BLOCK.
    """
    return evaluate_evidence_integrity(req)


@app.post("/v1/evidence/check/demo")
def check_evidence_demo(req: EvidenceIntegrityRequest):
    """
    Demo endpoint — no API key required.
    Use this for conference demonstrations only.
    Remove or disable in production.
    """
    return evaluate_evidence_integrity(req)
