"""
Person 3: requirement-level semantic matching.

Embeds each JD requirement and each individual resume chunk (never the whole
resume as one blob) using a local sentence-transformers model
(all-MiniLM-L6-v2 by default) and retrieves, for every requirement, the
single best-matching resume chunk plus its similarity score.

No network calls happen at match time: the embedding model is loaded once
(and cached) from local/HF-cache weights. Nothing here calls an LLM or any
external API.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional, Protocol, Tuple

from schemas import ParsedJD, ParsedResume, SemanticMatchResult

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class Embedder(Protocol):
    """Minimal interface semantic_matcher needs from an embedding model.

    Kept abstract so tests can inject a fast, deterministic fake instead of
    loading real model weights.
    """

    def encode(self, texts: List[str]):  # -> Sequence[Sequence[float]]
        ...


class SentenceTransformerEmbedder:
    """Thin wrapper around sentence-transformers, loaded lazily and once."""

    def __init__(self, model_name: str = MODEL_NAME):
        from sentence_transformers import SentenceTransformer  # local import: optional heavy dep

        self._model = SentenceTransformer(model_name)

    def encode(self, texts: List[str]):
        return self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)


@lru_cache(maxsize=1)
def get_default_embedder() -> "SentenceTransformerEmbedder":
    """Singleton so the model is only loaded into memory once per process."""
    return SentenceTransformerEmbedder()


def flatten_resume_chunks(resume: ParsedResume) -> List[Tuple[str, str]]:
    """Flatten resume['sections'] into a flat list of (section_name, chunk_text).

    Empty/whitespace-only chunks are dropped. Order follows the section dict's
    own iteration order, then each section's chunk order.
    """
    chunks: List[Tuple[str, str]] = []
    for section_name, section_chunks in resume["sections"].items():
        for chunk in section_chunks:
            if chunk and chunk.strip():
                chunks.append((section_name, chunk.strip()))
    return chunks


def _cosine_similarity_matrix(a, b):
    """Cosine similarity between every row of `a` and every row of `b`.

    Works with plain nested lists or numpy arrays so tests can use a fake
    embedder that returns plain Python lists without requiring numpy.
    """
    import numpy as np

    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a_norm = a / np.clip(np.linalg.norm(a, axis=1, keepdims=True), 1e-12, None)
    b_norm = b / np.clip(np.linalg.norm(b, axis=1, keepdims=True), 1e-12, None)
    return a_norm @ b_norm.T


def compute_semantic_matches(
    jd: ParsedJD,
    resume: ParsedResume,
    embedder: Optional[Embedder] = None,
) -> List[SemanticMatchResult]:
    """For every requirement in `jd`, find the best-matching resume chunk for
    `resume` (a single candidate) and return one SemanticMatchResult per
    requirement, in the same order as jd['requirements'].

    If the resume has no usable chunks at all, every requirement gets
    semantic_score=0.0 and empty evidence (never fabricated).
    """
    requirements = jd["requirements"]
    candidate_id = resume["candidate_id"]
    chunks = flatten_resume_chunks(resume)

    if not requirements:
        return []

    if not chunks:
        return [
            {
                "candidate_id": candidate_id,
                "requirement_id": req["id"],
                "semantic_score": 0.0,
                "best_evidence_text": "",
                "best_evidence_section": "",
            }
            for req in requirements
        ]

    embedder = embedder or get_default_embedder()
    requirement_texts = [req["text"] for req in requirements]
    chunk_texts = [text for _, text in chunks]

    requirement_vectors = embedder.encode(requirement_texts)
    chunk_vectors = embedder.encode(chunk_texts)
    similarity = _cosine_similarity_matrix(requirement_vectors, chunk_vectors)

    results: List[SemanticMatchResult] = []
    for row_idx, req in enumerate(requirements):
        row = similarity[row_idx]
        best_idx = int(row.argmax())
        best_score = float(row[best_idx])
        # schemas.py contracts semantic_score to [0.0, 1.0]; cosine similarity
        # can technically go negative or drift a hair outside [-1, 1].
        best_score = max(0.0, min(1.0, best_score))
        best_section, best_text = chunks[best_idx]
        results.append(
            {
                "candidate_id": candidate_id,
                "requirement_id": req["id"],
                "semantic_score": best_score,
                "best_evidence_text": best_text,
                "best_evidence_section": best_section,
            }
        )
    return results
