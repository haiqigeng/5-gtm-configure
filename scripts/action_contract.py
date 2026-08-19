"""Action-specific object contracts shared by contract and run validation."""

from __future__ import annotations

from typing import Any, Callable

from run_model import DELTA_ACTIONS, MUTATING_ACTIONS


def _non_empty_object(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_action_contract(
    item: dict[str, Any],
    *,
    path: str,
    fail: Callable[[str], None],
) -> None:
    """Reject an action that lacks the exact state or authority needed to execute it."""
    action = item.get("action")
    family = item.get("resource_family") or item.get("object_type")

    if action in MUTATING_ACTIONS - {"remove"} or action in {"reuse", "untouched"}:
        if not _non_empty_object(item.get("intended")):
            fail(f"{path}.intended must be a non-empty object for action {action!r}")

    if action in DELTA_ACTIONS:
        if not _non_empty_text(item.get("object_id")):
            fail(f"{path}.object_id is required for delta action {action!r}")
        if not _non_empty_object(item.get("pre_change")):
            fail(f"{path}.pre_change must be a non-empty object for delta action {action!r}")

    if action == "rename" and not _non_empty_text(item.get("new_name")):
        fail(f"{path}.new_name is required for rename")

    if action in {"remove", "replace"} and item.get("destructive_authorization") is not True:
        fail(f"{path}.destructive_authorization must be true for {action}")

    if action == "replace" and not _non_empty_text(item.get("replacement_reason")):
        fail(f"{path}.replacement_reason is required for replace")

    if family == "template" and action in MUTATING_ACTIONS:
        permission_delta = item.get("permission_delta")
        if not isinstance(permission_delta, dict):
            fail(f"{path}.permission_delta is required for a template mutation")
