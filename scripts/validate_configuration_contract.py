#!/usr/bin/env python3
"""Validate the versioned configure-gtm operational configuration contract."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SCHEMA_VERSION = "4.0"
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
    "rename",
    "pause",
    "unpause",
    "reuse",
    "untouched",
    "remove",
}
DELTA_ACTIONS = {"update", "rename", "pause", "unpause", "remove"}
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
HIGH_IMPACT_TYPE_KEYS = {
    "zone",
    "environment",
    "destination",
    "destinationlink",
    "containersetting",
}


class ContractValidationError(ValueError):
    """Raised when a configuration contract violates the v4 authority boundary."""


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


def _validate_legacy(value: dict[str, Any]) -> None:
    _require_object(value.get("scope"), "$.scope")
    _require_array(value.get("requirements"), "$.requirements")


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


def _validate_requirement(raw: Any, *, index: int, route: str) -> str:
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


def _is_high_impact(object_type: str) -> bool:
    normalized = "".join(character for character in object_type.lower() if character.isalnum())
    return normalized in HIGH_IMPACT_TYPE_KEYS or "customtemplatecode" in normalized


def _normalize_identity_part(value: str) -> str:
    return " ".join(value.split()).casefold()


def _validate_object_action(
    raw: Any, *, index: int
) -> tuple[str, str, str, str | None, str | None]:
    path = f"$.implementation.objects[{index}]"
    item = _require_object(raw, path)
    action = _require_text(item.get("action"), f"{path}.action")
    if action not in ACTIONS:
        raise ContractValidationError(f"{path}.action has unsupported value {action!r}")
    object_type = _require_text(item.get("object_type"), f"{path}.object_type")
    name = _require_text(item.get("name"), f"{path}.name")
    _require_text(item.get("justification"), f"{path}.justification")

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
    if action == "remove" and item.get("destructive_authorization") is not True:
        raise ContractValidationError(f"{path}.destructive_authorization must be true for remove")
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


def validate_document(value: Any, *, allow_legacy: bool = False) -> dict[str, Any]:
    """Validate a v4 document; optionally accept the legacy comparator shape."""
    contract = _require_object(value, "$")
    if "schema_version" not in contract:
        if not allow_legacy:
            raise ContractValidationError("$.schema_version is required")
        _validate_legacy(contract)
        return contract

    if contract.get("schema_version") != SCHEMA_VERSION:
        raise ContractValidationError(
            f"$.schema_version must be {SCHEMA_VERSION!r}, got {contract.get('schema_version')!r}"
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
        requirement_id = _validate_requirement(raw, index=index, route=route)
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
    object_action_records = []
    for index, raw in enumerate(objects):
        object_action_records.append(_validate_object_action(raw, index=index))
    _validate_object_action_conflicts(object_action_records)

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
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContractValidationError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ContractValidationError(f"invalid JSON in {path}: {exc}") from exc
    return validate_document(value, allow_legacy=allow_legacy)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a configure-gtm v4 contract.")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--allow-legacy", action="store_true")
    args = parser.parse_args()

    try:
        value = load_contract(args.contract, allow_legacy=args.allow_legacy)
    except ContractValidationError as exc:
        print(json.dumps({"pass": False, "error": str(exc)}))
        return 2

    print(json.dumps({"pass": True, "schema_version": value.get("schema_version", "legacy")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
