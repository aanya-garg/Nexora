"""
Top-3 explanation generator.

Rule: this module NEVER calls an LLM and NEVER invents a claim that isn't
directly backed by a requirement entry in the candidate's own data. Every
sentence traces back to a specific requirement/evidence pair, which is
what keeps this safe from hallucination and faithful to Person 3's score.
"""

STRONG_MATCH_TYPES = {"EXACT", "NORMALIZED", "SEMANTIC"}


def _avg(req):
    return (req["keyword_score"] + req["semantic_score"]) / 2


def build_explanation(candidate: dict) -> str:
    reqs = candidate["requirements"]
    matched = [r for r in reqs if r["match_type"] in STRONG_MATCH_TYPES]
    matched_sorted = sorted(matched, key=_avg, reverse=True)
    strongest = matched_sorted[:3]

    # Semantic matches that keyword search alone would have missed --
    # this is the clearest proof point that semantic matching mattered.
    semantic_highlights = [
        r for r in matched
        if r["match_type"] == "SEMANTIC" and r["keyword_score"] < 50 and r["semantic_score"] >= 70 and r.get("evidence")
    ]

    missing = [r for r in reqs if r["match_type"] == "NOT_EVIDENCED"]

    parts = [f"{candidate['candidate_name']} scored {candidate['final_score']:.1f}/100 overall."]

    if strongest:
        listed = "; ".join(
            f"{r['text']} ({r['match_type'].lower()}) -- "
            + (f"evidence: \"{r['evidence']}\"" if r.get("evidence") else "supporting evidence unavailable; review needed")
            for r in strongest
        )
        parts.append(f"Strongest matches: {listed}.")

    if semantic_highlights:
        r = semantic_highlights[0]
        parts.append(
            f"Semantic matching found relevant experience for \"{r['text']}\" even though the "
            f"literal matching was weaker -- evidence: \"{r['evidence']}\"."
        )

    if missing:
        listed = ", ".join(r["text"] for r in missing)
        parts.append(f"Not evidenced in the submitted resume: {listed}.")

    return " ".join(parts)


def generate_top3_explanations(ranked_candidates: list) -> list:
    """Returns explanation objects for the top 3 candidates by final_score."""
    top3 = sorted(ranked_candidates, key=lambda c: c["final_score"], reverse=True)[:3]
    return [
        {
            "candidate_id": c["candidate_id"],
            "candidate_name": c["candidate_name"],
            "explanation": build_explanation(c),
        }
        for c in top3
    ]
