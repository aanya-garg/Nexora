"""
Person 3: final score computation.

Combines the Evidence Ledger and semantic match data into the four
score_breakdown components, then a single 0-100 final_score using a fixed,
documented weight split. `compute_final_score` is a pure function: no I/O,
no randomness, no candidate-specific tuning -- the same inputs always
produce the same output, and the same weights are applied to every
candidate.
"""

from __future__ import annotations

from typing import Dict, List
import math

from schemas import CandidateResult, EvidenceLedgerEntry, ParsedJD, ParsedResume, ScoreBreakdown, SemanticMatchResult

# 40% semantic requirement alignment, 35% explicit/normalized requirement
# coverage, 15% experience/project relevance, 10% evidence strength.
# These four top-level weights are fixed and must not change.
DEFAULT_WEIGHTS: Dict[str, float] = {
    "semantic": 0.40,
    "keyword": 0.35,
    "experience": 0.15,
    "evidence_strength": 0.10,
}

REQUIRED_COMPONENT_KEYS = frozenset(DEFAULT_WEIGHTS.keys())

# Fixed, global weighting applied *inside* the semantic and keyword
# components only, so a missed "required" requirement drags those two
# components down twice as hard as a missed "preferred" one. Same weights
# for every candidate/JD -- never adjusted per-candidate. Does not touch the
# top-level 40/35/15/10 split, and is not applied to the experience or
# evidence_strength components.
REQUIREMENT_TYPE_WEIGHT: Dict[str, float] = {
    "required": 2.0,
    "preferred": 1.0,
}

# Person 2's real extract_requirements() can legitimately emit type=None for
# a requirement whose required/preferred priority is ambiguous in the JD
# wording (see engine.py's `priority_unspecified` warning) -- schemas.py's
# JDRequirement.type annotation doesn't capture this. Fall back to weight 1.0
# or an unrecognized type, mirroring Person 2's own weights.json
# ("unspecified": 1.0) default rather than crashing on real JDs.
DEFAULT_REQUIREMENT_TYPE_WEIGHT = 1.0

# Fixed, global weighting of match_type quality for the evidence_strength
# component. Identical for every candidate -- never adjusted per-candidate.
MATCH_TYPE_STRENGTH = {
    "EXACT": 1.0,
    "NORMALIZED": 0.85,
    "SEMANTIC": 0.6,
    "NOT_EVIDENCED": 0.0,
}

# Resume sections that count as "experience/project" evidence for the
# experience component.
EXPERIENCE_SECTIONS = frozenset({"experience", "projects"})


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _weighted_mean(scores_and_weights: List[tuple]) -> float:
    """weighted_average = sum(score_i * weight_i) / sum(weight_i)."""
    total_weight = sum(weight for _, weight in scores_and_weights)
    if total_weight == 0:
        return 0.0
    return sum(score * weight for score, weight in scores_and_weights) / total_weight


def compute_component_scores(
    jd: ParsedJD,
    ledger: List[EvidenceLedgerEntry],
    semantic_results: List[SemanticMatchResult],
) -> ScoreBreakdown:
    """Derive the four 0-100 score_breakdown components for one candidate
    from their JD, Evidence Ledger, and raw semantic match results.

    - keyword: requirement-type-weighted mean of keyword_score (0-100
      scale). A missed "required" requirement pulls this down twice as hard
      as a missed "preferred" one (REQUIREMENT_TYPE_WEIGHT, 2:1).
    - semantic: requirement-type-weighted mean of semantic_score (0-100
      scale), same 2:1 weighting. Included regardless of match_type/
      SEMANTIC_MATCH_THRESHOLD -- a below-threshold (NOT_EVIDENCED) semantic
      score still contributes its raw value here.
    - experience: unweighted mean of semantic_score restricted to
      requirements whose best evidence came from the resume's
      experience/projects sections. 0.0 if none did. Not requirement-type
      weighted.
    - evidence_strength: unweighted mean of match-type quality weight
      across all requirements (EXACT=1.0, NORMALIZED=0.85, SEMANTIC=0.6,
      NOT_EVIDENCED=0.0). Not requirement-type weighted.
    """
    type_by_requirement_id = {req["id"]: req["type"] for req in jd["requirements"]}

    keyword_items = [
        (entry["keyword_score"], REQUIREMENT_TYPE_WEIGHT.get(type_by_requirement_id[entry["id"]], DEFAULT_REQUIREMENT_TYPE_WEIGHT))
        for entry in ledger
    ]
    semantic_items = [
        (entry["semantic_score"], REQUIREMENT_TYPE_WEIGHT.get(type_by_requirement_id[entry["id"]], DEFAULT_REQUIREMENT_TYPE_WEIGHT))
        for entry in ledger
    ]

    keyword = _weighted_mean(keyword_items) * 100
    semantic = _weighted_mean(semantic_items) * 100

    experience_scores = [
        sr["semantic_score"] for sr in semantic_results if sr["best_evidence_section"] in EXPERIENCE_SECTIONS
    ]
    experience = _mean(experience_scores) * 100

    evidence_strength = _mean([MATCH_TYPE_STRENGTH[entry["match_type"]] for entry in ledger]) * 100

    return {
        "keyword": round(_clamp(keyword), 1),
        "semantic": round(_clamp(semantic), 1),
        "experience": round(_clamp(experience), 1),
        "evidence_strength": round(_clamp(evidence_strength), 1),
    }


def compute_final_score(component_scores: dict, weights: dict = None) -> float:
    """Pure function: component_scores + weights -> single 0-100 float.

    component_scores must contain "keyword", "semantic", "experience", and
    "evidence_strength" keys (each expected on a 0-100 scale). weights must
    contain the same keys with values summing to 1.0 (within floating point
    tolerance). Defaults to DEFAULT_WEIGHTS (40/35/15/10) when weights is
    omitted.
    """
    weights = DEFAULT_WEIGHTS if weights is None else weights

    missing_scores = REQUIRED_COMPONENT_KEYS - component_scores.keys()
    if missing_scores:
        raise ValueError(f"component_scores missing keys: {sorted(missing_scores)}")

    missing_weights = REQUIRED_COMPONENT_KEYS - weights.keys()
    if missing_weights:
        raise ValueError(f"weights missing keys: {sorted(missing_weights)}")

    for key in REQUIRED_COMPONENT_KEYS:
        value, weight = component_scores[key], weights[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Component scores must be finite numbers")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight) or weight < 0:
            raise ValueError("Weights must be finite nonnegative numbers")

    weight_total = sum(weights[key] for key in REQUIRED_COMPONENT_KEYS)
    if abs(weight_total - 1.0) > 1e-6:
        raise ValueError(f"weights for {sorted(REQUIRED_COMPONENT_KEYS)} must sum to 1.0, got {weight_total}")

    total = sum(component_scores[key] * weights[key] for key in REQUIRED_COMPONENT_KEYS)
    return round(_clamp(total), 1)


def score_candidate(
    jd: ParsedJD,
    resume: ParsedResume,
    ledger: List[EvidenceLedgerEntry],
    semantic_results: List[SemanticMatchResult],
    weights: dict = None,
) -> CandidateResult:
    """Assemble the full CandidateResult for one candidate: score_breakdown,
    final_score, and the Evidence Ledger itself.
    """
    score_breakdown = compute_component_scores(jd, ledger, semantic_results)
    final_score = compute_final_score(score_breakdown, weights)

    return {
        "candidate_id": resume["candidate_id"],
        "candidate_name": resume["candidate_name"],
        "final_score": final_score,
        "score_breakdown": score_breakdown,
        # The internal cosine ledger uses fractions; every public score is 0-100.
        "requirements": [{**row, "keyword_score": round(row["keyword_score"] * 100, 2),
                          "semantic_score": round(row["semantic_score"] * 100, 2)} for row in ledger],
    }
