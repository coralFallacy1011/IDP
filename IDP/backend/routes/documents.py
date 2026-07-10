from flask import Blueprint, request, jsonify
from models.document import documents
from services.generator import generate_document
from services.validator import validate
from services.export import text_to_pdf
import datetime, os

doc_bp = Blueprint("docs", __name__)

@doc_bp.route("/create", methods=["POST"])
def create_doc():
    payload = request.json
    doc_type = payload["doc_type"]
    fields = payload["fields"]

    ok, msg = validate(doc_type, fields)
    if not ok:
        return jsonify({"error": msg}), 400

    content = generate_document(doc_type, fields)

    os.makedirs("files", exist_ok=True)
    filename = f"{doc_type}_{int(datetime.datetime.now().timestamp())}.pdf"
    path = f"files/{filename}"

    text_to_pdf(content, path)

    result = documents.insert_one({
        "doc_type": doc_type,
        "fields": fields,
        "content": content,
        "file_url": path,
        "created_at": datetime.datetime.utcnow()
    })

    return jsonify({
        "id": str(result.inserted_id),
        "content": content,
        "file_url": path
    })