"""OCR API route.

POST /api/ocr/scan
  Accepts a multipart file upload (PDF, PNG, JPEG, TIFF).
  Optional form field: lang (Tesseract language code, default "eng").
  For multilingual docs: lang=eng+hin, lang=hin, lang=tam, etc.

Pipeline
--------
  Upload
    → Preprocess
    → OCR (raw + clean)
    → Language Detection
    → Field Extraction
    → Classification (zero-shot)
    → Metadata Extraction (spaCy + regex)
    → Summarization
    → SHA-256 hash of clean_text
    → MongoDB insert  (yields document_id = ObjectId)
    → Blockchain registration  (document_id = str(ObjectId))
    → MongoDB update with blockchain result

Response JSON:
  document_id       — MongoDB _id (string)
  document_type     — classified document type
  summary           — short description
  metadata          — extracted metadata
  blockchain        — {document_hash, transaction_hash, registered}
"""

from __future__ import annotations

import datetime
import os
import tempfile

from bson import ObjectId
from flask import Blueprint, jsonify, request

from models.document import db
from services.ocr_engine import (
    detect_language_hint,
    extract_text_and_boxes,
    legal_keyword_correction,
)
from services.parser import parse_fields
from services.preprocess import preprocess_image
from services.classification_service import classify as classify_document
from services.metadata_service import extract_metadata
from services.summarization_service import summarize as summarize_document
from services.blockchain_service import register_document, _sha256

ocr_bp = Blueprint("ocr", __name__)

UPLOAD = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD, exist_ok=True)


def _pdf_to_images(pdf_path: str) -> list[str]:
    """Convert a PDF to a list of PNG image paths (one per page).

    Uses pdf2image (requires poppler on PATH).
    Returns temp file paths — caller is responsible for cleanup.
    """
    from pdf2image import convert_from_path  # type: ignore
    pages = convert_from_path(pdf_path, dpi=200)
    paths = []
    for i, page in enumerate(pages):
        tmp = tempfile.NamedTemporaryFile(suffix=f"_page{i}.png", delete=False)
        page.save(tmp.name, "PNG")
        paths.append(tmp.name)
    return paths


@ocr_bp.route("/scan", methods=["POST"])
def scan():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    lang: str = request.form.get("lang", "").strip() or "eng"

    path = os.path.join(UPLOAD, f.filename)
    f.save(path)

    # ------------------------------------------------------------------
    # PDF → image conversion
    # ------------------------------------------------------------------
    tmp_image_paths: list[str] = []
    if f.filename.lower().endswith(".pdf"):
        try:
            tmp_image_paths = _pdf_to_images(path)
            path = tmp_image_paths[0]
        except Exception as e:
            return jsonify({"error": f"PDF conversion failed: {e}. "
                            "Install poppler and add it to PATH."}), 500

    # ------------------------------------------------------------------
    # Step 1: Preprocess
    # ------------------------------------------------------------------
    clean_path = None
    try:
        clean_path = preprocess_image(path, grayscale_only=True)
    except Exception:
        clean_path = None

    # ------------------------------------------------------------------
    # Step 2: raw_text
    # ------------------------------------------------------------------
    src = clean_path if clean_path else path
    raw_text, boxes = extract_text_and_boxes(src, psm=6, lang=lang, min_conf=45)
    if len(raw_text.strip()) < 30 and clean_path:
        raw_text, boxes = extract_text_and_boxes(path, psm=6, lang=lang, min_conf=45)

    # ------------------------------------------------------------------
    # Step 3: clean_text
    # ------------------------------------------------------------------
    clean_text_raw, _ = extract_text_and_boxes(src, psm=6, lang=lang, strict=True)
    if len(clean_text_raw.strip()) < 30 and clean_path:
        clean_text_raw, _ = extract_text_and_boxes(path, psm=6, lang=lang, strict=True)
    clean_text = legal_keyword_correction(clean_text_raw, lang=lang)

    # ------------------------------------------------------------------
    # Step 4: Language detection
    # ------------------------------------------------------------------
    lang_detected = detect_language_hint(raw_text) if lang == "eng" else lang

    # ------------------------------------------------------------------
    # Step 5: Field extraction
    # ------------------------------------------------------------------
    fields = parse_fields(clean_text)

    # ------------------------------------------------------------------
    # Step 6: Classification
    # ------------------------------------------------------------------
    try:
        classification = classify_document(clean_text)
    except Exception:
        classification = {"document_type": "Other", "confidence": 0.0}

    # ------------------------------------------------------------------
    # Step 7: Metadata extraction
    # ------------------------------------------------------------------
    try:
        metadata = extract_metadata(clean_text)
    except Exception:
        metadata = {
            "case_number": "", "fir_number": "", "date": "",
            "persons": [], "organizations": [], "addresses": [], "ipc_sections": [],
        }

    # ------------------------------------------------------------------
    # Step 8: Summarization
    # ------------------------------------------------------------------
    try:
        summary = summarize_document(clean_text)
    except Exception:
        summary = {"short_description": "", "summary": clean_text[:2000]}

    # ------------------------------------------------------------------
    # Step 9: Insert initial document into MongoDB to get a stable ObjectId
    # ------------------------------------------------------------------
    initial_doc = {
        "filename":    f.filename,
        "upload_time": datetime.datetime.utcnow(),
        "ocr_text": {
            "raw":   raw_text,
            "clean": clean_text,
            "boxes": boxes,
        },
        "fields":         fields,
        "classification": classification,
        "metadata":       metadata,
        "summary":        summary,
        "lang":           lang,
        "lang_detected":  lang_detected,
        "blockchain":     {"document_hash": "", "transaction_hash": "", "registered": False},
        "original_image_url": f"/api/ocr/file/uploads/{f.filename}",
        "preprocessed_image_url": f"/api/ocr/file/preprocessed/{os.path.basename(clean_path)}" if clean_path else None,
    }
    result      = db["documents"].insert_one(initial_doc)
    document_id = str(result.inserted_id)   # canonical ID used everywhere

    # ------------------------------------------------------------------
    # Step 10: SHA-256 + blockchain registration using the MongoDB ObjectId
    # ------------------------------------------------------------------
    document_hash = _sha256(clean_text)
    blockchain_data: dict = {
        "document_id":    document_id,
        "document_hash":  document_hash,
        "transaction_hash": "",
        "registered":     False,
    }
    try:
        bc_res = register_document(document_id, document_hash)
        blockchain_data.update({
            "transaction_hash": bc_res.get("transaction_hash", ""),
            "registered":       bool(bc_res.get("registered", False)),
            "block_number":     bc_res.get("block_number"),
        })
    except Exception as exc:
        blockchain_data["error"] = str(exc)

    # ------------------------------------------------------------------
    # Step 11: Update MongoDB record with blockchain result
    # ------------------------------------------------------------------
    db["documents"].update_one(
        {"_id": result.inserted_id},
        {"$set": {"blockchain": blockchain_data}},
    )

    # Cleanup temp PDF page images
    for tmp_path in tmp_image_paths:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    return jsonify({
        "document_id":   document_id,
        "document_type": classification.get("document_type", "Other"),
        "summary":       summary.get("short_description", summary.get("summary", "")),
        "metadata":      metadata,
        "blockchain": {
            "document_hash":   document_hash,
            "transaction_hash": blockchain_data.get("transaction_hash", ""),
            "registered":      blockchain_data.get("registered", False),
        },
        "original_image_url": f"/api/ocr/file/uploads/{f.filename}",
        "preprocessed_image_url": f"/api/ocr/file/preprocessed/{os.path.basename(clean_path)}" if clean_path else None,
    })


# ------------------------------------------------------------------
# GET /api/ocr/documents  — list all scanned documents
# ------------------------------------------------------------------

@ocr_bp.route("/documents", methods=["GET"])
def list_documents():
    """Return a paginated list of OCR documents from the database."""
    limit = int(request.args.get("limit", 20))
    skip  = int(request.args.get("skip", 0))
    lang  = request.args.get("lang", "")

    query: dict = {}
    if lang:
        query["lang"] = lang

    total = db["documents"].count_documents(query)
    docs  = list(
        db["documents"]
        .find(query, {
            "_id": 1, "filename": 1, "lang": 1, "lang_detected": 1,
            "upload_time": 1, "fields": 1, "classification": 1, "summary": 1,
            "metadata": 1, "blockchain": 1, "nlp": 1,
        })
        .sort("upload_time", -1)
        .skip(skip)
        .limit(limit)
    )

    data = []
    for doc in docs:
        data.append({
            "id":           str(doc["_id"]),
            "filename":     doc.get("filename", ""),
            "lang":         doc.get("lang", "eng"),
            "lang_detected": doc.get("lang_detected", ""),
            "created_at":   doc.get("upload_time", "").isoformat() if hasattr(doc.get("upload_time", ""), "isoformat") else str(doc.get("upload_time", "")),
            "fields":       doc.get("fields", {}),
            "nlp":          doc.get("nlp"),
        })

    return jsonify({"ok": True, "data": data, "total": total, "skip": skip, "limit": limit})


# ------------------------------------------------------------------
# GET /api/ocr/documents/<doc_id>  — get single OCR document
# ------------------------------------------------------------------

@ocr_bp.route("/documents/<doc_id>", methods=["GET"])
def get_document(doc_id: str):
    """Return a single OCR document by MongoDB ObjectId."""
    try:
        oid = ObjectId(doc_id)
    except Exception:
        return jsonify({"ok": False, "error": "invalid_id"}), 400

    doc = db["documents"].find_one({"_id": oid})
    if not doc:
        return jsonify({"ok": False, "error": "not_found"}), 404

    return jsonify({
        "ok": True,
        "data": {
            "id":            str(doc["_id"]),
            "filename":      doc.get("filename", ""),
            "lang":          doc.get("lang", "eng"),
            "lang_detected": doc.get("lang_detected", ""),
            "created_at":    doc.get("upload_time", "").isoformat() if hasattr(doc.get("upload_time", ""), "isoformat") else str(doc.get("upload_time", "")),
            "fields":        doc.get("fields", {}),
            "clean_text":    (doc.get("ocr_text") or {}).get("clean", ""),
            "nlp":           doc.get("nlp"),
            "metadata":      doc.get("metadata", {}),
            "blockchain":    doc.get("blockchain", {}),
            "original_image_url": doc.get("original_image_url"),
            "preprocessed_image_url": doc.get("preprocessed_image_url"),
        }
    })


# ------------------------------------------------------------------
# DELETE /api/ocr/documents/<doc_id>
# ------------------------------------------------------------------

@ocr_bp.route("/documents/<doc_id>", methods=["DELETE"])
def delete_document(doc_id: str):
    """Delete an OCR document."""
    try:
        oid = ObjectId(doc_id)
    except Exception:
        return jsonify({"ok": False, "error": "invalid_id"}), 400

    result = db["documents"].delete_one({"_id": oid})
    if result.deleted_count == 0:
        return jsonify({"ok": False, "error": "not_found"}), 404

    return jsonify({"ok": True, "deleted": doc_id})


# ------------------------------------------------------------------
# Static file serving endpoints
# ------------------------------------------------------------------

@ocr_bp.route("/file/uploads/<path:filename>", methods=["GET"])
def get_upload_file(filename):
    """Serve uploaded document files using send_from_directory."""
    from flask import send_from_directory
    return send_from_directory(UPLOAD, filename)


@ocr_bp.route("/file/preprocessed/<path:filename>", methods=["GET"])
def get_preprocessed_file(filename):
    """Serve preprocessed cached image files using send_from_directory."""
    from flask import send_from_directory
    from services.preprocess import _CACHE_DIR
    return send_from_directory(_CACHE_DIR, filename)
