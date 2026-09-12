"""Small helpers for building mock KeywordMatchResult objects in tests."""


def make_keyword_result(candidate_id, requirement_id, keyword_score=0.0, matched_terms=None, normalized_match=None):
    return {
        "candidate_id": candidate_id,
        "requirement_id": requirement_id,
        "keyword_score": keyword_score,
        "matched_terms": matched_terms or [],
        "normalized_match": normalized_match,
    }
