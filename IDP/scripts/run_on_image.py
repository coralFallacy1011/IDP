"""End-to-end pipeline test.

Usage:
    python scripts/run_on_image.py [<image_path>]

If image_path is omitted, uses the first FUNSD test image.
"""
from __future__ import annotations

import datetime
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from services.preprocess import preprocess_image
from services.ocr_engine import extract_text_and_boxes, legal_keyword_correction
from services.classification_service import classify
from services.metadata_service import extract_metadata
from services.summarization_service import summarize
from services.blockchain_service import register_document, verify_document, _sha256
from models.document import db


def run_pipeline(image_path: str):
    print("=" * 60)
    print(f"IMAGE : {image_path}")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Preprocess
    # ------------------------------------------------------------------
    clean_path = None
    try:
        clean_path = preprocess_image(image_path, grayscale_only=True)
        print(f"[✓] Preprocess → {clean_path}")
    except Exception as e:
        print(f"[!] Preprocess failed (using original): {e}")
        clean_path = image_path

    src = clean_path if clean_path else image_path

    # ------------------------------------------------------------------
    # 2. OCR
    # ------------------------------------------------------------------
    raw_text, boxes = extract_text_and_boxes(src, psm=6, lang="eng", min_conf=45)
    clean_text_raw, _ = extract_text_and_boxes(src, psm=6, lang="eng", strict=True)
    clean_text = legal_keyword_correction(clean_text_raw)
    print(f"[✓] OCR — raw chars: {len(raw_text)}, clean chars: {len(clean_text)}")

    # ------------------------------------------------------------------
    # 3. Classification
    # ------------------------------------------------------------------
    classification = classify(clean_text)
    print(f"[✓] Classification → {classification}")

    # ------------------------------------------------------------------
    # 4. Metadata
    # ------------------------------------------------------------------
    metadata = extract_metadata(clean_text)
    print(f"[✓] Metadata → {metadata}")

    # ------------------------------------------------------------------
    # 5. Summarization
    # ------------------------------------------------------------------
    summary = summarize(clean_text)
    print(f"[✓] Summary → {summary.get('short_description', summary.get('summary', ''))[:120]}")

    # ------------------------------------------------------------------
    # 6. MongoDB insert (get stable ObjectId first)
    # ------------------------------------------------------------------
    initial_doc = {
        "filename":    os.path.basename(image_path),
        "upload_time": datetime.datetime.utcnow(),
        "ocr_text":    {"raw": raw_text, "clean": clean_text, "boxes": boxes},
        "classification": classification,
        "metadata":    metadata,
        "summary":     summary,
        "source":      "run_on_image",
        "blockchain":  {"document_hash": "", "transaction_hash": "", "registered": False},
    }
    insert_result = db["documents"].insert_one(initial_doc)
    document_id   = str(insert_result.inserted_id)
    print(f"[✓] MongoDB insert → _id = {document_id}")

    # ------------------------------------------------------------------
    # 7. SHA-256 + Blockchain registration
    # ------------------------------------------------------------------
    doc_hash = _sha256(clean_text)
    print(f"[✓] SHA-256 → {doc_hash}")

    bc = None
    try:
        bc = register_document(document_id, doc_hash)
        print(f"[✓] Blockchain register → tx: {bc['transaction_hash']} (block {bc.get('block_number')})")
    except Exception as exc:
        print(f"[✗] Blockchain registration failed: {exc}")
        bc = {"registered": False, "transaction_hash": "", "document_hash": doc_hash}

    # ------------------------------------------------------------------
    # 8. Update MongoDB with blockchain result
    # ------------------------------------------------------------------
    blockchain_data = {
        "document_id":    document_id,
        "document_hash":  doc_hash,
        "transaction_hash": bc.get("transaction_hash", ""),
        "registered":     bc.get("registered", False),
        "block_number":   bc.get("block_number"),
    }
    db["documents"].update_one(
        {"_id": insert_result.inserted_id},
        {"$set": {"blockchain": blockchain_data}},
    )
    print(f"[✓] MongoDB updated with blockchain data")

    # ------------------------------------------------------------------
    # 9. Verify
    # ------------------------------------------------------------------
    if bc.get("registered"):
        verified = verify_document(document_id, doc_hash)
        print(f"[{'✓' if verified else '✗'}] Blockchain verify → {'authentic' if verified else 'tampered'}")
    else:
        verified = False
        print("[!] Skipping verification (registration failed)")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("PIPELINE RESULT")
    print("=" * 60)
    print(f"  document_id       : {document_id}")
    print(f"  document_type     : {classification.get('document_type')}")
    print(f"  document_hash     : {doc_hash}")
    print(f"  transaction_hash  : {bc.get('transaction_hash', 'N/A')}")
    print(f"  registered        : {bc.get('registered', False)}")
    print(f"  verified          : {verified}")
    print("=" * 60)

    # Confirm MongoDB record
    stored = db["documents"].find_one({"_id": insert_result.inserted_id})
    print("\nMONGODB DOCUMENT (blockchain field):")
    import json
    bc_field = stored.get("blockchain", {}) if stored else {}
    print(json.dumps(bc_field, indent=2, default=str))

    return document_id, bc.get("registered", False), verified


if __name__ == "__main__":
    if len(sys.argv) < 2:
        default = Path(__file__).resolve().parents[1] / "FUNSD" / "testing_data" / "images" / "82092117.png"
        img = str(default)
    else:
        img = sys.argv[1]

    if not os.path.exists(img):
        print(f"Image not found: {img}")
        sys.exit(1)

    doc_id, registered, verified = run_pipeline(img)

    if registered and verified:
        print("\nFINAL STATUS: PASS")
        sys.exit(0)
    else:
        print("\nFINAL STATUS: FAIL")
        sys.exit(1)
