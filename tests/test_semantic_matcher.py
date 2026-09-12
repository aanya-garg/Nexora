import pytest

from semantic_matcher import compute_semantic_matches, flatten_resume_chunks


def test_flatten_resume_chunks_skips_blank_entries():
    resume = {
        "candidate_id": "c1",
        "candidate_name": "X",
        "raw_text": "",
        "sections": {
            "skills": ["Python", "  ", ""],
            "experience": ["Did things.", "\n"],
            "projects": [],
            "education": [],
            "certifications": [],
        },
        "normalized_skills": [],
        "warnings": [],
    }
    chunks = flatten_resume_chunks(resume)
    assert chunks == [
        ("skills", "Python"),
        ("experience", "Did things."),
    ]


def test_compute_semantic_matches_picks_best_chunk_per_requirement(sample_jd, resume_strong, fake_embedder):
    results = compute_semantic_matches(sample_jd, resume_strong, embedder=fake_embedder)

    assert len(results) == len(sample_jd["requirements"])
    by_req = {r["requirement_id"]: r for r in results}

    python_match = by_req["REQ001"]
    assert python_match["candidate_id"] == "cand-1"
    assert python_match["semantic_score"] > 0.0
    assert "python" in python_match["best_evidence_text"].lower()
    # under the bag-of-words fake embedder, the single-word "Python" skills
    # chunk is a perfect (score 1.0) match for the single-word overlap in the
    # requirement text, beating the longer, more diluted experience bullet.
    assert python_match["best_evidence_section"] == "skills"
    assert python_match["semantic_score"] == 1.0

    sql_match = by_req["REQ004"]
    assert "sql" in sql_match["best_evidence_text"].lower()
    assert sql_match["best_evidence_section"] == "skills"


def test_compute_semantic_matches_no_overlap_still_returns_best_available(sample_jd, resume_weak, fake_embedder):
    results = compute_semantic_matches(sample_jd, resume_weak, embedder=fake_embedder)
    by_req = {r["requirement_id"]: r for r in results}

    # No word-overlap at all for "docker" against a Java/Spring/MySQL resume ->
    # score should be exactly 0 under the bag-of-words fake embedder, but a
    # chunk is still returned (never silently dropped).
    docker_match = by_req["REQ003"]
    assert docker_match["semantic_score"] == 0.0
    assert docker_match["best_evidence_text"] != ""


def test_compute_semantic_matches_empty_resume_returns_zero_scores(sample_jd, resume_empty, fake_embedder):
    results = compute_semantic_matches(sample_jd, resume_empty, embedder=fake_embedder)

    assert len(results) == len(sample_jd["requirements"])
    for r in results:
        assert r["semantic_score"] == 0.0
        assert r["best_evidence_text"] == ""
        assert r["best_evidence_section"] == ""


def test_compute_semantic_matches_empty_requirements_returns_empty_list(resume_strong, fake_embedder):
    empty_jd = {"raw_text": "", "requirements": []}
    assert compute_semantic_matches(empty_jd, resume_strong, embedder=fake_embedder) == []


def test_compute_semantic_matches_scores_are_clamped_to_unit_interval(sample_jd, resume_strong, fake_embedder):
    results = compute_semantic_matches(sample_jd, resume_strong, embedder=fake_embedder)
    for r in results:
        assert 0.0 <= r["semantic_score"] <= 1.0


def test_real_model_loads_and_produces_sane_scores(sample_jd, resume_strong):
    """Integration check against the real all-MiniLM-L6-v2 model. Skipped
    automatically if the model/weights aren't available locally (e.g. no
    network access to download from Hugging Face on first use), since the
    rest of the suite already exercises all matching/scoring/ranking logic
    with a fake embedder and does not depend on this test.
    """
    try:
        from semantic_matcher import get_default_embedder

        get_default_embedder.cache_clear()
        embedder = get_default_embedder()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"real embedding model unavailable in this environment: {exc}")

    results = compute_semantic_matches(sample_jd, resume_strong, embedder=embedder)
    by_req = {r["requirement_id"]: r for r in results}

    # The Python requirement should retrieve a chunk that actually mentions
    # Python, with a non-trivial similarity score.
    python_match = by_req["REQ001"]
    assert "python" in python_match["best_evidence_text"].lower()
    assert python_match["semantic_score"] > 0.3


def _get_real_embedder_or_skip():
    try:
        from semantic_matcher import get_default_embedder

        get_default_embedder.cache_clear()
        return get_default_embedder()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"real embedding model unavailable in this environment: {exc}")


def test_manual_semantic_sanity_check_related_pairs_score_higher_than_unrelated():
    """Hand-picked JD/resume-sentence pairs, scored with the real
    all-MiniLM-L6-v2 model, to sanity-check that semantically related text
    scores meaningfully higher than clearly unrelated text. Skipped if the
    real model isn't available in this environment (see
    test_real_model_loads_and_produces_sane_scores above).
    """
    embedder = _get_real_embedder_or_skip()
    from semantic_matcher import _cosine_similarity_matrix

    related_rest_api = (
        "Experience building REST APIs with Python",
        "Developed backend services using FastAPI and Python.",
    )
    related_ml = (
        "Machine learning experience",
        "Built classification models using scikit-learn.",
    )
    unrelated = (
        "React frontend development",
        "Designed PostgreSQL database schemas.",
    )

    pairs = [related_rest_api, related_ml, unrelated]
    jd_vectors = embedder.encode([p[0] for p in pairs])
    resume_vectors = embedder.encode([p[1] for p in pairs])
    similarity = _cosine_similarity_matrix(jd_vectors, resume_vectors)

    rest_api_score = float(similarity[0][0])
    ml_score = float(similarity[1][1])
    unrelated_score = float(similarity[2][2])

    # Both genuinely related pairs must clearly outscore the unrelated pair.
    assert rest_api_score > unrelated_score + 0.2
    assert ml_score > unrelated_score + 0.1
    # The unrelated pair (frontend vs. database schemas) should sit low.
    assert unrelated_score < 0.3
