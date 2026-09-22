"""Compliance profile policies and strict mode enforcement (Step 25)."""

from __future__ import annotations

from typing import Any

VALID_MODES: set[str] = {"enforce", "warn", "off"}
REQUIRED_OVERRIDE_CONFIRMATION = "CONFIRM_OVERRIDE"


def validate_mode_change(
    current_mode: str,
    target_mode: str,
    actor_role: str,
    confirmation: str | None,
    rationale: str | None,
) -> list[str]:
    """Validate compliance mode mutation rules (Step 25).

    Setting anything to warn or off requires MASTER_ADMIN, a typed confirmation,
    and a mandatory rationale.
    """
    errs: list[str] = []
    if target_mode not in VALID_MODES:
        return [f"Invalid compliance mode '{target_mode}'"]

    if target_mode in ("warn", "off") and current_mode != target_mode:
        if actor_role != "MASTER_ADMIN":
            errs.append(
                "Compliance rule degradation to warn or off requires MASTER_ADMIN role"
            )
        if confirmation != REQUIRED_OVERRIDE_CONFIRMATION:
            errs.append(
                f"Confirmation must match exact string '{REQUIRED_OVERRIDE_CONFIRMATION}'"
            )
        if not rationale or not rationale.strip():
            errs.append(
                "A non-empty rationale is mandatory when overriding compliance rules"
            )

    return errs


def compile_script_bundle(
    script_version: dict[str, Any],
    rule_set: dict[str, Any] | None = None,
    compliance_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile an active script version into a standalone JSON bundle for runtime Redis publishing."""
    return {
        "scriptVersionId": str(script_version.get("id")),
        "scriptId": str(script_version.get("script_id")),
        "version": script_version.get("version", 1),
        "entryNodeId": script_version.get("entry_node_id", "node-1"),
        "nodes": script_version.get("nodes", []),
        "ruleSet": rule_set or {},
        "complianceProfile": compliance_profile
        or {"rules": {"tpmo_disclaimer_precedes_benefits": "enforce"}},
    }
