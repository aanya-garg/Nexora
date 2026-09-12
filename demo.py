"""Training-data entry point; ranked results must come from Person C."""
import argparse
import json
from pathlib import Path
from training_data import load_training
from explanations import generate_top3_explanations
from validation import validate_ranking
from jd_quality import detect_jd_issues


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--training", default=str(Path(__file__).parent / "data/training/parsed_resumes.json"))
    cli.add_argument("--ranked", help="Person C's JSON list of ranked training candidates")
    cli.add_argument("--jd", help="Matching JD as a UTF-8 text file")
    args = cli.parse_args()
    try:
        training = load_training(args.training)
    except FileNotFoundError:
        cli.error("Run training_data.py with the training ZIP first.")
    docs = training["documents"]
    print(f"Training dataset: {len(docs)} resume documents (format variants retained separately).")
    if args.jd:
        print(json.dumps({"jd_issues": detect_jd_issues(Path(args.jd).read_text(encoding="utf-8-sig"))}, indent=2))
    if not args.ranked:
        print("Parsing is ready. Rankings and explanations await the JD and Person C's scored Evidence Ledger; no sample scores are used.")
        return
    ranked = json.loads(Path(args.ranked).read_text(encoding="utf-8"))
    valid_ids = {d["candidate"]["candidate_id"] for d in docs}
    if not isinstance(ranked, list) or not ranked or any(c.get("candidate_id") not in valid_ids for c in ranked):
        cli.error("Ranked results must reference this training dataset's candidate IDs.")
    report = validate_ranking(ranked)
    print(json.dumps({"validation": report}, indent=2))
    if report["status"] != "PASS":
        print("Resolve validation warnings before displaying explanations.")
        return
    print(json.dumps({"top3_explanations": generate_top3_explanations(ranked)}, indent=2))


if __name__ == "__main__":
    main()
