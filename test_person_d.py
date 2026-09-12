import copy
import pytest
from mock_data import MOCK_CANDIDATES
from explanations import generate_top3_explanations, build_explanation
from comparison import compare
from jd_quality import detect_jd_issues
from validation import validate_ranking


def test_demo_explanations_return_three_without_mutating_input():
    candidates = copy.deepcopy(MOCK_CANDIDATES)
    assert len(generate_top3_explanations(candidates)) == 3
    assert candidates == MOCK_CANDIDATES


def test_missing_evidence_is_flagged():
    candidates = copy.deepcopy(MOCK_CANDIDATES)
    candidates[0]["requirements"][0]["evidence"] = None
    assert validate_ranking(candidates)["status"] == "REVIEW"


def test_equal_scores_described_as_tied():
    x, y = copy.deepcopy(MOCK_CANDIDATES[:2])
    y["final_score"] = x["final_score"]
    sentence = compare(x, y)["sentence"]
    assert "ranks above" not in sentence and "ranks below" not in sentence, sentence


def test_invalid_score_is_flagged():
    candidates = copy.deepcopy(MOCK_CANDIDATES)
    candidates[0]["final_score"] = 150
    candidates[0]["requirements"][0]["keyword_score"] = -20
    assert validate_ranking(candidates)["status"] == "REVIEW"


def test_incorrect_input_order_is_flagged():
    assert validate_ranking(list(reversed(MOCK_CANDIDATES)))["status"] == "REVIEW"


def test_strongest_exact_match_cites_evidence():
    candidate = copy.deepcopy(MOCK_CANDIDATES[0])
    candidate["requirements"] = [candidate["requirements"][0]]
    assert candidate["requirements"][0]["evidence"] in build_explanation(candidate)


def test_international_does_not_mean_intern():
    issues = detect_jd_issues("Senior engineer at an international company. Requires 5 years of experience.")
    assert not any(i["category"] == "Seniority mismatch" for i in issues), issues


def test_reaction_does_not_mean_react():
    issues = detect_jd_issues("Analyze chemical reaction rates.")
    assert not any(i["category"] == "Overly narrow tool requirement" for i in issues), issues


def test_multiline_age_phrase_detected():
    issues = detect_jd_issues("Seeking a recent\ngraduate.")
    assert any(i["category"] == "Potential age bias" for i in issues), issues


@pytest.mark.parametrize("score", [-1, 101, float("nan"), float("inf"), True, None])
def test_invalid_final_scores_never_pass(score):
    candidates = copy.deepcopy(MOCK_CANDIDATES)
    candidates[0]["final_score"] = score
    assert validate_ranking(candidates)["status"] == "REVIEW"


def test_empty_ranking_requires_review():
    assert validate_ranking([])["status"] == "REVIEW"


def test_valid_mock_scores_pass():
    assert validate_ranking(MOCK_CANDIDATES)["status"] == "PASS"


def test_validation_does_not_change_order_or_scores():
    candidates = copy.deepcopy(list(reversed(MOCK_CANDIDATES)))
    original = copy.deepcopy(candidates)
    validate_ranking(candidates)
    assert candidates == original


def test_duplicate_candidate_ids_require_review():
    candidates = copy.deepcopy(MOCK_CANDIDATES)
    candidates[1]["candidate_id"] = candidates[0]["candidate_id"]
    assert validate_ranking(candidates)["status"] == "REVIEW"


def test_real_junior_role_still_flags_high_experience():
    assert any(i["category"] == "Seniority mismatch" for i in detect_jd_issues("Junior engineer: 5 years of experience"))


def test_real_tool_still_detected():
    assert any(i["phrase"] == "React" for i in detect_jd_issues("React experience required"))


def test_explanation_missing_evidence_is_explicit():
    candidate = copy.deepcopy(MOCK_CANDIDATES[0])
    candidate["requirements"][0]["evidence"] = None
    assert "supporting evidence unavailable" in build_explanation(candidate)
