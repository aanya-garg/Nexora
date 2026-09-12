import zipfile
import pytest
from evidencerank.parsing import parse_resume, parse_jd

WORD = b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Maya Kapoor</w:t></w:r></w:p><w:p><w:r><w:t>Skills</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Py</w:t></w:r><w:r><w:t>thon</w:t><w:tab/><w:t>React.js</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'


@pytest.mark.parametrize("extension", [".docx", ".DOCX", ".docxl", ".xml"])
def test_word_and_word_xml(tmp_path, extension):
    path = tmp_path / ("resume" + extension)
    if extension == ".xml":
        path.write_bytes(WORD)
    else:
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", WORD)
    result = parse_resume(path)
    assert result["candidate_name"] == "Maya Kapoor"
    assert result["normalized_skills"] == ["Python", "React"]
    assert "Python" in result["sections"]["skills"]
    assert set(parse_jd(path)) == {"raw_text", "clean_text", "warnings"}
    assert "Python" in parse_jd(path)["clean_text"]


def test_structured_unicode_xml(tmp_path):
    path = tmp_path / "resume.xml"
    path.write_bytes('<?xml version="1.0" encoding="UTF-16"?><resume><name>Maya Kapoor</name><skills><skill>Python</skill><skill>C++</skill></skills></resume>'.encode("utf-16"))
    result = parse_resume(path)
    assert result["candidate_name"] == "Maya Kapoor"
    assert result["normalized_skills"] == ["Python", "C++"]
    assert "Python" in result["sections"]["skills"]


@pytest.mark.parametrize("extension", [".docx", ".docxl", ".xml"])
def test_corrupt_files(tmp_path, extension):
    path = tmp_path / ("bad" + extension)
    path.write_bytes(b"invalid document")
    assert parse_resume(path)["raw_text"] == ""
    assert any("unreadable" in w for w in parse_jd(path)["warnings"])


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_dtd_entities_are_rejected(tmp_path, encoding):
    path = tmp_path / "unsafe.xml"
    path.write_bytes(f'<?xml version="1.0" encoding="{encoding}"?><!DOCTYPE r [<!ENTITY x "Python">]><r>&x;</r>'.encode(encoding))
    assert parse_jd(path) == {"raw_text": "", "clean_text": "", "warnings": ["xml_unreadable"]}


def test_empty_xml(tmp_path):
    path = tmp_path / "empty.xml"
    path.write_bytes(b"<resume/>")
    assert "document_no_text" in parse_jd(path)["warnings"]
