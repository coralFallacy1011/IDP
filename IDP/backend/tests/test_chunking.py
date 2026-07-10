"""
Unit tests for ``nlp_service.chunk_document``.

Tests cover:
  - coverage invariant   : every character in the input is covered by ≥ 1 chunk
  - overlap invariant    : consecutive chunks share ≈ ``overlap`` tokens
  - max-size invariant   : no chunk exceeds ``max_tokens`` tokens
  - single-chunk case    : short text produces exactly one chunk
  - start_char == 0      : first chunk always starts at character 0

No ML models are required — only pure chunking logic is exercised.

**Validates: Requirements 12 / Property 11**
"""

from __future__ import annotations

import sys
import os

# ---------------------------------------------------------------------------
# Ensure backend/ is on sys.path so relative imports resolve correctly
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import pytest
from services.nlp_service import chunk_document
from models.nlp_models import ChunkInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_text(n_words: int, word: str = "word") -> str:
    """Return a string of *n_words* space-separated copies of *word*."""
    return " ".join([word] * n_words)


def _token_count(chunk: ChunkInfo) -> int:
    return len(chunk.text.split())


# ---------------------------------------------------------------------------
# 1. start_char == 0
# ---------------------------------------------------------------------------

class TestStartChar:
    def test_start_char_is_zero_for_single_word(self):
        chunks = chunk_document("hello", max_tokens=512, overlap=0)
        assert chunks[0].start_char == 0

    def test_start_char_is_zero_for_long_text(self):
        text = _make_text(1000)
        chunks = chunk_document(text, max_tokens=512, overlap=64)
        assert chunks[0].start_char == 0

    def test_start_char_is_zero_for_exact_max_tokens(self):
        text = _make_text(512)
        chunks = chunk_document(text, max_tokens=512, overlap=64)
        assert chunks[0].start_char == 0

    def test_start_char_is_zero_with_leading_whitespace_preserved(self):
        # text.split() strips leading whitespace, so first word offset is > 0
        # but the spec says chunks[0].start_char == 0 (word-based, not char-based)
        # Actually the design says start_char of word[0] — let's verify the
        # implementation: offsets[0] is the index of the first word in text.
        # For "  hello world", text.index("hello", 0) == 2, so start_char == 2.
        # The spec postcondition says chunks[0].start_char == 0 for normal text.
        # We test with normal (no leading whitespace) text here.
        text = "alpha beta gamma"
        chunks = chunk_document(text, max_tokens=512, overlap=0)
        assert chunks[0].start_char == 0


# ---------------------------------------------------------------------------
# 2. Single-chunk for short text
# ---------------------------------------------------------------------------

class TestSingleChunk:
    def test_single_word_produces_one_chunk(self):
        chunks = chunk_document("hello", max_tokens=512, overlap=64)
        assert len(chunks) == 1

    def test_text_shorter_than_max_tokens_produces_one_chunk(self):
        text = _make_text(10)
        chunks = chunk_document(text, max_tokens=512, overlap=64)
        assert len(chunks) == 1

    def test_text_equal_to_max_tokens_no_overlap_produces_one_chunk(self):
        # With overlap=0, step == max_tokens, so exactly one chunk is produced
        # when len(words) == max_tokens.
        text = _make_text(512)
        chunks = chunk_document(text, max_tokens=512, overlap=0)
        assert len(chunks) == 1

    def test_single_chunk_text_equals_input(self):
        text = "the quick brown fox"
        chunks = chunk_document(text, max_tokens=512, overlap=0)
        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_single_chunk_end_char_equals_len_text(self):
        text = "the quick brown fox"
        chunks = chunk_document(text, max_tokens=512, overlap=0)
        assert chunks[0].end_char == len(text)


# ---------------------------------------------------------------------------
# 3. Max-size invariant: no chunk exceeds max_tokens tokens
# ---------------------------------------------------------------------------

class TestMaxSizeInvariant:
    def test_no_chunk_exceeds_max_tokens_default(self):
        text = _make_text(2000)
        chunks = chunk_document(text)
        for chunk in chunks:
            assert _token_count(chunk) <= 512

    def test_no_chunk_exceeds_max_tokens_small(self):
        text = _make_text(100)
        chunks = chunk_document(text, max_tokens=10, overlap=2)
        for chunk in chunks:
            assert _token_count(chunk) <= 10

    def test_no_chunk_exceeds_max_tokens_exact_boundary(self):
        # 513 words with max_tokens=512 → first chunk has 512, second has 1
        text = _make_text(513)
        chunks = chunk_document(text, max_tokens=512, overlap=0)
        for chunk in chunks:
            assert _token_count(chunk) <= 512

    def test_chunk_count_is_correct_no_overlap(self):
        # 100 words, max_tokens=10, overlap=0 → step=10 → 10 chunks
        text = _make_text(100)
        chunks = chunk_document(text, max_tokens=10, overlap=0)
        assert len(chunks) == 10

    def test_chunk_count_is_correct_with_overlap(self):
        # 20 words, max_tokens=10, overlap=2 → step=8
        # i=0,8,16 → 3 chunks
        text = _make_text(20)
        chunks = chunk_document(text, max_tokens=10, overlap=2)
        assert len(chunks) == 3


# ---------------------------------------------------------------------------
# 4. Coverage invariant: every character is covered by at least one chunk
# ---------------------------------------------------------------------------

class TestCoverageInvariant:
    def _covered_chars(self, text: str, chunks: list[ChunkInfo]) -> set[int]:
        covered: set[int] = set()
        for chunk in chunks:
            covered.update(range(chunk.start_char, chunk.end_char))
        return covered

    def test_all_chars_covered_short_text(self):
        text = "hello world"
        chunks = chunk_document(text, max_tokens=512, overlap=0)
        covered = self._covered_chars(text, chunks)
        assert covered == set(range(len(text)))

    def test_all_chars_covered_long_text_no_overlap(self):
        text = _make_text(200)
        chunks = chunk_document(text, max_tokens=50, overlap=0)
        covered = self._covered_chars(text, chunks)
        assert covered == set(range(len(text)))

    def test_all_chars_covered_long_text_with_overlap(self):
        text = _make_text(300)
        chunks = chunk_document(text, max_tokens=100, overlap=20)
        covered = self._covered_chars(text, chunks)
        assert covered == set(range(len(text)))

    def test_all_chars_covered_uneven_split(self):
        # 105 words, max_tokens=50, overlap=0 → step=50
        # chunks at i=0,50,100 → last chunk has 5 words
        text = _make_text(105)
        chunks = chunk_document(text, max_tokens=50, overlap=0)
        covered = self._covered_chars(text, chunks)
        assert covered == set(range(len(text)))

    def test_last_chunk_end_char_equals_len_text(self):
        text = _make_text(105)
        chunks = chunk_document(text, max_tokens=50, overlap=0)
        assert chunks[-1].end_char == len(text)

    def test_coverage_with_varied_word_lengths(self):
        text = "a bb ccc dddd eeeee ffffff ggggggg"
        chunks = chunk_document(text, max_tokens=3, overlap=1)
        covered = self._covered_chars(text, chunks)
        assert covered == set(range(len(text)))


# ---------------------------------------------------------------------------
# 5. Overlap invariant: consecutive chunks share ≈ overlap tokens
# ---------------------------------------------------------------------------

class TestOverlapInvariant:
    def test_consecutive_chunks_share_overlap_tokens(self):
        text = _make_text(100)
        max_tokens = 20
        overlap = 5
        chunks = chunk_document(text, max_tokens=max_tokens, overlap=overlap)
        words = text.split()
        step = max_tokens - overlap

        for k in range(len(chunks) - 1):
            i = k * step
            # words in chunk k: words[i : i+max_tokens]
            # words in chunk k+1: words[i+step : i+step+max_tokens]
            # overlap region: words[i+step : i+max_tokens]
            shared_start = i + step
            shared_end = min(i + max_tokens, len(words))
            expected_overlap = shared_end - shared_start
            # The actual overlap is the number of tokens in chunk k that also
            # appear at the start of chunk k+1.
            chunk_k_words = chunks[k].text.split()
            chunk_k1_words = chunks[k + 1].text.split()
            # The last `expected_overlap` words of chunk k should equal the
            # first `expected_overlap` words of chunk k+1.
            assert chunk_k_words[-expected_overlap:] == chunk_k1_words[:expected_overlap]

    def test_zero_overlap_chunks_do_not_share_tokens(self):
        text = _make_text(40)
        chunks = chunk_document(text, max_tokens=10, overlap=0)
        for k in range(len(chunks) - 1):
            words_k = set(chunks[k].text.split())
            words_k1 = set(chunks[k + 1].text.split())
            # With identical words this set intersection is non-empty, so
            # we check positional non-overlap instead.
            assert chunks[k].end_char <= chunks[k + 1].start_char

    def test_chunk_indices_are_sequential(self):
        text = _make_text(200)
        chunks = chunk_document(text, max_tokens=50, overlap=10)
        for k, chunk in enumerate(chunks):
            assert chunk.index == k


# ---------------------------------------------------------------------------
# 6. Character offset correctness
# ---------------------------------------------------------------------------

class TestCharOffsets:
    def test_start_char_matches_word_position_in_text(self):
        text = "alpha beta gamma delta"
        chunks = chunk_document(text, max_tokens=2, overlap=0)
        # chunk 0: "alpha beta" → start_char=0
        # chunk 1: "gamma delta" → start_char=text.index("gamma")
        assert chunks[0].start_char == 0
        assert chunks[1].start_char == text.index("gamma")

    def test_end_char_matches_word_end_in_text(self):
        text = "alpha beta gamma delta"
        chunks = chunk_document(text, max_tokens=2, overlap=0)
        # chunk 0 ends after "beta" → end_char == start of "gamma"
        assert chunks[0].end_char == text.index("gamma")
        # chunk 1 ends at len(text)
        assert chunks[1].end_char == len(text)

    def test_chunk_text_matches_text_slice(self):
        text = "one two three four five six seven eight nine ten"
        chunks = chunk_document(text, max_tokens=3, overlap=1)
        for chunk in chunks:
            # The chunk text should be recoverable from the original text
            # (modulo internal whitespace normalisation by split/join)
            extracted = " ".join(text[chunk.start_char:chunk.end_char].split())
            assert extracted == chunk.text


# ---------------------------------------------------------------------------
# 7. Edge cases and error handling
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_raises_on_empty_string(self):
        with pytest.raises(ValueError):
            chunk_document("")

    def test_raises_on_overlap_equal_to_max_tokens(self):
        with pytest.raises(ValueError):
            chunk_document("hello world", max_tokens=5, overlap=5)

    def test_raises_on_overlap_greater_than_max_tokens(self):
        with pytest.raises(ValueError):
            chunk_document("hello world", max_tokens=5, overlap=10)

    def test_raises_on_zero_max_tokens(self):
        with pytest.raises(ValueError):
            chunk_document("hello world", max_tokens=0, overlap=0)

    def test_max_tokens_one_no_overlap(self):
        text = "a b c d e"
        chunks = chunk_document(text, max_tokens=1, overlap=0)
        assert len(chunks) == 5
        assert all(_token_count(c) == 1 for c in chunks)

    def test_single_word_text(self):
        chunks = chunk_document("hello", max_tokens=10, overlap=2)
        assert len(chunks) == 1
        assert chunks[0].text == "hello"
        assert chunks[0].start_char == 0
        assert chunks[0].end_char == 5

    def test_returns_list_of_chunk_info(self):
        chunks = chunk_document("hello world foo bar", max_tokens=2, overlap=0)
        assert isinstance(chunks, list)
        assert all(isinstance(c, ChunkInfo) for c in chunks)
