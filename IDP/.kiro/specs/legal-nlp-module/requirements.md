# Requirements Document

## Introduction

This document defines the functional and non-functional requirements for the **Legal NLP/LLM Module** — the intelligent inference layer added on top of the existing OCR pipeline in the Secure Legal Document Management system. The module consumes `clean_text` and `fields` already stored in MongoDB's `ocr_documents` collection and produces higher-order outputs: document classification, deep entity extraction, legal clause detection, abstractive summarisation, risk/anomaly flagging, semantic search, and a retrieval-augmented generation (RAG) chatbot. All models are open-source and run locally (no paid API dependencies). The module is delivered in two phases: Phase 1 covers the four core inference endpoints; Phase 2 adds vector-based semantic search and the RAG chatbot.

---

## Glossary

- **AI_Blueprint**: The Flask blueprint (`routes/ai.py`) that exposes all NLP/AI HTTP endpoints.
- **NLP_Service**: The `services/nlp_service.py` module that lazy-loads and caches HuggingFace transformer pipelines and provides the four Phase 1 inference functions.
- **Embedding_Service**: The `services/embedding_service.py` module that generates sentence embeddings, manages per-document FAISS indices, and provides similarity search.
- **RAG_Service**: The `services/rag_service.py` module that implements retrieval-augmented generation using LangChain and a local GGUF LLM.
- **Classifier**: The document classification pipeline within NLP_Service, backed by `law-ai/InLegalBERT`.
- **NER_Pipeline**: The named-entity recognition pipeline within NLP_Service, backed by `nlpaueb/legal-bert-base-uncased`.
- **NLI_Pipeline**: The zero-shot NLI pipeline within NLP_Service, backed by `cross-encoder/nli-MiniLM2-L6-H768`, used for clause detection.
- **Summarizer**: The abstractive summarisation pipeline within NLP_Service, backed by `facebook/bart-large-cnn`.
- **FAISS_Index**: A per-document flat inner-product FAISS index stored at `faiss_index/{doc_id}.index` with accompanying metadata at `faiss_index/{doc_id}.meta.json`.
- **LLM**: The local quantised language model (TinyLlama-1.1B-Chat GGUF or Mistral-7B-Instruct GGUF) loaded via `llama-cpp-python` for RAG answer generation.
- **ocr_documents**: The existing MongoDB collection that stores OCR pipeline outputs; extended with an `nlp` sub-document by this module.
- **nlp sub-document**: The `nlp` field added to each `ocr_documents` record to cache all NLP inference results.
- **doc_id**: A MongoDB ObjectId string that uniquely identifies a document in `ocr_documents`.
- **clean_text**: The high-quality OCR output (confidence ≥ 60, garbage-filtered, keyword-corrected) stored in `ocr_documents`.
- **fields**: The regex-extracted structured fields dict stored in `ocr_documents` alongside `clean_text`.
- **ChunkInfo**: A data structure representing a sliding-window text chunk with `text`, `start_char`, `end_char`, and `index` fields.
- **ClassificationResult**: Typed dataclass with `doc_type`, `confidence`, and `all_scores`.
- **EntityExtractionResult**: Typed dataclass with `persons`, `organisations`, `dates`, `money`, `locations`, `case_numbers`, and `raw_entities`.
- **ClauseDetectionResult**: Typed dataclass with `clauses_found` and `clause_spans`.
- **SummarizationResult**: Typed dataclass with `summary`, `word_count`, and `compression_ratio`.
- **RiskResult**: Typed dataclass with `risk_level`, `score`, and `flags`.
- **RiskFlag**: Typed dataclass with `category`, `description`, and `severity`.
- **ChunkResult**: Typed dataclass with `chunk_text`, `doc_id`, `chunk_index`, and `score`.
- **RAGResult**: Typed dataclass with `answer`, `source_chunks`, and `model_used`.
- **LEGAL_DOC_TYPES**: The set of known legal document type labels: `FIR`, `contract`, `agreement`, `affidavit`, `judgment`, `petition`, `notice`, `deed`, `power_of_attorney`, `unknown`.
- **LEGAL_CLAUSE_LABELS**: The set of ten clause labels: `indemnity clause`, `termination clause`, `jurisdiction clause`, `arbitration clause`, `confidentiality clause`, `force majeure clause`, `limitation of liability clause`, `payment terms clause`, `intellectual property clause`, `governing law clause`.
- **ENTAILMENT_THRESHOLD**: The NLI confidence threshold (0.7) above which a clause is considered detected.
- **REQUIRED_CLAUSES_BY_TYPE**: A mapping from document type to the list of clauses that must be present for that type (e.g., contracts require termination, jurisdiction, and payment terms clauses).

---

## Requirements

### Requirement 1: Flask AI Blueprint and Endpoint Registration

**User Story:** As a backend developer, I want all NLP/AI endpoints exposed under a single Flask blueprint, so that the AI layer integrates cleanly with the existing Flask application without modifying `app.py` beyond blueprint registration.

#### Acceptance Criteria

1. THE AI_Blueprint SHALL expose the following HTTP endpoints: `POST /api/ai/classify`, `POST /api/ai/extract`, `POST /api/ai/summarize`, `POST /api/ai/risk-check`, `POST /api/ai/search`, `POST /api/ai/chat`, and `POST /api/ai/cross-search`.
2. WHEN `app.py` registers the AI_Blueprint with the prefix `/api/ai`, THE AI_Blueprint SHALL be reachable at all seven endpoint paths without modifying any existing route or blueprint.
3. WHEN a request body contains a `doc_id` field that is not a valid MongoDB ObjectId, THE AI_Blueprint SHALL return HTTP 400 with a JSON body containing an `error` field.
4. WHEN a request references a `doc_id` that does not exist in `ocr_documents`, THE AI_Blueprint SHALL return HTTP 404 with a JSON body containing an `error` field.
5. WHEN an NLP inference result is successfully computed, THE AI_Blueprint SHALL persist the result to the `nlp` sub-document of the corresponding `ocr_documents` record via a MongoDB `$set` operation.
6. WHEN a request is received with `force` set to `false` (or omitted) and a cached result already exists in the `nlp` sub-document, THE AI_Blueprint SHALL return the cached result without re-running inference.
7. THE AI_Blueprint SHALL return all responses in the JSON envelope `{"ok": bool, "data": ..., "cached": bool}`.

---

### Requirement 2: Document Classification

**User Story:** As a legal professional, I want each uploaded document automatically classified into its legal document type, so that I can quickly identify the nature of a document without reading it.

#### Acceptance Criteria

1. WHEN `POST /api/ai/classify` is called with a valid `doc_id`, THE Classifier SHALL return a `ClassificationResult` with `doc_type`, `confidence`, and `all_scores`.
2. THE Classifier SHALL truncate `clean_text` to 512 tokens before passing it to the classification pipeline.
3. WHEN `clean_text` is empty or shorter than 20 characters, THE Classifier SHALL return `ClassificationResult(doc_type="unknown", confidence=0.0, all_scores={})` without invoking the model.
4. THE Classifier SHALL apply field-based heuristic boosts to raw model scores before normalisation (e.g., presence of `fir_number` in `fields` boosts the `FIR` label score).
5. THE Classifier SHALL normalise all scores so that `sum(all_scores.values())` is approximately 1.0 within floating-point tolerance.
6. THE Classifier SHALL return a `doc_type` that is a member of `LEGAL_DOC_TYPES`.
7. THE Classifier SHALL return a `confidence` value in the range [0.0, 1.0].
8. IF the classification model fails to load or raises an exception, THEN THE Classifier SHALL return `ClassificationResult(doc_type="unknown", confidence=0.0, all_scores={})` without propagating the exception.

---

### Requirement 3: Named Entity and Field Extraction

**User Story:** As a legal analyst, I want structured entities (persons, organisations, dates, monetary values, locations, case numbers) extracted from each document, so that I can quickly identify key parties and facts without reading the full text.

#### Acceptance Criteria

1. WHEN `POST /api/ai/extract` is called with a valid `doc_id`, THE NER_Pipeline SHALL return an `EntityExtractionResult` containing `persons`, `organisations`, `dates`, `money`, `locations`, `case_numbers`, and `raw_entities`.
2. THE NER_Pipeline SHALL split `clean_text` into overlapping chunks of at most 512 tokens with a 64-token overlap before running inference, and SHALL aggregate entity results across all chunks.
3. THE NER_Pipeline SHALL merge transformer-detected entities with the existing regex `fields` from `ocr_documents`, with regex-extracted values taking precedence for structured fields (`names`, `dates`, `document_ids`, `financial`).
4. THE NER_Pipeline SHALL deduplicate entity values within each category so that no entity string appears more than once in any entity list.
5. THE NER_Pipeline SHALL return only non-empty, stripped strings in all entity lists.
6. THE NER_Pipeline SHALL populate `raw_entities` with dicts containing the keys `text`, `label`, `score`, `start`, and `end` for each detected entity span.
7. IF the NER model fails to load or raises an exception, THEN THE NER_Pipeline SHALL return an `EntityExtractionResult` with all lists empty without propagating the exception.

---

### Requirement 4: Legal Clause Detection

**User Story:** As a contract reviewer, I want the system to automatically detect which standard legal clauses are present in a document, so that I can quickly assess completeness and flag missing clauses.

#### Acceptance Criteria

1. WHEN `POST /api/ai/extract` is called (clause detection is part of the extraction endpoint) with a valid `doc_id`, THE NLI_Pipeline SHALL return a `ClauseDetectionResult` containing `clauses_found` and `clause_spans`.
2. THE NLI_Pipeline SHALL use a sliding window of 3 sentences with a step of 1 sentence over the full document text.
3. THE NLI_Pipeline SHALL classify each window against all labels in `LEGAL_CLAUSE_LABELS` using zero-shot NLI entailment.
4. WHEN the NLI entailment score for a window-label pair meets or exceeds `ENTAILMENT_THRESHOLD` (0.7), THE NLI_Pipeline SHALL record that clause label as found and store the best-scoring window text as the `text_snippet` in `clause_spans`.
5. THE NLI_Pipeline SHALL include only labels from `LEGAL_CLAUSE_LABELS` in `clauses_found`.
6. Each entry in `clause_spans` SHALL contain the keys `clause`, `text_snippet` (truncated to 200 characters), and `start_char`.
7. IF the NLI model fails to load or raises an exception, THEN THE NLI_Pipeline SHALL return `ClauseDetectionResult(clauses_found=[], clause_spans=[])` without propagating the exception.

---

### Requirement 5: Abstractive Summarisation

**User Story:** As a busy legal professional, I want a concise abstractive summary of each document, so that I can understand the key points without reading the full text.

#### Acceptance Criteria

1. WHEN `POST /api/ai/summarize` is called with a valid `doc_id`, THE Summarizer SHALL return a `SummarizationResult` containing `summary`, `word_count`, and `compression_ratio`.
2. WHEN `clean_text` contains 600 words or fewer, THE Summarizer SHALL summarise the text directly in a single pipeline call with `max_length=200` and `min_length=50`.
3. WHEN `clean_text` contains more than 600 words, THE Summarizer SHALL apply map-reduce summarisation: split into chunks of at most 900 tokens with 50-token overlap, summarise each chunk independently (`max_length=150`, `min_length=30`), concatenate the partial summaries, then summarise the concatenation (`max_length=200`, `min_length=50`).
4. THE Summarizer SHALL return a `summary` that is a non-empty string.
5. THE Summarizer SHALL return a `compression_ratio` that is strictly less than 1.0 (the summary is shorter than the input).
6. THE Summarizer SHALL return a `word_count` equal to `len(summary.split())`.
7. IF `clean_text` contains fewer than 30 words, THEN THE Summarizer SHALL return the input text as the summary without invoking the model.
8. IF the summarisation model fails to load or raises an exception, THEN THE Summarizer SHALL return the truncated input text as the summary without propagating the exception.

---

### Requirement 6: Risk and Anomaly Detection

**User Story:** As a legal reviewer, I want the system to automatically flag potential risks and anomalies in a document (missing clauses, date inconsistencies, missing parties, unusual terms), so that I can prioritise documents that need closer attention.

#### Acceptance Criteria

1. WHEN `POST /api/ai/risk-check` is called with a valid `doc_id`, THE NLP_Service SHALL return a `RiskResult` containing `risk_level`, `score`, and `flags`.
2. THE NLP_Service SHALL check for missing required clauses by comparing `clauses_found` against `REQUIRED_CLAUSES_BY_TYPE[doc_type]`; each missing clause SHALL produce a `RiskFlag` with `category="missing_clause"` and `severity="warning"`.
3. WHEN `fields["dates"]` contains two or more date values and the parsed dates contain a logically inconsistent ordering (a future date appearing before a past date in document context), THE NLP_Service SHALL produce a `RiskFlag` with `category="date_inconsistency"` and `severity="error"`.
4. WHEN `doc_type` is one of `contract`, `agreement`, or `affidavit` and `fields["names"]` contains fewer than 2 entries, THE NLP_Service SHALL produce a `RiskFlag` with `category="missing_party"` and `severity="warning"`.
5. THE NLP_Service SHALL scan `clean_text` for unusual legal terms and produce a `RiskFlag` with `category="unusual_term"` and `severity="warning"` for each term found.
6. THE NLP_Service SHALL compute a `score` in [0.0, 1.0] by summing weighted flag contributions (missing_clause: 0.25, date_inconsistency: 0.30, unusual_term: 0.20, missing_party: 0.25) and capping at 1.0.
7. THE NLP_Service SHALL assign `risk_level` as `"low"` when `score < 0.25`, `"medium"` when `0.25 ≤ score < 0.60`, and `"high"` when `score ≥ 0.60`.
8. THE NLP_Service SHALL return a `risk_level` that is one of `"low"`, `"medium"`, or `"high"`.
9. Each `RiskFlag` SHALL have a non-empty `category`, a non-empty `description`, and a `severity` that is one of `"warning"` or `"error"`.
10. IF an exception occurs during risk checking, THEN THE NLP_Service SHALL return `RiskResult(risk_level="low", score=0.0, flags=[])` without propagating the exception.

---

### Requirement 7: Sentence Embedding and FAISS Index Management

**User Story:** As a developer building semantic search, I want each document's text chunked, embedded, and indexed in a FAISS vector store, so that similarity queries can be answered efficiently without re-embedding on every request.

#### Acceptance Criteria

1. THE Embedding_Service SHALL chunk document text using a sliding window of at most 512 tokens with a 64-token overlap, producing a list of `ChunkInfo` objects each containing `text`, `start_char`, `end_char`, and `index`.
2. THE Embedding_Service SHALL generate L2-normalised 384-dimensional embeddings for each chunk using the `sentence-transformers/all-MiniLM-L6-v2` model.
3. WHEN `build_index` is called for a `doc_id`, THE Embedding_Service SHALL create a FAISS `IndexFlatIP` index, add all chunk embeddings, and persist the index to `faiss_index/{doc_id}.index`.
4. WHEN `build_index` is called for a `doc_id`, THE Embedding_Service SHALL persist chunk metadata (text, start_char, index) to `faiss_index/{doc_id}.meta.json`.
5. WHEN `build_index` completes, THE Embedding_Service SHALL ensure `index.ntotal` equals the number of chunks provided.
6. THE Embedding_Service SHALL return embeddings as 1D numpy arrays of shape (384,) with L2 norm approximately equal to 1.0.
7. WHEN `load_index` is called for a `doc_id` whose index file does not exist, THE Embedding_Service SHALL return `None`.
8. THE Embedding_Service SHALL expose a `get_or_create_index` function that loads an existing index if available or builds and persists a new one.

---

### Requirement 8: Semantic Search

**User Story:** As a legal researcher, I want to search across one or more documents using natural language queries, so that I can find relevant passages without knowing exact keywords.

#### Acceptance Criteria

1. WHEN `POST /api/ai/search` is called with a `query` string and an optional `top_k` integer, THE Embedding_Service SHALL return the top-k most semantically similar chunks from the indexed document corpus.
2. THE Embedding_Service SHALL return results sorted by descending similarity score.
3. THE Embedding_Service SHALL return at most `top_k` results (default 4).
4. Each result in the response SHALL be a `ChunkResult` containing `chunk_text`, `doc_id`, `chunk_index`, and `score`.
5. THE Embedding_Service SHALL return `score` values in the range [0.0, 1.0] (cosine similarity on L2-normalised vectors via inner product).
6. WHEN `POST /api/ai/cross-search` is called with a `query` string and an optional `doc_ids` list, THE Embedding_Service SHALL search across all specified document indices and return the globally top-k results.
7. WHEN `doc_ids` is omitted from a cross-search request, THE Embedding_Service SHALL search across all documents that have a FAISS index on disk.
8. IF a FAISS index for a requested `doc_id` does not exist, THEN THE Embedding_Service SHALL skip that document and continue searching the remaining indices without raising an exception.

---

### Requirement 9: RAG Chatbot

**User Story:** As a legal professional, I want to ask natural language questions about a specific document and receive grounded answers with source references, so that I can quickly extract information without reading the full text.

#### Acceptance Criteria

1. WHEN `POST /api/ai/chat` is called with a `doc_id` and a `question` string, THE RAG_Service SHALL return a `RAGResult` containing `answer`, `source_chunks`, and `model_used`.
2. THE RAG_Service SHALL retrieve the top-k (default 4) most relevant chunks from the document's FAISS index using the `question` as the query.
3. THE RAG_Service SHALL construct a prompt that includes the retrieved context chunks and the question, then pass it to the LLM for answer generation.
4. THE RAG_Service SHALL use a LangChain `ConversationalRetrievalChain` backed by the document's FAISS retriever.
5. THE RAG_Service SHALL maintain per-document conversation history in memory, keyed by `doc_id`, so that follow-up questions within the same session have access to prior exchanges.
6. THE RAG_Service SHALL return a `answer` that is a non-empty string.
7. THE RAG_Service SHALL return `source_chunks` containing the `ChunkResult` objects used to ground the answer, with `len(source_chunks) ≤ k`.
8. THE RAG_Service SHALL populate `model_used` with the identifier of the LLM that generated the answer.
9. IF the FAISS index for the requested `doc_id` does not exist, THEN THE RAG_Service SHALL build the index before answering.
10. IF the LLM fails to load or raises an exception during answer generation, THEN THE RAG_Service SHALL return a `RAGResult` with `answer` set to a descriptive error message and `source_chunks` set to the retrieved chunks, without propagating the exception.

---

### Requirement 10: Model Lazy-Loading and Singleton Management

**User Story:** As a system operator, I want NLP models loaded on first use and reused across requests, so that the Flask process does not reload heavy model weights on every API call.

#### Acceptance Criteria

1. THE NLP_Service SHALL store all loaded HuggingFace pipeline instances in a module-level dictionary (`_PIPELINES`) and return the same instance on subsequent calls.
2. WHEN a pipeline is requested for the first time, THE NLP_Service SHALL load it from the HuggingFace cache or download it, then store it in `_PIPELINES`.
3. THE Embedding_Service SHALL store the `sentence-transformers/all-MiniLM-L6-v2` model as a module-level singleton and return the same instance on all subsequent calls.
4. THE NLP_Service SHALL support thread-safe lazy initialisation so that concurrent requests do not trigger duplicate model loads.
5. WHEN a model fails to load due to an out-of-memory error or missing weights, THE NLP_Service SHALL log the error and return a graceful error response `{"ok": false, "error": "model_unavailable", "detail": "..."}` without crashing the Flask process.

---

### Requirement 11: MongoDB Schema Extension and Caching

**User Story:** As a developer, I want NLP results persisted to MongoDB alongside the original OCR data, so that repeated API calls for the same document return cached results instantly without re-running expensive inference.

#### Acceptance Criteria

1. THE AI_Blueprint SHALL extend each `ocr_documents` record with an `nlp` sub-document containing sub-fields: `classification`, `entities`, `clauses`, `summary`, `risk`, and `embedding`.
2. WHEN an NLP inference result is computed, THE AI_Blueprint SHALL write it to the corresponding `nlp` sub-field using a MongoDB `$set` operation and SHALL include a `processed_at` UTC datetime and a `model` identifier string.
3. WHEN a cached result exists in the `nlp` sub-document and `force` is not `true`, THE AI_Blueprint SHALL return the cached result with `"cached": true` in the response envelope.
4. THE AI_Blueprint SHALL validate that `nlp.classification.confidence` is in [0.0, 1.0] before persisting.
5. THE AI_Blueprint SHALL validate that `nlp.risk.score` is in [0.0, 1.0] before persisting.
6. THE AI_Blueprint SHALL validate that `nlp.risk.risk_level` is one of `"low"`, `"medium"`, or `"high"` before persisting.
7. THE AI_Blueprint SHALL create the following MongoDB indexes on `ocr_documents` if they do not already exist: `nlp.classification.doc_type` (ascending), `nlp.risk.risk_level` (ascending), `created_at` (descending).

---

### Requirement 12: Document Chunking

**User Story:** As a developer, I want a reusable document chunking utility that splits text into overlapping windows, so that all NLP services (NER, summarisation, embedding) use a consistent chunking strategy.

#### Acceptance Criteria

1. THE NLP_Service SHALL provide a `chunk_document(text, max_tokens, overlap)` function that splits `text` into a list of `ChunkInfo` objects.
2. WHEN `chunk_document` is called, THE NLP_Service SHALL ensure every character in `text` is covered by at least one chunk.
3. WHEN `chunk_document` is called, THE NLP_Service SHALL ensure consecutive chunks overlap by approximately `overlap` tokens.
4. WHEN `chunk_document` is called, THE NLP_Service SHALL ensure no chunk exceeds `max_tokens` tokens.
5. THE NLP_Service SHALL return at least one chunk for any non-empty input text.
6. THE NLP_Service SHALL set `chunks[0].start_char` to 0 for any non-empty input.

---

### Requirement 13: Typed Data Models

**User Story:** As a developer, I want all NLP result structures defined as typed Python dataclasses, so that service functions have clear contracts and JSON serialisation is consistent across all endpoints.

#### Acceptance Criteria

1. THE NLP_Service SHALL define the following dataclasses in `models/nlp_models.py`: `ClassificationResult`, `EntityExtractionResult`, `ClauseDetectionResult`, `SummarizationResult`, `RiskResult`, `RiskFlag`, `ChunkResult`, and `RAGResult`.
2. THE NLP_Service SHALL ensure `ClassificationResult` has fields `doc_type: str`, `confidence: float`, and `all_scores: dict[str, float]`.
3. THE NLP_Service SHALL ensure `RiskResult` has fields `risk_level: str`, `flags: list[RiskFlag]`, and `score: float`.
4. THE NLP_Service SHALL ensure `RiskFlag` has fields `category: str`, `description: str`, and `severity: str`.
5. THE NLP_Service SHALL ensure `ChunkResult` has fields `chunk_text: str`, `doc_id: str`, `chunk_index: int`, and `score: float`.
6. THE NLP_Service SHALL ensure `RAGResult` has fields `answer: str`, `source_chunks: list[ChunkResult]`, and `model_used: str`.
7. THE AI_Blueprint SHALL serialise all dataclass results to JSON-compatible dicts before returning them in API responses.

---

### Requirement 14: Error Handling and Graceful Degradation

**User Story:** As a system operator, I want all NLP service functions to handle model failures gracefully, so that a single model failure does not crash the Flask process or return unhandled 500 errors to clients.

#### Acceptance Criteria

1. IF any NLP_Service function raises an unhandled exception, THEN THE NLP_Service SHALL catch it, log it, and return a typed result object with safe default values (empty lists, `"unknown"` strings, 0.0 scores) rather than propagating the exception.
2. IF any Embedding_Service function raises an unhandled exception, THEN THE Embedding_Service SHALL catch it, log it, and return a safe default (empty list for search, `None` for index load) rather than propagating the exception.
3. IF any RAG_Service function raises an unhandled exception, THEN THE RAG_Service SHALL catch it, log it, and return a `RAGResult` with a descriptive error message in `answer` rather than propagating the exception.
4. WHEN a model is unavailable (OOM, missing weights, download failure), THE NLP_Service SHALL return `{"ok": false, "error": "model_unavailable", "detail": "<reason>"}` to the caller.
5. THE AI_Blueprint SHALL return HTTP 500 with a JSON error body only when an unrecoverable infrastructure error occurs (e.g., MongoDB connection failure), not for model inference failures.

---

### Requirement 15: Multilingual NLP Support

**User Story:** As a legal professional working with documents in Indian languages, I want the NLP module to process Hindi, Marathi, Tamil, Telugu, and other Indic-script documents correctly, so that classification, entity extraction, and search work on non-English legal documents without producing garbage output from English-only models.

#### Acceptance Criteria

1. THE NLP_Service SHALL expose a `_detect_script_family(lang: str) -> str` helper that maps any valid Tesseract language code (including compound codes such as `"eng+hin"`) to exactly one of `"latin"`, `"devanagari"`, `"indic"`, or `"arabic"`. For compound codes, the non-English part SHALL take precedence.
2. WHEN `classify()` is called with a `lang` whose script family is `"devanagari"`, THE NLP_Service SHALL use the `ai4bharat/indic-bert` zero-shot-classification pipeline and SHALL return a `doc_type` from `LEGAL_DOC_TYPES`.
3. WHEN `classify()` is called with a `lang` whose script family is `"indic"` or `"arabic"`, THE NLP_Service SHALL use `fields["doc_type_hint"]` from the regex parser directly; if the hint is present it SHALL be wrapped in a `ClassificationResult` with `confidence=0.8`, otherwise `ClassificationResult(doc_type="unknown", confidence=0.0, all_scores={})` SHALL be returned. No transformer model SHALL be invoked.
4. WHEN `extract_entities()` is called with a `lang` whose script family is `"devanagari"`, THE NLP_Service SHALL use the `ai4bharat/indic-bert` token-classification (NER) pipeline.
5. WHEN `extract_entities()` is called with a `lang` whose script family is `"indic"` or `"arabic"`, THE NLP_Service SHALL return an `EntityExtractionResult` populated entirely from `existing_fields` (the regex-extracted fields already stored in MongoDB) without invoking any transformer NER model.
6. WHEN `detect_clauses()` is called with a `lang` whose script family is not `"latin"`, THE NLP_Service SHALL return `ClauseDetectionResult(clauses_found=[], clause_spans=[])` immediately without invoking the NLI pipeline.
7. WHEN `summarize()` is called with a `lang` whose script family is not `"latin"`, THE NLP_Service SHALL return an extractive summary consisting of the first 3 sentences of the input text, with `compression_ratio` computed as `len(summary.split()) / max(len(text.split()), 1)`. No BART model SHALL be invoked.
8. THE AI_Blueprint SHALL read `lang_detected` from the MongoDB document when processing any NLP request; if `lang_detected` is absent or empty, it SHALL fall back to the `lang` field. The resolved language code SHALL be passed to all four service function calls (`classify`, `extract_entities`, `detect_clauses`, `summarize`).
9. THE AI_Blueprint SHALL include the resolved `lang` value in every `nlp` sub-document `$set` write alongside `processed_at` and `model`.
10. THE NLP_Service SHALL expose `get_indic_classification_pipeline()` that lazy-loads `ai4bharat/indic-bert` as a `zero-shot-classification` pipeline and stores it in `_PIPELINES["indic_classify"]`.
11. THE NLP_Service SHALL expose `get_indic_ner_pipeline()` that lazy-loads `ai4bharat/indic-bert` as a `token-classification` pipeline and stores it in `_PIPELINES["indic_ner"]`.
12. THE `sentence-transformers/all-MiniLM-L6-v2` embedding model SHALL be used as the single embedding model for all languages; no separate embedding model per script family is required.
