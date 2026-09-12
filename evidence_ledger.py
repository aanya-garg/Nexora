"""
Person 3: Evidence Ledger construction.

Merges Person 2's keyword/normalized match results with Person 3's own
semantic match results into one EvidenceLedgerEntry per (candidate,
requirement), with a deterministic match_type classification and a piece of
evidence text that is always copied verbatim from the resume (or empty) --
never fabricated or paraphrased.
"""

from __future__ import annotations

from typing import Dict, List

from schemas import (
    EvidenceLedgerEntry,
    JDRequirement,
    KeywordMatchResult,
    MatchType,
    ParsedJD,
    ParsedResume,
    SemanticMatchResult,
)
from semantic_matcher import flatten_resume_chunks

# Deterministic, fixed threshold: a requirement with no keyword/normalized
# match is classified SEMANTIC only if similarity clears this bar. This is a
# single global constant applied identically to every candidate -- it must
# never be adjusted per-candidate to change a ranking outcome.
#
# 0.35 is an empirically chosen hackathon default, not a universally correct
# cutoff: real all-MiniLM-L6-v2 cosine similarities for genuinely-related but
# differently-worded sentence pairs (e.g. "Machine learning experience" vs.
# "Built classification models using scikit-learn.", ~0.37) commonly land in
# the 0.3-0.5 band rather than 0.6+. A higher threshold (e.g. the previous
# 0.55) systematically misses true matches. This value should be revisited
# against a larger, representative sample of real JD/resume pairs once
# Person 1's parser output is available -- see tests/test_semantic_matcher.py
# for the sanity check this was derived from.
#
# This threshold ONLY gates match_type classification (see
# classify_match_type below). It never modifies semantic_score itself, which
# always contributes to the 40% semantic score_breakdown component
# regardless of which side of this threshold it falls on (see scoring.py).
SEMANTIC_MATCH_THRESHOLD = 0.35


def _empty_keyword_result(candidate_id: str, requirement_id: str) -> KeywordMatchResult:
    """Default used when Person 2 has not supplied a result for this
    (candidate, requirement) pair. Represents "no keyword evidence found",
    never a fabricated match.
    """
    return {
        "candidate_id": candidate_id,
        "requirement_id": requirement_id,
        "keyword_score": 0.0,
        "matched_terms": [],
        "normalized_match": None,
    }


def _empty_semantic_result(candidate_id: str, requirement_id: str) -> SemanticMatchResult:
    return {
        "candidate_id": candidate_id,
        "requirement_id": requirement_id,
        "semantic_score": 0.0,
        "best_evidence_text": "",
        "best_evidence_section": "",
    }


def classify_match_type(
    keyword_result: KeywordMatchResult,
    semantic_result: SemanticMatchResult,
    semantic_threshold: float = SEMANTIC_MATCH_THRESHOLD,
) -> MatchType:
    """Deterministic classification, checked in strict priority order:

    1. EXACT        -- Person 2 found a literal matched term.
    2. NORMALIZED    -- no literal term, but a normalized/alias match exists.
    3. SEMANTIC       -- no keyword evidence at all, but embedding similarity
                          clears `semantic_threshold`.
    4. NOT_EVIDENCED  -- none of the above.
    """
    if keyword_result["matched_terms"]:
        return "EXACT"
    if keyword_result["normalized_match"]:
        return "NORMALIZED"
    if semantic_result["semantic_score"] >= semantic_threshold:
        return "SEMANTIC"
    return "NOT_EVIDENCED"


def _select_evidence(
    requirement: JDRequirement,
    keyword_result: KeywordMatchResult,
    semantic_result: SemanticMatchResult,
    resume_chunks: List[tuple],
) -> str:
    """Return a verbatim resume chunk supporting the match, or "".

    Search order: literal matched_terms -> normalized_match string -> the
    requirement's own skill token, each checked as a case-insensitive
    substring against every resume chunk. Falls back to the semantic
    matcher's own best-evidence chunk (still real resume text) if no keyword
    based search succeeds. Every candidate value returned here is text that
    was actually extracted from the resume -- nothing is invented.
    """
    candidate_terms = list(keyword_result["matched_terms"])
    if keyword_result["normalized_match"]:
        candidate_terms.append(keyword_result["normalized_match"])
    candidate_terms.append(requirement["skill"])

    for term in candidate_terms:
        term = (term or "").strip()
        if not term:
            continue
        term_lower = term.lower()
        for _section, chunk in resume_chunks:
            if term_lower in chunk.lower():
                return chunk

    if semantic_result["best_evidence_text"]:
        return semantic_result["best_evidence_text"]

    return ""


def build_evidence_entry(
    requirement: JDRequirement,
    keyword_result: KeywordMatchResult,
    semantic_result: SemanticMatchResult,
    resume_chunks: List[tuple],
    semantic_threshold: float = SEMANTIC_MATCH_THRESHOLD,
) -> EvidenceLedgerEntry:
    """Build a single ledger row for one requirement."""
    match_type = classify_match_type(keyword_result, semantic_result, semantic_threshold)

    if match_type == "NOT_EVIDENCED":
        evidence = ""
    else:
        evidence = _select_evidence(requirement, keyword_result, semantic_result, resume_chunks)

    return {
        "id": requirement["id"],
        "text": requirement["text"],
        "keyword_score": keyword_result["keyword_score"],
        "semantic_score": semantic_result["semantic_score"],
        "match_type": match_type,
        "evidence": evidence,
    }


def build_ledger(
    jd: ParsedJD,
    resume: ParsedResume,
    keyword_results: List[KeywordMatchResult],
    semantic_results: List[SemanticMatchResult],
    semantic_threshold: float = SEMANTIC_MATCH_THRESHOLD,
) -> List[EvidenceLedgerEntry]:
    """Build the full Evidence Ledger (one entry per JD requirement) for a
    single candidate's resume.

    `keyword_results` / `semantic_results` are expected to contain one entry
    per requirement_id for this candidate_id (per CONTRACT.md), but any
    missing requirement_id is safely defaulted to "no evidence found" rather
    than raising, so a partial or not-yet-complete upstream implementation
    doesn't crash the ledger build.
    """
    candidate_id = resume["candidate_id"]
    resume_chunks = flatten_resume_chunks(resume)

    keyword_by_req: Dict[str, KeywordMatchResult] = {
        r["requirement_id"]: r for r in keyword_results if r["candidate_id"] == candidate_id
    }
    semantic_by_req: Dict[str, SemanticMatchResult] = {
        r["requirement_id"]: r for r in semantic_results if r["candidate_id"] == candidate_id
    }

    ledger: List[EvidenceLedgerEntry] = []
    for requirement in jd["requirements"]:
        req_id = requirement["id"]
        keyword_result = keyword_by_req.get(req_id) or _empty_keyword_result(candidate_id, req_id)
        semantic_result = semantic_by_req.get(req_id) or _empty_semantic_result(candidate_id, req_id)
        ledger.append(
            build_evidence_entry(requirement, keyword_result, semantic_result, resume_chunks, semantic_threshold)
        )
    return ledger
