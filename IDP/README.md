# IDP — Intelligent Document Processing (Legal & Forms NLP)

This repository implements an Intelligent Document Processing (IDP) pipeline aimed at legal and form-like documents (e.g., FUNSD, FIR, legal contracts). It couples OCR, layout parsing, NLP (NER/classification/chunking), dense embedding retrieval (FAISS), and template-based export (Jinja2) to extract structured information and produce human-readable outputs.

This README is intentionally detailed and LLM-friendly: it lists files, expected data shapes, configuration knobs, concrete example payloads, and developer guidance so an LLM (or a developer) can reason about, extend, or call into the code base.

Contents
- Quick summary
- File-by-file summary (key files)
- Data shapes and JSON examples (OCR output, FUNSD annotation, FAISS meta)
- Environment variables & configuration
- How to run locally (dev) + commands
- API examples (sample requests and responses)
- How to run tests
- Rebuilding FAISS index
- Developer notes, conventions, and recommended follow-ups

Quick summary
- Purpose: convert scanned images/PDFs into structured data (fields, entities, relations), support retrieval & RAG, and export templated documents.
- Primary language: Python (Flask web app + services). Models and heavy computation abstracted behind `backend/services/`.

File-by-file summary (key files and what to inspect first)

Top-level
- `requirements.txt` — pinned Python packages. Use as the single source for dependency install.

`backend/`
- `app.py`
  - Flask application entrypoint. Registers blueprints from `routes/` and configures app-level settings.
  - Look for `if __name__ == "__main__"` for how the server is started.

- `routes/` (HTTP endpoints)
  - `routes/ai.py` — AI helpers and RAG endpoints. Orchestrates `services/rag_service.py` and `services/generator.py`.
  - `routes/documents.py` — handles document upload, metadata queries, and starting pipeline runs (preprocess → OCR → parse → NLP).
  - `routes/ocr.py` — trigger OCR runs or retrieve previously computed OCR results.

- `services/` (core business logic)
  - `ocr_engine.py` — adapter/wrapper around chosen OCR backend (e.g., pytesseract, EasyOCR, or cloud). Key responsibilities:
    - Accept image or PDF pages, return token-level outputs: text, bbox, confidence.
    - Unified output shape for downstream consumers.
  - `preprocess.py` — image cleaning (deskew, denoise), normalization, caching to `preprocessed_cache/`.
  - `parser.py` — groups tokens into lines, blocks, and candidate key-value pairs (forms). Also computes heuristics for nearby tokens.
  - `nlp_service.py` — applies NER, classification, and chunking models defined in `models/nlp_models.py`.
  - `embedding_service.py` — computes dense embeddings for chunks, persists/retrieves from FAISS. Contains batching and normalization logic.
  - `rag_service.py` — query embedding → FAISS retrieval → context assembly → generator call.
  - `validator.py` — output validators and structure checks.
  - `evaluator.py`, `funsd_gt.py` — evaluation of model outputs against FUNSD ground truth; produces CSV & JSON reports in `reports/`.
  - `export.py`, `generator.py` — template rendering using `templates/`; generator may call LLM or local text-generation models.

- `models/`
  - `document.py` — domain model: Document, Page, Token, Block classes; helper methods for conversions to/from JSON.
  - `nlp_models.py` — wrappers that load tokenizers and models for NER/classification (can reference either HF transformers or lightweight classifiers).

- `faiss_index/` — pre-built FAISS index files (`*.index`) and metadata JSONs (`*.meta.json`). Each metadata JSON maps index ids → {doc_id, chunk_id, text, page_num, bbox}.

- `templates/` — Jinja2 templates for final export (affidavit, contract, rental_agreement, etc.). `export.py` wires document fields into these templates.

- `reports/` — output reports from evaluations: `funsd_eval_results.csv`, `funsd_eval_summary.json`.

- `tests/` — pytest unit & integration tests. Look at `conftest.py` for fixtures and mocking strategies.

Data shapes and JSON examples

1) OCR token output (unified schema used across services)

Example:

{
  "page_num": 0,
  "tokens": [
    {
      "id": "t0",
      "text": "Invoice",
      "confidence": 0.98,
      "bbox": [100, 50, 240, 90]  # [x0, y0, x1, y1]
    },
    {
      "id": "t1",
      "text": "Date:",
      "confidence": 0.95,
      "bbox": [300, 200, 360, 220]
    }
  ]
}

Notes:
- Coordinates are relative to the page image (pixel units). Normalization to [0,1] may be done by `preprocess.py` depending on downstream needs.

2) FUNSD annotation format (example simplified)

{
  "form": [
    {
      "id": 0,
      "words": ["Invoice"],
      "bbox": [100,50,240,90],
      "label": "header"
    },
    {
      "id": 1,
      "words": ["Date:", "2023-01-01"],
      "bbox": [300,190,430,220],
      "label": "question/answer"
    }
  ]
}

3) FAISS `.meta.json` format (expected)

[
  {
    "index_id": 0,
    "doc_id": "doc-001",
    "chunk_id": "doc-001-chunk-0",
    "text": "terms and conditions...",
    "page_num": 1,
    "bbox": [0,0,100,100]
  },
  {
    "index_id": 1,
    "doc_id": "doc-002",
    "chunk_id": "doc-002-chunk-0",
    "text": "notice of ...",
    "page_num": 2,
    "bbox": [10,20,110,120]
  }
]

Environment variables & configuration (common keys)

These are likely referenced across `backend/services/*`. Check for exact names by searching for `os.environ`.

- `OCR_BACKEND` — e.g., `tesseract`, `easyocr`, `cloud`.
- `EMBEDDING_MODEL` — name of the embedding model (HF model id or local model alias).
- `GENERATOR_MODEL` — text generation model name (LLM used for generator or RAG augmentation).
- `FAISS_INDEX_DIR` — directory to store/read FAISS index files (default: `backend/faiss_index/`).
- `CACHE_DIR` — directory for preprocessed images (default: `backend/preprocessed_cache/`).
- `DEBUG` — `1` or `0` to toggle Flask debug mode.

How to run locally (development)

1) Create and activate a virtualenv, install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Start Flask server (from `backend/` folder) — example

```bash
cd backend
export FLASK_APP=app.py
export FLASK_ENV=development
python app.py
# or: flask run --host=0.0.0.0 --port=5000
```

3) Visit endpoints or call with curl/postman (examples below).

API examples (sample requests and expected responses)

1) Upload a document

POST /documents/upload
Content-Type: multipart/form-data

Form fields: `file` (image/pdf), optional `metadata` JSON

Success response (JSON):

{
  "doc_id": "doc-001",
  "status": "uploaded",
  "pages": 2
}

2) Trigger OCR for an uploaded document

POST /ocr/run
Body (JSON): { "doc_id": "doc-001" }

Response: job id and status. The OCR result JSON will be stored and available via `GET /documents/{doc_id}`.

3) Query the AI/RAG endpoint

POST /ai/query
Body (JSON):

{
  "query": "What is the date on the invoice?",
  "doc_id": "doc-001",
  "top_k": 5
}

Response (example):

{
  "answer": "2023-01-01",
  "source_chunks": [
    {"doc_id":"doc-001","chunk_id":"...","score":0.84},
    ...
  ]
}

How to run tests

From repo root (after creating virtualenv and installing dependencies):

```bash
pytest -q
```

If tests require heavy models or external services, use mocks or set `TEST_MODE=1` to use small local models (see `backend/tests/conftest.py`).

Rebuilding a FAISS index (developer steps)

- Walk all source documents that should be indexed (PDFs/text files) and chunk them into retrieval-sized passages.
- Use `embedding_service.py` to compute embeddings for each chunk and write the vectors to FAISS index.
- Also write a `.meta.json` mapping `index_id` → metadata (doc_id, chunk_id, page_num, bbox, original_text).

Example pseudo-steps (scripts/ or Makefile target recommended):

```bash
# 1. python backend/services/embedding_service.py --build-index --input docs/ --out faiss_index/my.index
# 2. python backend/services/embedding_service.py --save-meta faiss_index/my.meta.json
```

Developer notes, conventions & recommended follow-ups

- Data shapes: preserve token-level schema (id, text, confidence, bbox). Add adapter functions in `models/document.py` if you integrate other OCR outputs.
- When adding or modifying models, provide a small sample and add/update tests in `backend/tests/`.
- Use `preprocessed_cache/` for expensive pre-processing results to avoid re-running image transforms across dev cycles.
- Add module-level docstrings to `services/*` and `models/*` to enable programmatic extraction of interfaces for tools and LLMs.

Suggested small, high-value follow-ups (I can implement these if you want):

1. Add a `backend/README.md` that extracts function/class signatures from `models/document.py` and `services/embedding_service.py` (make the README even more machine-actionable).
2. Add sample requests (curl and JSON files) under `docs/samples/` for each major endpoint.
3. Create a small `scripts/rebuild_faiss.py` to automate index building and metadata writing.
4. Add a CI job to run `pytest` and a linter (flake8/ruff).

If you want me to proceed with any of the follow-ups, tell me which and I will add the files and tests. If you prefer more detail inside the README about specific functions or class method signatures, I can parse and include them automatically.

---
Completion note: README.md updated with expanded, LLM-focused documentation and examples.
