"""
Validation / QA layer. Run this before every demo rehearsal -- it never
changes scores, it only flags things worth a human look.
"""

import math

ALLOWED_MATCH_TYPES = {"EXACT", "NORMALIZED", "SEMANTIC", "NOT_EVIDENCED"}
MIN_HEALTHY_SPREAD = 15  # final_score points between best and worst candidate


def validate_ranking(ranked_candidates: list) -> dict:
    warnings = []

    def valid_score(value):
        return (not isinstance(value, bool) and isinstance(value, (int, float))
                and math.isfinite(value) and 0 <= value <= 100)

    seen_ids = set()
    for c in ranked_candidates:
        cid = c.get("candidate_id", "<missing>")
        if cid in seen_ids:
            warnings.append(f"Duplicate candidate_id: {cid}.")
        seen_ids.add(cid)
        if not valid_score(c.get("final_score")):
            warnings.append(f"{cid}: final_score must be a finite number on 0-100.")
        for key in ("keyword", "semantic", "experience", "evidence_strength"):
            if not valid_score(c.get("score_breakdown", {}).get(key)):
                warnings.append(f"{cid}: {key} component must be a finite number on 0-100.")
        for r in c["requirements"]:
            for key in ("keyword_score", "semantic_score"):
                if not valid_score(r.get(key)):
                    warnings.append(f"{cid} / {r['id']}: {key} must be a finite number on 0-100.")

    valid_candidates = [c for c in ranked_candidates if valid_score(c.get("final_score"))]
    input_scores = [c["final_score"] for c in valid_candidates]
    if input_scores != sorted(input_scores, reverse=True):
        warnings.append("Candidates are not ordered by descending final_score; check Person C's ranking output.")
    sorted_c = sorted(valid_candidates, key=lambda c: c["final_score"], reverse=True)
    n = len(sorted_c)
    if not ranked_candidates:
        warnings.append("No candidates supplied; ranking cannot be validated.")

    top = [c["candidate_id"] for c in sorted_c[:3]]
    mid_start = max(0, n // 2 - 1)
    middle = [c["candidate_id"] for c in sorted_c[mid_start:mid_start + 3]]
    bottom = [c["candidate_id"] for c in sorted_c[-3:]]

    scores = [c["final_score"] for c in sorted_c]
    spread = round(max(scores) - min(scores), 1) if scores else 0
    if spread < MIN_HEALTHY_SPREAD:
        warnings.append(
            f"Score spread is only {spread} points across all candidates. Review the source evidence "
            f"and scoring for correctness; similar candidates may legitimately have similar scores."
        )

    for c in ranked_candidates:
        for r in c["requirements"]:
            tag = f"{c['candidate_id']} / {r['id']}"
            if r["match_type"] not in ALLOWED_MATCH_TYPES:
                warnings.append(f"{tag}: unexpected match_type '{r['match_type']}'.")
            if r["match_type"] != "NOT_EVIDENCED" and not r.get("evidence"):
                warnings.append(f"{tag}: match_type is {r['match_type']} but no evidence text is stored "
                                 f"-- check for a possible fabrication or missing-data bug.")
            if r["match_type"] == "NOT_EVIDENCED" and r.get("evidence"):
                warnings.append(f"{tag}: marked NOT_EVIDENCED but evidence text is present -- inconsistent, fix before demo.")

    return {
        "top_3": top,
        "middle_3": middle,
        "bottom_3": bottom,
        "score_spread": spread,
        "warnings": warnings,
        "status": "PASS" if not warnings else "REVIEW",
    }
