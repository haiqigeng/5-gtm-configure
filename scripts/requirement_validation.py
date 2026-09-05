"""Approved requirement semantics shared by the current contract and web model."""

from __future__ import annotations

from typing import Any

ROUTES = {"analytics", "media", "consent", "combined"}
REQUIREMENT_KINDS = {"analytics", "media", "consent"}
EVIDENCE_GRADES = {"approved-input", "official-current", "container-confirmed", "contract-sample"}
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
DELTA_ACTIONS = {"update", "replace", "rename", "pause", "unpause", "remove"}
MUTATING_ACTIONS = {"create", *DELTA_ACTIONS}
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


class ContractValidationError(ValueError):
    def __init__(self, message: str, *, error_code: str = "invalid_contract") -> None:
        super().__init__(message)
        self.error_code = error_code


def _require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractValidationError(f"{path} must be an object")
    return value


def _require_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{path} must be a non-empty string")
    return value.strip()


def _validate_provenance(value: Any, *, path: str, route: str) -> None:
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
    if _require_text(authority.get("grade"), f"{path}.grade") != "approved-input":
        raise ContractValidationError(f"{path}.grade must be 'approved-input' for a source")
    _require_text(authority.get("locator"), f"{path}.locator")


def validate_requirement(raw: Any, *, index: int, route: str) -> str:
    path = f"$.requirements[{index}]"
    requirement = _require_object(raw, path)
    requirement_id = _require_text(requirement.get("id"), f"{path}.id")
    forbidden = sorted(set(requirement) & IMPLEMENTATION_ONLY_REQUIREMENT_KEYS)
    if forbidden:
        raise ContractValidationError(
            f"{path} contains implementation-only key(s): {', '.join(forbidden)}"
        )
    authority = _require_object(requirement.get("authority"), f"{path}.authority")
    if _require_text(authority.get("grade"), f"{path}.authority.grade") != "approved-input":
        raise ContractValidationError(f"{path}.authority.grade must be 'approved-input'")
    _require_text(authority.get("locator"), f"{path}.authority.locator")
    if route == "combined":
        effective_route = _require_text(requirement.get("kind"), f"{path}.kind")
        if effective_route not in REQUIREMENT_KINDS:
            raise ContractValidationError(f"{path}.kind has unsupported value {effective_route!r}")
    else:
        effective_route = route
        if "kind" in requirement and _require_text(requirement["kind"], f"{path}.kind") != route:
            raise ContractValidationError(f"{path}.kind must match the top-level route {route!r}")
    for map_name in sorted(SEMANTIC_FIELD_MAPS & set(requirement)):
        fields = _require_object(requirement[map_name], f"{path}.{map_name}")
        for field_name, raw_field in fields.items():
            _require_text(field_name, f"{path}.{map_name} key")
            field_path = f"{path}.{map_name}.{field_name}"
            field = _require_object(raw_field, field_path)
            if "provenance" not in field:
                raise ContractValidationError(f"{field_path} is missing provenance")
            _validate_provenance(
                field["provenance"], path=f"{field_path}.provenance", route=effective_route
            )
            _require_text(field.get("destination_shape"), f"{field_path}.destination_shape")
            has_source, has_literal = "source" in field, "literal" in field
            if has_source and has_literal:
                raise ContractValidationError(f"{field_path} cannot define both source and literal")
            if has_source:
                _require_text(field["source"], f"{field_path}.source")
            if has_literal and field["literal"] is None:
                raise ContractValidationError(f"{field_path}.literal must not be null")
            if has_source or has_literal:
                _require_text(field.get("source_shape"), f"{field_path}.source_shape")
                source_authority = field.get("source_authority")
                if (
                    source_authority is None
                    and field["provenance"].get("grade") == "approved-input"
                ):
                    source_authority = field["provenance"]
                if source_authority is None:
                    raise ContractValidationError(
                        f"{field_path}.source_authority is required when destination provenance does not authorize the source"
                    )
                _validate_source_authority(source_authority, path=f"{field_path}.source_authority")
            elif "source_authority" in field:
                raise ContractValidationError(
                    f"{field_path}.source_authority requires source or literal"
                )
            elif field.get("source_shape") is not None:
                raise ContractValidationError(
                    f"{field_path}.source_shape requires source or literal"
                )
    return requirement_id
