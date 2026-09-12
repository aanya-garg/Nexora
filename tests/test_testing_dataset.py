import zipfile
import pytest
from training_data import prepare_training, load_training
from evidencerank.keyword import extract_requirements


def test_testing_split_cannot_overwrite_training(tmp_path):
    archive = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("resume.txt", "Maya Kapoor\nSkills: Python")
    destination = tmp_path / "split-isolation"
    prepare_training(archive, destination)
    with pytest.raises(ValueError, match="different dataset split"):
        prepare_training(archive, destination, dataset_type="testing")
    testing = prepare_training(archive, tmp_path / "testing", dataset_type="testing")
    assert testing["dataset_type"] == "testing"
    assert testing == load_training(tmp_path / "testing/parsed_resumes.json", dataset_type="testing")


def test_headings_and_parenthetical_priority():
    result = extract_requirements("Example Company\nABOUT THE ROLE\nJoin our team\nMUST-HAVE SKILLS\nA frontend framework (React preferred)\nGOOD-TO-HAVE SKILLS\nTesting frameworks (Jest, Mocha)\nSOFT SKILLS\nCommunication")
    reqs = result["requirements"]
    assert len(reqs) == 3
    assert [r["type"] for r in reqs] == ["required", "preferred", None]
    assert reqs[1]["text"] == "Testing frameworks (Jest, Mocha)"


def test_responsibilities_do_not_produce_bare_verbs():
    reqs = extract_requirements("KEY RESPONSIBILITIES\nDevelop and maintain web applications\nDebug and resolve issues reported by QA and users")["requirements"]
    assert len(reqs) == 2
    assert reqs[0]["text"] == "Develop and maintain web applications"
