# Person D: explanations, comparisons, JD checks and validation

This branch (`person-d-explainability`) contains all six files uploaded to main at a5dab1d, plus reviewed fixes and regression tests. The sample dataset in mock_data.py is unchanged. Replace it with Person C's real ranked output once available.

## Run

```sh
python demo.py
python -m pip install pytest
python -m pytest -q
```

Runtime uses only the Python standard library. No LLM or external API calls.

## Integration

All final, component, keyword and semantic scores are on **0–100**. Person B's updated keyword branch already returns this scale; do not multiply those scores by 100 again.

Call `validate_ranking(ranked_candidates)` before generating explanations. Review warnings before showing results. Call `generate_top3_explanations(ranked_candidates)`, `compare(candidate_x, candidate_y)`, and `detect_jd_issues(jd_clean_text)` for the corresponding features. These functions consume Person C's completed ledger, not Person B's intermediate keyword results.

The required candidate fields are `candidate_id`, `candidate_name`, `final_score`, `score_breakdown` (keyword, semantic, experience, evidence_strength), and `requirements`. Each requirement supplies id, text, keyword_score, semantic_score, match_type and evidence. Evidence can be null for NOT_EVIDENCED. Inputs must follow this structure; this is not a general malformed-JSON validator.

## Reviewed fixes

- Equal displayed scores are described as tied.
- Strongest matches quote their stored evidence; absent evidence explicitly requires review.
- Semantic highlights describe weaker literal matching instead of claiming the keyword is wholly absent.
- Validation flags invalid/nonfinite scores, missing score components, duplicate candidate IDs, incorrect ranking order and empty input. It does not mutate candidates or adjust scores.
- Low score spread prompts evidence review without suggesting scores should be altered for presentation.
- JD patterns respect word boundaries: international is not intern, reaction is not React. Multiword age phrases tolerate line breaks.

JD flags are heuristic review suggestions. Validation checks consistency of the supplied ledger; it cannot prove a quotation exists in a resume unless upstream evidence provenance is checked. Sample data is appropriate for development, but real-data integration and human review are still needed.

Main's existing uploaded files remain on main. Merge this branch to apply fixes there; no files were deleted from main.
