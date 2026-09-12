"""
Shared mock fixtures for Person 3's test suite.

Person 1 and Person 2 have not pushed implementations yet, so these fixtures
hand-build data that conforms to schemas.py (ParsedJD, ParsedResume,
KeywordMatchResult) to stand in for their output. Once real implementations
land, these fixtures should be swapped for (or cross-checked against) real
parser/matcher output -- see CONTRACT.md.
"""

import sys
from pathlib import Path
from typing import List

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factories import make_keyword_result  # noqa: E402


class FakeEmbedder:
    """Deterministic, dependency-free stand-in for the real sentence
    transformer. Encodes each text as a bag-of-words indicator vector over a
    fixed vocabulary, so cosine similarity reflects simple word overlap.
    Lets semantic_matcher tests run instantly, offline, with no model
    download.
    """

    VOCAB = [
        "python", "aws", "docker", "sql", "communication", "java", "spring",
        "mysql", "container", "kubernetes", "cloud", "database", "verbal",
        "written", "lambda", "postgresql", "microservice", "analytics",
    ]

    def encode(self, texts: List[str]):
        vectors = []
        for text in texts:
            lower = text.lower()
            vectors.append([1.0 if word in lower else 0.0 for word in self.VOCAB])
        return vectors


@pytest.fixture
def fake_embedder():
    return FakeEmbedder()


@pytest.fixture
def sample_jd():
    return {
        "raw_text": (
            "We need a backend engineer skilled in Python, AWS, and Docker "
            "with strong SQL and communication skills."
        ),
        "requirements": [
            {"id": "REQ001", "text": "3+ years of experience with Python", "skill": "python", "type": "required"},
            {"id": "REQ002", "text": "Experience deploying services on AWS cloud", "skill": "aws", "type": "required"},
            {"id": "REQ003", "text": "Familiarity with Docker containerization", "skill": "docker", "type": "preferred"},
            {"id": "REQ004", "text": "Strong SQL database query skills", "skill": "sql", "type": "required"},
            {"id": "REQ005", "text": "Excellent written and verbal communication", "skill": "communication", "type": "preferred"},
        ],
    }


@pytest.fixture
def resume_strong():
    """A candidate whose resume should score well: literal keyword overlap
    on most requirements plus semantically relevant experience bullets."""
    return {
        "candidate_id": "cand-1",
        "candidate_name": "Alice Example",
        "raw_text": "Alice Example resume text ...",
        "sections": {
            "skills": ["Python", "AWS", "Docker", "SQL"],
            "experience": [
                "Built and deployed backend microservices in Python on AWS Lambda for 4 years.",
                "Containerized applications with Docker as part of a cloud migration.",
            ],
            "projects": [
                "Designed a PostgreSQL analytics pipeline with complex SQL database queries.",
            ],
            "education": ["B.S. in Computer Science, State University"],
            "certifications": ["AWS Certified Solutions Architect"],
        },
        "normalized_skills": ["python", "aws", "docker", "sql"],
        "warnings": [],
    }


@pytest.fixture
def resume_weak():
    """A candidate with little literal or semantic overlap with the JD."""
    return {
        "candidate_id": "cand-2",
        "candidate_name": "Bob Example",
        "raw_text": "Bob Example resume text ...",
        "sections": {
            "skills": ["Java", "Spring", "MySQL"],
            "experience": [
                "Developed enterprise Java applications using the Spring framework for 5 years.",
                "Wrote MySQL database queries for internal reporting dashboards.",
            ],
            "projects": [],
            "education": ["B.S. in Information Systems"],
            "certifications": [],
        },
        "normalized_skills": ["java", "spring", "mysql"],
        "warnings": [],
    }


@pytest.fixture
def resume_empty():
    """Edge case: parser produced no usable chunks at all."""
    return {
        "candidate_id": "cand-3",
        "candidate_name": "Empty Example",
        "raw_text": "",
        "sections": {"skills": [], "experience": [], "projects": [], "education": [], "certifications": []},
        "normalized_skills": [],
        "warnings": ["Could not extract any resume text."],
    }


@pytest.fixture
def keyword_results_strong():
    """Mocked Person 2 output for resume_strong: literal matches on the
    first four requirements, nothing for communication."""
    cid = "cand-1"
    return [
        make_keyword_result(cid, "REQ001", keyword_score=1.0, matched_terms=["Python"]),
        make_keyword_result(cid, "REQ002", keyword_score=1.0, matched_terms=["AWS"]),
        make_keyword_result(cid, "REQ003", keyword_score=1.0, matched_terms=["Docker"]),
        make_keyword_result(cid, "REQ004", keyword_score=1.0, matched_terms=["SQL"]),
        make_keyword_result(cid, "REQ005", keyword_score=0.0),
    ]


@pytest.fixture
def keyword_results_weak():
    """Mocked Person 2 output for resume_weak: one normalized match, the
    rest unmatched."""
    cid = "cand-2"
    return [
        make_keyword_result(cid, "REQ001", keyword_score=0.0),
        make_keyword_result(cid, "REQ002", keyword_score=0.0),
        make_keyword_result(cid, "REQ003", keyword_score=0.0),
        make_keyword_result(cid, "REQ004", keyword_score=0.6, normalized_match="sql"),
        make_keyword_result(cid, "REQ005", keyword_score=0.0),
    ]
