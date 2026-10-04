#!/usr/bin/env python3
"""Expand compact approved input into the single current configuration contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from action_contract import build_mutation_approval
from native_configuration import supports_native_mapping, variable_name
from public_identifiers import public_identifier_paths, validate_public_identifiers
from redaction import scrub_sensitive_text, sensitive_paths
from resource_registry import semantic_object_key
from run_model import MUTATING_ACTIONS
from run_validation_web import _field_mappings, _resolved_event_parameter
from strict_json import load_json, write_json_atomic
from validate_configuration_contract import SCHEMA_VERSION, validate_document


def _derive_exact_declarations(contract: dict, objects: list[dict]) -> None:
    """Fill mechanical facts only; unresolved cases remain explicit validator input."""
    by_key = {item["object_key"]: item for item in objects}
    requirements = {item["id"]: item for item in contract["requirements"]}
    evidence = contract.setdefault("evidence", [])
    for requirement in requirements.values():
        locator = requirement["authority"]["locator"]
        if not any(
            item.get("grade") == "approved-input" and item.get("locator") == locator
            for item in evidence
        ):
            evidence.append(
                {"grade": "approved-input", "locator": locator, "supports": [requirement["id"]]}
            )
    for topology in contract["execution_topologies"]:
        owner = by_key.get(topology.get("tag_object_key"), {})
        linked = [requirements[key].get("source_event") for key in owner.get("requirement_ids", [])]
        if not linked or len(set(linked)) != 1 or not linked[0]:
            continue
        derived = []
        for key in owner.get("intended", {}).get("firingTriggerId", []):
            trigger = by_key.get(key, {}).get("intended", {})
            conditions = trigger.get("customEventFilter")
            if (
                trigger.get("type") != "customEvent"
                or trigger.get("filter")
                or not isinstance(conditions, list)
                or len(conditions) != 1
            ):
                break
            condition = conditions[0]
            params = condition.get("parameter", [])
            fields = {row.get("key"): row.get("value") for row in params}
            if (
                condition.get("type") != "equals"
                or len(params) != 2
                or fields != {"arg0": "{{_event}}", "arg1": linked[0]}
            ):
                break
            derived.append(
                {"trigger_object_key": key, "role": "source-event", "type": "custom-event"}
            )
        else:
            if derived:
                topology.setdefault("normal_triggers", derived)
                for row in topology["normal_triggers"]:
                    match = next(
                        (
                            item
                            for item in derived
                            if item["trigger_object_key"] == row.get("trigger_object_key")
                        ),
                        None,
                    )
                    if match:
                        for field in ("role", "type"):
                            row.setdefault(field, match[field])
    bindings = contract.setdefault("field_bindings", [])
    for requirement in requirements.values():
        for mapping in _field_mappings(requirement):
            key_fields = ("requirement_id", "field_scope", "destination_field")
            existing = next(
                (
                    row
                    for row in bindings
                    if all(row.get(key) == mapping[key] for key in key_fields)
                ),
                None,
            )
            field = requirement.get("parameters", {}).get(mapping["destination_field"], {})
            missing = (existing or {}).get("missing_behavior") or field.get("missing_behavior")
            if (
                not missing
                or not mapping.get("source_shape")
                or mapping["source_shape"] != mapping.get("destination_shape")
            ):
                continue
            matches = []
            for owner in objects:
                if (
                    owner["resource_family"] != "tag"
                    or requirement["id"] not in owner["requirement_ids"]
                ):
                    continue
                native = owner.get("intended", {})
                if not supports_native_mapping(mapping, native):
                    continue
                variables = {
                    item["name"]: item.get("intended", {})
                    for item in objects
                    if item["resource_family"] == "variable"
                    and item["target_id"] == owner["target_id"]
                }
                try:
                    value = _resolved_event_parameter(
                        owner, objects, variables, mapping["destination_field"]
                    )
                    variable = variables[variable_name(value)]
                except (ValueError, KeyError, TypeError):
                    continue
                params = variable.get("parameter", [])
                versions = [
                    row.get("value") for row in params if row.get("key") == "dataLayerVersion"
                ]
                if variable.get("formatValue") or versions != ["2"]:
                    continue
                if variable.get("type") != "v" or any(
                    row.get("key") not in {"name", "dataLayerVersion"} for row in params
                ):
                    continue
                names = [row.get("value") for row in params if row.get("key") == "name"]
                if names != [mapping["source"]]:
                    continue
                matches.append((owner, value))
            if len(matches) != 1:
                continue
            owner, value = matches[0]
            derived = {
                **{key: mapping[key] for key in key_fields},
                "shape_compatibility": "compatible",
                "mapping_method": "direct-dlv",
                "gtm_resolution": value,
                "template_field": mapping["destination_field"],
                "missing_behavior": missing,
                "status": "mapped",
                "native_binding": {
                    "object_key": owner["object_key"],
                    "field": mapping["destination_field"],
                },
            }
            if existing is None:
                bindings.append(derived)
            else:
                for key, value in derived.items():
                    existing.setdefault(key, value)


def compile_request(request: dict[str, Any], *, inventory: dict | None = None) -> dict[str, Any]:
    """Derive identities, approvals and explicit-reference closure, never product policy."""
    if inventory is not None:
        from mcp_discovery import fill_reuse_candidates

        request = fill_reuse_candidates(request, inventory)
    validate_public_identifiers(request)
    findings = sensitive_paths(request, public_identifier_paths=public_identifier_paths(request))
    if findings:
        raise ValueError("Remove literal secrets/user data at: " + ", ".join(findings))
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
    _derive_exact_declarations(contract, objects)
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
    parser.add_argument(
        "--inventory",
        type=Path,
        help="Fill omitted native bodies of explicitly selected reuse_candidates",
    )
    args = parser.parse_args()
    try:
        write_json_atomic(
            args.output,
            compile_request(
                load_json(args.request),
                inventory=load_json(args.inventory) if args.inventory else None,
            ),
        )
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(
            json.dumps(
                {
                    "status": "Blocked",
                    "error_type": type(exc).__name__,
                    "error": scrub_sensitive_text(str(exc), set()),
                }
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
