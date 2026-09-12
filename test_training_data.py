import json
import sys
import zipfile
from pathlib import Path
import pytest
from training_data import load_training, prepare_training
import demo


def test_bad_archive_paths_rejected(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../outside.txt", "unsafe")
    with pytest.raises(ValueError, match="Unsafe"):
        prepare_training(archive, tmp_path / "output")
    assert not (tmp_path / "outside.txt").exists()


def test_training_preserves_parser_contract(tmp_path):
    archive = tmp_path / "input.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("resume.txt", "Maya Kapoor\nSkills: Python")
    bundle = prepare_training(archive, tmp_path / "output")
    assert bundle == load_training(tmp_path / "output/parsed_resumes.json")
    candidate = bundle["documents"][0]["candidate"]
    assert candidate["normalized_skills"] == ["Python"]
    assert "final_score" not in candidate


def test_demo_without_scores_does_not_generate_explanations(tmp_path, monkeypatch, capsys):
    path = tmp_path / "training.json"
    path.write_text(json.dumps({"dataset_type": "training", "status": "parsed_unranked", "documents": []}))
    monkeypatch.setattr(sys, "argv", ["demo", "--training", str(path)])
    monkeypatch.setattr(demo, "generate_top3_explanations", lambda _: pytest.fail("Invented results"))
    demo.main()
    assert "no sample scores" in capsys.readouterr().out
