#!/usr/bin/env python3
"""Active shared web-domain rules plus the configuration-run@2.1 compatibility engine.

Run@3.0 web records are adapted through ``web_domain_validation`` and validated here, so this
module remains authoritative for web semantics. Its run-state/CLI compatibility functions are
retained for safe v8 artifact migration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from run_model_web import (
    ALLOWED_TRANSITIONS,
    BUILT_IN_TRIGGER_TYPES,
    CONFIGURATION_FIELD_ALIASES,
    CONSENT_MECHANISMS,
    CONSENT_MODES,
    CUSTOM_CODE_TAG_TYPES,
    DEFAULT_VENDOR_BLOCK_SCOPE,
    ECOMMERCE_ROUTES,
    EXECUTION_MODES,
    EXTENDED_MAPPING_KEYS,
    FIRING_OPTIONS,
    FIRST_PARTY_FEATURES,
    FIRST_PARTY_PRODUCTS,
    GA4_EVENT_TAG_TYPES,
    GOOGLE_ADS_CONVERSION_TAG_TYPES,
    GOOGLE_CONFIGURATION_TAG_TYPES,
    INVENTORY_DISPOSITIONS,
    LEGACY_SCHEMA_VERSIONS,
    LIFECYCLE_ROLES,
    MAPPING_METHODS,
    MAPPING_STATUSES,
    NON_EXECUTING_TAG_ACTIONS,
    NORMAL_TRIGGER_ROLES,
    NORMAL_TRIGGER_TYPES,
    OPERATION_STATES,
    PAGE_LOAD_TRIGGER_TYPES,
    PAGE_VIEW_OWNERS,
    PRE_CMP_POLICIES,
    REQUIREMENT_STATUSES,
    RUN_PHASES,
    RUN_STATUSES,
    SCHEMA_VERSION,
    SHAPE_COMPATIBILITY,
    TAG_TYPE_ALIASES,
    TOP_LEVEL_KEYS,
    TRIGGER_TYPE_ALIASES,
    VERIFICATION_SCHEMA_VERSION,
)
from strict_json import StrictJsonError, load_json, write_json_atomic, write_text_atomic
from validate_configuration_contract_v5 import (
    ACTIONS,
    DELTA_ACTIONS,
    MUTATING_ACTIONS,
    OBJECT_RESOURCE_FAMILIES,
    ContractValidationError,
)
from validate_configuration_contract_v5 import (
    validate_document as validate_configuration_contract,
)


class RunValidationError(ValueError):
    """Raised when a configuration-run manifest violates the operational contract."""

    def __init__(self, message: str, *, error_code: str = "invalid_run") -> None:
        super().__init__(message)
        self.error_code = error_code


class RunConflictError(RunValidationError):
    """Raised when another controller owns the same run artifact."""


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RunValidationError(f"{path} must be an object")
    return value


def _exact_keys(
    value: dict[str, Any],
    path: str,
    *,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    allowed = required | (optional or set())
    missing = sorted(required - set(value))
    unexpected = sorted(set(value) - allowed)
    if missing:
        raise RunValidationError(f"{path} is missing key(s): {', '.join(missing)}")
    if unexpected:
        raise RunValidationError(f"{path} contains unexpected key(s): {', '.join(unexpected)}")


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


def canonical_sha256(value: Any) -> str:
    """Hash one JSON-compatible value with one stable Unicode representation."""
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise RunValidationError(f"value cannot be fingerprinted safely: {exc}") from exc
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _verification_target(operation: dict[str, Any]) -> Any:
    if operation.get("action") == "remove":
        return {
            "action": "remove",
            "object_key": operation.get("object_key"),
            "expected_saved_state": None,
        }
    if isinstance(operation.get("intended"), dict):
        return operation["intended"]
    if operation.get("action") in {"reuse", "untouched"} and isinstance(
        operation.get("pre_change"), dict
    ):
        return operation["pre_change"]
    return {
        "action": operation.get("action"),
        "object_id": operation.get("object_id"),
        "object_key": operation.get("object_key"),
    }


def _required_comparison_fields(operation: dict[str, Any]) -> set[str]:
    target = _verification_target(operation)
    if not isinstance(target, dict) or not target:
        raise RunValidationError("verification target must be a non-empty object")
    return set(target)


def build_verification_comparison(
    operation: dict[str, Any],
    saved: Any,
    *,
    comparator: str,
    compared_fields: list[str],
    differences: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build auditable adapter evidence without persisting the complete saved object."""
    normalized_fields = _unique_texts(
        compared_fields,
        "compared_fields",
        allow_empty=False,
    )
    missing_fields = sorted(_required_comparison_fields(operation) - set(normalized_fields))
    if missing_fields:
        raise RunValidationError(
            "compared_fields does not cover intended field(s): " + ", ".join(missing_fields)
        )
    return {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "comparator": _text(comparator, "comparator"),
        "pass": not differences,
        "intended_sha256": canonical_sha256(_verification_target(operation)),
        "saved_sha256": canonical_sha256(saved),
        "compared_fields": normalized_fields,
        "differences": deepcopy(differences),
    }


_UNSET = object()


def validate_verification_comparison(
    value: Any,
    *,
    operation: dict[str, Any],
    saved: Any = _UNSET,
    require_pass: bool = False,
) -> dict[str, Any]:
    """Validate structured equality evidence and bind it to the immutable intention."""
    path = "comparison"
    comparison = _object(value, path)
    required = {
        "schema_version",
        "comparator",
        "pass",
        "intended_sha256",
        "saved_sha256",
        "compared_fields",
        "differences",
    }
    unexpected = sorted(set(comparison) - required)
    missing = sorted(required - set(comparison))
    if unexpected:
        raise RunValidationError(f"{path} contains unexpected key(s): {', '.join(unexpected)}")
    if missing:
        raise RunValidationError(f"{path} is missing key(s): {', '.join(missing)}")
    if comparison.get("schema_version") != VERIFICATION_SCHEMA_VERSION:
        raise RunValidationError(f"{path}.schema_version must be {VERIFICATION_SCHEMA_VERSION!r}")
    _text(comparison.get("comparator"), f"{path}.comparator")
    passed = comparison.get("pass")
    if not isinstance(passed, bool):
        raise RunValidationError(f"{path}.pass must be a boolean")
    intended_sha256 = _text(comparison.get("intended_sha256"), f"{path}.intended_sha256")
    saved_sha256 = _text(comparison.get("saved_sha256"), f"{path}.saved_sha256")
    for field_path, fingerprint in (
        (f"{path}.intended_sha256", intended_sha256),
        (f"{path}.saved_sha256", saved_sha256),
    ):
        if len(fingerprint) != 71 or not fingerprint.startswith("sha256:"):
            raise RunValidationError(f"{field_path} must be a sha256 fingerprint")
        try:
            int(fingerprint.removeprefix("sha256:"), 16)
        except ValueError as exc:
            raise RunValidationError(f"{field_path} must be a sha256 fingerprint") from exc
    expected_intended = canonical_sha256(_verification_target(operation))
    if intended_sha256 != expected_intended:
        raise RunValidationError(f"{path}.intended_sha256 does not match the operation")
    if saved is not _UNSET and saved_sha256 != canonical_sha256(saved):
        raise RunValidationError(f"{path}.saved_sha256 does not match adapter readback")
    compared_fields = _unique_texts(
        comparison.get("compared_fields"),
        f"{path}.compared_fields",
        allow_empty=False,
    )
    missing_fields = sorted(_required_comparison_fields(operation) - set(compared_fields))
    if missing_fields:
        raise RunValidationError(
            f"{path}.compared_fields does not cover intended field(s): " + ", ".join(missing_fields)
        )
    differences = _array(comparison.get("differences"), f"{path}.differences")
    for index, difference in enumerate(differences):
        if not isinstance(difference, dict) or not difference:
            raise RunValidationError(f"{path}.differences[{index}] must be a non-empty object")
    if passed and differences:
        raise RunValidationError(f"{path}.differences must be empty when pass is true")
    if not passed and not differences:
        raise RunValidationError(f"{path}.differences must explain a failed comparison")
    if require_pass and not passed:
        raise RunValidationError("verified requires a passing saved-readback comparison")
    return comparison


def _pre_write_operation(operation: dict[str, Any]) -> dict[str, Any]:
    pre_change = operation.get("pre_change")
    if operation.get("action") not in DELTA_ACTIONS or not isinstance(pre_change, dict):
        raise RunValidationError("pre-write comparison requires a delta operation with pre_change")
    return {
        "action": "update",
        "object_key": operation.get("object_key"),
        "intended": pre_change,
    }


def _subset_differences(expected: Any, observed: Any, path: str = "$") -> list[dict[str, Any]]:
    """Compare a normalized pre-change snapshot while tolerating extra adapter metadata."""
    differences: list[dict[str, Any]] = []
    stack: list[tuple[Any, Any, str]] = [(expected, observed, path)]
    while stack:
        expected_value, observed_value, current_path = stack.pop()
        if isinstance(expected_value, dict):
            if not isinstance(observed_value, dict):
                differences.append(
                    {
                        "path": current_path,
                        "expected": deepcopy(expected_value),
                        "actual": deepcopy(observed_value),
                    }
                )
                continue
            for key in reversed(list(expected_value)):
                child_path = f"{current_path}.{key}"
                if key not in observed_value:
                    differences.append(
                        {
                            "path": child_path,
                            "expected": deepcopy(expected_value[key]),
                            "actual": None,
                            "reason": "missing",
                        }
                    )
                    continue
                stack.append((expected_value[key], observed_value[key], child_path))
            continue
        if isinstance(expected_value, list):
            if not isinstance(observed_value, list) or len(expected_value) != len(observed_value):
                differences.append(
                    {
                        "path": current_path,
                        "expected": deepcopy(expected_value),
                        "actual": deepcopy(observed_value),
                    }
                )
                continue
            for index in range(len(expected_value) - 1, -1, -1):
                stack.append(
                    (expected_value[index], observed_value[index], f"{current_path}[{index}]")
                )
            continue
        if type(expected_value) is not type(observed_value) or expected_value != observed_value:
            differences.append(
                {
                    "path": current_path,
                    "expected": deepcopy(expected_value),
                    "actual": deepcopy(observed_value),
                }
            )
    return differences


def build_pre_write_comparison(
    operation: dict[str, Any],
    saved: Any,
    *,
    comparator: str = "configure-gtm-pre-change-subset-v1",
) -> dict[str, Any]:
    """Bind one fresh saved read to the approved pre-change snapshot before mutation."""
    pseudo_operation = _pre_write_operation(operation)
    pre_change = pseudo_operation["intended"]
    return build_verification_comparison(
        pseudo_operation,
        saved,
        comparator=comparator,
        compared_fields=sorted(pre_change),
        differences=_subset_differences(pre_change, saved),
    )


def validate_pre_write_comparison(
    value: Any,
    *,
    operation: dict[str, Any],
    saved: Any = _UNSET,
    require_pass: bool = False,
) -> dict[str, Any]:
    """Validate pre-write drift evidence against an operation's immutable pre_change."""
    return validate_verification_comparison(
        value,
        operation=_pre_write_operation(operation),
        saved=saved,
        require_pass=require_pass,
    )


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


def _normalized_token(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _effective_target(operation: dict[str, Any], path: str) -> dict[str, Any]:
    intended = operation.get("intended")
    if isinstance(intended, dict) and intended:
        return intended
    if operation.get("action") in {"reuse", "untouched", "pause"}:
        pre_change = operation.get("pre_change")
        if isinstance(pre_change, dict) and pre_change:
            return pre_change
    raise RunValidationError(
        f"{path} requires an exact intended or pre_change target snapshot for binding"
    )


def _semantic_trigger_reference(value: Any, path: str) -> str:
    reference = _text(value, path)
    if reference in {key.removeprefix("trigger::builtin::") for key in BUILT_IN_TRIGGER_TYPES}:
        return f"trigger::builtin::{reference}"
    if reference.startswith("trigger::") and len(reference) > len("trigger::"):
        return reference
    raise RunValidationError(
        f"{path} must use a semantic trigger:: reference or a reserved built-in trigger ID"
    )


def _semantic_trigger_references(value: Any, path: str) -> list[str]:
    references = [_semantic_trigger_reference(item, f"{path}[]") for item in _array(value, path)]
    if len(set(references)) != len(references):
        raise RunValidationError(f"{path} contains duplicate trigger references")
    return references


def _normalized_trigger_type(value: Any, path: str) -> str:
    raw = _text(value, path)
    normalized = TRIGGER_TYPE_ALIASES.get(_normalized_token(raw))
    if normalized is None:
        raise RunValidationError(f"{path} has unsupported GTM trigger type {raw!r}")
    return normalized


def _decode_parameter_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    if "value" in value:
        decoded = value["value"]
        if value.get("type") == "boolean" and isinstance(decoded, str):
            if decoded.casefold() == "true":
                return True
            if decoded.casefold() == "false":
                return False
        return decoded
    return value


def _configuration_value(target: dict[str, Any], names: set[str]) -> tuple[bool, Any]:
    normalized_names = {_normalized_token(name) for name in names}
    normalized_names = {
        alias
        for name in normalized_names
        for alias in CONFIGURATION_FIELD_ALIASES.get(name, {name})
    }
    for key, value in target.items():
        if _normalized_token(key) in normalized_names:
            return True, _decode_parameter_value(value)
    for container_key in ("fields", "parameters", "configuration", "eventParameters"):
        container = target.get(container_key)
        if isinstance(container, dict):
            for key, value in container.items():
                if _normalized_token(key) in normalized_names:
                    return True, _decode_parameter_value(value)
    for container_key in ("parameter", "parameters"):
        container = target.get(container_key)
        if not isinstance(container, list):
            continue
        for item in container:
            if not isinstance(item, dict):
                continue
            key = item.get("key") or item.get("name")
            if isinstance(key, str) and _normalized_token(key) in normalized_names:
                return True, _decode_parameter_value(item)
    return False, None


def _tag_type(target: dict[str, Any], path: str) -> str:
    normalized = _normalized_token(_text(target.get("type"), f"{path}.type"))
    return TAG_TYPE_ALIASES.get(normalized, normalized)


def _tag_trigger_references(
    target: dict[str, Any],
    field: str,
    path: str,
) -> list[str]:
    raw = target.get(field, [])
    return _semantic_trigger_references(raw, f"{path}.{field}")


def _tag_additional_consent_checks(target: dict[str, Any], path: str) -> list[str]:
    direct = target.get("additional_consent_checks")
    if direct is not None:
        return _unique_texts(direct, f"{path}.additional_consent_checks")
    settings = target.get("consentSettings")
    if settings is None:
        return []
    settings = _object(settings, f"{path}.consentSettings")
    status = settings.get("consentStatus")
    if status in {None, "notSet", "notNeeded"}:
        return []
    consent_type = settings.get("consentType")
    if not isinstance(consent_type, dict):
        raise RunValidationError(f"{path}.consentSettings.consentType must be an object")
    values = consent_type.get("list", [])
    checks = []
    for index, item in enumerate(_array(values, f"{path}.consentSettings.consentType.list")):
        item = _object(item, f"{path}.consentSettings.consentType.list[{index}]")
        checks.append(_text(item.get("value"), f"{path}.consentSettings.consentType.list[].value"))
    if len(set(checks)) != len(checks):
        raise RunValidationError(f"{path}.consentSettings contains duplicate consent types")
    return checks


def _tag_firing_option(target: dict[str, Any], path: str) -> str:
    raw = target.get("tagFiringOption")
    if raw is None:
        return "once-per-event"
    normalized = {
        "onceperevent": "once-per-event",
        "onceperload": "once-per-page",
        "unlimited": "unlimited",
    }.get(_normalized_token(_text(raw, f"{path}.tagFiringOption")))
    if normalized is None:
        raise RunValidationError(f"{path}.tagFiringOption is unsupported")
    return normalized


def _send_page_view_value(target: dict[str, Any], path: str) -> bool:
    present, raw = _configuration_value(target, {"send_page_view", "sendPageView"})
    if not present:
        return True
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str) and raw.casefold() in {"true", "false"}:
        return raw.casefold() == "true"
    raise RunValidationError(f"{path}.send_page_view must resolve to a boolean")


def _validate_google_destination(target: dict[str, Any], destination: str, path: str) -> None:
    present, value = _configuration_value(
        target,
        {
            "tag_id",
            "tagId",
            "measurement_id",
            "measurementId",
            "destination_id",
            "destinationId",
        },
    )
    candidates = {value} if present and isinstance(value, str) else set()
    for collection_name in {
        "destinations",
        "destination_ids",
        "destinationIds",
    }:
        collection_present, collection = _configuration_value(target, {collection_name})
        if not collection_present:
            continue
        if not isinstance(collection, list):
            collection = [collection]
        for item in collection:
            if isinstance(item, str):
                candidates.add(item)
            elif isinstance(item, dict):
                for key in ("id", "value", "destinationId", "measurementId"):
                    candidate = item.get(key)
                    if isinstance(candidate, str):
                        candidates.add(candidate)
    if destination not in candidates:
        raise RunValidationError(f"{path} does not bind destination {destination!r}")


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

    execution_mode = _text(run.get("execution_mode"), "$.run.execution_mode")
    if execution_mode not in EXECUTION_MODES:
        raise RunValidationError(f"$.run.execution_mode has unsupported value {execution_mode!r}")

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
    _exact_keys(delta, path, required={"added", "removed", "evidence_locator"})
    _unique_texts(delta.get("added"), f"{path}.added")
    _unique_texts(delta.get("removed"), f"{path}.removed")
    _text(delta.get("evidence_locator"), f"{path}.evidence_locator")


def _validate_object_changes(
    raw: Any,
    *,
    requirement_ids: set[str],
    schema_version: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    operations: dict[str, dict[str, Any]] = {}
    object_claims: dict[str, str] = {}
    dependency_map: dict[str, list[str]] = {}
    for index, item_raw in enumerate(_array(raw, "$.object_changes")):
        path = f"$.object_changes[{index}]"
        item = _object(item_raw, path)
        _exact_keys(
            item,
            path,
            required={
                "operation_id",
                "requirement_ids",
                "action",
                "object_type",
                "name",
                "object_key",
                "dependencies",
                "state",
                "evidence",
                "journal",
            },
            optional={
                "object_id",
                "intended",
                "pre_change",
                "replacement_reason",
                "destructive_authorization",
                "permission_delta",
                "result",
                "comparison",
                "pre_write_comparison",
                "error",
            },
        )
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
        if action in {"pause", "unpause"} and object_type != "tag":
            raise RunValidationError(f"{path}.{action} is supported only for tag objects")
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
            _exact_keys(entry, journal_path, required={"state", "at", "note"})
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
        if state == "verified":
            validate_verification_comparison(
                item.get("comparison"),
                operation=item,
                require_pass=True,
            )
        pre_write_comparison = item.get("pre_write_comparison")
        if pre_write_comparison is not None:
            validate_pre_write_comparison(
                pre_write_comparison,
                operation=item,
                require_pass=False,
            )
        mutation_started = any(entry.get("state") == "in_progress" for entry in journal)
        if schema_version == SCHEMA_VERSION and action in DELTA_ACTIONS and mutation_started:
            if pre_write_comparison is None:
                raise RunValidationError(
                    f"{path}.pre_write_comparison is required before a delta mutation"
                )
            validate_pre_write_comparison(
                pre_write_comparison,
                operation=item,
                require_pass=True,
            )
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

    state: dict[str, int] = {}
    for root in operations:
        if state.get(root) == 2:
            continue
        stack: list[tuple[str, bool]] = [(root, False)]
        while stack:
            operation_id, exiting = stack.pop()
            if exiting:
                state[operation_id] = 2
                continue
            current = state.get(operation_id, 0)
            if current == 2:
                continue
            if current == 1:
                raise RunValidationError(f"operation dependency cycle includes {operation_id!r}")
            state[operation_id] = 1
            stack.append((operation_id, True))
            for dependency in reversed(dependency_map[operation_id]):
                if state.get(dependency) == 1:
                    raise RunValidationError(f"operation dependency cycle includes {dependency!r}")
                if state.get(dependency) != 2:
                    stack.append((dependency, False))
    return operations, object_claims


def _validate_payload_mappings(raw: Any, requirement_ids: set[str]) -> list[dict[str, Any]]:
    identities: set[tuple[str, str]] = set()
    records: list[dict[str, Any]] = []
    for index, item_raw in enumerate(_array(raw, "$.payload_mappings")):
        path = f"$.payload_mappings[{index}]"
        item = _object(item_raw, path)
        _exact_keys(
            item,
            path,
            required={
                "requirement_id",
                "field_scope",
                "destination_field",
                "source",
                "gtm_resolution",
                "template_field",
                "status",
                "provenance_locator",
            },
            optional=EXTENDED_MAPPING_KEYS,
        )
        requirement_id = _text(item.get("requirement_id"), f"{path}.requirement_id")
        if requirement_id not in requirement_ids:
            raise RunValidationError(f"{path}.requirement_id is unknown")
        field_scope = _text(item.get("field_scope"), f"{path}.field_scope")
        if field_scope not in {"event-parameter", "user-property", "item-parameter"}:
            raise RunValidationError(f"{path}.field_scope has unsupported value {field_scope!r}")
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
                if destination_field == "user_data" and method == "settings-variable":
                    raise RunValidationError(
                        f"{path}.user_data must not use a shared Event Settings variable"
                    )
                if destination_field == "items" and method == "settings-variable":
                    raise RunValidationError(
                        f"{path}.items must not use a shared Event Settings variable"
                    )
                if destination_field.startswith("items.0."):
                    raise RunValidationError(
                        f"{path}.destination_field must preserve the items array"
                    )
                if destination_field == "user_id" and field_scope == "user-property":
                    raise RunValidationError(
                        f"{path}.user_id must not be configured as a GA4 user property"
                    )
        elif extended_keys and status in {"intentionally-omitted", "external", "blocked"}:
            if not missing_behavior:
                raise RunValidationError(f"{path}.missing_behavior is required for {status}")
        records.append(item)
    return records


def _validate_consent_routes(
    raw: Any,
    requirement_ids: set[str],
    *,
    trigger_types: dict[str, str],
) -> None:
    seen: set[str] = set()
    for index, item_raw in enumerate(_array(raw, "$.consent_routes")):
        path = f"$.consent_routes[{index}]"
        item = _object(item_raw, path)
        _exact_keys(
            item,
            path,
            required={
                "requirement_id",
                "product",
                "mode",
                "mechanism",
                "normal_trigger",
                "blocking_triggers",
                "built_in_consent_checks",
                "additional_consent_checks",
                "unknown_behavior",
                "evidence",
            },
            optional={"blocking_event_scope", "scope_exception_reason"},
        )
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
        normal_trigger = _semantic_trigger_reference(
            item.get("normal_trigger"),
            f"{path}.normal_trigger",
        )
        blocking = _semantic_trigger_references(
            item.get("blocking_triggers"),
            f"{path}.blocking_triggers",
        )
        if normal_trigger not in trigger_types:
            raise RunValidationError(f"{path}.normal_trigger references an unresolved trigger")
        for trigger_key in blocking:
            if trigger_types.get(trigger_key) != "custom-event":
                raise RunValidationError(
                    f"{path}.blocking_triggers contains an unresolved/non-Custom Event trigger"
                )
        _unique_texts(
            item.get("built_in_consent_checks"),
            f"{path}.built_in_consent_checks",
        )
        additional = _unique_texts(
            item.get("additional_consent_checks"),
            f"{path}.additional_consent_checks",
        )
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
            if additional:
                raise RunValidationError(
                    f"{path}.additional_consent_checks must be empty when the strict/basic "
                    "vendor block owns eligibility"
                )
        if mechanism == "native-advanced" and mode != "advanced-native":
            raise RunValidationError(f"{path}.native-advanced requires advanced-native mode")
        if mode == "advanced-native":
            if mechanism != "native-advanced":
                raise RunValidationError(f"{path}.advanced-native requires native-advanced")
            if blocking or block_scope or additional:
                raise RunValidationError(
                    f"{path}.advanced-native must not carry a defeating block or Additional "
                    "Consent Check"
                )


def _validate_container_baseline(raw: Any, *, execution_mode: str) -> dict[str, Any]:
    baseline = _object(raw, "$.container_baseline")
    _exact_keys(
        baseline,
        "$.container_baseline",
        required={
            "strategy",
            "captured_at",
            "complete",
            "resource_families",
            "family_counts",
            "in_scope_tag_keys",
            "trigger_index",
            "preexisting_workspace_changes",
            "fingerprint",
        },
    )
    strategy = _text(baseline.get("strategy"), "$.container_baseline.strategy")
    if strategy not in {"relevant-families", "full-paginated"}:
        raise RunValidationError(
            f"$.container_baseline.strategy has unsupported value {strategy!r}"
        )
    complete = baseline.get("complete")
    if not isinstance(complete, bool):
        raise RunValidationError("$.container_baseline.complete must be a boolean")
    captured_at = baseline.get("captured_at")
    if captured_at is not None:
        _timestamp(captured_at, "$.container_baseline.captured_at")
    families = _unique_texts(
        baseline.get("resource_families"),
        "$.container_baseline.resource_families",
    )
    family_counts = _object(
        baseline.get("family_counts"),
        "$.container_baseline.family_counts",
    )
    if set(family_counts) != set(families):
        raise RunValidationError(
            "$.container_baseline.family_counts must cover each resource family exactly"
        )
    for family, count in family_counts.items():
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise RunValidationError(
                f"$.container_baseline.family_counts.{family} must be a non-negative integer"
            )
    in_scope_tag_keys = set(
        _unique_texts(
            baseline.get("in_scope_tag_keys"),
            "$.container_baseline.in_scope_tag_keys",
        )
    )
    change_count = baseline.get("preexisting_workspace_changes")
    if change_count is not None and (
        not isinstance(change_count, int) or isinstance(change_count, bool) or change_count < 0
    ):
        raise RunValidationError(
            "$.container_baseline.preexisting_workspace_changes must be a non-negative integer "
            "or null"
        )
    fingerprint = _optional_text(
        baseline.get("fingerprint"),
        "$.container_baseline.fingerprint",
    )
    if fingerprint is not None:
        if len(fingerprint) != 71 or not fingerprint.startswith("sha256:"):
            raise RunValidationError(
                "$.container_baseline.fingerprint must be a sha256 fingerprint"
            )
        try:
            int(fingerprint.removeprefix("sha256:"), 16)
        except ValueError as exc:
            raise RunValidationError(
                "$.container_baseline.fingerprint must be a sha256 fingerprint"
            ) from exc
    if complete and (
        captured_at is None or not families or change_count is None or fingerprint is None
    ):
        raise RunValidationError(
            "a complete container baseline requires captured_at, resource_families, "
            "preexisting_workspace_changes, and fingerprint"
        )
    if execution_mode == "refonte-durable" and strategy != "full-paginated":
        raise RunValidationError("refonte-durable requires a full-paginated container baseline")
    if (
        complete
        and strategy == "full-paginated"
        and not {
            "tag",
            "trigger",
            "variable",
        }
        <= set(families)
    ):
        raise RunValidationError(
            "a full-paginated baseline must include tag, trigger, and variable families"
        )
    if "tag" in family_counts and len(in_scope_tag_keys) > family_counts["tag"]:
        raise RunValidationError(
            "$.container_baseline.in_scope_tag_keys exceeds the captured tag family count"
        )

    trigger_types: dict[str, str] = dict(BUILT_IN_TRIGGER_TYPES)
    indexed_triggers = _array(
        baseline.get("trigger_index"),
        "$.container_baseline.trigger_index",
    )
    for index, raw_trigger in enumerate(indexed_triggers):
        path = f"$.container_baseline.trigger_index[{index}]"
        trigger = _object(raw_trigger, path)
        _exact_keys(
            trigger,
            path,
            required={"object_key", "type", "fingerprint"},
        )
        object_key = _semantic_trigger_reference(
            trigger.get("object_key"),
            f"{path}.object_key",
        )
        if object_key in trigger_types:
            raise RunValidationError(f"duplicate baseline trigger index entry {object_key!r}")
        trigger_types[object_key] = _normalized_trigger_type(
            trigger.get("type"),
            f"{path}.type",
        )
        fingerprint_value = _optional_text(trigger.get("fingerprint"), f"{path}.fingerprint")
        if fingerprint_value is not None:
            if len(fingerprint_value) != 71 or not fingerprint_value.startswith("sha256:"):
                raise RunValidationError(f"{path}.fingerprint must be a sha256 fingerprint")
            try:
                int(fingerprint_value.removeprefix("sha256:"), 16)
            except ValueError as exc:
                raise RunValidationError(
                    f"{path}.fingerprint must be a sha256 fingerprint"
                ) from exc
    if "trigger" in family_counts and len(indexed_triggers) > family_counts["trigger"]:
        raise RunValidationError(
            "$.container_baseline.trigger_index exceeds the captured trigger family count"
        )
    return {
        "in_scope_tag_keys": in_scope_tag_keys,
        "trigger_types": trigger_types,
    }


def _resolved_trigger_types(
    operations: dict[str, dict[str, Any]],
    baseline_trigger_types: dict[str, str],
) -> dict[str, str]:
    resolved = dict(baseline_trigger_types)
    for operation in operations.values():
        if (
            operation["object_type"] != "trigger"
            or operation["action"] in NON_EXECUTING_TAG_ACTIONS
        ):
            continue
        target = _effective_target(operation, f"operation {operation['operation_id']}")
        resolved[operation["object_key"]] = _normalized_trigger_type(
            target.get("type"),
            f"operation {operation['operation_id']}.intended.type",
        )
    return resolved


def _validate_normal_trigger_bindings(
    item: dict[str, Any],
    *,
    path: str,
    target: dict[str, Any],
    trigger_types: dict[str, str],
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw_trigger in enumerate(
        _array(item.get("normal_triggers"), f"{path}.normal_triggers")
    ):
        trigger_path = f"{path}.normal_triggers[{index}]"
        trigger = _object(raw_trigger, trigger_path)
        _exact_keys(
            trigger,
            trigger_path,
            required={"trigger_object_key", "role", "type"},
        )
        object_key = _semantic_trigger_reference(
            trigger.get("trigger_object_key"),
            f"{trigger_path}.trigger_object_key",
        )
        if object_key in seen:
            raise RunValidationError(f"{path}.normal_triggers contains duplicate {object_key!r}")
        seen.add(object_key)
        role = _text(trigger.get("role"), f"{trigger_path}.role")
        if role not in NORMAL_TRIGGER_ROLES:
            raise RunValidationError(f"{trigger_path}.role has unsupported value {role!r}")
        trigger_type = _text(trigger.get("type"), f"{trigger_path}.type")
        if trigger_type not in NORMAL_TRIGGER_TYPES:
            raise RunValidationError(f"{trigger_path}.type has unsupported value {trigger_type!r}")
        actual_type = trigger_types.get(object_key)
        if actual_type is None:
            raise RunValidationError(
                f"{trigger_path} references an unresolved trigger {object_key!r}"
            )
        if trigger_type != actual_type:
            raise RunValidationError(
                f"{trigger_path}.type {trigger_type!r} differs from bound trigger type {actual_type!r}"
            )
        if role == "cmp-readiness-grant" and trigger_type != "custom-event":
            raise RunValidationError(f"{trigger_path}.cmp-readiness-grant must be a Custom Event")
        if role == "initialization-page-load" and trigger_type not in PAGE_LOAD_TRIGGER_TYPES:
            raise RunValidationError(
                f"{trigger_path}.initialization-page-load uses an incompatible trigger type"
            )
        records.append({"trigger_object_key": object_key, "role": role, "type": trigger_type})
    if not records:
        raise RunValidationError(f"{path}.normal_triggers must not be empty")
    intended_refs = set(_tag_trigger_references(target, "firingTriggerId", f"{path}.bound_tag"))
    declared_refs = {item["trigger_object_key"] for item in records}
    if intended_refs != declared_refs:
        raise RunValidationError(
            f"{path}.normal_triggers must equal bound firingTriggerId; "
            f"missing={sorted(intended_refs - declared_refs)}, "
            f"extra={sorted(declared_refs - intended_refs)}"
        )
    return records


def _validate_execution_topologies(
    raw: Any,
    *,
    requirement_ids: set[str],
    operations: dict[str, dict[str, Any]],
    baseline_trigger_types: dict[str, str],
    transporter_tag_keys: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    transporter_tag_keys = set(transporter_tag_keys or set())
    operation_by_key = {item["object_key"]: item for item in operations.values()}
    trigger_types = _resolved_trigger_types(operations, baseline_trigger_types)
    records: dict[str, dict[str, Any]] = {}
    for index, item_raw in enumerate(_array(raw, "$.execution_topologies")):
        path = f"$.execution_topologies[{index}]"
        item = _object(item_raw, path)
        _exact_keys(
            item,
            path,
            required={
                "tag_object_key",
                "requirement_ids",
                "lifecycle_role",
                "normal_triggers",
                "consent_mode",
                "blocking_trigger_keys",
                "blocking_event_scope",
                "built_in_consent_checks",
                "additional_consent_checks",
                "firing_option",
                "may_precede_cmp",
                "pre_cmp_policy",
                "page_view_capable",
                "page_view_destinations",
                "ecommerce_route",
                "manual_ecommerce_fields",
                "evidence",
            },
        )
        tag_key = _text(item.get("tag_object_key"), f"{path}.tag_object_key")
        if tag_key in records:
            raise RunValidationError(f"duplicate execution topology for {tag_key!r}")
        operation = operation_by_key.get(tag_key)
        if operation is None or operation["object_type"] != "tag":
            raise RunValidationError(f"{path}.tag_object_key must reference an in-scope tag")
        if operation["action"] in NON_EXECUTING_TAG_ACTIONS:
            raise RunValidationError(
                f"{path} must not assign target execution topology to {operation['action']!r}"
            )
        target = _effective_target(operation, path)
        linked = set(
            _unique_texts(
                item.get("requirement_ids"),
                f"{path}.requirement_ids",
                allow_empty=False,
            )
        )
        if linked - requirement_ids:
            raise RunValidationError(f"{path}.requirement_ids contains unknown IDs")
        if linked != set(operation["requirement_ids"]):
            raise RunValidationError(
                f"{path}.requirement_ids must equal the tag operation requirement_ids"
            )
        role = _text(item.get("lifecycle_role"), f"{path}.lifecycle_role")
        if role not in LIFECYCLE_ROLES:
            raise RunValidationError(f"{path}.lifecycle_role has unsupported value {role!r}")
        mode = _text(item.get("consent_mode"), f"{path}.consent_mode")
        if mode not in CONSENT_MODES:
            raise RunValidationError(f"{path}.consent_mode has unsupported value {mode!r}")
        is_transporter = tag_key in transporter_tag_keys
        normal_triggers = _validate_normal_trigger_bindings(
            item,
            path=path,
            target=target,
            trigger_types=trigger_types,
        )
        trigger_roles = {trigger["role"] for trigger in normal_triggers}
        if role == "event-driven":
            if trigger_roles != {"source-event"}:
                raise RunValidationError(
                    f"{path}.event-driven tags require only source-event triggers"
                )
            if any(trigger["type"] in PAGE_LOAD_TRIGGER_TYPES for trigger in normal_triggers):
                raise RunValidationError(
                    f"{path}.page-load trigger types require baseline-page-load lifecycle"
                )
        expected_baseline_role = (
            "cmp-readiness-grant" if mode == "strict-basic" else "initialization-page-load"
        )
        if role == "baseline-page-load" and expected_baseline_role not in trigger_roles:
            raise RunValidationError(
                f"{path}.baseline-page-load under {mode} requires a {expected_baseline_role} trigger"
            )

        blocking = _semantic_trigger_references(
            item.get("blocking_trigger_keys"),
            f"{path}.blocking_trigger_keys",
        )
        intended_blocks = set(
            _tag_trigger_references(target, "blockingTriggerId", f"{path}.bound_tag")
        )
        if set(blocking) != intended_blocks:
            raise RunValidationError(
                f"{path}.blocking_trigger_keys must equal bound blockingTriggerId"
            )
        for trigger_key in blocking:
            if trigger_types.get(trigger_key) != "custom-event":
                raise RunValidationError(
                    f"{path}.blocking_trigger_keys contains unresolved/non-Custom Event "
                    f"{trigger_key!r}"
                )
        block_scope = _optional_text(
            item.get("blocking_event_scope"),
            f"{path}.blocking_event_scope",
        )
        _unique_texts(
            item.get("built_in_consent_checks"),
            f"{path}.built_in_consent_checks",
        )
        additional = _unique_texts(
            item.get("additional_consent_checks"),
            f"{path}.additional_consent_checks",
        )
        if set(additional) != set(_tag_additional_consent_checks(target, f"{path}.bound_tag")):
            raise RunValidationError(
                f"{path}.additional_consent_checks differs from bound tag consentSettings"
            )
        if mode == "strict-basic":
            if is_transporter and (blocking or block_scope):
                raise RunValidationError(
                    f"{path} transporter tags must not inherit destination vendor blocks"
                )
            if not is_transporter and (not blocking or not block_scope):
                raise RunValidationError(
                    f"{path}.strict-basic requires blocking_trigger_keys and blocking_event_scope"
                )
            if additional:
                raise RunValidationError(
                    f"{path}.additional_consent_checks must be empty under strict-basic"
                )
        elif blocking or block_scope or additional:
            raise RunValidationError(
                f"{path}.advanced-native must not carry a defeating block or Additional check"
            )
        firing_option = _text(item.get("firing_option"), f"{path}.firing_option")
        if firing_option not in FIRING_OPTIONS:
            raise RunValidationError(
                f"{path}.firing_option has unsupported value {firing_option!r}"
            )
        if firing_option != _tag_firing_option(target, f"{path}.bound_tag"):
            raise RunValidationError(f"{path}.firing_option differs from the bound tag")
        may_precede_cmp = item.get("may_precede_cmp")
        if not isinstance(may_precede_cmp, bool):
            raise RunValidationError(f"{path}.may_precede_cmp must be a boolean")
        pre_cmp_policy = _text(item.get("pre_cmp_policy"), f"{path}.pre_cmp_policy")
        if pre_cmp_policy not in PRE_CMP_POLICIES:
            raise RunValidationError(
                f"{path}.pre_cmp_policy has unsupported value {pre_cmp_policy!r}"
            )
        if may_precede_cmp and role != "event-driven":
            raise RunValidationError(f"{path}.may_precede_cmp applies only to event-driven tags")
        if may_precede_cmp and pre_cmp_policy == "not-applicable":
            raise RunValidationError(
                f"{path}.pre_cmp_policy must resolve an event that may precede CMP"
            )
        if not may_precede_cmp and pre_cmp_policy != "not-applicable":
            raise RunValidationError(
                f"{path}.pre_cmp_policy must be not-applicable when may_precede_cmp is false"
            )
        if not isinstance(item.get("page_view_capable"), bool):
            raise RunValidationError(f"{path}.page_view_capable must be a boolean")
        page_view_destinations = _unique_texts(
            item.get("page_view_destinations"),
            f"{path}.page_view_destinations",
        )
        if item["page_view_capable"] != bool(page_view_destinations):
            raise RunValidationError(
                f"{path}.page_view_destinations must be populated exactly when page_view_capable"
            )
        ecommerce_route = _text(item.get("ecommerce_route"), f"{path}.ecommerce_route")
        if ecommerce_route not in ECOMMERCE_ROUTES:
            raise RunValidationError(
                f"{path}.ecommerce_route has unsupported value {ecommerce_route!r}"
            )
        manual_fields = _unique_texts(
            item.get("manual_ecommerce_fields"),
            f"{path}.manual_ecommerce_fields",
        )
        if ecommerce_route != "manual" and manual_fields:
            raise RunValidationError(
                f"{path}.manual_ecommerce_fields must be empty for a native/non-ecommerce route"
            )
        if any(field.startswith("items.0.") for field in manual_fields):
            raise RunValidationError(f"{path} must not flatten items into items.0.* fields")
        _unique_texts(item.get("evidence"), f"{path}.evidence", allow_empty=False)
        records[tag_key] = item
    return records


def _validate_page_view_decisions(
    raw: Any,
    *,
    requirement_ids: set[str],
    operations: dict[str, dict[str, Any]],
    external_dependencies: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    operation_by_key = {item["object_key"]: item for item in operations.values()}

    def bound_tag(object_key: str, field_path: str) -> tuple[dict[str, Any], dict[str, Any]]:
        operation = operation_by_key.get(object_key)
        if operation is None or operation["object_type"] != "tag":
            raise RunValidationError(f"{field_path} must reference an in-scope tag")
        if operation["action"] in NON_EXECUTING_TAG_ACTIONS:
            raise RunValidationError(f"{field_path} must reference an executing target tag")
        return operation, _effective_target(operation, field_path)

    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for index, item_raw in enumerate(_array(raw, "$.page_view_decisions")):
        path = f"$.page_view_decisions[{index}]"
        item = _object(item_raw, path)
        _exact_keys(
            item,
            path,
            required={
                "destination",
                "requirement_ids",
                "owner",
                "owner_object_key",
                "google_tag_object_key",
                "send_page_view",
                "external_dependency_ids",
                "reason",
                "evidence",
            },
        )
        destination = _text(item.get("destination"), f"{path}.destination")
        if destination in seen:
            raise RunValidationError(f"duplicate page-view decision for {destination!r}")
        seen.add(destination)
        linked = set(
            _unique_texts(
                item.get("requirement_ids"),
                f"{path}.requirement_ids",
                allow_empty=False,
            )
        )
        if linked - requirement_ids:
            raise RunValidationError(f"{path}.requirement_ids contains unknown IDs")
        owner = _text(item.get("owner"), f"{path}.owner")
        if owner not in PAGE_VIEW_OWNERS:
            raise RunValidationError(f"{path}.owner has unsupported value {owner!r}")
        owner_key = _optional_text(item.get("owner_object_key"), f"{path}.owner_object_key")
        google_tag_key = _optional_text(
            item.get("google_tag_object_key"),
            f"{path}.google_tag_object_key",
        )
        dependency_ids = set(
            _unique_texts(
                item.get("external_dependency_ids"),
                f"{path}.external_dependency_ids",
            )
        )
        if dependency_ids - set(external_dependencies):
            raise RunValidationError(f"{path}.external_dependency_ids contains unknown IDs")
        if any(
            not linked <= set(external_dependencies[dependency_id]["requirement_ids"])
            for dependency_id in dependency_ids
        ):
            raise RunValidationError(
                f"{path}.external_dependency_ids contains a dependency outside the requirements"
            )
        send_page_view = item.get("send_page_view")
        if not isinstance(send_page_view, bool):
            raise RunValidationError(f"{path}.send_page_view must be a boolean")
        if owner == "google-tag-automatic":
            if not owner_key or owner_key != google_tag_key or not send_page_view:
                raise RunValidationError(
                    f"{path}.google-tag-automatic requires the same owner and Google tag key "
                    "with send_page_view true"
                )
            owner_operation, owner_target = bound_tag(owner_key, f"{path}.owner_object_key")
            if _tag_type(owner_target, f"{path}.owner") not in GOOGLE_CONFIGURATION_TAG_TYPES:
                raise RunValidationError(f"{path}.google-tag-automatic owner is not a Google tag")
            if not _send_page_view_value(owner_target, f"{path}.owner"):
                raise RunValidationError(f"{path}.send_page_view differs from the bound Google tag")
            _validate_google_destination(owner_target, destination, f"{path}.owner")
            if not linked <= set(owner_operation["requirement_ids"]):
                raise RunValidationError(f"{path}.owner does not cover its requirement_ids")
        elif owner == "dedicated-ga4-event":
            if not owner_key or not google_tag_key or send_page_view:
                raise RunValidationError(
                    f"{path}.dedicated-ga4-event requires owner and Google tag keys with "
                    "send_page_view false"
                )
            owner_operation, owner_target = bound_tag(owner_key, f"{path}.owner_object_key")
            if _tag_type(owner_target, f"{path}.owner") not in GA4_EVENT_TAG_TYPES:
                raise RunValidationError(f"{path}.dedicated-ga4-event owner is not a GA4 Event tag")
            _, event_name = _configuration_value(owner_target, {"event_name", "eventName"})
            if event_name != "page_view":
                raise RunValidationError(
                    f"{path}.dedicated-ga4-event owner must send the page_view event"
                )
            if not linked <= set(owner_operation["requirement_ids"]):
                raise RunValidationError(f"{path}.owner does not cover its requirement_ids")
            google_operation, google_target = bound_tag(
                google_tag_key,
                f"{path}.google_tag_object_key",
            )
            if _tag_type(google_target, f"{path}.google_tag") not in GOOGLE_CONFIGURATION_TAG_TYPES:
                raise RunValidationError(f"{path}.google_tag_object_key is not a Google tag")
            if _send_page_view_value(google_target, f"{path}.google_tag"):
                raise RunValidationError(
                    f"{path}.dedicated-ga4-event requires bound Google tag send_page_view false"
                )
            _validate_google_destination(google_target, destination, f"{path}.google_tag")
            if not linked <= set(google_operation["requirement_ids"]):
                raise RunValidationError(f"{path}.Google tag does not cover its requirement_ids")
        else:
            if owner_key is not None or send_page_view:
                raise RunValidationError(
                    f"{path}.{owner} requires a null owner_object_key and send_page_view false"
                )
            if owner == "external" and not dependency_ids:
                raise RunValidationError(f"{path}.external requires an external dependency")
            if owner == "intentionally-none" and dependency_ids:
                raise RunValidationError(
                    f"{path}.intentionally-none must not claim an external owner"
                )
            if google_tag_key is not None:
                google_operation, google_target = bound_tag(
                    google_tag_key,
                    f"{path}.google_tag_object_key",
                )
                if (
                    _tag_type(
                        google_target,
                        f"{path}.google_tag",
                    )
                    not in GOOGLE_CONFIGURATION_TAG_TYPES
                ):
                    raise RunValidationError(f"{path}.google_tag_object_key is not a Google tag")
                if _send_page_view_value(google_target, f"{path}.google_tag"):
                    raise RunValidationError(
                        f"{path}.{owner} requires bound Google tag send_page_view false"
                    )
                _validate_google_destination(google_target, destination, f"{path}.google_tag")
                if not linked <= set(google_operation["requirement_ids"]):
                    raise RunValidationError(
                        f"{path}.Google tag does not cover its requirement_ids"
                    )
        _text(item.get("reason"), f"{path}.reason")
        _unique_texts(item.get("evidence"), f"{path}.evidence", allow_empty=False)
        records.append(item)
    return records


def _validate_first_party_feature_contract(
    *,
    path: str,
    feature: str,
    destination_field: str,
    timing: str,
    hashing_owner: str,
    field_names: set[str],
    consumer_targets: list[dict[str, Any]],
    dependency_ids: set[str],
    consent_types: set[str],
) -> None:
    product_types = {_tag_type(target, f"{path}.consumer") for target in consumer_targets}
    if feature == "ga4-user-id":
        if (
            hashing_owner != "not-applicable"
            or timing != "tag-wide"
            or destination_field != "user_id"
        ):
            raise RunValidationError(
                f"{path}.ga4-user-id requires destination user_id, tag-wide timing, and no hashing"
            )
        if field_names != {"user_id"}:
            raise RunValidationError(f"{path}.ga4-user-id requires only the user_id field")
        if not product_types <= GOOGLE_CONFIGURATION_TAG_TYPES:
            raise RunValidationError(f"{path}.ga4-user-id requires a Google configuration tag")
        return

    if hashing_owner == "not-applicable":
        raise RunValidationError(f"{path}.{feature} requires an explicit hashing owner")
    if feature == "ga4-user-provided-data":
        if destination_field != "user_data" or timing != "same-event":
            raise RunValidationError(f"{path}.ga4-user-provided-data requires same-event user_data")
        if not product_types <= GA4_EVENT_TAG_TYPES:
            raise RunValidationError(f"{path}.ga4-user-provided-data requires GA4 Event tags")
    elif feature == "google-ads-enhanced-conversions":
        if destination_field != "user_data" or timing != "same-event":
            raise RunValidationError(
                f"{path}.google-ads-enhanced-conversions requires same-event user_data"
            )
        if not product_types <= GOOGLE_ADS_CONVERSION_TAG_TYPES:
            raise RunValidationError(
                f"{path}.google-ads-enhanced-conversions requires the native Google Ads "
                "conversion tag"
            )
    elif feature == "google-ads-tag-wide-user-data":
        if destination_field != "user_data" or timing != "tag-wide":
            raise RunValidationError(
                f"{path}.google-ads-tag-wide-user-data requires tag-wide user_data"
            )
        if not product_types <= {"googtag"}:
            raise RunValidationError(
                f"{path}.google-ads-tag-wide-user-data requires a current Google tag"
            )
    elif feature == "google-ads-user-provided-data-event":
        if destination_field != "user_data" or timing != "prior-page":
            raise RunValidationError(
                f"{path}.google-ads-user-provided-data-event requires prior-page user_data"
            )

    if feature.startswith("google-ads-") and feature != "google-ads-tag-wide-user-data":
        if product_types & (GOOGLE_CONFIGURATION_TAG_TYPES | GA4_EVENT_TAG_TYPES):
            raise RunValidationError(
                f"{path}.{feature} must not bind a GA4 or generic Google configuration tag"
            )
    externally_administered = {
        "ga4-user-provided-data",
        "google-ads-enhanced-conversions",
        "google-ads-tag-wide-user-data",
        "google-ads-user-provided-data-event",
    }
    if feature in externally_administered and not dependency_ids:
        raise RunValidationError(f"{path}.{feature} requires an external administration dependency")
    if feature in externally_administered and "ad_user_data" not in consent_types:
        raise RunValidationError(f"{path}.{feature} requires ad_user_data consent")


def _validate_first_party_consumer_bindings(
    raw: Any,
    *,
    path: str,
    feature: str,
    consumers: set[str],
    consumer_targets: dict[str, dict[str, Any]],
) -> None:
    records: set[str] = set()
    for index, binding_raw in enumerate(_array(raw, f"{path}.consumer_bindings")):
        binding_path = f"{path}.consumer_bindings[{index}]"
        binding = _object(binding_raw, binding_path)
        _exact_keys(
            binding,
            binding_path,
            required={
                "object_key",
                "product",
                "implementation",
                "tag_type",
                "template_identity",
                "evidence",
            },
        )
        object_key = _text(binding.get("object_key"), f"{binding_path}.object_key")
        if object_key not in consumers or object_key in records:
            raise RunValidationError(
                f"{binding_path}.object_key is unknown or duplicated for this route"
            )
        records.add(object_key)
        product = _normalized_token(_text(binding.get("product"), f"{binding_path}.product"))
        expected_product = FIRST_PARTY_PRODUCTS.get(feature)
        if expected_product is not None and product != _normalized_token(expected_product):
            raise RunValidationError(
                f"{binding_path}.product must identify {expected_product!r} for {feature}"
            )
        implementation = _text(binding.get("implementation"), f"{binding_path}.implementation")
        if implementation not in {"native", "installed-template"}:
            raise RunValidationError(f"{binding_path}.implementation is unsupported")
        actual_type = _tag_type(consumer_targets[object_key], f"{binding_path}.consumer")
        declared_type = _normalized_token(
            _text(binding.get("tag_type"), f"{binding_path}.tag_type")
        )
        if declared_type != actual_type:
            raise RunValidationError(
                f"{binding_path}.tag_type differs from the bound saved tag type"
            )
        if actual_type in CUSTOM_CODE_TAG_TYPES:
            raise RunValidationError(
                f"{binding_path} cannot identify Custom HTML/Image as a product-native consumer"
            )
        template_identity = _optional_text(
            binding.get("template_identity"), f"{binding_path}.template_identity"
        )
        if implementation == "native" and template_identity is not None:
            raise RunValidationError(f"{binding_path}.native requires a null template_identity")
        if implementation == "installed-template":
            if template_identity is None:
                raise RunValidationError(
                    f"{binding_path}.installed-template requires template_identity"
                )
            if _normalized_token(template_identity) != actual_type:
                raise RunValidationError(
                    f"{binding_path}.template_identity differs from the bound saved tag type"
                )
        _unique_texts(
            binding.get("evidence"),
            f"{binding_path}.evidence",
            allow_empty=False,
        )
    if records != consumers:
        missing = sorted(consumers - records)
        raise RunValidationError(
            f"{path}.consumer_bindings must identify every consumer exactly; missing={missing}"
        )


def _validate_first_party_data_routes(
    raw: Any,
    *,
    requirement_ids: set[str],
    operations: dict[str, dict[str, Any]],
    external_dependencies: dict[str, dict[str, Any]],
    payload_mappings: list[dict[str, Any]],
    schema_version: str,
) -> list[dict[str, Any]]:
    operation_by_key = {item["object_key"]: item for item in operations.values()}
    mapped_fields = {
        (item["requirement_id"], item["destination_field"])
        for item in payload_mappings
        if item["status"] == "mapped"
    }
    identities: set[tuple[str, str]] = set()
    records: list[dict[str, Any]] = []
    for index, item_raw in enumerate(_array(raw, "$.first_party_data_routes")):
        path = f"$.first_party_data_routes[{index}]"
        item = _object(item_raw, path)
        required_keys = {
            "requirement_id",
            "feature",
            "destination_field",
            "consumer_object_keys",
            "source_priority",
            "timing",
            "hashing_owner",
            "fields",
            "consent_types",
            "external_dependency_ids",
            "evidence",
        }
        optional_keys: set[str] = set()
        if schema_version == SCHEMA_VERSION:
            required_keys.add("consumer_bindings")
        else:
            optional_keys.add("consumer_bindings")
        _exact_keys(
            item,
            path,
            required=required_keys,
            optional=optional_keys,
        )
        requirement_id = _text(item.get("requirement_id"), f"{path}.requirement_id")
        if requirement_id not in requirement_ids:
            raise RunValidationError(f"{path}.requirement_id is unknown")
        feature = _text(item.get("feature"), f"{path}.feature")
        if feature not in FIRST_PARTY_FEATURES:
            raise RunValidationError(f"{path}.feature has unsupported value {feature!r}")
        destination_field = _text(
            item.get("destination_field"),
            f"{path}.destination_field",
        )
        if (requirement_id, destination_field) not in mapped_fields:
            raise RunValidationError(
                f"{path} must bind to a mapped payload field {requirement_id}::{destination_field}"
            )
        identity = (requirement_id, feature)
        if identity in identities:
            raise RunValidationError(f"duplicate first-party-data route {identity!r}")
        identities.add(identity)
        consumers = set(
            _unique_texts(
                item.get("consumer_object_keys"),
                f"{path}.consumer_object_keys",
                allow_empty=False,
            )
        )
        consumer_targets: dict[str, dict[str, Any]] = {}
        for object_key in consumers:
            operation = operation_by_key.get(object_key)
            if operation is None or operation["object_type"] != "tag":
                raise RunValidationError(
                    f"{path}.consumer_object_keys contains a non-tag or unknown object"
                )
            if operation["action"] in NON_EXECUTING_TAG_ACTIONS:
                raise RunValidationError(
                    f"{path}.consumer_object_keys contains a non-executing tag"
                )
            if requirement_id not in operation["requirement_ids"]:
                raise RunValidationError(
                    f"{path}.consumer_object_keys contains a tag outside the requirement"
                )
            target = _effective_target(operation, f"{path}.consumer_object_keys")
            present, _ = _configuration_value(target, {destination_field})
            if not present:
                raise RunValidationError(
                    f"{path}.consumer {object_key!r} does not configure {destination_field!r}"
                )
            consumer_targets[object_key] = target
        if "consumer_bindings" in item:
            _validate_first_party_consumer_bindings(
                item["consumer_bindings"],
                path=path,
                feature=feature,
                consumers=consumers,
                consumer_targets=consumer_targets,
            )
        source_priority = _text(item.get("source_priority"), f"{path}.source_priority")
        if source_priority not in {"data-layer", "controlled-javascript", "dom", "automatic"}:
            raise RunValidationError(f"{path}.source_priority is unsupported")
        timing = _text(item.get("timing"), f"{path}.timing")
        if timing not in {"tag-wide", "same-event", "prior-page"}:
            raise RunValidationError(f"{path}.timing is unsupported")
        hashing_owner = _text(item.get("hashing_owner"), f"{path}.hashing_owner")
        if hashing_owner not in {"not-applicable", "native-raw", "prehashed-sha256"}:
            raise RunValidationError(f"{path}.hashing_owner is unsupported")
        fields = _array(item.get("fields"), f"{path}.fields")
        if not fields:
            raise RunValidationError(f"{path}.fields must not be empty")
        field_names: set[str] = set()
        for field_index, field_raw in enumerate(fields):
            field_path = f"{path}.fields[{field_index}]"
            field = _object(field_raw, field_path)
            _exact_keys(
                field,
                field_path,
                required={"name", "source", "normalization", "empty_behavior"},
            )
            name = _text(field.get("name"), f"{field_path}.name")
            if name in field_names:
                raise RunValidationError(f"{path}.fields contains duplicate field {name!r}")
            field_names.add(name)
            _text(field.get("source"), f"{field_path}.source")
            _unique_texts(field.get("normalization"), f"{field_path}.normalization")
            if field.get("empty_behavior") != "omit":
                raise RunValidationError(f"{field_path}.empty_behavior must be 'omit'")
        consent_types = set(_unique_texts(item.get("consent_types"), f"{path}.consent_types"))
        dependency_ids = set(
            _unique_texts(
                item.get("external_dependency_ids"),
                f"{path}.external_dependency_ids",
            )
        )
        if dependency_ids - set(external_dependencies):
            raise RunValidationError(f"{path}.external_dependency_ids contains unknown IDs")
        if any(
            requirement_id not in external_dependencies[dependency_id]["requirement_ids"]
            for dependency_id in dependency_ids
        ):
            raise RunValidationError(
                f"{path}.external_dependency_ids contains a dependency outside the requirement"
            )
        _unique_texts(item.get("evidence"), f"{path}.evidence", allow_empty=False)
        _validate_first_party_feature_contract(
            path=path,
            feature=feature,
            destination_field=destination_field,
            timing=timing,
            hashing_owner=hashing_owner,
            field_names=field_names,
            consumer_targets=list(consumer_targets.values()),
            dependency_ids=dependency_ids,
            consent_types=consent_types,
        )
        records.append(item)
    return records


def _validate_inventory_dispositions(
    raw: Any,
    *,
    execution_mode: str,
    in_scope_tag_keys: set[str],
    operations: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    allowed_tag_actions = {
        "added": {"create"},
        "keep": {"reuse", "untouched"},
        "update": {"update", "rename", "unpause"},
        "remap": {"update", "rename"},
        "pause": {"pause"},
        "remove": {"remove"},
        "replace": {"replace"},
        "supersede": {"pause", "reuse", "untouched"},
    }
    operation_ids = set(operations)
    row_ids: set[str] = set()
    orders: set[int] = set()
    before_keys: set[str] = set()
    after_names: set[str] = set()
    linked_tag_operation_ids: set[str] = set()
    records: list[dict[str, Any]] = []
    for index, item_raw in enumerate(_array(raw, "$.inventory_dispositions")):
        path = f"$.inventory_dispositions[{index}]"
        item = _object(item_raw, path)
        _exact_keys(
            item,
            path,
            required={
                "row_id",
                "source_order",
                "source_locator",
                "before_object_key",
                "before_tag_name",
                "disposition",
                "after_tag_name",
                "trigger_before",
                "trigger_after",
                "variable_changes",
                "parameter_changes",
                "consent_changes",
                "rationale",
                "operation_ids",
            },
        )
        row_id = _text(item.get("row_id"), f"{path}.row_id")
        if row_id in row_ids:
            raise RunValidationError(f"duplicate inventory row_id {row_id!r}")
        row_ids.add(row_id)
        order = item.get("source_order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 0:
            raise RunValidationError(f"{path}.source_order must be a non-negative integer")
        if order in orders:
            raise RunValidationError(f"duplicate inventory source_order {order}")
        orders.add(order)
        _text(item.get("source_locator"), f"{path}.source_locator")
        before_key = _optional_text(item.get("before_object_key"), f"{path}.before_object_key")
        before_name = _optional_text(item.get("before_tag_name"), f"{path}.before_tag_name")
        disposition = _text(item.get("disposition"), f"{path}.disposition")
        if disposition not in INVENTORY_DISPOSITIONS:
            raise RunValidationError(f"{path}.disposition has unsupported value {disposition!r}")
        after_name = _optional_text(item.get("after_tag_name"), f"{path}.after_tag_name")
        if disposition == "added":
            if before_key is not None or before_name is not None or after_name is None:
                raise RunValidationError(
                    f"{path}.added requires blank before identity and a non-empty after_tag_name"
                )
        else:
            if before_key is None or before_name is None:
                raise RunValidationError(
                    f"{path}.{disposition} requires before_object_key and before_tag_name"
                )
            if before_key in before_keys:
                raise RunValidationError(f"duplicate inventory before_object_key {before_key!r}")
            before_keys.add(before_key)
        if disposition == "remove" and after_name is not None:
            raise RunValidationError(f"{path}.remove requires a null after_tag_name")
        if disposition not in {"remove", "added"} and after_name is None:
            raise RunValidationError(f"{path}.{disposition} requires after_tag_name")
        if after_name is not None:
            if after_name in after_names:
                raise RunValidationError(f"duplicate inventory after_tag_name {after_name!r}")
            after_names.add(after_name)
        for field in (
            "trigger_before",
            "trigger_after",
            "variable_changes",
            "parameter_changes",
            "consent_changes",
        ):
            _unique_texts(item.get(field), f"{path}.{field}")
        _text(item.get("rationale"), f"{path}.rationale")
        linked_operations = set(_unique_texts(item.get("operation_ids"), f"{path}.operation_ids"))
        if linked_operations - operation_ids:
            raise RunValidationError(f"{path}.operation_ids contains unknown IDs")
        tag_operations = [
            operations[operation_id]
            for operation_id in linked_operations
            if operations[operation_id]["object_type"] == "tag"
        ]
        if len(tag_operations) != 1:
            raise RunValidationError(f"{path}.operation_ids must link exactly one tag operation")
        tag_operation = tag_operations[0]
        operation_id = tag_operation["operation_id"]
        if operation_id in linked_tag_operation_ids:
            raise RunValidationError(
                f"tag operation {operation_id!r} is linked by multiple inventory rows"
            )
        linked_tag_operation_ids.add(operation_id)
        if tag_operation["action"] not in allowed_tag_actions[disposition]:
            raise RunValidationError(
                f"{path}.{disposition} is incompatible with tag action {tag_operation['action']!r}"
            )
        target = _effective_target(tag_operation, path) if disposition != "remove" else None
        target_name = target.get("name") if isinstance(target, dict) else None
        if disposition == "added":
            if after_name != target_name:
                raise RunValidationError(f"{path}.after_tag_name differs from the created tag")
        else:
            if before_key != tag_operation["object_key"]:
                raise RunValidationError(f"{path}.before_object_key differs from its tag operation")
            pre_change = _object(
                tag_operation.get("pre_change"), f"{path}.tag_operation.pre_change"
            )
            if before_name != pre_change.get("name"):
                raise RunValidationError(f"{path}.before_tag_name differs from pre_change.name")
            if disposition != "remove" and after_name != target_name:
                raise RunValidationError(f"{path}.after_tag_name differs from the target tag")
        records.append(item)
    if execution_mode == "refonte-durable" and before_keys != in_scope_tag_keys:
        missing = sorted(in_scope_tag_keys - before_keys)
        extra = sorted(before_keys - in_scope_tag_keys)
        raise RunValidationError(
            "refonte inventory dispositions must cover every in-scope baseline tag exactly; "
            f"missing={missing}, extra={extra}"
        )
    if execution_mode == "refonte-durable":
        tag_operation_ids = {
            operation_id
            for operation_id, operation in operations.items()
            if operation["object_type"] == "tag"
        }
        if tag_operation_ids != linked_tag_operation_ids:
            missing = sorted(tag_operation_ids - linked_tag_operation_ids)
            extra = sorted(linked_tag_operation_ids - tag_operation_ids)
            raise RunValidationError(
                "refonte inventory rows must cover every tag operation exactly; "
                f"missing={missing}, extra={extra}"
            )
        existing_orders = [
            item["source_order"] for item in records if item["disposition"] != "added"
        ]
        added_orders = [item["source_order"] for item in records if item["disposition"] == "added"]
        if existing_orders and added_orders and min(added_orders) <= max(existing_orders):
            raise RunValidationError("refonte added inventory rows must follow all source rows")
    return records


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
        comparison = validate_verification_comparison(
            item.get("comparison"),
            operation=operations[operation_id],
            require_pass=True,
        )
        if comparison != operations[operation_id].get("comparison"):
            raise RunValidationError(f"{path}.comparison does not match its verified operation")
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


def _validate_external_dependencies(
    raw: Any,
    requirement_ids: set[str],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for index, item_raw in enumerate(_array(raw, "$.external_dependencies")):
        path = f"$.external_dependencies[{index}]"
        item = _object(item_raw, path)
        _exact_keys(
            item,
            path,
            required={"id", "requirement_ids", "owner", "action", "status"},
        )
        dependency_id = _text(item.get("id"), f"{path}.id")
        if dependency_id in records:
            raise RunValidationError(f"duplicate external dependency id {dependency_id!r}")
        linked = set(_unique_texts(item.get("requirement_ids"), f"{path}.requirement_ids"))
        if linked - requirement_ids:
            raise RunValidationError(f"{path}.requirement_ids contains unknown IDs")
        _text(item.get("owner"), f"{path}.owner")
        _text(item.get("action"), f"{path}.action")
        if _text(item.get("status"), f"{path}.status") not in {"open", "resolved", "deferred"}:
            raise RunValidationError(f"{path}.status is unsupported")
        records[dependency_id] = item
    return records


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
    if _text(handoff.get("manifest_version"), "$.recette_handoff.manifest_version") != "2.0":
        raise RunValidationError("$.recette_handoff.manifest_version must be '2.0'")
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
        _unique_texts(
            item.get("expected_normal_triggers"),
            f"{path}.expected_normal_triggers",
        )
        _unique_texts(
            item.get("expected_blocking_triggers"),
            f"{path}.expected_blocking_triggers",
        )
        _unique_texts(item.get("expected_consent_states"), f"{path}.expected_consent_states")
        _unique_texts(
            item.get("expected_user_data_keys"),
            f"{path}.expected_user_data_keys",
        )
        _unique_texts(item.get("network_cues"), f"{path}.network_cues")
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
    schema_version = document.get("schema_version")
    if schema_version != SCHEMA_VERSION and schema_version not in LEGACY_SCHEMA_VERSIONS:
        raise RunValidationError(
            f"$.schema_version must be {SCHEMA_VERSION!r} or a supported legacy version"
        )

    run, requirement_ids, status = _validate_run_header(document["run"])
    requirements = _validate_requirements(document["requirements"], requirement_ids)
    operations, _ = _validate_object_changes(
        document["object_changes"],
        requirement_ids=requirement_ids,
        schema_version=schema_version,
    )
    payload_mappings = _validate_payload_mappings(
        document["payload_mappings"],
        requirement_ids,
    )
    baseline = _validate_container_baseline(
        document["container_baseline"],
        execution_mode=run["execution_mode"],
    )
    trigger_types = _resolved_trigger_types(operations, baseline["trigger_types"])
    _validate_consent_routes(
        document["consent_routes"],
        requirement_ids,
        trigger_types=trigger_types,
    )
    _validate_execution_topologies(
        document["execution_topologies"],
        requirement_ids=requirement_ids,
        operations=operations,
        baseline_trigger_types=baseline["trigger_types"],
    )
    external_dependencies = _validate_external_dependencies(
        document["external_dependencies"], requirement_ids
    )
    _validate_page_view_decisions(
        document["page_view_decisions"],
        requirement_ids=requirement_ids,
        operations=operations,
        external_dependencies=external_dependencies,
    )
    readback = _validate_readback(document["saved_readback"], operations=operations)
    _validate_official_sources(document["official_sources"])
    _validate_first_party_data_routes(
        document["first_party_data_routes"],
        requirement_ids=requirement_ids,
        operations=operations,
        external_dependencies=external_dependencies,
        payload_mappings=payload_mappings,
        schema_version=schema_version,
    )
    _validate_inventory_dispositions(
        document["inventory_dispositions"],
        execution_mode=run["execution_mode"],
        in_scope_tag_keys=baseline["in_scope_tag_keys"],
        operations=operations,
    )
    _validate_recovery_boundary(document["recovery_boundary"], required=status == "Partial")

    idempotency = _object(document["idempotency"], "$.idempotency")
    if schema_version == SCHEMA_VERSION:
        _exact_keys(
            idempotency,
            "$.idempotency",
            required={"checked", "remaining_actions", "evidence"},
        )
    else:
        _exact_keys(
            idempotency,
            "$.idempotency",
            required={"checked", "remaining_actions"},
            optional={"evidence"},
        )
    if not isinstance(idempotency.get("checked"), bool):
        raise RunValidationError("$.idempotency.checked must be a boolean")
    remaining_actions = _unique_texts(
        idempotency.get("remaining_actions"),
        "$.idempotency.remaining_actions",
    )
    idempotency_evidence = _unique_texts(
        idempotency.get("evidence", []),
        "$.idempotency.evidence",
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
        if schema_version == SCHEMA_VERSION and not idempotency_evidence:
            raise RunValidationError("Configured requires structured idempotency evidence")
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
        value = load_json(path)
    except StrictJsonError as exc:
        raise RunValidationError(str(exc), error_code=exc.error_code) from exc
    return validate_document(value)


def upgrade_document(document: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a safe v2.0 run to v2.1 without inventing missing mutation evidence."""
    document = deepcopy(validate_document(document))
    if document["schema_version"] == SCHEMA_VERSION:
        return document
    if document["run"]["status"] == "Configured":
        raise RunValidationError(
            "a finalized legacy run remains readable; do not rewrite its historical evidence"
        )
    unsafe_delta = [
        item["operation_id"]
        for item in document["object_changes"]
        if item["action"] in DELTA_ACTIONS
        and any(entry.get("state") == "in_progress" for entry in item["journal"])
        and "pre_write_comparison" not in item
    ]
    if unsafe_delta:
        raise RunValidationError(
            "legacy delta mutation history lacks pre-write drift evidence: "
            + ", ".join(unsafe_delta)
        )
    operations = {item["object_key"]: item for item in document["object_changes"]}
    requirements = {item["id"]: item for item in document["requirements"]}
    for route in document["first_party_data_routes"]:
        if "consumer_bindings" in route:
            continue
        bindings = []
        for object_key in route["consumer_object_keys"]:
            target = _effective_target(operations[object_key], "legacy first-party consumer")
            tag_type = _tag_type(target, "legacy first-party consumer")
            if tag_type in CUSTOM_CODE_TAG_TYPES:
                raise RunValidationError(
                    f"legacy first-party route {route['requirement_id']!r} uses Custom HTML/Image; "
                    "replace it with a verified native or installed-template consumer"
                )
            expected_product = FIRST_PARTY_PRODUCTS.get(route["feature"])
            product = expected_product or requirements[route["requirement_id"]].get("destination")
            if not isinstance(product, str) or not product.strip():
                raise RunValidationError(
                    f"legacy first-party route {route['requirement_id']!r} lacks product identity"
                )
            native_types = (
                GOOGLE_CONFIGURATION_TAG_TYPES
                | GA4_EVENT_TAG_TYPES
                | GOOGLE_ADS_CONVERSION_TAG_TYPES
            )
            native = tag_type in native_types
            bindings.append(
                {
                    "object_key": object_key,
                    "product": product,
                    "implementation": "native" if native else "installed-template",
                    "tag_type": tag_type,
                    "template_identity": None if native else tag_type,
                    "evidence": ["legacy-v2.0-route", *route["evidence"]],
                }
            )
        route["consumer_bindings"] = bindings
    document["schema_version"] = SCHEMA_VERSION
    document["idempotency"].setdefault("evidence", [])
    return validate_document(document)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _contract_fingerprint(contract: dict[str, Any]) -> str:
    return canonical_sha256(contract)


def _field_mappings(requirement: dict[str, Any]) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    field_scopes = {
        "parameters": "event-parameter",
        "user_properties": "user-property",
        "item_parameters": "item-parameter",
    }
    for map_name, field_scope in field_scopes.items():
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
                    "field_scope": field_scope,
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


def _durable_risk_reasons(document: dict[str, Any]) -> list[str]:
    operations = document["object_changes"]
    reasons: list[str] = []
    if any(item["action"] in {"remove", "replace"} for item in operations):
        reasons.append("destructive object action")
    if any(len(item["requirement_ids"]) > 1 for item in operations):
        reasons.append("shared object across requirements")
    high_impact_types = {
        "zone",
        "environment",
        "destination",
        "google tag configuration",
        "container setting",
        "template",
    }
    if any(item["object_type"] in high_impact_types for item in operations):
        reasons.append("high-impact GTM resource")
    products = {
        _normalized_token(item["product"])
        for item in document["consent_routes"]
        if item.get("product")
    }
    if len(products) > 1:
        reasons.append("multiple product consent routes")
    page_view_destinations = {
        item["destination"].strip().casefold()
        for item in document["page_view_decisions"]
        if isinstance(item.get("destination"), str)
    }
    if len(page_view_destinations) > 1:
        reasons.append("multiple Google page-view destinations")
    return reasons


def _preflight_issues(
    document: dict[str, Any],
    requirement_ids: set[str],
) -> list[str]:
    issues: list[str] = []
    baseline = document["container_baseline"]
    if not baseline["complete"]:
        issues.append("authoritative container baseline is incomplete")

    linked_operations = [
        item
        for item in document["object_changes"]
        if set(item["requirement_ids"]) & requirement_ids
    ]
    has_executing_target_tag = any(
        item["object_type"] == "tag" and item["action"] not in NON_EXECUTING_TAG_ACTIONS
        for item in linked_operations
    )
    durable_reasons = _durable_risk_reasons(document)
    if document["run"]["execution_mode"] == "isolated-lightweight" and durable_reasons:
        issues.append(
            "risk surface requires a durable configuration-run artifact: "
            + ", ".join(durable_reasons)
        )

    for mapping in document["payload_mappings"]:
        if not has_executing_target_tag or mapping["requirement_id"] not in requirement_ids:
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
    executable_tag_requirement_ids = {
        requirement_id
        for item in linked_operations
        if item["object_type"] == "tag" and item["action"] not in NON_EXECUTING_TAG_ACTIONS
        for requirement_id in item["requirement_ids"]
    }
    for requirement_id, requirement in requirements.items():
        if requirement["kind"] == "consent" or requirement["status"] == "Deferred":
            continue
        if (
            requirement_id in executable_tag_requirement_ids
            and requirement_id not in consent_by_requirement
        ):
            issues.append(f"consent route {requirement_id} is missing")

    topology_by_tag = {item["tag_object_key"]: item for item in document["execution_topologies"]}
    tag_operations = [
        item
        for item in linked_operations
        if item["object_type"] == "tag"
        and item["action"] not in NON_EXECUTING_TAG_ACTIONS
        and any(
            requirements.get(requirement_id, {}).get("kind") not in {None, "consent"}
            for requirement_id in item["requirement_ids"]
        )
    ]
    for operation in tag_operations:
        tag_key = operation["object_key"]
        topology = topology_by_tag.get(tag_key)
        if topology is None:
            issues.append(f"execution topology {tag_key} is missing")
            continue
        for requirement_id in operation["requirement_ids"]:
            requirement = requirements.get(requirement_id)
            if requirement is None or requirement["kind"] == "consent":
                continue
            route = consent_by_requirement.get(requirement_id)
            if route is None:
                continue
            if topology["consent_mode"] != route["mode"]:
                issues.append(
                    f"execution topology {tag_key} consent mode differs from {requirement_id}"
                )
            if route["normal_trigger"] not in {
                trigger["trigger_object_key"] for trigger in topology["normal_triggers"]
            }:
                issues.append(
                    f"execution topology {tag_key} normal triggers omit {requirement_id} route"
                )
            if set(topology["blocking_trigger_keys"]) != set(route["blocking_triggers"]):
                issues.append(
                    f"execution topology {tag_key} blocking triggers differ from {requirement_id}"
                )
            if set(topology["additional_consent_checks"]) != set(
                route["additional_consent_checks"]
            ):
                issues.append(
                    f"execution topology {tag_key} Additional Consent Checks differ from "
                    f"{requirement_id}"
                )

        if topology["page_view_capable"]:
            decisions = {
                item["destination"]: item
                for item in document["page_view_decisions"]
                if set(item["requirement_ids"]) & set(operation["requirement_ids"])
            }
            expected_destinations = set(topology["page_view_destinations"])
            if set(decisions) != expected_destinations:
                issues.append(
                    f"page-view ownership for {tag_key} must resolve exactly for destinations "
                    f"{sorted(expected_destinations)}"
                )
            for decision in decisions.values():
                if (
                    decision["owner"] == "google-tag-automatic"
                    and decision["owner_object_key"] == tag_key
                    and topology["lifecycle_role"] != "baseline-page-load"
                ):
                    issues.append(
                        f"automatic page-view owner {tag_key} requires baseline-page-load topology"
                    )

        mapped_items = [
            item
            for item in document["payload_mappings"]
            if item["requirement_id"] in operation["requirement_ids"]
            and item["destination_field"] == "items"
            and item["status"] == "mapped"
        ]
        if topology["ecommerce_route"].startswith("native-") and mapped_items:
            issues.append(f"ecommerce {tag_key} mixes a native route with a manual items mapping")

    first_party_by_requirement: dict[str, set[str]] = {}
    for route in document["first_party_data_routes"]:
        first_party_by_requirement.setdefault(route["requirement_id"], set()).add(route["feature"])
    for mapping in document["payload_mappings"]:
        if (
            not has_executing_target_tag
            or mapping["requirement_id"] not in requirement_ids
            or mapping["status"] != "mapped"
        ):
            continue
        if mapping["destination_field"] == "user_data" and not (
            first_party_by_requirement.get(mapping["requirement_id"], set())
            & {
                "ga4-user-provided-data",
                "google-ads-enhanced-conversions",
                "google-ads-tag-wide-user-data",
                "google-ads-user-provided-data-event",
                "vendor-advanced-matching",
            }
        ):
            issues.append(
                f"first-party-data route for {mapping['requirement_id']}::user_data is missing"
            )
        if mapping["destination_field"] == "user_id" and "ga4-user-id" not in (
            first_party_by_requirement.get(mapping["requirement_id"], set())
        ):
            issues.append(f"GA4 user_id route for {mapping['requirement_id']} is missing")
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
        raise RunValidationError(str(exc), error_code=exc.error_code) from exc
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
    high_risk = route == "combined" or any(
        item["action"] in {"remove", "replace"}
        or item["object_type"]
        in {
            "zone",
            "environment",
            "destination",
            "google tag configuration",
            "container setting",
            "template",
        }
        or len(item.get("requirement_ids") or contract_ids) > 1
        for item in contract["implementation"]["objects"]
    )
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
            "execution_mode": "isolated-durable" if high_risk else "isolated-lightweight",
            "publication": {"performed": False, "version_created": False},
        },
        "requirements": requirements,
        "object_changes": object_changes,
        "payload_mappings": payload_mappings,
        "consent_routes": [],
        "container_baseline": {
            "strategy": "relevant-families",
            "captured_at": None,
            "complete": False,
            "resource_families": [],
            "family_counts": {},
            "in_scope_tag_keys": [],
            "trigger_index": [],
            "preexisting_workspace_changes": None,
            "fingerprint": None,
        },
        "execution_topologies": [],
        "page_view_decisions": [],
        "first_party_data_routes": [],
        "inventory_dispositions": [],
        "saved_readback": [],
        "official_sources": official_sources,
        "external_dependencies": external_dependencies,
        "recovery_boundary": None,
        "idempotency": {"checked": False, "remaining_actions": [], "evidence": []},
        "recette_handoff": {
            "manifest_version": "2.0",
            "requirements": [
                {
                    "id": requirement_id,
                    "expected_tags": [],
                    "expected_normal_triggers": [],
                    "expected_blocking_triggers": [],
                    "expected_consent_states": [],
                    "expected_user_data_keys": [],
                    "network_cues": [],
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
    preflight_cache: dict[frozenset[str], list[str]] = {}
    unsafe = []
    failed = []
    for item in document["object_changes"]:
        operation_id = item["operation_id"]
        if item["state"] in {"in_progress", "uncertain"}:
            unsafe.append(operation_id)
        if item["state"] == "failed":
            failed.append(operation_id)
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
            requirement_key = frozenset(item["requirement_ids"])
            issues = preflight_cache.get(requirement_key)
            if issues is None:
                issues = _preflight_issues(document, set(requirement_key))
                preflight_cache[requirement_key] = issues
            if issues:
                preflight_blockers[operation_id] = issues
            else:
                ready.append(operation_id)
        else:
            ready.append(operation_id)
    safe_to_resume = not unsafe and not failed
    status = document["run"]["status"]
    if failed:
        suggested_status = (
            "Partial"
            if any(state in {"saved", "verified"} for state in states.values())
            else "Blocked"
        )
    elif unsafe:
        suggested_status = "Partial"
    elif all(state in {"verified", "skipped"} for state in states.values()):
        remaining = document["idempotency"]["remaining_actions"]
        suggested_status = (
            "Configured" if document["idempotency"]["checked"] and not remaining else "In progress"
        )
    else:
        suggested_status = "In progress"
    successful = status == "Configured"
    if failed:
        error_code = "failed_operations"
    elif unsafe:
        error_code = "unsafe_operations"
    elif preflight_blockers:
        error_code = "preflight_incomplete"
    elif all(state in {"verified", "skipped"} for state in states.values()) and not successful:
        error_code = "finalization_required"
    else:
        error_code = None
    return {
        "pass": successful,
        "valid": True,
        "successful": successful,
        "completed": document["run"]["phase"] == "complete",
        "resumable": safe_to_resume,
        "safe_to_resume": safe_to_resume,
        "error_code": error_code,
        "suggested_status": suggested_status,
        "ready_operations": ready,
        "waiting_on_dependencies": waiting,
        "preflight_blockers": preflight_blockers,
        "unsafe_operations": unsafe,
        "failed_operations": failed,
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
    pre_write_comparison: dict[str, Any] | None = None,
    pre_write_saved: Any = _UNSET,
    saved: Any = _UNSET,
    error: str | None = None,
) -> dict[str, Any]:
    """Apply one validated state transition; callers persist only the returned document."""
    document = upgrade_document(document)
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
    if pre_write_comparison is not None:
        if operation["action"] not in DELTA_ACTIONS:
            raise RunValidationError("pre-write comparison is accepted only for delta actions")
        pre_write_comparison = validate_pre_write_comparison(
            pre_write_comparison,
            operation=operation,
            saved=pre_write_saved,
            require_pass=state != "failed",
        )
    elif pre_write_saved is not _UNSET:
        raise RunValidationError("pre-write readback requires pre-write comparison evidence")
    if current == "planned" and state == "in_progress" and operation["action"] in DELTA_ACTIONS:
        if pre_write_comparison is None or pre_write_saved is _UNSET:
            raise RunValidationError(
                "delta mutation requires a fresh passing pre-write comparison and readback"
            )
    if state == "verified":
        if saved is _UNSET:
            raise RunValidationError("verified requires authoritative saved readback")
        comparison = validate_verification_comparison(
            comparison,
            operation=operation,
            saved=saved,
            require_pass=True,
        )
    else:
        if comparison is not None:
            raise RunValidationError("comparison is accepted only for a verified checkpoint")
        if saved is not _UNSET:
            raise RunValidationError("saved readback is accepted only for a verified checkpoint")
    if state in {"failed", "uncertain"}:
        error = _text(error, "error")

    operation["state"] = state
    operation.setdefault("journal", []).append({"state": state, "at": at, "note": note})
    if result is not None:
        operation["result"] = deepcopy(result)
    if comparison is not None:
        operation["comparison"] = deepcopy(comparison)
    if pre_write_comparison is not None:
        operation["pre_write_comparison"] = deepcopy(pre_write_comparison)
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
                "comparison": deepcopy(comparison),
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
    document = upgrade_document(document)
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
    operation.pop("comparison", None)
    operation.pop("pre_write_comparison", None)
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
    document["idempotency"] = {"checked": False, "remaining_actions": [], "evidence": []}
    return validate_document(document)


def finalize_document(
    document: dict[str, Any],
    *,
    idempotency_evidence: list[str],
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Atomically derive Configured only from complete readback and rerun evidence."""
    document = upgrade_document(document)
    evidence = _unique_texts(
        idempotency_evidence,
        "idempotency_evidence",
        allow_empty=False,
    )
    unfinished = [
        item["operation_id"]
        for item in document["object_changes"]
        if item["state"] not in {"verified", "skipped"}
    ]
    if unfinished:
        raise RunValidationError(
            "finalization requires every operation verified or skipped: " + ", ".join(unfinished)
        )
    active_requirement_ids = {
        item["id"] for item in document["requirements"] if item["status"] != "Deferred"
    }
    issues = _preflight_issues(document, active_requirement_ids)
    if issues:
        raise RunValidationError("finalization preflight is incomplete: " + "; ".join(issues))
    at = timestamp or _utc_now()
    _timestamp(at, "timestamp")
    for requirement in document["requirements"]:
        if requirement["status"] != "Deferred":
            requirement["status"] = "Configured"
    document["idempotency"] = {
        "checked": True,
        "remaining_actions": [],
        "evidence": evidence,
    }
    document["recovery_boundary"] = None
    document["run"]["phase"] = "complete"
    document["run"]["status"] = "Configured"
    document["run"]["updated_at"] = at
    return validate_document(document)


@contextmanager
def run_file_lock(path: Path):
    """Acquire a non-blocking cross-process lock for one run artifact."""
    lock_path = path.with_name(f".{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    stream = lock_path.open("a+b")
    try:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RunConflictError(
                f"run artifact is already controlled by another process: {path}"
            ) from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    finally:
        stream.close()


def _replaceable_planned_run(path: Path) -> bool:
    document = load_document(path)
    return (
        document["run"]["status"] == "In progress"
        and not document["saved_readback"]
        and all(item["state"] == "planned" for item in document["object_changes"])
    )


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    """Preserve the public helper while sharing the strict atomic writer."""
    write_json_atomic(path, value)


def _json_value_file(path: Path, label: str) -> Any:
    try:
        return load_json(path)
    except StrictJsonError as exc:
        raise RunValidationError(
            f"cannot load {label} {path}: {exc}",
            error_code=exc.error_code,
        ) from exc


def _json_file(path: Path, label: str) -> dict[str, Any]:
    return _object(_json_value_file(path, label), label)


def _markdown_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = "; ".join(str(item) for item in value)
    return str(value).replace("|", "\\|").replace("\n", " ")


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
        f"- Execution mode: `{run['execution_mode']}`",
        (
            "- Adapter baseline: {strategy}; complete={complete}; pre-existing workspace "
            "changes={changes}"
        ).format(
            strategy=document["container_baseline"]["strategy"],
            complete=str(document["container_baseline"]["complete"]).lower(),
            changes=document["container_baseline"]["preexisting_workspace_changes"],
        ),
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

    if document["inventory_dispositions"]:
        lines.extend(
            [
                "",
                "## Inventory-aligned tag change log",
                "",
                "| Order | Source row | Vendor/source | Disposition | Tag before | Tag after | "
                "Trigger before | Trigger after | Variable changes | Parameter changes | Consent "
                "changes | Rationale |",
                "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in sorted(
            document["inventory_dispositions"], key=lambda value: value["source_order"]
        ):
            lines.append(
                "| {order} | {row} | {source} | {disposition} | {before} | {after} | "
                "{trigger_before} | {trigger_after} | {variables} | {parameters} | {consent} | "
                "{rationale} |".format(
                    order=item["source_order"],
                    row=_markdown_cell(item["row_id"]),
                    source=_markdown_cell(item["source_locator"]),
                    disposition=_markdown_cell(item["disposition"]),
                    before=_markdown_cell(item["before_tag_name"]),
                    after=_markdown_cell(item["after_tag_name"]),
                    trigger_before=_markdown_cell(item["trigger_before"]),
                    trigger_after=_markdown_cell(item["trigger_after"]),
                    variables=_markdown_cell(item["variable_changes"]),
                    parameters=_markdown_cell(item["parameter_changes"]),
                    consent=_markdown_cell(item["consent_changes"]),
                    rationale=_markdown_cell(item["rationale"]),
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
            lines.append(
                "- Consent checks: built-in "
                + (", ".join(consent["built_in_consent_checks"]) or "none recorded")
                + "; Additional "
                + (", ".join(consent["additional_consent_checks"]) or "not set")
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

    lines.extend(["## Per-tag execution topology", ""])
    if not document["execution_topologies"]:
        lines.append("No tag topology is recorded.")
    for topology in document["execution_topologies"]:
        normal_triggers = ", ".join(
            "{key} [{role}/{type}]".format(
                key=trigger["trigger_object_key"],
                role=trigger["role"],
                type=trigger["type"],
            )
            for trigger in topology["normal_triggers"]
        )
        lines.append(
            "- `{tag}`: {role}; triggers {triggers}; blocks {blocks}; Additional "
            "{additional}; firing {firing}; pre-CMP {pre_cmp}; ecommerce {ecommerce}".format(
                tag=topology["tag_object_key"],
                role=topology["lifecycle_role"],
                triggers=normal_triggers,
                blocks=", ".join(topology["blocking_trigger_keys"]) or "none",
                additional=", ".join(topology["additional_consent_checks"]) or "not set",
                firing=topology["firing_option"],
                pre_cmp=topology["pre_cmp_policy"],
                ecommerce=topology["ecommerce_route"],
            )
        )
    lines.append("")

    lines.extend(["## Page-view and first-party-data decisions", ""])
    for decision in document["page_view_decisions"]:
        lines.append(
            f"- Page view `{decision['destination']}`: {decision['owner']}; "
            f"send_page_view={str(decision['send_page_view']).lower()}; "
            f"Google tag={decision.get('google_tag_object_key') or 'none'}; "
            f"{decision['reason']}"
        )
    for route in document["first_party_data_routes"]:
        field_names = ", ".join(field["name"] for field in route["fields"])
        lines.append(
            f"- First-party data `{route['requirement_id']}`: {route['feature']}; "
            f"destination={route['destination_field']}; timing={route['timing']}; "
            f"hashing={route['hashing_owner']}; keys={field_names}"
        )
    if not document["page_view_decisions"] and not document["first_party_data_routes"]:
        lines.append("- No page-view-capable or first-party-data decision is in scope.")
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
    print(json.dumps(value, indent=2, sort_keys=True, allow_nan=False))


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
    init_parser.add_argument(
        "--replace-planned",
        action="store_true",
        help="Replace only an existing untouched planned run; never replace saved history.",
    )

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--run", type=Path, required=True)

    upgrade_parser = subparsers.add_parser("upgrade")
    upgrade_parser.add_argument("--run", type=Path, required=True)

    checkpoint_parser = subparsers.add_parser("checkpoint")
    checkpoint_parser.add_argument("--run", type=Path, required=True)
    checkpoint_parser.add_argument("--operation", required=True)
    checkpoint_parser.add_argument(
        "--state",
        choices=sorted(OPERATION_STATES - {"planned"}),
        required=True,
    )
    checkpoint_parser.add_argument("--note", required=True)
    checkpoint_parser.add_argument("--timestamp")
    checkpoint_parser.add_argument("--result", type=Path)
    checkpoint_parser.add_argument("--comparison", type=Path)
    checkpoint_parser.add_argument("--saved-readback", type=Path)
    checkpoint_parser.add_argument("--pre-write-comparison", type=Path)
    checkpoint_parser.add_argument("--pre-write-readback", type=Path)
    checkpoint_parser.add_argument("--error")

    reopen_parser = subparsers.add_parser("reopen")
    reopen_parser.add_argument("--run", type=Path, required=True)
    reopen_parser.add_argument("--operation", required=True)
    reopen_parser.add_argument("--note", required=True)
    reopen_parser.add_argument("--timestamp")

    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--run", type=Path, required=True)
    finalize_parser.add_argument(
        "--evidence",
        action="append",
        required=True,
        help="Repeat for each idempotent-rerun/readback evidence locator.",
    )
    finalize_parser.add_argument("--timestamp")

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
            with run_file_lock(args.output):
                if args.output.exists():
                    if not args.replace_planned:
                        raise RunValidationError(
                            f"output already exists; use a new path or --replace-planned: "
                            f"{args.output}"
                        )
                    if not _replaceable_planned_run(args.output):
                        raise RunValidationError(
                            "--replace-planned refuses an artifact with non-planned or saved state"
                        )
                atomic_write(args.output, document)
            _emit_json({"pass": True, "output": str(args.output.resolve())})
        elif args.command == "inspect":
            _emit_json(inspect_document(load_document(args.run)))
        elif args.command == "upgrade":
            with run_file_lock(args.run):
                document = upgrade_document(load_document(args.run))
                atomic_write(args.run, document)
            _emit_json({"pass": True, "schema_version": document["schema_version"]})
        elif args.command == "checkpoint":
            result = _json_file(args.result, "result") if args.result else None
            comparison = _json_file(args.comparison, "comparison") if args.comparison else None
            pre_write_comparison = (
                _json_file(args.pre_write_comparison, "pre-write comparison")
                if args.pre_write_comparison
                else None
            )
            pre_write_saved = (
                _json_value_file(args.pre_write_readback, "pre-write readback")
                if args.pre_write_readback
                else _UNSET
            )
            saved = (
                _json_value_file(args.saved_readback, "saved readback")
                if args.saved_readback
                else _UNSET
            )
            with run_file_lock(args.run):
                document = checkpoint_operation(
                    load_document(args.run),
                    operation_id=args.operation,
                    state=args.state,
                    note=args.note,
                    timestamp=args.timestamp,
                    result=result,
                    comparison=comparison,
                    pre_write_comparison=pre_write_comparison,
                    pre_write_saved=pre_write_saved,
                    saved=saved,
                    error=args.error,
                )
                atomic_write(args.run, document)
            _emit_json({"pass": True, "operation": args.operation, "state": args.state})
        elif args.command == "reopen":
            with run_file_lock(args.run):
                document = reopen_failed_operation(
                    load_document(args.run),
                    operation_id=args.operation,
                    note=args.note,
                    timestamp=args.timestamp,
                )
                atomic_write(args.run, document)
            _emit_json({"pass": True, "operation": args.operation, "state": "planned"})
        elif args.command == "finalize":
            with run_file_lock(args.run):
                document = finalize_document(
                    load_document(args.run),
                    idempotency_evidence=args.evidence,
                    timestamp=args.timestamp,
                )
                atomic_write(args.run, document)
            _emit_json({"pass": True, "status": "Configured"})
        else:
            rendered = render_markdown(
                load_document(args.run),
                embed_machine=args.embed_machine,
            )
            if args.output:
                write_text_atomic(args.output, rendered)
                _emit_json({"pass": True, "output": str(args.output.resolve())})
            else:
                sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
                print(rendered, end="")
    except RunConflictError as exc:
        _emit_json({"pass": False, "error_code": "run_conflict", "error": str(exc)})
        return 2
    except RunValidationError as exc:
        _emit_json({"pass": False, "error_code": exc.error_code, "error": str(exc)})
        return 2
    except (OSError, UnicodeError) as exc:
        _emit_json({"pass": False, "error_code": "io_error", "error": str(exc)})
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
