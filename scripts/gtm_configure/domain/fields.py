"""Web fields: shared across preparation and execution."""

from __future__ import annotations

from typing import Any

import gtm_configure.core.validation as validation
import gtm_configure.domain.web_model as web_model
import gtm_configure.domain.web_native as web_native
from gtm_configure.core.schemas import field_collections, validate_definition
from gtm_configure.core.validation import (
    RunValidationError,
    array,
    object,
    optional_text,
    text,
)
from gtm_configure.domain.native import (
    NATIVE_MAPPING_SCOPES,
    direct_dlv_source,
    native_mapping_scope,
    supports_native_mapping,
    variable_name,
)
from gtm_configure.domain.shapes import collection_shape
from gtm_configure.domain.web_model import (
    EXTENDED_MAPPING_KEYS,
    MAPPING_METHODS,
    MAPPING_STATUSES,
    SHAPE_COMPATIBILITY,
)


def validate_payload_mappings(raw: Any, requirement_ids: set[str]) -> list[dict[str, Any]]:
    identities: set[tuple[str, str, str]] = set()
    records: list[dict[str, Any]] = []
    for index, item_raw in enumerate(array(raw, "$.payload_mappings")):
        path = f"$.payload_mappings[{index}]"
        item = object(item_raw, path)
        requirement_id = text(item.get("requirement_id"), f"{path}.requirement_id")
        if requirement_id not in requirement_ids:
            raise RunValidationError(f"{path}.requirement_id is unknown")
        field_scope = text(item.get("field_scope"), f"{path}.field_scope")
        if field_scope not in {
            model["payload_scope"]
            for model in field_collections().values()
            if model["payload_scope"]
        }:
            raise RunValidationError(f"{path}.field_scope has unsupported value {field_scope!r}")
        destination_field = text(item.get("destination_field"), f"{path}.destination_field")
        identity = (requirement_id, field_scope, destination_field)
        if identity in identities:
            raise RunValidationError(f"duplicate payload mapping {identity!r}")
        identities.add(identity)
        optional_text(item.get("source"), f"{path}.source")
        optional_text(item.get("gtm_resolution"), f"{path}.gtm_resolution")
        optional_text(item.get("template_field"), f"{path}.template_field")
        for shape_field in ("source_shape", "destination_shape"):
            if item.get(shape_field) is not None:
                try:
                    collection_shape(item[shape_field])
                except ValueError as exc:
                    raise RunValidationError(f"{path}.{shape_field}: {exc}") from exc
        status = text(item.get("status"), f"{path}.status")
        if field_scope == "unresolved" and status != "blocked":
            raise RunValidationError(
                f"{path}: unresolved destinations remain blocked until the approved field contract specifies a destination surface"
            )
        if status not in MAPPING_STATUSES:
            raise RunValidationError(f"{path}.status has unsupported value {status!r}")
        text(item.get("provenance_locator"), f"{path}.provenance_locator")
        extended_keys = set(item) & EXTENDED_MAPPING_KEYS
        if extended_keys and extended_keys != EXTENDED_MAPPING_KEYS:
            missing = ", ".join(sorted(EXTENDED_MAPPING_KEYS - extended_keys))
            raise RunValidationError(f"{path} is missing extended mapping key(s): {missing}")
        if extended_keys:
            authority_grade = optional_text(
                item.get("source_authority_grade"),
                f"{path}.source_authority_grade",
            )
            authority_locator = optional_text(
                item.get("source_authority_locator"),
                f"{path}.source_authority_locator",
            )
            source_shape = optional_text(item.get("source_shape"), f"{path}.source_shape")
            destination_shape = optional_text(
                item.get("destination_shape"),
                f"{path}.destination_shape",
            )
            compatibility = optional_text(
                item.get("shape_compatibility"),
                f"{path}.shape_compatibility",
            )
            method = optional_text(item.get("mapping_method"), f"{path}.mapping_method")
            missing_behavior = optional_text(
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
            text(item.get("source"), f"{path}.source")
            text(item.get("gtm_resolution"), f"{path}.gtm_resolution")
            text(item.get("template_field"), f"{path}.template_field")
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
        elif extended_keys and status in {
            "intentionally-omitted",
            "external",
            "blocked",
        }:
            if not missing_behavior:
                raise RunValidationError(f"{path}.missing_behavior is required for {status}")
        records.append(item)
    return records


def field_mappings(requirement: dict[str, Any]) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    for map_name, model in field_collections().items():
        field_scope = model["payload_scope"]
        if field_scope is None:
            continue
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
                    "missing_behavior": (
                        "An approved destination surface is required"
                        if field_scope == "unresolved"
                        else None
                    ),
                    "status": "blocked" if field_scope == "unresolved" else "pending",
                    "provenance_locator": field["provenance"]["locator"],
                }
            )
    return mappings


def fail_validation(message):
    raise validation.RunValidationError(message)


def materialize_payload_mappings(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Attach implementation decisions without rewriting approved source semantics."""
    mappings = [
        row for requirement in contract["requirements"] for row in field_mappings(requirement)
    ]
    by_key = {
        (row["requirement_id"], row["field_scope"], row["destination_field"]): row
        for row in mappings
    }
    bindings = contract["implementation"].get("field_bindings", [])
    if not isinstance(bindings, list):
        raise validation.RunValidationError("implementation.field_bindings must be an array")
    seen = set()
    for binding in bindings:
        validate_definition(binding, "fieldBinding", fail_validation)
        key = (
            binding["requirement_id"],
            binding["field_scope"],
            binding["destination_field"],
        )
        if key not in by_key or key in seen:
            raise validation.RunValidationError("field binding is unknown or duplicated")
        seen.add(key)
        by_key[key].update(binding)
    return validate_payload_mappings(mappings, {item["id"] for item in contract["requirements"]})


def validate_native_mappings(mappings, operations, fail):
    """Validate field ownership at every status, then prove supported mapped values."""
    by_key = {item.get("object_key"): item for item in operations}
    for mapping in mappings:
        binding = mapping.get("native_binding")
        if binding is None and mapping["status"] != "mapped":
            continue
        if binding is None and not any(
            mapping["requirement_id"] in item.get("requirement_ids", [])
            and supports_native_mapping(
                mapping, item.get("intended") or item.get("pre_change") or {}
            )
            for item in operations
        ):
            continue
        if binding is None:
            fail("mapped scalar native field requires native_binding object_key and field")
            continue
        validate_definition(binding, "nativeBinding", fail)
        owner = by_key.get(binding["object_key"], {})
        if (
            (owner.get("resource_family") or owner.get("object_type")) != "tag"
            or owner.get("action") in web_model.NON_EXECUTING_TAG_ACTIONS
            or mapping["requirement_id"] not in owner.get("requirement_ids", [])
        ):
            fail("native mapping owner must be an active tag for the approved requirement")
            continue
        try:
            target = owner.get("intended") or owner.get("pre_change") or {}
            if binding["field"] != mapping["destination_field"]:
                raise ValueError(
                    "native mapping field must identify the approved destination field"
                )
            if target.get("paused") is True:
                raise ValueError("native mapping owner is paused")
            scope = native_mapping_scope(target)
            if (
                scope is not None
                and mapping["field_scope"] in NATIVE_MAPPING_SCOPES.values()
                and scope != mapping["field_scope"]
            ):
                raise ValueError("native mapping owner has a different field namespace")
            if mapping["status"] != "mapped" or not supports_native_mapping(mapping, target):
                continue
            variables = {
                item["name"]: item.get("intended") or item.get("pre_change") or {}
                for item in operations
                if item.get("target_id") == owner.get("target_id")
                and (item.get("resource_family") or item.get("object_type")) == "variable"
                and item.get("action") not in web_model.NON_EXECUTING_TAG_ACTIONS
            }
            value = web_native.resolved_mapping_value(owner, operations, variables, mapping)
            if validation.canonical_sha256(value) != validation.canonical_sha256(
                mapping["gtm_resolution"]
            ):
                raise ValueError("native mapping value differs from gtm_resolution")
            if mapping.get("mapping_method") == "direct-dlv":
                if (
                    not isinstance(value, str)
                    or not value.startswith("{{")
                    or not value.endswith("}}")
                ):
                    raise ValueError("direct-dlv requires a native variable reference")
                variable = variables[variable_name(value)]
                source = direct_dlv_source(variable)
                if source != mapping["source"]:
                    raise ValueError("direct-dlv source differs from the approved source")
        except (ValueError, KeyError, TypeError) as exc:
            fail(f"native mapping {mapping['destination_field']!r} is unresolved: {exc}")
