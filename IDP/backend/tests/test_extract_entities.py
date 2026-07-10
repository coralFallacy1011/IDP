"""
Property-based and unit tests for ``nlp_service.extract_entities``.

Tests cover:
  - Entity lists contain only unique, non-empty, stripped strings
  - ``raw_entities`` dicts have all five required keys (text, label, score, start, end)
  - ``score`` in [0.0, 1.0]
  - Deduplication preserves first-occurrence order
  - Merging with existing_fields works correctly
  - Exception returns empty EntityExtractionResult

All tests mock the NER pipeline — no real model downloads.

**Validates: Requirements 3 / Properties 3, 4**
"""

from __future__ import annotations

import sys
import os
import types
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Ensure backend/ is on sys.path
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_pipelines() -> None:
    import services.nlp_service as svc
    svc._PIPELINES.clear()


def _make_fake_transformers(pipeline_factory) -> types.ModuleType:
    fake = types.ModuleType("transformers")
    fake.pipeline = pipeline_factory
    return fake


def _make_ner_pipeline(entities: list[dict]):
    """Return a callable that mimics the HuggingFace NER pipeline output."""
    mock_pipe = MagicMock(return_value=entities)
    return mock_pipe


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_pipeline_cache():
    _reset_pipelines()
    yield
    _reset_pipelines()


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Non-empty text with at least 20 chars (to avoid short-text issues in chunking)
text_st = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
    min_size=20,
).filter(lambda t: len(t.split()) >= 1)

# Strategy for a single NER entity dict (HuggingFace format)
ner_entity_st = st.fixed_dictionaries({
    "word":         st.text(min_size=1, max_size=20).filter(str.strip),
    "entity_group": st.sampled_from(["PER", "ORG", "DATE", "MONEY", "GPE"]),
    "score":        st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    "start":        st.integers(min_value=0, max_value=100),
    "end":          st.integers(min_value=1, max_value=200),
})

# Strategy for a list of NER entities
ner_entities_st = st.lists(ner_entity_st, min_size=0, max_size=10)


# ---------------------------------------------------------------------------
# 1. Property: entity lists contain only unique, non-empty, stripped strings
# ---------------------------------------------------------------------------

class TestEntityListsUnique:
    """Property 3: All entity lists contain only unique, non-empty, stripped strings."""

    @given(text_st, ner_entities_st)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_entity_lists_unique_property(self, text, entities):
        """**Validates: Requirements 3 / Property 3**"""
        from services.nlp_service import extract_entities

        mock_pipe = _make_ner_pipeline(entities)
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = extract_entities(text, {})

        for lst_name, lst in [
            ("persons", result.persons),
            ("organisations", result.organisations),
            ("dates", result.dates),
            ("money", result.money),
            ("locations", result.locations),
            ("case_numbers", result.case_numbers),
        ]:
            # All non-empty
            assert all(len(s) > 0 for s in lst), (
                f"{lst_name} contains empty strings"
            )
            # All stripped
            assert all(s == s.strip() for s in lst), (
                f"{lst_name} contains unstripped strings"
            )
            # All unique
            assert len(lst) == len(set(lst)), (
                f"{lst_name} contains duplicates"
            )

    def test_entity_lists_unique_example(self):
        from services.nlp_service import extract_entities

        entities = [
            {"word": "John Doe", "entity_group": "PER", "score": 0.9, "start": 0, "end": 8},
            {"word": "John Doe", "entity_group": "PER", "score": 0.8, "start": 0, "end": 8},
            {"word": "  Jane  ", "entity_group": "PER", "score": 0.7, "start": 10, "end": 18},
        ]
        mock_pipe = _make_ner_pipeline(entities)
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = extract_entities("This is a legal document with sufficient length.", {})

        # "John Doe" should appear only once
        assert result.persons.count("John Doe") == 1
        # "Jane" should be stripped
        assert "Jane" in result.persons
        assert "  Jane  " not in result.persons

    def test_empty_entities_returns_empty_lists(self):
        from services.nlp_service import extract_entities

        mock_pipe = _make_ner_pipeline([])
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = extract_entities("This is a legal document with sufficient length.", {})

        assert result.persons == []
        assert result.organisations == []
        assert result.dates == []
        assert result.money == []
        assert result.locations == []
        assert result.case_numbers == []


# ---------------------------------------------------------------------------
# 2. Property: raw_entities dicts have all five required keys
# ---------------------------------------------------------------------------

class TestRawEntitiesKeys:
    """Property 4: raw_entities dicts have all five required keys."""

    REQUIRED_KEYS = {"text", "label", "score", "start", "end"}

    @given(text_st, ner_entities_st)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_raw_entities_have_required_keys_property(self, text, entities):
        """**Validates: Requirements 3 / Property 4**"""
        from services.nlp_service import extract_entities

        mock_pipe = _make_ner_pipeline(entities)
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = extract_entities(text, {})

        for ent in result.raw_entities:
            missing = self.REQUIRED_KEYS - set(ent.keys())
            assert not missing, (
                f"raw_entity missing keys: {missing}. Entity: {ent}"
            )

    def test_raw_entities_have_required_keys_example(self):
        from services.nlp_service import extract_entities

        entities = [
            {"word": "Acme Corp", "entity_group": "ORG", "score": 0.95, "start": 5, "end": 14},
        ]
        mock_pipe = _make_ner_pipeline(entities)
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = extract_entities("This is a legal document with sufficient length.", {})

        assert len(result.raw_entities) == 1
        ent = result.raw_entities[0]
        assert set(ent.keys()) >= self.REQUIRED_KEYS

    def test_raw_entities_text_field_populated(self):
        from services.nlp_service import extract_entities

        entities = [
            {"word": "John Smith", "entity_group": "PER", "score": 0.9, "start": 0, "end": 10},
        ]
        mock_pipe = _make_ner_pipeline(entities)
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = extract_entities("This is a legal document with sufficient length.", {})

        assert result.raw_entities[0]["text"] == "John Smith"
        assert result.raw_entities[0]["label"] == "PER"


# ---------------------------------------------------------------------------
# 3. Property: score in [0.0, 1.0]
# ---------------------------------------------------------------------------

class TestRawEntityScoreRange:
    """Property: score in raw_entities is always in [0.0, 1.0]."""

    @given(text_st, ner_entities_st)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_raw_entity_score_in_range_property(self, text, entities):
        """**Validates: Requirements 3 / Property 4**"""
        from services.nlp_service import extract_entities

        mock_pipe = _make_ner_pipeline(entities)
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = extract_entities(text, {})

        for ent in result.raw_entities:
            score = ent["score"]
            assert 0.0 <= score <= 1.0, (
                f"score {score} not in [0.0, 1.0]"
            )

    def test_score_in_range_example(self):
        from services.nlp_service import extract_entities

        entities = [
            {"word": "John", "entity_group": "PER", "score": 0.75, "start": 0, "end": 4},
            {"word": "Acme", "entity_group": "ORG", "score": 0.99, "start": 5, "end": 9},
        ]
        mock_pipe = _make_ner_pipeline(entities)
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = extract_entities("This is a legal document with sufficient length.", {})

        for ent in result.raw_entities:
            assert 0.0 <= ent["score"] <= 1.0


# ---------------------------------------------------------------------------
# 4. Merging with existing_fields
# ---------------------------------------------------------------------------

class TestMergeWithExistingFields:
    """Existing fields should be merged into the appropriate entity lists."""

    def test_existing_names_merged_into_persons(self):
        from services.nlp_service import extract_entities

        mock_pipe = _make_ner_pipeline([])
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = extract_entities(
                "This is a legal document with sufficient length.",
                {"names": ["Alice", "Bob"]},
            )

        assert "Alice" in result.persons
        assert "Bob" in result.persons

    def test_existing_dates_merged_into_dates(self):
        from services.nlp_service import extract_entities

        mock_pipe = _make_ner_pipeline([])
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = extract_entities(
                "This is a legal document with sufficient length.",
                {"dates": ["2024-01-01", "2024-06-15"]},
            )

        assert "2024-01-01" in result.dates
        assert "2024-06-15" in result.dates

    def test_existing_document_ids_become_case_numbers(self):
        from services.nlp_service import extract_entities

        mock_pipe = _make_ner_pipeline([])
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = extract_entities(
                "This is a legal document with sufficient length.",
                {"document_ids": ["CASE/001/2024"]},
            )

        assert "CASE/001/2024" in result.case_numbers

    def test_transformer_and_existing_fields_deduped(self):
        """If transformer and existing_fields both have the same name, it appears once."""
        from services.nlp_service import extract_entities

        entities = [
            {"word": "Alice", "entity_group": "PER", "score": 0.9, "start": 0, "end": 5},
        ]
        mock_pipe = _make_ner_pipeline(entities)
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = extract_entities(
                "This is a legal document with sufficient length.",
                {"names": ["Alice"]},
            )

        assert result.persons.count("Alice") == 1


# ---------------------------------------------------------------------------
# 5. Exception handling
# ---------------------------------------------------------------------------

class TestExceptionHandling:
    """Exception in pipeline must return empty EntityExtractionResult."""

    def test_pipeline_exception_returns_empty_result(self):
        from services.nlp_service import extract_entities

        mock_pipe = MagicMock(side_effect=RuntimeError("NER failed"))
        fake_transformers = _make_fake_transformers(MagicMock(return_value=mock_pipe))
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = extract_entities(
                "This is a legal document with sufficient length.", {}
            )

        assert result.persons == []
        assert result.organisations == []
        assert result.dates == []
        assert result.money == []
        assert result.locations == []
        assert result.case_numbers == []
        assert result.raw_entities == []

    def test_pipeline_load_exception_returns_empty_result(self):
        from services.nlp_service import extract_entities

        fake_transformers = _make_fake_transformers(
            MagicMock(side_effect=OSError("weights not found"))
        )
        with patch.dict(sys.modules, {"transformers": fake_transformers}):
            result = extract_entities(
                "This is a legal document with sufficient length.", {}
            )

        assert result.persons == []
        assert result.raw_entities == []


# ---------------------------------------------------------------------------
# 6. deduplicate helper
# ---------------------------------------------------------------------------

class TestDeduplicate:
    """Unit tests for the deduplicate helper function."""

    def test_removes_duplicates(self):
        from services.nlp_service import deduplicate
        assert deduplicate(["a", "b", "a", "c"]) == ["a", "b", "c"]

    def test_removes_empty_strings(self):
        from services.nlp_service import deduplicate
        assert deduplicate(["a", "", "b", ""]) == ["a", "b"]

    def test_strips_whitespace(self):
        from services.nlp_service import deduplicate
        assert deduplicate(["  a  ", "b", " a "]) == ["a", "b"]

    def test_preserves_first_occurrence_order(self):
        from services.nlp_service import deduplicate
        result = deduplicate(["c", "a", "b", "a", "c"])
        assert result == ["c", "a", "b"]

    def test_empty_list(self):
        from services.nlp_service import deduplicate
        assert deduplicate([]) == []

    def test_all_duplicates(self):
        from services.nlp_service import deduplicate
        assert deduplicate(["x", "x", "x"]) == ["x"]


# ---------------------------------------------------------------------------
# 7. group_by_label helper
# ---------------------------------------------------------------------------

class TestGroupByLabel:
    """Unit tests for the group_by_label helper function."""

    def test_groups_by_label(self):
        from services.nlp_service import group_by_label
        entities = [
            {"text": "John", "label": "PER", "score": 0.9, "start": 0, "end": 4},
            {"text": "Acme", "label": "ORG", "score": 0.8, "start": 5, "end": 9},
            {"text": "Jane", "label": "PER", "score": 0.7, "start": 10, "end": 14},
        ]
        result = group_by_label(entities)
        assert result["PER"] == ["John", "Jane"]
        assert result["ORG"] == ["Acme"]
        assert result["DATE"] == []
        assert result["MONEY"] == []
        assert result["GPE"] == []

    def test_unknown_label_ignored(self):
        from services.nlp_service import group_by_label
        entities = [
            {"text": "something", "label": "MISC", "score": 0.5, "start": 0, "end": 9},
        ]
        result = group_by_label(entities)
        # MISC is not a known label, should not appear
        assert "MISC" not in result
        assert all(v == [] for v in result.values())

    def test_empty_input(self):
        from services.nlp_service import group_by_label
        result = group_by_label([])
        assert result == {"PER": [], "ORG": [], "DATE": [], "MONEY": [], "GPE": []}
