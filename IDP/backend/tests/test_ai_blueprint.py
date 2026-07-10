"""Integration tests for the AI Flask blueprint (routes/ai.py).

Tests validate:
- Property 18: All responses contain ``ok``, ``data``, ``cached`` keys.
- Property 19: After an endpoint call the MongoDB document has an ``nlp``
  sub-document with ``processed_at`` and ``model`` fields.
- Property 20: A second call to the same endpoint returns ``cached=True``
  with the same data.

Additional coverage:
- 400 on invalid ObjectId.
- 404 on missing document.
- Correct envelope structure for every endpoint.

All MongoDB and service calls are mocked so no real DB or models are needed.
"""

from __future__ import annotations

import datetime
import sys
import os
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup — ensure backend/ is on sys.path so Flask app can be imported
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    """Create a minimal Flask test application with only the AI blueprint.

    We build a fresh Flask app and register only ``ai_bp`` so that missing
    sibling route modules (documents, ocr) do not cause import errors.

    We patch ``routes.ai.db`` directly — the module-level ``db`` reference
    that the blueprint uses — rather than trying to intercept MongoClient at
    import time (which has already happened by the time tests run).

    The fixture yields ``(flask_app, mock_collection)`` where
    ``mock_collection`` is the mock returned by ``db["ocr_documents"]``.
    """
    from flask import Flask
    from routes.ai import ai_bp

    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True
    flask_app.register_blueprint(ai_bp, url_prefix="/api/ai")

    # mock_collection simulates db["ocr_documents"]
    mock_collection = MagicMock()
    mock_db = MagicMock()
    # Any key access on mock_db returns mock_collection
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)

    with patch("routes.ai.db", mock_db):
        yield flask_app, mock_collection


@pytest.fixture()
def client(app):
    flask_app, mock_collection = app
    with flask_app.test_client() as c:
        yield c, mock_collection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(doc_id_str: str, nlp: dict | None = None) -> dict:
    """Return a minimal ocr_documents document dict."""
    from bson import ObjectId
    return {
        "_id":           ObjectId(doc_id_str),
        "filename":      "test.pdf",
        "clean_text":    "This is a sample legal contract between Party A and Party B.",
        "fields":        {"names": ["Party A", "Party B"]},
        "lang":          "eng",
        "lang_detected": "eng",
        "created_at":    datetime.datetime.utcnow(),
        "nlp":           nlp or {},
    }


VALID_OID = "507f1f77bcf86cd799439011"


# ---------------------------------------------------------------------------
# 400 on invalid ObjectId
# ---------------------------------------------------------------------------

class TestInvalidObjectId:
    """All Phase 1 endpoints must return 400 for a malformed doc_id."""

    @pytest.mark.parametrize("endpoint", [
        "/api/ai/classify",
        "/api/ai/extract",
        "/api/ai/summarize",
        "/api/ai/risk-check",
    ])
    def test_400_on_invalid_oid(self, client, endpoint):
        c, _ = client
        resp = c.post(endpoint, json={"doc_id": "not-an-objectid"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert "error" in data

    def test_search_400_on_invalid_oid(self, client):
        c, _ = client
        resp = c.post("/api/ai/search",
                      json={"doc_id": "bad", "query": "contract"})
        assert resp.status_code == 400

    def test_chat_400_on_invalid_oid(self, client):
        c, _ = client
        resp = c.post("/api/ai/chat",
                      json={"doc_id": "bad", "question": "What is this?"})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 404 on missing document
# ---------------------------------------------------------------------------

class TestMissingDocument:
    """All Phase 1 endpoints must return 404 when the document is not found."""

    @pytest.mark.parametrize("endpoint", [
        "/api/ai/classify",
        "/api/ai/extract",
        "/api/ai/summarize",
        "/api/ai/risk-check",
    ])
    def test_404_on_missing_doc(self, client, endpoint):
        c, mock_col = client
        mock_col.find_one.return_value = None
        resp = c.post(endpoint, json={"doc_id": VALID_OID})
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["ok"] is False

    def test_search_404_on_missing_doc(self, client):
        c, mock_col = client
        mock_col.find_one.return_value = None
        resp = c.post("/api/ai/search",
                      json={"doc_id": VALID_OID, "query": "contract"})
        assert resp.status_code == 404

    def test_chat_404_on_missing_doc(self, client):
        c, mock_col = client
        mock_col.find_one.return_value = None
        resp = c.post("/api/ai/chat",
                      json={"doc_id": VALID_OID, "question": "What is this?"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Envelope structure — Property 18
# ---------------------------------------------------------------------------

class TestEnvelopeStructure:
    """Every successful response must contain ``ok``, ``data``, ``cached``."""

    def _setup_doc(self, mock_col, nlp=None):
        doc = _make_doc(VALID_OID, nlp=nlp)
        mock_col.find_one.return_value = doc
        mock_col.update_one.return_value = MagicMock()
        return doc

    def test_classify_envelope(self, client):
        c, mock_col = client
        self._setup_doc(mock_col)
        from models.nlp_models import ClassificationResult
        mock_result = ClassificationResult(
            doc_type="contract", confidence=0.9,
            all_scores={"contract": 0.9, "FIR": 0.1}
        )
        with patch("routes.ai.nlp_service.classify", return_value=mock_result):
            resp = c.post("/api/ai/classify", json={"doc_id": VALID_OID})
        assert resp.status_code == 200
        body = resp.get_json()
        assert "ok" in body
        assert "data" in body
        assert "cached" in body
        assert body["ok"] is True
        assert body["cached"] is False

    def test_extract_envelope(self, client):
        c, mock_col = client
        self._setup_doc(mock_col)
        from models.nlp_models import EntityExtractionResult, ClauseDetectionResult
        mock_entities = EntityExtractionResult(
            persons=["Alice"], organisations=[], dates=[], money=[],
            locations=[], case_numbers=[], raw_entities=[]
        )
        mock_clauses = ClauseDetectionResult(clauses_found=[], clause_spans=[])
        with patch("routes.ai.nlp_service.extract_entities", return_value=mock_entities), \
             patch("routes.ai.nlp_service.detect_clauses", return_value=mock_clauses):
            resp = c.post("/api/ai/extract", json={"doc_id": VALID_OID})
        assert resp.status_code == 200
        body = resp.get_json()
        assert "ok" in body and "data" in body and "cached" in body
        assert "entities" in body["data"]
        assert "clauses" in body["data"]

    def test_summarize_envelope(self, client):
        c, mock_col = client
        self._setup_doc(mock_col)
        from models.nlp_models import SummarizationResult
        mock_result = SummarizationResult(
            summary="A contract between two parties.", word_count=6,
            compression_ratio=0.1
        )
        with patch("routes.ai.nlp_service.summarize", return_value=mock_result):
            resp = c.post("/api/ai/summarize", json={"doc_id": VALID_OID})
        assert resp.status_code == 200
        body = resp.get_json()
        assert "ok" in body and "data" in body and "cached" in body
        assert "text" in body["data"]

    def test_risk_check_envelope(self, client):
        c, mock_col = client
        self._setup_doc(mock_col)
        from models.nlp_models import RiskResult
        mock_result = RiskResult(risk_level="low", flags=[], score=0.1)
        with patch("routes.ai.nlp_service.risk_check", return_value=mock_result):
            resp = c.post("/api/ai/risk-check", json={"doc_id": VALID_OID})
        assert resp.status_code == 200
        body = resp.get_json()
        assert "ok" in body and "data" in body and "cached" in body
        assert body["data"]["risk_level"] in {"low", "medium", "high"}

    def test_search_envelope(self, client):
        c, mock_col = client
        self._setup_doc(mock_col)
        from models.nlp_models import ChunkResult
        mock_results = [ChunkResult(chunk_text="text", doc_id=VALID_OID,
                                    chunk_index=0, score=0.9)]
        with patch("routes.ai.embedding_service.similarity_search",
                   return_value=mock_results):
            resp = c.post("/api/ai/search",
                          json={"doc_id": VALID_OID, "query": "contract"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert "ok" in body and "data" in body and "cached" in body

    def test_chat_envelope(self, client):
        c, mock_col = client
        self._setup_doc(mock_col)
        from models.nlp_models import RAGResult
        mock_result = RAGResult(answer="It is a contract.", source_chunks=[],
                                model_used="TinyLlama")
        with patch("routes.ai.rag_service.answer_question", return_value=mock_result):
            resp = c.post("/api/ai/chat",
                          json={"doc_id": VALID_OID, "question": "What is this?"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert "ok" in body and "data" in body and "cached" in body

    def test_cross_search_envelope(self, client):
        c, _ = client
        from models.nlp_models import ChunkResult
        mock_results = [ChunkResult(chunk_text="text", doc_id=VALID_OID,
                                    chunk_index=0, score=0.8)]
        with patch("routes.ai.embedding_service.cross_document_search",
                   return_value=mock_results):
            resp = c.post("/api/ai/cross-search",
                          json={"query": "contract", "doc_ids": [VALID_OID]})
        assert resp.status_code == 200
        body = resp.get_json()
        assert "ok" in body and "data" in body and "cached" in body


# ---------------------------------------------------------------------------
# NLP persistence — Property 19
# ---------------------------------------------------------------------------

class TestNLPPersistence:
    """After an endpoint call the MongoDB document must have ``processed_at``
    and ``model`` in the ``nlp`` sub-document."""

    def _setup_doc(self, mock_col):
        doc = _make_doc(VALID_OID)
        mock_col.find_one.return_value = doc
        mock_col.update_one.return_value = MagicMock()
        return doc

    def test_classify_persists_processed_at_and_model(self, client):
        c, mock_col = client
        self._setup_doc(mock_col)
        from models.nlp_models import ClassificationResult
        mock_result = ClassificationResult(
            doc_type="FIR", confidence=0.85, all_scores={"FIR": 0.85}
        )
        with patch("routes.ai.nlp_service.classify", return_value=mock_result):
            resp = c.post("/api/ai/classify", json={"doc_id": VALID_OID})
        assert resp.status_code == 200

        # Verify update_one was called with $set containing processed_at and model
        update_call = mock_col.update_one.call_args
        assert update_call is not None
        set_doc = update_call[0][1]["$set"]["nlp.classification"]
        assert "processed_at" in set_doc
        assert "model" in set_doc
        assert set_doc["model"] == "InLegalBERT"

    def test_summarize_persists_processed_at_and_model(self, client):
        c, mock_col = client
        self._setup_doc(mock_col)
        from models.nlp_models import SummarizationResult
        mock_result = SummarizationResult(
            summary="Short summary.", word_count=2, compression_ratio=0.05
        )
        with patch("routes.ai.nlp_service.summarize", return_value=mock_result):
            resp = c.post("/api/ai/summarize", json={"doc_id": VALID_OID})
        assert resp.status_code == 200

        update_call = mock_col.update_one.call_args
        set_doc = update_call[0][1]["$set"]["nlp.summary"]
        assert "processed_at" in set_doc
        assert "model" in set_doc
        assert set_doc["model"] == "BART-large-CNN"

    def test_risk_check_persists_processed_at(self, client):
        c, mock_col = client
        self._setup_doc(mock_col)
        from models.nlp_models import RiskResult
        mock_result = RiskResult(risk_level="medium", flags=[], score=0.4)
        with patch("routes.ai.nlp_service.risk_check", return_value=mock_result):
            resp = c.post("/api/ai/risk-check", json={"doc_id": VALID_OID})
        assert resp.status_code == 200

        update_call = mock_col.update_one.call_args
        set_doc = update_call[0][1]["$set"]["nlp.risk"]
        assert "processed_at" in set_doc

    def test_extract_persists_both_subdocs(self, client):
        c, mock_col = client
        self._setup_doc(mock_col)
        from models.nlp_models import EntityExtractionResult, ClauseDetectionResult
        mock_entities = EntityExtractionResult(
            persons=[], organisations=[], dates=[], money=[],
            locations=[], case_numbers=[], raw_entities=[]
        )
        mock_clauses = ClauseDetectionResult(clauses_found=[], clause_spans=[])
        with patch("routes.ai.nlp_service.extract_entities", return_value=mock_entities), \
             patch("routes.ai.nlp_service.detect_clauses", return_value=mock_clauses):
            resp = c.post("/api/ai/extract", json={"doc_id": VALID_OID})
        assert resp.status_code == 200

        update_call = mock_col.update_one.call_args
        set_payload = update_call[0][1]["$set"]
        assert "nlp.entities" in set_payload
        assert "nlp.clauses" in set_payload
        assert "processed_at" in set_payload["nlp.entities"]
        assert "model" in set_payload["nlp.entities"]
        assert "processed_at" in set_payload["nlp.clauses"]


# ---------------------------------------------------------------------------
# Caching idempotence — Property 20
# ---------------------------------------------------------------------------

class TestCachingIdempotence:
    """A second call to the same endpoint must return ``cached=True``."""

    def test_classify_cached_on_second_call(self, client):
        c, mock_col = client
        cached_classification = {
            "doc_type":     "contract",
            "confidence":   0.9,
            "all_scores":   {"contract": 0.9},
            "model":        "InLegalBERT",
            "processed_at": datetime.datetime.utcnow().isoformat(),
            "lang":         "eng",
        }
        doc = _make_doc(VALID_OID, nlp={"classification": cached_classification})
        mock_col.find_one.return_value = doc

        resp = c.post("/api/ai/classify", json={"doc_id": VALID_OID})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["cached"] is True
        assert body["data"] == cached_classification

    def test_summarize_cached_on_second_call(self, client):
        c, mock_col = client
        cached_summary = {
            "text":              "A short summary.",
            "word_count":        3,
            "compression_ratio": 0.05,
            "model":             "BART-large-CNN",
            "processed_at":      datetime.datetime.utcnow().isoformat(),
            "lang":              "eng",
        }
        doc = _make_doc(VALID_OID, nlp={"summary": cached_summary})
        mock_col.find_one.return_value = doc

        resp = c.post("/api/ai/summarize", json={"doc_id": VALID_OID})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["cached"] is True
        assert body["data"] == cached_summary

    def test_risk_check_cached_on_second_call(self, client):
        c, mock_col = client
        cached_risk = {
            "risk_level":   "low",
            "score":        0.1,
            "flags":        [],
            "processed_at": datetime.datetime.utcnow().isoformat(),
            "lang":         "eng",
        }
        doc = _make_doc(VALID_OID, nlp={"risk": cached_risk})
        mock_col.find_one.return_value = doc

        resp = c.post("/api/ai/risk-check", json={"doc_id": VALID_OID})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["cached"] is True

    def test_extract_cached_on_second_call(self, client):
        c, mock_col = client
        cached_entities = {
            "persons": ["Alice"], "organisations": [], "dates": [],
            "money": [], "locations": [], "case_numbers": [], "raw_entities": [],
            "model": "Legal-BERT-NER",
            "processed_at": datetime.datetime.utcnow().isoformat(),
            "lang": "eng",
        }
        cached_clauses = {
            "clauses_found": [], "clause_spans": [],
            "processed_at": datetime.datetime.utcnow().isoformat(),
            "lang": "eng",
        }
        doc = _make_doc(VALID_OID, nlp={
            "entities": cached_entities,
            "clauses":  cached_clauses,
        })
        mock_col.find_one.return_value = doc

        resp = c.post("/api/ai/extract", json={"doc_id": VALID_OID})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["cached"] is True

    def test_force_bypasses_cache(self, client):
        c, mock_col = client
        cached_classification = {
            "doc_type":     "FIR",
            "confidence":   0.7,
            "all_scores":   {"FIR": 0.7},
            "model":        "InLegalBERT",
            "processed_at": datetime.datetime.utcnow().isoformat(),
            "lang":         "eng",
        }
        doc = _make_doc(VALID_OID, nlp={"classification": cached_classification})
        mock_col.find_one.return_value = doc
        mock_col.update_one.return_value = MagicMock()

        from models.nlp_models import ClassificationResult
        new_result = ClassificationResult(
            doc_type="contract", confidence=0.95,
            all_scores={"contract": 0.95}
        )
        with patch("routes.ai.nlp_service.classify", return_value=new_result):
            resp = c.post("/api/ai/classify",
                          json={"doc_id": VALID_OID, "force": True})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["cached"] is False
        assert body["data"]["doc_type"] == "contract"


# ---------------------------------------------------------------------------
# Validation tests (12.11)
# ---------------------------------------------------------------------------

class TestValidation:
    """Confidence and risk score must be clamped to [0.0, 1.0]."""

    def _setup_doc(self, mock_col):
        doc = _make_doc(VALID_OID)
        mock_col.find_one.return_value = doc
        mock_col.update_one.return_value = MagicMock()

    def test_confidence_clamped(self, client):
        c, mock_col = client
        self._setup_doc(mock_col)
        from models.nlp_models import ClassificationResult
        # Simulate a result with out-of-range confidence
        mock_result = ClassificationResult(
            doc_type="contract", confidence=1.5,
            all_scores={"contract": 1.5}
        )
        with patch("routes.ai.nlp_service.classify", return_value=mock_result):
            resp = c.post("/api/ai/classify", json={"doc_id": VALID_OID})
        assert resp.status_code == 200
        body = resp.get_json()
        assert 0.0 <= body["data"]["confidence"] <= 1.0

    def test_risk_score_clamped(self, client):
        c, mock_col = client
        self._setup_doc(mock_col)
        from models.nlp_models import RiskResult
        mock_result = RiskResult(risk_level="high", flags=[], score=2.5)
        with patch("routes.ai.nlp_service.risk_check", return_value=mock_result):
            resp = c.post("/api/ai/risk-check", json={"doc_id": VALID_OID})
        assert resp.status_code == 200
        body = resp.get_json()
        assert 0.0 <= body["data"]["score"] <= 1.0

    def test_risk_level_validated(self, client):
        c, mock_col = client
        self._setup_doc(mock_col)
        from models.nlp_models import RiskResult
        mock_result = RiskResult(risk_level="critical", flags=[], score=0.5)
        with patch("routes.ai.nlp_service.risk_check", return_value=mock_result):
            resp = c.post("/api/ai/risk-check", json={"doc_id": VALID_OID})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["risk_level"] in {"low", "medium", "high"}


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------

class TestMissingRequiredFields:
    """Endpoints that require a query/question must return 400 when missing."""

    def test_search_missing_query(self, client):
        c, mock_col = client
        doc = _make_doc(VALID_OID)
        mock_col.find_one.return_value = doc
        resp = c.post("/api/ai/search", json={"doc_id": VALID_OID})
        assert resp.status_code == 400

    def test_chat_missing_question(self, client):
        c, mock_col = client
        doc = _make_doc(VALID_OID)
        mock_col.find_one.return_value = doc
        resp = c.post("/api/ai/chat", json={"doc_id": VALID_OID})
        assert resp.status_code == 400

    def test_cross_search_missing_query(self, client):
        c, _ = client
        resp = c.post("/api/ai/cross-search", json={"doc_ids": [VALID_OID]})
        assert resp.status_code == 400
