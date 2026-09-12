# Person A: local parsing

Install from the repository root with `python -m pip install -e ".[test]"`.
Run tests with `python -m pytest -q`.

```python
from evidencerank.parsing import parse_resume, parse_jd

resume = parse_resume("candidate.pdf")
jd = parse_jd("job_description.pdf")
# UTF-8 .txt files are also supported.
```

## Shared contract

Resume output is a plain JSON-serializable dictionary:

- `candidate_id`: string, `candidate_` plus 20 hex characters of the file's SHA-256. Identical bytes share an ID; changed files get new IDs. Unreadable/empty files use the absolute path as fallback. This is a document ID, not a verified person identity.
- `candidate_name`: string, best-effort first name-like header line, or empty string with a warning. Review before display; titles can resemble names.
- `raw_text`: original extracted text before cleaning, retained for downstream evidence.
- `sections`: exactly `skills`, `experience`, `projects`, `education`, `certifications`, each a string; missing/empty sections are `""`.
- `normalized_skills`: list of deduplicated canonical technology mentions across the cleaned document, in first-mention order. These are literal mentions, not verified skills, proficiency, scores, or semantic matches.
- `warnings`: list of strings.

JD output contains only `raw_text`, `clean_text`, `warnings`. Person B should consume `clean_text` to extract requirements; this module does not perform that step.

The plan PDF was not available in the repository during implementation. Keys match the supplied contract; field types and identity behavior above are explicit integration assumptions.

## Editable normalization

Edit `technology_aliases.json` beside the parser. Map a canonical name to a list of aliases. Canonical names are automatically recognized. Matching ignores case, respects token boundaries and technical punctuation, and prefers longer aliases. Unknown terms remain in text but are not added to `normalized_skills`.

Optionally call `parse_resume(path, config_path="team_aliases.json")` or `normalize_skills(text, config_path=...)`. Malformed/missing config raises a configuration error rather than silently disabling normalization. Conflicting aliases are rejected.

## Robustness and limits

PDF extraction uses local pypdf layout extraction. No network calls, credentials, external APIs, models, or OCR are used at runtime. Image-only pages return an OCR warning. Password-protected files, damaged PDFs, missing files, unsupported extensions, empty documents and text encoding replacements produce warnings. Successfully extracted pages survive individual page failures. Text fixtures use UTF-8; undecodable bytes are replaced and flagged.

Section detection supports case/spacing variations, inline colon headings, common aliases, bullets and repeated headings (appended). Known unrelated headings stop section collection. Unknown headings and complex multi-column reading order can be ambiguous; raw text is always retained. The parser does not guess absent sections or reconstruct lost PDF content. Add team-specific heading aliases in `parser.py` as needed.

Warnings include `file_unreadable`, `unsupported_format`, `pdf_encrypted`, `pdf_unreadable`, `page_unreadable:N`, `page_no_text:N:ocr_may_be_required`, `document_no_text`, `text_encoding_replacements`, `text_contains_replacement_characters`, `section_missing_or_empty:NAME`, and `candidate_name_not_detected`. Section warnings indicate absent extracted content; they do not establish that the source resume lacks that section.

## Scope and tests

Only Person A's extraction/cleaning/sectioning/normalization code is implemented. No UI, ranking, keyword scoring, semantic matching, or atomic JD requirements are included. Three synthetic text fixtures cover a complete resume, messy resume and generic JD. Tests also construct real PDFs in temporary directories to exercise extraction, blank pages, encryption and damage, and cover normalization/config, identity and failure contracts.
