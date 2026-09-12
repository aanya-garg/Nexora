"""Local training data preparation; scores are supplied separately by Person C."""
import argparse
import json
from pathlib import Path
import zipfile


def prepare_training(archive_path, output_dir):
    from evidencerank.parsing import parse_resume
    output_dir = Path(output_dir).resolve()
    documents = output_dir / "resumes"
    documents.mkdir(parents=True, exist_ok=True)
    candidates = []
    with zipfile.ZipFile(archive_path) as archive:
        members = [i for i in archive.infolist() if not i.is_dir()]
        if sum(i.file_size for i in members) > 200 * 1024 * 1024:
            raise ValueError("Training archive exceeds 200 MiB")
        targets = set()
        for item in members:
            target = (documents / item.filename.replace("\\", "/")).resolve()
            if not target.is_relative_to(documents) or ":" in item.filename:
                raise ValueError("Unsafe archive member path")
            if str(target).casefold() in targets:
                raise ValueError("Duplicate archive destination")
            targets.add(str(target).casefold())
        for item in members:
            target = (documents / item.filename.replace("\\", "/")).resolve()
            if target.suffix.lower() not in {".pdf", ".docx", ".docxl", ".xml", ".txt"}:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(item))
            candidates.append({"source_file": target.relative_to(output_dir).as_posix(), "candidate": parse_resume(target)})
    bundle = {"dataset_type": "training", "status": "parsed_unranked", "documents": candidates}
    (output_dir / "parsed_resumes.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return bundle


def load_training(path):
    bundle = json.loads(Path(path).read_text(encoding="utf-8"))
    if bundle.get("dataset_type") != "training" or bundle.get("status") != "parsed_unranked" or not isinstance(bundle.get("documents"), list):
        raise ValueError("Expected a parsed training dataset")
    return bundle


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("archive")
    cli.add_argument("--output", default="data/training")
    args = cli.parse_args()
    docs = prepare_training(args.archive, args.output)["documents"]
    print(f"Prepared {len(docs)} training documents; {sum(bool(d['candidate']['raw_text'].strip()) for d in docs)} contain extracted text. No scores generated.")
