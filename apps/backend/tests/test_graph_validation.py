"""Table-driven test for graph validation rules (Step 21)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.scripts.policies import validate_graph

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "graph"


class StrictComplianceProfile:
    def rule(self, name: str) -> str:
        if name == "tpmo_disclaimer_precedes_benefits":
            return "enforce"
        return "off"


STRICT = StrictComplianceProfile()


def load_fixture(name: str):
    path = FIXTURES_DIR / name
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["nodes"], data["entryId"]


@pytest.mark.parametrize(
    "fixture,expected",
    [
        ("valid_medicare.json", []),
        ("dangling_transition.json", ["DANGLING_TRANSITION"]),
        ("unreachable_node.json", ["UNREACHABLE"]),
        ("dead_end.json", ["DEAD_END"]),
        ("benefits_first.json", ["BENEFITS_BEFORE_DISCLAIMER"]),
    ],
)
def test_graph_validation(fixture: str, expected: list[str]):
    nodes, entry_id = load_fixture(fixture)
    errs = validate_graph(nodes, entry_id, profile=STRICT)
    codes = [e.code for e in errs]
    assert sorted(codes) == sorted(expected)
