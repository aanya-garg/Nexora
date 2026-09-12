"""
Person 3: final candidate ranking.

Sorts CandidateResult records best-to-worst by final_score, with a fully
deterministic tie-break chain so the output order never depends on input
order or on any per-candidate special-casing.
"""

from __future__ import annotations

from typing import List

from schemas import CandidateResult


def _rank_key(result: CandidateResult):
    breakdown = result["score_breakdown"]
    return (
        -result["final_score"],
        -breakdown["semantic"],
        -breakdown["keyword"],
        -breakdown["evidence_strength"],
        -breakdown["experience"],
        result["candidate_id"],
    )


def rank_candidates(results: List[CandidateResult]) -> List[CandidateResult]:
    """Return `results` sorted best-to-worst.

    Primary key: final_score (descending).
    Tie-break chain (all descending, applied in order): semantic, keyword,
    evidence_strength, experience score_breakdown components.
    Final tie-break: candidate_id ascending, so ordering is fully
    deterministic even for two otherwise-identical candidates.
    """
    return sorted(results, key=_rank_key)
