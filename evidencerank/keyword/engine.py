"""Literal evidence only. No semantic inference, final ranking, or network IO."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from evidencerank.parsing import clean_text


DEFAULT_LEXICON = Path(__file__).parents[1] / "parsing" / "technology_aliases.json"
REQUIRED = re.compile(r"\b(?:must(?: have)?|required|mandatory|essential)\b", re.I)
PREFERRED = re.compile(r"\b(?:preferred|desirable|nice[- ]to[- ]have|a plus|a bonus|optional)\b", re.I)
HEADINGS = {
    "requirements": None, "qualifications": None, "skills": None,
    "technical skills": None, "responsibilities": None, "what you will do": None,
    "required": "required", "required skills": "required", "minimum qualifications": "required",
    "must have": "required", "must-have": "required", "essential skills": "required",
    "preferred": "preferred", "preferred qualifications": "preferred", "preferred skills": "preferred",
    "nice to have": "preferred", "nice-to-have": "preferred", "desirable": "preferred",
}
IGNORE_HEADINGS = {"about us", "about the company", "benefits", "what we offer", "compensation", "how to apply", "equal opportunity"}
NEGATED = re.compile(r"\b(?:no|not|without|never|lack(?:s|ing)?)\b[^.;\n]{0,65}$", re.I)


def _lexicon(path=None):
    config = json.loads(Path(path or DEFAULT_LEXICON).read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Lexicon must map canonical names to alias lists")
    lookup = {}
    for canonical, aliases in config.items():
        if not isinstance(canonical, str) or not canonical.strip() or not isinstance(aliases, list):
            raise ValueError("Invalid lexicon entry")
        for alias in [canonical, *aliases]:
            if not isinstance(alias, str) or not alias.strip():
                raise ValueError("Aliases must be nonempty strings")
            key = clean_text(alias).casefold()
            if key in lookup and lookup[key] != canonical:
                raise ValueError(f"Ambiguous alias: {alias}")
            lookup[key] = canonical
    return lookup


def _pattern(term):
    body = r"\s+".join(re.escape(part) for part in term.split())
    return re.compile(r"(?<![\w+#])" + body + r"(?![\w+#])", re.I)


def _literal_skill(fragment):
    # Remove linguistic scaffolding only; retain numeric and substantive constraints.
    value = re.sub(r"^(?:candidates? (?:must|should) have\s+|you (?:must|should) have\s+|must have\s+)", "", fragment, flags=re.I)
    value = re.sub(r"^(?:experience (?:with|in)|knowledge of|proficiency in|familiarity with|skilled in)\s+", "", value, flags=re.I)
    value = re.sub(r"^(?:required|preferred|mandatory|optional)\s*:?\s+", "", value, flags=re.I)
    value = re.sub(r"\s+(?:(?:is|are)\s+)?(?:required|preferred|mandatory|optional|desirable|a plus|a bonus)\s*$", "", value, flags=re.I)
    return value.strip(" .:;\t")


def extract_requirements(jd: str | dict, *, config_path=None) -> dict:
    """Return {requirements, warnings}; input is JD text or Person A's JD dict.

    type=None means wording did not specify priority. IDs repeat deterministically
    for identical input; editing/reordering the JD can renumber them.
    """
    lookup = _lexicon(config_path)
    raw = jd.get("clean_text", jd.get("raw_text", "")) if isinstance(jd, dict) else jd
    if not isinstance(raw, str):
        raise ValueError("JD must be text or a parsed JD dictionary")
    warnings = list(jd.get("warnings", [])) if isinstance(jd, dict) else []
    requirements = []
    context = None
    ignore = False
    seen = set()
    for original_line in clean_text(raw).splitlines():
        line = re.sub(r"^\s*(?:[-*•]+|\d+[.)])\s*", "", original_line).strip()
        if not line:
            continue
        label, colon, tail = line.partition(":")
        heading = label.casefold().strip()
        if heading in HEADINGS:
            context, ignore = HEADINGS[heading], False
            line = tail.strip() if colon else ""
        elif heading in IGNORE_HEADINGS:
            ignore = True
            continue
        elif line.endswith(":"):
            # Unknown section headings must not inherit required/preferred status.
            context, ignore = None, False
            warnings.append(f"unrecognized_heading:{line[:-1]}")
            continue
        if not line or ignore:
            continue
        # Periods followed by spaces terminate sentences; Node.js and .NET survive.
        for sentence in re.split(r";\s*|(?<=[.!?])\s+", line):
            if not sentence.strip():
                continue
            # Keep OR alternatives and qualifications in one unit for human review.
            alternative = bool(re.search(r"\bor\b", sentence, re.I))
            fragments = [sentence] if alternative else re.split(r",\s*|\s+and\s+", sentence, flags=re.I)
            required = bool(REQUIRED.search(sentence))
            preferred = bool(PREFERRED.search(sentence))
            shared_type = ("required" if required else "preferred") if required != preferred else context
            for fragment in fragments:
                fragment = fragment.strip(" .;\t")
                skill = _literal_skill(fragment)
                if not skill:
                    continue
                local_required, local_preferred = bool(REQUIRED.search(fragment)), bool(PREFERRED.search(fragment))
                req_type = ("required" if local_required else "preferred") if local_required != local_preferred else shared_type
                if required and preferred and not (local_required != local_preferred):
                    req_type = None
                ambiguous_priority = bool(re.search(r"\b(?:not|no)\b[^,;]{0,25}\brequired\b", fragment, re.I))
                if ambiguous_priority:
                    req_type = None
                canonical = lookup.get(skill.casefold(), skill)
                # Plain unknown standalone lines (e.g. a title) need review, never disappear.
                key = (canonical.casefold(), req_type, fragment.casefold())
                if key in seen:
                    continue
                seen.add(key)
                identifier = f"REQ{len(requirements) + 1:03d}"
                requirements.append({"id": identifier, "text": fragment, "skill": canonical, "type": req_type})
                if req_type is None:
                    warnings.append(f"priority_unspecified:{identifier}")
                if alternative or ambiguous_priority or canonical.casefold() not in lookup:
                    warnings.append(f"review_requirement:{identifier}")
    if not requirements:
        warnings.append("no_requirements_extracted")
    return {"requirements": requirements, "warnings": list(dict.fromkeys(warnings))}


def _validate_requirements(requirements):
    ids = set()
    for req in requirements:
        if any(not isinstance(req.get(key), str) or not req[key].strip() for key in ("id", "text", "skill")):
            raise ValueError("Each requirement needs nonempty id, text and skill strings")
        if req.get("type") not in {None, "required", "preferred"}:
            raise ValueError("Requirement type must be required, preferred or None")
        if req["id"] in ids:
            raise ValueError("Requirement IDs must be unique")
        ids.add(req["id"])


def match_candidate(candidate: dict, requirements: list[dict], *, config_path=None) -> dict:
    """Return per-requirement literal matches with scores on [0, 1].

    Exact and alias hits both receive 1.0; absent/negated evidence receives 0.0.
    Counts do not increase scores. No semantic or final candidate score is returned.
    """
    lookup = _lexicon(config_path)
    _validate_requirements(requirements)
    raw = candidate.get("raw_text", "")
    normalized = candidate.get("normalized_skills", [])
    if not isinstance(raw, str) or not isinstance(normalized, list) or any(not isinstance(s, str) for s in normalized):
        raise ValueError("Candidate raw_text must be a string and normalized_skills a list of strings")
    results = []
    for req in requirements:
        term = req["skill"]
        canonical = lookup.get(clean_text(term).casefold())
        aliases = [a for a, name in lookup.items() if canonical and name == canonical]
        hits = []
        negated = False
        for alias in dict.fromkeys([term, *aliases]):
            for match in _pattern(alias).finditer(raw):
                prefix = raw[max(0, match.start() - 70):match.start()]
                suffix = raw[match.end():match.end() + 45]
                if NEGATED.search(prefix) or re.match(r"\s*[:(-]?\s*(?:none|no experience|not (?:known|used))\b", suffix, re.I):
                    negated = True
                    continue
                exact = clean_text(match.group()).casefold() == clean_text(term).casefold()
                hits.append({"term": match.group(), "source": "raw_text", "start": match.start(), "end": match.end(), "match_type": "EXACT" if exact else "NORMALIZED"})
        unique = {(h["start"], h["end"]): h for h in hits}
        # React inside React.js is one alias mention, not a separate exact hit.
        longest = []
        for hit in sorted(unique.values(), key=lambda h: -(h["end"] - h["start"])):
            if not any(h["start"] <= hit["start"] and hit["end"] <= h["end"] for h in longest):
                longest.append(hit)
        hits = sorted(longest, key=lambda h: (h["match_type"] != "EXACT", h["start"]))
        # A structured skill can be used if raw text is unavailable, but never
        # override a detected negation or absence in an available raw document.
        if not hits and not raw.strip() and not negated and canonical:
            for skill in normalized:
                if lookup.get(clean_text(skill).casefold()) == canonical:
                    hits.append({"term": skill, "source": "normalized_skills", "start": None, "end": None, "match_type": "NORMALIZED"})
                    break
        best = hits[0] if hits else None
        evidence = ""
        if best and best["source"] == "raw_text":
            start = raw.rfind("\n", 0, best["start"]) + 1
            end = raw.find("\n", best["end"])
            evidence = raw[start:end if end >= 0 else len(raw)]
        results.append({**req, "keyword_score": 1.0 if hits else 0.0,
                        "match_type": best["match_type"] if best else "NOT_EVIDENCED",
                        "matched_terms": list(dict.fromkeys(h["term"] for h in hits)),
                        "matches": hits, "evidence": evidence,
                        "not_explicitly_evidenced": not bool(hits),
                        "warnings": (["negated_mention_ignored"] if negated else []) +
                        (["raw_evidence_unavailable"] if best and best["source"] == "normalized_skills" else [])})
    return {"candidate_id": candidate.get("candidate_id", ""),
            "candidate_name": candidate.get("candidate_name", ""), "requirements": results}


def match_candidates(candidates: list[dict], requirements: list[dict], *, config_path=None) -> list[dict]:
    """Preserve candidate order; Person C owns sorting/ranking."""
    return [match_candidate(c, requirements, config_path=config_path) for c in candidates]


def keyword_coverage(matches: list[dict], *, weights: dict | None = None) -> float:
    """Optional weighted keyword component only, [0,1]; default equal importance."""
    if weights is None:
        weights = json.loads(Path(__file__).with_name("weights.json").read_text())
    if set(weights) != {"required", "preferred", "unspecified"} or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in weights.values()
    ):
        raise ValueError("Weights must provide finite nonnegative required, preferred and unspecified values")
    numerator = denominator = 0.0
    for row in matches:
        kind = row.get("type")
        if kind not in {None, "required", "preferred"}:
            raise ValueError("Invalid requirement type")
        score = row["keyword_score"]
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("Keyword scores must be finite numbers on [0,1]")
        weight = weights[kind or "unspecified"]
        numerator += weight * score
        denominator += weight
    if matches and denominator == 0:
        raise ValueError("At least one matched requirement must have positive weight")
    return numerator / denominator if denominator else 0.0
