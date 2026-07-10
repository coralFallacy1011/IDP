"""
Property-based and unit tests for ``nlp_service.detect_clauses``.

Tests cover:
  - ``clauses_found`` labels are all in ``LEGAL_CLAUSE_LABELS``
  - ``clause_spans`` entries have all three required keys (clause, text_snippet, start_char)
  - ``text_snippet`` ≤ 200 characters
  - Exception returns ``ClauseDetectionResult([], [])``

All tests mock the NLI pipeline — no real model downloads.

**Validates: Requirements 5 / Property 5**
"""

from __future__ import annotations

import sys
import os
import types
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, HealthCheck
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


def _make_nli_pipeline_returning_score(score: float):
    """Return a callable that always returns the given score for the first label."""
    def _pipe(text, candidate_labels, **kwargs):
        labels = candidate_labels if isinstance(candidate_labels, list) else [candidate_labels]
        return {
            "labels": labels,
            "scores": [score] * len(labels),
        }
    return MagicMock(side_effect=_pipe)


def _make_nli_pipeline_no_match():
    """Return a callable that always returns score 0.0 (no clause detected)."""
    return _make_nli_pipeline_returning_score(0.0)


def _make_nli_pipeline_all_match():
    """Return a callable that always returns score 0.9 (all clauses detected)."""
    return _make_nli_pipeline_returning_score(0.9)


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

# Text with multiple sentences (to create sliding windows)
sentence_text_st = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
        min_size=5,
        max_size=50,
    ),
    min_size=1,
    max_size=10,
).map(lambda sents: ". ".join(sents) + ".")


# ---------------------------------------------------------------------------
# 1. Property: clauses_found labels are all in LEGAL_CLAUSE_LABELS
# ---------------------------------------------------------------------------

class TestClausesFoundInLegalClauseLabels:
    """Property 5: clauses_found labels are all in LEGAL_CLAUSE_LABELS."""

    @given(sentence_text_st)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_clauses_found_in_legal_clause_labels_property(self, text):
        """**Validates: Requirements 5 / Property 5**"""
        from services.nlp_service import detect_clauses, LEGAL_CLAUSE_LABELS

        mock_pipe = _make_nli_pipeline_all_match()
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = detect_clauses(text)

        for label in result.clauses_found:
            assert label in LEGAL_CLAUSE_LABELS, (
                f"clauses_found contains unknown label: '{label}'"
            )

    def test_clauses_found_in_legal_clause_labels_example(self):
        from services.nlp_service import detect_clauses, LEGAL_CLAUSE_LABELS

        text = (
            "This agreement shall be terminated upon 30 days notice. "
            "The parties agree to arbitration for dispute resolution. "
            "This contract is governed by the laws of India."
        )
        mock_pipe = _make_nli_pipeline_all_match()
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = detect_clauses(text)

        for label in result.clauses_found:
            assert label in LEGAL_CLAUSE_LABELS

    def test_no_clauses_when_score_below_threshold(self):
        from services.nlp_service import detect_clauses

        text = "This is a simple legal document. It has two sentences."
        mock_pipe = _make_nli_pipeline_no_match()
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = detect_clauses(text)

        assert result.clauses_found == []
        assert result.clause_spans == []

    def test_clauses_found_matches_clause_spans(self):
        """clauses_found and clause_spans should be consistent."""
        from services.nlp_service import detect_clauses

        text = (
            "This agreement shall be terminated upon 30 days notice. "
            "The parties agree to arbitration for dispute resolution. "
            "This contract is governed by the laws of India."
        )
        mock_pipe = _make_nli_pipeline_all_match()
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = detect_clauses(text)

        # Every clause in clause_spans should be in clauses_found
        span_clauses = {span["clause"] for span in result.clause_spans}
        assert span_clauses == set(result.clauses_found)


# ---------------------------------------------------------------------------
# 2. Property: clause_spans entries have all three required keys
# ---------------------------------------------------------------------------

class TestClauseSpansKeys:
    """Property 5: clause_spans entries have all three required keys."""

    REQUIRED_KEYS = {"clause", "text_snippet", "start_char"}

    @given(sentence_text_st)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_clause_spans_have_required_keys_property(self, text):
        """**Validates: Requirements 5 / Property 5**"""
        from services.nlp_service import detect_clauses

        mock_pipe = _make_nli_pipeline_all_match()
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = detect_clauses(text)

        for span in result.clause_spans:
            missing = self.REQUIRED_KEYS - set(span.keys())
            assert not missing, (
                f"clause_span missing keys: {missing}. Span: {span}"
            )

    def test_clause_spans_have_required_keys_example(self):
        from services.nlp_service import detect_clauses

        text = (
            "This agreement shall be terminated upon 30 days notice. "
            "The parties agree to arbitration for dispute resolution. "
            "This contract is governed by the laws of India."
        )
        mock_pipe = _make_nli_pipeline_all_match()
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = detect_clauses(text)

        for span in result.clause_spans:
            assert "clause" in span
            assert "text_snippet" in span
            assert "start_char" in span

    def test_start_char_is_non_negative(self):
        from services.nlp_service import detect_clauses

        text = (
            "This agreement shall be terminated upon 30 days notice. "
            "The parties agree to arbitration for dispute resolution."
        )
        mock_pipe = _make_nli_pipeline_all_match()
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = detect_clauses(text)

        for span in result.clause_spans:
            assert span["start_char"] >= 0


# ---------------------------------------------------------------------------
# 3. Property: text_snippet ≤ 200 characters
# ---------------------------------------------------------------------------

class TestTextSnippetLength:
    """Property 5: text_snippet is at most 200 characters."""

    @given(sentence_text_st)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_text_snippet_max_200_chars_property(self, text):
        """**Validates: Requirements 5 / Property 5**"""
        from services.nlp_service import detect_clauses

        mock_pipe = _make_nli_pipeline_all_match()
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = detect_clauses(text)

        for span in result.clause_spans:
            assert len(span["text_snippet"]) <= 200, (
                f"text_snippet exceeds 200 chars: {len(span['text_snippet'])}"
            )

    def test_text_snippet_truncated_for_long_window(self):
        """A very long window text should be truncated to 200 chars in text_snippet."""
        from services.nlp_service import detect_clauses

        # Create a text with very long sentences
        long_sentence = "word " * 100  # 500 chars
        text = f"{long_sentence}. {long_sentence}. {long_sentence}."

        mock_pipe = _make_nli_pipeline_all_match()
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = detect_clauses(text)

        for span in result.clause_spans:
            assert len(span["text_snippet"]) <= 200

    def test_text_snippet_is_string(self):
        from services.nlp_service import detect_clauses

        text = "This agreement shall be terminated. The parties agree to arbitration."
        mock_pipe = _make_nli_pipeline_all_match()
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = detect_clauses(text)

        for span in result.clause_spans:
            assert isinstance(span["text_snippet"], str)


# ---------------------------------------------------------------------------
# 4. Exception handling
# ---------------------------------------------------------------------------

class TestExceptionHandling:
    """Exception in pipeline must return ClauseDetectionResult([], [])."""

    def test_pipeline_exception_returns_empty_result(self):
        from services.nlp_service import detect_clauses

        mock_pipe = MagicMock(side_effect=RuntimeError("NLI failed"))
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = detect_clauses(
                "This agreement shall be terminated upon 30 days notice."
            )

        assert result.clauses_found == []
        assert result.clause_spans == []

    def test_pipeline_load_exception_returns_empty_result(self):
        from services.nlp_service import detect_clauses

        fake_transformers = _make_fake_transformers(
            MagicMock(side_effect=OSError("weights not found"))
        )
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = detect_clauses(
                "This agreement shall be terminated upon 30 days notice."
            )

        assert result.clauses_found == []
        assert result.clause_spans == []


# ---------------------------------------------------------------------------
# 5. LEGAL_CLAUSE_LABELS constant
# ---------------------------------------------------------------------------

class TestLegalClauseLabels:
    """Verify the LEGAL_CLAUSE_LABELS constant has exactly 10 entries."""

    def test_legal_clause_labels_has_10_entries(self):
        from services.nlp_service import LEGAL_CLAUSE_LABELS
        assert len(LEGAL_CLAUSE_LABELS) == 10

    def test_legal_clause_labels_are_strings(self):
        from services.nlp_service import LEGAL_CLAUSE_LABELS
        assert all(isinstance(label, str) for label in LEGAL_CLAUSE_LABELS)

    def test_legal_clause_labels_no_duplicates(self):
        from services.nlp_service import LEGAL_CLAUSE_LABELS
        assert len(LEGAL_CLAUSE_LABELS) == len(set(LEGAL_CLAUSE_LABELS))

    def test_entailment_threshold_is_0_7(self):
        from services.nlp_service import ENTAILMENT_THRESHOLD
        assert ENTAILMENT_THRESHOLD == 0.7
