#!/usr/bin/env python3
"""Validate the versioned configure-gtm operational configuration contract."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from strict_json import StrictJsonError, load_json

SCHEMA_VERSION = "5.0"
LEGACY_SCHEMA_VERSIONS = {"4.0"}
ROUTES = {"analytics", "media", "consent", "combined"}
REQUIREMENT_KINDS = {"analytics", "media", "consent"}
EVIDENCE_GRADES = {
    "approved-input",
    "official-current",
    "container-confirmed",
    "contract-sample",
}
ACTIONS = {
    "create",
    "update",
    "replace",
    "rename",
    "pause",
    "unpause",
    "reuse",
    "untouched",
    "remove",
}
LEGACY_ACTIONS = ACTIONS - {"replace"}
DELTA_ACTIONS = {"update", "replace", "rename", "pause", "unpause", "remove"}
MUTATING_ACTIONS = {"create", *DELTA_ACTIONS}
EXISTING_OBJECT_ACTIONS = {"reuse", "untouched", *DELTA_ACTIONS}
MUTATION_AUTHORITY_GRADES = {"approved-input", "official-current"}
TOP_LEVEL_KEYS = {
    "schema_version",
    "route",
    "scope",
    "requirements",
    "implementation",
    "evidence",
    "external_dependencies",
}
IMPLEMENTATION_ONLY_REQUIREMENT_KEYS = {
    "workspace",
    "tag_type",
    "template",
    "template_version",
    "gtm_variable",
    "trigger",
    "trigger_id",
    "blocking_trigger",
    "folder",
    "fingerprint",
    "object_id",
    "object_actions",
    "consent_settings",
    "adapter_fields",
}
SEMANTIC_FIELD_MAPS = {"parameters", "user_properties", "item_parameters"}
V4_HIGH_IMPACT_TYPE_KEYS = {
    "zone",
    "environment",
    "destination",
    "destinationlink",
    "containersetting",
}
HIGH_IMPACT_TYPE_KEYS = {
    *V4_HIGH_IMPACT_TYPE_KEYS,
    "googletagconfiguration",
    "template",
}
OBJECT_RESOURCE_FAMILIES = {
    "built-in variable",
    "container setting",
    "destination",
    "environment",
    "folder",
    "google tag configuration",
    "tag",
    "template",
    "trigger",
    "variable",
    "workspace",
    "zone",
}


class ContractValidationError(ValueError):
    """Raised when a configuration contract violates its declared authority boundary."""

    def __init__(self, message: str, *, error_code: str = "invalid_contract") -> None:
        super().__init__(message)
        self.error_code = error_code


def _require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractValidationError(f"{path} must be an object")
    return value


def _require_array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractValidationError(f"{path} must be an array")
    return value


def _require_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{path} must be a non-empty string")
    return value.strip()


def _validate_provenance(
    value: Any,
    *,
    path: str,
    route: str,
) -> None:
    provenance = _require_object(value, path)
    grade = _require_text(provenance.get("grade"), f"{path}.grade")
    if grade not in EVIDENCE_GRADES:
        raise ContractValidationError(f"{path}.grade has unsupported value {grade!r}")
    _require_text(provenance.get("locator"), f"{path}.locator")
    if route == "analytics" and grade != "approved-input":
        raise ContractValidationError(
            f"{path}.grade must be 'approved-input' for analytics collection fields"
        )
    if route in {"media", "combined"} and grade not in {"approved-input", "official-current"}:
        raise ContractValidationError(f"{path}.grade cannot authorize a media destination field")


def _validate_source_authority(value: Any, *, path: str) -> None:
    authority = _require_object(value, path)
    grade = _require_text(authority.get("grade"), f"{path}.grade")
    if grade != "approved-input":
        raise ContractValidationError(f"{path}.grade must be 'approved-input' for a source")
    _require_text(authority.get("locator"), f"{path}.locator")


def _validate_requirement(
    raw: Any,
    *,
    index: int,
    route: str,
    require_field_shapes: bool,
) -> str:
    path = f"$.requirements[{index}]"
    requirement = _require_object(raw, path)
    requirement_id = _require_text(requirement.get("id"), f"{path}.id")

    forbidden = sorted(set(requirement) & IMPLEMENTATION_ONLY_REQUIREMENT_KEYS)
    if forbidden:
        raise ContractValidationError(
            f"{path} contains implementation-only key(s): {', '.join(forbidden)}"
        )

    authority = _require_object(requirement.get("authority"), f"{path}.authority")
    grade = _require_text(authority.get("grade"), f"{path}.authority.grade")
    if grade != "approved-input":
        raise ContractValidationError(f"{path}.authority.grade must be 'approved-input'")
    _require_text(authority.get("locator"), f"{path}.authority.locator")

    if route == "combined":
        effective_route = _require_text(requirement.get("kind"), f"{path}.kind")
        if effective_route not in REQUIREMENT_KINDS:
            raise ContractValidationError(f"{path}.kind has unsupported value {effective_route!r}")
    else:
        effective_route = route
        if "kind" in requirement:
            declared_kind = _require_text(requirement["kind"], f"{path}.kind")
            if declared_kind != route:
                raise ContractValidationError(
                    f"{path}.kind must match the top-level route {route!r}"
                )

    for field_map_name in sorted(SEMANTIC_FIELD_MAPS & set(requirement)):
        field_map = _require_object(requirement[field_map_name], f"{path}.{field_map_name}")
        for field_name, raw_field in field_map.items():
            _require_text(field_name, f"{path}.{field_map_name} key")
            field = _require_object(raw_field, f"{path}.{field_map_name}.{field_name}")
            if "provenance" not in field:
                raise ContractValidationError(
                    f"{path}.{field_map_name}.{field_name} is missing provenance"
                )
            _validate_provenance(
                field["provenance"],
                path=f"{path}.{field_map_name}.{field_name}.provenance",
                route=effective_route,
            )
            if not require_field_shapes:
                continue
            _require_text(
                field.get("destination_shape"),
                f"{path}.{field_map_name}.{field_name}.destination_shape",
            )
            has_source = "source" in field
            has_literal = "literal" in field
            if has_source and has_literal:
                raise ContractValidationError(
                    f"{path}.{field_map_name}.{field_name} cannot define both source and literal"
                )
            if has_source:
                _require_text(
                    field["source"],
                    f"{path}.{field_map_name}.{field_name}.source",
                )
            if has_literal and field["literal"] is None:
                raise ContractValidationError(
                    f"{path}.{field_map_name}.{field_name}.literal must not be null"
                )
            if has_source or has_literal:
                _require_text(
                    field.get("source_shape"),
                    f"{path}.{field_map_name}.{field_name}.source_shape",
                )
                source_authority = field.get("source_authority")
                if source_authority is None:
                    provenance = _require_object(
                        field["provenance"],
                        f"{path}.{field_map_name}.{field_name}.provenance",
                    )
                    if provenance.get("grade") == "approved-input":
                        source_authority = provenance
                if source_authority is None:
                    raise ContractValidationError(
                        f"{path}.{field_map_name}.{field_name}.source_authority is required "
                        "when destination provenance does not authorize the source"
                    )
                _validate_source_authority(
                    source_authority,
                    path=f"{path}.{field_map_name}.{field_name}.source_authority",
                )
            elif "source_authority" in field:
                raise ContractValidationError(
                    f"{path}.{field_map_name}.{field_name}.source_authority requires source or literal"
                )
            elif "source_shape" in field and field["source_shape"] is not None:
                raise ContractValidationError(
                    f"{path}.{field_map_name}.{field_name}.source_shape requires source or literal"
                )
    return requirement_id


def _validate_evidence(raw: Any, *, index: int) -> str:
    path = f"$.evidence[{index}]"
    evidence = _require_object(raw, path)
    grade = _require_text(evidence.get("grade"), f"{path}.grade")
    if grade not in EVIDENCE_GRADES:
        raise ContractValidationError(f"{path}.grade has unsupported value {grade!r}")
    _require_text(evidence.get("locator"), f"{path}.locator")
    if grade == "official-current":
        url = _require_text(evidence.get("url"), f"{path}.url")
        parsed_url = urlparse(url)
        if parsed_url.scheme != "https" or not parsed_url.netloc:
            raise ContractValidationError(f"{path}.url must be an absolute HTTPS URL")
        _require_text(evidence.get("title"), f"{path}.title")
        access_date = _require_text(evidence.get("access_date"), f"{path}.access_date")
        try:
            parsed_date = date.fromisoformat(access_date)
        except ValueError as exc:
            raise ContractValidationError(f"{path}.access_date must use YYYY-MM-DD") from exc
        if parsed_date.isoformat() != access_date:
            raise ContractValidationError(f"{path}.access_date must use YYYY-MM-DD")
    return grade


def _is_high_impact(object_type: str, *, type_keys: set[str] = HIGH_IMPACT_TYPE_KEYS) -> bool:
    normalized = "".join(character for character in object_type.lower() if character.isalnum())
    return normalized in type_keys or "customtemplatecode" in normalized


def _normalize_identity_part(value: str) -> str:
    return " ".join(value.split()).casefold()


def _validate_v4_object_action(raw: Any, *, index: int) -> None:
    """Validate the historical v4 object-action rules without applying v5 tightening."""
    path = f"$.implementation.objects[{index}]"
    item = _require_object(raw, path)
    action = _require_text(item.get("action"), f"{path}.action")
    if action not in LEGACY_ACTIONS:
        raise ContractValidationError(f"{path}.action has unsupported value {action!r}")
    object_type = _require_text(item.get("object_type"), f"{path}.object_type")
    _require_text(item.get("name"), f"{path}.name")
    _require_text(item.get("justification"), f"{path}.justification")

    evidence = _require_array(item.get("evidence"), f"{path}.evidence")
    if not evidence:
        raise ContractValidationError(f"{path}.evidence must not be empty")
    for evidence_index, grade in enumerate(evidence):
        value = _require_text(grade, f"{path}.evidence[{evidence_index}]")
        if value not in EVIDENCE_GRADES:
            raise ContractValidationError(
                f"{path}.evidence[{evidence_index}] has unsupported value {value!r}"
            )

    if action in {"update", "rename", "pause", "unpause"} and "pre_change" not in item:
        raise ContractValidationError(f"{path}.pre_change is required for {action}")
    if action == "rename":
        _require_text(item.get("new_name"), f"{path}.new_name")
    if action == "remove" and item.get("destructive_authorization") is not True:
        raise ContractValidationError(f"{path}.destructive_authorization must be true for remove")
    if action in MUTATING_ACTIONS and _is_high_impact(
        object_type, type_keys=V4_HIGH_IMPACT_TYPE_KEYS
    ):
        if item.get("explicit_authority") is not True:
            raise ContractValidationError(
                f"{path}.explicit_authority must be true for high-impact {object_type!r}"
            )


def _validate_object_action(
    raw: Any,
    *,
    index: int,
    requirement_ids: set[str],
) -> tuple[str, str, str, str | None, str | None]:
    path = f"$.implementation.objects[{index}]"
    item = _require_object(raw, path)
    action = _require_text(item.get("action"), f"{path}.action")
    if action not in ACTIONS:
        raise ContractValidationError(f"{path}.action has unsupported value {action!r}")
    object_type = _require_text(item.get("object_type"), f"{path}.object_type")
    if object_type not in OBJECT_RESOURCE_FAMILIES:
        supported = ", ".join(sorted(OBJECT_RESOURCE_FAMILIES))
        raise ContractValidationError(
            f"{path}.object_type must be a canonical GTM resource family: {supported}"
        )
    name = _require_text(item.get("name"), f"{path}.name")
    _require_text(item.get("justification"), f"{path}.justification")

    if "requirement_ids" in item:
        linked_ids = _require_array(item["requirement_ids"], f"{path}.requirement_ids")
        normalized_ids = {_require_text(value, f"{path}.requirement_ids[]") for value in linked_ids}
        if len(normalized_ids) != len(linked_ids):
            raise ContractValidationError(f"{path}.requirement_ids contains duplicate IDs")
        unknown_ids = sorted(normalized_ids - requirement_ids)
        if unknown_ids:
            raise ContractValidationError(
                f"{path}.requirement_ids contains unknown requirement IDs: {', '.join(unknown_ids)}"
            )

    evidence = _require_array(item.get("evidence"), f"{path}.evidence")
    if not evidence:
        raise ContractValidationError(f"{path}.evidence must not be empty")
    evidence_grades: set[str] = set()
    for evidence_index, grade in enumerate(evidence):
        value = _require_text(grade, f"{path}.evidence[{evidence_index}]")
        if value not in EVIDENCE_GRADES:
            raise ContractValidationError(
                f"{path}.evidence[{evidence_index}] has unsupported value {value!r}"
            )
        evidence_grades.add(value)

    if evidence_grades == {"contract-sample"}:
        raise ContractValidationError(
            f"{path}.evidence cannot use 'contract-sample' as sole action evidence"
        )
    if action in MUTATING_ACTIONS and not evidence_grades & MUTATION_AUTHORITY_GRADES:
        raise ContractValidationError(
            f"{path}.evidence needs 'approved-input' or 'official-current' for {action}"
        )
    if action in EXISTING_OBJECT_ACTIONS and "container-confirmed" not in evidence_grades:
        raise ContractValidationError(
            f"{path}.evidence needs 'container-confirmed' for existing-object action {action}"
        )

    if action in DELTA_ACTIONS:
        pre_change = _require_object(item.get("pre_change"), f"{path}.pre_change")
        if not pre_change:
            raise ContractValidationError(f"{path}.pre_change must not be empty for {action}")

    new_name: str | None = None
    if action == "rename":
        new_name = _require_text(item.get("new_name"), f"{path}.new_name")
        if _normalize_identity_part(new_name) == _normalize_identity_part(name):
            raise ContractValidationError(f"{path}.new_name must differ from the current name")
    if action in {"remove", "replace"} and item.get("destructive_authorization") is not True:
        raise ContractValidationError(f"{path}.destructive_authorization must be true for {action}")
    if action == "replace":
        _require_text(item.get("replacement_reason"), f"{path}.replacement_reason")
        intended = _require_object(item.get("intended"), f"{path}.intended")
        if not intended:
            raise ContractValidationError(f"{path}.intended must not be empty for replace")
    if action in {"create", "update", "rename", "pause", "unpause", "remove"} and _is_high_impact(
        object_type
    ):
        if item.get("explicit_authority") is not True:
            raise ContractValidationError(
                f"{path}.explicit_authority must be true for high-impact {object_type!r}"
            )
    object_id: str | None = None
    if "object_id" in item:
        object_id = _require_text(item["object_id"], f"{path}.object_id")
    if action == "replace" and object_id is None:
        raise ContractValidationError(f"{path}.object_id is required for replace")
    return action, object_type, name, object_id, new_name


def _validate_object_action_conflicts(
    records: list[tuple[str, str, str, str | None, str | None]],
) -> None:
    claimed: dict[tuple[str, str, str], tuple[int, str]] = {}
    for index, (action, object_type, name, object_id, new_name) in enumerate(records):
        normalized_type = _normalize_identity_part(object_type)
        identities = [("name", normalized_type, _normalize_identity_part(name))]
        if object_id is not None:
            identities.append(("id", normalized_type, object_id))
        if new_name is not None:
            identities.append(("name", normalized_type, _normalize_identity_part(new_name)))

        for identity in identities:
            previous = claimed.get(identity)
            if previous is not None:
                previous_index, previous_action = previous
                identity_value = identity[2]
                raise ContractValidationError(
                    "$.implementation.objects contains duplicate or contradictory actions "
                    f"for {object_type!r} identity {identity_value!r}: "
                    f"index {previous_index} {previous_action!r} and index {index} {action!r}"
                )
            claimed[identity] = (index, action)


def _validate_object_dependencies(objects: list[Any]) -> None:
    """Require dependency edges to use stable canonical object keys."""
    keys: list[str] = []
    for index, raw in enumerate(objects):
        path = f"$.implementation.objects[{index}]"
        item = _require_object(raw, path)
        object_type = _require_text(item.get("object_type"), f"{path}.object_type")
        name = _require_text(item.get("name"), f"{path}.name")
        keys.append(f"{object_type}::{name}")

    known = set(keys)
    dependency_map: dict[str, list[str]] = {}
    for index, raw in enumerate(objects):
        path = f"$.implementation.objects[{index}]"
        item = _require_object(raw, path)
        dependencies = _require_array(item.get("dependencies", []), f"{path}.dependencies")
        normalized = [_require_text(value, f"{path}.dependencies[]") for value in dependencies]
        if len(set(normalized)) != len(normalized):
            raise ContractValidationError(f"{path}.dependencies contains duplicate keys")
        object_key = keys[index]
        if object_key in normalized:
            raise ContractValidationError(f"{path}.dependencies cannot contain its own object key")
        unknown = sorted(set(normalized) - known)
        if unknown:
            raise ContractValidationError(
                f"{path}.dependencies contains unknown canonical object keys: " + ", ".join(unknown)
            )
        dependency_map[object_key] = normalized

    state: dict[str, int] = {}
    for root in keys:
        if state.get(root) == 2:
            continue
        stack: list[tuple[str, bool]] = [(root, False)]
        while stack:
            object_key, exiting = stack.pop()
            if exiting:
                state[object_key] = 2
                continue
            current = state.get(object_key, 0)
            if current == 2:
                continue
            if current == 1:
                raise ContractValidationError(
                    f"$.implementation.objects dependency cycle includes {object_key!r}"
                )
            state[object_key] = 1
            stack.append((object_key, True))
            for dependency in reversed(dependency_map[object_key]):
                if state.get(dependency) == 1:
                    raise ContractValidationError(
                        f"$.implementation.objects dependency cycle includes {dependency!r}"
                    )
                if state.get(dependency) != 2:
                    stack.append((dependency, False))


def validate_document(value: Any, *, allow_legacy: bool = False) -> dict[str, Any]:
    """Validate a v5 mutation contract; optionally accept an explicit historical v4 contract."""
    contract = _require_object(value, "$")
    if "schema_version" not in contract:
        raise ContractValidationError(
            "$.schema_version is required; unversioned comparison inputs cannot authorize mutation"
        )

    schema_version = contract.get("schema_version")
    is_legacy_v4 = schema_version in LEGACY_SCHEMA_VERSIONS
    if schema_version != SCHEMA_VERSION and not (allow_legacy and is_legacy_v4):
        if is_legacy_v4:
            raise ContractValidationError(
                f"$.schema_version {schema_version!r} is legacy; migrate to {SCHEMA_VERSION!r} "
                "or rerun with --allow-legacy"
            )
        raise ContractValidationError(
            f"$.schema_version must be {SCHEMA_VERSION!r}, got {schema_version!r}"
        )
    unexpected = sorted(set(contract) - TOP_LEVEL_KEYS)
    if unexpected:
        raise ContractValidationError(f"unexpected top-level key(s): {', '.join(unexpected)}")
    missing = sorted(TOP_LEVEL_KEYS - set(contract))
    if missing:
        raise ContractValidationError(f"missing top-level key(s): {', '.join(missing)}")

    route = _require_text(contract["route"], "$.route")
    if route not in ROUTES:
        raise ContractValidationError(f"$.route has unsupported value {route!r}")

    scope = _require_object(contract["scope"], "$.scope")
    scope_sets: dict[str, set[str]] = {}
    for field in ("included", "reference_only", "excluded"):
        values = _require_array(scope.get(field), f"$.scope.{field}")
        normalized = {_require_text(value, f"$.scope.{field}[]") for value in values}
        if len(normalized) != len(values):
            raise ContractValidationError(f"$.scope.{field} contains duplicate IDs")
        scope_sets[field] = normalized
    for left, right in (
        ("included", "reference_only"),
        ("included", "excluded"),
        ("reference_only", "excluded"),
    ):
        overlap = sorted(scope_sets[left] & scope_sets[right])
        if overlap:
            raise ContractValidationError(
                f"$.scope.{left} and $.scope.{right} overlap: {', '.join(overlap)}"
            )
    included_ids = scope_sets["included"]

    requirements = _require_array(contract["requirements"], "$.requirements")
    requirement_ids: set[str] = set()
    for index, raw in enumerate(requirements):
        requirement_id = _validate_requirement(
            raw,
            index=index,
            route=route,
            require_field_shapes=not is_legacy_v4,
        )
        if requirement_id in requirement_ids:
            raise ContractValidationError(f"duplicate requirement id {requirement_id!r}")
        requirement_ids.add(requirement_id)
    if requirement_ids != included_ids:
        raise ContractValidationError(
            "$.scope.included must equal the IDs represented in $.requirements"
        )

    implementation = _require_object(contract["implementation"], "$.implementation")
    workspace = _require_object(implementation.get("workspace"), "$.implementation.workspace")
    for field in ("account_id", "container_id", "id"):
        _require_text(workspace.get(field), f"$.implementation.workspace.{field}")
    container_type = _require_text(
        workspace.get("container_type"), "$.implementation.workspace.container_type"
    )
    if container_type.lower() != "web":
        raise ContractValidationError("$.implementation.workspace.container_type must be 'web'")
    objects = _require_array(implementation.get("objects"), "$.implementation.objects")
    if is_legacy_v4:
        for index, raw in enumerate(objects):
            _validate_v4_object_action(raw, index=index)
    else:
        object_action_records = []
        for index, raw in enumerate(objects):
            object_action_records.append(
                _validate_object_action(
                    raw,
                    index=index,
                    requirement_ids=requirement_ids,
                )
            )
        _validate_object_action_conflicts(object_action_records)
        _validate_object_dependencies(objects)

    evidence = _require_array(contract["evidence"], "$.evidence")
    grades = {_validate_evidence(raw, index=index) for index, raw in enumerate(evidence)}
    for required_grade in ("official-current", "container-confirmed"):
        if required_grade not in grades:
            raise ContractValidationError(
                f"$.evidence needs at least one {required_grade!r} record"
            )

    _require_array(contract["external_dependencies"], "$.external_dependencies")
    return contract


def load_contract(path: Path, *, allow_legacy: bool = False) -> dict[str, Any]:
    try:
        value = load_json(path)
    except StrictJsonError as exc:
        raise ContractValidationError(str(exc), error_code=exc.error_code) from exc
    return validate_document(value, allow_legacy=allow_legacy)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a configure-gtm v5 contract.")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--allow-legacy", action="store_true")
    args = parser.parse_args()

    try:
        value = load_contract(args.contract, allow_legacy=args.allow_legacy)
    except ContractValidationError as exc:
        print(json.dumps({"pass": False, "error_code": exc.error_code, "error": str(exc)}))
        return 2

    print(json.dumps({"pass": True, "schema_version": value.get("schema_version", "legacy")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
