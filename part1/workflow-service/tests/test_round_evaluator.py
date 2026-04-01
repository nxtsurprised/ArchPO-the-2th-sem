"""
Unit tests for round_evaluator.evaluate_round.

Covers all 9 combinations from the spec + edge cases.
"""
from __future__ import annotations
from dataclasses import dataclass

import pytest

from app.services.round_evaluator import evaluate_round


@dataclass
class MockDecision:
    decision_type: str
    user_side: str


# ── Helper ─────────────────────────────────────────────────────────────────────

def decisions(*pairs) -> list[MockDecision]:
    """Build list of MockDecision from (decision_type, user_side) pairs."""
    return [MockDecision(decision_type=dt, user_side=side) for dt, side in pairs]


# ── All 9 combinations for tz_final ───────────────────────────────────────────

def test_both_approve():
    result = evaluate_round(decisions(("approve", "customer"), ("approve", "contractor")), "tz_final")
    assert result == "approved"


def test_customer_approve_contractor_revision():
    result = evaluate_round(decisions(("approve", "customer"), ("revision", "contractor")), "tz_final")
    assert result == "revision"


def test_customer_approve_contractor_reject():
    result = evaluate_round(decisions(("approve", "customer"), ("reject", "contractor")), "tz_final")
    assert result == "rejected"


def test_customer_revision_contractor_approve():
    result = evaluate_round(decisions(("revision", "customer"), ("approve", "contractor")), "tz_final")
    assert result == "revision"


def test_both_revision():
    result = evaluate_round(decisions(("revision", "customer"), ("revision", "contractor")), "tz_final")
    assert result == "revision"


def test_customer_reject_contractor_approve():
    result = evaluate_round(decisions(("reject", "customer"), ("approve", "contractor")), "tz_final")
    assert result == "rejected"


def test_both_reject():
    result = evaluate_round(decisions(("reject", "customer"), ("reject", "contractor")), "tz_final")
    assert result == "rejected"


def test_customer_revision_contractor_reject():
    result = evaluate_round(decisions(("revision", "customer"), ("reject", "contractor")), "tz_final")
    assert result == "rejected"


def test_customer_reject_contractor_revision():
    result = evaluate_round(decisions(("reject", "customer"), ("revision", "contractor")), "tz_final")
    assert result == "rejected"


# ── Still waiting ──────────────────────────────────────────────────────────────

def test_only_one_side_decided_returns_none():
    result = evaluate_round(decisions(("approve", "customer")), "tz_final")
    assert result is None


def test_empty_decisions_returns_none():
    result = evaluate_round([], "tz_final")
    assert result is None


# ── review type never closes ───────────────────────────────────────────────────

def test_review_type_always_returns_none():
    result = evaluate_round(
        decisions(("review", "customer"), ("review", "contractor")), "review"
    )
    assert result is None


# ── review decisions ignored for round closure ─────────────────────────────────

def test_review_decisions_ignored_in_tz_final():
    """Analysts submitting review do not count toward round closure."""
    result = evaluate_round(
        decisions(
            ("review", "customer"),   # analyst, informational
            ("approve", "customer"),  # pm
            ("approve", "contractor"),
        ),
        "tz_final",
    )
    assert result == "approved"


def test_review_alone_does_not_close_round():
    result = evaluate_round(
        decisions(("review", "customer"), ("approve", "customer")), "tz_final"
    )
    assert result is None  # contractor hasn't decided


# ── nmck_final same logic ──────────────────────────────────────────────────────

def test_nmck_both_approve():
    result = evaluate_round(decisions(("approve", "customer"), ("approve", "contractor")), "nmck_final")
    assert result == "approved"


def test_nmck_reject_wins():
    result = evaluate_round(decisions(("reject", "customer"), ("revision", "contractor")), "nmck_final")
    assert result == "rejected"


def test_nmck_one_side_returns_none():
    result = evaluate_round(decisions(("approve", "customer")), "nmck_final")
    assert result is None
