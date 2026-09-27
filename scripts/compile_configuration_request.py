#!/usr/bin/env python3
"""Expand compact approved input into the single current configuration contract."""

from __future__ import annotations

import argparse
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from action_contract import build_mutation_approval
from redaction import sensitive_paths
from resource_registry import semantic_object_key
from run_model import MUTATING_ACTIONS
from strict_json import load_json, write_json_atomic
from validate_configuration_contract import SCHEMA_VERSION, validate_document


def compile_request(request: dict[str, Any]) -> dict[str, Any]:
    """Derive identities, approvals and explicit-reference closure, never product policy."""
    if sensitive_paths(request):
        raise ValueError("Remove literal secrets/user data before compiling the request")
    contract = deepcopy(request)
    candidates = contract.pop("reuse_candidates", [])
    supplied_objects = contract.pop("objects")
    if "implementation" in contract:
        raise ValueError("Use objects and field_bindings in compact input, not implementation")
    contract.setdefault("schema_version", SCHEMA_VERSION)
    requirements = contract["requirements"]
    targets = contract["targets"]
    requirement_ids = [item["id"] for item in requirements]
    locators = {item["id"]: item["authority"]["locator"] for item in requirements}
    contract.setdefault(
        "scope", {"included": requirement_ids, "reference_only": [], "excluded": []}
    )
    for field in (
        "pipelines",
        "consent_topologies",
        "dedup_contracts",
        "execution_topologies",
        "page_view_decisions",
        "first_party_data_routes",
        "inventory_dispositions",
        "external_dependencies",
    ):
        contract.setdefault(field, [])

    def expand(item: dict[str, Any], *, reuse: bool = False) -> dict[str, Any]:
        item = deepcopy(item)
        if "target_id" not in item and len(targets) == 1:
            item["target_id"] = targets[0]["target_id"]
        if "requirement_ids" not in item and len(requirements) == 1:
            item["requirement_ids"] = requirement_ids.copy()
        item.setdefault(
            "object_key",
            semantic_object_key(item["target_id"], item["resource_family"], item["name"]),
        )
        item.setdefault("depends_on", [])
        if reuse:
            if item.get("action", "reuse") != "reuse":
                raise ValueError("reuse_candidates may only supply reuse objects")
            item["action"] = "reuse"
        return item

    objects = [expand(item) for item in supplied_objects]
    candidate_by_key = {}
    for raw in candidates:
        item = expand(raw, reuse=True)
        if item["object_key"] in candidate_by_key:
            raise ValueError("Duplicate reuse candidate identity")
        candidate_by_key[item["object_key"]] = item
    selected = {item["object_key"]: item for item in objects}
    if len(selected) != len(objects) or selected.keys() & candidate_by_key.keys():
        raise ValueError("Duplicate object identity in compact request")
    all_objects = {**candidate_by_key, **selected}

    def references(value: Any, target: str) -> set[str]:
        if isinstance(value, dict):
            return set().union(*(references(child, target) for child in value.values()))
        if isinstance(value, list):
            return set().union(*(references(child, target) for child in value))
        if not isinstance(value, str):
            return set()
        refs = {value} if value in all_objects else set()
        for name in re.findall(r"\{\{([^{}]+)\}\}", value):
            key = semantic_object_key(target, "variable", name)
            if key in all_objects:
                refs.add(key)
        return refs

    index = 0
    while index < len(objects):
        item = objects[index]
        dependencies = set(item["depends_on"]) | references(
            item.get("intended", {}), item["target_id"]
        )
        dependencies.discard(item["object_key"])
        for key in sorted(dependencies):
            if key not in selected:
                if key not in candidate_by_key:
                    raise ValueError(f"Missing dependency: {key}")
                candidate = deepcopy(candidate_by_key[key])
                candidate["requirement_ids"] = list(item["requirement_ids"])
                selected[key] = candidate
                objects.append(candidate)
        item["depends_on"] = sorted(dependencies)
        if item["action"] in MUTATING_ACTIONS:
            # The source locator records existing authorization; this is not approval discovery.
            item["approval"] = build_mutation_approval(item, locators[item["requirement_ids"][0]])
        index += 1
    # Shared dependencies may be reached later through a longer path. Propagate
    # requirement attribution over the complete closure until it stops changing.
    changed = True
    while changed:
        changed = False
        for item in objects:
            for key in item["depends_on"]:
                if key not in candidate_by_key:
                    continue
                dependency = selected[key]
                merged = sorted(set(dependency["requirement_ids"]) | set(item["requirement_ids"]))
                if merged != dependency["requirement_ids"]:
                    dependency["requirement_ids"] = merged
                    changed = True
    contract["implementation"] = {
        "execution_mode": contract.pop("execution_mode", "isolated-durable"),
        "field_bindings": contract.pop("field_bindings", []),
        "objects": objects,
    }
    return validate_document(contract)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    args = parser.parse_args()
    write_json_atomic(args.output, compile_request(load_json(args.request)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
