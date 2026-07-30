#!/usr/bin/env python3
"""Normalize and compare intended versus saved GTM object graphs read-only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT_METADATA_KEYS = {
    "accountId",
    "containerId",
    "workspaceId",
    "path",
    "fingerprint",
    "tagManagerUrl",
    "tagId",
    "triggerId",
    "variableId",
    "folderId",
    "templateId",
    "zoneId",
    "environmentId",
    "created_at",
    "updated_at",
    "createdAt",
    "updatedAt",
    "_meta",
}
SET_LIKE_KEYS = {"firingTriggerId", "blockingTriggerId"}
ID_FIELDS = {
    "tagId": "tag",
    "triggerId": "trigger",
    "variableId": "variable",
    "folderId": "folder",
    "templateId": "template",
    "zoneId": "zone",
    "environmentId": "environment",
}
REFERENCE_FIELDS = {
    "firingTriggerId": "triggerId",
    "blockingTriggerId": "triggerId",
    "parentFolderId": "folderId",
}
SEQUENCING_KEYS = {"setupTag", "teardownTag"}


class GraphError(ValueError):
    """Raised when an object graph cannot be normalized safely."""


def _canonical(
    value: Any,
    *,
    parent_key: str | None = None,
    path: str = "$",
    parameter_array_mode: str | None = None,
) -> Any:
    if isinstance(value, dict):
        parameter_type = value.get("type")
        output: dict[str, Any] = {}
        for key in sorted(value):
            child_mode = None
            if key == "parameter":
                child_mode = "keyed"
            elif key == "map" and parameter_type == "map":
                child_mode = "keyed"
            elif key == "list" and parameter_type == "list":
                child_mode = "ordered"
            output[key] = _canonical(
                value[key],
                parent_key=key,
                path=f"{path}.{key}",
                parameter_array_mode=child_mode,
            )
        return output
    if isinstance(value, list):
        normalized = []
        parameter_keys: set[str] = set()
        for index, raw_item in enumerate(value):
            item = raw_item
            if parameter_array_mode in {"keyed", "ordered"}:
                if not isinstance(item, dict):
                    raise GraphError(f"{path}[{index}] must be a GTM Parameter object")
                if parameter_array_mode == "ordered":
                    item = {key: child for key, child in item.items() if key != "key"}
                else:
                    key = item.get("key")
                    if not isinstance(key, str) or not key.strip():
                        raise GraphError(f"{path}[{index}].key must be a non-empty string")
                    if key in parameter_keys:
                        raise GraphError(f"{path} contains duplicate GTM Parameter key {key!r}")
                    parameter_keys.add(key)
            normalized.append(
                _canonical(
                    item,
                    path=f"{path}[{index}]",
                )
            )
        if parameter_array_mode == "keyed":
            return sorted(
                normalized,
                key=lambda item: (
                    item["key"],
                    json.dumps(item, sort_keys=True),
                ),
            )
        if parent_key in SET_LIKE_KEYS:
            return sorted(
                normalized,
                key=lambda item: json.dumps(item, sort_keys=True),
            )
        return normalized
    return value


def _identity(item: dict[str, Any], path: str) -> tuple[str, str]:
    object_type = item.get("object_type")
    name = item.get("name")
    if not isinstance(object_type, str) or not object_type.strip():
        raise GraphError(f"{path} needs a non-empty object_type annotation")
    if not isinstance(name, str) or not name.strip():
        raise GraphError(f"{path} needs a non-empty name")
    return object_type.strip(), name.strip()


def _normalized_object_type(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _reference_maps(
    objects: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, str]], dict[str, set[str]]]:
    maps = {field: {} for field in ID_FIELDS}
    identities = {semantic_type: set() for semantic_type in ID_FIELDS.values()}
    for index, item in enumerate(objects):
        object_type, name = _identity(item, f"$.objects[{index}]")
        normalized_type = _normalized_object_type(object_type)
        if normalized_type in identities:
            identities[normalized_type].add(f"{normalized_type}::{name}")
        for field, semantic_type in ID_FIELDS.items():
            raw_id = item.get(field)
            if raw_id is None:
                continue
            if not isinstance(raw_id, str) or not raw_id.strip():
                raise GraphError(f"$.objects[{index}].{field} must be a non-empty string")
            semantic = f"{semantic_type}::{name}"
            identities[semantic_type].add(semantic)
            previous = maps[field].get(raw_id)
            if previous is not None and previous != semantic:
                raise GraphError(f"duplicate {field} {raw_id!r} for {previous!r} and {semantic!r}")
            maps[field][raw_id] = semantic
    return maps, identities


def _semantic_reference(
    value: Any,
    *,
    mapping: dict[str, str],
    identities: set[str],
    semantic_type: str,
    path: str,
) -> Any:
    if isinstance(value, str):
        translated = mapping.get(value, value)
        if translated not in identities:
            raise GraphError(
                f"{path} contains unresolved {semantic_type} reference {value!r}; "
                "include the referenced object in the graph"
            )
        return translated
    if isinstance(value, list):
        return [
            _semantic_reference(
                item,
                mapping=mapping,
                identities=identities,
                semantic_type=semantic_type,
                path=f"{path}[{index}]",
            )
            for index, item in enumerate(value)
        ]
    raise GraphError(f"{path} must be a string reference or an array of string references")


def _translate_references(
    value: Any,
    *,
    maps: dict[str, dict[str, str]],
    identities: dict[str, set[str]],
    parent_key: str | None = None,
    path: str = "$",
) -> Any:
    """Replace server IDs with semantic references and reject incomplete reference graphs."""
    if isinstance(value, dict):
        translated: dict[str, Any] = {}
        for key, item in value.items():
            if key in REFERENCE_FIELDS:
                id_field = REFERENCE_FIELDS[key]
                semantic_type = ID_FIELDS[id_field]
                translated[key] = _semantic_reference(
                    item,
                    mapping=maps[id_field],
                    identities=identities[semantic_type],
                    semantic_type=semantic_type,
                    path=f"{path}.{key}",
                )
            elif key == "tagName" and parent_key in SEQUENCING_KEYS:
                translated[key] = _semantic_reference(
                    item,
                    mapping=maps["tagId"],
                    identities=identities["tag"],
                    semantic_type="tag",
                    path=f"{path}.{key}",
                )
            else:
                translated[key] = _translate_references(
                    item,
                    maps=maps,
                    identities=identities,
                    parent_key=key,
                    path=f"{path}.{key}",
                )
        return translated
    if isinstance(value, list):
        return [
            _translate_references(
                item,
                maps=maps,
                identities=identities,
                parent_key=parent_key,
                path=f"{path}[{index}]",
            )
            for index, item in enumerate(value)
        ]
    return value


def normalize_graph(value: Any) -> dict[str, dict[str, Any]]:
    """Return semantic objects with server IDs translated in cross-object references."""
    if isinstance(value, dict):
        objects = value.get("objects")
    else:
        objects = value
    if not isinstance(objects, list):
        raise GraphError("graph must be an array or an object containing an objects array")

    raw_objects: list[dict[str, Any]] = []
    for index, raw in enumerate(objects):
        path = f"$.objects[{index}]"
        if not isinstance(raw, dict):
            raise GraphError(f"{path} must be an object")
        _identity(raw, path)
        raw_objects.append(raw)

    maps, identities = _reference_maps(raw_objects)
    normalized: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_objects):
        path = f"$.objects[{index}]"
        object_type, name = _identity(raw, path)
        key = f"{object_type}::{name}"
        if key in normalized:
            raise GraphError(f"duplicate semantic object identity {key!r}")
        cleaned = {field: value for field, value in raw.items() if field not in ROOT_METADATA_KEYS}
        cleaned["object_type"] = object_type
        cleaned["name"] = name
        normalized[key] = _canonical(
            _translate_references(
                cleaned,
                maps=maps,
                identities=identities,
                path=path,
            ),
            path=path,
        )
    return {key: normalized[key] for key in sorted(normalized)}


def differences(expected: Any, actual: Any, path: str = "$") -> list[dict[str, Any]]:
    if type(expected) is not type(actual):
        return [{"path": path, "kind": "type_mismatch", "expected": expected, "actual": actual}]
    if isinstance(expected, dict):
        output: list[dict[str, Any]] = []
        expected_keys = set(expected)
        actual_keys = set(actual)
        for key in sorted(expected_keys - actual_keys):
            output.append({"path": f"{path}.{key}", "kind": "missing", "expected": expected[key]})
        for key in sorted(actual_keys - expected_keys):
            output.append({"path": f"{path}.{key}", "kind": "extra", "actual": actual[key]})
        for key in sorted(expected_keys & actual_keys):
            output.extend(differences(expected[key], actual[key], f"{path}.{key}"))
        return output
    if isinstance(expected, list):
        if expected == actual:
            return []
        return [{"path": path, "kind": "array_mismatch", "expected": expected, "actual": actual}]
    if expected != actual:
        return [{"path": path, "kind": "value_mismatch", "expected": expected, "actual": actual}]
    return []


def compare_graphs(expected: Any, saved: Any) -> dict[str, Any]:
    normalized_expected = normalize_graph(expected)
    normalized_saved = normalize_graph(saved)
    expected_keys = set(normalized_expected)
    saved_keys = set(normalized_saved)
    field_differences: list[dict[str, Any]] = []
    for key in sorted(expected_keys & saved_keys):
        found = differences(normalized_expected[key], normalized_saved[key], f"$.objects[{key!r}]")
        if found:
            field_differences.append({"identity": key, "differences": found})
    report = {
        "pass": False,
        "missing_objects": sorted(expected_keys - saved_keys),
        "extra_objects": sorted(saved_keys - expected_keys),
        "object_differences": field_differences,
        "normalized_expected_count": len(normalized_expected),
        "normalized_saved_count": len(normalized_saved),
    }
    report["pass"] = not any(
        (report["missing_objects"], report["extra_objects"], report["object_differences"])
    )
    return report


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise GraphError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise GraphError(f"invalid JSON in {path}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare intended and saved GTM object graphs.")
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--saved", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = compare_graphs(_load(args.expected), _load(args.saved))
    except GraphError as exc:
        print(json.dumps({"pass": False, "error": str(exc)}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
