"""
Property-based and unit tests for ``embedding_service``.

Tests cover Properties 12, 13, 14, and 15 from the design document:

  - Property 12: embed_text returns shape-(384,) L2-normalised vector
  - Property 13: build_index produces index.ntotal == len(chunks)
  - Property 14: similarity_search results are sorted descending, len <= k,
                 scores in [0.0, 1.0]
  - Property 15: cross_document_search skips missing indices gracefully

All tests mock ``sentence_transformers.SentenceTransformer`` and ``faiss``
so no real models are needed.

**Validates: Requirements 7.2, 7.3, 7.4, 7.5, 8.2, 8.3, 8.4, 8.5, 8.6, 8.8**
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Ensure backend/ is on sys.path so relative imports resolve correctly
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from models.nlp_models import ChunkInfo, ChunkResult


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_unit_vec(dim: int = 384, seed: int = 0) -> np.ndarray:
    """Return a deterministic L2-normalised float32 vector of length *dim*."""
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(dim).astype(np.float32)
    return v / np.linalg.norm(v)


def _make_embedding_matrix(n: int, dim: int = 384, seed: int = 42) -> np.ndarray:
    """Return an (n, dim) matrix of L2-normalised float32 rows."""
    rng = np.random.default_rng(seed)
    mat = rng.standard_normal((n, dim)).astype(np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    return mat / norms


def _make_mock_model(n_texts: int = 1, dim: int = 384, seed: int = 0) -> MagicMock:
    """Return a mock SentenceTransformer whose ``encode`` returns normalised vecs."""
    mock = MagicMock()

    def _encode(texts, normalize_embeddings=True, show_progress_bar=False):
        if isinstance(texts, str):
            return _make_unit_vec(dim, seed)
        n = len(texts)
        return _make_embedding_matrix(n, dim, seed)

    mock.encode.side_effect = _encode
    return mock


def _make_chunks(n: int) -> list[ChunkInfo]:
    return [
        ChunkInfo(text=f"chunk text {i}", start_char=i * 10, end_char=(i + 1) * 10, index=i)
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Context manager: patch the module-level singleton and faiss_index dir
# ---------------------------------------------------------------------------

class _EmbeddingPatch:
    """Context manager that patches the embedding model singleton and
    redirects the FAISS index directory to a temp folder."""

    def __init__(self, n_texts: int = 1, seed: int = 0):
        self._mock_model = _make_mock_model(n_texts, seed=seed)
        self._tmpdir = tempfile.mkdtemp()

    def __enter__(self):
        import services.embedding_service as svc

        self._orig_model = svc._EMBEDDING_MODEL
        self._orig_faiss_dir = svc._FAISS_DIR
        svc._EMBEDDING_MODEL = self._mock_model
        svc._FAISS_DIR = self._tmpdir
        return self._mock_model, self._tmpdir

    def __exit__(self, *_):
        import services.embedding_service as svc

        svc._EMBEDDING_MODEL = self._orig_model
        svc._FAISS_DIR = self._orig_faiss_dir


# ===========================================================================
# Property 12: embed_text returns shape-(384,) L2-normalised vector
# **Validates: Requirements 7.2, 7.6**
# ===========================================================================

class TestEmbedText:
    """Unit tests for embed_text()."""

    def test_embed_text_shape(self):
        """embed_text returns a 1-D array of length 384."""
        with _EmbeddingPatch() as (mock_model, _):
            from services.embedding_service import embed_text

            result = embed_text("some legal text")
            assert result.shape == (384,)

    def test_embed_text_l2_norm_approx_one(self):
        """embed_text returns a vector whose L2 norm is within 0.01 of 1.0."""
        with _EmbeddingPatch() as (mock_model, _):
            from services.embedding_service import embed_text

            result = embed_text("contract clause indemnity")
            norm = float(np.linalg.norm(result))
            assert abs(norm - 1.0) < 0.01, f"L2 norm was {norm}, expected ≈ 1.0"

    def test_embed_text_dtype_float32(self):
        """embed_text returns a float32 array."""
        with _EmbeddingPatch() as (mock_model, _):
            from services.embedding_service import embed_text

            result = embed_text("hello world")
            assert result.dtype == np.float32

    def test_embed_text_error_returns_zero_vector(self):
        """embed_text returns a zero vector of shape (384,) on model error."""
        import services.embedding_service as svc

        orig = svc._EMBEDDING_MODEL
        try:
            bad_model = MagicMock()
            bad_model.encode.side_effect = RuntimeError("model exploded")
            svc._EMBEDDING_MODEL = bad_model
            result = svc.embed_text("text")
            assert result.shape == (384,)
            assert np.all(result == 0.0)
        finally:
            svc._EMBEDDING_MODEL = orig


class TestEmbedChunks:
    """Unit tests for embed_chunks()."""

    def test_embed_chunks_shape(self):
        """embed_chunks returns shape (N, 384) for N input strings."""
        with _EmbeddingPatch(n_texts=5) as (mock_model, _):
            from services.embedding_service import embed_chunks

            texts = [f"chunk {i}" for i in range(5)]
            result = embed_chunks(texts)
            assert result.shape == (5, 384)

    def test_embed_chunks_each_row_normalised(self):
        """Every row of embed_chunks output has L2 norm ≈ 1.0."""
        with _EmbeddingPatch(n_texts=3) as (mock_model, _):
            from services.embedding_service import embed_chunks

            texts = ["alpha", "beta", "gamma"]
            result = embed_chunks(texts)
            norms = np.linalg.norm(result, axis=1)
            assert np.all(np.abs(norms - 1.0) < 0.01), f"Norms: {norms}"

    def test_embed_chunks_empty_list(self):
        """embed_chunks returns shape (0, 384) for an empty list."""
        with _EmbeddingPatch() as (mock_model, _):
            from services.embedding_service import embed_chunks

            result = embed_chunks([])
            assert result.shape == (0, 384)


# ===========================================================================
# Property 12 — Hypothesis property test
# **Validates: Requirements 7.2, 7.6**
# ===========================================================================

@given(text=st.text(min_size=1, max_size=200))
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_12_embed_text_shape_and_norm(text):
    """
    **Validates: Requirements 7.2, 7.6**

    Property 12: For any non-empty text string, embed_text() SHALL return a
    1D numpy array of shape (384,) whose L2 norm is within 0.01 of 1.0.
    """
    import services.embedding_service as svc

    orig_model = svc._EMBEDDING_MODEL
    try:
        svc._EMBEDDING_MODEL = _make_mock_model(seed=1)
        result = svc.embed_text(text)
        assert result.shape == (384,), f"Expected shape (384,), got {result.shape}"
        norm = float(np.linalg.norm(result))
        assert abs(norm - 1.0) < 0.01, f"L2 norm was {norm}, expected ≈ 1.0"
    finally:
        svc._EMBEDDING_MODEL = orig_model


# ===========================================================================
# Property 13: build_index produces index.ntotal == len(chunks)
# **Validates: Requirements 7.3, 7.4, 7.5**
# ===========================================================================

class TestBuildIndex:
    """Unit tests for build_index()."""

    def test_build_index_ntotal_equals_chunk_count(self):
        """After build_index, index.ntotal == len(chunks)."""
        import faiss

        with _EmbeddingPatch(n_texts=4) as (mock_model, tmpdir):
            from services.embedding_service import build_index

            chunks = _make_chunks(4)
            index = build_index("doc_abc", chunks)
            assert index is not None
            assert index.ntotal == 4

    def test_build_index_creates_index_file(self):
        """build_index persists a .index file to faiss_index/."""
        import faiss

        with _EmbeddingPatch(n_texts=2) as (mock_model, tmpdir):
            from services.embedding_service import build_index

            chunks = _make_chunks(2)
            build_index("doc_xyz", chunks)
            assert os.path.exists(os.path.join(tmpdir, "doc_xyz.index"))

    def test_build_index_creates_meta_json(self):
        """build_index persists a .meta.json file to faiss_index/."""
        import faiss

        with _EmbeddingPatch(n_texts=3) as (mock_model, tmpdir):
            from services.embedding_service import build_index

            chunks = _make_chunks(3)
            build_index("doc_meta", chunks)
            meta_path = os.path.join(tmpdir, "doc_meta.meta.json")
            assert os.path.exists(meta_path)
            with open(meta_path) as fh:
                meta = json.load(fh)
            assert len(meta) == 3

    def test_build_index_meta_json_has_required_keys(self):
        """Each entry in the metadata JSON has 'text', 'start', 'index' keys."""
        import faiss

        with _EmbeddingPatch(n_texts=2) as (mock_model, tmpdir):
            from services.embedding_service import build_index

            chunks = _make_chunks(2)
            build_index("doc_keys", chunks)
            with open(os.path.join(tmpdir, "doc_keys.meta.json")) as fh:
                meta = json.load(fh)
            for entry in meta:
                assert "text" in entry
                assert "start" in entry
                assert "index" in entry

    def test_build_index_returns_none_on_error(self):
        """build_index returns None when an error occurs."""
        import services.embedding_service as svc

        orig_model = svc._EMBEDDING_MODEL
        orig_dir = svc._FAISS_DIR
        try:
            bad_model = MagicMock()
            bad_model.encode.side_effect = RuntimeError("encode failed")
            svc._EMBEDDING_MODEL = bad_model
            svc._FAISS_DIR = "/nonexistent_path_xyz"
            result = svc.build_index("doc_err", _make_chunks(2))
            assert result is None
        finally:
            svc._EMBEDDING_MODEL = orig_model
            svc._FAISS_DIR = orig_dir


@given(n=st.integers(min_value=1, max_value=20))
@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_13_index_ntotal_equals_chunk_count(n):
    """
    **Validates: Requirements 7.3, 7.4, 7.5**

    Property 13: For any doc_id and list of chunks with len(chunks) >= 1,
    after build_index(doc_id, chunks) completes, the persisted FAISS index
    SHALL have ntotal equal to len(chunks).
    """
    import faiss
    import services.embedding_service as svc

    orig_model = svc._EMBEDDING_MODEL
    orig_dir = svc._FAISS_DIR
    tmpdir = tempfile.mkdtemp()
    try:
        svc._EMBEDDING_MODEL = _make_mock_model(n_texts=n, seed=n)
        svc._FAISS_DIR = tmpdir
        chunks = _make_chunks(n)
        index = svc.build_index(f"doc_{n}", chunks)
        assert index is not None, "build_index returned None"
        assert index.ntotal == n, f"Expected ntotal={n}, got {index.ntotal}"
        # Also verify the persisted index
        loaded = faiss.read_index(os.path.join(tmpdir, f"doc_{n}.index"))
        assert loaded.ntotal == n
    finally:
        svc._EMBEDDING_MODEL = orig_model
        svc._FAISS_DIR = orig_dir


# ===========================================================================
# Property 14: similarity_search results sorted descending, len <= k,
#              scores in [0.0, 1.0]
# **Validates: Requirements 8.2, 8.3, 8.4, 8.5**
# ===========================================================================

def _build_test_index(tmpdir: str, doc_id: str, n_chunks: int, seed: int = 42):
    """Helper: build a real FAISS index in tmpdir using mock embeddings."""
    import faiss

    import services.embedding_service as svc

    chunks = _make_chunks(n_chunks)
    embeddings = _make_embedding_matrix(n_chunks, seed=seed)

    dim = 384
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    faiss.write_index(index, os.path.join(tmpdir, f"{doc_id}.index"))

    metadata = [
        {"text": c.text, "start": c.start_char, "index": c.index}
        for c in chunks
    ]
    with open(os.path.join(tmpdir, f"{doc_id}.meta.json"), "w") as fh:
        json.dump(metadata, fh)

    return index


class TestSimilaritySearch:
    """Unit tests for similarity_search()."""

    def test_search_returns_at_most_k_results(self):
        """similarity_search returns at most k results."""
        import services.embedding_service as svc

        orig_model = svc._EMBEDDING_MODEL
        orig_dir = svc._FAISS_DIR
        tmpdir = tempfile.mkdtemp()
        try:
            svc._EMBEDDING_MODEL = _make_mock_model(seed=7)
            svc._FAISS_DIR = tmpdir
            _build_test_index(tmpdir, "doc1", n_chunks=10)
            results = svc.similarity_search("query text", "doc1", k=4)
            assert len(results) <= 4
        finally:
            svc._EMBEDDING_MODEL = orig_model
            svc._FAISS_DIR = orig_dir

    def test_search_results_sorted_descending(self):
        """similarity_search results are sorted by descending score."""
        import services.embedding_service as svc

        orig_model = svc._EMBEDDING_MODEL
        orig_dir = svc._FAISS_DIR
        tmpdir = tempfile.mkdtemp()
        try:
            svc._EMBEDDING_MODEL = _make_mock_model(seed=3)
            svc._FAISS_DIR = tmpdir
            _build_test_index(tmpdir, "doc2", n_chunks=8)
            results = svc.similarity_search("legal clause", "doc2", k=5)
            scores = [r.score for r in results]
            assert scores == sorted(scores, reverse=True), f"Scores not sorted: {scores}"
        finally:
            svc._EMBEDDING_MODEL = orig_model
            svc._FAISS_DIR = orig_dir

    def test_search_scores_in_range(self):
        """Every score returned by similarity_search is in [0.0, 1.0]."""
        import services.embedding_service as svc

        orig_model = svc._EMBEDDING_MODEL
        orig_dir = svc._FAISS_DIR
        tmpdir = tempfile.mkdtemp()
        try:
            svc._EMBEDDING_MODEL = _make_mock_model(seed=5)
            svc._FAISS_DIR = tmpdir
            _build_test_index(tmpdir, "doc3", n_chunks=6)
            results = svc.similarity_search("indemnity clause", "doc3", k=6)
            for r in results:
                assert 0.0 <= r.score <= 1.0, f"Score out of range: {r.score}"
        finally:
            svc._EMBEDDING_MODEL = orig_model
            svc._FAISS_DIR = orig_dir

    def test_search_returns_chunk_results(self):
        """similarity_search returns ChunkResult instances."""
        import services.embedding_service as svc

        orig_model = svc._EMBEDDING_MODEL
        orig_dir = svc._FAISS_DIR
        tmpdir = tempfile.mkdtemp()
        try:
            svc._EMBEDDING_MODEL = _make_mock_model(seed=9)
            svc._FAISS_DIR = tmpdir
            _build_test_index(tmpdir, "doc4", n_chunks=5)
            results = svc.similarity_search("query", "doc4", k=3)
            for r in results:
                assert isinstance(r, ChunkResult)
                assert r.doc_id == "doc4"
                assert len(r.chunk_text) > 0
                assert r.chunk_index >= 0
        finally:
            svc._EMBEDDING_MODEL = orig_model
            svc._FAISS_DIR = orig_dir

    def test_search_missing_index_returns_empty(self):
        """similarity_search returns [] when the index file does not exist."""
        import services.embedding_service as svc

        orig_dir = svc._FAISS_DIR
        tmpdir = tempfile.mkdtemp()
        try:
            svc._FAISS_DIR = tmpdir
            results = svc.similarity_search("query", "nonexistent_doc", k=4)
            assert results == []
        finally:
            svc._FAISS_DIR = orig_dir


@given(
    k=st.integers(min_value=1, max_value=10),
    n_chunks=st.integers(min_value=1, max_value=15),
)
@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_14_search_sorted_bounded_scored(k, n_chunks):
    """
    **Validates: Requirements 8.2, 8.3, 8.4, 8.5**

    Property 14: similarity_search(query, doc_id, k) SHALL return at most k
    results, results SHALL be sorted by descending score, every score SHALL be
    in [0.0, 1.0], and every result SHALL be a ChunkResult.
    """
    import services.embedding_service as svc

    orig_model = svc._EMBEDDING_MODEL
    orig_dir = svc._FAISS_DIR
    tmpdir = tempfile.mkdtemp()
    try:
        svc._EMBEDDING_MODEL = _make_mock_model(seed=k + n_chunks)
        svc._FAISS_DIR = tmpdir
        _build_test_index(tmpdir, f"doc_{k}_{n_chunks}", n_chunks=n_chunks, seed=k)
        results = svc.similarity_search("test query", f"doc_{k}_{n_chunks}", k=k)

        # len <= k
        assert len(results) <= k, f"Expected <= {k} results, got {len(results)}"

        # sorted descending
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True), f"Scores not sorted: {scores}"

        # scores in [0.0, 1.0]
        for r in results:
            assert 0.0 <= r.score <= 1.0, f"Score out of range: {r.score}"
            assert isinstance(r, ChunkResult)
    finally:
        svc._EMBEDDING_MODEL = orig_model
        svc._FAISS_DIR = orig_dir


# ===========================================================================
# Property 15: cross_document_search skips missing indices gracefully
# **Validates: Requirements 8.6, 8.8**
# ===========================================================================

class TestCrossDocumentSearch:
    """Unit tests for cross_document_search()."""

    def test_cross_search_skips_missing_indices(self):
        """cross_document_search skips doc_ids whose index files are absent."""
        import services.embedding_service as svc

        orig_model = svc._EMBEDDING_MODEL
        orig_dir = svc._FAISS_DIR
        tmpdir = tempfile.mkdtemp()
        try:
            svc._EMBEDDING_MODEL = _make_mock_model(seed=11)
            svc._FAISS_DIR = tmpdir
            # Only build index for "doc_present"; "doc_missing" has no file
            _build_test_index(tmpdir, "doc_present", n_chunks=5)
            results = svc.cross_document_search(
                "query", ["doc_present", "doc_missing"], k=10
            )
            # All results must come from doc_present
            for r in results:
                assert r.doc_id == "doc_present"
        finally:
            svc._EMBEDDING_MODEL = orig_model
            svc._FAISS_DIR = orig_dir

    def test_cross_search_all_missing_returns_empty(self):
        """cross_document_search returns [] when all indices are missing."""
        import services.embedding_service as svc

        orig_dir = svc._FAISS_DIR
        tmpdir = tempfile.mkdtemp()
        try:
            svc._FAISS_DIR = tmpdir
            results = svc.cross_document_search("query", ["a", "b", "c"], k=5)
            assert results == []
        finally:
            svc._FAISS_DIR = orig_dir

    def test_cross_search_results_sorted_descending(self):
        """cross_document_search returns results sorted by descending score."""
        import services.embedding_service as svc

        orig_model = svc._EMBEDDING_MODEL
        orig_dir = svc._FAISS_DIR
        tmpdir = tempfile.mkdtemp()
        try:
            svc._EMBEDDING_MODEL = _make_mock_model(seed=13)
            svc._FAISS_DIR = tmpdir
            _build_test_index(tmpdir, "docA", n_chunks=5, seed=1)
            _build_test_index(tmpdir, "docB", n_chunks=5, seed=2)
            results = svc.cross_document_search("query", ["docA", "docB"], k=8)
            scores = [r.score for r in results]
            assert scores == sorted(scores, reverse=True), f"Scores not sorted: {scores}"
        finally:
            svc._EMBEDDING_MODEL = orig_model
            svc._FAISS_DIR = orig_dir

    def test_cross_search_returns_at_most_k(self):
        """cross_document_search returns at most k results."""
        import services.embedding_service as svc

        orig_model = svc._EMBEDDING_MODEL
        orig_dir = svc._FAISS_DIR
        tmpdir = tempfile.mkdtemp()
        try:
            svc._EMBEDDING_MODEL = _make_mock_model(seed=17)
            svc._FAISS_DIR = tmpdir
            _build_test_index(tmpdir, "d1", n_chunks=10, seed=1)
            _build_test_index(tmpdir, "d2", n_chunks=10, seed=2)
            results = svc.cross_document_search("query", ["d1", "d2"], k=5)
            assert len(results) <= 5
        finally:
            svc._EMBEDDING_MODEL = orig_model
            svc._FAISS_DIR = orig_dir

    def test_cross_search_does_not_raise_on_mixed_availability(self):
        """cross_document_search does not raise when some indices are missing."""
        import services.embedding_service as svc

        orig_model = svc._EMBEDDING_MODEL
        orig_dir = svc._FAISS_DIR
        tmpdir = tempfile.mkdtemp()
        try:
            svc._EMBEDDING_MODEL = _make_mock_model(seed=19)
            svc._FAISS_DIR = tmpdir
            _build_test_index(tmpdir, "real_doc", n_chunks=3)
            # Should not raise
            results = svc.cross_document_search(
                "query",
                ["missing1", "real_doc", "missing2", "missing3"],
                k=10,
            )
            assert isinstance(results, list)
        finally:
            svc._EMBEDDING_MODEL = orig_model
            svc._FAISS_DIR = orig_dir


@given(
    present_count=st.integers(min_value=0, max_value=3),
    missing_count=st.integers(min_value=0, max_value=3),
    k=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_15_cross_search_skips_missing(present_count, missing_count, k):
    """
    **Validates: Requirements 8.6, 8.8**

    Property 15: cross_document_search() SHALL return results only from
    available indices, SHALL NOT raise an exception, and the returned results
    SHALL be sorted by descending score.
    """
    import services.embedding_service as svc

    orig_model = svc._EMBEDDING_MODEL
    orig_dir = svc._FAISS_DIR
    tmpdir = tempfile.mkdtemp()
    try:
        svc._EMBEDDING_MODEL = _make_mock_model(seed=present_count + missing_count)
        svc._FAISS_DIR = tmpdir

        present_ids = [f"present_{i}" for i in range(present_count)]
        missing_ids = [f"missing_{i}" for i in range(missing_count)]

        for doc_id in present_ids:
            _build_test_index(tmpdir, doc_id, n_chunks=3, seed=hash(doc_id) % 100)

        all_ids = present_ids + missing_ids
        # Must not raise
        results = svc.cross_document_search("test query", all_ids, k=k)

        assert isinstance(results, list)
        assert len(results) <= k

        # All results come from present indices
        for r in results:
            assert r.doc_id in present_ids, f"Unexpected doc_id: {r.doc_id}"

        # Sorted descending
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True), f"Scores not sorted: {scores}"
    finally:
        svc._EMBEDDING_MODEL = orig_model
        svc._FAISS_DIR = orig_dir


# ===========================================================================
# load_index tests
# ===========================================================================

class TestLoadIndex:
    """Unit tests for load_index()."""

    def test_load_index_returns_none_for_missing_file(self):
        """load_index returns None when the index file does not exist."""
        import services.embedding_service as svc

        orig_dir = svc._FAISS_DIR
        tmpdir = tempfile.mkdtemp()
        try:
            svc._FAISS_DIR = tmpdir
            result = svc.load_index("nonexistent")
            assert result is None
        finally:
            svc._FAISS_DIR = orig_dir

    def test_load_index_returns_index_for_existing_file(self):
        """load_index returns a FAISS index when the file exists."""
        import services.embedding_service as svc

        orig_model = svc._EMBEDDING_MODEL
        orig_dir = svc._FAISS_DIR
        tmpdir = tempfile.mkdtemp()
        try:
            svc._EMBEDDING_MODEL = _make_mock_model(seed=21)
            svc._FAISS_DIR = tmpdir
            _build_test_index(tmpdir, "loadable", n_chunks=4)
            result = svc.load_index("loadable")
            assert result is not None
            assert result.ntotal == 4
        finally:
            svc._EMBEDDING_MODEL = orig_model
            svc._FAISS_DIR = orig_dir
