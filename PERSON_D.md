# Person D: explanations, comparisons, JD checks and validation

This branch (`person-d-explainability`) contains Person D's modules plus reviewed fixes and regression tests. The demo now uses the host training dataset. The former mock_data.py is renamed synthetic_test_data.py and used only for regression tests, never as live results.

## Run

```sh
python demo.py
python -m pip install pytest
python -m pytest -q
```

Runtime uses only the Python standard library. No LLM or external API calls.

Training preparation additionally requires Person A's updated parsing package (commit 21de7ec or later) and pypdf. Install that checkout with `python -m pip install -e PATH_TO_PERSON_A_CHECKOUT`, or integrate Person A's branch first.

```sh
python training_data.py PATH_TO_TRAINING_ZIP --output data/training
python demo.py
python demo.py --ranked PATH_TO_PERSON_C_RESULTS.json --jd PATH_TO_JD.txt
```

The supplied archive contains 220 resume documents, with multiple formats/versions of some resumes, and no JD or ranked ledger. All 220 produced text locally. The loader retains every document, source filename, parser candidate ID and warnings in data/training/parsed_resumes.json. It does not infer unique people, remove duplicates, generate rankings, or invent scores. Person C should select/deduplicate the intended candidate documents explicitly before ranking; filenames alone are not reliable person identities.

`demo.py` defaults to the training bundle and reports that scoring is pending unless `--ranked` is provided. Ranked IDs must belong to this dataset and scores must pass Person D's validation before explanations are shown. The JD should be the one used to score the ledger. Raw resumes and parsed personal data are excluded from Git by data/ in .gitignore. Teammates prepare their local copy from the same ZIP. Keep future final-testing data in a separate directory and pass its prepared input explicitly; the current loader marks its output as training.

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
