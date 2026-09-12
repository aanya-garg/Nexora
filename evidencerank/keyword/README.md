# Person B — JD requirements and explicit matching

Implemented by Person A while covering Person B's work. Person A remains the user's team role. Branch: `person-b-keyword`, based on `person-a-parsing` so integration can run immediately. Merge Person A before Person B, or merge this branch including its parser ancestor commits.

This module follows the Person 2 section of EvidenceRank_Final_Plan.pdf: atomic requirements, controlled aliases, exact/normalized matches, per-requirement scores, explicit terms, and tests. It does not implement Person C's semantic matching, final score formula or ranking, Person D's explanations, or UI.

## Install and run

From the repository root:

```sh
python -m pip install -e ".[test]"
python -m pytest -q
python -m examples.keyword_demo
```

```python
from evidencerank.parsing import parse_jd, parse_resume
from evidencerank.keyword import (
    extract_requirements, match_candidates, keyword_coverage,
)

jd = parse_jd("job.pdf")
extracted = extract_requirements(jd)
requirements = extracted["requirements"]
# Review extracted["warnings"] and the requirements before using real hiring data.
candidates = [parse_resume(path) for path in ["one.pdf", "two.pdf"]]
keyword_results = match_candidates(candidates, requirements)
keyword_component = keyword_coverage(keyword_results[0]["requirements"])
```

The synthetic demo uses two actual Person A fixture parses and a third in-memory candidate. It prints all requirement evidence plus keyword components, preserving input candidate order.

## Contract for Person C

`extract_requirements(text_or_parsed_jd)` returns `{requirements, warnings}`. Requirements contain exactly `{id, text, skill, type}`. IDs are `REQ001`, `REQ002`, etc., stable for identical input; reordered/edited requirements may be renumbered. They are not persistent database identities. Duplicate identical fragments with the same priority are deduplicated.

**Priority clarification:** the PDF permits only `required|preferred` but also forbids inventing priority. Unspecified or conflicting wording therefore returns `type: None` (JSON `null`) and a warning. Do not coerce it to required. This is a deliberate contract extension; downstream consumers must accept null or a human must resolve those entries first. Explicit headings and wording support required/preferred status; unknown colon headings reset inherited priority.

`match_candidate(candidate, requirements)` returns `{candidate_id, candidate_name, requirements}`. `match_candidates(...)` returns these objects in the original candidate order. Every output requirement retains its input fields and adds:

- `keyword_score`: 0.0 or 100.0. Exact and safe-alias matches are equally credited. Frequency never increases the score.
- `match_type`: `EXACT`, `NORMALIZED`, or `NOT_EVIDENCED`. Person C adds semantic matches later.
- `matched_terms`: deduplicated actual matching strings.
- `matches`: source, actual term, match type, and zero-based, end-exclusive raw-text offsets. Every raw-text match can be verified with `raw_text[start:end]`.
- `evidence`: an original resume line (or multiple lines when the matched term wraps), never generated prose. Empty when unavailable.
- `not_explicitly_evidenced`: boolean; this is absence of literal evidence, not a claim about candidate ability.
- `warnings`: ignored negated mentions or missing raw evidence.

EXACT means a case-insensitive literal occurrence of the canonical `skill` field, allowing whitespace differences. NORMALIZED means a configured alternative such as Mongo DB -> MongoDB or React.js -> React. Longer aliases take precedence over contained canonical names. The matcher never treats REST/Express as Backend APIs through semantic inference.

The parser's `normalized_skills` is a fallback only when raw text is unavailable. Such a result explicitly records `source: normalized_skills`, null offsets, empty evidence and `raw_evidence_unavailable`. Structured mentions never override contradictory raw text.

`keyword_coverage(rows, weights=...)` computes only an optional weighted average of keyword scores on **0–100**, matching Person D's score scale. Person C should keep all components and final scores on 0–100; do not multiply these keyword outputs by 100 again. For example, one matched and one unmatched equally weighted requirement returns 50.0. Recompute any cached outputs from the earlier 0–1 version before integration. It does not apply the plan's final 40/35/15/10 formula. Weights live in `weights.json`; equal defaults avoid inventing importance. A caller can explicitly supply `{"required": 2, "preferred": 1, "unspecified": 1}`. These weights are relative multipliers, not scores. Invalid/nonfinite/negative weights, all-zero effective weights, and out-of-range scores raise errors. Empty requirements return 0.0; extraction also warns on an empty JD.

## Configuration and review limits

Both Person A and Person B use `evidencerank/parsing/technology_aliases.json`. This branch adds MongoDB/Mongo DB and Backend APIs/backend API to that single shared file. No duplicate technology dictionary was introduced. Extraction and matching accept an optional `config_path` override; pass the same override to both. Invalid or ambiguous aliases raise errors.

Extraction is deliberately rule-based: common headings, bullets, comma/and lists and sentences are supported. Generic lead-ins such as "experience with" are removed from the matching phrase. Unknown phrases, experience/degree constraints and OR alternatives remain intact and get `review_requirement` warnings rather than being silently dropped or reduced to one technology. OR alternatives do not become two mandatory requirements. Non-requirement headings such as Benefits are skipped. Unknown titles/prose can remain as reviewable entries; this is not a language model and does not understand every JD layout or compound phrase.

Quantified phrases only receive an exact phrase match: mentioning Python alone does not satisfy "3 years of Python". String matching does not verify employment durations or candidate claims. Basic local negation patterns avoid crediting "no experience with Python"; complex negation and mixed clauses can be ambiguous and require review. No automated hiring decisions should be inferred from these component outputs.

Review the extracted requirement list on the real JD before Person C consumes it. All processing runs locally and deterministically, with no model or API calls.
