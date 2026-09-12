from evidence_ledger import (
    SEMANTIC_MATCH_THRESHOLD,
    build_ledger,
    classify_match_type,
)
from factories import make_keyword_result


def _kw(matched_terms=None, normalized_match=None, keyword_score=0.0):
    return make_keyword_result("c1", "REQ001", keyword_score=keyword_score, matched_terms=matched_terms, normalized_match=normalized_match)


def _sem(score=0.0, text="", section=""):
    return {
        "candidate_id": "c1",
        "requirement_id": "REQ001",
        "semantic_score": score,
        "best_evidence_text": text,
        "best_evidence_section": section,
    }


def test_classify_exact_takes_priority_over_everything_else():
    kw = _kw(matched_terms=["Python"], keyword_score=1.0)
    sem = _sem(score=0.0)
    assert classify_match_type(kw, sem) == "EXACT"


def test_classify_normalized_when_no_literal_term():
    kw = _kw(matched_terms=[], normalized_match="python", keyword_score=0.6)
    sem = _sem(score=0.0)
    assert classify_match_type(kw, sem) == "NORMALIZED"


def test_classify_semantic_when_no_keyword_evidence_but_score_above_threshold():
    kw = _kw()
    sem = _sem(score=SEMANTIC_MATCH_THRESHOLD)
    assert classify_match_type(kw, sem) == "SEMANTIC"


def test_classify_not_evidenced_when_score_below_threshold():
    kw = _kw()
    sem = _sem(score=SEMANTIC_MATCH_THRESHOLD - 0.01)
    assert classify_match_type(kw, sem) == "NOT_EVIDENCED"


def test_threshold_is_exactly_0_35():
    assert SEMANTIC_MATCH_THRESHOLD == 0.35


def test_semantic_score_of_0_35_classifies_as_semantic():
    kw = _kw()
    sem = _sem(score=0.35)
    assert classify_match_type(kw, sem) == "SEMANTIC"


def test_semantic_score_just_below_0_35_classifies_as_not_evidenced():
    kw = _kw()
    sem = _sem(score=0.349999)
    assert classify_match_type(kw, sem) == "NOT_EVIDENCED"


def test_classify_exact_overrides_semantic_even_with_high_semantic_score():
    """EXACT must win even when the semantic score would independently
    clear the SEMANTIC threshold -- keyword evidence always takes priority."""
    kw = _kw(matched_terms=["Python"], keyword_score=1.0)
    sem = _sem(score=0.95)
    assert classify_match_type(kw, sem) == "EXACT"


def test_classify_normalized_overrides_semantic_even_with_high_semantic_score():
    """NORMALIZED must win over SEMANTIC even when the semantic score is high,
    as long as there's no literal matched term (which would make it EXACT)."""
    kw = _kw(matched_terms=[], normalized_match="python", keyword_score=0.6)
    sem = _sem(score=0.95)
    assert classify_match_type(kw, sem) == "NORMALIZED"


def test_below_threshold_semantic_score_still_feeds_the_semantic_component():
    """A NOT_EVIDENCED requirement (semantic_score below threshold) must
    still contribute its raw semantic_score to the ledger entry -- the
    threshold only changes match_type, never the stored score."""
    kw = _kw()
    sem = _sem(score=0.20)
    match_type = classify_match_type(kw, sem)
    assert match_type == "NOT_EVIDENCED"

    from evidence_ledger import build_evidence_entry

    requirement = {"id": "REQ001", "text": "text", "skill": "python", "type": "required"}
    entry = build_evidence_entry(requirement, kw, sem, resume_chunks=[])
    assert entry["match_type"] == "NOT_EVIDENCED"
    assert entry["semantic_score"] == 0.20  # unchanged, not zeroed out


def test_build_ledger_produces_one_entry_per_requirement_in_order(sample_jd, resume_strong, keyword_results_strong, fake_embedder):
    from semantic_matcher import compute_semantic_matches

    semantic_results = compute_semantic_matches(sample_jd, resume_strong, embedder=fake_embedder)
    ledger = build_ledger(sample_jd, resume_strong, keyword_results_strong, semantic_results)

    assert [entry["id"] for entry in ledger] == [r["id"] for r in sample_jd["requirements"]]
    assert all(set(entry.keys()) == {"id", "text", "keyword_score", "semantic_score", "match_type", "evidence"} for entry in ledger)


def test_build_ledger_exact_matches_have_real_evidence_text(sample_jd, resume_strong, keyword_results_strong, fake_embedder):
    from semantic_matcher import compute_semantic_matches

    semantic_results = compute_semantic_matches(sample_jd, resume_strong, embedder=fake_embedder)
    ledger = build_ledger(sample_jd, resume_strong, keyword_results_strong, semantic_results)
    by_id = {e["id"]: e for e in ledger}

    assert by_id["REQ001"]["match_type"] == "EXACT"
    assert "python" in by_id["REQ001"]["evidence"].lower()
    # evidence must be verbatim text that really appears in the resume
    all_chunks = [c for chunks in resume_strong["sections"].values() for c in chunks]
    assert by_id["REQ001"]["evidence"] in all_chunks


def test_build_ledger_not_evidenced_requirement_has_empty_evidence(sample_jd, resume_strong, keyword_results_strong, fake_embedder):
    from semantic_matcher import compute_semantic_matches

    semantic_results = compute_semantic_matches(sample_jd, resume_strong, embedder=fake_embedder)
    ledger = build_ledger(sample_jd, resume_strong, keyword_results_strong, semantic_results)
    by_id = {e["id"]: e for e in ledger}

    assert by_id["REQ005"]["match_type"] == "NOT_EVIDENCED"
    assert by_id["REQ005"]["evidence"] == ""


def test_build_ledger_normalized_match_evidence_is_verbatim(sample_jd, resume_weak, keyword_results_weak, fake_embedder):
    from semantic_matcher import compute_semantic_matches

    semantic_results = compute_semantic_matches(sample_jd, resume_weak, embedder=fake_embedder)
    ledger = build_ledger(sample_jd, resume_weak, keyword_results_weak, semantic_results)
    by_id = {e["id"]: e for e in ledger}

    assert by_id["REQ004"]["match_type"] == "NORMALIZED"
    assert by_id["REQ004"]["evidence"] != ""
    all_chunks = [c for chunks in resume_weak["sections"].values() for c in chunks]
    assert by_id["REQ004"]["evidence"] in all_chunks


def test_build_ledger_defaults_missing_keyword_result_to_no_match(sample_jd, resume_strong, fake_embedder):
    """If Person 2 hasn't supplied a result for some requirement, the ledger
    must still produce a complete row rather than crashing or omitting it."""
    from semantic_matcher import compute_semantic_matches

    semantic_results = compute_semantic_matches(sample_jd, resume_strong, embedder=fake_embedder)
    ledger = build_ledger(sample_jd, resume_strong, keyword_results=[], semantic_results=semantic_results)

    assert len(ledger) == len(sample_jd["requirements"])
    for entry in ledger:
        assert entry["keyword_score"] == 0.0
