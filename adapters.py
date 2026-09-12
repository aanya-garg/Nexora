"""
Translation layer between Person 1/Person 2's actual, real output shapes and
the canonical schemas.py contract Person 3's modules are written against.

Person 1 (evidencerank.parsing) and Person 2 (evidencerank.keyword) were
built independently and diverge from schemas.py in three concrete ways
(discovered by inspecting their real code, not assumed):

1. Person 1's parse_jd() returns no `requirements` at all -- Person 2's
   extract_requirements() is the one that produces them, as a *separate*
   dict. adapt_jd() merges the two into one ParsedJD.
2. Person 1's ParsedResume["sections"] values are single joined strings
   (one blob per section), not List[str] chunks. adapt_resume() splits
   each section into non-empty line-level chunks.
3. Person 2's match_candidates() returns one dict per candidate containing
   a nested `requirements` list (with `id`, `match_type`, `matched_terms`,
   evidence, etc.), not a flat List[KeywordMatchResult] keyed by
   `requirement_id`/`normalized_match`. adapt_keyword_results() flattens
   and renames fields, preserving Person 2's own EXACT/NORMALIZED
   distinction (only one of matched_terms/normalized_match is ever
   populated, so evidence_ledger.classify_match_type re-derives the exact
   same match_type Person 2 already computed).
4. Person 2's engine.py (commit a79c357, "Standardize keyword scores and
   coverage on 0-100 scale") emits keyword_score on [0, 100], diverging from
   CONTRACT.md section 4.1's agreed 0.0-1.0 scale, which scoring.py's
   weighted mean and evidence_ledger.py's 0.0 default are written against.
   adapt_keyword_results() divides by 100 back onto [0, 1] so downstream
   Person 3 code keeps working unmodified against the agreed scale.

Nothing here invents data that Person 1/2 didn't produce, and nothing here
duplicates Person 3's own matching/scoring logic -- semantic_matcher.py,
evidence_ledger.py, ranking.py and the scoring formula in scoring.py are
called unchanged.
"""

from __future__ import annotations

from typing import Dict, List
import re

from schemas import KeywordMatchResult, ParsedJD, ParsedResume


def adapt_jd(person1_jd: dict, person2_extracted: dict) -> ParsedJD:
    """Merge Person 1's parse_jd() output and Person 2's
    extract_requirements() output into one ParsedJD.

    person1_jd: Person 1's parse_jd() return value -- {raw_text, clean_text, warnings}.
    person2_extracted: Person 2's extract_requirements(person1_jd) return
        value -- {requirements, warnings}. Requirement "type" may be None
        (ambiguous priority) -- passed through as-is; scoring.py handles it.
    """
    return {
        "raw_text": person1_jd["raw_text"],
        "requirements": person2_extracted["requirements"],
    }


def _split_section_into_chunks(section_text: str) -> List[str]:
    """Person 1 joins each section's lines with "\\n" into one string.
    Split back into line-level chunks, dropping blank lines, so
    semantic_matcher.flatten_resume_chunks gets real chunks instead of
    iterating individual characters of a single string.
    """
    return [line.strip() for line in section_text.splitlines() if line.strip()]


def adapt_resume(person1_resume: dict) -> ParsedResume:
    """Convert Person 1's parse_resume() output (sections: dict[str, str])
    into schemas.py's ParsedResume shape (sections: dict[str, List[str]]).
    """
    def original_chunks(text):
        chunks = []
        for line in _split_section_into_chunks(text):
            match = re.search(r"\s+".join(re.escape(word) for word in line.split()), person1_resume["raw_text"])
            if match:
                chunks.append(match.group())
        return chunks

    return {
        "candidate_id": person1_resume["candidate_id"],
        "candidate_name": person1_resume["candidate_name"],
        "raw_text": person1_resume["raw_text"],
        "sections": {
            section: original_chunks(text)
            for section, text in person1_resume["sections"].items()
        },
        "normalized_skills": person1_resume["normalized_skills"],
        "warnings": list(person1_resume["warnings"]),
    }


def adapt_keyword_results(person2_match_candidates_output: List[dict]) -> List[KeywordMatchResult]:
    """Flatten Person 2's match_candidates() output (one dict per candidate,
    each with a nested `requirements` list) into a flat List[KeywordMatchResult]
    keyed by (candidate_id, requirement_id), as evidence_ledger.build_ledger
    expects.

    Person 2's own `match_type` (EXACT/NORMALIZED/NOT_EVIDENCED) is not
    copied directly -- instead, exactly one of matched_terms/normalized_match
    is populated per Person 2's classification, so that
    evidence_ledger.classify_match_type() independently re-derives the same
    match_type Person 2 already computed (EXACT if matched_terms is
    non-empty, else NORMALIZED if normalized_match is set, else falls
    through to Person 3's own SEMANTIC/NOT_EVIDENCED check).
    """
    flat: List[KeywordMatchResult] = []
    for candidate in person2_match_candidates_output:
        candidate_id = candidate["candidate_id"]
        for row in candidate["requirements"]:
            match_type = row["match_type"]
            matched_terms = row["matched_terms"] if match_type == "EXACT" else []
            normalized_match = row["matched_terms"][0] if match_type == "NORMALIZED" and row["matched_terms"] else None
            flat.append({
                "candidate_id": candidate_id,
                "requirement_id": row["id"],
                "keyword_score": row["keyword_score"] / 100.0,
                "matched_terms": matched_terms,
                "normalized_match": normalized_match,
                "evidence": row.get("evidence", ""),
            })
    return flat
