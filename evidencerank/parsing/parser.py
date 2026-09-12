"""Offline, deterministic extraction; no scoring or requirement inference."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import TypedDict

from pypdf import PdfReader


SECTION_NAMES = ("skills", "experience", "projects", "education", "certifications")
ALIASES = {
    "skills": ("skills", "technical skills", "technologies", "core competencies", "tech stack"),
    "experience": ("experience", "work experience", "professional experience", "employment", "employment history", "internships"),
    "projects": ("projects", "personal projects", "academic projects", "selected projects"),
    "education": ("education", "academic background", "academic qualifications"),
    "certifications": ("certifications", "certificates", "licenses and certifications"),
}
OTHER_HEADINGS = {"summary", "professional summary", "profile", "objective", "achievements", "awards", "interests", "languages", "references", "publications", "volunteering", "contact"}
HEADINGS = {alias: section for section, aliases in ALIASES.items() for alias in aliases}


class ResumeResult(TypedDict):
    candidate_id: str
    candidate_name: str
    raw_text: str
    sections: dict[str, str]
    normalized_skills: list[str]
    warnings: list[str]


class JDResult(TypedDict):
    raw_text: str
    clean_text: str
    warnings: list[str]


def clean_text(text: str) -> str:
    """Normalize Unicode/spacing while preserving lines and technical punctuation."""
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x0c", "\n").replace("\u00ad", "")
    text = "".join(c for c in text if c in "\n\t" or unicodedata.category(c) not in {"Cc", "Cf"})
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _extract(path: Path) -> tuple[str, list[str], bytes]:
    warnings: list[str] = []
    try:
        data = path.read_bytes()
    except OSError:
        return "", ["file_unreadable"], b""
    if path.suffix.lower() == ".txt":
        try:
            raw = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raw = data.decode("utf-8-sig", errors="replace")
            warnings.append("text_encoding_replacements")
    elif path.suffix.lower() == ".pdf":
        import io
        try:
            reader = PdfReader(io.BytesIO(data), strict=False)
            if reader.is_encrypted and not reader.decrypt(""):
                return "", ["pdf_encrypted"], data
            pages = []
            for number, page in enumerate(reader.pages, 1):
                try:
                    value = (page.extract_text(extraction_mode="layout") or "") if page.get("/Contents") is not None else ""
                    if not clean_text(value):
                        warnings.append(f"page_no_text:{number}:ocr_may_be_required")
                    pages.append(value)
                except Exception:
                    # A broken page must not discard successfully extracted pages.
                    warnings.append(f"page_unreadable:{number}")
                    pages.append("")
            raw = "\n\n".join(pages)
        except Exception:
            return "", ["pdf_unreadable"], data
    else:
        return "", ["unsupported_format"], data
    if not clean_text(raw):
        warnings.append("document_no_text")
    if "\ufffd" in raw:
        warnings.append("text_contains_replacement_characters")
    return raw, warnings, data


def _heading(line: str) -> tuple[str | None, str, bool]:
    value = line.strip(" \t•*-#")
    label, separator, content = value.partition(":")
    key = re.sub(r"\s+", " ", label).strip().casefold()
    if key in HEADINGS:
        return HEADINGS[key], content.strip() if separator else "", True
    if key in OTHER_HEADINGS:
        return None, "", True
    return None, "", False


def _sections(text: str) -> dict[str, str]:
    chunks: dict[str, list[str]] = {key: [] for key in SECTION_NAMES}
    current = None
    for line in text.splitlines():
        section, content, is_heading = _heading(line)
        if is_heading:
            current = section
            if current and content:
                chunks[current].append(content)
        elif current:
            chunks[current].append(line)
    return {key: "\n".join(value).strip() for key, value in chunks.items()}


def normalize_skills(text: str, config_path: str | Path | None = None) -> list[str]:
    """Return canonical technology mentions in first-occurrence order, deduplicated."""
    path = Path(config_path) if config_path is not None else Path(__file__).with_name("technology_aliases.json")
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or any(
        not isinstance(k, str) or not k.strip() or not isinstance(v, list)
        or any(not isinstance(a, str) or not a.strip() for a in v)
        for k, v in config.items()
    ):
        raise ValueError("Technology config must map canonical names to lists of nonempty aliases")
    aliases: dict[str, str] = {}
    for canonical, values in config.items():
        for alias in [canonical, *values]:
            key = clean_text(alias).casefold()
            if key in aliases and aliases[key] != canonical:
                raise ValueError(f"Ambiguous technology alias: {alias}")
            aliases[key] = canonical
    if not aliases:
        return []
    pattern = r"(?<![\w+#])(?:" + "|".join(re.escape(a) for a in sorted(aliases, key=len, reverse=True)) + r")(?![\w+#])"
    matches = re.finditer(pattern, clean_text(text).casefold())
    return list(dict.fromkeys(aliases[m.group()] for m in matches))


def _name(text: str) -> str:
    for line in text.splitlines()[:8]:
        if not line:
            continue
        if _heading(line)[2]:
            break
        if line.casefold() in {"resume", "curriculum vitae", "cv"}:
            continue
        words = line.split()
        if 2 <= len(words) <= 5 and all(all(c.isalpha() or c in "-'.’" for c in word) for word in words):
            return line
        break
    return ""


def parse_resume(path: str | Path, *, config_path: str | Path | None = None) -> ResumeResult:
    """Extract a resume. Document failures return warnings; config errors raise."""
    path = Path(path)
    raw, warnings, data = _extract(path)
    cleaned = clean_text(raw)
    sections = _sections(cleaned)
    for section, content in sections.items():
        if not content:
            warnings.append(f"section_missing_or_empty:{section}")
    name = _name(cleaned)
    if not name:
        warnings.append("candidate_name_not_detected")
    identity = data if data else str(path.resolve()).encode("utf-8")
    return {
        "candidate_id": "candidate_" + hashlib.sha256(identity).hexdigest()[:20],
        "candidate_name": name,
        "raw_text": raw,
        "sections": sections,
        "normalized_skills": normalize_skills(cleaned, config_path),
        "warnings": warnings,
    }


def parse_jd(path: str | Path) -> JDResult:
    """Extract and clean a JD without interpreting requirements."""
    raw, warnings, _ = _extract(Path(path))
    return {"raw_text": raw, "clean_text": clean_text(raw), "warnings": warnings}
