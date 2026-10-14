"""Web native: shared across preparation and execution."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from gtm_configure.core.validation import (
    RunValidationError,
    array,
    canonical_sha256,
    normalized_token,
    object,
    text,
    unique_texts,
)
from gtm_configure.domain.native import (
    FieldResolutionError,
    effective_collection_fields,
    effective_fields,
    field_key,
    local_fields,
)
from gtm_configure.domain.native import decode_parameter as _decode_parameter_value
from gtm_configure.domain.web_model import (
    BUILT_IN_TRIGGER_TYPES,
    NON_EXECUTING_TAG_ACTIONS,
    TAG_TYPE_ALIASES,
    TRIGGER_TYPE_ALIASES,
)


def effective_target(operation: dict[str, Any], path: str) -> dict[str, Any]:
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


def semantic_trigger_reference(value: Any, path: str) -> str:
    reference = text(value, path)
    if reference in {key.removeprefix("trigger::builtin::") for key in BUILT_IN_TRIGGER_TYPES}:
        return f"trigger::builtin::{reference}"
    if reference.startswith("trigger::") and len(reference) > len("trigger::"):
        return reference
    raise RunValidationError(
        f"{path} must use a semantic trigger:: reference or a reserved built-in trigger ID"
    )


def semantic_trigger_references(value: Any, path: str) -> list[str]:
    references = [semantic_trigger_reference(item, f"{path}[]") for item in array(value, path)]
    if len(set(references)) != len(references):
        raise RunValidationError(f"{path} contains duplicate trigger references")
    return references


def _normalized_trigger_type(value: Any, path: str) -> str:
    raw = text(value, path)
    normalized = TRIGGER_TYPE_ALIASES.get(normalized_token(raw))
    if normalized is None:
        raise RunValidationError(f"{path} has unsupported GTM trigger type {raw!r}")
    return normalized


def configuration_value(target: dict[str, Any], names: set[str]) -> tuple[bool, Any]:
    try:
        return field_value(local_fields(target), names)
    except FieldResolutionError as exc:
        raise RunValidationError(str(exc)) from exc


def field_value(fields: dict[str, Any], names: set[str]) -> tuple[bool, Any]:
    matches = set(fields) & {field_key(name) for name in names}
    if len(matches) > 1:
        raise RunValidationError("ambiguous configuration field aliases")
    return (True, fields[next(iter(matches))]) if matches else (False, None)


def _native_variables(operations, path):
    return {
        item["name"]: effective_target(item, path)
        for item in (operations or {}).values()
        if (item.get("object_type") or item.get("resource_family")) == "variable"
        and item.get("action") not in NON_EXECUTING_TAG_ACTIONS
    }


def resolved_collection_fields(target, operations, path, *, namespace):
    try:
        return effective_collection_fields(
            target, _native_variables(operations, path), namespace=namespace
        )
    except FieldResolutionError as exc:
        raise RunValidationError(f"{path}: {exc}") from exc


def resolved_fields(target, operations, path, *, event_settings=True):
    try:
        return effective_fields(
            target, _native_variables(operations, path), event_settings=event_settings
        )
    except FieldResolutionError as exc:
        raise RunValidationError(f"{path}: {exc}") from exc


def tag_type(target: dict[str, Any], path: str) -> str:
    normalized = normalized_token(text(target.get("type"), f"{path}.type"))
    return TAG_TYPE_ALIASES.get(normalized, normalized)


def tag_trigger_references(
    target: dict[str, Any],
    field: str,
    path: str,
) -> list[str]:
    raw = target.get(field, [])
    return semantic_trigger_references(raw, f"{path}.{field}")


def tag_additional_consent_checks(target: dict[str, Any], path: str) -> list[str]:
    direct = target.get("additional_consent_checks")
    if direct is not None:
        return unique_texts(direct, f"{path}.additional_consent_checks")
    settings = target.get("consentSettings")
    if settings is None:
        return []
    settings = object(settings, f"{path}.consentSettings")
    status = settings.get("consentStatus")
    if status in {None, "notSet", "notNeeded"}:
        return []
    consent_type = settings.get("consentType")
    if not isinstance(consent_type, dict):
        raise RunValidationError(f"{path}.consentSettings.consentType must be an object")
    values = consent_type.get("list", [])
    checks = []
    for index, item in enumerate(array(values, f"{path}.consentSettings.consentType.list")):
        item = object(item, f"{path}.consentSettings.consentType.list[{index}]")
        checks.append(text(item.get("value"), f"{path}.consentSettings.consentType.list[].value"))
    if len(set(checks)) != len(checks):
        raise RunValidationError(f"{path}.consentSettings contains duplicate consent types")
    return checks


def tag_firing_option(target: dict[str, Any], path: str) -> str:
    raw = target.get("tagFiringOption")
    if raw is None:
        return "once-per-event"
    normalized = {
        "onceperevent": "once-per-event",
        "onceperload": "once-per-page",
        "unlimited": "unlimited",
    }.get(normalized_token(text(raw, f"{path}.tagFiringOption")))
    if normalized is None:
        raise RunValidationError(f"{path}.tagFiringOption is unsupported")
    return normalized


def effective_configuration_value(
    target: dict[str, Any],
    names: set[str],
    operations: dict[str, dict[str, Any]] | None,
    path: str,
) -> tuple[bool, Any]:
    return field_value(resolved_fields(target, operations, path, event_settings=False), names)


def send_page_view_value(
    target: dict[str, Any],
    path: str,
    operations: dict[str, dict[str, Any]] | None = None,
) -> bool:
    present, raw = effective_configuration_value(
        target, {"send_page_view", "sendPageView"}, operations, path
    )
    if not present:
        return True
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str) and raw.casefold() in {"true", "false"}:
        return raw.casefold() == "true"
    raise RunValidationError(f"{path}.send_page_view must resolve to a boolean")


def resolve_constant_reference(value: Any, operations: dict[str, dict[str, Any]], path: str) -> Any:
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
    target = effective_target(operation, path)
    if normalized_token(str(target.get("type", ""))) not in {"c", "constant"}:
        raise RunValidationError(f"{path} destination reference must use a Constant variable")
    present, resolved = configuration_value(target, {"value"})
    if not present or not isinstance(resolved, str) or not resolved.strip():
        raise RunValidationError(f"{path} Constant variable has no literal value")
    return resolved.strip()


def configured_destinations(
    target: dict[str, Any],
    operations: dict[str, dict[str, Any]],
    path: str,
) -> set[str]:
    candidates: set[str] = set()
    present, value = configuration_value(
        target,
        {
            "tag_id",
            "tagId",
            "measurement_id",
            "measurementId",
            "measurementIdOverride",
            "destination_id",
            "destinationId",
        },
    )
    if present and isinstance(value, str):
        candidates.add(resolve_constant_reference(value, operations, path))
    for collection_name in {"destinations", "destination_ids", "destinationIds"}:
        collection_present, collection = configuration_value(target, {collection_name})
        if not collection_present:
            continue
        if not isinstance(collection, list):
            collection = [collection]
        for item in collection:
            if isinstance(item, str):
                candidates.add(resolve_constant_reference(item, operations, path))
            elif isinstance(item, dict):
                for key in ("id", "value", "destinationId", "measurementId"):
                    candidate = item.get(key)
                    if isinstance(candidate, str):
                        candidates.add(resolve_constant_reference(candidate, operations, path))
    return candidates


def resolved_event_parameter(owner, operations, variables, field):
    """Use associated Google-tag defaults only for an absent event-level field."""
    event_fields = effective_collection_fields(effective_target(owner, "native mapping"), variables)
    if field in event_fields:
        return event_fields[field]
    base = associated_google_tag(owner, operations)
    return effective_collection_fields(base or {}, variables)[field]


def associated_google_tag(
    owner: dict[str, Any], operations: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Resolve one active same-target Google tag from native destination identity.

    Unresolved or ambiguous associations cannot contribute inherited parameters.
    This is configuration proof only, not proof of initialization or evaluation time.
    """
    scoped = {
        item["object_key"]: item
        for item in operations
        if item.get("target_id") == owner.get("target_id")
        and item.get("action") not in NON_EXECUTING_TAG_ACTIONS
    }
    path = f"native mapping {owner.get('object_key')}"
    try:
        destinations = configured_destinations(effective_target(owner, path), scoped, path)
    except ValueError:
        return None
    if len(destinations) != 1 or any("{{" in value or "}}" in value for value in destinations):
        return None
    bases = []
    for item in scoped.values():
        if (item.get("resource_family") or item.get("object_type")) != "tag":
            continue
        target = effective_target(item, path)
        if target.get("type") != "googtag" or target.get("paused") is True:
            continue
        try:
            if destinations <= configured_destinations(target, scoped, path):
                bases.append(target)
        except ValueError:
            continue
    return bases[0] if len(bases) == 1 else None


def configured_transport_endpoint(
    operation: dict[str, Any],
    operations: dict[str, dict[str, Any]],
    path: str,
) -> str | None:
    target = effective_target(operation, path)
    present, value = effective_configuration_value(
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
    resolved = resolve_constant_reference(value, operations, path)
    if not isinstance(resolved, str) or not resolved.strip():
        raise RunValidationError(f"{path} transport endpoint must resolve to a non-empty string")
    return normalize_transport_endpoint(resolved, path)


def normalize_transport_endpoint(value: str, path: str) -> str:
    endpoint = value.strip().rstrip("/")
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise RunValidationError(
            f"{path} transport endpoint must be an absolute credential-free HTTPS URL"
        )
    return endpoint


def validate_google_destination(
    target: dict[str, Any],
    destination: str,
    path: str,
    operations: dict[str, dict[str, Any]] | None = None,
) -> None:
    operations = operations or {}
    candidates = configured_destinations(target, operations, path)
    if destination not in candidates:
        raise RunValidationError(f"{path} does not bind destination {destination!r}")


def resolved_trigger_types(
    operations: dict[str, dict[str, Any]],
    baseline_trigger_types: dict[str, str],
) -> dict[str, str]:
    resolved = {**baseline_trigger_types, **BUILT_IN_TRIGGER_TYPES}
    for operation in operations.values():
        if (
            operation["object_type"] != "trigger"
            or operation["action"] in NON_EXECUTING_TAG_ACTIONS
        ):
            continue
        target = effective_target(operation, f"operation {operation['operation_id']}")
        resolved[operation["object_key"]] = _normalized_trigger_type(
            target.get("type"),
            f"operation {operation['operation_id']}.intended.type",
        )
    return resolved


def trigger_filter_predicates(
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
        for index, raw in enumerate(array(rows, f"{path}.{field}")):
            row_path = f"{path}.{field}[{index}]"
            row = object(raw, row_path)
            operator = text(row.get("type"), f"{row_path}.type")
            parameters: dict[str, Any] = {}
            for entry in array(row.get("parameter"), f"{row_path}.parameter"):
                entry = object(entry, f"{row_path}.parameter[]")
                key = text(entry.get("key"), f"{row_path}.parameter[].key")
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
                    (
                        canonical_sha256({"type": operator, "parameters": parameters}),
                        negate,
                    )
                )
                continue
            signature = canonical_sha256({"type": operator, "parameters": parameters})
            predicates[(signature, negate)] = row_path
    return predicates, event_context


def resolved_mapping_value(owner, operations, variables, mapping):
    """Read only the native namespace authorized by this mapping."""
    field = mapping["destination_field"]
    if mapping["field_scope"] == "configuration":
        fields = effective_collection_fields(
            effective_target(owner, "$.mapping.owner"), variables, namespace="configuration"
        )
        if field not in fields:
            raise FieldResolutionError(f"configuration field {field!r} is absent")
        return fields[field]
    return resolved_event_parameter(owner, operations, variables, field)
