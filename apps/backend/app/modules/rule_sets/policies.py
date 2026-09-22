"""Constrained expression language and evaluation policies for rule sets (Step 24)."""

from __future__ import annotations

import operator
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Evaluation:
    status: str  # "qualified", "disqualified", "incomplete"
    reason: str | None = None


def _isin(val: Any, container: Any) -> bool:
    if container is None:
        return False
    return val in container


OPS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "in": _isin,
}


MEDICARE_RS = {
    "all": [
        {"field": "medicare_part_ab", "operator": "==", "value": True},
        {"field": "age_in_range", "operator": "==", "value": True},
    ],
    "disqualificationReasons": {
        "medicare_part_ab": "disqualified_no_part_ab",
        "age_in_range": "disqualified_age_range",
    },
}


def evaluate(rule_set: dict[str, Any], fields: dict[str, Any]) -> Evaluation:
    """Evaluate a rule set against extracted call fields.

    Pure function: no eval, no Python code execution, no LLM.
    """
    conditions = rule_set.get("all", [])
    reasons = rule_set.get("disqualificationReasons", {})

    for cond in conditions:
        field_name = cond["field"]
        op_str = cond["operator"]
        target_val = cond["value"]

        val = fields.get(field_name)
        if val is None:
            return Evaluation("incomplete", f"missing:{field_name}")

        op_func = OPS.get(op_str)
        if not op_func:
            return Evaluation("disqualified", f"invalid_operator:{op_str}")

        if not op_func(val, target_val):
            disqual_reason = reasons.get(field_name, f"disqualified_{field_name}")
            return Evaluation("disqualified", disqual_reason)

    return Evaluation("qualified", None)
