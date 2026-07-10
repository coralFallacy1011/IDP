"""
Property-based and unit tests for ``nlp_service.summarize``.

Tests cover:
  - ``compression_ratio < 1.0`` for valid inputs (texts ≥ 30 words)
  - ``word_count == len(summary.split())``
  - Short-text guard: texts < 30 words return input as summary
  - Exception returns truncated input as summary

All tests mock the summarizer pipeline — no real model downloads.

**Validates: Requirements 6 / Properties 6, 7**
"""

from __future__ import annotations

import sys
import os
import types
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Ensure backend/ is on sys.path
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_pipelines() -> None:
    import services.nlp_service as svc
    svc._PIPELINES.clear()


def _make_fake_transformers(pipeline_factory) -> types.ModuleType:
    fake = types.ModuleType("transformers")
    fake.pipeline = pipeline_factory
    return fake


def _make_summarizer_pipeline(summary_text: str):
    """Return a callable that always returns the given summary text."""
    mock_pipe = MagicMock(return_value=[{"summary_text": summary_text}])
    return mock_pipe


def _words(n: int) -> str:
    """Return a string of n space-separated words."""
    return " ".join([f"word{i}" for i in range(n)])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_pipeline_cache():
    _reset_pipelines()
    yield
    _reset_pipelines()


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Text with at least 30 words (passes short-text guard)
long_text_st = st.integers(min_value=30, max_value=100).map(_words)

# Text with fewer than 30 words (triggers short-text guard)
short_text_st = st.integers(min_value=0, max_value=29).map(_words)

# A shorter summary (fewer words than the input)
def _make_shorter_summary(input_text: str) -> str:
    words = input_text.split()
    # Return first half of words as summary (always shorter)
    half = max(1, len(words) // 2)
    return " ".join(words[:half])


# ---------------------------------------------------------------------------
# 1. Property: word_count == len(summary.split())
# ---------------------------------------------------------------------------

class TestWordCountConsistency:
    """Property 6: word_count always equals len(summary.split())."""

    @given(long_text_st)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_word_count_equals_summary_split_property(self, text):
        """**Validates: Requirements 6 / Property 6**"""
        from services.nlp_service import summarize

        summary_text = _make_shorter_summary(text)
        mock_pipe = _make_summarizer_pipeline(summary_text)
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = summarize(text)

        assert result.word_count == len(result.summary.split()), (
            f"word_count {result.word_count} != len(summary.split()) "
            f"{len(result.summary.split())}"
        )

    def test_word_count_equals_summary_split_example(self):
        from services.nlp_service import summarize

        text = _words(50)
        summary_text = _words(10)
        mock_pipe = _make_summarizer_pipeline(summary_text)
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = summarize(text)

        assert result.word_count == len(result.summary.split())
        assert result.word_count == 10

    def test_word_count_for_short_text_guard(self):
        """Short text guard: word_count should equal len(text.split())."""
        from services.nlp_service import summarize

        text = _words(15)  # < 30 words
        result = summarize(text)
        assert result.word_count == len(result.summary.split())
        assert result.word_count == len(text.split())


# ---------------------------------------------------------------------------
# 2. Property: compression_ratio < 1.0 for valid inputs
# ---------------------------------------------------------------------------

class TestCompressionRatio:
    """Property 7: compression_ratio < 1.0 for texts with ≥ 30 words."""

    @given(long_text_st)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_compression_ratio_less_than_one_property(self, text):
        """**Validates: Requirements 6 / Property 7**"""
        from services.nlp_service import summarize

        # Summary is always shorter than input
        summary_text = _make_shorter_summary(text)
        assume(len(summary_text.split()) < len(text.split()))

        mock_pipe = _make_summarizer_pipeline(summary_text)
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = summarize(text)

        assert result.compression_ratio < 1.0, (
            f"compression_ratio {result.compression_ratio} should be < 1.0"
        )

    def test_compression_ratio_example(self):
        from services.nlp_service import summarize

        text = _words(60)  # 60 words
        summary_text = _words(10)  # 10 words → ratio = 10/60 ≈ 0.167
        mock_pipe = _make_summarizer_pipeline(summary_text)
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = summarize(text)

        assert result.compression_ratio < 1.0
        assert abs(result.compression_ratio - 10 / 60) < 0.01

    def test_compression_ratio_formula(self):
        """compression_ratio = word_count / max(len(text.split()), 1)."""
        from services.nlp_service import summarize

        text = _words(40)
        summary_text = _words(8)
        mock_pipe = _make_summarizer_pipeline(summary_text)
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = summarize(text)

        expected_ratio = 8 / 40
        assert abs(result.compression_ratio - expected_ratio) < 0.001


# ---------------------------------------------------------------------------
# 3. Short-text guard: texts < 30 words return input as summary
# ---------------------------------------------------------------------------

class TestShortTextGuard:
    """Property: texts with < 30 words return the input text as summary."""

    @given(short_text_st)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_short_text_returns_input_property(self, text):
        """**Validates: Requirements 6 / Property 7**"""
        from services.nlp_service import summarize

        result = summarize(text)
        assert result.summary == text, (
            f"Short text guard should return input as summary"
        )

    def test_empty_text_returns_empty_summary(self):
        from services.nlp_service import summarize

        result = summarize("")
        assert result.summary == ""
        assert result.word_count == 0

    def test_29_words_returns_input(self):
        from services.nlp_service import summarize

        text = _words(29)
        result = summarize(text)
        assert result.summary == text

    def test_exactly_30_words_does_not_trigger_guard(self):
        """Text with exactly 30 words should attempt summarization."""
        from services.nlp_service import summarize

        text = _words(30)
        summary_text = _words(5)
        mock_pipe = _make_summarizer_pipeline(summary_text)
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = summarize(text)

        # Should have used the pipeline, not returned input
        assert result.summary == summary_text

    def test_short_text_compression_ratio(self):
        """Short text guard: compression_ratio should be 1.0 (summary == input)."""
        from services.nlp_service import summarize

        text = _words(10)
        result = summarize(text)
        assert result.compression_ratio == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 4. Exception handling
# ---------------------------------------------------------------------------

class TestExceptionHandling:
    """Exception in pipeline must return truncated input as summary."""

    def test_pipeline_exception_returns_truncated_input(self):
        from services.nlp_service import summarize

        text = _words(50)
        mock_pipe = MagicMock(side_effect=RuntimeError("BART failed"))
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = summarize(text)

        # Should return truncated input (first max_length=200 words)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0
        # word_count should still be consistent
        assert result.word_count == len(result.summary.split())

    def test_pipeline_load_exception_returns_truncated_input(self):
        from services.nlp_service import summarize

        text = _words(50)
        fake_transformers = _make_fake_transformers(
            MagicMock(side_effect=OSError("weights not found"))
        )
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = summarize(text)

        assert isinstance(result.summary, str)
        assert result.word_count == len(result.summary.split())

    def test_exception_result_word_count_consistent(self):
        """Even on exception, word_count must equal len(summary.split())."""
        from services.nlp_service import summarize

        text = _words(100)
        mock_pipe = MagicMock(side_effect=ValueError("bad input"))
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = summarize(text)

        assert result.word_count == len(result.summary.split())


# ---------------------------------------------------------------------------
# 5. Map-reduce path for long texts
# ---------------------------------------------------------------------------

class TestMapReducePath:
    """Texts > 600 words should use the map-reduce summarization path."""

    def test_long_text_uses_pipeline(self):
        from services.nlp_service import summarize

        text = _words(700)  # > 600 words
        summary_text = _words(20)

        call_count = {"n": 0}
        def _pipe(t, max_length=None, min_length=None, truncation=None):
            call_count["n"] += 1
            return [{"summary_text": summary_text}]

        mock_pipe = MagicMock(side_effect=_pipe)
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = summarize(text)

        # Pipeline should be called multiple times (once per chunk + once for final)
        assert call_count["n"] > 1
        assert result.word_count == len(result.summary.split())

    def test_short_text_uses_pipeline_once(self):
        from services.nlp_service import summarize

        text = _words(100)  # ≤ 600 words
        summary_text = _words(15)

        call_count = {"n": 0}
        def _pipe(t, max_length=None, min_length=None, truncation=None):
            call_count["n"] += 1
            return [{"summary_text": summary_text}]

        mock_pipe = MagicMock(side_effect=_pipe)
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = summarize(text)

        # Pipeline should be called exactly once for direct path
        assert call_count["n"] == 1
