# EvidenceRank — Shared Data Contract (PROPOSED)

Status: **proposed by Person 3**, not yet confirmed by Person 1 or Person 2.
No implementation exists yet anywhere in this repo. This document plus
`schemas.py` are the only artifacts introduced so far.

Purpose: fix the interfaces between the four roles *before* anyone writes
matching/scoring code, so nobody builds against a guess that turns out wrong.

---

## 1. Pipeline

```
Person 1 (parsing)
   parse_jd(path)     -> ParsedJD
   parse_resume(path) -> ParsedResume
        |
        v
Person 2 (keyword / normalized matching)
   consumes: ParsedJD.requirements, ParsedResume
   produces: KeywordMatchResult   (one per candidate x requirement)
        |
        v
Person 3 (semantic matching, evidence ledger, final ranking)  <- you are here
   consumes: ParsedJD, ParsedResume, KeywordMatchResult
   internal: SemanticMatchResult  (own component, not shared upstream)
   produces: CandidateResult      (one per candidate, includes Evidence Ledger)
        |
        v
Person 4 (app / UI)
   consumes: List[CandidateResult], ranked best-to-worst
```

## 2. Schemas

All types are defined as `TypedDict`s in `schemas.py` (stdlib `typing` only,
no extra dependency). Summary:

### `parse_jd(path) -> ParsedJD`
```
{
  "raw_text": str,
  "requirements": [
    {"id": str, "text": str, "skill": str, "type": "required" | "preferred"},
    ...
  ]
}
```

### `parse_resume(path) -> ParsedResume`
```
{
  "candidate_id": str,
  "candidate_name": str,
  "raw_text": str,
  "sections": {
    "skills": [str, ...],
    "experience": [str, ...],
    "projects": [str, ...],
    "education": [str, ...],
    "certifications": [str, ...]
  },
  "normalized_skills": [str, ...],
  "warnings": [str, ...]
}
```

### Person 2 output — `KeywordMatchResult` (one per candidate × requirement)
```
{
  "candidate_id": str,
  "requirement_id": str,
  "keyword_score": float,          # 0.0-1.0
  "matched_terms": [str, ...],
  "normalized_match": str | None
}
```

### Person 3 internal — `SemanticMatchResult` (not shared upstream)
```
{
  "candidate_id": str,
  "requirement_id": str,
  "semantic_score": float,          # cosine similarity, 0.0-1.0
  "best_evidence_text": str,
  "best_evidence_section": str      # which resume section it came from
}
```

### Person 3 output — `CandidateResult` (final, consumed by Person 4)
```
{
  "candidate_id": str,
  "candidate_name": str,
  "final_score": float,             # 0-100
  "score_breakdown": {
    "keyword": float, "semantic": float,
    "experience": float, "evidence_strength": float   # each 0-100
  },
  "requirements": [
    {
      "id": str, "text": str,
      "keyword_score": float, "semantic_score": float,
      "match_type": "EXACT" | "NORMALIZED" | "SEMANTIC" | "NOT_EVIDENCED",
      "evidence": str            # verbatim resume text, "" if NOT_EVIDENCED
    },
    ...
  ]
}
```

### Scoring function (contract only, not yet implemented)
```
compute_final_score(component_scores: dict, weights: dict = DEFAULT_WEIGHTS) -> float
```
- `component_scores` keys: `keyword`, `semantic`, `experience`, `evidence_strength` (each 0-100).
- `weights` defaults: `semantic=0.40, keyword=0.35, experience=0.15, evidence_strength=0.10`.
- Pure function: no I/O, no randomness, no hidden state.

## 3. Decisions Person 1 must confirm

1. **Section granularity**: are `sections.experience` / `sections.projects` / etc.
   lists of *chunks* (one bullet point or sentence per list item), or a single
   raw string per section? Person 3's semantic matcher needs chunk-level lists
   to retrieve "best evidence" per requirement rather than matching against an
   entire blob. `schemas.py` currently assumes `List[str]` per section.
2. **`normalized_skills` definition**: what normalization is applied (lowercasing
   only? alias table, e.g. "js" -> "javascript"? stemming?). Person 2's
   `normalized_match` and Person 3's NORMALIZED match type both depend on this
   being consistent and documented.
3. **`requirements[].skill`**: confirm this is always a single canonical token
   (not a phrase), since Person 3 uses it for NORMALIZED-tier comparison against
   `normalized_skills`.
4. **Encoding/language assumptions**: any non-English or malformed-PDF handling
   that produces `warnings` — Person 3 will skip/flag candidates with warnings
   rather than silently scoring bad extractions, but needs to know what warning
   strings to expect (or if `warnings` is currently unused/always `[]`).

## 4. Decisions Person 2 must confirm

1. **`keyword_score` scale**: confirm 0.0-1.0 (not 0-100 or raw count). Person 3's
   35%-weight component assumes this scale and will convert to 0-100 internally.
2. **`normalized_match` semantics**: confirm it is `None` when there is no match
   at all (as opposed to `""` or omitted), and that it holds the *matched
   normalized string* (not a boolean) when a normalized/alias match occurred.
   This directly drives Person 3's EXACT vs NORMALIZED classification:
   - `matched_terms` non-empty with a literal substring match -> EXACT
   - `normalized_match` set (no literal match) -> NORMALIZED
   - neither, but semantic similarity clears a threshold -> SEMANTIC
   - neither -> NOT_EVIDENCED
3. **One result per requirement, always present**: confirm Person 2 emits a
   `KeywordMatchResult` for every `(candidate_id, requirement_id)` pair, even
   when there's no match (`keyword_score=0.0, matched_terms=[], normalized_match=None`),
   rather than omitting rows — Person 3's ledger builder needs a complete pairing
   to avoid silently dropping requirements.

## 5. Explicitly out of scope for Person 3 (per role boundaries)

- No UI/app code.
- No recruiter Q&A feature.
- No dependencies beyond what semantic matching requires
  (`sentence-transformers` + its transitive deps, e.g. `torch`, `numpy`).
- No changes to Person 1/2's internal implementation — only consumption of
  the interfaces above.

## 6. Not yet decided (Person 3's own open items, flagged for visibility)

- Semantic similarity threshold for SEMANTIC vs NOT_EVIDENCED classification
  (to be a named constant, not tuned per-candidate).
- Exact formula for `experience` (15%) and `evidence_strength` (10%) components
  — both are computed entirely from Person 1/3's own data (resume sections +
  the ledger itself), so they don't require Person 1/2 sign-off, but will be
  documented alongside the implementation for review.

---

**Nothing beyond this document and `schemas.py` has been created.** Semantic
matcher, evidence ledger builder, scorer, and ranker implementations are
pending your approval.
