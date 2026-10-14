"""Small semantic graph predicates shared by domain validators."""

import re
from copy import deepcopy
from graphlib import TopologicalSorter
from typing import Any, Callable

from gtm_configure.core.schemas import validate_definition
from gtm_configure.domain.localization import (
    local_array,
    local_text,
)


def _reference_values(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {item for child in value.values() for item in _reference_values(child)}
    if isinstance(value, list):
        return {item for child in value for item in _reference_values(child)}
    return {value} if isinstance(value, str) else set()


def active_tag(item: dict[str, Any]) -> bool:
    intended = item.get("intended") if isinstance(item.get("intended"), dict) else {}
    return (
        item.get("resource_family") == "tag"
        and item.get("action") not in {"remove", "pause"}
        and intended.get("paused") is not True
    )


def reference_name(value: str) -> str | None:
    match = re.fullmatch(r"\{\{\s*(.+?)\s*\}\}", value)
    return match.group(1) if match else None


def external_dependency_index(
    dependencies: list[Any], requirement_ids: set[str], fail: Callable[[str], None]
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(dependencies, start=1):
        path = f"$.external_dependencies[{index - 1}]"
        if not isinstance(raw, dict):
            fail(f"{path} must be an object")
            continue
        dependency = raw
        validate_definition(dependency, "externalDependency", fail)
        dependency_id = local_text(dependency.get("id"), f"{path}.id", error_type=fail)
        if dependency_id in output:
            fail(f"duplicate external dependency {dependency_id!r}")
        links = set(
            local_array(
                dependency.get("requirement_ids"), f"{path}.requirement_ids", error_type=fail
            )
        )
        if not links <= requirement_ids:
            fail(f"{path}.requirement_ids contains unknown IDs")
        local_text(dependency.get("owner"), f"{path}.owner", error_type=fail)
        local_text(dependency.get("action"), f"{path}.action", error_type=fail)
        output[dependency_id] = deepcopy(dependency)
    return output


def served_requirements(operations: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    """Derive dependency demand without modifying the authority of any operation."""
    order = tuple(
        TopologicalSorter(
            {key: item["dependencies"] for key, item in operations.items()}
        ).static_order()
    )
    serves = {key: set(item["requirement_ids"]) for key, item in operations.items()}
    for key in reversed(order):
        for dependency in operations[key]["dependencies"]:
            serves[dependency].update(serves[key])
    return serves


def object_references(value: Any) -> set[str]:
    """Collect explicit semantic references for native-consumer ownership projection."""
    return _reference_values(value)
