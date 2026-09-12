"""
Shared data-contract definitions for the EvidenceRank hackathon project.

Single source of truth for the shapes passed between:
    Person 1 -> parse_jd() / parse_resume()
    Person 2 -> keyword / normalized requirement matching
    Person 3 -> semantic matching, Evidence Ledger, final scoring & ranking
    Person 4 -> app / UI consumption of CandidateResult

STATUS: PROPOSED by Person 3. Pending confirmation from Person 1 and Person 2.
Open questions are marked with `# CONFIRM:` comments - see CONTRACT.md for the
full list and rationale.

No third-party imports here on purpose: this module must be importable by
everyone's code without pulling in any person's specific dependencies.
"""

from typing import List, Literal, Optional, TypedDict


# ---------------------------------------------------------------------------
# Person 1 -> everyone: JD parsing output
# ---------------------------------------------------------------------------

RequirementType = Literal["required", "preferred"]


class JDRequirement(TypedDict):
    id: str            # stable id, e.g. "REQ001"
    text: str           # atomic requirement sentence, e.g. "3+ years of Python experience"
    skill: str           # canonical skill/keyword extracted from `text`, e.g. "python"
    type: RequirementType


class ParsedJD(TypedDict):
    raw_text: str
    requirements: List[JDRequirement]


# ---------------------------------------------------------------------------
# Person 1 -> everyone: Resume parsing output
# ---------------------------------------------------------------------------

class ResumeSections(TypedDict):
    # CONFIRM (Person 1): each section must be a list of resume CHUNKS
    # (bullet points / sentences), not one raw blob string per section.
    # Person 3 needs chunk-level granularity to compare each JD requirement
    # against individual pieces of resume evidence, not the whole section at once.
    skills: List[str]
    experience: List[str]
    projects: List[str]
    education: List[str]
    certifications: List[str]


class ParsedResume(TypedDict):
    candidate_id: str
    candidate_name: str
    raw_text: str
    sections: ResumeSections
    # CONFIRM (Person 1): canonicalized/alias-mapped skill strings,
    # e.g. "js" -> "javascript", "k8s" -> "kubernetes".
    normalized_skills: List[str]
    warnings: List[str]


# ---------------------------------------------------------------------------
# Person 2 -> Person 3: keyword / normalized requirement matcher output
# ---------------------------------------------------------------------------

class KeywordMatchResult(TypedDict):
    candidate_id: str
    requirement_id: str            # must match a JDRequirement["id"]
    # CONFIRM (Person 2): scale is 0.0-1.0 (coverage/match ratio), not 0-100.
    keyword_score: float
    matched_terms: List[str]        # literal terms found in resume text supporting this requirement
    # CONFIRM (Person 2): set to the normalized/aliased form that matched
    # (e.g. resume term "js" matched requirement skill "javascript" via an
    # alias table), or None if the match was direct/literal, or no match found.
    normalized_match: Optional[str]


# ---------------------------------------------------------------------------
# Person 3 (internal): semantic matcher output.
# Not part of the cross-team contract - consumed only by the Evidence Ledger
# builder inside Person 3's own module. Listed here for transparency.
# ---------------------------------------------------------------------------

class SemanticMatchResult(TypedDict):
    candidate_id: str
    requirement_id: str
    semantic_score: float           # cosine similarity in [0.0, 1.0]
    best_evidence_text: str          # highest-similarity resume chunk for this requirement
    best_evidence_section: str       # which ResumeSections key best_evidence_text came from


# ---------------------------------------------------------------------------
# Person 3 -> Person 4: Evidence Ledger entry (one per candidate x requirement)
# ---------------------------------------------------------------------------

MatchType = Literal["EXACT", "NORMALIZED", "SEMANTIC", "NOT_EVIDENCED"]


class EvidenceLedgerEntry(TypedDict):
    id: str                # requirement id
    text: str                # requirement text, copied from JDRequirement for display
    keyword_score: float
    semantic_score: float
    match_type: MatchType
    # Verbatim resume chunk supporting the match; "" if NOT_EVIDENCED.
    # Must always be a real substring taken from the resume - never fabricated.
    evidence: str


# ---------------------------------------------------------------------------
# Person 3 -> Person 4: final candidate result (one per candidate)
# ---------------------------------------------------------------------------

class ScoreBreakdown(TypedDict):
    keyword: float             # 0-100
    semantic: float            # 0-100
    experience: float          # 0-100
    evidence_strength: float    # 0-100


class CandidateResult(TypedDict):
    candidate_id: str
    candidate_name: str
    final_score: float           # 0-100
    score_breakdown: ScoreBreakdown
    requirements: List[EvidenceLedgerEntry]


# ---------------------------------------------------------------------------
# Person 3: scoring weights (contract only - implementation pending approval)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS = {
    "semantic": 0.40,
    "keyword": 0.35,
    "experience": 0.15,
    "evidence_strength": 0.10,
}


def compute_final_score(component_scores: dict, weights: dict = DEFAULT_WEIGHTS) -> float:
    """
    Signature contract only. Implementation pending approval - see CONTRACT.md.

    component_scores: {"keyword": float, "semantic": float, "experience": float,
                        "evidence_strength": float}, each on a 0-100 scale.
    weights: same keys, values summing to 1.0.
    Returns a single 0-100 float.
    """
    raise NotImplementedError("Awaiting approval to implement.")
