"""
AIiTAPP — Evidence Integrity and Conflict Layer
Version: 1.0.0

Pre-recommendation evidence validation layer.

Before a scored action can proceed, this layer compares trusted internal lab
evidence against external sources, classifies each source by claim type, and
determines whether the evidence bundle is safe to act on or must be paused,
reviewed, or blocked.

Claim Types Recognized
──────────────────────
  validated_fact           Published, replicated, high-authority finding
  provisional_finding      Preliminary result — comparison use only
  hypothesis               Untested conjecture — not for support use
  interview_supposition    Researcher statement — not for support use
  commentary_opinion       Editorial or expert opinion — not for support use
  stale_research           Evidence beyond usable age threshold
  contradictory_unresolved Conflicting evidence without resolution
  comparison_only          Explicitly flagged comparison-only material

Integrity Gate States
─────────────────────
  PASS    Evidence integrity confirmed — proceed to delegation scoring
  REVIEW  Partial conflicts detected — human should validate before proceeding
  PAUSE   Conflict detected — must be resolved before agent proceeds
  BLOCK   Contaminated evidence bundle — supervisor review required
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# ── Claim type sets ───────────────────────────────────────────────────────────
# These claim types must never be used as primary support evidence
HIGH_RISK_CLAIM_TYPES = {
    "interview_supposition",
    "commentary_opinion",
    "hypothesis",
    "contradictory_unresolved",
}

# These claim types are safe for comparison or background context only
COMPARISON_ONLY_CLAIM_TYPES = {
    "comparison_only",
    "provisional_finding",
    "stale_research",
}

# ── Contamination risk thresholds ─────────────────────────────────────────────
# Risk score is accumulated from individual signal flags below
CONTAMINATION_RISK_LEVELS = [
    (7, "critical"),
    (5, "high"),
    (3, "medium"),
    (1, "low"),
    (0, "none"),
]

# ── Input Models ──────────────────────────────────────────────────────────────
class EvidenceSource(BaseModel):
    source_id: str = Field(..., description="Unique identifier for this evidence source")
    source_type: str = Field(..., description="e.g. lab_study, meta_analysis, peer_review, interview, commentary, preprint")
    claim_text: str = Field(..., description="Plain English description of what this source claims")
    claim_type: str = Field(..., description="validated_fact | provisional_finding | hypothesis | interview_supposition | commentary_opinion | stale_research | contradictory_unresolved | comparison_only")
    evidence_status: str = Field(..., description="e.g. published, preprint, unpublished, informal")
    provenance_score: float = Field(..., ge=0, le=10, description="Evidence traceability and source chain quality 0-10")
    authority_score: float = Field(..., ge=0, le=10, description="Institutional and methodological authority 0-10")
    evidence_age_hours: float = Field(..., ge=0, description="Age of this source in hours from original publication or capture")
    replication_status: str = Field("unknown", description="replicated | partial | not_replicated | unknown")
    sample_size: Optional[int] = Field(None, ge=0, description="Sample size underpinning the claim (None if not applicable)")
    included_in_query: bool = Field(True, description="Whether this source was included in the agent's query")
    intended_use: str = Field("support", description="Declared intended use: support | comparison_only | background_only")
    source_origin_lab: Optional[str] = Field(None, description="Institution or lab this source originates from")


class EvidenceIntegrityRequest(BaseModel):
    agent_id: str = Field(..., description="Unique identifier for the requesting agent")
    agent_name: str = Field(..., description="Human-readable agent name")
    action_description: str = Field(..., description="Plain English description of the proposed action this evidence supports")
    internal_lab_evidence: List[EvidenceSource] = Field(..., description="Trusted internal lab evidence sources")
    external_evidence_sources: List[EvidenceSource] = Field(..., description="External sources to validate against internal evidence")
    weight_profile: str = Field("default", description="default | medical")
    session_id: Optional[str] = Field(None, description="Optional session identifier for audit grouping")


# ── Output Models ─────────────────────────────────────────────────────────────
class InternalConsensus(BaseModel):
    source_count: int
    avg_provenance: float
    avg_authority: float
    avg_age_hours: float
    internal_conflict_detected: bool
    consensus_strength: str  # strong | moderate | weak


class SourceIntegrityResult(BaseModel):
    source_id: str
    claim_type: str
    intended_use: str
    claim_validity_state: str   # valid | provisional | speculative | stale | contradictory | misclassified
    authority_gap: float        # internal avg authority minus this source's authority (positive = source is weaker)
    freshness_gap: float        # source age minus internal avg age (positive = source is older)
    provenance_gap: float       # internal avg provenance minus source provenance (positive = source is weaker)
    replication_flag: bool      # True if not replicated or unknown
    contamination_risk: str     # none | low | medium | high | critical
    contamination_reason: Optional[str]
    allowed_use: str            # support | comparison_only | background_only | blocked
    block_reason: Optional[str]


class CrossLabInfluenceRisk(BaseModel):
    score: float
    contributing_sources: List[str]
    interpretation: str


class EvidenceIntegrityResponse(BaseModel):
    # Internal evidence summary
    internal_consensus: InternalConsensus

    # Per-source results for all external sources
    source_results: List[SourceIntegrityResult]

    # Aggregate outputs
    external_alignment: str           # aligned | partial | misaligned | contaminated
    overall_contamination_risk: str   # none | low | medium | high | critical
    cross_lab_influence_risk: CrossLabInfluenceRisk

    # Decision outputs
    conflict_state: str               # aligned | partial_conflict | conflict | contaminated
    conflict_explanation: str
    human_review_required: bool
    supervisor_alert: bool
    supervisor_alert_reason: Optional[str]
    recommended_action: str
    integrity_gate: str               # PASS | REVIEW | PAUSE | BLOCK

    # Metadata
    evaluated_at: str
    agent_id: str
    source_count_internal: int
    source_count_external: int


# ── Internal Consensus ────────────────────────────────────────────────────────
def compute_internal_consensus(sources: List[EvidenceSource]) -> InternalConsensus:
    if not sources:
        return InternalConsensus(
            source_count=0,
            avg_provenance=0.0,
            avg_authority=0.0,
            avg_age_hours=0.0,
            internal_conflict_detected=False,
            consensus_strength="none"
        )

    avg_prov = sum(s.provenance_score for s in sources) / len(sources)
    avg_auth = sum(s.authority_score for s in sources) / len(sources)
    avg_age  = sum(s.evidence_age_hours for s in sources) / len(sources)

    internal_conflict = any(s.claim_type.lower() == "contradictory_unresolved" for s in sources)

    if avg_auth >= 7.5 and avg_prov >= 7.0:
        strength = "strong"
    elif avg_auth >= 5.5 or avg_prov >= 5.0:
        strength = "moderate"
    else:
        strength = "weak"

    return InternalConsensus(
        source_count=len(sources),
        avg_provenance=round(avg_prov, 2),
        avg_authority=round(avg_auth, 2),
        avg_age_hours=round(avg_age, 1),
        internal_conflict_detected=internal_conflict,
        consensus_strength=strength
    )


# ── Per-Source Assessment ─────────────────────────────────────────────────────
def assess_source_integrity(
    source: EvidenceSource,
    internal_consensus: InternalConsensus
) -> SourceIntegrityResult:

    claim_type   = source.claim_type.lower()
    intended_use = source.intended_use.lower()

    # ── Gap metrics ───────────────────────────────────────────────────────────
    authority_gap   = round(internal_consensus.avg_authority  - source.authority_score,   2)
    freshness_gap   = round(source.evidence_age_hours          - internal_consensus.avg_age_hours, 1)
    provenance_gap  = round(internal_consensus.avg_provenance  - source.provenance_score,  2)
    replication_flag = source.replication_status.lower() in ("not_replicated", "unknown")

    # ── Claim validity state ──────────────────────────────────────────────────
    if claim_type in HIGH_RISK_CLAIM_TYPES and intended_use == "support":
        claim_validity_state = "misclassified"
    elif claim_type in ("interview_supposition", "commentary_opinion", "hypothesis"):
        claim_validity_state = "speculative"
    elif claim_type == "stale_research":
        claim_validity_state = "stale"
    elif claim_type == "contradictory_unresolved":
        claim_validity_state = "contradictory"
    elif claim_type == "validated_fact":
        claim_validity_state = "valid"
    else:
        claim_validity_state = "provisional"

    # ── Contamination risk accumulation ──────────────────────────────────────
    risk_score = 0
    reasons    = []

    # Primary flag: high-risk claim type declared as support
    if claim_type in HIGH_RISK_CLAIM_TYPES and intended_use == "support":
        risk_score += 4
        reasons.append(
            f"{claim_type} is being used as support evidence — "
            f"this claim type cannot support downstream recommendations"
        )

    # Secondary flag: high-risk source was included in the agent query
    if claim_type in HIGH_RISK_CLAIM_TYPES and source.included_in_query:
        risk_score += 2
        reasons.append(f"{claim_type} was included in the agent query")

    # Authority gap flag: source is substantially weaker than internal evidence
    if authority_gap >= 4.0:
        risk_score += 2
        reasons.append(f"authority gap of {authority_gap:.1f} points vs internal evidence baseline")

    # Freshness flag: source is significantly older than internal evidence
    if freshness_gap >= 720:  # 30+ days older than internal
        risk_score += 1
        reasons.append(
            f"source is {freshness_gap:.0f}h older than internal evidence baseline"
        )

    # Replication flag: unverified source being used as support
    if replication_flag and intended_use == "support":
        risk_score += 1
        reasons.append(f"replication status is {source.replication_status}")

    # Map accumulation to contamination level
    contamination_risk = "none"
    for threshold, level in CONTAMINATION_RISK_LEVELS:
        if risk_score >= threshold:
            contamination_risk = level
            break

    contamination_reason = "; ".join(reasons) if reasons else None

    # ── Allowed use determination ─────────────────────────────────────────────
    # Rules applied in priority order: most severe gate wins.
    block_reason = None

    if claim_type in HIGH_RISK_CLAIM_TYPES and intended_use == "support":
        # Rule 1: High-risk claim type cannot serve as support — block immediately
        allowed_use  = "blocked"
        block_reason = contamination_reason

    elif contamination_risk in ("critical", "high"):
        # Rule 2: Any source with critical/high contamination is blocked
        allowed_use  = "blocked"
        block_reason = contamination_reason

    elif claim_type in COMPARISON_ONLY_CLAIM_TYPES and intended_use == "support":
        # Rule 3: Provisional/comparison-only claim types cannot be primary support
        allowed_use = "comparison_only"

    elif authority_gap >= 3.5 and intended_use == "support":
        # Rule 4: Significant authority gap — downgrade from support to comparison
        allowed_use = "comparison_only"

    elif freshness_gap >= 720 and intended_use in ("support", "comparison_only"):
        # Rule 5: Very stale evidence — background context only
        allowed_use = "background_only"

    else:
        # No gate triggered — honor the declared intended use
        allowed_use = intended_use

    return SourceIntegrityResult(
        source_id=source.source_id,
        claim_type=claim_type,
        intended_use=intended_use,
        claim_validity_state=claim_validity_state,
        authority_gap=authority_gap,
        freshness_gap=freshness_gap,
        provenance_gap=provenance_gap,
        replication_flag=replication_flag,
        contamination_risk=contamination_risk,
        contamination_reason=contamination_reason,
        allowed_use=allowed_use,
        block_reason=block_reason
    )


# ── Cross-Lab Influence Risk ──────────────────────────────────────────────────
def compute_cross_lab_influence_risk(
    sources: List[EvidenceSource],
    source_results: List[SourceIntegrityResult]
) -> CrossLabInfluenceRisk:
    """
    Measures risk from lower-authority external sources that are still permitted
    to influence the recommendation (not blocked). Blocked sources are excluded
    because they will not reach the reasoning layer.
    """
    contributing = []
    risk_score   = 0.0

    for src, result in zip(sources, source_results):
        if result.allowed_use in ("support", "comparison_only") and result.authority_gap >= 2.0:
            contributing.append(src.source_id)
            risk_score += result.authority_gap * 0.5

    risk_score = min(10.0, round(risk_score, 1))

    if risk_score >= 7.0:
        interp = "HIGH — low-authority external sources are positioned to influence downstream recommendations"
    elif risk_score >= 4.0:
        interp = "MEDIUM — external sources have a notable authority gap relative to internal evidence"
    else:
        interp = "LOW — permitted external sources are close enough in authority to be manageable"

    return CrossLabInfluenceRisk(
        score=risk_score,
        contributing_sources=contributing,
        interpretation=interp
    )


# ── Integrity Gate ────────────────────────────────────────────────────────────
def integrity_gate(conflict_state: str, supervisor_alert: bool) -> tuple[str, str]:
    """Returns (gate_state, recommended_action)."""
    if conflict_state == "contaminated" or supervisor_alert:
        return (
            "BLOCK",
            "BLOCK — Evidence set cannot proceed. Remove or reclassify misclassified "
            "sources. Supervisor review required before this evidence bundle reaches "
            "the recommendation engine."
        )
    if conflict_state == "conflict":
        return (
            "PAUSE",
            "PAUSE — One or more external sources conflict with internal evidence. "
            "A human reviewer must resolve the conflicting sources before the agent proceeds."
        )
    if conflict_state == "partial_conflict":
        return (
            "REVIEW",
            "REVIEW — Evidence bundle has partial conflicts or authority gaps. "
            "Human reviewer should validate external source quality and confirm "
            "allowed-use classifications before proceeding."
        )
    return (
        "PASS",
        "Evidence integrity check passed. Proceed to delegation scoring."
    )


# ── Core Engine ───────────────────────────────────────────────────────────────
def evaluate_evidence_integrity(req: EvidenceIntegrityRequest) -> EvidenceIntegrityResponse:

    # Step 1 — Internal consensus
    internal_consensus = compute_internal_consensus(req.internal_lab_evidence)

    # Step 2 — Assess each external source independently
    source_results = [
        assess_source_integrity(src, internal_consensus)
        for src in req.external_evidence_sources
    ]

    # Step 3 — Cross-lab influence risk (across permitted sources only)
    cross_lab = compute_cross_lab_influence_risk(req.external_evidence_sources, source_results)

    # Step 4 — Aggregate contamination risk (worst single source wins)
    risk_order = ["none", "low", "medium", "high", "critical"]
    overall_contamination = max(
        (r.contamination_risk for r in source_results),
        key=lambda x: risk_order.index(x),
        default="none"
    )

    # Step 5 — Conflict state (relational: considers full bundle)
    misclassified_count = sum(1 for r in source_results if r.claim_validity_state == "misclassified")
    blocked_count       = sum(1 for r in source_results if r.allowed_use == "blocked")
    high_risk_count     = sum(1 for r in source_results if r.contamination_risk in ("high", "critical"))

    if misclassified_count > 0 or overall_contamination == "critical":
        conflict_state      = "contaminated"
        external_alignment  = "contaminated"
    elif blocked_count > 0:
        conflict_state      = "conflict"
        external_alignment  = "misaligned"
    elif high_risk_count > 0 or overall_contamination == "high":
        conflict_state      = "partial_conflict"
        external_alignment  = "partial"
    else:
        conflict_state      = "aligned"
        external_alignment  = "aligned"

    # Step 6 — Conflict explanation (per-source, actionable)
    explanation_parts = []
    for r in source_results:
        if r.claim_validity_state == "misclassified":
            explanation_parts.append(
                f"{r.source_id}: {r.claim_type} is classified as support evidence — "
                f"this claim type cannot support downstream recommendations"
            )
        elif r.contamination_risk in ("high", "critical") and r.allowed_use == "blocked":
            explanation_parts.append(
                f"{r.source_id}: blocked — contamination risk is {r.contamination_risk.upper()} "
                f"({r.contamination_reason})"
            )
        elif r.allowed_use == "blocked" and r.block_reason:
            explanation_parts.append(f"{r.source_id}: blocked — {r.block_reason}")

    if not explanation_parts:
        explanation_parts.append(
            "No significant conflicts detected between internal and external evidence."
        )

    conflict_explanation = " | ".join(explanation_parts)

    # Step 7 — Supervisor alert
    supervisor_alert        = False
    supervisor_alert_reason = None

    if misclassified_count > 0:
        supervisor_alert = True
        supervisor_alert_reason = (
            f"{misclassified_count} source(s) are misclassified as support evidence. "
            "Interview statements, opinion pieces, and hypothesis material are "
            "positioned to directly influence a downstream recommendation. "
            "Supervisor review is required before this evidence set proceeds."
        )
    elif overall_contamination == "critical":
        supervisor_alert = True
        supervisor_alert_reason = (
            "Critical contamination risk detected. At least one source poses "
            "unacceptable epistemic risk to downstream reasoning."
        )

    # Step 8 — Human review required
    human_review_required = (
        conflict_state in ("contaminated", "conflict", "partial_conflict")
        or supervisor_alert
        or cross_lab.score >= 5.0
    )

    # Step 9 — Integrity gate
    gate, recommended_action = integrity_gate(conflict_state, supervisor_alert)

    return EvidenceIntegrityResponse(
        internal_consensus=internal_consensus,
        source_results=source_results,
        external_alignment=external_alignment,
        overall_contamination_risk=overall_contamination,
        cross_lab_influence_risk=cross_lab,
        conflict_state=conflict_state,
        conflict_explanation=conflict_explanation,
        human_review_required=human_review_required,
        supervisor_alert=supervisor_alert,
        supervisor_alert_reason=supervisor_alert_reason,
        recommended_action=recommended_action,
        integrity_gate=gate,
        evaluated_at=datetime.utcnow().isoformat() + "Z",
        agent_id=req.agent_id,
        source_count_internal=len(req.internal_lab_evidence),
        source_count_external=len(req.external_evidence_sources)
    )
