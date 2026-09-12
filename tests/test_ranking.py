from ranking import rank_candidates


def _candidate(candidate_id, final_score, semantic=0.0, keyword=0.0, evidence_strength=0.0, experience=0.0):
    return {
        "candidate_id": candidate_id,
        "candidate_name": candidate_id,
        "final_score": final_score,
        "score_breakdown": {
            "keyword": keyword,
            "semantic": semantic,
            "experience": experience,
            "evidence_strength": evidence_strength,
        },
        "requirements": [],
    }


def test_rank_candidates_sorts_by_final_score_descending():
    candidates = [_candidate("a", 50.0), _candidate("b", 90.0), _candidate("c", 70.0)]
    ranked = rank_candidates(candidates)
    assert [c["candidate_id"] for c in ranked] == ["b", "c", "a"]


def test_rank_candidates_empty_list_returns_empty_list():
    assert rank_candidates([]) == []


def test_rank_candidates_single_candidate():
    candidates = [_candidate("solo", 42.0)]
    assert rank_candidates(candidates) == candidates


def test_rank_candidates_tie_break_by_semantic_score():
    candidates = [
        _candidate("low_semantic", 80.0, semantic=50.0),
        _candidate("high_semantic", 80.0, semantic=90.0),
    ]
    ranked = rank_candidates(candidates)
    assert [c["candidate_id"] for c in ranked] == ["high_semantic", "low_semantic"]


def test_rank_candidates_tie_break_falls_through_to_candidate_id():
    candidates = [
        _candidate("zeta", 80.0, semantic=50.0, keyword=50.0, evidence_strength=50.0, experience=50.0),
        _candidate("alpha", 80.0, semantic=50.0, keyword=50.0, evidence_strength=50.0, experience=50.0),
    ]
    ranked = rank_candidates(candidates)
    assert [c["candidate_id"] for c in ranked] == ["alpha", "zeta"]


def test_rank_candidates_is_deterministic_regardless_of_input_order():
    candidates = [_candidate("a", 50.0), _candidate("b", 90.0), _candidate("c", 70.0)]
    reversed_input = list(reversed(candidates))
    assert rank_candidates(candidates) == rank_candidates(reversed_input)


def test_rank_candidates_does_not_mutate_input_list():
    candidates = [_candidate("a", 50.0), _candidate("b", 90.0)]
    original_order = list(candidates)
    rank_candidates(candidates)
    assert candidates == original_order
