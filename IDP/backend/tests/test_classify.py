"""
Property-based and unit tests for ``nlp_service.classify``.

Tests cover:
  - scores sum to 1.0 (within 0.01 tolerance)
  - ``doc_type`` is always in ``LEGAL_DOC_TYPES``
  - ``confidence`` is always in [0.0, 1.0]
  - short-text guard: text < 20 chars returns ``ClassificationResult("unknown", 0.0, {})``
  - empty string returns safe default
  - exception in pipeline returns safe default
  - ``apply_field_hints`` boosts correct labels

All tests mock the ML pipeline — no real model downloads.

**Validates: Requirements 2 / Properties 1, 2**
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


def _make_mock_classify_pipeline(labels, scores):
    """Return a callable that mimics the HuggingFace zero-shot pipeline output."""
    mock_pipe = MagicMock()
    mock_pipe.return_value = {"labels": labels, "scores": scores}
    return mock_pipe


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

# Generate text that is at least 20 characters long (passes the short-text guard)
long_text_st = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
    min_size=20,
).filter(lambda t: len(t) >= 20 and len(t.split()) >= 1)

# Generate text that is shorter than 20 characters (triggers short-text guard)
short_text_st = st.text(min_size=0, max_size=19)

# Generate a dict of fields (may be empty or have hint keys)
fields_st = st.fixed_dictionaries({}).map(lambda _: {})


# ---------------------------------------------------------------------------
# 1. Property: scores sum to 1.0 (within 0.01 tolerance)
# ---------------------------------------------------------------------------

class TestScoresSumToOne:
    """Property 1: all_scores values sum to approximately 1.0."""

    def _run_classify_with_uniform_scores(self, text: str, fields: dict):
        from services.nlp_service import classify, LEGAL_DOC_TYPES

        n = len(LEGAL_DOC_TYPES)
        uniform_score = 1.0 / n
        mock_pipe = _make_mock_classify_pipeline(
            labels=LEGAL_DOC_TYPES,
            scores=[uniform_score] * n,
        )
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = classify(text, fields)
        return result

    @given(long_text_st, fields_st)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_scores_sum_to_one_property(self, text, fields):
        """**Validates: Requirements 2 / Property 1**"""
        result = self._run_classify_with_uniform_scores(text, fields)
        if result.all_scores:
            total = sum(result.all_scores.values())
            assert abs(total - 1.0) < 0.01, (
                f"all_scores should sum to ~1.0, got {total}"
            )

    def test_scores_sum_to_one_example(self):
        from services.nlp_service import classify, LEGAL_DOC_TYPES
        text = "This is a legal contract document with sufficient length."
        n = len(LEGAL_DOC_TYPES)
        mock_pipe = _make_mock_classify_pipeline(
            labels=LEGAL_DOC_TYPES,
            scores=[1.0 / n] * n,
        )
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = classify(text, {})
        assert abs(sum(result.all_scores.values()) - 1.0) < 0.01

    def test_scores_sum_to_one_after_field_hints(self):
        """Scores must still sum to 1.0 after apply_field_hints boosts."""
        from services.nlp_service import classify, LEGAL_DOC_TYPES
        text = "This is a legal contract document with sufficient length."
        n = len(LEGAL_DOC_TYPES)
        mock_pipe = _make_mock_classify_pipeline(
            labels=LEGAL_DOC_TYPES,
            scores=[1.0 / n] * n,
        )
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = classify(text, {"fir_number": "FIR/123/2024", "parties": ["A", "B"]})
        assert abs(sum(result.all_scores.values()) - 1.0) < 0.01


# ---------------------------------------------------------------------------
# 2. Property: doc_type is always in LEGAL_DOC_TYPES
# ---------------------------------------------------------------------------

class TestDocTypeInLegalDocTypes:
    """Property 2: doc_type is always a member of LEGAL_DOC_TYPES."""

    @given(long_text_st, fields_st)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_doc_type_in_legal_doc_types_property(self, text, fields):
        """**Validates: Requirements 2 / Property 2**"""
        from services.nlp_service import classify, LEGAL_DOC_TYPES
        n = len(LEGAL_DOC_TYPES)
        mock_pipe = _make_mock_classify_pipeline(
            labels=LEGAL_DOC_TYPES,
            scores=[1.0 / n] * n,
        )
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = classify(text, fields)
        assert result.doc_type in LEGAL_DOC_TYPES, (
            f"doc_type '{result.doc_type}' not in LEGAL_DOC_TYPES"
        )

    def test_doc_type_in_legal_doc_types_example(self):
        from services.nlp_service import classify, LEGAL_DOC_TYPES
        text = "This is a legal contract document with sufficient length."
        n = len(LEGAL_DOC_TYPES)
        mock_pipe = _make_mock_classify_pipeline(
            labels=LEGAL_DOC_TYPES,
            scores=[1.0 / n] * n,
        )
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = classify(text, {})
        assert result.doc_type in LEGAL_DOC_TYPES

    def test_short_text_returns_unknown_doc_type(self):
        from services.nlp_service import classify, LEGAL_DOC_TYPES
        result = classify("short", {})
        assert result.doc_type in LEGAL_DOC_TYPES
        assert result.doc_type == "unknown"

    def test_empty_string_returns_unknown_doc_type(self):
        from services.nlp_service import classify, LEGAL_DOC_TYPES
        result = classify("", {})
        assert result.doc_type in LEGAL_DOC_TYPES
        assert result.doc_type == "unknown"


# ---------------------------------------------------------------------------
# 3. Property: confidence is always in [0.0, 1.0]
# ---------------------------------------------------------------------------

class TestConfidenceInRange:
    """Property: confidence is always in [0.0, 1.0]."""

    @given(long_text_st, fields_st)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_confidence_in_range_property(self, text, fields):
        """**Validates: Requirements 2 / Property 2**"""
        from services.nlp_service import classify, LEGAL_DOC_TYPES
        n = len(LEGAL_DOC_TYPES)
        mock_pipe = _make_mock_classify_pipeline(
            labels=LEGAL_DOC_TYPES,
            scores=[1.0 / n] * n,
        )
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = classify(text, fields)
        assert 0.0 <= result.confidence <= 1.0, (
            f"confidence {result.confidence} not in [0.0, 1.0]"
        )

    def test_confidence_in_range_example(self):
        from services.nlp_service import classify, LEGAL_DOC_TYPES
        text = "This is a legal contract document with sufficient length."
        n = len(LEGAL_DOC_TYPES)
        mock_pipe = _make_mock_classify_pipeline(
            labels=LEGAL_DOC_TYPES,
            scores=[1.0 / n] * n,
        )
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = classify(text, {})
        assert 0.0 <= result.confidence <= 1.0

    def test_confidence_in_range_after_boost(self):
        """Confidence must remain in [0.0, 1.0] even after field hint boosts."""
        from services.nlp_service import classify, LEGAL_DOC_TYPES
        text = "This is a legal contract document with sufficient length."
        n = len(LEGAL_DOC_TYPES)
        mock_pipe = _make_mock_classify_pipeline(
            labels=LEGAL_DOC_TYPES,
            scores=[1.0 / n] * n,
        )
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = classify(text, {"fir_number": "FIR/001/2024"})
        assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# 4. Short-text guard
# ---------------------------------------------------------------------------

class TestShortTextGuard:
    """Short text (< 20 chars) must return ClassificationResult("unknown", 0.0, {})."""

    @given(short_text_st)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_short_text_returns_safe_default_property(self, text):
        """**Validates: Requirements 2 / Property 1**"""
        from services.nlp_service import classify
        result = classify(text, {})
        assert result.doc_type == "unknown"
        assert result.confidence == 0.0
        assert result.all_scores == {}

    def test_empty_string_returns_safe_default(self):
        from services.nlp_service import classify
        result = classify("", {})
        assert result.doc_type == "unknown"
        assert result.confidence == 0.0
        assert result.all_scores == {}

    def test_19_char_text_returns_safe_default(self):
        from services.nlp_service import classify
        result = classify("a" * 19, {})
        assert result.doc_type == "unknown"
        assert result.confidence == 0.0
        assert result.all_scores == {}

    def test_exactly_20_chars_does_not_trigger_guard(self):
        """Text of exactly 20 chars should attempt classification (not return safe default)."""
        from services.nlp_service import classify, LEGAL_DOC_TYPES
        text = "a" * 20
        n = len(LEGAL_DOC_TYPES)
        mock_pipe = _make_mock_classify_pipeline(
            labels=LEGAL_DOC_TYPES,
            scores=[1.0 / n] * n,
        )
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = classify(text, {})
        # Should have attempted classification — all_scores should be non-empty
        assert result.all_scores != {}


# ---------------------------------------------------------------------------
# 5. Exception in pipeline returns safe default
# ---------------------------------------------------------------------------

class TestExceptionHandling:
    """Any exception during pipeline inference must return the safe default."""

    def test_pipeline_exception_returns_safe_default(self):
        from services.nlp_service import classify
        text = "This is a legal contract document with sufficient length."

        mock_pipe = MagicMock(side_effect=RuntimeError("GPU OOM"))
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = classify(text, {})
        assert result.doc_type == "unknown"
        assert result.confidence == 0.0
        assert result.all_scores == {}

    def test_pipeline_load_exception_returns_safe_default(self):
        from services.nlp_service import classify
        text = "This is a legal contract document with sufficient length."

        # Make the pipeline factory itself raise
        fake_transformers = _make_fake_transformers(
            MagicMock(side_effect=OSError("weights not found"))
        )
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = classify(text, {})
        assert result.doc_type == "unknown"
        assert result.confidence == 0.0
        assert result.all_scores == {}

    def test_value_error_in_pipeline_returns_safe_default(self):
        from services.nlp_service import classify
        text = "This is a legal contract document with sufficient length."

        mock_pipe = MagicMock(side_effect=ValueError("bad input"))
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = classify(text, {})
        assert result.doc_type == "unknown"
        assert result.confidence == 0.0
        assert result.all_scores == {}


# ---------------------------------------------------------------------------
# 6. apply_field_hints boosts correct labels
# ---------------------------------------------------------------------------

class TestApplyFieldHints:
    """apply_field_hints must boost the correct labels based on field presence."""

    def test_fir_number_boosts_fir(self):
        from services.nlp_service import apply_field_hints
        raw = {"FIR": 0.1, "contract": 0.5, "agreement": 0.4}
        boosted = apply_field_hints(raw, {"fir_number": "FIR/001/2024"})
        assert boosted["FIR"] > raw["FIR"]
        assert boosted["FIR"] == pytest.approx(0.1 + 0.3)

    def test_parties_boosts_contract_and_agreement(self):
        from services.nlp_service import apply_field_hints
        raw = {"FIR": 0.1, "contract": 0.5, "agreement": 0.4}
        boosted = apply_field_hints(raw, {"parties": ["Party A", "Party B"]})
        assert boosted["contract"] == pytest.approx(0.5 + 0.2)
        assert boosted["agreement"] == pytest.approx(0.4 + 0.2)

    def test_case_number_boosts_judgment_and_petition(self):
        from services.nlp_service import apply_field_hints
        raw = {"judgment": 0.3, "petition": 0.2, "FIR": 0.5}
        boosted = apply_field_hints(raw, {"case_number": "CASE/001/2024"})
        assert boosted["judgment"] == pytest.approx(0.3 + 0.15)
        assert boosted["petition"] == pytest.approx(0.2 + 0.15)

    def test_notary_boosts_affidavit(self):
        from services.nlp_service import apply_field_hints
        raw = {"affidavit": 0.2, "contract": 0.8}
        boosted = apply_field_hints(raw, {"notary": "Notary Public"})
        assert boosted["affidavit"] == pytest.approx(0.2 + 0.2)

    def test_empty_fields_no_boost(self):
        from services.nlp_service import apply_field_hints
        raw = {"FIR": 0.5, "contract": 0.3, "agreement": 0.2}
        boosted = apply_field_hints(raw, {})
        assert boosted == raw

    def test_field_hints_boost_leads_to_correct_classification(self):
        """FIR field hint should cause FIR to win classification."""
        from services.nlp_service import classify, LEGAL_DOC_TYPES
        text = "This is a legal document with sufficient length for classification."
        n = len(LEGAL_DOC_TYPES)
        # Give FIR a low initial score
        scores = [0.05] * n
        fir_idx = LEGAL_DOC_TYPES.index("FIR")
        scores[fir_idx] = 0.05  # FIR starts low

        mock_pipe = _make_mock_classify_pipeline(
            labels=LEGAL_DOC_TYPES,
            scores=scores,
        )
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = classify(text, {"fir_number": "FIR/001/2024"})
        # After boost of 0.3, FIR should win
        assert result.doc_type == "FIR"
