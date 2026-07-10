"""
Unit tests for NLP pipeline singleton management in ``nlp_service.py``.

Tests cover:
  - Singleton identity: calling any getter twice returns the **same** Python
    object (``is`` identity equality) — validates Property 17.
  - Call-once guarantee: the underlying ``transformers.pipeline`` factory is
    invoked exactly once even when a getter is called multiple times.
  - Error propagation: ``ModelUnavailableError`` is raised when the
    ``transformers.pipeline`` factory raises an exception.

All tests inject a fake ``transformers`` module into ``sys.modules`` so no
real ML models are downloaded or loaded during the test run.

**Validates: Requirements 4 / Property 17**
"""

from __future__ import annotations

import sys
import os
import types
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure backend/ is on sys.path so relative imports resolve correctly
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_pipelines() -> None:
    """Clear the module-level ``_PIPELINES`` dict between tests."""
    import services.nlp_service as svc
    svc._PIPELINES.clear()


def _make_fake_transformers(pipeline_factory) -> types.ModuleType:
    """Return a minimal fake ``transformers`` module whose ``pipeline``
    attribute is *pipeline_factory*.
    """
    fake = types.ModuleType("transformers")
    fake.pipeline = pipeline_factory
    return fake


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_pipeline_cache():
    """Automatically clear the pipeline cache before and after every test."""
    _reset_pipelines()
    yield
    _reset_pipelines()


@pytest.fixture()
def inject_transformers():
    """Context-manager fixture that injects a fake ``transformers`` module.

    Usage::

        def test_foo(inject_transformers):
            mock_pipe = MagicMock()
            with inject_transformers(mock_pipe) as factory:
                result = get_classification_pipeline()
                assert factory.call_count == 1
    """
    import contextlib

    @contextlib.contextmanager
    def _ctx(return_value=None, side_effect=None):
        mock_factory = MagicMock(
            return_value=return_value,
            side_effect=side_effect,
        )
        fake_transformers = _make_fake_transformers(mock_factory)
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            yield mock_factory

    return _ctx


# ---------------------------------------------------------------------------
# 1. Singleton identity — Property 17
# ---------------------------------------------------------------------------

class TestSingletonIdentity:
    """Calling a getter twice must return the exact same Python object."""

    def test_classification_pipeline_is_singleton(self, inject_transformers):
        mock_pipe = MagicMock(name="classify_pipeline")
        with inject_transformers(return_value=mock_pipe):
            from services.nlp_service import get_classification_pipeline
            first = get_classification_pipeline()
            second = get_classification_pipeline()
        assert first is second, (
            "get_classification_pipeline() must return the same object on repeated calls"
        )

    def test_ner_pipeline_is_singleton(self, inject_transformers):
        mock_pipe = MagicMock(name="ner_pipeline")
        with inject_transformers(return_value=mock_pipe):
            from services.nlp_service import get_ner_pipeline
            first = get_ner_pipeline()
            second = get_ner_pipeline()
        assert first is second, (
            "get_ner_pipeline() must return the same object on repeated calls"
        )

    def test_nli_pipeline_is_singleton(self, inject_transformers):
        mock_pipe = MagicMock(name="nli_pipeline")
        with inject_transformers(return_value=mock_pipe):
            from services.nlp_service import get_nli_pipeline
            first = get_nli_pipeline()
            second = get_nli_pipeline()
        assert first is second, (
            "get_nli_pipeline() must return the same object on repeated calls"
        )

    def test_summarizer_pipeline_is_singleton(self, inject_transformers):
        mock_pipe = MagicMock(name="summarizer_pipeline")
        with inject_transformers(return_value=mock_pipe):
            from services.nlp_service import get_summarizer_pipeline
            first = get_summarizer_pipeline()
            second = get_summarizer_pipeline()
        assert first is second, (
            "get_summarizer_pipeline() must return the same object on repeated calls"
        )

    def test_multiple_calls_all_return_same_object(self, inject_transformers):
        """Calling a getter N times always returns the same object."""
        mock_pipe = MagicMock(name="classify_pipeline")
        with inject_transformers(return_value=mock_pipe):
            from services.nlp_service import get_classification_pipeline
            results = [get_classification_pipeline() for _ in range(5)]
        assert all(r is results[0] for r in results), (
            "All calls must return the identical singleton object"
        )


# ---------------------------------------------------------------------------
# 2. Call-once guarantee
# ---------------------------------------------------------------------------

class TestPipelineCalledOnce:
    """The ``transformers.pipeline`` factory must be called exactly once."""

    def test_classification_pipeline_factory_called_once(self, inject_transformers):
        mock_pipe = MagicMock(name="classify_pipeline")
        with inject_transformers(return_value=mock_pipe) as factory:
            from services.nlp_service import get_classification_pipeline
            get_classification_pipeline()
            get_classification_pipeline()
            get_classification_pipeline()
        assert factory.call_count == 1, (
            "transformers.pipeline should be called exactly once for classification"
        )

    def test_ner_pipeline_factory_called_once(self, inject_transformers):
        mock_pipe = MagicMock(name="ner_pipeline")
        with inject_transformers(return_value=mock_pipe) as factory:
            from services.nlp_service import get_ner_pipeline
            get_ner_pipeline()
            get_ner_pipeline()
        assert factory.call_count == 1, (
            "transformers.pipeline should be called exactly once for NER"
        )

    def test_nli_pipeline_factory_called_once(self, inject_transformers):
        mock_pipe = MagicMock(name="nli_pipeline")
        with inject_transformers(return_value=mock_pipe) as factory:
            from services.nlp_service import get_nli_pipeline
            get_nli_pipeline()
            get_nli_pipeline()
        assert factory.call_count == 1, (
            "transformers.pipeline should be called exactly once for NLI"
        )

    def test_summarizer_pipeline_factory_called_once(self, inject_transformers):
        mock_pipe = MagicMock(name="summarizer_pipeline")
        with inject_transformers(return_value=mock_pipe) as factory:
            from services.nlp_service import get_summarizer_pipeline
            get_summarizer_pipeline()
            get_summarizer_pipeline()
        assert factory.call_count == 1, (
            "transformers.pipeline should be called exactly once for summarizer"
        )

    def test_different_getters_use_independent_singletons(self, inject_transformers):
        """Each getter manages its own key in ``_PIPELINES``; they are independent."""
        classify_mock = MagicMock(name="classify")
        ner_mock = MagicMock(name="ner")
        call_count = {"n": 0}
        mocks = [classify_mock, ner_mock]

        def side_effect(*args, **kwargs):
            result = mocks[call_count["n"]]
            call_count["n"] += 1
            return result

        with inject_transformers(side_effect=side_effect):
            from services.nlp_service import (
                get_classification_pipeline,
                get_ner_pipeline,
            )
            cls1 = get_classification_pipeline()
            ner1 = get_ner_pipeline()
            cls2 = get_classification_pipeline()
            ner2 = get_ner_pipeline()

        assert cls1 is cls2, "Classification singleton must be stable"
        assert ner1 is ner2, "NER singleton must be stable"
        assert cls1 is not ner1, "Different getters must return different objects"


# ---------------------------------------------------------------------------
# 3. ModelUnavailableError on pipeline load failure
# ---------------------------------------------------------------------------

class TestModelUnavailableError:
    """``ModelUnavailableError`` must be raised when the pipeline fails to load."""

    def test_classification_raises_model_unavailable_on_failure(self, inject_transformers):
        from services.nlp_service import ModelUnavailableError, get_classification_pipeline
        with inject_transformers(side_effect=RuntimeError("OOM")):
            with pytest.raises(ModelUnavailableError):
                get_classification_pipeline()

    def test_ner_raises_model_unavailable_on_failure(self, inject_transformers):
        from services.nlp_service import ModelUnavailableError, get_ner_pipeline
        with inject_transformers(side_effect=OSError("weights not found")):
            with pytest.raises(ModelUnavailableError):
                get_ner_pipeline()

    def test_nli_raises_model_unavailable_on_failure(self, inject_transformers):
        from services.nlp_service import ModelUnavailableError, get_nli_pipeline
        with inject_transformers(side_effect=ValueError("bad config")):
            with pytest.raises(ModelUnavailableError):
                get_nli_pipeline()

    def test_summarizer_raises_model_unavailable_on_failure(self, inject_transformers):
        from services.nlp_service import ModelUnavailableError, get_summarizer_pipeline
        with inject_transformers(side_effect=MemoryError("OOM")):
            with pytest.raises(ModelUnavailableError):
                get_summarizer_pipeline()

    def test_model_unavailable_error_wraps_original_exception(self, inject_transformers):
        """The original exception should be chained as ``__cause__``."""
        from services.nlp_service import ModelUnavailableError, get_classification_pipeline
        original = RuntimeError("GPU not available")
        with inject_transformers(side_effect=original):
            with pytest.raises(ModelUnavailableError) as exc_info:
                get_classification_pipeline()
        assert exc_info.value.__cause__ is original

    def test_failed_load_does_not_cache_broken_pipeline(self, inject_transformers):
        """After a failed load the key must NOT be stored in ``_PIPELINES``.

        This ensures a subsequent call (after the error is resolved) can
        attempt to load the pipeline again rather than returning ``None``.
        """
        import services.nlp_service as svc
        from services.nlp_service import ModelUnavailableError, get_classification_pipeline

        with inject_transformers(side_effect=RuntimeError("fail")):
            with pytest.raises(ModelUnavailableError):
                get_classification_pipeline()

        assert "classify" not in svc._PIPELINES, (
            "A failed pipeline load must not leave a broken entry in _PIPELINES"
        )

    def test_retry_after_failure_succeeds(self, inject_transformers):
        """After a failed load, a subsequent call with a working factory succeeds."""
        from services.nlp_service import ModelUnavailableError, get_classification_pipeline

        mock_pipe = MagicMock(name="classify_pipeline")

        # First call fails
        with inject_transformers(side_effect=RuntimeError("transient")):
            with pytest.raises(ModelUnavailableError):
                get_classification_pipeline()

        # Second call succeeds
        with inject_transformers(return_value=mock_pipe):
            result = get_classification_pipeline()

        assert result is mock_pipe
