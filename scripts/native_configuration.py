"""Read native parameter tables and resolve shared Google settings without rewriting payloads."""

from __future__ import annotations

import re
from typing import Any

from run_model_web import CONFIGURATION_FIELD_ALIASES

CONFIGURATION_SETTINGS_TYPES = {
    "gtcs",
    "googtagconfigsettings",
    "googtagconfigurationsettings",
    "googletagconfigurationsettings",
}
EVENT_SETTINGS_TYPES = {"gtes", "googtageventsettings", "googletageventsettings"}
USER_DATA_VARIABLE_TYPES = {"awec", "userprovideddata", "userprovideddatavariable"}
SETTINGS_REFERENCES = {
    "configsettingsvariable": CONFIGURATION_SETTINGS_TYPES,
    "configurationsettingsvariable": CONFIGURATION_SETTINGS_TYPES,
    "eventsettingsvariable": EVENT_SETTINGS_TYPES,
    "inheritedeventsettings": EVENT_SETTINGS_TYPES,
}
TABLES = {"configsettingstable", "eventsettingstable", "eventparameters"}
OBJECT_METADATA = {
    "name",
    "notes",
    "fingerprint",
    "path",
    "accountId",
    "containerId",
    "workspaceId",
    "tagManagerUrl",
    "parentFolderId",
    "object_type",
    "object_id",
    "variableId",
    "triggerId",
}


class FieldResolutionError(ValueError):
    """The current native fields do not establish one effective configuration."""


def token(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def field_key(value: str) -> str:
    normalized = token(value)
    return next(
        (key for key, aliases in CONFIGURATION_FIELD_ALIASES.items() if normalized in aliases),
        normalized,
    )


def decode_parameter(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    if "value" in value:
        result = value["value"]
        if token(str(value.get("type", ""))) == "boolean" and isinstance(result, str):
            if result.casefold() in {"true", "false"}:
                return result.casefold() == "true"
        return result
    if "list" in value:
        if not isinstance(value["list"], list):
            raise FieldResolutionError("native parameter list must be an array")
        return [decode_parameter(item) for item in value["list"]]
    if "map" in value:
        result = {}
        if not isinstance(value["map"], list):
            raise FieldResolutionError("native parameter map must be an array")
        for item in value["map"]:
            if not isinstance(item, dict) or not isinstance(item.get("key"), str):
                raise FieldResolutionError("native map entry needs a key")
            if item["key"] in result:
                raise FieldResolutionError("duplicate native map key")
            result[item["key"]] = decode_parameter(item)
        return result
    return value


def local_fields(target: dict[str, Any]) -> dict[str, Any]:
    """Decode current adapter fields and native tables; ambiguous ownership is an error."""
    result = {}

    def add(key, value):
        key = field_key(key)
        if key in result:
            raise FieldResolutionError(f"duplicate or ambiguous configuration field {key!r}")
        result[key] = value

    containers = ("fields", "parameters", "configuration", "eventParameters", "parameter")
    native = target.get("parameter", [])
    native_keys = (
        {item.get("key") for item in native if isinstance(item, dict)}
        if isinstance(native, list)
        else set()
    )
    for key, value in target.items():
        if key not in containers and key not in OBJECT_METADATA:
            # Native resource IDs are numeric; a Google collection ID is a different field.
            if key != "tagId" or (key not in native_keys and not str(value).isdecimal()):
                add(key, value)
    for key in containers:
        container = target.get(key)
        if isinstance(container, dict):
            for name, value in container.items():
                add(name, value)
        elif isinstance(container, list):
            for item in container:
                if not isinstance(item, dict) or not isinstance(
                    item.get("key") or item.get("name"), str
                ):
                    raise FieldResolutionError("native parameter entry needs a key")
                name = item.get("key") or item["name"]
                if token(name) not in TABLES:
                    add(name, decode_parameter(item))
                    continue
                rows = decode_parameter(item)
                if not isinstance(rows, list):
                    raise FieldResolutionError("native settings table must contain map rows")
                for row in rows:
                    if not isinstance(row, dict):
                        raise FieldResolutionError("native settings table row must be a map")
                    pair = (
                        ("name", "value")
                        if token(name) == "eventparameters"
                        else ("parameter", "parameterValue")
                    )
                    if (
                        not isinstance(row.get(pair[0]), str)
                        or not row[pair[0]].strip()
                        or pair[1] not in row
                    ):
                        raise FieldResolutionError(
                            "native settings row needs its parameter name and value"
                        )
                    add(row[pair[0]], row[pair[1]])
    return result


def variable_name(reference: str) -> str:
    if reference.startswith("{{") and reference.endswith("}}"):
        return reference[2:-2].strip()
    if "variable::" in reference:
        return reference.split("variable::", 1)[1]
    return reference


def effective_fields(
    target: dict[str, Any],
    variables: dict[str, dict[str, Any]],
    *,
    event_settings: bool = True,
    active: tuple[str, ...] = (),
) -> dict[str, Any]:
    local = local_fields(target)
    inherited = {}
    for key, types in SETTINGS_REFERENCES.items():
        reference = local.pop(key, None)
        if reference in (None, "") or (types == EVENT_SETTINGS_TYPES and not event_settings):
            continue
        if not isinstance(reference, str):
            raise FieldResolutionError("shared settings reference must identify one variable")
        name = variable_name(reference)
        if name in active:
            raise FieldResolutionError("cyclic shared settings reference")
        settings = variables.get(name)
        if settings is None or token(str(settings.get("type", ""))) not in types:
            raise FieldResolutionError(
                "shared settings variable is unresolved or has the wrong type"
            )
        for field, value in effective_fields(
            settings, variables, event_settings=event_settings, active=(*active, name)
        ).items():
            if field in {"type"} or field in local:
                continue
            if field in inherited:
                raise FieldResolutionError(f"ambiguous shared field {field!r}")
            inherited[field] = value
    return {**inherited, **local}


def supports_native_mapping(mapping: dict, target: dict) -> bool:
    """Deterministic ordinary-field proof is limited to scalar GA4 event parameters."""
    return (
        target.get("type") == "gaawe"
        and mapping.get("field_scope") == "event-parameter"
        and (mapping.get("destination_shape") or "").startswith("scalar:")
        and mapping.get("mapping_method") != "native-template"
    )


def effective_event_parameters(
    target: dict[str, Any],
    variables: dict[str, dict[str, Any]],
    *,
    active: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Exact GA4 event names, excluding configuration controls and other namespaces.

    Read only represented native event tables and event-settings references. Local
    rows override inherited rows by exact name; configuration field aliases never apply.
    """
    local, references = {}, []
    for entry in target.get("parameter", []):
        key = entry.get("key")
        if key in {"eventSettingsVariable", "inheritedEventSettings"}:
            reference = decode_parameter(entry)
            if reference not in (None, ""):
                references.append(reference)
        elif key == "eventSettingsTable":
            rows = decode_parameter(entry)
            if not isinstance(rows, list):
                raise FieldResolutionError("native event table must contain map rows")
            for row in rows:
                if (
                    not isinstance(row, dict)
                    or not isinstance(row.get("parameter"), str)
                    or not row["parameter"].strip()
                    or "parameterValue" not in row
                ):
                    raise FieldResolutionError(
                        "native event row needs its parameter name and value"
                    )
                name = row["parameter"]
                if name in local:
                    raise FieldResolutionError(f"duplicate native event parameter {name!r}")
                local[name] = row["parameterValue"]
    inherited = {}
    for reference in references:
        if not isinstance(reference, str):
            raise FieldResolutionError("shared event settings must identify one variable")
        name = variable_name(reference)
        if name in active:
            raise FieldResolutionError("cyclic shared event settings reference")
        settings = variables.get(name)
        if settings is None or token(str(settings.get("type", ""))) not in EVENT_SETTINGS_TYPES:
            raise FieldResolutionError(
                "shared event settings are unresolved or have the wrong type"
            )
        for field, value in effective_event_parameters(
            settings, variables, active=(*active, name)
        ).items():
            if field in local:
                continue
            if field in inherited:
                raise FieldResolutionError(f"ambiguous shared event parameter {field!r}")
            inherited[field] = value
    return {**inherited, **local}


def variable_references(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(variable_references(child) for child in value.values()))
    if isinstance(value, list):
        return set().union(*(variable_references(child) for child in value))
    if isinstance(value, str):
        names = {name.strip() for name in re.findall(r"\{\{([^{}]+)\}\}", value)}
        if "variable::" in value and "{{" not in value:
            names.add(variable_name(value))
        return names
    return set()


def sensitive_fields(value: Any) -> set[str]:
    """Inspect decoded fields, including nested payloads, without scanning prose values."""
    if isinstance(value, dict):
        return {
            field_key(key)
            for key, child in value.items()
            if field_key(key) in {"userdata", "userid"} and child is not None and child != ""
        } | set().union(*(sensitive_fields(child) for child in value.values()))
    if isinstance(value, list):
        return set().union(*(sensitive_fields(child) for child in value))
    return set()


def referenced_variable_closure(value: Any, variables: dict[str, dict[str, Any]]) -> set[str]:
    """Trace represented variables, including CJS/table indirection, without evaluating code."""
    visited = set()

    def visit(name, active):
        if name in active:
            raise FieldResolutionError("cyclic variable reference")
        if name in visited:
            return
        visited.add(name)
        if name in variables:
            for child in variable_references(effective_fields(variables[name], variables)):
                visit(child, active | {name})

    for name in variable_references(value):
        visit(name, set())
    return visited


def variable_consumers(operation: dict, tags: list[dict], variables: list[dict]) -> set[str]:
    """All direct/indirect baseline consumers of a changed variable, before or after a rename."""

    def references(item):
        payload = {key: value for key, value in item.items() if key not in {"name", "notes"}}
        found = variable_references(payload)
        for key, value in local_fields(item).items():
            if key in SETTINGS_REFERENCES and isinstance(value, str) and value:
                found.add(variable_name(value))
        return found

    names = {operation["name"]}
    if operation.get("new_name"):
        names.add(operation["new_name"])
    before = operation.get("pre_change") or {}
    if isinstance(before.get("name"), str):
        names.add(before["name"])
    while True:
        additional = {
            item["name"]
            for item in variables
            if isinstance(item.get("name"), str) and references(item) & names
        }
        if additional <= names:
            break
        names.update(additional)
    return {
        item["name"]
        for item in tags
        if isinstance(item.get("name"), str) and references(item) & names
    }
