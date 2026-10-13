#!/usr/bin/env python3
"""Validate the current configure-gtm configuration-contract@8.0."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import gtm_configure.core.validation as validation
import gtm_configure.domain.requirements as requirement_support
from gtm_configure.core.contract_validation import (
    ContractValidationError,
    _array,
    _authority,
    _fail,
    _object,
    _text,
    _unique_texts,
)
from gtm_configure.core.json_io import StrictJsonError, load_json
from gtm_configure.core.model import (
    ACTIONS,
    CONTRACT_SCHEMA_VERSION,
    DELTA_ACTIONS,
    EVIDENCE_GRADES,
    MUTATING_ACTIONS,
    ROUTES,
    RUN_MODES,
    TARGET_TYPES,
)
from gtm_configure.core.privacy import sensitive_paths
from gtm_configure.core.public_identifiers import (
    public_identifier_paths,
    validate_public_identifiers,
)
from gtm_configure.core.schemas import validate_structure
from gtm_configure.domain.actions import validate_action_contract
from gtm_configure.domain.resources import (
    ResourceRegistryError,
    semantic_object_key,
    validate_target_family,
)
from gtm_configure.domain.web import validate_web_domain

_WEB_BUILT_IN_TRIGGER_IDS = {"2147479553", "2147479572", "2147479573"}
_MAX_OFFICIAL_EVIDENCE_AGE_DAYS = 365


SCHEMA_VERSION = CONTRACT_SCHEMA_VERSION

OBJECT_RESOURCE_FAMILIES = requirement_support.OBJECT_RESOURCE_FAMILIES | {
    "client",
    "transformation",
}
HIGH_IMPACT_RESOURCE_FAMILIES = {
    "client",
    "container setting",
    "destination",
    "environment",
    "google tag configuration",
    "template",
    "transformation",
    "zone",
}
TOP_LEVEL_KEYS = {
    "schema_version",
    "mode",
    "route",
    "scope",
    "requirements",
    "targets",
    "pipelines",
    "consent_topologies",
    "dedup_contracts",
    "execution_topologies",
    "page_view_decisions",
    "first_party_data_routes",
    "inventory_dispositions",
    "implementation",
    "evidence",
    "external_dependencies",
}


def _validate_scope_and_requirements(contract: dict[str, Any], route: str) -> set[str]:
    scope = _object(contract["scope"], "$.scope")
    partitions = {
        name: set(_unique_texts(scope.get(name), f"$.scope.{name}"))
        for name in ("included", "reference_only", "excluded")
    }
    for left, right in (
        ("included", "reference_only"),
        ("included", "excluded"),
        ("reference_only", "excluded"),
    ):
        overlap = sorted(partitions[left] & partitions[right])
        if overlap:
            raise ContractValidationError(
                f"$.scope.{left} and $.scope.{right} overlap: {', '.join(overlap)}"
            )
    requirement_ids: set[str] = set()
    for index, raw in enumerate(_array(contract["requirements"], "$.requirements")):
        try:
            requirement_id = requirement_support.validate_requirement(
                raw,
                index=index,
                route=route,
            )
        except ValueError as exc:
            raise ContractValidationError(str(exc)) from exc
        if requirement_id in requirement_ids:
            raise ContractValidationError(f"duplicate requirement id {requirement_id!r}")
        requirement_ids.add(requirement_id)
    if requirement_ids != partitions["included"]:
        raise ContractValidationError(
            "$.scope.included must equal the IDs represented in $.requirements"
        )
    return requirement_ids


def _validate_targets(raw: Any, mode: str) -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(_array(raw, "$.targets")):
        path = f"$.targets[{index}]"
        target = _object(value, path)
        target_id = _text(target.get("target_id"), f"{path}.target_id")
        if "::" in target_id:
            raise ContractValidationError(f"{path}.target_id must not contain '::'")
        if target_id in targets:
            raise ContractValidationError(f"duplicate target_id {target_id!r}")
        container_type = _text(target.get("container_type"), f"{path}.container_type")
        if container_type not in TARGET_TYPES:
            raise ContractValidationError(f"{path}.container_type has unsupported value")
        for field in ("account_id", "container_id", "workspace_id"):
            _text(target.get(field), f"{path}.{field}")
        _authority(target.get("authority"), f"{path}.authority", approved=True)
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


def _object_is_high_impact(item: dict[str, Any]) -> bool:
    family = item["resource_family"]
    if item["action"] in {"remove", "replace", "pause", "unpause"}:
        return True
    if family not in HIGH_IMPACT_RESOURCE_FAMILIES:
        return False
    if family == "client" and item["action"] == "reuse":
        return False
    if (
        family == "transformation"
        and item.get("assertions", {}).get("transformation", {}).get("scope")
        == "single-destination"
    ):
        return False
    return item["action"] in MUTATING_ACTIONS


def _validate_objects(
    raw: Any,
    targets: dict[str, dict[str, Any]],
    requirements: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    requirement_ids = set(requirements)
    objects: dict[str, dict[str, Any]] = {}
    aliases: dict[str, str] = {}
    for index, value in enumerate(_array(raw, "$.implementation.objects")):
        path = f"$.implementation.objects[{index}]"
        item = _object(value, path)
        target_id = _text(item.get("target_id"), f"{path}.target_id")
        if target_id not in targets:
            raise ContractValidationError(f"{path}.target_id references an unknown target")
        action = _text(item.get("action"), f"{path}.action")
        if action not in ACTIONS:
            raise ContractValidationError(f"{path}.action has unsupported value {action!r}")
        family = _text(item.get("resource_family"), f"{path}.resource_family")
        try:
            family = validate_target_family(targets[target_id]["container_type"], family)
        except ResourceRegistryError as exc:
            raise ContractValidationError(f"{path}: {exc}") from exc
        item["resource_family"] = family
        if action in {"pause", "unpause"} and family != "tag":
            raise ContractValidationError(f"{path}.{action} is supported only for tags")
        name = _text(item.get("name"), f"{path}.name")
        key = semantic_object_key(target_id, family, name)
        if key in objects:
            raise ContractValidationError(f"duplicate object identity {key!r}")
        alias = _text(item.get("object_key", key), f"{path}.object_key")
        if alias != key:
            raise ContractValidationError(f"{path}.object_key must equal {key!r}")
        _text(item.get("justification"), f"{path}.justification")
        links = set(_unique_texts(item.get("requirement_ids", []), f"{path}.requirement_ids"))
        unknown = sorted(links - requirement_ids)
        if unknown:
            raise ContractValidationError(
                f"{path}.requirement_ids contains unknown IDs: {', '.join(unknown)}"
            )
        evidence = set(_unique_texts(item.get("evidence"), f"{path}.evidence", allow_empty=False))
        if not evidence <= EVIDENCE_GRADES:
            raise ContractValidationError(f"{path}.evidence contains an unsupported grade")
        if action in MUTATING_ACTIONS:
            if not links:
                raise ContractValidationError(
                    f"{path}.requirement_ids must bind every mutation to approved scope"
                )
            if "approved-input" not in evidence:
                raise ContractValidationError(
                    f"{path}.evidence needs 'approved-input' mutation authority"
                )
        if (
            action in {"reuse", "untouched", *DELTA_ACTIONS}
            and "container-confirmed" not in evidence
        ):
            raise ContractValidationError(f"{path}.evidence needs 'container-confirmed'")
        if action in DELTA_ACTIONS:
            pre_change = _object(item.get("pre_change"), f"{path}.pre_change")
            if not pre_change:
                raise ContractValidationError(f"{path}.pre_change must not be empty")
        if action in {"create", "update", "replace"}:
            intended = _object(item.get("intended"), f"{path}.intended")
            if not intended:
                raise ContractValidationError(f"{path}.intended must not be empty")
        risk = item.get("risk", "routine")
        if risk not in {"routine", "high-impact"}:
            raise ContractValidationError(f"{path}.risk has unsupported value {risk!r}")
        expected_high = _object_is_high_impact(item)
        if expected_high and risk != "high-impact":
            raise ContractValidationError(f"{path}.risk must be 'high-impact'")
        validate_action_contract(
            item,
            path=path,
            fail=_fail,
            authority_locators={requirements[value]["authority"]["locator"] for value in links},
        )
        objects[key] = item
        aliases[key] = key
    for key, item in objects.items():
        dependencies = _unique_texts(
            item.get("depends_on", []), f"$.implementation.objects[{key!r}].depends_on"
        )
        for dependency in dependencies:
            if dependency not in aliases:
                raise ContractValidationError(
                    f"object {key!r} depends on unknown object {dependency!r}"
                )
            if dependency == key:
                raise ContractValidationError(f"object {key!r} cannot depend on itself")
    _reject_cycles({key: item.get("depends_on", []) for key, item in objects.items()}, "objects")
    return objects, aliases


def _reject_cycles(graph: dict[str, list[str]], label: str) -> None:
    remaining = {key: len(value) for key, value in graph.items()}
    dependents: dict[str, list[str]] = {key: [] for key in graph}
    for key, dependencies in graph.items():
        for dependency in dependencies:
            dependents.setdefault(dependency, []).append(key)
    ready = [key for key, count in remaining.items() if count == 0]
    seen = 0
    while ready:
        key = ready.pop()
        seen += 1
        for dependent in dependents.get(key, []):
            remaining[dependent] -= 1
            if remaining[dependent] == 0:
                ready.append(dependent)
    if seen != len(graph):
        raise ContractValidationError(f"{label} dependency graph contains a cycle")


def _validate_server_object_graph(objects, targets, requirements, pipelines):
    from gtm_configure.domain.server import validate_server_operations

    operations = [
        {**item, "operation_id": key, "dependencies": item.get("depends_on", [])}
        for key, item in objects.items()
    ]
    flows = [
        {
            **pipeline,
            "event_flows": [
                {
                    **flow,
                    "server_consumer_operation_ids": flow.get("server_consumer_keys", []),
                }
                for flow in pipeline.get("event_flows", [])
            ],
        }
        for pipeline in pipelines
    ]
    validate_server_operations(
        operations,
        {key: value["container_type"] for key, value in targets.items()},
        _fail,
        pipelines=flows,
        requirements=list(requirements.values()),
    )


def _validate_evidence(raw: Any, requirement_ids: set[str], product_requirements: set[str]) -> None:
    grades: set[str] = set()
    officially_supported: set[str] = set()
    for index, value in enumerate(_array(raw, "$.evidence")):
        path = f"$.evidence[{index}]"
        evidence = _object(value, path)
        grade = _text(evidence.get("grade"), f"{path}.grade")
        if grade not in EVIDENCE_GRADES:
            raise ContractValidationError(f"{path}.grade is unsupported")
        grades.add(grade)
        locator = _text(evidence.get("locator"), f"{path}.locator")
        if grade == "official-current":
            for field in ("title", "decision"):
                _text(evidence.get(field), f"{path}.{field}")
            try:
                parsed = urlparse(locator)
                valid_locator = (
                    parsed.scheme == "https"
                    and bool(parsed.hostname)
                    and parsed.username is None
                    and parsed.password is None
                )
            except ValueError:
                valid_locator = False
            if not valid_locator:
                raise ContractValidationError(
                    f"{path}.locator must be a credential-free HTTPS documentation URL"
                )
            try:
                accessed_on = date.fromisoformat(
                    _text(evidence.get("accessed_on"), f"{path}.accessed_on")
                )
            except ValueError as exc:
                raise ContractValidationError(f"{path}.accessed_on must be an ISO date") from exc
            age = (date.today() - accessed_on).days
            if age < 0:
                raise ContractValidationError(f"{path}.accessed_on cannot be in the future")
            if age > _MAX_OFFICIAL_EVIDENCE_AGE_DAYS:
                raise ContractValidationError(
                    f"{path}.official-current evidence is older than "
                    f"{_MAX_OFFICIAL_EVIDENCE_AGE_DAYS} days"
                )
            supports = set(
                _unique_texts(evidence.get("supports"), f"{path}.supports", allow_empty=False)
            )
            if supports - requirement_ids:
                raise ContractValidationError(f"{path}.supports contains an unknown requirement")
            officially_supported.update(supports)
    if "container-confirmed" not in grades or (
        product_requirements and "official-current" not in grades
    ):
        raise ContractValidationError(
            "$.evidence needs official-current and container-confirmed records"
        )
    if product_requirements - officially_supported:
        raise ContractValidationError(
            "official-current evidence must support every included requirement; missing="
            + repr(sorted(product_requirements - officially_supported))
        )


def validate_document(value: Any) -> dict[str, Any]:
    validate_structure(value, "contract", _fail)
    contract = _object(value, "$")
    version = contract.get("schema_version")
    if version is None:
        raise ContractValidationError(
            "$.schema_version is required; unversioned inputs cannot authorize mutation"
        )
    if version != SCHEMA_VERSION:
        raise ContractValidationError(f"$.schema_version must be {SCHEMA_VERSION!r}")
    unexpected = sorted(set(contract) - TOP_LEVEL_KEYS)
    missing = sorted(TOP_LEVEL_KEYS - set(contract))
    if unexpected:
        raise ContractValidationError(f"unexpected top-level key(s): {', '.join(unexpected)}")
    if missing:
        raise ContractValidationError(f"missing top-level key(s): {', '.join(missing)}")
    try:
        validate_public_identifiers(contract)
    except ValueError as exc:
        raise ContractValidationError(str(exc)) from exc
    leaks = sensitive_paths(contract, public_identifier_paths=public_identifier_paths(contract))
    if leaks:
        raise ContractValidationError(
            "contract contains literal secret or user data at: " + ", ".join(leaks)
        )
    mode = _text(contract["mode"], "$.mode")
    if mode not in RUN_MODES:
        raise ContractValidationError(f"$.mode has unsupported value {mode!r}")
    route = _text(contract["route"], "$.route")
    if route not in ROUTES:
        raise ContractValidationError(f"$.route has unsupported value {route!r}")
    requirement_ids = _validate_scope_and_requirements(contract, route)
    targets = _validate_targets(contract["targets"], mode)
    implementation = _object(contract["implementation"], "$.implementation")
    if not {"execution_mode", "objects"} <= set(implementation) or set(implementation) - {
        "execution_mode",
        "objects",
        "field_bindings",
    }:
        raise ContractValidationError(
            "$.implementation requires execution_mode and objects, with optional field_bindings"
        )
    execution_mode = _text(implementation["execution_mode"], "$.implementation.execution_mode")
    requirement_by_id = {item["id"]: item for item in contract["requirements"]}
    objects, _ = _validate_objects(implementation["objects"], targets, requirement_by_id)
    implemented_requirement_ids = {
        requirement_id
        for item in objects.values()
        for requirement_id in item.get("requirement_ids", [])
    }
    missing_implementation = sorted(requirement_ids - implemented_requirement_ids)
    if missing_implementation:
        raise ContractValidationError(
            "every included requirement needs an implementing create/update/reuse/untouched "
            f"object; missing={missing_implementation}"
        )
    _validate_server_object_graph(
        objects,
        targets,
        requirement_by_id,
        contract["pipelines"],
    )
    from gtm_configure.domain.fields import materialize_payload_mappings

    try:
        payload_mappings = materialize_payload_mappings(contract)
    except validation.RunValidationError as exc:
        raise ContractValidationError(str(exc)) from exc
    unresolved = [
        f"{row['requirement_id']}::{row['destination_field']}"
        for row in payload_mappings
        if row.get("status") == "pending"
    ]
    if unresolved:
        raise ContractValidationError(
            "Bind approved fields before execution (implementation.field_bindings): "
            + ", ".join(unresolved)
        )
    from gtm_configure.domain.pipeline import validate_pipeline_contract

    validate_pipeline_contract(contract, payload_mappings, _fail)
    validate_web_domain(
        execution_mode=execution_mode,
        requirements=[
            {**item, "kind": item.get("kind", route)} for item in contract["requirements"]
        ],
        operations=list(objects.values()),
        target_types={key: item["container_type"] for key, item in targets.items()},
        payload_mappings=payload_mappings,
        consent_topologies=contract["consent_topologies"],
        execution_topologies=contract["execution_topologies"],
        page_view_decisions=contract["page_view_decisions"],
        first_party_data_routes=contract["first_party_data_routes"],
        pipelines=contract["pipelines"],
        inventory_dispositions=contract["inventory_dispositions"],
        external_dependencies=contract["external_dependencies"],
        fail=_fail,
        contract_phase=True,
    )
    organization_ids = {
        item["id"] for item in contract["requirements"] if item.get("kind", route) == "organization"
    }
    for item in objects.values():
        if organization_ids & set(item.get("requirement_ids", [])) and (
            item["resource_family"] != "folder"
            or item["action"] not in {"create", "rename", "reuse", "untouched"}
        ):
            _fail("organization requirements support only folder creation, rename, or reuse")
    for item in contract["requirements"]:
        if item["id"] in organization_ids and (
            set(item) & requirement_support.SEMANTIC_FIELD_MAPS
            or item.get("event_name")
            or item.get("source_event")
        ):
            _fail("organization requirements cannot contain collection semantics")
    _validate_evidence(contract["evidence"], requirement_ids, requirement_ids - organization_ids)
    _array(contract["external_dependencies"], "$.external_dependencies")
    return contract


def load_contract(path: Path) -> dict[str, Any]:
    try:
        value = load_json(path)
    except StrictJsonError as exc:
        raise ContractValidationError(str(exc), error_code=exc.error_code) from exc
    return validate_document(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    args = parser.parse_args()
    try:
        contract = load_contract(args.contract)
    except ContractValidationError as exc:
        print(json.dumps({"pass": False, "error_code": exc.error_code, "error": str(exc)}))
        return 2
    print(json.dumps({"pass": True, "schema_version": contract["schema_version"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
