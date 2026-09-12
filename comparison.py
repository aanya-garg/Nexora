"""
Recruiter Q&A / comparison logic.

Design choice: this is a set of PARAMETERIZED functions the UI calls from
dropdowns/buttons (per the hackathon guide's instruction to avoid an
open-ended chatbot), not a free-text question parser. Every answer is
computed from stored scores first, then rendered into a sentence -- never
the other way around.
"""

NOTABLE_DELTA_THRESHOLD = 15  # points, on the 0-100 keyword/semantic scale


def _req_avg(req):
    return (req["keyword_score"] + req["semantic_score"]) / 2


def compare(candidate_x: dict, candidate_y: dict) -> dict:
    """Why is candidate_x ranked above/below candidate_y?"""
    deltas = {
        key: round(candidate_x["score_breakdown"].get(key, 0) - candidate_y["score_breakdown"].get(key, 0), 1)
        for key in candidate_x["score_breakdown"]
    }
    final_delta = round(candidate_x["final_score"] - candidate_y["final_score"], 1)

    req_x = {r["id"]: r for r in candidate_x["requirements"]}
    req_y = {r["id"]: r for r in candidate_y["requirements"]}
    requirement_diffs = []
    for rid, rx in req_x.items():
        ry = req_y.get(rid)
        if ry is None:
            continue
        diff = round(_req_avg(rx) - _req_avg(ry), 1)
        if abs(diff) >= NOTABLE_DELTA_THRESHOLD:
            requirement_diffs.append({"requirement": rx["text"], "delta": diff})
    requirement_diffs.sort(key=lambda d: -abs(d["delta"]))

    sign = "above" if final_delta > 0 else "below"
    component_str = ", ".join(
        f"{'+' if v >= 0 else ''}{v} {k}" for k, v in deltas.items() if abs(v) >= 1
    )
    sentence = (
        f"{candidate_x['candidate_name']} ranks {sign} {candidate_y['candidate_name']} by "
        f"{abs(final_delta)} points overall ({component_str})."
    )
    if final_delta == 0:
        sentence = f"{candidate_x['candidate_name']} and {candidate_y['candidate_name']} are tied on the displayed final score."
        if component_str:
            sentence += f" Component differences: {component_str}."
    if requirement_diffs:
        top = ", ".join(f"{d['requirement']} ({'+' if d['delta'] >= 0 else ''}{d['delta']})"
                         for d in requirement_diffs[:3])
        sentence += f" Biggest requirement-level differences: {top}."

    return {
        "component_deltas": deltas,
        "final_delta": final_delta,
        "requirement_diffs": requirement_diffs,
        "sentence": sentence,
    }


def not_evidenced(candidate: dict) -> list:
    """What is this candidate not clearly evidencing?"""
    return [r["text"] for r in candidate["requirements"] if r["match_type"] == "NOT_EVIDENCED"]


def strongest_on_requirement(candidates: list, requirement_keyword: str) -> list:
    """Who has stronger <backend/project/etc> evidence? Ranks all candidates
    on any requirement whose text contains the given keyword."""
    scored = []
    for c in candidates:
        for r in c["requirements"]:
            if requirement_keyword.lower() in r["text"].lower():
                scored.append({
                    "candidate_name": c["candidate_name"],
                    "requirement": r["text"],
                    "score": round(_req_avg(r), 1),
                    "match_type": r["match_type"],
                    "evidence": r["evidence"],
                })
    scored.sort(key=lambda s: -s["score"])
    return scored
