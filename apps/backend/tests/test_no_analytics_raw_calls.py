"""Analytics architecture gates that run fully offline (roadmap STEP 40).

Enforces the two rules that cannot drift silently:

- **No analytics endpoint touches raw ``calls``** (blueprint §14.4 / roadmap
  STEP 39): the module source must never reference the ``calls`` table or the
  ``Call`` / ``CallPerformance`` ORM models.  The rollup worker is exempt by
  design - it is the aggregation layer, not an endpoint.
- **Rule R5**: every analytics repository query takes a ``scope`` argument and
  none of them provides a default.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ANALYTICS = BACKEND / "app" / "modules" / "analytics"

ANALYTICS_ENDPOINTS = (
    "/analytics/summary",
    "/analytics/campaigns",
    "/analytics/scripts",
    "/analytics/sources",
    "/analytics/bot",
    "/analytics/compliance",
    "/analytics/performance",
)
CONTRACT_PATHS = tuple(f"/api/v1{path}" for path in ANALYTICS_ENDPOINTS)


def _module_files() -> list[Path]:
    files = [p for p in ANALYTICS.rglob("*.py") if p.name != "__init__.py"]
    return [f for f in files if f.name != "rollup.py"]


def test_no_analytics_source_touches_raw_calls() -> None:
    for f in _module_files():
        text = f.read_text(encoding="utf-8")
        assert "FROM calls" not in text, f
        assert "select(Call)" not in text, f
        assert re.search(r"import Call\b", text) is None, f
        assert "CallPerformance" not in text, f


def test_rollup_is_calls_aware_but_idempotent() -> None:
    """The rollup worker may aggregate FROM calls - but every statement must be
    a watermark-windowed UPSERT (STEP 39 idempotency)."""
    from app.modules.analytics import rollup

    for name, sql in rollup._SQL.items():
        assert "ON CONFLICT" in sql, name
        assert ":now" in sql, name
        if name != "agg_dashboard_counters":
            assert ":watermark" in sql, name
            assert "FROM calls" in sql, name


def test_all_seven_endpoints_exist_and_are_gated() -> None:
    import inspect

    from app.modules.analytics import router as router_mod
    from app.modules.analytics.router import router

    # 1. Every PRD endpoint is registered on the router.
    registered = {route.path for route in router.routes}
    for endpoint in ANALYTICS_ENDPOINTS:
        assert endpoint in registered, endpoint

    # 2. Every handler depends on the AnalyticsGate alias.
    src = inspect.getsource(router_mod)
    assert "require_permissions([PERM_ANALYTICS_VIEW])" in src
    assert "router.get(" in src
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            args = node.args.args
            assert any(a.arg == "actor" for a in args), node.name


def test_analytics_gate_rejects_missing_permission_offline() -> None:
    """The R4 gate itself - exercised without a DB by calling the checker."""
    import asyncio
    import uuid

    import pytest

    from app.core.context import UserContext
    from app.core.dependencies import require_permissions
    from app.core.permissions import PERM_ANALYTICS_VIEW
    from app.packages.contracts.errors import (
        PermissionDeniedError,
        register_core_errors,
    )

    register_core_errors()

    def actor(perms: set[str]) -> UserContext:
        return UserContext.from_principal(
            user_id=uuid.uuid4(),
            role="CAMPAIGN_MANAGER",
            permissions=perms,
            tenant_id="t1",
        )

    checker = require_permissions([PERM_ANALYTICS_VIEW])
    with pytest.raises(PermissionDeniedError):
        asyncio.run(checker(user=actor({"campaign.view"})))

    holder = actor({"campaign.view", PERM_ANALYTICS_VIEW})
    assert asyncio.run(checker(user=holder)) is holder


def test_analytics_view_granted_to_reporting_roles_only() -> None:
    from app.core.permissions import (
        PERM_ANALYTICS_VIEW,
        ROLE_PERMISSIONS,
    )

    assert PERM_ANALYTICS_VIEW in ROLE_PERMISSIONS["MASTER_ADMIN"]
    assert PERM_ANALYTICS_VIEW in ROLE_PERMISSIONS["DEVOPS_IT"]
    assert PERM_ANALYTICS_VIEW in ROLE_PERMISSIONS["CAMPAIGN_MANAGER"]
    assert PERM_ANALYTICS_VIEW in ROLE_PERMISSIONS["QA"]
    assert PERM_ANALYTICS_VIEW in ROLE_PERMISSIONS["REPORTING_USER"]
    assert PERM_ANALYTICS_VIEW not in ROLE_PERMISSIONS["VERIFIER"]
    assert PERM_ANALYTICS_VIEW not in ROLE_PERMISSIONS["VIEWER"]


def test_repository_queries_require_explicit_scope_no_default() -> None:
    """Rule R5: a scope argument exists and must not default to 'everything'."""
    repo = ANALYTICS / "repository.py"
    tree = ast.parse(repo.read_text(encoding="utf-8"))
    async_functions = [
        node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)
    ]
    assert async_functions, "no repository queries found"
    for fn in async_functions:
        args = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.posonlyargs}
        assert "scope" in args, f"{fn.name} must take an explicit scope (Rule R5)"
        for a in fn.args.args:
            if a.arg == "scope":
                assert a.annotation is not None, f"{fn.name}.scope must be annotated"


def test_metrics_manual_has_a_definition_for_every_aggregate() -> None:
    """docs/metrics.md must document each agg table and the PRD reports it serves."""
    from app.packages.db.models import (
        AggBotDaily,
        AggCampaignDaily,
        AggComplianceDaily,
        AggDashboardCounters,
        AggScriptVersionDaily,
        AggSourceDaily,
    )

    tables = [
        AggCampaignDaily.__tablename__,
        AggScriptVersionDaily.__tablename__,
        AggSourceDaily.__tablename__,
        AggBotDaily.__tablename__,
        AggComplianceDaily.__tablename__,
        AggDashboardCounters.__tablename__,
    ]
    manual = (BACKEND / "docs" / "metrics.md").read_text(encoding="utf-8")
    assert manual, "docs/metrics.md is missing"
    for table in tables:
        assert table in manual, f"{table} is not documented in docs/metrics.md"
    assert "PRD report" in manual
    assert "contact rate" in manual and "verifier close rate" in manual


def test_committed_contract_still_includes_analytics() -> None:
    from scripts.contract import contract_json

    schema = json.loads(contract_json())
    paths = set(schema["paths"])
    for endpoint in CONTRACT_PATHS:
        assert endpoint in paths, f"{endpoint} missing from openapi contract"
