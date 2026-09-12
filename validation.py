"""
Validation / QA layer. Run this before every demo rehearsal -- it never
changes scores, it only flags things worth a human look.
"""

ALLOWED_MATCH_TYPES = {"EXACT", "NORMALIZED", "SEMANTIC", "NOT_EVIDENCED"}
MIN_HEALTHY_SPREAD = 15  # final_score points between best and worst candidate


def validate_ranking(ranked_candidates: list) -> dict:
    sorted_c = sorted(ranked_candidates, key=lambda c: c["final_score"], reverse=True)
    n = len(sorted_c)
    warnings = []

    top = [c["candidate_id"] for c in sorted_c[:3]]
    mid_start = max(0, n // 2 - 1)
    middle = [c["candidate_id"] for c in sorted_c[mid_start:mid_start + 3]]
    bottom = [c["candidate_id"] for c in sorted_c[-3:]]

    scores = [c["final_score"] for c in sorted_c]
    spread = round(max(scores) - min(scores), 1) if scores else 0
    if spread < MIN_HEALTHY_SPREAD:
        warnings.append(
            f"Score spread is only {spread} points across all candidates -- ranking may look too "
            f"uniform to judges. Revisit weights or requirement scoring."
        )

    for c in sorted_c:
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
