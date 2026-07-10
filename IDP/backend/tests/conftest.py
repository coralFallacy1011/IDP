"""
Shared pytest fixtures for the Legal NLP/LLM module test suite.

Provides mock pipelines, sample texts, and a minimal MongoDB document
fixture so individual test modules don't need to repeat boilerplate.
"""

from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Ensure backend/ is on sys.path so service/model imports work
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Import LEGAL_DOC_TYPES lazily to avoid loading the full service at collection
# time (which would attempt to import transformers).
def _get_legal_doc_types() -> list[str]:
    from services.nlp_service import LEGAL_DOC_TYPES  # noqa: PLC0415
    return LEGAL_DOC_TYPES


# ---------------------------------------------------------------------------
# MongoDB mock
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_mongo_collection() -> MagicMock:
    """A MagicMock that simulates a pymongo Collection.

    Provides ``find_one``, ``update_one``, and ``create_index`` methods.
    """
    collection = MagicMock()
    collection.find_one = MagicMock(return_value=None)
    collection.update_one = MagicMock(return_value=MagicMock(modified_count=1))
    collection.create_index = MagicMock(return_value="index_name")
    return collection


# ---------------------------------------------------------------------------
# Pipeline mocks
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_classify_pipeline() -> MagicMock:
    """Mock HuggingFace zero-shot classification pipeline.

    Returns uniform scores across all LEGAL_DOC_TYPES so that tests are
    deterministic and independent of model weights.
    """
    legal_doc_types = _get_legal_doc_types()
    n = len(legal_doc_types)
    uniform_score = 1.0 / n

    mock_pipe = MagicMock()
    mock_pipe.return_value = {
        "labels": list(legal_doc_types),
        "scores": [uniform_score] * n,
    }
    return mock_pipe


@pytest.fixture
def mock_ner_pipeline() -> MagicMock:
    """Mock HuggingFace token-classification (NER) pipeline.

    Returns a list of entity dicts with keys ``text``, ``label``, ``score``,
    ``start``, and ``end``.
    """
    mock_pipe = MagicMock()
    mock_pipe.return_value = [
        {"text": "John Smith",  "label": "PER",   "score": 0.95, "start": 0,  "end": 10},
        {"text": "Acme Corp",   "label": "ORG",   "score": 0.90, "start": 15, "end": 24},
        {"text": "1 January 2024", "label": "DATE", "score": 0.88, "start": 30, "end": 45},
        {"text": "New Delhi",   "label": "GPE",   "score": 0.85, "start": 50, "end": 59},
        {"text": "INR 50,000",  "label": "MONEY", "score": 0.80, "start": 65, "end": 75},
    ]
    return mock_pipe


@pytest.fixture
def mock_nli_pipeline() -> MagicMock:
    """Mock HuggingFace zero-shot NLI pipeline.

    Returns entailment scores above the ENTAILMENT_THRESHOLD (0.7) for the
    first candidate label so that clause detection tests have a predictable
    positive result.
    """
    mock_pipe = MagicMock()

    def _nli_side_effect(text: str, candidate_labels: list[str], **kwargs):
        n = len(candidate_labels)
        # Give the first label a high entailment score; rest get low scores
        scores = [0.05] * n
        if n > 0:
            scores[0] = 0.85
        return {"labels": list(candidate_labels), "scores": scores}

    mock_pipe.side_effect = _nli_side_effect
    return mock_pipe


@pytest.fixture
def mock_summarizer_pipeline() -> MagicMock:
    """Mock HuggingFace summarization pipeline.

    Returns a short, fixed summary string so summarization tests are
    deterministic without loading any model weights.
    """
    mock_pipe = MagicMock()
    mock_pipe.return_value = [
        {"summary_text": "This is a concise summary of the legal document."}
    ]
    return mock_pipe


# ---------------------------------------------------------------------------
# Sample texts
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_legal_text() -> str:
    """A sample legal contract text of at least 100 words."""
    return (
        "THIS AGREEMENT is entered into as of the 1st day of January 2024, "
        "by and between Acme Corporation, a company incorporated under the laws "
        "of India, having its registered office at 123 Business Park, New Delhi "
        "(hereinafter referred to as 'the Company'), and John Smith, residing at "
        "456 Residential Colony, Mumbai (hereinafter referred to as 'the Contractor'). "
        "WHEREAS the Company desires to engage the Contractor to provide certain "
        "professional services, and the Contractor is willing to provide such services "
        "on the terms and conditions set forth herein. NOW THEREFORE, in consideration "
        "of the mutual covenants and agreements contained herein, and for other good "
        "and valuable consideration, the receipt and sufficiency of which are hereby "
        "acknowledged, the parties agree as follows: The Contractor shall provide "
        "software development services as described in Schedule A attached hereto. "
        "The Company shall pay the Contractor a fee of INR 50,000 per month. "
        "Either party may terminate this Agreement upon thirty days written notice. "
        "This Agreement shall be governed by the laws of India. Any disputes arising "
        "under this Agreement shall be resolved by arbitration in New Delhi."
    )


@pytest.fixture
def sample_short_text() -> str:
    """Text shorter than 20 characters (triggers the short-text guard)."""
    return "Short text."


# ---------------------------------------------------------------------------
# Sample MongoDB document
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_doc() -> dict:
    """A minimal MongoDB document dict as stored in the IDP collection.

    Contains the fields expected by the NLP service:
    ``_id``, ``clean_text``, ``fields``, ``lang``, ``lang_detected``, ``nlp``.
    """
    return {
        "_id": "doc_001",
        "clean_text": (
            "THIS AGREEMENT is entered into as of the 1st day of January 2024 "
            "by and between Acme Corporation and John Smith."
        ),
        "fields": {
            "parties": ["Acme Corporation", "John Smith"],
            "dates": ["1 January 2024"],
            "document_ids": [],
        },
        "lang": "eng",
        "lang_detected": "en",
        "nlp": {},
    }
