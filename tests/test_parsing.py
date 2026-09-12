import json
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from evidencerank.parsing import clean_text, normalize_skills, parse_jd, parse_resume

FIXTURES = Path(__file__).parent / "fixtures"


def make_pdf(path, lines=(), *, blank=False, password=None):
    """Minimal real PDF fixture, built locally with the runtime dependency."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    if not blank:
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        escaped = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
        stream = DecodedStreamObject()
        stream.set_data(("BT /F1 12 Tf 50 740 Td 16 TL " + " ".join(f"({line}) Tj T*" for line in escaped) + " ET").encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    if password:
        writer.encrypt(password)
    writer.write(path)


def test_complete_contract():
    result = parse_resume(FIXTURES / "resume_complete.txt")
    assert set(result) == {"candidate_id", "candidate_name", "raw_text", "sections", "normalized_skills", "warnings"}
    assert result["candidate_name"] == "Maya Kapoor"
    assert set(result["sections"]) == {"skills", "experience", "projects", "education", "certifications"}
    assert result["normalized_skills"] == ["Python", "React", "C++", "PostgreSQL", "Node.js", "Docker"]
    assert result["warnings"] == []
    assert result["raw_text"] == (FIXTURES / "resume_complete.txt").read_text()


def test_messy_sections():
    result = parse_resume(FIXTURES / "resume_messy.txt")
    assert result["candidate_name"] == "Arjun Rao"
    assert "Second mock" in result["sections"]["projects"]
    assert "Photography" not in result["sections"]["projects"]
    assert "section_missing_or_empty:education" in result["warnings"]
    assert "section_missing_or_empty:certifications" in result["warnings"]
    assert result["normalized_skills"] == ["JavaScript", "C#", "scikit-learn", "Python", "Node.js", "AWS", "TypeScript"]


def test_jd_only_extracts_and_cleans():
    result = parse_jd(FIXTURES / "jd_mock.txt")
    assert set(result) == {"raw_text", "clean_text", "warnings"}
    assert "Build local tools" in result["clean_text"]
    assert "  Build   local" in result["raw_text"]


def test_cleaning_preserves_lines_and_punctuation():
    assert clean_text("Ａ\u00a0 B\r\nC++\tC#\x00\n\n\nReact.js\u200b\u00ad") == "A B\nC++ C#\n\nReact.js"
    text = "skills:\nPython C++"
    assert clean_text(clean_text(text)) == clean_text(text)


def test_normalization_boundaries_and_deduplication():
    assert normalize_skills("JavaScript Java javabeans C++ C# reactjs React.js git GitHub PostgreSQL") == ["JavaScript", "Java", "C++", "C#", "React", "Git", "PostgreSQL"]
    assert normalize_skills("my_python pythonic typescripts") == []


def test_editable_config(tmp_path):
    config = tmp_path / "aliases.json"
    config.write_text(json.dumps({"ExampleDB": ["example db", "edb"]}))
    assert normalize_skills("EDB example db", config) == ["ExampleDB"]
    assert parse_resume(FIXTURES / "resume_complete.txt", config_path=config)["normalized_skills"] == []


@pytest.mark.parametrize("config", [{"X": "x"}, {"X": [""]}, {"X": ["same"], "Y": ["same"]}, []])
def test_invalid_config_raises(tmp_path, config):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        normalize_skills("anything", path)


def test_real_pdf_extraction(tmp_path):
    path = tmp_path / "resume.pdf"
    make_pdf(path, (FIXTURES / "resume_complete.txt").read_text().splitlines())
    result = parse_resume(path)
    assert result["candidate_name"] == "Maya Kapoor"
    assert result["warnings"] == []
    assert "Node.js" in result["normalized_skills"]
    assert "BSc" in result["sections"]["education"]
    assert "TECHNICAL SKILLS" in parse_jd(path)["clean_text"]


@pytest.mark.parametrize("kind,warning", [("blank", "page_no_text:1:ocr_may_be_required"), ("encrypted", "pdf_encrypted"), ("corrupt", "pdf_unreadable")])
def test_bad_pdfs(tmp_path, kind, warning):
    path = tmp_path / "bad.pdf"
    if kind == "corrupt":
        path.write_bytes(b"not a pdf")
    else:
        make_pdf(path, blank=True, password="secret" if kind == "encrypted" else None)
    for parser in (parse_resume, parse_jd):
        result = parser(path)
        assert result["raw_text"] == ""
        assert warning in result["warnings"]


def test_missing_unsupported_empty_and_bad_encoding(tmp_path):
    assert "file_unreadable" in parse_resume(tmp_path / "missing.pdf")["warnings"]
    path = tmp_path / "x.docx"
    path.write_bytes(b"x")
    assert parse_jd(path)["warnings"] == ["unsupported_format"]
    path = tmp_path / "empty.txt"
    path.write_bytes(b"")
    assert "document_no_text" in parse_jd(path)["warnings"]
    path.write_bytes(b"Skills:\nPython\xff")
    assert "text_encoding_replacements" in parse_resume(path)["warnings"]


def test_identity_stable_across_paths(tmp_path):
    source = FIXTURES / "resume_complete.txt"
    copy = tmp_path / "renamed.txt"
    copy.write_bytes(source.read_bytes())
    assert parse_resume(source)["candidate_id"] == parse_resume(copy)["candidate_id"]


def test_headerless_resume_preserves_text(tmp_path):
    path = tmp_path / "no_headings.txt"
    path.write_text("contact@example.test\nBuilt Python services")
    result = parse_resume(path)
    assert result["candidate_name"] == ""
    assert result["normalized_skills"] == ["Python"]
    assert all(value == "" for value in result["sections"].values())
    assert "Built Python" in result["raw_text"]


def test_partial_page_failure_preserves_other_pages(tmp_path, monkeypatch):
    import evidencerank.parsing.parser as module

    class Page:
        def __init__(self, text):
            self.text = text

        def get(self, key):
            return True

        def extract_text(self, **kwargs):
            if self.text is None:
                raise ValueError("damaged page")
            return self.text

    class Reader:
        is_encrypted = False
        pages = [Page("Maya Kapoor\nSkills: Python"), Page(None), Page("Projects: Demo")]

    monkeypatch.setattr(module, "PdfReader", lambda *a, **k: Reader())
    path = tmp_path / "partial.pdf"
    path.write_bytes(b"mock reader input")
    result = parse_resume(path)
    assert result["sections"]["skills"] == "Python"
    assert result["sections"]["projects"] == "Demo"
    assert "page_unreadable:2" in result["warnings"]
