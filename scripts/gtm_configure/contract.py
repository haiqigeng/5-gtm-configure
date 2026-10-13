#!/usr/bin/env python3
"""Validate the current configure-gtm configuration contract."""

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
    array,
    fail,
    object,
    text,
    unique_texts,
)
from gtm_configure.core.json_io import StrictJsonError, load_json
from gtm_configure.core.model import (
    ACTIONS,
    CONTRACT_SCHEMA_VERSION,
    DELTA_ACTIONS,
    EVIDENCE_GRADES,
    HIGH_IMPACT_ACTIONS,
    MUTATING_ACTIONS,
    ROUTES,
    RUN_MODES,
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
from gtm_configure.domain.targets import validate_targets
from gtm_configure.domain.web import validate_web_domain

_MAX_OFFICIAL_EVIDENCE_AGE_DAYS = 365


SCHEMA_VERSION = CONTRACT_SCHEMA_VERSION

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


def _validate_scope_and_requirements(contract: dict[str, Any], route: str) -> set[str]:
    scope = object(contract["scope"], "$.scope")
    partitions = {
        name: set(unique_texts(scope.get(name), f"$.scope.{name}"))
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
    for index, raw in enumerate(array(contract["requirements"], "$.requirements")):
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


def _object_is_high_impact(item: dict[str, Any]) -> bool:
    family = item["resource_family"]
    if item["action"] in HIGH_IMPACT_ACTIONS:
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
    for index, value in enumerate(array(raw, "$.implementation.objects")):
        path = f"$.implementation.objects[{index}]"
        item = object(value, path)
        target_id = text(item.get("target_id"), f"{path}.target_id")
        if target_id not in targets:
            raise ContractValidationError(f"{path}.target_id references an unknown target")
        action = text(item.get("action"), f"{path}.action")
        if action not in ACTIONS:
            raise ContractValidationError(f"{path}.action has unsupported value {action!r}")
        family = text(item.get("resource_family"), f"{path}.resource_family")
        try:
            family = validate_target_family(targets[target_id]["container_type"], family)
        except ResourceRegistryError as exc:
            raise ContractValidationError(f"{path}: {exc}") from exc
        item["resource_family"] = family
        if action in {"pause", "unpause"} and family != "tag":
            raise ContractValidationError(f"{path}.{action} is supported only for tags")
        name = text(item.get("name"), f"{path}.name")
        key = semantic_object_key(target_id, family, name)
        if key in objects:
            raise ContractValidationError(f"duplicate object identity {key!r}")
        alias = text(item.get("object_key", key), f"{path}.object_key")
        if alias != key:
            raise ContractValidationError(f"{path}.object_key must equal {key!r}")
        text(item.get("justification"), f"{path}.justification")
        links = set(unique_texts(item.get("requirement_ids", []), f"{path}.requirement_ids"))
        unknown = sorted(links - requirement_ids)
        if unknown:
            raise ContractValidationError(
                f"{path}.requirement_ids contains unknown IDs: {', '.join(unknown)}"
            )
        evidence = set(unique_texts(item.get("evidence"), f"{path}.evidence", allow_empty=False))
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
            pre_change = object(item.get("pre_change"), f"{path}.pre_change")
            if not pre_change:
                raise ContractValidationError(f"{path}.pre_change must not be empty")
        if action in {"create", "update", "replace"}:
            intended = object(item.get("intended"), f"{path}.intended")
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
            fail=fail,
            authority_locators={requirements[value]["authority"]["locator"] for value in links},
        )
        objects[key] = item
        aliases[key] = key
    for key, item in objects.items():
        dependencies = unique_texts(
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


def _validate_evidence(raw: Any, requirement_ids: set[str], product_requirements: set[str]) -> None:
    grades: set[str] = set()
    officially_supported: set[str] = set()
    for index, value in enumerate(array(raw, "$.evidence")):
        path = f"$.evidence[{index}]"
        evidence = object(value, path)
        grade = text(evidence.get("grade"), f"{path}.grade")
        if grade not in EVIDENCE_GRADES:
            raise ContractValidationError(f"{path}.grade is unsupported")
        grades.add(grade)
        locator = text(evidence.get("locator"), f"{path}.locator")
        if grade == "official-current":
            for field in ("title", "decision"):
                text(evidence.get(field), f"{path}.{field}")
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
                    text(evidence.get("accessed_on"), f"{path}.accessed_on")
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
                unique_texts(evidence.get("supports"), f"{path}.supports", allow_empty=False)
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
    validate_structure(value, "contract", fail)
    contract = object(value, "$")
    version = contract.get("schema_version")
    if version is None:
        raise ContractValidationError(
            "$.schema_version is required; unversioned inputs cannot authorize mutation"
        )
    if version != SCHEMA_VERSION:
        raise ContractValidationError(f"$.schema_version must be {SCHEMA_VERSION!r}")
    try:
        validate_public_identifiers(contract)
    except ValueError as exc:
        raise ContractValidationError(str(exc)) from exc
    leaks = sensitive_paths(contract, public_identifier_paths=public_identifier_paths(contract))
    if leaks:
        raise ContractValidationError(
            "contract contains literal secret or user data at: " + ", ".join(leaks)
        )
    mode = text(contract["mode"], "$.mode")
    if mode not in RUN_MODES:
        raise ContractValidationError(f"$.mode has unsupported value {mode!r}")
    route = text(contract["route"], "$.route")
    if route not in ROUTES:
        raise ContractValidationError(f"$.route has unsupported value {route!r}")
    requirement_ids = _validate_scope_and_requirements(contract, route)
    targets = validate_targets(contract["targets"], mode)
    implementation = object(contract["implementation"], "$.implementation")
    execution_mode = text(implementation["execution_mode"], "$.implementation.execution_mode")
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
    from gtm_configure.domain.context import ConfigurationGraph
    from gtm_configure.domain.pipeline import validate_pipeline
    from gtm_configure.domain.server import validate_server_operations

    graph = ConfigurationGraph.from_contract(contract, payload_mappings)
    validate_server_operations(
        graph.operations,
        graph.target_types,
        fail,
        pipelines=graph.pipelines,
        requirements=graph.requirements,
    )
    validate_pipeline(graph, fail)
    validate_web_domain(
        execution_mode=execution_mode,
        graph=graph,
        execution_topologies=contract["execution_topologies"],
        page_view_decisions=contract["page_view_decisions"],
        first_party_data_routes=contract["first_party_data_routes"],
        external_dependencies=contract["external_dependencies"],
        fail=fail,
    )
    organization_ids = {
        item["id"] for item in contract["requirements"] if item.get("kind", route) == "organization"
    }
    for item in objects.values():
        if organization_ids & set(item.get("requirement_ids", [])) and (
            item["resource_family"] != "folder"
            or item["action"] not in {"create", "rename", "reuse", "untouched"}
        ):
            fail("organization requirements support only folder creation, rename, or reuse")
    for item in contract["requirements"]:
        if item["id"] in organization_ids and (
            set(item) & requirement_support.SEMANTIC_FIELD_MAPS
            or item.get("event_name")
            or item.get("source_event")
        ):
            fail("organization requirements cannot contain collection semantics")
    _validate_evidence(contract["evidence"], requirement_ids, requirement_ids - organization_ids)
    array(contract["external_dependencies"], "$.external_dependencies")
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
