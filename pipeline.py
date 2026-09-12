"""Single backend entry point for the future UI. No runtime network calls."""
import argparse
import json
from pathlib import Path

from evidencerank.parsing import parse_jd, parse_resume
from evidencerank.keyword import extract_requirements, match_candidates
from adapters import adapt_jd, adapt_resume, adapt_keyword_results
from semantic_matcher import compute_semantic_matches, get_default_embedder
from evidence_ledger import build_ledger
from scoring import score_candidate, compute_final_score
from ranking import rank_candidates
from explanations import generate_top3_explanations
from jd_quality import detect_jd_issues
from validation import validate_ranking


def analyze_candidates(jd_path, resume_paths, *, weights=None, embedder=None):
    parsed_jd = parse_jd(jd_path)
    if not parsed_jd["clean_text"]:
        raise ValueError(f"JD has no readable text: {parsed_jd['warnings']}")
    extracted = extract_requirements(parsed_jd)
    jd = adapt_jd(parsed_jd, extracted)
    if not jd["requirements"]:
        raise ValueError("No JD requirements extracted")
    originals, excluded, seen = [], [], set()
    for path in resume_paths:
        resume = parse_resume(path)
        if not resume["raw_text"].strip():
            excluded.append({"source_file": str(path), "warnings": resume["warnings"]})
            continue
        if resume["candidate_id"] in seen:
            excluded.append({"source_file": str(path), "warnings": ["duplicate_document"]})
            continue
        seen.add(resume["candidate_id"])
        originals.append(resume)
    if not originals:
        raise ValueError("No readable, unique resume documents supplied")
    # Fail clearly if the real model is missing; never silently substitute keyword vectors.
    embedder = embedder or get_default_embedder()
    keywords = adapt_keyword_results(match_candidates(originals, jd["requirements"]))
    results = []
    for original in originals:
        resume = adapt_resume(original)
        semantic = compute_semantic_matches(jd, resume, embedder)
        ledger = build_ledger(jd, resume, keywords, semantic)
        result = score_candidate(jd, resume, ledger, semantic, weights)
        for row in result["requirements"]:
            if row["evidence"] and row["evidence"] not in original["raw_text"]:
                raise ValueError("Evidence does not occur in source resume")
        results.append(result)
    ranked = rank_candidates(results)
    return {"ranked_candidates": ranked, "top3_explanations": generate_top3_explanations(ranked),
            "requirements": jd["requirements"], "jd_warnings": extracted["warnings"],
            "parsing_warnings": {r["candidate_id"]: r["warnings"] for r in originals},
            "excluded_documents": excluded, "jd_issues": detect_jd_issues(parsed_jd["clean_text"]),
            "validation": validate_ranking(ranked)}


def rescore_candidates(candidates, weights):
    """UI sliders reuse computed components without rerunning embeddings."""
    return rank_candidates([{**c, "final_score": compute_final_score(c["score_breakdown"], weights)} for c in candidates])


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--jd", required=True)
    cli.add_argument("--resumes", nargs="+", required=True)
    cli.add_argument("--output", required=True)
    args = cli.parse_args()
    bundle = analyze_candidates(args.jd, args.resumes)
    Path(args.output).write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Ranked {len(bundle['ranked_candidates'])} candidates; validation {bundle['validation']['status']}.")
