"""Prepare/inspect a labelled dataset or run it through the real local model."""
import argparse
import json
from pathlib import Path
from training_data import load_training
from evidencerank.parsing import parse_jd
from evidencerank.keyword import extract_requirements, match_candidates
from pipeline import analyze_candidates


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--dataset", required=True)
    cli.add_argument("--split", choices=["training", "testing"], required=True)
    cli.add_argument("--jd", required=True)
    cli.add_argument("--prepare-only", action="store_true", help="Extract requirements and keyword evidence without final scoring")
    args = cli.parse_args()
    dataset_path = Path(args.dataset)
    bundle = load_training(dataset_path, dataset_type=args.split)
    parsed_jd = parse_jd(args.jd)
    if not parsed_jd["clean_text"]:
        raise ValueError("JD has no readable text")
    extracted = extract_requirements(parsed_jd)
    if args.prepare_only:
        result = {"dataset_type": args.split, "status": "keyword_only_not_final_scores", "jd": parsed_jd,
                  "extraction": extracted, "candidates": match_candidates([d["candidate"] for d in bundle["documents"]], extracted["requirements"])}
        target = dataset_path.parent / "preparation.json"
    else:
        paths = [dataset_path.parent / d["source_file"] for d in bundle["documents"]]
        result = {"dataset_type": args.split, **analyze_candidates(args.jd, paths)}
        target = dataset_path.parent / "results.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {target}; {len(bundle['documents'])} documents, {len(extracted['requirements'])} extracted requirements.")


if __name__ == "__main__":
    main()
