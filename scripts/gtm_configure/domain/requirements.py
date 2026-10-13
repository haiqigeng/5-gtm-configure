"""Approved requirement semantics shared by the current contract and web model."""

from __future__ import annotations

from typing import Any

from gtm_configure.core.contract_validation import ContractValidationError, object, text
from gtm_configure.core.model import EVIDENCE_GRADES, REQUIREMENT_KINDS
from gtm_configure.domain.shapes import collection_shape

SEMANTIC_FIELD_MAPS = {"parameters", "user_properties", "item_parameters"}


def _validate_provenance(value: Any, *, path: str, route: str) -> None:
    provenance = object(value, path)
    grade = text(provenance.get("grade"), f"{path}.grade")
    if grade not in EVIDENCE_GRADES:
        raise ContractValidationError(f"{path}.grade has unsupported value {grade!r}")
    text(provenance.get("locator"), f"{path}.locator")
    if route == "analytics" and grade != "approved-input":
        raise ContractValidationError(
            f"{path}.grade must be 'approved-input' for analytics collection fields"
        )
    if route in {"media", "combined"} and grade not in {
        "approved-input",
        "official-current",
    }:
        raise ContractValidationError(f"{path}.grade cannot authorize a media destination field")


def _validate_source_authority(value: Any, *, path: str) -> None:
    authority = object(value, path)
    if text(authority.get("grade"), f"{path}.grade") != "approved-input":
        raise ContractValidationError(f"{path}.grade must be 'approved-input' for a source")
    text(authority.get("locator"), f"{path}.locator")


def validate_requirement(raw: Any, *, index: int, route: str) -> str:
    path = f"$.requirements[{index}]"
    requirement = object(raw, path)
    requirement_id = text(requirement.get("id"), f"{path}.id")
    authority = object(requirement.get("authority"), f"{path}.authority")
    if text(authority.get("grade"), f"{path}.authority.grade") != "approved-input":
        raise ContractValidationError(f"{path}.authority.grade must be 'approved-input'")
    text(authority.get("locator"), f"{path}.authority.locator")
    if route == "combined":
        effective_route = text(requirement.get("kind"), f"{path}.kind")
        if effective_route not in REQUIREMENT_KINDS:
            raise ContractValidationError(f"{path}.kind has unsupported value {effective_route!r}")
    else:
        effective_route = route
        if "kind" in requirement and text(requirement["kind"], f"{path}.kind") != route:
            raise ContractValidationError(f"{path}.kind must match the top-level route {route!r}")
    for map_name in sorted(SEMANTIC_FIELD_MAPS & set(requirement)):
        fields = object(requirement[map_name], f"{path}.{map_name}")
        for field_name, raw_field in fields.items():
            text(field_name, f"{path}.{map_name} key")
            field_path = f"{path}.{map_name}.{field_name}"
            field = object(raw_field, field_path)
            if "provenance" not in field:
                raise ContractValidationError(f"{field_path} is missing provenance")
            _validate_provenance(
                field["provenance"],
                path=f"{field_path}.provenance",
                route=effective_route,
            )
            collection_shape(field.get("destination_shape"))
            has_source, has_literal = "source" in field, "literal" in field
            if has_source and has_literal:
                raise ContractValidationError(f"{field_path} cannot define both source and literal")
            if has_source:
                text(field["source"], f"{field_path}.source")
            if has_literal and field["literal"] is None:
                raise ContractValidationError(f"{field_path}.literal must not be null")
            if has_source or has_literal:
                collection_shape(field.get("source_shape"))
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
