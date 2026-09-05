#!/usr/bin/env python3
"""Shared current web-domain normalization and validation rules."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from requirement_validation import DELTA_ACTIONS
from resource_registry import CONFIGURATION_SETTINGS_VARIABLE_TYPES
from run_model_web import (
    BUILT_IN_TRIGGER_TYPES,
    CONFIGURATION_FIELD_ALIASES,
    CONSENT_MODES,
    CUSTOM_CODE_TAG_TYPES,
    ECOMMERCE_ROUTES,
    EXTENDED_MAPPING_KEYS,
    FIRING_OPTIONS,
    FIRST_PARTY_FEATURES,
    FIRST_PARTY_PRODUCTS,
    GA4_EVENT_TAG_TYPES,
    GOOGLE_ADS_CONVERSION_TAG_TYPES,
    GOOGLE_CONFIGURATION_TAG_TYPES,
    INVENTORY_DISPOSITIONS,
    LIFECYCLE_ROLES,
    MAPPING_METHODS,
    MAPPING_STATUSES,
    NON_EXECUTING_TAG_ACTIONS,
    NORMAL_TRIGGER_ROLES,
    NORMAL_TRIGGER_TYPES,
    PAGE_LOAD_TRIGGER_TYPES,
    PAGE_VIEW_OCCURRENCES,
    PAGE_VIEW_OWNERS,
    PRE_CMP_POLICIES,
    SCHEMA_VERSION,
    SHAPE_COMPATIBILITY,
    TAG_TYPE_ALIASES,
    TRIGGER_TYPE_ALIASES,
    VERIFICATION_SCHEMA_VERSION,
)

# Google product support, native type IDs, and consent parameters checked 2026-09-05:
# https://support.google.com/tagmanager/answer/10000067
# https://developers.google.com/tag-platform/tag-manager/restrict
# https://developers.google.com/tag-platform/gtagjs/reference#consent
# This bounds declared names, not the exact checks exposed by each installed template.
# Custom templates/CMPs can define their own types; this is NOT a GTM-wide allowlist.
_GOOGLE_NATIVE_CONSENT_TAG_TYPES = (
    GOOGLE_CONFIGURATION_TAG_TYPES
    | GA4_EVENT_TAG_TYPES
    | GOOGLE_ADS_CONVERSION_TAG_TYPES
    | {"sp", "flc", "fls", "gclidw"}
)
_GOOGLE_NATIVE_CONSENT_TYPES = {
    "ad_storage",
    "analytics_storage",
    "ad_user_data",
    "ad_personalization",
}


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
            if isinstance(key, str) and _normalized_token(key) == "configsettingstable":
                rows = item.get("list", [])
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    entries = row.get("map", []) if isinstance(row, dict) else []
                    if not isinstance(entries, list):
                        continue
                    decoded = {
                        entry.get("key"): _decode_parameter_value(entry)
                        for entry in entries
                        if isinstance(entry, dict) and isinstance(entry.get("key"), str)
                    }
                    parameter_name = decoded.get("parameter") or decoded.get("name")
                    if (
                        isinstance(parameter_name, str)
                        and _normalized_token(parameter_name) in normalized_names
                    ):
                        return True, decoded.get("parameterValue", decoded.get("value"))
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


def _configuration_settings_target(
    target: dict[str, Any],
    operations: dict[str, dict[str, Any]] | None,
    path: str,
) -> dict[str, Any] | None:
    present, reference = _configuration_value(
        target,
        {
            "configSettingsVariable",
            "configuration_settings_variable",
            "configurationSettingsVariable",
        },
    )
    if not present:
        return None
    if operations is None:
        raise RunValidationError(f"{path} cannot resolve its Configuration Settings variable")
    if not isinstance(reference, str) or not reference.strip():
        raise RunValidationError(f"{path} Configuration Settings reference must be a string")
    reference = reference.strip()
    name = (
        reference[2:-2].strip() if reference.startswith("{{") and reference.endswith("}}") else None
    )
    operation = operations.get(reference)
    if operation is None and name:
        operation = next(
            (
                item
                for item in operations.values()
                if (item.get("object_type") or item.get("resource_family")) == "variable"
                and item.get("name") == name
            ),
            None,
        )
    if (
        operation is None
        or (operation.get("object_type") or operation.get("resource_family")) != "variable"
    ):
        raise RunValidationError(f"{path} Configuration Settings variable is unresolved")
    settings = _effective_target(operation, f"{path}.configuration_settings")
    settings_type = _normalized_token(str(settings.get("type", "")))
    if settings_type not in CONFIGURATION_SETTINGS_VARIABLE_TYPES:
        raise RunValidationError(
            f"{path} reference is not a Google tag Configuration Settings variable"
        )
    return settings


def _effective_configuration_value(
    target: dict[str, Any],
    names: set[str],
    operations: dict[str, dict[str, Any]] | None,
    path: str,
) -> tuple[bool, Any]:
    direct = _configuration_value(target, names)
    if direct[0]:
        return direct
    settings = _configuration_settings_target(target, operations, path)
    return _configuration_value(settings, names) if settings is not None else (False, None)


def _send_page_view_value(
    target: dict[str, Any],
    path: str,
    operations: dict[str, dict[str, Any]] | None = None,
) -> bool:
    present, raw = _effective_configuration_value(
        target, {"send_page_view", "sendPageView"}, operations, path
    )
    if not present:
        return True
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str) and raw.casefold() in {"true", "false"}:
        return raw.casefold() == "true"
    raise RunValidationError(f"{path}.send_page_view must resolve to a boolean")


def _resolve_constant_reference(
    value: Any, operations: dict[str, dict[str, Any]], path: str
) -> Any:
    if not isinstance(value, str) or not (value.startswith("{{") and value.endswith("}}")):
        return value
    name = value[2:-2].strip()
    operation = next(
        (
            item
            for item in operations.values()
            if (item.get("object_type") or item.get("resource_family")) == "variable"
            and item.get("name") == name
        ),
        None,
    )
    if operation is None:
        raise RunValidationError(f"{path} contains unresolved variable reference {value!r}")
    target = _effective_target(operation, path)
    if _normalized_token(str(target.get("type", ""))) not in {"c", "constant"}:
        raise RunValidationError(f"{path} destination reference must use a Constant variable")
    present, resolved = _configuration_value(target, {"value"})
    if not present or not isinstance(resolved, str) or not resolved.strip():
        raise RunValidationError(f"{path} Constant variable has no literal value")
    return resolved.strip()


def _configured_destinations(
    target: dict[str, Any],
    operations: dict[str, dict[str, Any]],
    path: str,
) -> set[str]:
    candidates: set[str] = set()
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
    if present and isinstance(value, str):
        candidates.add(_resolve_constant_reference(value, operations, path))
    for collection_name in {"destinations", "destination_ids", "destinationIds"}:
        collection_present, collection = _configuration_value(target, {collection_name})
        if not collection_present:
            continue
        if not isinstance(collection, list):
            collection = [collection]
        for item in collection:
            if isinstance(item, str):
                candidates.add(_resolve_constant_reference(item, operations, path))
            elif isinstance(item, dict):
                for key in ("id", "value", "destinationId", "measurementId"):
                    candidate = item.get(key)
                    if isinstance(candidate, str):
                        candidates.add(_resolve_constant_reference(candidate, operations, path))
    return candidates


def _configured_transport_endpoint(
    operation: dict[str, Any],
    operations: dict[str, dict[str, Any]],
    path: str,
) -> str | None:
    target = _effective_target(operation, path)
    present, value = _effective_configuration_value(
        target,
        {
            "server_container_url",
            "serverContainerUrl",
            "transport_url",
            "transportUrl",
        },
        operations,
        path,
    )
    if not present:
        return None
    resolved = _resolve_constant_reference(value, operations, path)
    if not isinstance(resolved, str) or not resolved.strip():
        raise RunValidationError(f"{path} transport endpoint must resolve to a non-empty string")
    return _normalize_transport_endpoint(resolved, path)


def _normalize_transport_endpoint(value: str, path: str) -> str:
    endpoint = value.strip().rstrip("/")
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise RunValidationError(
            f"{path} transport endpoint must be an absolute credential-free HTTPS URL"
        )
    return endpoint


def _validate_google_destination(
    target: dict[str, Any],
    destination: str,
    path: str,
    operations: dict[str, dict[str, Any]] | None = None,
) -> None:
    operations = operations or {}
    candidates = _configured_destinations(target, operations, path)
    if destination not in candidates:
        raise RunValidationError(f"{path} does not bind destination {destination!r}")


def _validate_payload_mappings(raw: Any, requirement_ids: set[str]) -> list[dict[str, Any]]:
    identities: set[tuple[str, str, str]] = set()
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
        identity = (requirement_id, field_scope, destination_field)
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


def _trigger_filter_predicates(
    target: dict[str, Any],
    path: str,
) -> tuple[dict[tuple[str, bool], str], set[tuple[str, bool]]]:
    """Index actual non-event Conditions by operand/operator/options and polarity.

    GTM's Condition API stores operands and flags as unordered named parameter rows:
    https://developers.google.com/tag-platform/tag-manager/api/reference/rest/v2/Condition
    Only structural complements are proved; no variable-name heuristics, CMP value-domain
    assumptions, regex equivalence, or runtime evaluation belongs in this static check.
    """
    predicates: dict[tuple[str, bool], str] = {}
    event_context: set[tuple[str, bool]] = set()
    for field in ("filter", "customEventFilter", "autoEventFilter"):
        rows = target.get(field, [])
        if field == "customEventFilter" and isinstance(rows, str):
            if rows != ".*":
                event_context.add((canonical_sha256({"compact_event_regex": rows}), False))
            continue  # The contract's compact event selector is lifecycle, not eligibility.
        for index, raw in enumerate(_array(rows, f"{path}.{field}")):
            row_path = f"{path}.{field}[{index}]"
            row = _object(raw, row_path)
            operator = _text(row.get("type"), f"{row_path}.type")
            parameters: dict[str, Any] = {}
            for entry in _array(row.get("parameter"), f"{row_path}.parameter"):
                entry = _object(entry, f"{row_path}.parameter[]")
                key = _text(entry.get("key"), f"{row_path}.parameter[].key")
                if key in parameters:
                    raise RunValidationError(f"{row_path}.parameter repeats key {key!r}")
                parameters[key] = _decode_parameter_value(entry)
            if not {"arg0", "arg1"} <= parameters.keys():
                raise RunValidationError(f"{row_path} requires GTM arg0 and arg1 parameters")
            negate = parameters.pop("negate", False)
            ignore_case = parameters.pop("ignore_case", False)
            if not isinstance(negate, bool) or not isinstance(ignore_case, bool):
                raise RunValidationError(f"{row_path} negate/ignore_case must be boolean flags")
            if operator == "matchRegex":
                parameters["ignore_case"] = ignore_case
            if parameters["arg0"] in ("{{_event}}", "{{Event}}"):
                parameters["arg0"] = "{{_event}}"
                if operator == "matchRegex" and parameters["arg1"] == ".*" and not negate:
                    continue  # An unrestricted event selector adds no coverage constraint.
                event_context.add(
                    (canonical_sha256({"type": operator, "parameters": parameters}), negate)
                )
                continue
            signature = canonical_sha256({"type": operator, "parameters": parameters})
            predicates[(signature, negate)] = row_path
    return predicates, event_context


def _validate_trigger_consent_predicates(
    normal_triggers: list[dict[str, str]],
    blocking: list[str],
    operation_by_key: dict[str, dict[str, Any]],
    path: str,
) -> None:
    """Reject a repeated custom grant whose inverse is already an attached block.

    Filter rows are ANDed. A block with additional independent predicates is not the
    inverse of one firing condition. Shared business/host/environment filters can supply
    that context, but must never themselves be rejected merely for appearing in both.
    """
    by_trigger: dict[str, dict[tuple[str, bool], str]] = {}
    event_contexts: dict[str, set[tuple[str, bool]]] = {}
    for key in dict.fromkeys(
        [trigger["trigger_object_key"] for trigger in normal_triggers] + blocking
    ):
        if key in BUILT_IN_TRIGGER_TYPES:
            by_trigger[key] = {}
            event_contexts[key] = set()
            continue
        operation = operation_by_key.get(key)
        if operation is None or operation["object_type"] != "trigger":
            raise RunValidationError(f"{path} requires bound trigger snapshot for {key!r}")
        trigger_path = f"{path}.bound_trigger[{key!r}]"
        by_trigger[key], event_contexts[key] = _trigger_filter_predicates(
            _effective_target(operation, trigger_path), trigger_path
        )
    for trigger in normal_triggers:
        normal = by_trigger[trigger["trigger_object_key"]]
        for block_key in blocking:
            if not event_contexts[block_key] <= event_contexts[trigger["trigger_object_key"]]:
                # Do not remove a firing condition on the strength of an exception whose
                # event coverage is unproved. Exact lifecycle coverage remains a source/UI
                # review duty; this check does not infer arbitrary regex containment.
                continue
            block = by_trigger[block_key]
            for (signature, negate), normal_path in normal.items():
                inverse = (signature, not negate)
                if inverse in block and block.keys() - {inverse} <= normal.keys():
                    raise RunValidationError(
                        f"{path}: duplicated consent predicate between normal firing "
                        f"{normal_path} and blocking {block[inverse]}; "
                        "the attached block already owns this custom eligibility condition"
                    )


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
                "page_view_occurrences",
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
        expected_baseline_roles = (
            {"cmp-readiness-grant"}
            if mode == "strict-basic"
            else {"initialization-page-load", "cmp-readiness-grant"}
        )
        if role == "baseline-page-load" and not expected_baseline_roles & trigger_roles:
            raise RunValidationError(
                f"{path}.baseline-page-load under {mode} requires a {' or '.join(sorted(expected_baseline_roles))} trigger"
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
        built_in = _unique_texts(
            item.get("built_in_consent_checks"),
            f"{path}.built_in_consent_checks",
        )
        # Built-in checks are template behavior, never another configurable firing gate.
        # They can coexist with a strict-basic vendor block. Additional checks below
        # are different: GTM requires all their configured types to be granted.
        # https://support.google.com/tagmanager/answer/10718549
        if _tag_type(target, f"{path}.bound_tag") in _GOOGLE_NATIVE_CONSENT_TAG_TYPES and (
            unsupported := set(built_in) - _GOOGLE_NATIVE_CONSENT_TYPES
        ):
            raise RunValidationError(
                f"{path}.built_in_consent_checks contains undocumented Google native "
                f"consent types: {sorted(unsupported)}"
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
            if blocking:
                _validate_trigger_consent_predicates(
                    normal_triggers, blocking, operation_by_key, path
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
        page_view_occurrences = _unique_texts(
            item.get("page_view_occurrences"),
            f"{path}.page_view_occurrences",
        )
        if set(page_view_occurrences) - PAGE_VIEW_OCCURRENCES:
            raise RunValidationError(f"{path}.page_view_occurrences contains unsupported values")
        if item["page_view_capable"] != bool(page_view_occurrences):
            raise RunValidationError(
                f"{path}.page_view_occurrences must be populated exactly when page_view_capable"
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

    seen: set[tuple[str, str]] = set()
    records: list[dict[str, Any]] = []
    for index, item_raw in enumerate(_array(raw, "$.page_view_decisions")):
        path = f"$.page_view_decisions[{index}]"
        item = _object(item_raw, path)
        _exact_keys(
            item,
            path,
            required={
                "destination",
                "occurrence",
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
        occurrence = _text(item.get("occurrence"), f"{path}.occurrence")
        if occurrence not in PAGE_VIEW_OCCURRENCES:
            raise RunValidationError(f"{path}.occurrence has unsupported value {occurrence!r}")
        decision_key = (destination, occurrence)
        if decision_key in seen:
            raise RunValidationError(
                f"duplicate page-view decision for {destination!r} / {occurrence!r}"
            )
        seen.add(decision_key)
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
        if send_page_view is not None and not isinstance(send_page_view, bool):
            raise RunValidationError(f"{path}.send_page_view must be boolean or null")
        if owner == "google-tag-automatic":
            if occurrence != "initial-page-load":
                raise RunValidationError(
                    f"{path}.google-tag-automatic covers only the initial page load; "
                    "model history-based collection separately"
                )
            if not owner_key or owner_key != google_tag_key or send_page_view is not True:
                raise RunValidationError(
                    f"{path}.google-tag-automatic requires the same owner and Google tag key "
                    "with send_page_view true"
                )
            owner_operation, owner_target = bound_tag(owner_key, f"{path}.owner_object_key")
            if _tag_type(owner_target, f"{path}.owner") not in GOOGLE_CONFIGURATION_TAG_TYPES:
                raise RunValidationError(f"{path}.google-tag-automatic owner is not a Google tag")
            if not _send_page_view_value(owner_target, f"{path}.owner", operations):
                raise RunValidationError(f"{path}.send_page_view differs from the bound Google tag")
            _validate_google_destination(owner_target, destination, f"{path}.owner", operations)
            if not linked <= set(owner_operation["requirement_ids"]):
                raise RunValidationError(f"{path}.owner does not cover its requirement_ids")
        elif owner == "dedicated-ga4-event":
            if not owner_key or not google_tag_key or send_page_view is not False:
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
            _validate_google_destination(owner_target, destination, f"{path}.owner", operations)
            if not linked <= set(owner_operation["requirement_ids"]):
                raise RunValidationError(f"{path}.owner does not cover its requirement_ids")
            google_operation, google_target = bound_tag(
                google_tag_key,
                f"{path}.google_tag_object_key",
            )
            if _tag_type(google_target, f"{path}.google_tag") not in GOOGLE_CONFIGURATION_TAG_TYPES:
                raise RunValidationError(f"{path}.google_tag_object_key is not a Google tag")
            if _send_page_view_value(google_target, f"{path}.google_tag", operations):
                raise RunValidationError(
                    f"{path}.dedicated-ga4-event requires bound Google tag send_page_view false"
                )
            _validate_google_destination(
                google_target, destination, f"{path}.google_tag", operations
            )
            if not linked <= set(google_operation["requirement_ids"]):
                raise RunValidationError(f"{path}.Google tag does not cover its requirement_ids")
        elif owner == "internal-tag":
            if not owner_key or google_tag_key is not None or send_page_view is not None:
                raise RunValidationError(
                    f"{path}.internal-tag requires an owner, no Google tag, and null send_page_view"
                )
            owner_operation, _ = bound_tag(owner_key, f"{path}.owner_object_key")
            if not linked <= set(owner_operation["requirement_ids"]):
                raise RunValidationError(f"{path}.owner does not cover its requirement_ids")
        else:
            if owner_key is not None or send_page_view is not None:
                raise RunValidationError(
                    f"{path}.{owner} requires a null owner_object_key and send_page_view null"
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
                if occurrence == "initial-page-load" and _send_page_view_value(
                    google_target, f"{path}.google_tag", operations
                ):
                    raise RunValidationError(
                        f"{path}.{owner} requires bound Google tag send_page_view false"
                    )
                _validate_google_destination(
                    google_target, destination, f"{path}.google_tag", operations
                )
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
    if feature == "analytics-user-id":
        if (
            hashing_owner != "not-applicable"
            or timing not in {"tag-wide", "same-event"}
            or destination_field != "user_id"
            or field_names != {"user_id"}
        ):
            raise RunValidationError(
                f"{path}.analytics-user-id requires user_id, tag-wide or same-event timing, "
                "one user_id field, and no hashing"
            )
        if product_types & (
            GOOGLE_CONFIGURATION_TAG_TYPES | GA4_EVENT_TAG_TYPES | GOOGLE_ADS_CONVERSION_TAG_TYPES
        ):
            raise RunValidationError(
                f"{path}.analytics-user-id is reserved for non-Google analytics consumers"
            )
        return
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
        if not product_types <= {"googtag"}:
            raise RunValidationError(
                f"{path}.google-ads-enhanced-conversions requires the Google tag associated "
                "with the Ads conversion action"
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
        if product_types != {"googleadsuserprovideddataevent"}:
            raise RunValidationError(
                f"{path}.google-ads-user-provided-data-event requires the native "
                "Google Ads User-Provided Data Event tag"
            )
    elif feature == "google-ads-server-user-data-transport":
        if destination_field != "user_data" or timing not in {"same-event", "tag-wide"}:
            raise RunValidationError(
                f"{path}.{feature} requires same-event or explicitly authorized tag-wide user_data"
            )
        expected_types = GA4_EVENT_TAG_TYPES if timing == "same-event" else {"googtag"}
        if not product_types <= expected_types:
            owner = "GA4 Event sender" if timing == "same-event" else "Google tag sender"
            raise RunValidationError(f"{path}.{feature} requires the documented {owner}")
    elif feature == "google-ads-server-user-provided-data-event":
        if destination_field != "user_data" or timing != "prior-page":
            raise RunValidationError(
                f"{path}.{feature} requires prior-page user_data on the event where it is available"
            )
        if not product_types <= ({"googtag"} | GA4_EVENT_TAG_TYPES):
            raise RunValidationError(
                f"{path}.{feature} requires a Google tag or GA4 Event user_data sender"
            )

    if feature.startswith("google-ads-") and feature not in {
        "google-ads-enhanced-conversions",
        "google-ads-tag-wide-user-data",
        "google-ads-server-user-data-transport",
        "google-ads-server-user-provided-data-event",
    }:
        if product_types & (GOOGLE_CONFIGURATION_TAG_TYPES | GA4_EVENT_TAG_TYPES):
            raise RunValidationError(
                f"{path}.{feature} must not bind a GA4 or generic Google configuration tag"
            )
    externally_administered = {
        "ga4-user-provided-data",
        "google-ads-enhanced-conversions",
        "google-ads-tag-wide-user-data",
        "google-ads-user-provided-data-event",
        "google-ads-server-user-data-transport",
        "google-ads-server-user-provided-data-event",
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
    mapping_by_identity = {
        (item["requirement_id"], item["destination_field"]): item
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
        if item.get("feature") in {
            "google-ads-server-user-data-transport",
            "google-ads-server-user-provided-data-event",
        }:
            required_keys.add("server_consumer_object_keys")
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
            present, configured_value = _configuration_value(target, {destination_field})
            if not present:
                raise RunValidationError(
                    f"{path}.consumer {object_key!r} does not configure {destination_field!r}"
                )
            expected_binding = mapping_by_identity[(requirement_id, destination_field)].get(
                "gtm_resolution"
            )
            if expected_binding is not None and configured_value != expected_binding:
                raise RunValidationError(
                    f"{path}.consumer {object_key!r} {destination_field!r} binding differs "
                    "from the approved field binding"
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
