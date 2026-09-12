import pytest

from evidence_ledger import build_ledger
from scoring import (
    DEFAULT_WEIGHTS,
    REQUIREMENT_TYPE_WEIGHT,
    compute_component_scores,
    compute_final_score,
    score_candidate,
)
from semantic_matcher import compute_semantic_matches


def _jd(requirement_types):
    """Build a minimal ParsedJD with one requirement per (id, type) pair."""
    return {
        "raw_text": "",
        "requirements": [
            {"id": req_id, "text": req_id, "skill": req_id, "type": req_type}
            for req_id, req_type in requirement_types
        ],
    }


def _ledger_entry(req_id, keyword_score, semantic_score, match_type):
    return {
        "id": req_id,
        "text": req_id,
        "keyword_score": keyword_score,
        "semantic_score": semantic_score,
        "match_type": match_type,
        "evidence": "some evidence" if match_type != "NOT_EVIDENCED" else "",
    }


def test_compute_final_score_matches_manual_weighted_sum():
    component_scores = {"keyword": 80.0, "semantic": 90.0, "experience": 70.0, "evidence_strength": 60.0}
    expected = 80.0 * 0.35 + 90.0 * 0.40 + 70.0 * 0.15 + 60.0 * 0.10
    assert compute_final_score(component_scores, DEFAULT_WEIGHTS) == round(expected, 1)


def test_compute_final_score_uses_default_weights_when_omitted():
    component_scores = {"keyword": 100.0, "semantic": 0.0, "experience": 0.0, "evidence_strength": 0.0}
    assert compute_final_score(component_scores) == 35.0


def test_compute_final_score_is_pure_and_deterministic():
    component_scores = {"keyword": 55.5, "semantic": 42.2, "experience": 33.3, "evidence_strength": 10.0}
    first = compute_final_score(component_scores, DEFAULT_WEIGHTS)
    second = compute_final_score(dict(component_scores), dict(DEFAULT_WEIGHTS))
    assert first == second


def test_compute_final_score_raises_on_missing_component_key():
    with pytest.raises(ValueError):
        compute_final_score({"keyword": 1.0, "semantic": 1.0, "experience": 1.0})


def test_compute_final_score_raises_when_weights_do_not_sum_to_one():
    bad_weights = {"keyword": 0.5, "semantic": 0.5, "experience": 0.5, "evidence_strength": 0.5}
    component_scores = {"keyword": 10.0, "semantic": 10.0, "experience": 10.0, "evidence_strength": 10.0}
    with pytest.raises(ValueError):
        compute_final_score(component_scores, bad_weights)


def test_compute_final_score_clamps_to_0_100_range():
    component_scores = {"keyword": 1000.0, "semantic": 1000.0, "experience": 1000.0, "evidence_strength": 1000.0}
    assert compute_final_score(component_scores, DEFAULT_WEIGHTS) == 100.0


def test_default_weights_sum_to_one():
    assert set(DEFAULT_WEIGHTS.keys()) == {"keyword", "semantic", "experience", "evidence_strength"}
    assert DEFAULT_WEIGHTS == {"semantic": 0.40, "keyword": 0.35, "experience": 0.15, "evidence_strength": 0.10}
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


def test_compute_component_scores_all_exact_matches_maxes_keyword_and_evidence_strength():
    jd = _jd([("REQ1", "required"), ("REQ2", "preferred"), ("REQ3", "required")])
    ledger = [_ledger_entry(req["id"], 1.0, 1.0, "EXACT") for req in jd["requirements"]]
    breakdown = compute_component_scores(jd, ledger, semantic_results=[])
    assert breakdown["keyword"] == 100.0
    assert breakdown["semantic"] == 100.0
    assert breakdown["evidence_strength"] == 100.0
    # no semantic_results supplied -> experience defaults to 0
    assert breakdown["experience"] == 0.0


def test_compute_component_scores_all_not_evidenced_is_all_zero():
    jd = _jd([("REQ1", "required"), ("REQ2", "preferred"), ("REQ3", "required")])
    ledger = [_ledger_entry(req["id"], 0.0, 0.0, "NOT_EVIDENCED") for req in jd["requirements"]]
    breakdown = compute_component_scores(jd, ledger, semantic_results=[])
    assert breakdown == {"keyword": 0.0, "semantic": 0.0, "experience": 0.0, "evidence_strength": 0.0}


def test_compute_component_scores_experience_only_counts_experience_and_project_sections():
    jd = _jd([("R1", "required"), ("R2", "required")])
    ledger = [_ledger_entry("R1", 0.5, 0.8, "SEMANTIC"), _ledger_entry("R2", 0.5, 0.2, "SEMANTIC")]
    semantic_results = [
        {"candidate_id": "c", "requirement_id": "R1", "semantic_score": 0.8, "best_evidence_text": "x", "best_evidence_section": "experience"},
        {"candidate_id": "c", "requirement_id": "R2", "semantic_score": 0.2, "best_evidence_text": "y", "best_evidence_section": "skills"},
    ]
    breakdown = compute_component_scores(jd, ledger, semantic_results)
    # only the "experience" section entry (0.8) counts toward the experience component
    assert breakdown["experience"] == 80.0


def test_compute_final_score_empty_component_scores_all_zero_yields_zero():
    component_scores = {"keyword": 0.0, "semantic": 0.0, "experience": 0.0, "evidence_strength": 0.0}
    assert compute_final_score(component_scores, DEFAULT_WEIGHTS) == 0.0


def test_keyword_and_semantic_both_materially_affect_final_score():
    """Changing only keyword evidence, or only semantic evidence, must move
    final_score by a non-trivial amount -- neither signal is a no-op."""
    base = {"keyword": 0.0, "semantic": 0.0, "experience": 0.0, "evidence_strength": 0.0}

    keyword_only = dict(base, keyword=100.0)
    semantic_only = dict(base, semantic=100.0)

    base_score = compute_final_score(base, DEFAULT_WEIGHTS)
    keyword_score = compute_final_score(keyword_only, DEFAULT_WEIGHTS)
    semantic_score = compute_final_score(semantic_only, DEFAULT_WEIGHTS)

    assert keyword_score - base_score >= 30.0  # ~35 pts, matches the 35% keyword weight
    assert semantic_score - base_score >= 35.0  # ~40 pts, matches the 40% semantic weight
    assert keyword_score != semantic_score


def test_keyword_and_semantic_both_materially_affect_final_score_end_to_end(
    sample_jd, resume_strong, keyword_results_strong, fake_embedder
):
    """Same guarantee, but exercised through the real component-scoring path
    (compute_component_scores + compute_final_score), not hand-built
    component_scores dicts."""
    semantic_results = compute_semantic_matches(sample_jd, resume_strong, embedder=fake_embedder)
    ledger = build_ledger(sample_jd, resume_strong, keyword_results_strong, semantic_results)
    full_result = score_candidate(sample_jd, resume_strong, ledger, semantic_results)

    # zero out all keyword evidence -> final score must drop materially
    no_keyword_ledger = [dict(entry, keyword_score=0.0, match_type="NOT_EVIDENCED") for entry in ledger]
    no_keyword_result = score_candidate(sample_jd, resume_strong, no_keyword_ledger, semantic_results)

    # zero out all semantic evidence -> final score must also drop materially
    zeroed_semantic_results = [dict(sr, semantic_score=0.0) for sr in semantic_results]
    no_semantic_ledger = [dict(entry, semantic_score=0.0) for entry in ledger]
    no_semantic_result = score_candidate(sample_jd, resume_strong, no_semantic_ledger, zeroed_semantic_results)

    assert no_keyword_result["final_score"] < full_result["final_score"]
    assert no_semantic_result["final_score"] < full_result["final_score"]


def test_score_candidate_end_to_end(sample_jd, resume_strong, keyword_results_strong, fake_embedder):
    semantic_results = compute_semantic_matches(sample_jd, resume_strong, embedder=fake_embedder)
    ledger = build_ledger(sample_jd, resume_strong, keyword_results_strong, semantic_results)
    result = score_candidate(sample_jd, resume_strong, ledger, semantic_results)

    assert result["candidate_id"] == "cand-1"
    assert result["candidate_name"] == "Alice Example"
    assert 0.0 <= result["final_score"] <= 100.0
    assert set(result["score_breakdown"].keys()) == {"keyword", "semantic", "experience", "evidence_strength"}
    assert len(result["requirements"]) == len(sample_jd["requirements"])


def test_strong_candidate_scores_higher_than_weak_candidate(
    sample_jd, resume_strong, resume_weak, keyword_results_strong, keyword_results_weak, fake_embedder
):
    strong_semantic = compute_semantic_matches(sample_jd, resume_strong, embedder=fake_embedder)
    weak_semantic = compute_semantic_matches(sample_jd, resume_weak, embedder=fake_embedder)

    strong_ledger = build_ledger(sample_jd, resume_strong, keyword_results_strong, strong_semantic)
    weak_ledger = build_ledger(sample_jd, resume_weak, keyword_results_weak, weak_semantic)

    strong_result = score_candidate(sample_jd, resume_strong, strong_ledger, strong_semantic)
    weak_result = score_candidate(sample_jd, resume_weak, weak_ledger, weak_semantic)

    assert strong_result["final_score"] > weak_result["final_score"]


# ---------------------------------------------------------------------------
# Required vs preferred requirement weighting (2:1, applied only inside the
# keyword and semantic components).
# ---------------------------------------------------------------------------

def test_requirement_type_weight_is_two_to_one():
    assert REQUIREMENT_TYPE_WEIGHT == {"required": 2.0, "preferred": 1.0}


def test_missing_required_requirement_hurts_more_than_missing_preferred():
    jd = _jd([("REQ_REQUIRED", "required"), ("REQ_PREFERRED", "preferred")])

    # Case A: the REQUIRED requirement is unmet, the PREFERRED one is fully met.
    ledger_missing_required = [
        _ledger_entry("REQ_REQUIRED", 0.0, 0.0, "NOT_EVIDENCED"),
        _ledger_entry("REQ_PREFERRED", 1.0, 1.0, "EXACT"),
    ]
    # Case B: the PREFERRED requirement is unmet, the REQUIRED one is fully met.
    ledger_missing_preferred = [
        _ledger_entry("REQ_REQUIRED", 1.0, 1.0, "EXACT"),
        _ledger_entry("REQ_PREFERRED", 0.0, 0.0, "NOT_EVIDENCED"),
    ]

    breakdown_missing_required = compute_component_scores(jd, ledger_missing_required, semantic_results=[])
    breakdown_missing_preferred = compute_component_scores(jd, ledger_missing_preferred, semantic_results=[])

    # Missing the required requirement must produce a strictly lower
    # keyword/semantic component than missing the preferred one.
    assert breakdown_missing_required["keyword"] < breakdown_missing_preferred["keyword"]
    assert breakdown_missing_required["semantic"] < breakdown_missing_preferred["semantic"]

    # Exact expected values under 2:1 weighting: missing "required" (weight 2)
    # while preferred (weight 1) is fully met -> (0*2 + 1*1) / 3 = 0.333 -> 33.3
    assert breakdown_missing_required["keyword"] == pytest.approx(33.3, abs=0.1)
    # Missing "preferred" (weight 1) while required (weight 2) is fully met
    # -> (1*2 + 0*1) / 3 = 0.667 -> 66.7
    assert breakdown_missing_preferred["keyword"] == pytest.approx(66.7, abs=0.1)


def test_requirement_type_weighting_is_deterministic():
    jd = _jd([("R1", "required"), ("R2", "preferred"), ("R3", "required")])
    ledger = [
        _ledger_entry("R1", 0.4, 0.6, "SEMANTIC"),
        _ledger_entry("R2", 0.9, 0.3, "EXACT"),
        _ledger_entry("R3", 0.1, 0.9, "NORMALIZED"),
    ]
    first = compute_component_scores(jd, ledger, semantic_results=[])
    second = compute_component_scores(jd, list(ledger), semantic_results=[])
    assert first == second


def test_requirement_type_weighting_does_not_affect_experience_or_evidence_strength():
    """Type weighting only applies to keyword/semantic -- experience and
    evidence_strength must stay plain, unweighted means."""
    jd_all_required = _jd([("R1", "required"), ("R2", "required")])
    jd_all_preferred = _jd([("R1", "preferred"), ("R2", "preferred")])
    ledger = [_ledger_entry("R1", 0.5, 0.5, "SEMANTIC"), _ledger_entry("R2", 0.9, 0.1, "EXACT")]
    semantic_results = [
        {"candidate_id": "c", "requirement_id": "R1", "semantic_score": 0.5, "best_evidence_text": "x", "best_evidence_section": "experience"},
        {"candidate_id": "c", "requirement_id": "R2", "semantic_score": 0.1, "best_evidence_text": "y", "best_evidence_section": "projects"},
    ]

    breakdown_required = compute_component_scores(jd_all_required, ledger, semantic_results)
    breakdown_preferred = compute_component_scores(jd_all_preferred, ledger, semantic_results)

    assert breakdown_required["experience"] == breakdown_preferred["experience"]
    assert breakdown_required["evidence_strength"] == breakdown_preferred["evidence_strength"]
    # but keyword/semantic are identical here too, since both requirements
    # share the same type within each jd (uniform weighting == plain mean)
    assert breakdown_required["keyword"] == breakdown_preferred["keyword"]
