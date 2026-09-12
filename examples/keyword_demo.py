"""Run from the repository root: python -m examples.keyword_demo"""
import json
from pathlib import Path

from evidencerank.parsing import parse_jd, parse_resume
from evidencerank.keyword import extract_requirements, match_candidates, keyword_coverage


def main():
    fixtures = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
    extracted = extract_requirements(parse_jd(fixtures / "jd_keyword.txt"))
    candidates = [parse_resume(fixtures / name) for name in ("resume_complete.txt", "resume_messy.txt")]
    candidates.append({"candidate_id": "synthetic-third", "candidate_name": "Sam Example", "raw_text": "Skills: React, Backend APIs, Mongo DB, Git", "normalized_skills": []})
    results = match_candidates(candidates, extracted["requirements"])
    print(json.dumps({"extraction": extracted, "candidates": results,
                      "keyword_components": [keyword_coverage(r["requirements"]) for r in results]}, indent=2))


if __name__ == "__main__":
    main()
