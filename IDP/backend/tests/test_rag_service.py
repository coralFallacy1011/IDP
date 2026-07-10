"""
Unit tests for ``rag_service``.

Tests cover Property 16 from the design document:

  - Property 16: RAG result fields are always populated
    - ``answer`` is non-empty
    - ``len(source_chunks) <= k``
    - ``model_used`` is non-empty
    - Conversation history is maintained across calls
    - LLM failure returns error message in ``answer``

All tests mock ``llama_cpp.Llama`` and ``embedding_service.similarity_search``
so no real models are needed.

**Validates: Requirements 9.6, 9.7, 9.8, 9.5, 9.10**
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure backend/ is on sys.path so relative imports resolve correctly
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from models.nlp_models import ChunkResult, RAGResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk_results(n: int, doc_id: str = "doc_test") -> list[ChunkResult]:
    """Return *n* dummy ChunkResult objects."""
    return [
        ChunkResult(
            chunk_text=f"This is chunk number {i} with some legal text.",
            doc_id=doc_id,
            chunk_index=i,
            score=1.0 - i * 0.1,
        )
        for i in range(n)
    ]


def _make_llm_mock(answer_text: str = "The contract was signed on 1st January 2024.") -> MagicMock:
    """Return a mock Llama instance that returns *answer_text*."""
    mock = MagicMock()
    mock.return_value = {
        "choices": [{"text": answer_text}]
    }
    return mock


# ---------------------------------------------------------------------------
# Context manager: patch rag_service singletons and dependencies
# ---------------------------------------------------------------------------

class _RAGPatch:
    """Context manager that patches the LLM singleton and embedding service
    dependencies in rag_service so no real models are loaded."""

    def __init__(
        self,
        llm_mock: MagicMock | None = None,
        chunks: list[ChunkResult] | None = None,
        llm_raises: Exception | None = None,
    ):
        self._llm_mock = llm_mock or _make_llm_mock()
        self._chunks = chunks if chunks is not None else _make_chunk_results(3)
        self._llm_raises = llm_raises

    def __enter__(self):
        import services.rag_service as svc

        # Reset module-level singletons and history for test isolation
        self._orig_llm = svc._LLM
        self._orig_histories = dict(svc._CONVERSATION_HISTORIES)
        svc._LLM = None
        svc._CONVERSATION_HISTORIES.clear()

        # Patch get_llm to return our mock (or raise)
        if self._llm_raises is not None:
            exc = self._llm_raises

            def _raising_get_llm():
                raise exc

            self._get_llm_patcher = patch.object(svc, "get_llm", side_effect=_raising_get_llm)
        else:
            self._get_llm_patcher = patch.object(svc, "get_llm", return_value=self._llm_mock)

        self._get_llm_patcher.start()

        # Patch get_or_create_index to be a no-op
        self._index_patcher = patch(
            "services.embedding_service.get_or_create_index",
            return_value=MagicMock(),
        )
        self._index_patcher.start()

        # Patch similarity_search to return our chunks
        chunks = self._chunks

        self._search_patcher = patch(
            "services.embedding_service.similarity_search",
            return_value=chunks,
        )
        self._search_patcher.start()

        return svc

    def __exit__(self, *_):
        import services.rag_service as svc

        self._get_llm_patcher.stop()
        self._index_patcher.stop()
        self._search_patcher.stop()

        svc._LLM = self._orig_llm
        svc._CONVERSATION_HISTORIES.clear()
        svc._CONVERSATION_HISTORIES.update(self._orig_histories)


# ===========================================================================
# Property 16 — answer is non-empty
# **Validates: Requirements 9.6**
# ===========================================================================

class TestAnswerNonEmpty:
    """answer_question always returns a non-empty answer string."""

    def test_answer_is_non_empty_string(self):
        """answer_question returns a non-empty answer."""
        with _RAGPatch() as svc:
            result = svc.answer_question("What is the contract date?", "doc1")
            assert isinstance(result.answer, str)
            assert len(result.answer) > 0

    def test_answer_contains_llm_output(self):
        """answer_question returns the LLM-generated text in answer."""
        expected = "The contract was executed on 15th March 2023."
        with _RAGPatch(llm_mock=_make_llm_mock(expected)) as svc:
            result = svc.answer_question("When was the contract signed?", "doc2")
            assert result.answer == expected

    def test_answer_strips_whitespace(self):
        """answer_question strips leading/trailing whitespace from LLM output."""
        with _RAGPatch(llm_mock=_make_llm_mock("  Answer with spaces.  ")) as svc:
            result = svc.answer_question("question", "doc3")
            assert result.answer == "Answer with spaces."

    def test_answer_fallback_when_llm_returns_empty(self):
        """answer_question returns a fallback message when LLM returns empty text."""
        with _RAGPatch(llm_mock=_make_llm_mock("")) as svc:
            result = svc.answer_question("question", "doc4")
            assert len(result.answer) > 0


# ===========================================================================
# Property 16 — len(source_chunks) <= k
# **Validates: Requirements 9.7**
# ===========================================================================

class TestSourceChunksBounded:
    """source_chunks length is always <= k."""

    def test_source_chunks_len_lte_k_default(self):
        """source_chunks has at most k=4 items by default."""
        chunks = _make_chunk_results(4)
        with _RAGPatch(chunks=chunks) as svc:
            result = svc.answer_question("question", "doc5")
            assert len(result.source_chunks) <= 4

    def test_source_chunks_len_lte_k_custom(self):
        """source_chunks has at most k items for custom k."""
        for k in [1, 2, 3, 6, 10]:
            n = min(k, 5)  # similarity_search returns at most n chunks
            chunks = _make_chunk_results(n)
            with _RAGPatch(chunks=chunks) as svc:
                result = svc.answer_question("question", f"doc_k{k}", k=k)
                assert len(result.source_chunks) <= k, (
                    f"Expected <= {k} chunks, got {len(result.source_chunks)}"
                )

    def test_source_chunks_are_chunk_result_instances(self):
        """Every item in source_chunks is a ChunkResult."""
        chunks = _make_chunk_results(3)
        with _RAGPatch(chunks=chunks) as svc:
            result = svc.answer_question("question", "doc6")
            for chunk in result.source_chunks:
                assert isinstance(chunk, ChunkResult)

    def test_source_chunks_empty_when_no_index(self):
        """source_chunks is empty when similarity_search returns no results."""
        with _RAGPatch(chunks=[]) as svc:
            result = svc.answer_question("question", "doc7")
            assert result.source_chunks == []


# ===========================================================================
# Property 16 — model_used is non-empty
# **Validates: Requirements 9.8**
# ===========================================================================

class TestModelUsedNonEmpty:
    """model_used is always a non-empty string."""

    def test_model_used_is_non_empty(self):
        """model_used is a non-empty string on success."""
        with _RAGPatch() as svc:
            result = svc.answer_question("question", "doc8")
            assert isinstance(result.model_used, str)
            assert len(result.model_used) > 0

    def test_model_used_is_tinyllama(self):
        """model_used is 'TinyLlama-1.1B-Chat' when LLM loads successfully."""
        with _RAGPatch() as svc:
            result = svc.answer_question("question", "doc9")
            assert result.model_used == "TinyLlama-1.1B-Chat"

    def test_model_used_is_unknown_on_failure(self):
        """model_used is 'unknown' when LLM raises an exception."""
        with _RAGPatch(llm_raises=RuntimeError("model crashed")) as svc:
            result = svc.answer_question("question", "doc10")
            assert result.model_used == "unknown"


# ===========================================================================
# Property 16 — conversation history is maintained across calls
# **Validates: Requirements 9.5**
# ===========================================================================

class TestConversationHistory:
    """Conversation history is persisted per doc_id across calls."""

    def test_history_is_populated_after_first_call(self):
        """After one call, _CONVERSATION_HISTORIES[doc_id] has 2 entries."""
        with _RAGPatch() as svc:
            svc.answer_question("What is the penalty clause?", "doc_hist1")
            history = svc._CONVERSATION_HISTORIES.get("doc_hist1", [])
            assert len(history) == 2
            assert history[0]["role"] == "user"
            assert history[0]["content"] == "What is the penalty clause?"
            assert history[1]["role"] == "assistant"

    def test_history_grows_across_multiple_calls(self):
        """History accumulates entries across multiple calls for the same doc."""
        with _RAGPatch() as svc:
            svc.answer_question("First question?", "doc_hist2")
            svc.answer_question("Second question?", "doc_hist2")
            history = svc._CONVERSATION_HISTORIES.get("doc_hist2", [])
            # 2 entries per call (user + assistant)
            assert len(history) == 4

    def test_history_is_separate_per_doc_id(self):
        """History for different doc_ids is stored independently."""
        with _RAGPatch() as svc:
            svc.answer_question("Question for doc A?", "doc_histA")
            svc.answer_question("Question for doc B?", "doc_histB")
            hist_a = svc._CONVERSATION_HISTORIES.get("doc_histA", [])
            hist_b = svc._CONVERSATION_HISTORIES.get("doc_histB", [])
            assert len(hist_a) == 2
            assert len(hist_b) == 2
            assert hist_a[0]["content"] == "Question for doc A?"
            assert hist_b[0]["content"] == "Question for doc B?"

    def test_external_chat_history_is_merged(self):
        """Externally supplied chat_history is merged into the in-memory store."""
        prior_history = [
            {"role": "user", "content": "Prior question?"},
            {"role": "assistant", "content": "Prior answer."},
        ]
        with _RAGPatch() as svc:
            svc.answer_question(
                "Follow-up question?",
                "doc_hist3",
                chat_history=prior_history,
            )
            history = svc._CONVERSATION_HISTORIES.get("doc_hist3", [])
            # prior (2) + new exchange (2) = 4
            assert len(history) == 4
            assert history[0]["content"] == "Prior question?"
            assert history[2]["content"] == "Follow-up question?"

    def test_history_not_populated_on_llm_failure(self):
        """On LLM failure, the failed exchange is NOT added to history."""
        with _RAGPatch(llm_raises=RuntimeError("LLM down")) as svc:
            svc.answer_question("question", "doc_hist_fail")
            # The exception is caught before history is updated
            history = svc._CONVERSATION_HISTORIES.get("doc_hist_fail", [])
            assert len(history) == 0


# ===========================================================================
# Property 16 — LLM failure returns error message in answer
# **Validates: Requirements 9.10**
# ===========================================================================

class TestLLMFailureGracefulDegradation:
    """LLM failure returns a RAGResult with error message, not an exception."""

    def test_llm_failure_returns_rag_result(self):
        """answer_question returns a RAGResult even when LLM raises."""
        with _RAGPatch(llm_raises=RuntimeError("GPU out of memory")) as svc:
            result = svc.answer_question("question", "doc_fail1")
            assert isinstance(result, RAGResult)

    def test_llm_failure_answer_starts_with_error(self):
        """answer on LLM failure starts with 'Error:'."""
        with _RAGPatch(llm_raises=RuntimeError("GPU out of memory")) as svc:
            result = svc.answer_question("question", "doc_fail2")
            assert result.answer.startswith("Error:")

    def test_llm_failure_answer_contains_reason(self):
        """answer on LLM failure contains the exception message."""
        with _RAGPatch(llm_raises=RuntimeError("GPU out of memory")) as svc:
            result = svc.answer_question("question", "doc_fail3")
            assert "GPU out of memory" in result.answer

    def test_llm_failure_source_chunks_empty(self):
        """source_chunks is empty when LLM raises."""
        with _RAGPatch(llm_raises=RuntimeError("model not found")) as svc:
            result = svc.answer_question("question", "doc_fail4")
            assert result.source_chunks == []

    def test_llm_failure_model_used_is_unknown(self):
        """model_used is 'unknown' when LLM raises."""
        with _RAGPatch(llm_raises=RuntimeError("model not found")) as svc:
            result = svc.answer_question("question", "doc_fail5")
            assert result.model_used == "unknown"

    def test_file_not_found_returns_error_result(self):
        """FileNotFoundError from get_llm is caught and returned as error."""
        with _RAGPatch(llm_raises=FileNotFoundError("GGUF file missing")) as svc:
            result = svc.answer_question("question", "doc_fail6")
            assert isinstance(result, RAGResult)
            assert result.answer.startswith("Error:")
            assert result.model_used == "unknown"

    def test_does_not_raise_on_any_exception(self):
        """answer_question never propagates exceptions to the caller."""
        for exc in [
            RuntimeError("crash"),
            ValueError("bad input"),
            FileNotFoundError("missing file"),
            MemoryError("OOM"),
        ]:
            with _RAGPatch(llm_raises=exc) as svc:
                # Must not raise
                result = svc.answer_question("question", "doc_no_raise")
                assert isinstance(result, RAGResult)


# ===========================================================================
# Additional integration-style unit tests
# ===========================================================================

class TestRAGResultStructure:
    """RAGResult has the correct structure and types."""

    def test_result_is_rag_result_instance(self):
        """answer_question returns a RAGResult dataclass instance."""
        with _RAGPatch() as svc:
            result = svc.answer_question("question", "doc_struct1")
            assert isinstance(result, RAGResult)

    def test_result_has_all_fields(self):
        """RAGResult has answer, source_chunks, and model_used fields."""
        with _RAGPatch() as svc:
            result = svc.answer_question("question", "doc_struct2")
            assert hasattr(result, "answer")
            assert hasattr(result, "source_chunks")
            assert hasattr(result, "model_used")

    def test_source_chunks_is_list(self):
        """source_chunks is always a list."""
        with _RAGPatch() as svc:
            result = svc.answer_question("question", "doc_struct3")
            assert isinstance(result.source_chunks, list)

    def test_to_dict_serialisable(self):
        """RAGResult.to_dict() returns a JSON-serialisable dict."""
        import json

        with _RAGPatch() as svc:
            result = svc.answer_question("question", "doc_struct4")
            d = result.to_dict()
            assert isinstance(d, dict)
            # Should not raise
            json.dumps(d)

    def test_build_rag_chain_returns_callable(self):
        """build_rag_chain returns a callable that produces RAGResult."""
        with _RAGPatch() as svc:
            chain = svc.build_rag_chain("doc_chain1")
            assert callable(chain)
            result = chain("What are the payment terms?")
            assert isinstance(result, RAGResult)
            assert len(result.answer) > 0
