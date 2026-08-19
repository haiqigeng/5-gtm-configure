"""Target-aware GTM resource identity and adapter capability rules."""

from __future__ import annotations

import re
from typing import Any

from run_model import RESOURCE_FAMILIES, SERVER_RESOURCE_FAMILIES, WEB_RESOURCE_FAMILIES


class ResourceRegistryError(ValueError):
    """Raised when a target/resource combination cannot be represented safely."""


_TOKEN = re.compile(r"[^a-z0-9]+")


def normalized_family(value: str) -> str:
    family = _TOKEN.sub(" ", value.casefold()).strip()
    if family not in RESOURCE_FAMILIES:
        raise ResourceRegistryError(f"unsupported GTM resource family {value!r}")
    return family


def semantic_object_key(target_id: str, resource_family: str, name: str) -> str:
    """Return the v9 target-scoped semantic identity."""
    if not isinstance(target_id, str) or not target_id.strip():
        raise ResourceRegistryError("target_id must be a non-empty string")
    if not isinstance(name, str) or not name.strip():
        raise ResourceRegistryError("object name must be a non-empty string")
    family = normalized_family(resource_family)
    return f"{target_id.strip()}::{family}::{name.strip()}"


def validate_target_family(container_type: str, resource_family: str) -> str:
    family = normalized_family(resource_family)
    allowed = WEB_RESOURCE_FAMILIES if container_type == "web" else SERVER_RESOURCE_FAMILIES
    if container_type not in {"web", "server"}:
        raise ResourceRegistryError(f"unsupported container_type {container_type!r}")
    if family not in allowed:
        raise ResourceRegistryError(
            f"{family!r} is not a {container_type!r} container resource family"
        )
    return family


def capability_matrix(
    target: dict[str, Any],
    discovered: dict[str, Any] | None = None,
) -> dict[str, dict[str, bool]]:
    """Normalize capability discovery without inventing unsupported operations."""
    container_type = target.get("container_type")
    if container_type == "web":
        allowed = WEB_RESOURCE_FAMILIES
    elif container_type == "server":
        allowed = SERVER_RESOURCE_FAMILIES
    else:
        raise ResourceRegistryError(f"unsupported container_type {container_type!r}")
    discovered = discovered or {}
    output: dict[str, dict[str, bool]] = {}
    for family in sorted(allowed):
        raw = discovered.get(family, {})
        if not isinstance(raw, dict):
            raise ResourceRegistryError(f"capability record for {family!r} must be an object")
        output[family] = {
            "list": raw.get("list") is True,
            "get": raw.get("get") is True,
            "create": raw.get("create") is True,
            "update": raw.get("update") is True,
            "remove": raw.get("remove") is True,
        }
    return output


def operation_capability(action: str) -> str | None:
    if action in {"reuse", "untouched"}:
        return "get"
    if action == "create":
        return "create"
    if action in {"update", "rename", "pause", "unpause"}:
        return "update"
    if action in {"remove", "replace"}:
        return "remove"
    return None


def unsupported_operation_reason(
    operation: dict[str, Any], matrix: dict[str, dict[str, bool]]
) -> str | None:
    family = normalized_family(operation["resource_family"])
    if operation["action"] == "replace":
        missing = [
            capability
            for capability in ("remove", "create")
            if not matrix.get(family, {}).get(capability, False)
        ]
        if missing:
            return (
                "adapter lacks "
                + " and ".join(repr(value) for value in missing)
                + f" capability for governed replace of {family!r}"
            )
        return None
    capability = operation_capability(operation["action"])
    if capability is None:
        return f"unsupported action {operation['action']!r}"
    if not matrix.get(family, {}).get(capability, False):
        return f"adapter lacks {capability!r} capability for {family!r}"
    return None
