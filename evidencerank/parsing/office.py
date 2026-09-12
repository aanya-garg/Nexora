"""Local Word/XML text extraction; no archive extraction or external entities."""
import io
import zipfile
from xml.etree.ElementTree import TreeBuilder
from xml.parsers import expat

MAX_XML_BYTES = 20 * 1024 * 1024
WORD_NAMESPACES = {
    "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "http://purl.oclc.org/ooxml/wordprocessingml/main",
    "http://schemas.microsoft.com/office/word/2003/wordml",
}


def read_xml(data):
    if len(data) > MAX_XML_BYTES:
        raise ValueError("XML exceeds size limit")
    builder = TreeBuilder()
    parser = expat.ParserCreate(namespace_separator="}")
    parser.StartElementHandler = builder.start
    parser.EndElementHandler = builder.end
    parser.CharacterDataHandler = builder.data

    def reject(*args):
        raise ValueError("DTD and entities are unsupported")

    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    parser.Parse(data, True)
    return builder.close()


def xml_text(data):
    root = read_xml(data)
    namespace = root.tag.rsplit("}", 1)[0] if "}" in root.tag else ""
    if namespace in WORD_NAMESPACES:
        parts = []
        for node in root.iter():
            tag = node.tag.rsplit("}", 1)[-1]
            if tag == "t":
                parts.append(node.text or "")
            elif tag == "tab":
                parts.append("\t")
            elif tag in {"br", "cr"}:
                parts.append("\n")
            elif tag == "p":
                parts.append("\n")
        return "".join(parts).strip()

    def render(node):
        # Element boundaries separate structured fields; inline text remains intact.
        tag = node.tag.rsplit("}", 1)[-1].lower()
        heading = tag.capitalize() + "\n" if tag in {"skills", "experience", "projects", "education", "certifications"} else ""
        result = heading + (node.text or "")
        for child in node:
            result += "\n" + render(child) + "\n" + (child.tail or "")
        return result

    return render(root).strip()


def docx_text(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        info = archive.getinfo("word/document.xml")
        if info.file_size > MAX_XML_BYTES:
            raise ValueError("Word XML exceeds size limit")
        return xml_text(archive.read(info))
