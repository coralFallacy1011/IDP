# Implementation Tasks: Legal NLP/LLM Module

## Overview

These tasks implement the Legal NLP/LLM Module on top of the existing OCR pipeline in the Secure Legal Document Management system. Tasks are ordered by dependency: data models and utilities first, then service layer, then API layer, then Phase 2 features, then tests.

---

## Task List

- [x] 1. Set up project structure and install dependencies
  - [x] 1.1 Create the NLP module directory structure (`backend/services/`, `backend/models/`, `backend/routes/` already exist; add `backend/faiss_index/` placeholder and `backend/models/nlp_models.py`)
  - [x] 1.2 Update `IDP/requirements.txt` with all NLP/LLM dependencies: `transformers`, `torch`, `sentence-transformers`, `faiss-cpu`, `langchain`, `langchain-community`, `llama-cpp-python`, `ctransformers`, `bson`, `python-dateutil`, `langdetect` (optional, for more accurate language detection on mixed-script documents); note that `ai4bharat/indic-bert` is downloaded at runtime via HuggingFace and does not require a separate pip package
  - [x] 1.3 Verify existing `backend/models/document.py` MongoDB connection is importable and add the three new indexes (`nlp.classification.doc_type`, `nlp.risk.risk_level`, `created_at`) to the startup sequence

- [x] 2. Implement typed data models (`backend/models/nlp_models.py`)
  - [x] 2.1 Define `ClassificationResult` dataclass with fields `doc_type: str`, `confidence: float`, `all_scores: dict[str, float]`
  - [x] 2.2 Define `EntityExtractionResult` dataclass with fields `persons`, `organisations`, `dates`, `money`, `locations`, `case_numbers` (all `list[str]`), and `raw_entities: list[dict]`
  - [x] 2.3 Define `ClauseDetectionResult` dataclass with fields `clauses_found: list[str]` and `clause_spans: list[dict]`
  - [x] 2.4 Define `SummarizationResult` dataclass with fields `summary: str`, `word_count: int`, `compression_ratio: float`
  - [x] 2.5 Define `RiskFlag` dataclass with fields `category: str`, `description: str`, `severity: str`
  - [x] 2.6 Define `RiskResult` dataclass with fields `risk_level: str`, `flags: list[RiskFlag]`, `score: float`
  - [x] 2.7 Define `ChunkInfo` dataclass with fields `text: str`, `start_char: int`, `end_char: int`, `index: int`
  - [x] 2.8 Define `ChunkResult` dataclass with fields `chunk_text: str`, `doc_id: str`, `chunk_index: int`, `score: float`
  - [x] 2.9 Define `RAGResult` dataclass with fields `answer: str`, `source_chunks: list[ChunkResult]`, `model_used: str`
  - [x] 2.10 Add a `to_dict()` helper method (or use `dataclasses.asdict`) to each dataclass for JSON serialisation

- [x] 3. Implement document chunking utility in `nlp_service.py`
  - [x] 3.1 Create `backend/services/nlp_service.py` with the `chunk_document(text, max_tokens=512, overlap=64)` function that returns `list[ChunkInfo]`
  - [x] 3.2 Implement the sliding-window algorithm: `step = max_tokens - overlap`; iterate with `i += step`; each chunk covers `words[i : i + max_tokens]`
  - [x] 3.3 Compute `start_char` and `end_char` for each chunk by tracking character offsets from the word list
  - [x] 3.4 Ensure `chunks[0].start_char == 0` and that every character in the input is covered by at least one chunk
  - [x] 3.5 Write unit tests for `chunk_document`: verify coverage invariant, overlap invariant, max-size invariant, single-chunk for short text, and `start_char == 0` (validates Properties 11)

- [x] 4. Implement NLP pipeline singleton management in `nlp_service.py`
  - [x] 4.1 Add a module-level `_PIPELINES: dict[str, Any]` dictionary and a `threading.Lock` for thread-safe initialisation
  - [x] 4.2 Implement `get_classification_pipeline()` that lazy-loads `law-ai/InLegalBERT` as a `zero-shot-classification` pipeline and stores it in `_PIPELINES["classify"]`
  - [x] 4.3 Implement `get_ner_pipeline()` that lazy-loads `nlpaueb/legal-bert-base-uncased` as a `token-classification` (NER) pipeline and stores it in `_PIPELINES["ner"]`
  - [x] 4.4 Implement `get_nli_pipeline()` that lazy-loads `cross-encoder/nli-MiniLM2-L6-H768` as a `zero-shot-classification` pipeline and stores it in `_PIPELINES["nli"]`
  - [x] 4.5 Implement `get_summarizer_pipeline()` that lazy-loads `facebook/bart-large-cnn` as a `summarization` pipeline and stores it in `_PIPELINES["summarize"]`
  - [x] 4.6 Wrap each getter in a `try/except` that logs the error and raises a custom `ModelUnavailableError` on failure
  - [x] 4.7 Write a unit test verifying that calling any getter twice returns the same Python object (validates Property 17)

- [x] 5. Implement document classification (`nlp_service.classify`)
  - [x] 5.1 Implement `classify(text: str, fields: dict) -> ClassificationResult` following Algorithm 1 from the design
  - [x] 5.2 Add the short-text guard: return `ClassificationResult("unknown", 0.0, {})` when `len(text) < 20`
  - [x] 5.3 Implement `truncate_to_tokens(text, max_tokens=512)` helper using whitespace splitting as a token approximation
  - [x] 5.4 Implement `apply_field_hints(raw_scores, fields)` that boosts scores based on field presence (e.g., `fir_number` → boost `FIR`; `parties` → boost `contract`/`agreement`)
  - [x] 5.5 Implement score normalisation so `sum(all_scores.values()) ≈ 1.0`
  - [x] 5.6 Wrap the entire function body in `try/except`; on any exception return `ClassificationResult("unknown", 0.0, {})`
  - [x] 5.7 Write property tests for `classify`: scores sum to 1.0, `doc_type` in `LEGAL_DOC_TYPES`, `confidence` in [0.0, 1.0], short-text guard (validates Properties 1, 2)

- [x] 6. Implement named entity extraction (`nlp_service.extract_entities`)
  - [x] 6.1 Implement `extract_entities(text: str, existing_fields: dict = {}) -> EntityExtractionResult` following Algorithm 2
  - [x] 6.2 Split `text` into 512-token chunks with 64-token overlap using `chunk_document`; run NER pipeline on each chunk; aggregate results
  - [x] 6.3 Implement `group_by_label(raw_entities)` to bucket entities by their NER label (`PER`, `ORG`, `DATE`, `MONEY`, `GPE`)
  - [x] 6.4 Implement `deduplicate(entity_list)` that returns a list of unique, non-empty, stripped strings preserving first-occurrence order
  - [x] 6.5 Merge transformer entities with `existing_fields` (regex fields take precedence for `names`, `dates`, `document_ids`, `financial`)
  - [x] 6.6 Wrap the entire function body in `try/except`; on any exception return `EntityExtractionResult` with all lists empty
  - [x] 6.7 Write property tests: entity lists contain only unique non-empty stripped strings; `raw_entities` dicts have all five required keys; `score` in [0.0, 1.0] (validates Properties 3, 4)

- [x] 7. Implement legal clause detection (`nlp_service.detect_clauses`)
  - [x] 7.1 Implement `detect_clauses(text: str) -> ClauseDetectionResult` following Algorithm 3
  - [x] 7.2 Define `LEGAL_CLAUSE_LABELS` constant list with the ten clause labels from the design
  - [x] 7.3 Implement sentence splitting using a simple regex or `nltk.sent_tokenize`; create sliding windows of 3 sentences with step 1
  - [x] 7.4 For each window, run the NLI pipeline against all clause labels; record labels with score ≥ `ENTAILMENT_THRESHOLD` (0.7)
  - [x] 7.5 Store only the best-scoring window per clause label; truncate `text_snippet` to 200 characters
  - [x] 7.6 Wrap the entire function body in `try/except`; on any exception return `ClauseDetectionResult([], [])`
  - [x] 7.7 Write property tests: `clauses_found` labels are all in `LEGAL_CLAUSE_LABELS`; `clause_spans` entries have all three required keys; `text_snippet` ≤ 200 chars (validates Property 5)

- [x] 8. Implement abstractive summarisation (`nlp_service.summarize`)
  - [x] 8.1 Implement `summarize(text: str, max_length: int = 200) -> SummarizationResult` following Algorithm 4
  - [x] 8.2 Add the short-text guard: return input text as summary when `len(text.split()) < 30`
  - [x] 8.3 Implement the direct path for texts ≤ 600 words: single pipeline call with `max_length=200, min_length=50`
  - [x] 8.4 Implement the map-reduce path for texts > 600 words: chunk at 900 tokens / 50 overlap, summarise each chunk (`max_length=150, min_length=30`), concatenate, then summarise the concatenation
  - [x] 8.5 Compute `word_count = len(summary.split())` and `compression_ratio = word_count / max(len(text.split()), 1)`
  - [x] 8.6 Wrap the entire function body in `try/except`; on any exception return the truncated input as summary
  - [x] 8.7 Write property tests: `compression_ratio < 1.0` for valid inputs, `word_count == len(summary.split())`, short-text guard returns input (validates Properties 6, 7)

- [x] 9. Implement risk and anomaly detection (`nlp_service.risk_check`)
  - [x] 9.1 Implement `risk_check(text: str, fields: dict, doc_type: str, clauses_found: list[str]) -> RiskResult` following Algorithm 5
  - [x] 9.2 Define `REQUIRED_CLAUSES_BY_TYPE` and `RISK_WEIGHTS` constants as specified in the design
  - [x] 9.3 Implement Check 1: missing required clauses — compare `clauses_found` against `REQUIRED_CLAUSES_BY_TYPE[doc_type]`
  - [x] 9.4 Implement Check 2: date inconsistency — parse dates from `fields["dates"]` using `python-dateutil`; detect future-before-past ordering
  - [x] 9.5 Implement Check 3: missing party names — flag when `doc_type` in `{contract, agreement, affidavit}` and `len(fields.get("names", [])) < 2`
  - [x] 9.6 Implement Check 4: unusual terms — define a list of unusual legal terms and scan `text` for their presence
  - [x] 9.7 Compute `final_score = min(raw_score, 1.0)` and assign `risk_level` based on thresholds (< 0.25 → low, < 0.60 → medium, ≥ 0.60 → high)
  - [x] 9.8 Wrap the entire function body in `try/except`; on any exception return `RiskResult("low", [], 0.0)`
  - [x] 9.9 Write property tests: `score` in [0.0, 1.0], `risk_level` in valid set, level consistent with score, missing clauses produce flags, risk flags are well-formed (validates Properties 8, 9, 10)

- [x] 10. Implement embedding service (`backend/services/embedding_service.py`)
  - [x] 10.1 Create `backend/services/embedding_service.py` with a module-level `_EMBEDDING_MODEL` singleton
  - [x] 10.2 Implement `get_embedding_model()` that lazy-loads `sentence-transformers/all-MiniLM-L6-v2` and stores it as the singleton
  - [x] 10.3 Implement `embed_text(text: str) -> np.ndarray` that returns a shape-(384,) L2-normalised embedding
  - [x] 10.4 Implement `embed_chunks(chunks: list[str]) -> np.ndarray` that returns a shape-(N, 384) matrix of L2-normalised embeddings
  - [x] 10.5 Implement `build_index(doc_id: str, chunks: list[ChunkInfo]) -> faiss.Index` following Algorithm 7: create `IndexFlatIP`, add normalised embeddings, persist index and metadata JSON
  - [x] 10.6 Implement `load_index(doc_id: str) -> faiss.Index | None` that reads from `faiss_index/{doc_id}.index`; returns `None` if file does not exist
  - [x] 10.7 Implement `get_or_create_index(doc_id: str, text: str) -> faiss.Index` that loads existing index or builds a new one from the document text
  - [x] 10.8 Implement `similarity_search(query: str, doc_id: str, k: int = 4) -> list[ChunkResult]` following Algorithm 7: embed query, search index, return sorted `ChunkResult` list
  - [x] 10.9 Implement `cross_document_search(query: str, doc_ids: list[str], k: int = 10) -> list[ChunkResult]` that merges results from multiple indices, skipping missing ones
  - [x] 10.10 Wrap all functions in `try/except`; log errors and return safe defaults (empty list or `None`)
  - [x] 10.11 Write property tests: embedding shape is (384,), L2 norm ≈ 1.0; `index.ntotal == len(chunks)` after build; search results sorted descending; `len(results) ≤ k`; scores in [0.0, 1.0]; cross-search skips missing indices (validates Properties 12, 13, 14, 15)

- [x] 11. Implement RAG chatbot service (`backend/services/rag_service.py`)
  - [x] 11.1 Create `backend/services/rag_service.py` with a module-level `_CONVERSATION_HISTORIES: dict[str, list]` for per-document chat history
  - [x] 11.2 Implement `get_llm()` that lazy-loads TinyLlama-1.1B-Chat GGUF via `llama-cpp-python` (or `CTransformers` as fallback); store as module-level singleton
  - [x] 11.3 Implement `build_rag_chain(doc_id: str) -> ConversationalRetrievalChain` using LangChain: wrap the FAISS index as a `LangChain` retriever, attach the local LLM
  - [x] 11.4 Implement `answer_question(question: str, doc_id: str, chat_history: list[dict] | None = None, k: int = 4) -> RAGResult`
  - [x] 11.5 In `answer_question`: call `get_or_create_index` to ensure the FAISS index exists; retrieve top-k chunks; construct prompt; call LLM; return `RAGResult`
  - [x] 11.6 Persist conversation history in `_CONVERSATION_HISTORIES[doc_id]` after each exchange
  - [x] 11.7 Wrap the entire function body in `try/except`; on any exception return `RAGResult(answer="Error: <reason>", source_chunks=[], model_used="unknown")`
  - [x] 11.8 Write unit tests: `answer` is non-empty, `len(source_chunks) ≤ k`, `model_used` is non-empty, conversation history is maintained across calls, LLM failure returns error message in `answer` (validates Property 16)

- [x] 12. Implement the AI Flask blueprint (`backend/routes/ai.py`)
  - [x] 12.1 Create `backend/routes/ai.py` with `ai_bp = Blueprint("ai", __name__)`
  - [x] 12.2 Implement the `_get_document(doc_id_str)` helper: validate ObjectId format (return 400 on invalid), fetch from `ocr_documents` (return 404 if not found)
  - [x] 12.3 Implement `_check_cache(doc, nlp_key, force)` helper: return cached result with `{"ok": True, "data": ..., "cached": True}` if cache hit and `force` is falsy
  - [x] 12.4 Implement `POST /classify` endpoint: call `_get_document`, check cache, call `nlp_service.classify`, persist to `nlp.classification` via `$set`, return envelope
  - [x] 12.5 Implement `POST /extract` endpoint: call `_get_document`, check cache, call `nlp_service.extract_entities` and `nlp_service.detect_clauses`, persist to `nlp.entities` and `nlp.clauses`, return envelope
  - [x] 12.6 Implement `POST /summarize` endpoint: call `_get_document`, check cache, call `nlp_service.summarize`, persist to `nlp.summary`, return envelope
  - [x] 12.7 Implement `POST /risk-check` endpoint: call `_get_document`, check cache, call `nlp_service.risk_check` (using cached `doc_type` and `clauses_found` if available), persist to `nlp.risk`, return envelope
  - [x] 12.8 Implement `POST /search` endpoint: accept `query` and optional `top_k`; call `embedding_service.similarity_search`; return results in envelope
  - [x] 12.9 Implement `POST /chat` endpoint: accept `doc_id` and `question`; call `rag_service.answer_question`; return `RAGResult` in envelope
  - [x] 12.10 Implement `POST /cross-search` endpoint: accept `query` and optional `doc_ids`; call `embedding_service.cross_document_search`; return results in envelope
  - [x] 12.11 Add validation: `nlp.classification.confidence` in [0.0, 1.0], `nlp.risk.score` in [0.0, 1.0], `nlp.risk.risk_level` in `{"low", "medium", "high"}` before any `$set` write
  - [x] 12.12 Add `processed_at` (UTC datetime) and `model` (string identifier) to every `nlp` sub-document write
  - [x] 12.13 Register `ai_bp` in `backend/app.py` with prefix `/api/ai`
  - [x] 12.14 Write integration tests for the blueprint: 400 on invalid ObjectId, 404 on missing doc, correct envelope structure, `cached=true` on second call (validates Properties 18, 19, 20)

- [x] 13. Add MongoDB indexes
  - [x] 13.1 Add index creation calls to `backend/models/document.py` (or a `backend/db_init.py` script): `db["ocr_documents"].create_index([("nlp.classification.doc_type", 1)])`, `db["ocr_documents"].create_index([("nlp.risk.risk_level", 1)])`, `db["ocr_documents"].create_index([("created_at", -1)])`
  - [x] 13.2 Call the index creation function from `app.py` startup (inside `if __name__ == "__main__"` or an `@app.before_first_request` hook)

- [x] 14. Write comprehensive property-based and unit tests (`backend/tests/`)
  - [x] 14.1 Create `backend/tests/` directory with `__init__.py` and `conftest.py` (pytest fixtures for mock MongoDB, mock pipelines, sample documents)
  - [x] 14.2 Write property tests for `chunk_document` using `hypothesis`: coverage invariant, overlap invariant, max-size invariant (Property 11)
  - [x] 14.3 Write property tests for `classify` using `hypothesis`: scores sum to 1.0, `doc_type` in `LEGAL_DOC_TYPES`, `confidence` in [0.0, 1.0] (Properties 1, 2)
  - [x] 14.4 Write property tests for `extract_entities` using `hypothesis`: entity lists contain unique non-empty stripped strings, `raw_entities` have all five keys (Properties 3, 4)
  - [x] 14.5 Write property tests for `detect_clauses` using `hypothesis`: `clauses_found` labels in `LEGAL_CLAUSE_LABELS`, `clause_spans` well-formed (Property 5)
  - [x] 14.6 Write property tests for `summarize` using `hypothesis`: `compression_ratio < 1.0`, `word_count == len(summary.split())`, short-text guard (Properties 6, 7)
  - [x] 14.7 Write property tests for `risk_check` using `hypothesis`: `score` in [0.0, 1.0], `risk_level` consistent with score, flags well-formed, missing clauses produce flags (Properties 8, 9, 10)
  - [x] 14.8 Write property tests for `embed_text` using `hypothesis`: shape (384,), L2 norm ≈ 1.0 (Property 12)
  - [x] 14.9 Write property tests for `build_index` and `similarity_search` using `hypothesis`: `index.ntotal == len(chunks)`, results sorted, `len(results) ≤ k`, scores in [0.0, 1.0] (Properties 13, 14)
  - [x] 14.10 Write property tests for `cross_document_search` using `hypothesis`: skips missing indices, results sorted (Property 15)
  - [x] 14.11 Write unit tests for `answer_question`: non-empty answer, `len(source_chunks) ≤ k`, `model_used` non-empty, conversation history maintained (Property 16)
  - [x] 14.12 Write unit tests for pipeline singleton: same object returned on repeated calls (Property 17)
  - [x] 14.13 Write unit tests for API envelope: all responses contain `ok`, `data`, `cached` keys (Property 18)
  - [x] 14.14 Write unit tests for NLP persistence round-trip: after endpoint call, MongoDB document has `nlp` sub-document with `processed_at` and `model` (Property 19)
  - [x] 14.15 Write unit tests for caching idempotence: second call returns `cached=true` with same data (Property 20)
  - [x] 14.16 Write unit tests for graceful degradation: mock model failures and verify safe defaults are returned (Property 21)

- [~] 15. Integration and end-to-end validation
  - [~] 15.1 Run the full Flask application locally and verify all seven AI endpoints are reachable via `curl` or Postman using a document previously uploaded via `/api/ocr/scan`
  - [~] 15.2 Verify that calling `/api/ai/classify` twice on the same document returns `cached=true` on the second call
  - [~] 15.3 Verify that `/api/ai/chat` returns a grounded answer with `source_chunks` populated
  - [~] 15.4 Verify that `/api/ai/cross-search` returns results across multiple indexed documents
  - [~] 15.5 Verify that all NLP results are correctly persisted in MongoDB by inspecting the `nlp` sub-document via MongoDB Compass or `mongosh`
  - [x] 15.6 Run the full test suite with `pytest backend/tests/ -v` and confirm all tests pass
  - [~] 15.7 Upload a Hindi document via `/api/ocr/scan?lang=hin` and verify `/api/ai/classify` returns a valid `doc_type` from `LEGAL_DOC_TYPES` using the Indic pipeline (not InLegalBERT), and that the `nlp.classification` sub-document includes a `lang` field set to `"hin"`
  - [~] 15.8 Verify `/api/ai/extract` on a Hindi document returns entities populated from regex `fields` without NER transformer errors; confirm `nlp.entities.lang` is stored correctly
  - [~] 15.9 Verify `/api/ai/chat` (semantic search) works on a Hindi document — embeddings should be generated correctly by `all-MiniLM-L6-v2` and the returned `source_chunks` should contain Devanagari text

- [x] 16. Implement language-aware NLP dispatch
  - [x] 16.1 Implement `_detect_script_family(lang: str) -> str` in `nlp_service.py` that maps language codes to `"latin"`, `"devanagari"`, `"indic"`, or `"arabic"`; handle compound codes like `"eng+hin"` by splitting on `"+"` and giving precedence to the non-English part
    - `DEVANAGARI_LANGS = {"hin", "mar"}`, `INDIC_LANGS = {"tam", "tel", "kan", "mal", "ben", "guj", "pan"}`, `ARABIC_LANGS = {"urd", "ara"}`
    - _Requirements: 15.1_

  - [x] 16.2 Add `get_indic_classification_pipeline()` that lazy-loads `ai4bharat/indic-bert` as a `zero-shot-classification` pipeline and stores it in `_PIPELINES["indic_classify"]`; wrap in `try/except` and raise `ModelUnavailableError` on failure
    - _Requirements: 15.10_

  - [x] 16.3 Add `get_indic_ner_pipeline()` that lazy-loads `ai4bharat/indic-bert` as a `token-classification` pipeline and stores it in `_PIPELINES["indic_ner"]`; wrap in `try/except` and raise `ModelUnavailableError` on failure
    - _Requirements: 15.11_

  - [x] 16.4 Update `classify(text, fields, lang="eng")` to dispatch based on script family: `latin` → existing InLegalBERT zero-shot path; `devanagari` → `get_indic_classification_pipeline()` zero-shot with same `LEGAL_DOC_TYPES` labels; `indic`/`arabic` → use `fields.get("doc_type_hint")` wrapped in `ClassificationResult(confidence=0.8)` if present, else return `ClassificationResult("unknown", 0.0, {})`
    - _Requirements: 15.2, 15.3_

  - [x] 16.5 Update `extract_entities(text, existing_fields, lang="eng")` to dispatch based on script family: `latin` → existing Legal-BERT NER path; `devanagari` → `get_indic_ner_pipeline()` token-classification; `indic`/`arabic` → return `EntityExtractionResult` populated entirely from `existing_fields` without invoking any transformer model
    - _Requirements: 15.4, 15.5_

  - [x] 16.6 Update `detect_clauses(text, lang="eng")` to return `ClauseDetectionResult(clauses_found=[], clause_spans=[])` immediately for any script family other than `"latin"`, without invoking the NLI pipeline
    - _Requirements: 15.6_

  - [x] 16.7 Update `summarize(text, max_length, lang="eng")` to return an extractive summary (first 3 sentences of `text`) for non-`"latin"` script families instead of invoking BART; compute `compression_ratio` as `len(summary.split()) / max(len(text.split()), 1)`
    - _Requirements: 15.7_

  - [x] 16.8 Update `routes/ai.py` to read `lang_detected` from the MongoDB document (falling back to `lang` if `lang_detected` is absent or empty) and pass the resolved language code to all four service function calls (`classify`, `extract_entities`, `detect_clauses`, `summarize`)
    - _Requirements: 15.8_

  - [x] 16.9 Update every `nlp` sub-document `$set` write in `routes/ai.py` to include the resolved `lang` field alongside `processed_at` and `model`
    - _Requirements: 15.9_

  - [x] 16.10 Add `langdetect` to `IDP/requirements.txt` as an optional dependency for more accurate language detection on mixed-script documents
    - _Requirements: 15.1_

  - [ ]* 16.11 Write property tests for `_detect_script_family`: verify all 12 Tesseract language codes map to the correct family, and that compound codes like `"eng+hin"`, `"eng+tam"`, `"hin+eng"` are handled correctly with non-English precedence
    - **Property 25: `detect_script_family` is total over all valid Tesseract language codes**
    - **Validates: Requirements 15.1**

  - [ ]* 16.12 Write property tests for multilingual `classify`: Devanagari text (`lang="hin"` or `lang="mar"`) uses the Indic pipeline and returns a `doc_type` from `LEGAL_DOC_TYPES`; Indic/Arabic text uses regex fallback and never invokes a transformer
    - **Property 22: Devanagari documents use the Indic classification pipeline**
    - **Validates: Requirements 15.2, 15.3**

  - [ ]* 16.13 Write property tests for multilingual `extract_entities`: non-Latin scripts (`lang` in `INDIC_LANGS` or `ARABIC_LANGS`) return `EntityExtractionResult` populated from `existing_fields` without any transformer call; verify by mocking the NER pipeline and asserting it is never called
    - **Property 23: Non-Latin entity extraction never invokes a transformer**
    - **Validates: Requirements 15.5**

  - [ ]* 16.14 Write property tests for multilingual `detect_clauses`: any `lang` whose script family is not `"latin"` returns `ClauseDetectionResult(clauses_found=[], clause_spans=[])` and the NLI pipeline is never invoked
    - **Property 24: Non-Latin clause detection always returns empty result**
    - **Validates: Requirements 15.6**
