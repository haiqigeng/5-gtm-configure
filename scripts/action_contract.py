"""Action-specific object contracts shared by contract and run validation."""

from __future__ import annotations

from typing import Any, Callable

from run_model import DELTA_ACTIONS, MUTATING_ACTIONS
from verification import canonical_sha256


def _non_empty_object(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_native_authoring(family, intended, *, path, fail):
    """Reject demonstrated non-native write forms, without rewriting saved objects."""
    if not isinstance(intended, dict):
        return
    if family == "trigger":
        for field in ("customEventFilter", "filter", "autoEventFilter"):
            if field in intended and (
                not isinstance(intended[field], list)
                or any(
                    not isinstance(row, dict)
                    or not isinstance(row.get("parameter"), list)
                    or not row.get("type")
                    for row in intended[field]
                )
            ):
                fail(f"{path}.{field} requires native Condition objects")
    if family == "tag" and intended.get("type") == "gaawe":
        parameters = intended.get("parameter", [])
        keys = (
            {row.get("key") for row in parameters if isinstance(row, dict)}
            if isinstance(parameters, list)
            else set()
        )
        if {"eventParameters", "sendEcommerce"} & (set(intended) | keys):
            fail(
                f"{path} uses obsolete GA4 authoring fields; use eventSettingsTable and sendEcommerceData"
            )
        for row in parameters if isinstance(parameters, list) else []:
            if not isinstance(row, dict):
                fail(f"{path}.parameter requires native Parameter objects")
                continue
            if row.get("key") == "sendEcommerceData" and (
                str(row.get("type", "")).lower() != "boolean"
                or row.get("value") not in {"true", "false"}
            ):
                fail(f"{path}.sendEcommerceData requires native BOOLEAN true/false")
            if row.get("key") != "eventSettingsTable":
                continue
            if str(row.get("type", "")).lower() != "list" or not isinstance(row.get("list"), list):
                fail(f"{path}.eventSettingsTable requires a native LIST")
                continue
            for cell in row["list"]:
                fields = cell.get("map", []) if isinstance(cell, dict) else []
                if (
                    not isinstance(cell, dict)
                    or str(cell.get("type", "")).lower() != "map"
                    or not isinstance(fields, list)
                    or {entry.get("key") for entry in fields if isinstance(entry, dict)}
                    != {"parameter", "parameterValue"}
                ):
                    fail(
                        f"{path}.eventSettingsTable rows require parameter/parameterValue MAP cells"
                    )


def mutation_approval_projection(item: dict[str, Any]) -> dict[str, Any]:
    """Return the exact mutation dimensions that approved input must bind."""
    projection = {
        "object_key": item.get("object_key"),
        "action": item.get("action"),
        "requirement_ids": sorted(item.get("requirement_ids", [])),
    }
    for field in (
        "object_id",
        "intended",
        "pre_change",
        "new_name",
        "replacement_reason",
        "permission_delta",
        "public_identifiers",
        "scope",
    ):
        if field in item:
            projection[field] = item[field]
    return projection


def build_mutation_approval(item: dict[str, Any], locator: str) -> dict[str, Any]:
    """Record source traceability and payload consistency, not independent authorization."""
    return {
        "grade": "approved-input",
        "locator": locator,
        "object_key": item.get("object_key"),
        "action": item.get("action"),
        "requirement_ids": sorted(item.get("requirement_ids", [])),
        "payload_sha256": canonical_sha256(mutation_approval_projection(item)),
    }


def validate_action_contract(
    item: dict[str, Any],
    *,
    path: str,
    fail: Callable[[str], None],
    authority_locators: set[str] | None = None,
) -> None:
    """Check action state and authority traceability; source authenticity is a host/agent duty."""
    action = item.get("action")
    family = item.get("resource_family") or item.get("object_type")

    if action in MUTATING_ACTIONS - {"remove"}:
        validate_native_authoring(family, item.get("intended", {}), path=path, fail=fail)

    if action in MUTATING_ACTIONS - {"remove"} or action in {"reuse", "untouched"}:
        if not _non_empty_object(item.get("intended")):
            fail(f"{path}.intended must be a non-empty object for action {action!r}")

    if action in DELTA_ACTIONS:
        if not _non_empty_text(item.get("object_id")):
            fail(f"{path}.object_id is required for delta action {action!r}")
        if not _non_empty_object(item.get("pre_change")):
            fail(f"{path}.pre_change must be a non-empty object for delta action {action!r}")

    if family in {"tag", "trigger", "variable", "client", "transformation"}:
        snapshots = ["pre_change"] if action == "remove" else ["intended"]
        if action in DELTA_ACTIONS and action != "remove":
            snapshots.append("pre_change")
        for snapshot in snapshots:
            if not _non_empty_text((item.get(snapshot) or {}).get("type")):
                fail(
                    f"{path}.{snapshot}.type is required; use complete object snapshots, not patches"
                )

    if action == "rename" and not _non_empty_text(item.get("new_name")):
        fail(f"{path}.new_name is required for rename")

    if action in {"pause", "unpause"}:
        expected_paused = action == "pause"
        if item.get("intended", {}).get("paused") is not expected_paused:
            fail(f"{path}.intended.paused must be {str(expected_paused).lower()} for {action}")

    if action in MUTATING_ACTIONS:
        approval = item.get("approval")
        if not isinstance(approval, dict) or set(approval) != {
            "grade",
            "locator",
            "object_key",
            "action",
            "requirement_ids",
            "payload_sha256",
        }:
            fail(f"{path}.approval must bind the exact approved mutation")
        else:
            expected = build_mutation_approval(item, str(approval.get("locator", "")))
            if approval != expected or approval.get("grade") != "approved-input":
                fail(f"{path}.approval differs from the exact mutation projection")
            if authority_locators is not None and approval.get("locator") not in authority_locators:
                fail(f"{path}.approval.locator is not an approved linked requirement source")

    if action == "replace" and not _non_empty_text(item.get("replacement_reason")):
        fail(f"{path}.replacement_reason is required for replace")

    if family == "template" and action in MUTATING_ACTIONS:
        permission_delta = item.get("permission_delta")
        if not isinstance(permission_delta, dict):
            fail(f"{path}.permission_delta is required for a template mutation")
