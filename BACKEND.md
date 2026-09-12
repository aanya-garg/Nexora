# Backend integration handoff

Branch: integration/backend-ready. Combines Person C's integration/person3-complete with updated A (DOCX/XML) and D (fixes and training loader). Person B's 0–100 changes are already included in C's branch. Main is not changed by this integration.

## Setup

From this checkout, install dependencies and explicitly cache the model once while online:

```powershell
python -m pip install -e ".[test,semantic]"
python setup_model.py
python -m pytest -q
```

The integration was tested locally with deterministic test embeddings. Real-model checks skip when sentence-transformers/model weights are missing; a passing suite with those skips is not verification of real semantic behavior. Runtime uses local_files_only=True and never downloads a model. No fake embedder is selected automatically.

## Frontend API

```python
from pipeline import analyze_candidates, rescore_candidates

bundle = analyze_candidates(jd_path, resume_paths)
ranked = bundle["ranked_candidates"]
reranked = rescore_candidates(ranked, {
    "semantic": .40, "keyword": .35,
    "experience": .15, "evidence_strength": .10,
})
```

The bundle includes ranked_candidates, top3_explanations, requirements, jd_warnings, parsing_warnings, excluded_documents, jd_issues and validation. Show extraction/review warnings to the user. Empty/unreadable JDs and a completely unreadable candidate set raise ValueError. Unreadable resumes and identical-byte duplicate documents are listed under excluded_documents, not silently scored. Different file formats of the same person are not automatically merged.

All public scores (including each ledger row) are **0–100**. The private C matching/ledger calculations use fractions before score_candidate converts the public result. Do not multiply public outputs by 100. Top-level defaults remain 40/35/15/10; C's explicit required/preferred weights remain 2:1, with unspecified priority weight 1. The public keyword component therefore uses C's configured weighting, not Person B's standalone equal-weight convenience average.

Keyword evidence is passed directly from B to C. Semantic chunks recover original source whitespace, and the pipeline verifies all returned evidence occurs in raw_text. Unclassified raw lines remain available for matching when headings are missing. Validation never changes scores to create a more attractive spread.

## Training and readiness

The supplied ZIP contains 220 resume documents and no job description. It is local data, not committed. Prepare it with training_data.py as documented in PERSON_D.md, then select the intended candidate documents. The final host JD is still needed for a meaningful evaluation. A deliberately labelled synthetic JD can be used for development; never present those scores as host-task results.

UI construction can begin against the API above. Before claiming the full application works, install/cache the real model, run the non-skipped semantic tests and run analyze_candidates on a chosen JD plus representative training resumes. Real scoring performance, threshold quality and parsing accuracy still need human review on those inputs. Unit tests cannot guarantee absence of all faults.
