import json
from pathlib import Path

import pytest

from evidencerank.parsing import parse_jd, parse_resume
from evidencerank.keyword import extract_requirements, match_candidate, match_candidates, keyword_coverage

FIXTURES = Path(__file__).parent / "fixtures"


def requirement(skill, kind="required"):
    return {"id": "REQ001", "text": skill, "skill": skill, "type": kind}


def test_mock_extractor_contract_and_order():
    result = extract_requirements(parse_jd(FIXTURES / "jd_keyword.txt"))
    assert [r["skill"] for r in result["requirements"]] == ["React", "Backend APIs", "MongoDB", "Git", "Docker"]
    assert [r["type"] for r in result["requirements"]] == ["required"] * 4 + ["preferred"]
    assert [r["id"] for r in result["requirements"]] == [f"REQ{i:03}" for i in range(1, 6)]
    assert all(set(r) == {"id", "text", "skill", "type"} for r in result["requirements"])
    assert result == extract_requirements(parse_jd(FIXTURES / "jd_keyword.txt"))
    assert not result["warnings"]


def test_unspecified_priority_is_not_invented():
    result = extract_requirements("React, backend APIs, MongoDB, Git.")
    assert len(result["requirements"]) == 4
    assert all(r["type"] is None for r in result["requirements"])
    assert "priority_unspecified:REQ001" in result["warnings"]


def test_aliases_and_unseen_requirements():
    result = extract_requirements("Requirements:\nExperience with ReactJS and Mongo DB\nQuantum widgets\n3 years of Python")
    assert [r["skill"] for r in result["requirements"]] == ["React", "MongoDB", "Quantum widgets", "3 years of Python"]
    assert "review_requirement:REQ003" in result["warnings"]
    assert "review_requirement:REQ004" in result["warnings"]


def test_priority_resets_and_mixed_priorities():
    result = extract_requirements("Required:\nPython\nPreferred:\nDocker\nOther skills:\nGit\nReact required and MongoDB preferred")
    assert [r["type"] for r in result["requirements"]] == ["required", "preferred", None, "required", "preferred"]


def test_benefits_are_not_requirements():
    result = extract_requirements("Required: Python\nBenefits:\nFree lunch and coffee\nPreferred: Git")
    assert [r["skill"] for r in result["requirements"]] == ["Python", "Git"]


def test_alternatives_are_preserved_for_review():
    result = extract_requirements("Required: Python or Java")
    assert len(result["requirements"]) == 1
    assert result["requirements"][0]["skill"] == "Python or Java"
    assert "review_requirement:REQ001" in result["warnings"]
    assert match_candidate({"raw_text": "Python"}, result["requirements"])["requirements"][0]["keyword_score"] == 0


@pytest.mark.parametrize("text,kind", [("MongoDB", "EXACT"), ("mongo db", "NORMALIZED"), ("MONGODB", "EXACT"), ("mongo\nDB", "NORMALIZED")])
def test_exact_and_alias_matches(text, kind):
    row = match_candidate({"raw_text": text}, [requirement("MongoDB")])["requirements"][0]
    assert row["match_type"] == kind
    assert row["keyword_score"] == 100.0
    assert not row["not_explicitly_evidenced"]
    assert row["evidence"] in text
    for match in row["matches"]:
        assert text[match["start"]:match["end"]] == match["term"]


def test_false_positive_boundaries_and_no_semantic_inference():
    for skill, raw in [("Java", "JavaScript"), ("Git", "GitHub"), ("C++", "C"), ("Backend APIs", "Developed REST endpoints using Express")]:
        row = match_candidate({"raw_text": raw}, [requirement(skill)])["requirements"][0]
        assert row["match_type"] == "NOT_EVIDENCED"
        assert row["keyword_score"] == 0
        assert row["matched_terms"] == []


def test_repetition_does_not_inflate_score():
    row = match_candidate({"raw_text": "ReactJS React React ReactJS"}, [requirement("React")])["requirements"][0]
    assert row["keyword_score"] == 100
    assert row["match_type"] == "EXACT"


@pytest.mark.parametrize("raw", ["No experience with Python", "Python: no experience", "I have never used Python"])
def test_negative_mentions_do_not_count(raw):
    row = match_candidate({"raw_text": raw, "normalized_skills": ["Python"]}, [requirement("Python")])["requirements"][0]
    assert row["not_explicitly_evidenced"]
    assert "negated_mention_ignored" in row["warnings"]


def test_structured_fallback_has_explicit_provenance():
    row = match_candidate({"normalized_skills": ["MongoDB"]}, [requirement("MongoDB")])["requirements"][0]
    assert row["match_type"] == "NORMALIZED"
    assert row["evidence"] == ""
    assert row["matches"][0]["source"] == "normalized_skills"
    assert "raw_evidence_unavailable" in row["warnings"]


def test_numeric_qualifiers_are_not_dropped():
    reqs = extract_requirements("Required: 3 years of Python")["requirements"]
    assert match_candidate({"raw_text": "Python"}, reqs)["requirements"][0]["keyword_score"] == 0


def test_custom_lexicon_is_shared_by_extraction_and_matching(tmp_path):
    path = tmp_path / "lexicon.json"
    path.write_text(json.dumps({"ExampleDB": ["edb"]}))
    reqs = extract_requirements("Required: edb", config_path=path)["requirements"]
    assert reqs[0]["skill"] == "ExampleDB"
    assert match_candidate({"raw_text": "edb"}, reqs, config_path=path)["requirements"][0]["match_type"] == "NORMALIZED"


def test_end_to_end_person_a_objects_and_order():
    candidates = [parse_resume(FIXTURES / "resume_complete.txt"), parse_resume(FIXTURES / "resume_messy.txt")]
    reqs = extract_requirements(parse_jd(FIXTURES / "jd_keyword.txt"))["requirements"]
    results = match_candidates(candidates, reqs)
    assert [r["candidate_id"] for r in results] == [c["candidate_id"] for c in candidates]
    assert results[0]["requirements"][0]["match_type"] == "NORMALIZED"
    assert all(len(r["requirements"]) == 5 for r in results)
    assert "final_score" not in results[0]
    json.dumps(results)


def test_weighted_keyword_component():
    rows = [{"type": "required", "keyword_score": 100}, {"type": "preferred", "keyword_score": 0}]
    assert keyword_coverage(rows) == 50
    assert keyword_coverage(rows, weights={"required": 2, "preferred": 1, "unspecified": 1}) == pytest.approx(200 / 3)
    assert keyword_coverage([]) == 0


@pytest.mark.parametrize("weights", [{"required": -1, "preferred": 1, "unspecified": 1}, {"required": float("nan"), "preferred": 1, "unspecified": 1}, {"required": 0, "preferred": 0, "unspecified": 0}, {"required": 1}])
def test_bad_weights_rejected(weights):
    with pytest.raises(ValueError):
        keyword_coverage([{"type": "required", "keyword_score": 100}], weights=weights)


@pytest.mark.parametrize("score", [-1, 101, float("nan"), float("inf"), True])
def test_invalid_percentage_scores_rejected(score):
    with pytest.raises(ValueError, match="0,100"):
        keyword_coverage([{"type": "required", "keyword_score": score}])


def test_full_keyword_coverage_is_100():
    rows = match_candidate({"raw_text": "Mongo DB"}, [requirement("MongoDB")])["requirements"]
    assert keyword_coverage(rows) == 100.0


def test_empty_jd_and_duplicate_ids():
    assert extract_requirements("")["warnings"] == ["no_requirements_extracted"]
    with pytest.raises(ValueError):
        match_candidate({}, [requirement("Python"), requirement("Git")])


def test_negated_priority_is_not_marked_required():
    result = extract_requirements("Python is not required")
    assert result["requirements"][0]["type"] is None
    assert "review_requirement:REQ001" in result["warnings"]


def test_long_alias_takes_precedence_over_canonical_prefix():
    row = match_candidate({"raw_text": "React.js"}, [requirement("React")])["requirements"][0]
    assert row["match_type"] == "NORMALIZED"
    assert row["matched_terms"] == ["React.js"]
