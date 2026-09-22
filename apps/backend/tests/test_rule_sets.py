"""Tests for STEP 24 — Rule sets evaluation engine."""

from __future__ import annotations

import pytest

from app.modules.rule_sets.policies import MEDICARE_RS, evaluate


@pytest.mark.parametrize(
    "part_ab,age,expected,reason",
    [
        (True, True, "qualified", None),
        (False, True, "disqualified", "disqualified_no_part_ab"),
        (True, False, "disqualified", "disqualified_age_range"),
        (False, False, "disqualified", "disqualified_no_part_ab"),  # first failure wins
        (None, True, "incomplete", "missing:medicare_part_ab"),
    ],
)
def test_medicare_rule_set(
    part_ab: bool | None, age: bool | None, expected: str, reason: str | None
):
    r = evaluate(MEDICARE_RS, {"medicare_part_ab": part_ab, "age_in_range": age})
    assert (r.status, r.reason) == (expected, reason)
