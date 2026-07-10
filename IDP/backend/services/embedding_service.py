"""
Embedding Service — Legal NLP/LLM Module
==========================================
Phase 2 embedding service. Provides sentence embeddings via
``sentence-transformers/all-MiniLM-L6-v2``, manages per-document FAISS
indices on disk, and exposes similarity search and cross-document search.

The embedding model singleton is managed at module level and lazy-loaded on
first use (Task 10.1 / 10.2).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Path setup — allow imports from backend/models when running tests directly
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from models.nlp_models import ChunkInfo, ChunkResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FAISS index directory — relative to this file's parent (backend/)
# ---------------------------------------------------------------------------
_FAISS_DIR = os.path.join(_BACKEND_DIR, "faiss_index")

# ---------------------------------------------------------------------------
# Task 10.1 — Module-level embedding model singleton (initially None)
# ---------------------------------------------------------------------------
_EMBEDDING_MODEL: Any = None


# ---------------------------------------------------------------------------
# Task 10.2 — Lazy-load the sentence-transformer model
# ---------------------------------------------------------------------------

def get_embedding_model() -> Any:
    """Lazy-load ``sentence-transformers/all-MiniLM-L6-v2`` and return the
    singleton instance.

    The model is stored in the module-level ``_EMBEDDING_MODEL`` variable and
    reused on subsequent calls.

    Returns
    -------
    SentenceTransformer
        The loaded model instance.

    Raises
    ------
    RuntimeError
        If the model cannot be loaded.
    """
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            _EMBEDDING_MODEL = SentenceTransformer(
                "sentence-transformers/all-MiniLM-L6-v2"
            )
            logger.info("Loaded embedding model: sentence-transformers/all-MiniLM-L6-v2")
        except Exception as exc:
            logger.error("Failed to load embedding model: %s", exc, exc_info=True)
            raise RuntimeError(f"Embedding model unavailable: {exc}") from exc
    return _EMBEDDING_MODEL


# ---------------------------------------------------------------------------
# Task 10.3 — embed_text: single text → shape-(384,) L2-normalised embedding
# ---------------------------------------------------------------------------

def embed_text(text: str) -> np.ndarray:
    """Embed a single text string and return an L2-normalised 384-dim vector.

    Parameters
    ----------
    text:
        Non-empty input string.

    Returns
    -------
    np.ndarray
        Shape ``(384,)`` float32 array with L2 norm ≈ 1.0.
        Returns a zero vector of shape ``(384,)`` on error.
    """
    try:
        model = get_embedding_model()
        embedding: np.ndarray = model.encode(text, normalize_embeddings=True)
        # Ensure 1-D shape (384,)
        embedding = np.asarray(embedding, dtype=np.float32).flatten()
        # Re-normalise defensively (model may already normalise)
        norm = np.linalg.norm(embedding)
        if norm > 0.0:
            embedding = embedding / norm
        return embedding
    except Exception as exc:
        logger.error("embed_text() failed: %s", exc, exc_info=True)
        return np.zeros(384, dtype=np.float32)


# ---------------------------------------------------------------------------
# Task 10.4 — embed_chunks: list[str] → shape-(N, 384) L2-normalised matrix
# ---------------------------------------------------------------------------

def embed_chunks(chunks: list[str]) -> np.ndarray:
    """Embed a list of text strings and return an L2-normalised matrix.

    Parameters
    ----------
    chunks:
        List of text strings to embed.

    Returns
    -------
    np.ndarray
        Shape ``(N, 384)`` float32 array where each row has L2 norm ≈ 1.0.
        Returns an empty array of shape ``(0, 384)`` on error.
    """
    try:
        if not chunks:
            return np.zeros((0, 384), dtype=np.float32)
        model = get_embedding_model()
        embeddings: np.ndarray = model.encode(
            chunks, normalize_embeddings=True, show_progress_bar=False
        )
        embeddings = np.asarray(embeddings, dtype=np.float32)
        # Re-normalise each row defensively
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms > 0.0, norms, 1.0)
        embeddings = embeddings / norms
        return embeddings
    except Exception as exc:
        logger.error("embed_chunks() failed: %s", exc, exc_info=True)
        return np.zeros((0, 384), dtype=np.float32)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _index_path(doc_id: str) -> str:
    return os.path.join(_FAISS_DIR, f"{doc_id}.index")


def _meta_path(doc_id: str) -> str:
    return os.path.join(_FAISS_DIR, f"{doc_id}.meta.json")


def _write_json(path: str, data: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Task 10.5 — build_index: Algorithm 7
# ---------------------------------------------------------------------------

def build_index(doc_id: str, chunks: list[ChunkInfo]):  # -> faiss.Index
    """Build a FAISS ``IndexFlatIP`` from *chunks*, persist it to disk, and
    return the index.

    Implements Algorithm 7 from the design document.

    Parameters
    ----------
    doc_id:
        Unique document identifier used as the filename stem.
    chunks:
        List of :class:`~models.nlp_models.ChunkInfo` objects.

    Returns
    -------
    faiss.Index
        The built index with ``ntotal == len(chunks)``.
        Returns ``None`` on error.
    """
    try:
        import faiss  # type: ignore

        texts = [c.text for c in chunks]
        embeddings = embed_chunks(texts)

        # If embed_chunks returned an empty matrix (error path), abort
        if embeddings.shape[0] == 0:
            logger.error(
                "build_index() aborted for doc_id=%s: embed_chunks returned empty matrix",
                doc_id,
            )
            return None

        dim = embeddings.shape[1]  # 384
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        # Persist index
        os.makedirs(_FAISS_DIR, exist_ok=True)
        faiss.write_index(index, _index_path(doc_id))

        # Persist metadata
        metadata = [
            {"text": c.text, "start": c.start_char, "index": c.index}
            for c in chunks
        ]
        _write_json(_meta_path(doc_id), metadata)

        logger.info(
            "Built FAISS index for doc_id=%s with %d vectors", doc_id, index.ntotal
        )
        return index
    except Exception as exc:
        logger.error("build_index() failed for doc_id=%s: %s", doc_id, exc, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Task 10.6 — load_index: read from disk; return None if missing
# ---------------------------------------------------------------------------

def load_index(doc_id: str):  # -> faiss.Index | None
    """Load a persisted FAISS index from disk.

    Parameters
    ----------
    doc_id:
        Document identifier whose index file is at
        ``faiss_index/{doc_id}.index``.

    Returns
    -------
    faiss.Index or None
        The loaded index, or ``None`` if the file does not exist or an error
        occurs.
    """
    try:
        import faiss  # type: ignore

        path = _index_path(doc_id)
        if not os.path.exists(path):
            return None
        index = faiss.read_index(path)
        logger.debug("Loaded FAISS index for doc_id=%s (%d vectors)", doc_id, index.ntotal)
        return index
    except Exception as exc:
        logger.error("load_index() failed for doc_id=%s: %s", doc_id, exc, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Task 10.7 — get_or_create_index
# ---------------------------------------------------------------------------

def get_or_create_index(doc_id: str, text: str):  # -> faiss.Index
    """Return the existing FAISS index for *doc_id*, or build one from *text*.

    If an index file already exists on disk it is loaded and returned.
    Otherwise the document text is chunked and a new index is built and
    persisted.

    Parameters
    ----------
    doc_id:
        Document identifier.
    text:
        Full document text used to build the index if it does not exist.

    Returns
    -------
    faiss.Index or None
        The index, or ``None`` on error.
    """
    try:
        existing = load_index(doc_id)
        if existing is not None:
            return existing

        # Build from text — import chunk_document here to avoid circular imports
        from services.nlp_service import chunk_document  # type: ignore

        chunks = chunk_document(text)
        return build_index(doc_id, chunks)
    except Exception as exc:
        logger.error(
            "get_or_create_index() failed for doc_id=%s: %s", doc_id, exc, exc_info=True
        )
        return None


# ---------------------------------------------------------------------------
# Task 10.8 — similarity_search: Algorithm 7 search path
# ---------------------------------------------------------------------------

def similarity_search(
    query: str,
    doc_id: str,
    k: int = 4,
) -> list[ChunkResult]:
    """Search the FAISS index for *doc_id* and return the top-*k* chunks.

    Implements the similarity_search algorithm from Algorithm 7 in the design
    document.

    Parameters
    ----------
    query:
        Natural language query string.
    doc_id:
        Document to search within.
    k:
        Number of results to return (default 4).

    Returns
    -------
    list[ChunkResult]
        At most *k* results sorted by descending score.
        Returns an empty list on error or if the index does not exist.
    """
    try:
        import faiss  # type: ignore

        idx_path = _index_path(doc_id)
        meta_path = _meta_path(doc_id)

        if not os.path.exists(idx_path):
            logger.warning("similarity_search: index not found for doc_id=%s", doc_id)
            return []

        index = faiss.read_index(idx_path)
        metadata = _read_json(meta_path)

        model = get_embedding_model()
        query_vec: np.ndarray = model.encode(
            [query], normalize_embeddings=True
        )
        query_vec = np.asarray(query_vec, dtype=np.float32)

        scores, indices = index.search(query_vec, k)

        results: list[ChunkResult] = []
        for i in range(len(indices[0])):
            idx = int(indices[0][i])
            if idx >= 0:  # FAISS returns -1 for empty slots
                score = float(scores[0][i])
                # Clamp score to [0.0, 1.0] (cosine similarity on normalised vectors)
                score = max(0.0, min(1.0, score))
                results.append(
                    ChunkResult(
                        chunk_text=metadata[idx]["text"],
                        doc_id=doc_id,
                        chunk_index=int(metadata[idx]["index"]),
                        score=score,
                    )
                )

        # FAISS IndexFlatIP already returns results in descending score order,
        # but sort explicitly to guarantee the postcondition.
        results.sort(key=lambda r: r.score, reverse=True)
        return results
    except Exception as exc:
        logger.error(
            "similarity_search() failed for doc_id=%s: %s", doc_id, exc, exc_info=True
        )
        return []


# ---------------------------------------------------------------------------
# Task 10.9 — cross_document_search
# ---------------------------------------------------------------------------

def cross_document_search(
    query: str,
    doc_ids: list[str],
    k: int = 10,
) -> list[ChunkResult]:
    """Search across multiple FAISS indices and return the top-*k* results.

    Missing indices are silently skipped (Property 15).

    Parameters
    ----------
    query:
        Natural language query string.
    doc_ids:
        List of document identifiers to search.
    k:
        Total number of results to return (default 10).

    Returns
    -------
    list[ChunkResult]
        At most *k* results merged from all available indices, sorted by
        descending score.  Returns an empty list on error.
    """
    try:
        all_results: list[ChunkResult] = []
        for doc_id in doc_ids:
            if not os.path.exists(_index_path(doc_id)):
                logger.debug(
                    "cross_document_search: skipping missing index for doc_id=%s", doc_id
                )
                continue
            doc_results = similarity_search(query, doc_id, k=k)
            all_results.extend(doc_results)

        # Merge and sort by descending score, then take top-k
        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results[:k]
    except Exception as exc:
        logger.error("cross_document_search() failed: %s", exc, exc_info=True)
        return []
