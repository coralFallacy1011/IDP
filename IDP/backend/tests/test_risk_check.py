"""
Property-based and unit tests for ``nlp_service.risk_check``.

Tests cover:
  - ``score`` in [0.0, 1.0]
  - ``risk_level`` in valid set {"low", "medium", "high"}
  - ``risk_level`` is consistent with ``score`` thresholds
  - Missing required clauses produce flags
  - Risk flags are well-formed (non-empty category and description)
  - Exception returns ``RiskResult("low", [], 0.0)``

No ML pipelines are used — risk_check is pure logic.

**Validates: Requirements 8 / Properties 8, 9, 10**
"""

from __future__ import annotations

import sys
import os
from unittest.mock import patch

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
# Strategies
# ---------------------------------------------------------------------------

from services.nlp_service import (
    LEGAL_DOC_TYPES,
    LEGAL_CLAUSE_LABELS,
    REQUIRED_CLAUSES_BY_TYPE,
    RISK_WEIGHTS,
    UNUSUAL_LEGAL_TERMS,
)

# Strategy for doc_type
doc_type_st = st.sampled_from(LEGAL_DOC_TYPES)

# Strategy for clauses_found (subset of LEGAL_CLAUSE_LABELS)
clauses_found_st = st.lists(
    st.sampled_from(LEGAL_CLAUSE_LABELS),
    min_size=0,
    max_size=len(LEGAL_CLAUSE_LABELS),
    unique=True,
)

# Strategy for fields dict
fields_st = st.fixed_dictionaries({
    "names": st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=5),
    "dates": st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=3),
})

# Strategy for text
text_st = st.text(min_size=0, max_size=200)


# ---------------------------------------------------------------------------
# 1. Property: score in [0.0, 1.0]
# ---------------------------------------------------------------------------

class TestScoreInRange:
    """Property 8: score is always in [0.0, 1.0]."""

    @given(text_st, fields_st, doc_type_st, clauses_found_st)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_score_in_range_property(self, text, fields, doc_type, clauses_found):
        """**Validates: Requirements 8 / Property 8**"""
        from services.nlp_service import risk_check

        result = risk_check(text, fields, doc_type, clauses_found)
        assert 0.0 <= result.score <= 1.0, (
            f"score {result.score} not in [0.0, 1.0]"
        )

    def test_score_in_range_no_risks(self):
        from services.nlp_service import risk_check

        result = risk_check("simple text", {}, "FIR", [])
        assert 0.0 <= result.score <= 1.0

    def test_score_in_range_all_risks(self):
        from services.nlp_service import risk_check

        # Trigger all risk checks
        result = risk_check(
            "notwithstanding hereinafter whereas indemnify subrogation estoppel tortious malfeasance",
            {"names": [], "dates": ["2024-12-01", "2020-01-01"]},
            "contract",
            [],  # no clauses found → all required clauses missing
        )
        assert 0.0 <= result.score <= 1.0

    def test_score_capped_at_1_0(self):
        """Score must never exceed 1.0 even when many risks are triggered."""
        from services.nlp_service import risk_check

        # Trigger all checks: missing clauses + date inconsistency + missing party + unusual terms
        result = risk_check(
            "notwithstanding hereinafter whereas indemnify subrogation estoppel tortious malfeasance",
            {"names": [], "dates": ["2025-01-01", "2020-01-01"]},
            "contract",
            [],
        )
        assert result.score <= 1.0


# ---------------------------------------------------------------------------
# 2. Property: risk_level in valid set
# ---------------------------------------------------------------------------

class TestRiskLevelValid:
    """Property 9: risk_level is always one of "low", "medium", "high"."""

    VALID_LEVELS = {"low", "medium", "high"}

    @given(text_st, fields_st, doc_type_st, clauses_found_st)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_risk_level_in_valid_set_property(self, text, fields, doc_type, clauses_found):
        """**Validates: Requirements 8 / Property 9**"""
        from services.nlp_service import risk_check

        result = risk_check(text, fields, doc_type, clauses_found)
        assert result.risk_level in self.VALID_LEVELS, (
            f"risk_level '{result.risk_level}' not in {self.VALID_LEVELS}"
        )

    def test_risk_level_low_example(self):
        from services.nlp_service import risk_check

        result = risk_check("simple text", {}, "FIR", [])
        assert result.risk_level == "low"

    def test_risk_level_high_example(self):
        from services.nlp_service import risk_check

        # Missing 3 required clauses for contract → 3 * 0.25 = 0.75 → high
        result = risk_check("simple text", {"names": ["A", "B"]}, "contract", [])
        assert result.risk_level == "high"


# ---------------------------------------------------------------------------
# 3. Property: risk_level consistent with score thresholds
# ---------------------------------------------------------------------------

class TestRiskLevelConsistentWithScore:
    """Property 10: risk_level is consistent with score thresholds."""

    @given(text_st, fields_st, doc_type_st, clauses_found_st)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_risk_level_consistent_with_score_property(self, text, fields, doc_type, clauses_found):
        """**Validates: Requirements 8 / Property 10**"""
        from services.nlp_service import risk_check

        result = risk_check(text, fields, doc_type, clauses_found)
        score = result.score
        level = result.risk_level

        if score < 0.25:
            assert level == "low", (
                f"score {score} < 0.25 should be 'low', got '{level}'"
            )
        elif score < 0.60:
            assert level == "medium", (
                f"score {score} in [0.25, 0.60) should be 'medium', got '{level}'"
            )
        else:
            assert level == "high", (
                f"score {score} >= 0.60 should be 'high', got '{level}'"
            )

    def test_score_0_is_low(self):
        from services.nlp_service import risk_check

        result = risk_check("simple text", {}, "FIR", [])
        assert result.risk_level == "low"
        assert result.score < 0.25

    def test_score_0_25_is_medium(self):
        from services.nlp_service import risk_check

        # One missing clause for contract → 0.25 → medium
        result = risk_check(
            "simple text",
            {"names": ["A", "B"]},
            "contract",
            ["termination clause", "jurisdiction clause"],  # missing payment terms
        )
        assert result.score == pytest.approx(0.25)
        assert result.risk_level == "medium"

    def test_score_0_60_is_high(self):
        from services.nlp_service import risk_check

        # Missing 3 clauses for contract → 0.75 → high
        result = risk_check(
            "simple text",
            {"names": ["A", "B"]},
            "contract",
            [],
        )
        assert result.score >= 0.60
        assert result.risk_level == "high"


# ---------------------------------------------------------------------------
# 4. Missing clauses produce flags
# ---------------------------------------------------------------------------

class TestMissingClausesProduceFlags:
    """Missing required clauses must produce risk flags."""

    def test_missing_clause_produces_flag(self):
        from services.nlp_service import risk_check

        # contract requires termination, jurisdiction, payment terms
        result = risk_check(
            "simple text",
            {"names": ["A", "B"]},
            "contract",
            [],  # no clauses found
        )
        missing_clause_flags = [
            f for f in result.flags if f.category == "missing_clause"
        ]
        assert len(missing_clause_flags) == 3  # all 3 required clauses missing

    def test_present_clause_does_not_produce_flag(self):
        from services.nlp_service import risk_check

        result = risk_check(
            "simple text",
            {"names": ["A", "B"]},
            "contract",
            ["termination clause", "jurisdiction clause", "payment terms clause"],
        )
        missing_clause_flags = [
            f for f in result.flags if f.category == "missing_clause"
        ]
        assert len(missing_clause_flags) == 0

    def test_fir_has_no_required_clauses(self):
        from services.nlp_service import risk_check

        result = risk_check("simple text", {}, "FIR", [])
        missing_clause_flags = [
            f for f in result.flags if f.category == "missing_clause"
        ]
        assert len(missing_clause_flags) == 0

    @given(clauses_found_st)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_missing_clauses_count_correct_property(self, clauses_found):
        """**Validates: Requirements 8 / Property 10**"""
        from services.nlp_service import risk_check, REQUIRED_CLAUSES_BY_TYPE

        doc_type = "contract"
        required = REQUIRED_CLAUSES_BY_TYPE[doc_type]
        expected_missing = [c for c in required if c not in clauses_found]

        result = risk_check(
            "simple text",
            {"names": ["A", "B"]},
            doc_type,
            clauses_found,
        )
        missing_clause_flags = [
            f for f in result.flags if f.category == "missing_clause"
        ]
        assert len(missing_clause_flags) == len(expected_missing)


# ---------------------------------------------------------------------------
# 5. Risk flags are well-formed
# ---------------------------------------------------------------------------

class TestRiskFlagsWellFormed:
    """Property: risk flags have non-empty category and description."""

    @given(text_st, fields_st, doc_type_st, clauses_found_st)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_risk_flags_well_formed_property(self, text, fields, doc_type, clauses_found):
        """**Validates: Requirements 8 / Property 10**"""
        from services.nlp_service import risk_check

        result = risk_check(text, fields, doc_type, clauses_found)
        for flag in result.flags:
            assert flag.category, "flag.category must be non-empty"
            assert flag.description, "flag.description must be non-empty"
            assert flag.severity in {"warning", "error"}, (
                f"flag.severity '{flag.severity}' not in {{warning, error}}"
            )

    def test_missing_clause_flag_has_correct_category(self):
        from services.nlp_service import risk_check

        result = risk_check("simple text", {"names": ["A", "B"]}, "contract", [])
        for flag in result.flags:
            if flag.category == "missing_clause":
                assert "termination clause" in flag.description or \
                       "jurisdiction clause" in flag.description or \
                       "payment terms clause" in flag.description

    def test_unusual_term_flag_has_correct_category(self):
        from services.nlp_service import risk_check

        result = risk_check("notwithstanding the above", {}, "FIR", [])
        unusual_flags = [f for f in result.flags if f.category == "unusual_term"]
        assert len(unusual_flags) >= 1
        assert "notwithstanding" in unusual_flags[0].description

    def test_missing_party_flag_for_contract(self):
        from services.nlp_service import risk_check

        result = risk_check(
            "simple text",
            {"names": []},  # no names
            "contract",
            ["termination clause", "jurisdiction clause", "payment terms clause"],
        )
        party_flags = [f for f in result.flags if f.category == "missing_party"]
        assert len(party_flags) == 1

    def test_no_missing_party_flag_for_fir(self):
        from services.nlp_service import risk_check

        result = risk_check("simple text", {"names": []}, "FIR", [])
        party_flags = [f for f in result.flags if f.category == "missing_party"]
        assert len(party_flags) == 0


# ---------------------------------------------------------------------------
# 6. Date inconsistency check
# ---------------------------------------------------------------------------

class TestDateInconsistency:
    """Date inconsistency check should flag future-before-past ordering."""

    def test_inconsistent_dates_produce_flag(self):
        from services.nlp_service import risk_check

        # Later date listed before earlier date
        result = risk_check(
            "simple text",
            {"dates": ["2025-01-01", "2020-01-01"]},
            "FIR",
            [],
        )
        date_flags = [f for f in result.flags if f.category == "date_inconsistency"]
        assert len(date_flags) == 1

    def test_consistent_dates_no_flag(self):
        from services.nlp_service import risk_check

        # Earlier date listed before later date (consistent)
        result = risk_check(
            "simple text",
            {"dates": ["2020-01-01", "2025-01-01"]},
            "FIR",
            [],
        )
        date_flags = [f for f in result.flags if f.category == "date_inconsistency"]
        assert len(date_flags) == 0

    def test_single_date_no_flag(self):
        from services.nlp_service import risk_check

        result = risk_check(
            "simple text",
            {"dates": ["2024-01-01"]},
            "FIR",
            [],
        )
        date_flags = [f for f in result.flags if f.category == "date_inconsistency"]
        assert len(date_flags) == 0


# ---------------------------------------------------------------------------
# 7. Exception handling
# ---------------------------------------------------------------------------

class TestExceptionHandling:
    """Exception must return RiskResult("low", [], 0.0)."""

    def test_exception_returns_safe_default(self):
        from services.nlp_service import risk_check

        # Pass a non-dict fields to trigger an exception
        with patch("services.nlp_service.REQUIRED_CLAUSES_BY_TYPE", side_effect=Exception("boom")):
            # This won't actually trigger the side_effect, so let's use a different approach
            pass

        # Directly test by passing invalid types that cause exceptions
        result = risk_check(None, {}, "contract", [])  # type: ignore
        # Should return safe default
        assert result.risk_level == "low"
        assert result.flags == []
        assert result.score == 0.0

    def test_safe_default_structure(self):
        from services.nlp_service import risk_check, RiskResult

        # Trigger exception with None text
        result = risk_check(None, {}, "contract", [])  # type: ignore
        assert isinstance(result, RiskResult)
        assert result.risk_level == "low"
        assert result.score == 0.0


# ---------------------------------------------------------------------------
# 8. Constants
# ---------------------------------------------------------------------------

class TestConstants:
    """Verify the risk_check constants are correctly defined."""

    def test_required_clauses_by_type_has_expected_keys(self):
        from services.nlp_service import REQUIRED_CLAUSES_BY_TYPE
        assert "contract" in REQUIRED_CLAUSES_BY_TYPE
        assert "agreement" in REQUIRED_CLAUSES_BY_TYPE
        assert "FIR" in REQUIRED_CLAUSES_BY_TYPE
        assert "affidavit" in REQUIRED_CLAUSES_BY_TYPE

    def test_contract_requires_three_clauses(self):
        from services.nlp_service import REQUIRED_CLAUSES_BY_TYPE
        assert len(REQUIRED_CLAUSES_BY_TYPE["contract"]) == 3

    def test_fir_requires_no_clauses(self):
        from services.nlp_service import REQUIRED_CLAUSES_BY_TYPE
        assert REQUIRED_CLAUSES_BY_TYPE["FIR"] == []

    def test_risk_weights_sum_to_one(self):
        from services.nlp_service import RISK_WEIGHTS
        # The four weights should sum to 1.0
        assert abs(sum(RISK_WEIGHTS.values()) - 1.0) < 0.01

    def test_unusual_legal_terms_non_empty(self):
        from services.nlp_service import UNUSUAL_LEGAL_TERMS
        assert len(UNUSUAL_LEGAL_TERMS) > 0
        assert all(isinstance(t, str) for t in UNUSUAL_LEGAL_TERMS)
