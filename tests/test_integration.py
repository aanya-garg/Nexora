"""
End-to-end integration test: REAL Person 1 parsing -> REAL Person 2 keyword
matching -> adapters.py -> Person 3 (real all-MiniLM-L6-v2 semantic matching,
Evidence Ledger, scoring, ranking).

Uses the actual fixture files from Person 1/Person 2's branches
(tests/fixtures/jd_keyword.txt, resume_complete.txt, resume_messy.txt) and
their actual code (evidencerank.parsing, evidencerank.keyword), materialized
locally from origin/person-a-parsing and origin/person-b-keyword without
merging/checking out those branches. Skips automatically if the real
embedding model isn't available in this environment.
"""

from pathlib import Path

import pytest

from adapters import adapt_jd, adapt_keyword_results, adapt_resume
from evidence_ledger import build_ledger
from evidencerank.keyword import extract_requirements, match_candidates
from evidencerank.parsing import parse_jd, parse_resume
from ranking import rank_candidates
from scoring import score_candidate
from semantic_matcher import compute_semantic_matches

FIXTURES = Path(__file__).parent / "fixtures"
ALL_RESUME_FIXTURES = ["resume_complete.txt", "resume_messy.txt"]


def _get_real_embedder_or_skip():
    try:
        from semantic_matcher import get_default_embedder

        get_default_embedder.cache_clear()
        return get_default_embedder()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"real embedding model unavailable in this environment: {exc}")


def _build_real_jd():
    person1_jd = parse_jd(FIXTURES / "jd_keyword.txt")
    person2_extracted = extract_requirements(person1_jd)
    return adapt_jd(person1_jd, person2_extracted)


def _run_pipeline_for_resumes(resume_filenames, embedder):
    jd = _build_real_jd()

    person1_resumes = [parse_resume(FIXTURES / name) for name in resume_filenames]
    person2_matches = match_candidates(person1_resumes, jd["requirements"])
    flat_keyword_results = adapt_keyword_results(person2_matches)

    results = []
    for person1_resume in person1_resumes:
        resume = adapt_resume(person1_resume)
        semantic_results = compute_semantic_matches(jd, resume, embedder=embedder)
        ledger = build_ledger(jd, resume, flat_keyword_results, semantic_results)
        results.append(score_candidate(jd, resume, ledger, semantic_results))
    return jd, results


def test_single_real_jd_and_resume_full_pipeline():
    """Real PDF-parser-shaped text -> Person 1 -> Person 2 -> adapters.py ->
    Person 3 (real model) -> one complete CandidateResult."""
    embedder = _get_real_embedder_or_skip()

    jd, results = _run_pipeline_for_resumes(["resume_complete.txt"], embedder)
    assert len(results) == 1
    candidate = results[0]

    # Full CandidateResult contract shape.
    assert set(candidate.keys()) == {"candidate_id", "candidate_name", "final_score", "score_breakdown", "requirements"}
    assert candidate["candidate_name"] == "Maya Kapoor"
    assert len(candidate["requirements"]) == len(jd["requirements"])
    assert set(candidate["score_breakdown"].keys()) == {"keyword", "semantic", "experience", "evidence_strength"}
    assert 0.0 <= candidate["final_score"] <= 100.0

    # React is in Maya's resume (as "React.js"/"reactjs") -> Person 2 should
    # find it via NORMALIZED, and evidence must be real resume text.
    by_id = {r["id"]: r for r in candidate["requirements"]}
    react_req = next(r for r in jd["requirements"] if r["skill"] == "React")
    react_entry = by_id[react_req["id"]]
    assert react_entry["match_type"] in {"EXACT", "NORMALIZED"}
    assert react_entry["evidence"] != ""


def test_full_pipeline_across_all_real_resumes():
    """Run the same real pipeline across every available real resume fixture,
    then rank them deterministically."""
    embedder = _get_real_embedder_or_skip()

    jd, results = _run_pipeline_for_resumes(ALL_RESUME_FIXTURES, embedder)
    assert len(results) == len(ALL_RESUME_FIXTURES)

    ranked = rank_candidates(results)
    assert len(ranked) == len(ALL_RESUME_FIXTURES)
    # Deterministic, stable ordering by final_score (descending).
    scores = [c["final_score"] for c in ranked]
    assert scores == sorted(scores, reverse=True)

    # Re-running produces identical ranking (determinism, no I/O/randomness).
    _, results_again = _run_pipeline_for_resumes(ALL_RESUME_FIXTURES, embedder)
    ranked_again = rank_candidates(results_again)
    assert [c["candidate_id"] for c in ranked] == [c["candidate_id"] for c in ranked_again]
    assert [c["final_score"] for c in ranked] == [c["final_score"] for c in ranked_again]


def test_requirement_with_unspecified_priority_does_not_crash_scoring():
    """jd_keyword.txt's requirements all resolve to required/preferred, so
    this directly exercises adapt_jd + scoring.py's None-type fix using a
    requirement list containing an explicit type=None, proving real
    ambiguous-priority JD wording (which Person 2's engine.py can produce)
    doesn't crash compute_component_scores.
    """
    embedder = _get_real_embedder_or_skip()
    jd, _ = _run_pipeline_for_resumes(["resume_complete.txt"], embedder)

    # Inject an unspecified-priority requirement, mirroring what Person 2's
    # extract_requirements() legitimately produces for ambiguous JD wording.
    jd = {**jd, "requirements": jd["requirements"] + [
        {"id": "REQ999", "text": "Familiarity with GraphQL", "skill": "GraphQL", "type": None}
    ]}
    person1_resume = parse_resume(FIXTURES / "resume_complete.txt")
    resume = adapt_resume(person1_resume)
    person2_matches = match_candidates([person1_resume], jd["requirements"])
    flat_keyword_results = adapt_keyword_results(person2_matches)
    semantic_results = compute_semantic_matches(jd, resume, embedder=embedder)
    ledger = build_ledger(jd, resume, flat_keyword_results, semantic_results)

    candidate = score_candidate(jd, resume, ledger, semantic_results)
    assert 0.0 <= candidate["final_score"] <= 100.0
