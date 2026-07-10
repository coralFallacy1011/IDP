"""
Typed data models for the Legal NLP/LLM module.

All dataclasses expose a ``to_dict()`` helper that delegates to
``dataclasses.asdict`` so they can be serialised directly to JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


# ---------------------------------------------------------------------------
# Phase 1 — Core NLP results
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    """Result of document-type classification."""

    doc_type: str
    confidence: float
    all_scores: dict[str, float]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EntityExtractionResult:
    """Named-entity extraction result, split by entity category.

    ``raw_entities`` preserves the full transformer output so callers can
    access span offsets and per-token scores:
    ``[{text, label, score, start, end}, ...]``
    """

    persons: list[str]
    organisations: list[str]
    dates: list[str]
    money: list[str]
    locations: list[str]
    case_numbers: list[str]
    raw_entities: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ClauseDetectionResult:
    """Result of legal-clause detection.

    ``clause_spans`` carries positional metadata for each detected clause:
    ``[{clause, text_snippet, start_char}, ...]``
    """

    clauses_found: list[str]
    clause_spans: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SummarizationResult:
    """Abstractive summarisation result."""

    summary: str
    word_count: int
    compression_ratio: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RiskFlag:
    """A single risk or anomaly flag raised during risk assessment."""

    category: str
    description: str
    severity: str  # e.g. "low" | "medium" | "high"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RiskResult:
    """Aggregate risk-assessment result for a document."""

    risk_level: str  # e.g. "low" | "medium" | "high"
    flags: list[RiskFlag]
    score: float

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Phase 2 — Embedding / RAG results
# ---------------------------------------------------------------------------

@dataclass
class ChunkInfo:
    """Metadata for a single text chunk produced during document chunking."""

    text: str
    start_char: int
    end_char: int
    index: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ChunkResult:
    """A retrieved chunk returned by a similarity search."""

    chunk_text: str
    doc_id: str
    chunk_index: int
    score: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RAGResult:
    """Result of a retrieval-augmented generation (RAG) query."""

    answer: str
    source_chunks: list[ChunkResult]
    model_used: str

    def to_dict(self) -> dict:
        return asdict(self)
