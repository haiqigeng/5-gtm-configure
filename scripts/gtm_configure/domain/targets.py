"""Approved target identity and mode membership."""

from typing import Any

from gtm_configure.core.contract_validation import (
    ContractValidationError,
    array,
    authority,
    object,
    text,
)
from gtm_configure.core.model import TARGET_TYPES


def validate_targets(raw: Any, mode: str) -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(array(raw, "$.targets")):
        path = f"$.targets[{index}]"
        target = object(value, path)
        target_id = text(target.get("target_id"), f"{path}.target_id")
        if "::" in target_id:
            raise ContractValidationError(f"{path}.target_id must not contain '::'")
        if target_id in targets:
            raise ContractValidationError(f"duplicate target_id {target_id!r}")
        container_type = text(target.get("container_type"), f"{path}.container_type")
        if container_type not in TARGET_TYPES:
            raise ContractValidationError(f"{path}.container_type has unsupported value")
        for field in ("account_id", "container_id", "workspace_id"):
            text(target.get(field), f"{path}.{field}")
        authority(target.get("authority"), f"{path}.authority", approved=True)
        targets[target_id] = target
    if not targets:
        raise ContractValidationError("$.targets must not be empty")
    target_types = {target["container_type"] for target in targets.values()}
    if mode == "web" and target_types != {"web"}:
        raise ContractValidationError("web mode permits only web targets")
    if mode == "server" and target_types != {"server"}:
        raise ContractValidationError("server mode permits only server targets")
    if mode == "pipeline" and target_types != TARGET_TYPES:
        raise ContractValidationError(
            "pipeline mode requires at least one web and one server target"
        )
    return targets
