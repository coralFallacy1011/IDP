"""Blockchain REST API.

Endpoints
---------
POST /api/blockchain/register
    Body: {"document_id": "...", "document_hash": "..."}
    Registers the hash on-chain.

POST /api/blockchain/verify
    Body: {"document_id": "..."}
    Looks up the stored OCR text in MongoDB, recomputes its SHA-256, then
    queries the contract.  Returns {"status": "authentic"} or {"status": "tampered"}.

GET  /api/blockchain/document/<doc_id>
    Returns the on-chain record for doc_id.
"""

from flask import Blueprint, request, jsonify
from bson import ObjectId
from flask import g

from models.document import db
from services.blockchain_service import (
    register_document,
    verify_document,
    get_registered_record,
    _sha256,
)
from services.audit_service import log_action

blockchain_bp = Blueprint("blockchain", __name__)


@blockchain_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    document_id   = data.get("document_id")
    document_hash = data.get("document_hash")
    if not document_id or not document_hash:
        return jsonify({"error": "document_id and document_hash required"}), 400
    try:
        res = register_document(document_id, document_hash)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(res)


@blockchain_bp.route("/verify", methods=["POST"])
def verify():
    data = request.get_json() or {}
    document_id = data.get("document_id")
    if not document_id:
        return jsonify({"error": "document_id required"}), 400

    # Caller may supply document_hash directly…
    document_hash = data.get("document_hash")

    if not document_hash:
        # … or we fetch the OCR text from MongoDB and recompute
        try:
            oid = ObjectId(document_id)
        except Exception:
            return jsonify({"error": "invalid document_id format (expected MongoDB ObjectId)"}), 400

        doc = db["documents"].find_one({"_id": oid})
        if not doc:
            return jsonify({"error": "document not found in database"}), 404

        # Prefer the clean OCR text used at registration time
        ocr = doc.get("ocr_text", {})
        text = ocr.get("clean") or ocr.get("raw") or ""
        if not text:
            return jsonify({"error": "no OCR text stored for this document"}), 400

        document_hash = _sha256(text)

    # Retrieve the document_id key used at registration (stored in blockchain sub-doc)
    doc_bc_id = document_id   # default: caller's ID
    if db is not None:
        try:
            oid = ObjectId(document_id)
            doc = db["documents"].find_one({"_id": oid}, {"blockchain": 1})
            if doc and doc.get("blockchain", {}).get("document_id"):
                doc_bc_id = doc["blockchain"]["document_id"]
        except Exception:
            pass

    ok = verify_document(doc_bc_id, document_hash)

    # Audit: verify_document event
    try:
        u = getattr(g, "current_user", {})
        log_action(user=u.get("name","unknown"), role=u.get("role","unknown"),
                   action="verify_document", document_id=document_id)
    except Exception:
        pass

    return jsonify({
        "document_id":   document_id,
        "document_hash": document_hash,
        "status":        "authentic" if ok else "tampered",
    })


@blockchain_bp.route("/document/<doc_id>", methods=["GET"])
def get_doc(doc_id: str):
    rec = get_registered_record(doc_id)
    if not rec:
        return jsonify({"error": "not found on blockchain"}), 404

    # Audit: view_document event
    try:
        u = getattr(g, "current_user", {})
        log_action(user=u.get("name","unknown"), role=u.get("role","unknown"),
                   action="view_document", document_id=doc_id)
    except Exception:
        pass

    return jsonify(rec)
