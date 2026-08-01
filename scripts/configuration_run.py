#!/usr/bin/env python3
"""Create, validate, checkpoint, inspect, and render configure-gtm run manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from validate_configuration_contract import (
    ACTIONS,
    DELTA_ACTIONS,
    MUTATING_ACTIONS,
    OBJECT_RESOURCE_FAMILIES,
    ContractValidationError,
)
from validate_configuration_contract import (
    validate_document as validate_configuration_contract,
)

SCHEMA_VERSION = "1.0"
RUN_PHASES = {"preflight", "mutation", "readback", "complete"}
RUN_STATUSES = {"In progress", "Configured", "Partial", "Blocked", "Deferred"}
REQUIREMENT_STATUSES = {"In progress", "Configured", "Partial", "Blocked", "Deferred"}
OPERATION_STATES = {
    "planned",
    "in_progress",
    "saved",
    "verified",
    "failed",
    "uncertain",
    "skipped",
}
FINAL_OPERATION_STATES = {"verified", "failed", "skipped"}
CONSENT_MODES = {"strict-basic", "advanced-native"}
CONSENT_MECHANISMS = {"blocking-trigger", "grant-event", "native-advanced"}
MAPPING_STATUSES = {"pending", "mapped", "intentionally-omitted", "external", "blocked"}
MAPPING_METHODS = {
    "constant",
    "custom-javascript",
    "direct-dlv",
    "lookup-table",
    "native-template",
    "regex-table",
    "settings-variable",
}
SHAPE_COMPATIBILITY = {"compatible", "conversion-required"}
EXTENDED_MAPPING_KEYS = {
    "source_authority_grade",
    "source_authority_locator",
    "source_shape",
    "destination_shape",
    "shape_compatibility",
    "mapping_method",
    "missing_behavior",
}
DEFAULT_VENDOR_BLOCK_SCOPE = "regex:.*"
TOP_LEVEL_KEYS = {
    "schema_version",
    "run",
    "requirements",
    "object_changes",
    "payload_mappings",
    "consent_routes",
    "saved_readback",
    "official_sources",
    "external_dependencies",
    "recovery_boundary",
    "idempotency",
    "recette_handoff",
}
ALLOWED_TRANSITIONS = {
    "planned": {"in_progress", "skipped", "verified", "failed"},
    "in_progress": {"saved", "verified", "failed", "uncertain"},
    "saved": {"verified", "failed", "uncertain"},
    "uncertain": {"verified", "failed"},
    "verified": set(),
    "failed": set(),
    "skipped": set(),
}


class RunValidationError(ValueError):
    """Raised when a configuration-run manifest violates the operational contract."""


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RunValidationError(f"{path} must be an object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise RunValidationError(f"{path} must be an array")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RunValidationError(f"{path} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _text(value, path)


def _unique_texts(value: Any, path: str, *, allow_empty: bool = True) -> list[str]:
    items = _array(value, path)
    normalized = [_text(item, f"{path}[]") for item in items]
    if len(set(normalized)) != len(normalized):
        raise RunValidationError(f"{path} contains duplicate values")
    if not allow_empty and not normalized:
        raise RunValidationError(f"{path} must not be empty")
    return normalized


def _timestamp(value: Any, path: str) -> str:
    text = _text(value, path)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RunValidationError(f"{path} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise RunValidationError(f"{path} must include a timezone")
    return text


def _date(value: Any, path: str) -> str:
    text = _text(value, path)
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise RunValidationError(f"{path} must use YYYY-MM-DD") from exc
    return text


def _canonical_object_key(object_type: str, name: str) -> str:
    return f"{object_type}::{name}"


def _validate_run_header(raw: Any) -> tuple[dict[str, Any], set[str], str]:
    run = _object(raw, "$.run")
    _text(run.get("id"), "$.run.id")
    phase = _text(run.get("phase"), "$.run.phase")
    if phase not in RUN_PHASES:
        raise RunValidationError(f"$.run.phase has unsupported value {phase!r}")
    status = _text(run.get("status"), "$.run.status")
    if status not in RUN_STATUSES:
        raise RunValidationError(f"$.run.status has unsupported value {status!r}")
    _timestamp(run.get("started_at"), "$.run.started_at")
    _timestamp(run.get("updated_at"), "$.run.updated_at")

    target = _object(run.get("target"), "$.run.target")
    for field in ("account_id", "container_id", "workspace_id"):
        _text(target.get(field), f"$.run.target.{field}")
    if _text(target.get("container_type"), "$.run.target.container_type").casefold() != "web":
        raise RunValidationError("$.run.target.container_type must be 'web'")

    contract = _object(run.get("contract"), "$.run.contract")
    _text(contract.get("schema_version"), "$.run.contract.schema_version")
    requirement_ids = set(
        _unique_texts(
            contract.get("requirement_ids"),
            "$.run.contract.requirement_ids",
            allow_empty=False,
        )
    )
    _text(contract.get("source_locator"), "$.run.contract.source_locator")
    _text(contract.get("fingerprint"), "$.run.contract.fingerprint")

    publication = _object(run.get("publication"), "$.run.publication")
    if publication.get("performed") is not False:
        raise RunValidationError("$.run.publication.performed must be false")
    if publication.get("version_created") is not False:
        raise RunValidationError("$.run.publication.version_created must be false")
    return run, requirement_ids, status


def _validate_requirements(raw: Any, expected_ids: set[str]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for index, item_raw in enumerate(_array(raw, "$.requirements")):
        path = f"$.requirements[{index}]"
        item = _object(item_raw, path)
        requirement_id = _text(item.get("id"), f"{path}.id")
        if requirement_id in records:
            raise RunValidationError(f"duplicate requirement id {requirement_id!r}")
        kind = _text(item.get("kind"), f"{path}.kind")
        if kind not in {"analytics", "media", "consent"}:
            raise RunValidationError(f"{path}.kind has unsupported value {kind!r}")
        _text(item.get("source_locator"), f"{path}.source_locator")
        _optional_text(item.get("source_event"), f"{path}.source_event")
        _optional_text(item.get("destination"), f"{path}.destination")
        status = _text(item.get("status"), f"{path}.status")
        if status not in REQUIREMENT_STATUSES:
            raise RunValidationError(f"{path}.status has unsupported value {status!r}")
        _unique_texts(item.get("object_keys"), f"{path}.object_keys")
        records[requirement_id] = item
    if set(records) != expected_ids:
        raise RunValidationError("$.requirements IDs must equal $.run.contract.requirement_ids")
    return records


def _validate_permission_delta(value: Any, path: str) -> None:
    delta = _object(value, path)
    _unique_texts(delta.get("added"), f"{path}.added")
    _unique_texts(delta.get("removed"), f"{path}.removed")
    _text(delta.get("evidence_locator"), f"{path}.evidence_locator")


def _validate_object_changes(
    raw: Any,
    *,
    requirement_ids: set[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    operations: dict[str, dict[str, Any]] = {}
    object_claims: dict[str, str] = {}
    dependency_map: dict[str, list[str]] = {}
    for index, item_raw in enumerate(_array(raw, "$.object_changes")):
        path = f"$.object_changes[{index}]"
        item = _object(item_raw, path)
        operation_id = _text(item.get("operation_id"), f"{path}.operation_id")
        if operation_id in operations:
            raise RunValidationError(f"duplicate operation_id {operation_id!r}")
        linked_ids = set(
            _unique_texts(
                item.get("requirement_ids"),
                f"{path}.requirement_ids",
                allow_empty=False,
            )
        )
        unknown_ids = sorted(linked_ids - requirement_ids)
        if unknown_ids:
            raise RunValidationError(
                f"{path}.requirement_ids contains unknown IDs: {', '.join(unknown_ids)}"
            )
        action = _text(item.get("action"), f"{path}.action")
        if action not in ACTIONS:
            raise RunValidationError(f"{path}.action has unsupported value {action!r}")
        object_type = _text(item.get("object_type"), f"{path}.object_type")
        if object_type not in OBJECT_RESOURCE_FAMILIES:
            raise RunValidationError(f"{path}.object_type is not a canonical resource family")
        name = _text(item.get("name"), f"{path}.name")
        object_key = _text(item.get("object_key"), f"{path}.object_key")
        expected_key = _canonical_object_key(object_type, name)
        if object_key != expected_key:
            raise RunValidationError(f"{path}.object_key must be {expected_key!r}")
        if object_key in object_claims:
            raise RunValidationError(
                f"{path}.object_key is already claimed by {object_claims[object_key]!r}"
            )
        object_claims[object_key] = operation_id
        dependencies = _unique_texts(item.get("dependencies"), f"{path}.dependencies")
        if operation_id in dependencies:
            raise RunValidationError(f"{path}.dependencies cannot contain itself")
        dependency_map[operation_id] = dependencies
        state = _text(item.get("state"), f"{path}.state")
        if state not in OPERATION_STATES:
            raise RunValidationError(f"{path}.state has unsupported value {state!r}")
        _unique_texts(item.get("evidence"), f"{path}.evidence", allow_empty=False)

        if action in MUTATING_ACTIONS - {"remove"}:
            intended = _object(item.get("intended"), f"{path}.intended")
            if not intended:
                raise RunValidationError(f"{path}.intended must not be empty for {action}")
        if action in DELTA_ACTIONS:
            pre_change = _object(item.get("pre_change"), f"{path}.pre_change")
            if not pre_change:
                raise RunValidationError(f"{path}.pre_change must not be empty for {action}")
        if action in {"remove", "replace"} and item.get("destructive_authorization") is not True:
            raise RunValidationError(f"{path}.destructive_authorization must be true for {action}")
        if action == "replace":
            _text(item.get("object_id"), f"{path}.object_id")
            _text(item.get("replacement_reason"), f"{path}.replacement_reason")
        if object_type == "template" and action in MUTATING_ACTIONS:
            _validate_permission_delta(item.get("permission_delta"), f"{path}.permission_delta")

        journal = _array(item.get("journal"), f"{path}.journal")
        for journal_index, entry_raw in enumerate(journal):
            journal_path = f"{path}.journal[{journal_index}]"
            entry = _object(entry_raw, journal_path)
            entry_state = _text(entry.get("state"), f"{journal_path}.state")
            if entry_state not in OPERATION_STATES:
                raise RunValidationError(
                    f"{journal_path}.state has unsupported value {entry_state!r}"
                )
            _timestamp(entry.get("at"), f"{journal_path}.at")
            _text(entry.get("note"), f"{journal_path}.note")
        if journal and journal[-1].get("state") != state:
            raise RunValidationError(f"{path}.journal final state must equal {path}.state")
        if state in {"saved", "verified"}:
            _object(item.get("result"), f"{path}.result")
        if state in {"failed", "uncertain"}:
            _text(item.get("error"), f"{path}.error")
        operations[operation_id] = item

    operation_ids = set(operations)
    for operation_id, dependencies in dependency_map.items():
        unknown = sorted(set(dependencies) - operation_ids)
        if unknown:
            raise RunValidationError(
                f"operation {operation_id!r} has unknown dependencies: {', '.join(unknown)}"
            )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(operation_id: str) -> None:
        if operation_id in visiting:
            raise RunValidationError(f"operation dependency cycle includes {operation_id!r}")
        if operation_id in visited:
            return
        visiting.add(operation_id)
        for dependency in dependency_map[operation_id]:
            visit(dependency)
        visiting.remove(operation_id)
        visited.add(operation_id)

    for operation_id in operations:
        visit(operation_id)
    return operations, object_claims


def _validate_payload_mappings(raw: Any, requirement_ids: set[str]) -> None:
    identities: set[tuple[str, str]] = set()
    for index, item_raw in enumerate(_array(raw, "$.payload_mappings")):
        path = f"$.payload_mappings[{index}]"
        item = _object(item_raw, path)
        requirement_id = _text(item.get("requirement_id"), f"{path}.requirement_id")
        if requirement_id not in requirement_ids:
            raise RunValidationError(f"{path}.requirement_id is unknown")
        destination_field = _text(item.get("destination_field"), f"{path}.destination_field")
        identity = (requirement_id, destination_field)
        if identity in identities:
            raise RunValidationError(f"duplicate payload mapping {identity!r}")
        identities.add(identity)
        _optional_text(item.get("source"), f"{path}.source")
        _optional_text(item.get("gtm_resolution"), f"{path}.gtm_resolution")
        _optional_text(item.get("template_field"), f"{path}.template_field")
        status = _text(item.get("status"), f"{path}.status")
        if status not in MAPPING_STATUSES:
            raise RunValidationError(f"{path}.status has unsupported value {status!r}")
        _text(item.get("provenance_locator"), f"{path}.provenance_locator")
        extended_keys = set(item) & EXTENDED_MAPPING_KEYS
        if extended_keys and extended_keys != EXTENDED_MAPPING_KEYS:
            missing = ", ".join(sorted(EXTENDED_MAPPING_KEYS - extended_keys))
            raise RunValidationError(f"{path} is missing extended mapping key(s): {missing}")
        if extended_keys:
            authority_grade = _optional_text(
                item.get("source_authority_grade"),
                f"{path}.source_authority_grade",
            )
            authority_locator = _optional_text(
                item.get("source_authority_locator"),
                f"{path}.source_authority_locator",
            )
            source_shape = _optional_text(item.get("source_shape"), f"{path}.source_shape")
            destination_shape = _optional_text(
                item.get("destination_shape"),
                f"{path}.destination_shape",
            )
            compatibility = _optional_text(
                item.get("shape_compatibility"),
                f"{path}.shape_compatibility",
            )
            method = _optional_text(item.get("mapping_method"), f"{path}.mapping_method")
            missing_behavior = _optional_text(
                item.get("missing_behavior"),
                f"{path}.missing_behavior",
            )
            if authority_grade is not None and authority_grade != "approved-input":
                raise RunValidationError(f"{path}.source_authority_grade must be 'approved-input'")
            if compatibility is not None and compatibility not in SHAPE_COMPATIBILITY:
                raise RunValidationError(
                    f"{path}.shape_compatibility has unsupported value {compatibility!r}"
                )
            if method is not None and method not in MAPPING_METHODS:
                raise RunValidationError(f"{path}.mapping_method has unsupported value {method!r}")
        if status == "mapped":
            _text(item.get("source"), f"{path}.source")
            _text(item.get("gtm_resolution"), f"{path}.gtm_resolution")
            _text(item.get("template_field"), f"{path}.template_field")
            if extended_keys:
                if authority_grade != "approved-input":
                    raise RunValidationError(
                        f"{path}.source_authority_grade must be 'approved-input' when mapped"
                    )
                if not authority_locator:
                    raise RunValidationError(
                        f"{path}.source_authority_locator is required when mapped"
                    )
                if not source_shape or not destination_shape:
                    raise RunValidationError(
                        f"{path} needs source_shape and destination_shape when mapped"
                    )
                if not compatibility or not method or not missing_behavior:
                    raise RunValidationError(
                        f"{path} needs shape_compatibility, mapping_method, and missing_behavior "
                        "when mapped"
                    )
                if method in {"direct-dlv", "native-template"} and compatibility != "compatible":
                    raise RunValidationError(
                        f"{path}.{method} requires compatible source and destination shapes"
                    )
                if method == "custom-javascript" and compatibility != "conversion-required":
                    raise RunValidationError(
                        f"{path}.custom-javascript requires a documented shape conversion"
                    )
        elif extended_keys and status in {"intentionally-omitted", "external", "blocked"}:
            if not missing_behavior:
                raise RunValidationError(f"{path}.missing_behavior is required for {status}")


def _validate_consent_routes(raw: Any, requirement_ids: set[str]) -> None:
    seen: set[str] = set()
    for index, item_raw in enumerate(_array(raw, "$.consent_routes")):
        path = f"$.consent_routes[{index}]"
        item = _object(item_raw, path)
        requirement_id = _text(item.get("requirement_id"), f"{path}.requirement_id")
        if requirement_id not in requirement_ids:
            raise RunValidationError(f"{path}.requirement_id is unknown")
        if requirement_id in seen:
            raise RunValidationError(f"duplicate consent route for {requirement_id!r}")
        seen.add(requirement_id)
        _text(item.get("product"), f"{path}.product")
        mode = _text(item.get("mode"), f"{path}.mode")
        if mode not in CONSENT_MODES:
            raise RunValidationError(f"{path}.mode has unsupported value {mode!r}")
        mechanism = _text(item.get("mechanism"), f"{path}.mechanism")
        if mechanism not in CONSENT_MECHANISMS:
            raise RunValidationError(f"{path}.mechanism has unsupported value {mechanism!r}")
        normal_trigger = _text(item.get("normal_trigger"), f"{path}.normal_trigger")
        blocking = _unique_texts(item.get("blocking_triggers"), f"{path}.blocking_triggers")
        _text(item.get("unknown_behavior"), f"{path}.unknown_behavior")
        _unique_texts(item.get("evidence"), f"{path}.evidence", allow_empty=False)
        block_scope = _optional_text(
            item.get("blocking_event_scope"),
            f"{path}.blocking_event_scope",
        )
        scope_reason = _optional_text(
            item.get("scope_exception_reason"),
            f"{path}.scope_exception_reason",
        )
        if mode == "strict-basic":
            if not blocking:
                raise RunValidationError(
                    f"{path}.blocking_triggers must not be empty under strict-basic consent"
                )
            if not block_scope:
                raise RunValidationError(
                    f"{path}.blocking_event_scope is required under strict-basic consent"
                )
            if block_scope != DEFAULT_VENDOR_BLOCK_SCOPE and not scope_reason:
                raise RunValidationError(
                    f"{path}.scope_exception_reason is required when blocking_event_scope is not "
                    f"{DEFAULT_VENDOR_BLOCK_SCOPE!r}"
                )
        if mechanism == "native-advanced" and mode != "advanced-native":
            raise RunValidationError(f"{path}.native-advanced requires advanced-native mode")
        if mode == "advanced-native":
            if mechanism != "native-advanced":
                raise RunValidationError(f"{path}.advanced-native requires native-advanced")
            if blocking or block_scope:
                raise RunValidationError(
                    f"{path}.advanced-native must not carry a defeating blocking trigger"
                )
        if not normal_trigger:
            raise RunValidationError(f"{path}.normal_trigger must be non-empty")


def _validate_readback(
    raw: Any,
    *,
    operations: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for index, item_raw in enumerate(_array(raw, "$.saved_readback")):
        path = f"$.saved_readback[{index}]"
        item = _object(item_raw, path)
        operation_id = _text(item.get("operation_id"), f"{path}.operation_id")
        if operation_id not in operations:
            raise RunValidationError(f"{path}.operation_id is unknown")
        if operation_id in records:
            raise RunValidationError(f"duplicate saved readback for {operation_id!r}")
        if (
            _text(item.get("object_key"), f"{path}.object_key")
            != operations[operation_id]["object_key"]
        ):
            raise RunValidationError(f"{path}.object_key does not match its operation")
        if item.get("verified") is not True:
            raise RunValidationError(f"{path}.verified must be true")
        differences = _array(item.get("differences"), f"{path}.differences")
        if differences:
            raise RunValidationError(f"{path}.differences must be empty when verified")
        _optional_text(item.get("object_id"), f"{path}.object_id")
        _optional_text(item.get("fingerprint"), f"{path}.fingerprint")
        _timestamp(item.get("verified_at"), f"{path}.verified_at")
        records[operation_id] = item
    return records


def _validate_official_sources(raw: Any) -> None:
    for index, item_raw in enumerate(_array(raw, "$.official_sources")):
        path = f"$.official_sources[{index}]"
        item = _object(item_raw, path)
        url = _text(item.get("url"), f"{path}.url")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise RunValidationError(f"{path}.url must be an absolute HTTPS URL")
        _text(item.get("title"), f"{path}.title")
        _date(item.get("access_date"), f"{path}.access_date")
        _unique_texts(item.get("supports"), f"{path}.supports", allow_empty=False)


def _validate_external_dependencies(raw: Any, requirement_ids: set[str]) -> None:
    seen: set[str] = set()
    for index, item_raw in enumerate(_array(raw, "$.external_dependencies")):
        path = f"$.external_dependencies[{index}]"
        item = _object(item_raw, path)
        dependency_id = _text(item.get("id"), f"{path}.id")
        if dependency_id in seen:
            raise RunValidationError(f"duplicate external dependency id {dependency_id!r}")
        seen.add(dependency_id)
        linked = set(_unique_texts(item.get("requirement_ids"), f"{path}.requirement_ids"))
        if linked - requirement_ids:
            raise RunValidationError(f"{path}.requirement_ids contains unknown IDs")
        _text(item.get("owner"), f"{path}.owner")
        _text(item.get("action"), f"{path}.action")
        if _text(item.get("status"), f"{path}.status") not in {"open", "resolved", "deferred"}:
            raise RunValidationError(f"{path}.status is unsupported")


def _validate_recovery_boundary(value: Any, *, required: bool) -> None:
    if value is None:
        if required:
            raise RunValidationError("$.recovery_boundary is required for Partial")
        return
    boundary = _object(value, "$.recovery_boundary")
    _text(boundary.get("reason"), "$.recovery_boundary.reason")
    _optional_text(
        boundary.get("last_verified_operation"),
        "$.recovery_boundary.last_verified_operation",
    )
    _unique_texts(boundary.get("unsafe_operations"), "$.recovery_boundary.unsafe_operations")
    _text(boundary.get("next_action"), "$.recovery_boundary.next_action")


def _validate_recette_handoff(raw: Any, requirement_ids: set[str]) -> None:
    handoff = _object(raw, "$.recette_handoff")
    if _text(handoff.get("manifest_version"), "$.recette_handoff.manifest_version") != "1.0":
        raise RunValidationError("$.recette_handoff.manifest_version must be '1.0'")
    records = _array(handoff.get("requirements"), "$.recette_handoff.requirements")
    seen: set[str] = set()
    for index, item_raw in enumerate(records):
        path = f"$.recette_handoff.requirements[{index}]"
        item = _object(item_raw, path)
        requirement_id = _text(item.get("id"), f"{path}.id")
        if requirement_id not in requirement_ids or requirement_id in seen:
            raise RunValidationError(f"{path}.id is unknown or duplicated")
        seen.add(requirement_id)
        _unique_texts(item.get("expected_tags"), f"{path}.expected_tags")
        _unique_texts(item.get("expected_consent_states"), f"{path}.expected_consent_states")
        _unique_texts(item.get("cues"), f"{path}.cues")
    if seen != requirement_ids:
        raise RunValidationError("$.recette_handoff.requirements must cover every requirement")
    if handoff.get("runtime_validation_performed") is not False:
        raise RunValidationError("$.recette_handoff.runtime_validation_performed must be false")
    if handoff.get("publication_performed") is not False:
        raise RunValidationError("$.recette_handoff.publication_performed must be false")


def validate_document(value: Any) -> dict[str, Any]:
    """Validate a versioned configuration-run and enforce final-state invariants."""
    document = _object(value, "$")
    unexpected = sorted(set(document) - TOP_LEVEL_KEYS)
    missing = sorted(TOP_LEVEL_KEYS - set(document))
    if unexpected:
        raise RunValidationError(f"unexpected top-level key(s): {', '.join(unexpected)}")
    if missing:
        raise RunValidationError(f"missing top-level key(s): {', '.join(missing)}")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise RunValidationError(f"$.schema_version must be {SCHEMA_VERSION!r}")

    run, requirement_ids, status = _validate_run_header(document["run"])
    requirements = _validate_requirements(document["requirements"], requirement_ids)
    operations, _ = _validate_object_changes(
        document["object_changes"],
        requirement_ids=requirement_ids,
    )
    _validate_payload_mappings(document["payload_mappings"], requirement_ids)
    _validate_consent_routes(document["consent_routes"], requirement_ids)
    readback = _validate_readback(document["saved_readback"], operations=operations)
    _validate_official_sources(document["official_sources"])
    _validate_external_dependencies(document["external_dependencies"], requirement_ids)
    _validate_recovery_boundary(document["recovery_boundary"], required=status == "Partial")

    idempotency = _object(document["idempotency"], "$.idempotency")
    if not isinstance(idempotency.get("checked"), bool):
        raise RunValidationError("$.idempotency.checked must be a boolean")
    remaining_actions = _unique_texts(
        idempotency.get("remaining_actions"),
        "$.idempotency.remaining_actions",
    )
    _validate_recette_handoff(document["recette_handoff"], requirement_ids)

    states = {operation_id: item["state"] for operation_id, item in operations.items()}
    written_states = {"saved", "verified"}
    failed_states = {"failed", "uncertain"}
    if status == "Configured":
        if run["phase"] != "complete":
            raise RunValidationError("Configured requires $.run.phase 'complete'")
        invalid_requirements = sorted(
            requirement_id
            for requirement_id, item in requirements.items()
            if item["status"] not in {"Configured", "Deferred"}
        )
        if invalid_requirements:
            raise RunValidationError(
                "Configured has unfinished requirements: " + ", ".join(invalid_requirements)
            )
        unfinished = sorted(
            operation_id
            for operation_id, state in states.items()
            if state not in {"verified", "skipped"}
        )
        if unfinished:
            raise RunValidationError(
                "Configured has unfinished object operations: " + ", ".join(unfinished)
            )
        missing_readback = sorted(
            operation_id
            for operation_id, item in operations.items()
            if item["state"] == "verified" and operation_id not in readback
        )
        if missing_readback:
            raise RunValidationError(
                "Configured lacks verified readback for: " + ", ".join(missing_readback)
            )
        if not idempotency["checked"] or remaining_actions:
            raise RunValidationError(
                "Configured requires checked idempotency with no remaining actions"
            )
        configured_requirement_ids = {
            requirement_id
            for requirement_id, item in requirements.items()
            if item["status"] == "Configured"
        }
        preflight_issues = _preflight_issues(document, configured_requirement_ids)
        if preflight_issues:
            raise RunValidationError(
                "Configured has unresolved preflight decisions: " + "; ".join(preflight_issues)
            )
        if document["recovery_boundary"] is not None:
            raise RunValidationError("Configured requires a null recovery boundary")
    elif status == "Partial":
        if not any(state in written_states for state in states.values()):
            raise RunValidationError("Partial requires at least one saved or verified operation")
        if not any(
            state in failed_states | {"planned", "in_progress"} for state in states.values()
        ):
            raise RunValidationError("Partial requires unfinished or uncertain work")
    elif status == "Blocked":
        if any(state in written_states for state in states.values()):
            raise RunValidationError("Blocked with saved current-run work must be Partial")
        if any(state == "in_progress" for state in states.values()):
            raise RunValidationError("Blocked cannot contain an in-progress operation")
    elif status == "Deferred":
        if any(item["status"] != "Deferred" for item in requirements.values()):
            raise RunValidationError("Deferred requires every requirement to be Deferred")
        if any(state in written_states | {"in_progress"} for state in states.values()):
            raise RunValidationError("Deferred cannot contain a current-run mutation")
    elif run["phase"] == "complete":
        raise RunValidationError("In progress cannot use $.run.phase 'complete'")
    return document


def load_document(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RunValidationError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RunValidationError(f"invalid JSON in {path}: {exc}") from exc
    return validate_document(value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _contract_fingerprint(contract: dict[str, Any]) -> str:
    encoded = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _field_mappings(requirement: dict[str, Any]) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    for map_name in ("parameters", "user_properties", "item_parameters"):
        for field_name, field in requirement.get(map_name, {}).items():
            source = field.get("source")
            if source is None and "literal" in field:
                source = f"literal:{field['literal']}"
            source_authority = field.get("source_authority")
            if (
                source is not None
                and source_authority is None
                and field["provenance"].get("grade") == "approved-input"
            ):
                source_authority = field["provenance"]
            mappings.append(
                {
                    "requirement_id": requirement["id"],
                    "destination_field": field_name,
                    "source": source,
                    "source_authority_grade": (
                        source_authority.get("grade") if source_authority else None
                    ),
                    "source_authority_locator": (
                        source_authority.get("locator") if source_authority else None
                    ),
                    "source_shape": field.get("source_shape"),
                    "destination_shape": field.get("destination_shape"),
                    "shape_compatibility": None,
                    "mapping_method": None,
                    "gtm_resolution": None,
                    "template_field": None,
                    "missing_behavior": None,
                    "status": "pending",
                    "provenance_locator": field["provenance"]["locator"],
                }
            )
    return mappings


def _preflight_issues(
    document: dict[str, Any],
    requirement_ids: set[str],
) -> list[str]:
    issues: list[str] = []
    for mapping in document["payload_mappings"]:
        if mapping["requirement_id"] not in requirement_ids:
            continue
        identity = f"{mapping['requirement_id']}::{mapping['destination_field']}"
        if mapping["status"] == "pending":
            issues.append(f"payload mapping {identity} is pending")
        elif mapping["status"] == "blocked":
            issues.append(f"payload mapping {identity} is blocked")

    requirements = {
        item["id"]: item for item in document["requirements"] if item["id"] in requirement_ids
    }
    consent_by_requirement = {item["requirement_id"]: item for item in document["consent_routes"]}
    for requirement_id, requirement in requirements.items():
        if requirement["kind"] == "consent" or requirement["status"] == "Deferred":
            continue
        if requirement_id not in consent_by_requirement:
            issues.append(f"consent route {requirement_id} is missing")
    return issues


def create_from_contract(
    contract: dict[str, Any],
    *,
    run_id: str,
    source_locator: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Ingest a strict configuration contract without changing requirement semantics."""
    try:
        contract = validate_configuration_contract(contract)
    except ContractValidationError as exc:
        raise RunValidationError(str(exc)) from exc
    now = timestamp or _utc_now()
    _timestamp(now, "timestamp")
    contract_ids = [item["id"] for item in contract["requirements"]]
    route = contract["route"]
    requirements = []
    payload_mappings = []
    for requirement in contract["requirements"]:
        kind = requirement.get("kind", route)
        requirements.append(
            {
                "id": requirement["id"],
                "kind": kind,
                "source_locator": requirement["authority"]["locator"],
                "source_event": requirement.get("source_event"),
                "destination": requirement.get("destination") or requirement.get("event_name"),
                "status": "In progress",
                "object_keys": [],
            }
        )
        payload_mappings.extend(_field_mappings(requirement))

    operation_ids_by_object_key = {
        _canonical_object_key(item["object_type"], item["name"]): f"OP-{index:03d}"
        for index, item in enumerate(contract["implementation"]["objects"], start=1)
    }
    object_changes = []
    for index, item in enumerate(contract["implementation"]["objects"], start=1):
        linked_ids = item.get("requirement_ids")
        if linked_ids is None:
            if len(contract_ids) != 1:
                raise RunValidationError(
                    "every object action in a multi-requirement contract needs requirement_ids"
                )
            linked_ids = contract_ids
        object_key = _canonical_object_key(item["object_type"], item["name"])
        dependencies = [
            operation_ids_by_object_key[dependency] for dependency in item.get("dependencies", [])
        ]
        record = {
            "operation_id": f"OP-{index:03d}",
            "requirement_ids": linked_ids,
            "action": item["action"],
            "object_type": item["object_type"],
            "name": item["name"],
            "object_key": object_key,
            "dependencies": dependencies,
            "intended": item.get("intended"),
            "state": "planned",
            "evidence": item["evidence"],
            "journal": [],
        }
        for optional in (
            "object_id",
            "pre_change",
            "destructive_authorization",
            "replacement_reason",
            "permission_delta",
        ):
            if optional in item:
                record[optional] = item[optional]
        if item["action"] == "remove":
            record.pop("intended", None)
        object_changes.append(record)
        for requirement in requirements:
            if requirement["id"] in linked_ids:
                requirement["object_keys"].append(object_key)

    official_sources = [
        {
            "url": evidence["url"],
            "title": evidence["title"],
            "access_date": evidence["access_date"],
            "supports": [evidence["locator"]],
        }
        for evidence in contract["evidence"]
        if evidence["grade"] == "official-current"
    ]
    external_dependencies = []
    for index, dependency in enumerate(contract["external_dependencies"], start=1):
        if isinstance(dependency, str):
            external_dependencies.append(
                {
                    "id": f"EXT-{index:03d}",
                    "requirement_ids": contract_ids,
                    "owner": "external",
                    "action": dependency,
                    "status": "open",
                }
            )
        else:
            external_dependencies.append(dependency)

    workspace = contract["implementation"]["workspace"]
    document = {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "id": run_id,
            "phase": "preflight",
            "status": "In progress",
            "started_at": now,
            "updated_at": now,
            "target": {
                "account_id": workspace["account_id"],
                "container_id": workspace["container_id"],
                "workspace_id": workspace["id"],
                "container_type": "web",
            },
            "contract": {
                "schema_version": contract["schema_version"],
                "requirement_ids": contract_ids,
                "source_locator": source_locator,
                "fingerprint": _contract_fingerprint(contract),
            },
            "publication": {"performed": False, "version_created": False},
        },
        "requirements": requirements,
        "object_changes": object_changes,
        "payload_mappings": payload_mappings,
        "consent_routes": [],
        "saved_readback": [],
        "official_sources": official_sources,
        "external_dependencies": external_dependencies,
        "recovery_boundary": None,
        "idempotency": {"checked": False, "remaining_actions": []},
        "recette_handoff": {
            "manifest_version": "1.0",
            "requirements": [
                {
                    "id": requirement_id,
                    "expected_tags": [],
                    "expected_consent_states": [],
                    "cues": [],
                }
                for requirement_id in contract_ids
            ],
            "runtime_validation_performed": False,
            "publication_performed": False,
        },
    }
    return validate_document(document)


def inspect_document(document: dict[str, Any]) -> dict[str, Any]:
    document = validate_document(document)
    states = {item["operation_id"]: item["state"] for item in document["object_changes"]}
    ready = []
    waiting: dict[str, list[str]] = {}
    preflight_blockers: dict[str, list[str]] = {}
    unsafe = []
    for item in document["object_changes"]:
        operation_id = item["operation_id"]
        if item["state"] in {"in_progress", "uncertain"}:
            unsafe.append(operation_id)
        if item["state"] != "planned":
            continue
        pending_dependencies = [
            dependency
            for dependency in item["dependencies"]
            if states[dependency] not in {"verified", "skipped"}
        ]
        if pending_dependencies:
            waiting[operation_id] = pending_dependencies
        elif item["action"] in MUTATING_ACTIONS:
            issues = _preflight_issues(document, set(item["requirement_ids"]))
            if issues:
                preflight_blockers[operation_id] = issues
            else:
                ready.append(operation_id)
        else:
            ready.append(operation_id)
    return {
        "pass": not unsafe,
        "resumable": not unsafe,
        "ready_operations": ready,
        "waiting_on_dependencies": waiting,
        "preflight_blockers": preflight_blockers,
        "unsafe_operations": unsafe,
    }


def checkpoint_operation(
    document: dict[str, Any],
    *,
    operation_id: str,
    state: str,
    note: str,
    timestamp: str | None = None,
    result: dict[str, Any] | None = None,
    comparison: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Apply one validated state transition; callers persist only the returned document."""
    document = validate_document(document)
    if state not in OPERATION_STATES:
        raise RunValidationError(f"unsupported checkpoint state {state!r}")
    operations = {item["operation_id"]: item for item in document["object_changes"]}
    if operation_id not in operations:
        raise RunValidationError(f"unknown operation_id {operation_id!r}")
    operation = operations[operation_id]
    current = operation["state"]
    if state not in ALLOWED_TRANSITIONS[current]:
        raise RunValidationError(f"invalid state transition {current!r} -> {state!r}")
    if (
        current == "planned"
        and state in {"in_progress", "saved", "verified"}
        and operation["action"] in MUTATING_ACTIONS
    ):
        issues = _preflight_issues(document, set(operation["requirement_ids"]))
        if issues:
            raise RunValidationError("preflight is incomplete: " + "; ".join(issues))
    at = timestamp or _utc_now()
    _timestamp(at, "timestamp")
    note = _text(note, "note")
    if state in {"saved", "verified"} and result is None:
        raise RunValidationError(f"{state} requires a saved result")
    if state == "verified":
        if not isinstance(comparison, dict) or comparison.get("pass") is not True:
            raise RunValidationError("verified requires a passing saved-readback comparison")
    if state in {"failed", "uncertain"}:
        error = _text(error, "error")

    operation["state"] = state
    operation.setdefault("journal", []).append({"state": state, "at": at, "note": note})
    if result is not None:
        operation["result"] = result
    if error is not None:
        operation["error"] = error
    if state == "verified":
        document["saved_readback"] = [
            item for item in document["saved_readback"] if item["operation_id"] != operation_id
        ]
        document["saved_readback"].append(
            {
                "operation_id": operation_id,
                "object_key": operation["object_key"],
                "object_id": (result or {}).get("object_id"),
                "fingerprint": (result or {}).get("fingerprint"),
                "verified": True,
                "differences": [],
                "verified_at": at,
            }
        )
    document["run"]["updated_at"] = at
    if state in {"in_progress", "saved"}:
        document["run"]["phase"] = "mutation"
    elif state in {"verified", "failed", "uncertain"}:
        document["run"]["phase"] = "readback"
    return validate_document(document)


def reopen_failed_operation(
    document: dict[str, Any],
    *,
    operation_id: str,
    note: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Explicitly reopen a proved failed/no-write operation after its blocker is resolved."""
    document = validate_document(document)
    operations = {item["operation_id"]: item for item in document["object_changes"]}
    if operation_id not in operations:
        raise RunValidationError(f"unknown operation_id {operation_id!r}")
    operation = operations[operation_id]
    if operation["state"] != "failed":
        raise RunValidationError("only a failed operation can be explicitly reopened")
    at = timestamp or _utc_now()
    _timestamp(at, "timestamp")
    note = _text(note, "note")

    operation["state"] = "planned"
    operation.setdefault("journal", []).append({"state": "planned", "at": at, "note": note})
    operation.pop("error", None)
    operation.pop("result", None)
    document["saved_readback"] = [
        item for item in document["saved_readback"] if item["operation_id"] != operation_id
    ]
    for requirement in document["requirements"]:
        if requirement["id"] in operation["requirement_ids"]:
            requirement["status"] = "In progress"
    document["run"]["phase"] = "mutation"
    document["run"]["status"] = "In progress"
    document["run"]["updated_at"] = at
    document["recovery_boundary"] = None
    document["idempotency"] = {"checked": False, "remaining_actions": []}
    return validate_document(document)


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _json_file(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunValidationError(f"cannot load {label} {path}: {exc}") from exc
    return _object(value, label)


def render_markdown(document: dict[str, Any], *, embed_machine: bool = False) -> str:
    """Render one manifest into executive, analyst, and optional machine layers."""
    document = validate_document(document)
    run = document["run"]
    operations = document["object_changes"]
    counts: dict[str, int] = {}
    for item in operations:
        counts[item["action"]] = counts.get(item["action"], 0) + 1
    preview = run["phase"] == "preflight" and all(item["state"] == "planned" for item in operations)
    heading = "Pre-mutation impact preview" if preview else "GTM configuration handoff"
    lines = [
        f"# {heading}",
        "",
        "## Executive summary",
        "",
        f"- Verdict: **{run['status']}**",
        (
            "- Target: account `{account_id}` / container `{container_id}` / workspace "
            "`{workspace_id}`"
        ).format(**run["target"]),
        f"- Requirements: {len(document['requirements'])}",
        "- Intended object actions: "
        + (", ".join(f"{action} {count}" for action, count in sorted(counts.items())) or "none"),
        "- Consent routes: " + str(len(document["consent_routes"])),
        "- Publication: not performed; no GTM version created",
    ]
    if preview:
        preflight_blockers = inspect_document(document)["preflight_blockers"]
        high_impact = [
            item
            for item in operations
            if item["object_type"]
            in {
                "zone",
                "environment",
                "destination",
                "google tag configuration",
                "container setting",
                "template",
            }
            or item["action"] in {"remove", "replace"}
        ]
        lines.append(
            "- Preflight decision: "
            + (
                f"resolve mapping/consent blockers on {len(preflight_blockers)} operation(s)"
                if preflight_blockers
                else (
                    f"explicit authority required for {len(high_impact)} "
                    "high-impact/destructive action(s)"
                    if high_impact
                    else "routine in-scope writes may proceed without a separate approval pause"
                )
            )
        )

    lines.extend(["", "## Analyst and developer change log", ""])
    if not operations:
        lines.append("No GTM object operation is recorded.")
    for item in operations:
        lines.extend(
            [
                f"### [{item['action'].upper()} / {item['state'].upper()}] {item['object_key']}",
                "",
                f"- Requirements: {', '.join(item['requirement_ids'])}",
                "- Dependencies: " + (", ".join(item["dependencies"]) or "none"),
                f"- Evidence: {', '.join(item['evidence'])}",
            ]
        )
        if item.get("replacement_reason"):
            lines.append(f"- Replacement reason: {item['replacement_reason']}")
        if item.get("permission_delta"):
            delta = item["permission_delta"]
            lines.append(
                "- Template permission delta: added "
                + (", ".join(delta["added"]) or "none")
                + "; removed "
                + (", ".join(delta["removed"]) or "none")
            )
        if item.get("error"):
            lines.append(f"- Error: {item['error']}")
        lines.append("")

    lines.extend(["## Payload and consent mapping", ""])
    for requirement in document["requirements"]:
        requirement_id = requirement["id"]
        mappings = [
            item
            for item in document["payload_mappings"]
            if item["requirement_id"] == requirement_id
        ]
        consent = next(
            (
                item
                for item in document["consent_routes"]
                if item["requirement_id"] == requirement_id
            ),
            None,
        )
        lines.append(f"### {requirement_id} — {requirement['status']}")
        lines.append("")
        lines.append(f"- Source event: {requirement.get('source_event') or 'not applicable'}")
        lines.append(f"- Destination: {requirement.get('destination') or 'not supplied'}")
        if consent:
            lines.append(
                f"- Consent: {consent['mode']} via {consent['mechanism']} "
                f"on `{consent['normal_trigger']}`; block scope "
                f"`{consent.get('blocking_event_scope') or 'not applicable'}`"
            )
        else:
            lines.append("- Consent: not yet recorded")
        for mapping in mappings:
            lines.append(
                "- Field `{field}`: `{source}` [{source_shape}] → {method} "
                "→ `{resolution}` → `{template}` [{destination_shape}] ({status})".format(
                    field=mapping["destination_field"],
                    source=mapping.get("source") or "unresolved",
                    source_shape=mapping.get("source_shape") or "shape unresolved",
                    method=mapping.get("mapping_method") or "method unresolved",
                    resolution=mapping.get("gtm_resolution") or "unresolved",
                    template=mapping.get("template_field") or "unresolved",
                    destination_shape=mapping.get("destination_shape") or "shape unresolved",
                    status=mapping["status"],
                )
            )
        lines.append("")

    lines.extend(["## External actions and handoff", ""])
    for dependency in document["external_dependencies"]:
        lines.append(f"- [{dependency['status']}] {dependency['owner']}: {dependency['action']}")
    if not document["external_dependencies"]:
        lines.append("- No external dependency recorded.")
    lines.extend(
        [
            "- Runtime GTM Preview/recette was not performed.",
            "- Publication and GTM version creation were not performed.",
            "",
            "## Machine handoff",
            "",
            f"- Schema: `configure-gtm/configuration-run@{SCHEMA_VERSION}`",
            f"- Run ID: `{run['id']}`",
            f"- Contract fingerprint: `{run['contract']['fingerprint']}`",
        ]
    )
    if embed_machine:
        lines.extend(
            [
                "",
                "```json",
                json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False),
                "```",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _emit_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--run", type=Path, required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--contract", type=Path, required=True)
    init_parser.add_argument("--run-id", required=True)
    init_parser.add_argument("--source-locator", required=True)
    init_parser.add_argument("--timestamp")
    init_parser.add_argument("--output", type=Path, required=True)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--run", type=Path, required=True)

    checkpoint_parser = subparsers.add_parser("checkpoint")
    checkpoint_parser.add_argument("--run", type=Path, required=True)
    checkpoint_parser.add_argument("--operation", required=True)
    checkpoint_parser.add_argument("--state", choices=sorted(OPERATION_STATES), required=True)
    checkpoint_parser.add_argument("--note", required=True)
    checkpoint_parser.add_argument("--timestamp")
    checkpoint_parser.add_argument("--result", type=Path)
    checkpoint_parser.add_argument("--comparison", type=Path)
    checkpoint_parser.add_argument("--error")

    reopen_parser = subparsers.add_parser("reopen")
    reopen_parser.add_argument("--run", type=Path, required=True)
    reopen_parser.add_argument("--operation", required=True)
    reopen_parser.add_argument("--note", required=True)
    reopen_parser.add_argument("--timestamp")

    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--run", type=Path, required=True)
    render_parser.add_argument("--output", type=Path)
    render_parser.add_argument("--embed-machine", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "validate":
            document = load_document(args.run)
            _emit_json({"pass": True, "schema_version": document["schema_version"]})
        elif args.command == "init":
            contract = _json_file(args.contract, "contract")
            document = create_from_contract(
                contract,
                run_id=args.run_id,
                source_locator=args.source_locator,
                timestamp=args.timestamp,
            )
            atomic_write(args.output, document)
            _emit_json({"pass": True, "output": str(args.output.resolve())})
        elif args.command == "inspect":
            _emit_json(inspect_document(load_document(args.run)))
        elif args.command == "checkpoint":
            result = _json_file(args.result, "result") if args.result else None
            comparison = _json_file(args.comparison, "comparison") if args.comparison else None
            document = checkpoint_operation(
                load_document(args.run),
                operation_id=args.operation,
                state=args.state,
                note=args.note,
                timestamp=args.timestamp,
                result=result,
                comparison=comparison,
                error=args.error,
            )
            atomic_write(args.run, document)
            _emit_json({"pass": True, "operation": args.operation, "state": args.state})
        elif args.command == "reopen":
            document = reopen_failed_operation(
                load_document(args.run),
                operation_id=args.operation,
                note=args.note,
                timestamp=args.timestamp,
            )
            atomic_write(args.run, document)
            _emit_json({"pass": True, "operation": args.operation, "state": "planned"})
        else:
            rendered = render_markdown(
                load_document(args.run),
                embed_machine=args.embed_machine,
            )
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(rendered, encoding="utf-8", newline="\n")
                _emit_json({"pass": True, "output": str(args.output.resolve())})
            else:
                sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
                print(rendered, end="")
    except RunValidationError as exc:
        _emit_json({"pass": False, "error": str(exc)})
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
