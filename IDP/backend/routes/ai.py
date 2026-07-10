"""AI API blueprint — Legal NLP/LLM Module.

Exposes seven endpoints under ``/api/ai``:

Phase 1 (core NLP):
  POST /classify    — document-type classification
  POST /extract     — named-entity extraction + clause detection
  POST /summarize   — abstractive summarisation
  POST /risk-check  — risk / anomaly detection

Phase 2 (vector search + RAG):
  POST /search       — single-document semantic similarity search
  POST /chat         — retrieval-augmented generation chatbot
  POST /cross-search — cross-document semantic search

All endpoints return a consistent JSON envelope::

    {"ok": bool, "data": ..., "cached": bool}

Cached results are returned when the ``nlp`` sub-document already contains
the requested key and the caller has not set ``force=true`` in the request
body.

Every ``nlp`` sub-document write includes ``processed_at`` (UTC datetime),
``model`` (string identifier), and ``lang`` (resolved language code).
"""

from __future__ import annotations

import datetime
import logging

from bson import ObjectId
from flask import Blueprint, jsonify, request

# bson.errors.InvalidId is available in pymongo's bundled bson.
# The standalone 'bson' package exposes it at bson.objectid.InvalidId.
# We try both and fall back to catching Exception broadly.
try:
    from bson.errors import InvalidId as _BsonInvalidId
except ImportError:
    try:
        from bson.objectid import InvalidId as _BsonInvalidId  # type: ignore[no-redef]
    except ImportError:
        _BsonInvalidId = Exception  # type: ignore[assignment,misc]

from models.document import db
import services.nlp_service as nlp_service
import services.embedding_service as embedding_service
import services.rag_service as rag_service

logger = logging.getLogger(__name__)

ai_bp = Blueprint("ai", __name__)

# ---------------------------------------------------------------------------
# Model identifier strings (12.12)
# ---------------------------------------------------------------------------
_MODEL_CLASSIFY  = "InLegalBERT"
_MODEL_EXTRACT   = "Legal-BERT-NER"
_MODEL_SUMMARIZE = "BART-large-CNN"
_MODEL_RISK      = "rule-based"


# ---------------------------------------------------------------------------
# Helper: fetch document from MongoDB (12.2)
# ---------------------------------------------------------------------------

def _get_document(doc_id_str: str):
    """Validate *doc_id_str* as a MongoDB ObjectId and fetch the document.

    Returns
    -------
    tuple[dict, None]
        ``(doc, None)`` on success.
    tuple[None, flask.Response]
        ``(None, error_response)`` on failure (400 or 404).
    """
    try:
        oid = ObjectId(doc_id_str)
    except Exception:
        return None, (jsonify({"ok": False, "error": "invalid_id",
                               "detail": f"'{doc_id_str}' is not a valid ObjectId"}), 400)

    # OCR pipeline stores documents in db["documents"] collection
    doc = db["documents"].find_one({"_id": oid})
    if doc is None:
        return None, (jsonify({"ok": False, "error": "not_found",
                               "detail": f"Document '{doc_id_str}' not found"}), 404)

    return doc, None


# ---------------------------------------------------------------------------
# Helper: check NLP cache (12.3)
# ---------------------------------------------------------------------------

def _check_cache(doc: dict, nlp_key: str, force: bool):
    """Return a cached-hit response if the NLP result already exists.

    Parameters
    ----------
    doc:
        MongoDB document dict.
    nlp_key:
        Key inside ``doc["nlp"]`` to check (e.g. ``"classification"``).
    force:
        When ``True``, bypass the cache and return ``None``.

    Returns
    -------
    flask.Response or None
        A JSON response with ``cached=True`` if a cache hit is found and
        *force* is falsy; ``None`` otherwise.
    """
    if force:
        return None
    nlp = doc.get("nlp") or {}
    cached_data = nlp.get(nlp_key)
    if cached_data is not None:
        return jsonify({"ok": True, "data": cached_data, "cached": True})
    return None


# ---------------------------------------------------------------------------
# Helper: resolve language from document (16.8 / 12.12)
# ---------------------------------------------------------------------------

def _resolve_lang(doc: dict) -> str:
    """Return the best available language code from *doc*."""
    return (doc.get("lang_detected") or doc.get("lang") or "eng").strip() or "eng"


def _get_clean_text(doc: dict) -> str:
    """Extract clean OCR text from the document.

    OCR pipeline stores text under ``ocr_text.clean``; falls back to
    ``ocr_text.raw``, then top-level ``clean_text`` or ``raw_text``.
    """
    ocr = doc.get("ocr_text") or {}
    return (
        ocr.get("clean")
        or ocr.get("raw")
        or doc.get("clean_text")
        or doc.get("raw_text")
        or ""
    )


# ---------------------------------------------------------------------------
# POST /classify (12.4)
# ---------------------------------------------------------------------------

@ai_bp.route("/classify", methods=["POST"])
def classify():
    """Classify a document into a legal document type.

    Request body (JSON):
        doc_id (str): MongoDB ObjectId of the document.
        force  (bool, optional): bypass cache when ``true``.

    Returns:
        JSON envelope with ``nlp.classification`` sub-document.
    """
    body = request.get_json(silent=True) or {}
    doc_id_str = body.get("doc_id", "")
    force = bool(body.get("force", False))

    doc, err = _get_document(doc_id_str)
    if err:
        return err

    cached = _check_cache(doc, "classification", force)
    if cached:
        return cached

    lang = _resolve_lang(doc)
    text = _get_clean_text(doc)
    fields = doc.get("fields", {})

    result = nlp_service.classify(text, fields, lang=lang)

    # Validation (12.11)
    confidence = float(result.confidence)
    if not (0.0 <= confidence <= 1.0):
        confidence = max(0.0, min(1.0, confidence))

    nlp_doc = {
        **result.to_dict(),
        "confidence":    confidence,
        "model":         _MODEL_CLASSIFY,
        "processed_at":  datetime.datetime.utcnow(),
        "lang":          lang,
    }

    db["documents"].update_one(
        {"_id": doc["_id"]},
        {"$set": {"nlp.classification": nlp_doc}},
    )

    return jsonify({"ok": True, "data": nlp_doc, "cached": False})


# ---------------------------------------------------------------------------
# POST /extract (12.5)
# ---------------------------------------------------------------------------

@ai_bp.route("/extract", methods=["POST"])
def extract():
    """Extract named entities and detect legal clauses.

    Request body (JSON):
        doc_id (str): MongoDB ObjectId of the document.
        force  (bool, optional): bypass cache when ``true``.

    Returns:
        JSON envelope with ``nlp.entities`` and ``nlp.clauses`` sub-documents.
    """
    body = request.get_json(silent=True) or {}
    doc_id_str = body.get("doc_id", "")
    force = bool(body.get("force", False))

    doc, err = _get_document(doc_id_str)
    if err:
        return err

    # Cache check: both entities and clauses must be present
    if not force:
        nlp = doc.get("nlp") or {}
        if nlp.get("entities") is not None and nlp.get("clauses") is not None:
            return jsonify({
                "ok": True,
                "data": {"entities": nlp["entities"], "clauses": nlp["clauses"]},
                "cached": True,
            })

    lang = _resolve_lang(doc)
    text = _get_clean_text(doc)
    fields = doc.get("fields", {})

    entity_result = nlp_service.extract_entities(text, existing_fields=fields, lang=lang)
    clause_result = nlp_service.detect_clauses(text, lang=lang)

    now = datetime.datetime.utcnow()

    entities_doc = {
        **entity_result.to_dict(),
        "model":        _MODEL_EXTRACT,
        "processed_at": now,
        "lang":         lang,
    }
    clauses_doc = {
        **clause_result.to_dict(),
        "processed_at": now,
        "lang":         lang,
    }

    db["documents"].update_one(
        {"_id": doc["_id"]},
        {"$set": {
            "nlp.entities": entities_doc,
            "nlp.clauses":  clauses_doc,
        }},
    )

    return jsonify({
        "ok": True,
        "data": {"entities": entities_doc, "clauses": clauses_doc},
        "cached": False,
    })


# ---------------------------------------------------------------------------
# POST /summarize (12.6)
# ---------------------------------------------------------------------------

@ai_bp.route("/summarize", methods=["POST"])
def summarize():
    """Produce an abstractive summary of a document.

    Request body (JSON):
        doc_id (str): MongoDB ObjectId of the document.
        force  (bool, optional): bypass cache when ``true``.

    Returns:
        JSON envelope with ``nlp.summary`` sub-document.
    """
    body = request.get_json(silent=True) or {}
    doc_id_str = body.get("doc_id", "")
    force = bool(body.get("force", False))

    doc, err = _get_document(doc_id_str)
    if err:
        return err

    cached = _check_cache(doc, "summary", force)
    if cached:
        return cached

    lang = _resolve_lang(doc)
    text = _get_clean_text(doc)

    result = nlp_service.summarize(text, lang=lang)

    nlp_doc = {
        "text":              result.summary,
        "summary":           result.summary,
        "word_count":        result.word_count,
        "compression_ratio": result.compression_ratio,
        "model":             _MODEL_SUMMARIZE,
        "processed_at":      datetime.datetime.utcnow(),
        "lang":              lang,
    }

    db["documents"].update_one(
        {"_id": doc["_id"]},
        {"$set": {"nlp.summary": nlp_doc}},
    )

    return jsonify({"ok": True, "data": nlp_doc, "cached": False})


# ---------------------------------------------------------------------------
# POST /risk-check (12.7)
# ---------------------------------------------------------------------------

@ai_bp.route("/risk-check", methods=["POST"])
def risk_check():
    """Assess risk and anomalies in a document.

    Uses cached ``doc_type`` and ``clauses_found`` from ``nlp.classification``
    and ``nlp.clauses`` if available.

    Request body (JSON):
        doc_id (str): MongoDB ObjectId of the document.
        force  (bool, optional): bypass cache when ``true``.

    Returns:
        JSON envelope with ``nlp.risk`` sub-document.
    """
    body = request.get_json(silent=True) or {}
    doc_id_str = body.get("doc_id", "")
    force = bool(body.get("force", False))

    doc, err = _get_document(doc_id_str)
    if err:
        return err

    cached = _check_cache(doc, "risk", force)
    if cached:
        return cached

    lang = _resolve_lang(doc)
    text = _get_clean_text(doc)
    fields = doc.get("fields", {})
    nlp = doc.get("nlp") or {}

    # Use cached classification / clause data when available (12.7)
    doc_type = (nlp.get("classification") or {}).get("doc_type", "unknown")
    clauses_found = (nlp.get("clauses") or {}).get("clauses_found", [])

    result = nlp_service.risk_check(text, fields, doc_type, clauses_found)

    # Validation (12.11)
    score = float(result.score)
    if not (0.0 <= score <= 1.0):
        score = max(0.0, min(1.0, score))

    risk_level = result.risk_level
    if risk_level not in {"low", "medium", "high"}:
        risk_level = "low"

    nlp_doc = {
        "risk_level":   risk_level,
        "score":        score,
        "flags":        [f.to_dict() for f in result.flags],
        "processed_at": datetime.datetime.utcnow(),
        "lang":         lang,
    }

    db["documents"].update_one(
        {"_id": doc["_id"]},
        {"$set": {"nlp.risk": nlp_doc}},
    )

    return jsonify({"ok": True, "data": nlp_doc, "cached": False})


# ---------------------------------------------------------------------------
# POST /search (12.8)
# ---------------------------------------------------------------------------

@ai_bp.route("/search", methods=["POST"])
def search():
    """Semantic similarity search within a single document.

    Request body (JSON):
        doc_id (str): MongoDB ObjectId of the document.
        query  (str): Natural language query.
        top_k  (int, optional): Number of results to return (default 4).

    Returns:
        JSON envelope with a list of ``ChunkResult`` dicts.
    """
    body = request.get_json(silent=True) or {}
    doc_id_str = body.get("doc_id", "")
    query = body.get("query", "")
    top_k = int(body.get("top_k", 4))

    if not query:
        return jsonify({"ok": False, "error": "missing_query",
                        "detail": "'query' is required"}), 400

    doc, err = _get_document(doc_id_str)
    if err:
        return err

    # Auto-build FAISS index from document text if it doesn't exist yet
    text = _get_clean_text(doc)
    if text:
        embedding_service.get_or_create_index(doc_id_str, text)

    results = embedding_service.similarity_search(query, doc_id_str, k=top_k)
    data = [r.to_dict() for r in results]

    return jsonify({"ok": True, "data": data, "cached": False})


# ---------------------------------------------------------------------------
# POST /chat (12.9)
# ---------------------------------------------------------------------------

@ai_bp.route("/chat", methods=["POST"])
def chat():
    """Retrieval-augmented generation chatbot for a document.

    Request body (JSON):
        doc_id   (str): MongoDB ObjectId of the document.
        question (str): Natural language question.

    Returns:
        JSON envelope with a ``RAGResult`` dict.
    """
    body = request.get_json(silent=True) or {}
    doc_id_str = body.get("doc_id", "")
    question = body.get("question", "")

    if not question:
        return jsonify({"ok": False, "error": "missing_question",
                        "detail": "'question' is required"}), 400

    doc, err = _get_document(doc_id_str)
    if err:
        return err

    # Ensure FAISS index is built for this document before RAG
    text = _get_clean_text(doc)
    if text:
        embedding_service.get_or_create_index(doc_id_str, text)

    result = rag_service.answer_question(question, doc_id_str)
    data = result.to_dict()

    return jsonify({"ok": True, "data": data, "cached": False})


# ---------------------------------------------------------------------------
# POST /cross-search (12.10)
# ---------------------------------------------------------------------------

@ai_bp.route("/cross-search", methods=["POST"])
def cross_search():
    """Semantic search across multiple documents.

    Request body (JSON):
        query   (str): Natural language query.
        doc_ids (list[str], optional): Document IDs to search.
            If omitted, searches all indexed documents.

    Returns:
        JSON envelope with a list of ``ChunkResult`` dicts.
    """
    body = request.get_json(silent=True) or {}
    query = body.get("query", "")
    doc_ids = body.get("doc_ids") or []

    if not query:
        return jsonify({"ok": False, "error": "missing_query",
                        "detail": "'query' is required"}), 400

    results = embedding_service.cross_document_search(query, doc_ids)
    data = [r.to_dict() for r in results]

    return jsonify({"ok": True, "data": data, "cached": False})
