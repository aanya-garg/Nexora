"""
JD Quality / Bias Lens.

Local, transparent pattern checks only -- no LLM, no scoring influence.
This is intentionally a small, EDITABLE rule set: extend BIAS_PATTERNS or
NAMED_TOOLS as your team reviews the real JD, rather than rewriting the
detection logic.
"""

import re

BIAS_PATTERNS = [
    {
        "pattern": r"\brock\s*star\b|\bninja\b|\bguru\b|\bwizard\b",
        "category": "Exclusionary tone",
        "reason": "Informal, macho-coded job-title language can discourage some qualified applicants from applying.",
        "rewrite": 'Use a neutral skill description instead, e.g. "experienced developer" or "skilled engineer."',
    },
    {
        "pattern": r"\bdigital\s+native\b|\brecent\s+graduate\b|\byoung\s+and\s+energetic\b",
        "category": "Potential age bias",
        "reason": "This phrasing can read as a preference for younger candidates, which is not a genuine skill requirement.",
        "rewrite": 'Describe the actual skill needed (e.g. "comfortable learning new tools quickly") instead of referencing age or career stage.',
    },
    {
        "pattern": r"\bhe\b|\bhis\b|\bhimself\b",
        "category": "Gendered language",
        "reason": "Gender-specific pronouns can signal an unintended preference.",
        "rewrite": 'Use "they/their" or refer to "the candidate" instead.',
    },
]

# Checked separately because it needs surrounding context (seniority) and a
# capture group, rather than a fixed phrase.
SENIORITY_KEYWORDS = r"\b(?:intern(?:ship)?|junior|entry[\s-]+level)\b"


def _check_seniority_mismatch(jd_text: str) -> list:
    issues = []
    is_junior_role = bool(re.search(SENIORITY_KEYWORDS, jd_text, re.I))
    if not is_junior_role:
        return issues
    for m in re.finditer(r"\b(\d+)\+?\s*years?\b", jd_text, re.I):
        years = int(m.group(1))
        if years >= 3:
            issues.append({
                "phrase": m.group(0),
                "category": "Seniority mismatch",
                "reason": "A high years-of-experience figure on an internship/entry-level posting can "
                          "screen out qualified junior candidates unnecessarily.",
                "suggested_rewrite": "Confirm this figure matches the role's actual seniority; lower or remove it if the role is entry-level.",
            })
    return issues


NAMED_TOOLS = ["React", "Node.js", "NodeJS", "MongoDB", "Angular", "Vue", "Docker", "Kubernetes"]


def _check_narrow_tool_requirements(jd_text: str) -> list:
    issues = []
    for tool in NAMED_TOOLS:
        for m in re.finditer(r"(?<![\w+#])" + re.escape(tool) + r"(?![\w+#])", jd_text, re.I):
            window = jd_text[max(0, m.start() - 40): m.end() + 40]
            if not re.search(r"\bor\b|\bequivalent\b|\bsimilar\b", window, re.I):
                issues.append({
                    "phrase": m.group(0),
                    "category": "Overly narrow tool requirement",
                    "reason": f"'{tool}' is named with no 'or equivalent' option, which can exclude "
                              f"candidates with comparable skills in alternative tools.",
                    "suggested_rewrite": f'Consider: "experience with a modern tool such as {tool} (or equivalent)" '
                                         f"if the underlying skill matters more than the specific tool.",
                })
    return issues


def detect_jd_issues(jd_raw_text: str) -> list:
    issues = []
    for rule in BIAS_PATTERNS:
        for m in re.finditer(rule["pattern"], jd_raw_text, re.I):
            issues.append({
                "phrase": m.group(0),
                "category": rule["category"],
                "reason": rule["reason"],
                "suggested_rewrite": rule["rewrite"],
            })
    issues += _check_seniority_mismatch(jd_raw_text)
    issues += _check_narrow_tool_requirements(jd_raw_text)

    seen = set()
    deduped = []
    for i in issues:
        key = (i["phrase"].lower(), i["category"])
        if key not in seen:
            seen.add(key)
            deduped.append(i)
    return deduped
