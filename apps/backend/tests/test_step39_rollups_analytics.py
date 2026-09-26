"""Tests for STEP 39 — Rollups Engine & Analytics Query Isolation."""

from __future__ import annotations

from pathlib import Path


def test_no_analytics_query_hits_raw_calls():
    """Step 39 CI Requirement: No analytics endpoint touches raw calls table."""
    src = list(Path("app/modules/analytics").rglob("*.py"))
    assert len(src) > 0, "app/modules/analytics has no python source files"
    for f in src:
        t = f.read_text()
        assert "FROM calls" not in t and "select(Call)" not in t, (
            f"Raw calls table query found in {f}"
        )
