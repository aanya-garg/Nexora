import copy
from pathlib import Path
import pytest
from pipeline import analyze_candidates, rescore_candidates
from scoring import compute_final_score, DEFAULT_WEIGHTS
from semantic_matcher import SentenceTransformerEmbedder

FIXTURES = Path(__file__).parent / "fixtures"


def test_full_abcd_pipeline_public_scale_and_provenance(fake_embedder):
    bundle = analyze_candidates(FIXTURES / "jd_keyword.txt", [FIXTURES / "resume_complete.txt", FIXTURES / "resume_messy.txt"], embedder=fake_embedder)
    assert len(bundle["ranked_candidates"]) == 2
    assert len(bundle["top3_explanations"]) == 2
    maya = next(c for c in bundle["ranked_candidates"] if c["candidate_name"] == "Maya Kapoor")
    react = next(r for r in maya["requirements"] if r["text"] == "React")
    assert react["keyword_score"] == 100
    assert react["match_type"] == "NORMALIZED"
    assert "React.js" in react["evidence"]
    assert react["evidence"] in (FIXTURES / "resume_complete.txt").read_bytes().decode()
    assert all(0 <= r["semantic_score"] <= 100 for c in bundle["ranked_candidates"] for r in c["requirements"])


def test_ui_rescore_avoids_mutation(fake_embedder):
    candidates = analyze_candidates(FIXTURES / "jd_keyword.txt", [FIXTURES / "resume_complete.txt"], embedder=fake_embedder)["ranked_candidates"]
    original = copy.deepcopy(candidates)
    result = rescore_candidates(candidates, {"keyword": 1, "semantic": 0, "experience": 0, "evidence_strength": 0})
    assert result[0]["final_score"] == result[0]["score_breakdown"]["keyword"]
    assert candidates == original


def test_missing_jd_is_an_error(fake_embedder):
    with pytest.raises(ValueError, match="JD has no readable"):
        analyze_candidates(FIXTURES / "missing.pdf", [], embedder=fake_embedder)


def test_unreadable_and_duplicate_documents_reported(fake_embedder):
    path = FIXTURES / "resume_complete.txt"
    bundle = analyze_candidates(FIXTURES / "jd_keyword.txt", [path, path, FIXTURES / "missing.pdf"], embedder=fake_embedder)
    assert len(bundle["ranked_candidates"]) == 1
    assert len(bundle["excluded_documents"]) == 2


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1])
def test_invalid_slider_weights_rejected(value):
    weights = dict(DEFAULT_WEIGHTS, keyword=value)
    with pytest.raises(ValueError):
        compute_final_score(dict.fromkeys(DEFAULT_WEIGHTS, 50), weights)


def test_model_never_downloads_at_runtime(monkeypatch):
    import sys
    import types
    calls = []
    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=lambda *a, **k: calls.append(k)))
    SentenceTransformerEmbedder()
    assert calls == [{"local_files_only": True}]
