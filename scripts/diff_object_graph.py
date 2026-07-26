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
SET_LIKE_KEYS = {"firingTriggerId", "blockingTriggerId", "monitoringMetadata"}
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


def _canonical(value: Any, *, parent_key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {key: _canonical(value[key], parent_key=key) for key in sorted(value)}
    if isinstance(value, list):
        normalized = [_canonical(item) for item in value]
        if parent_key in SET_LIKE_KEYS:
            return sorted(
                normalized,
                key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True),
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


def _reference_maps(objects: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    maps = {field: {} for field in ID_FIELDS}
    for index, item in enumerate(objects):
        _, name = _identity(item, f"$.objects[{index}]")
        for field, semantic_type in ID_FIELDS.items():
            raw_id = item.get(field)
            if raw_id is None:
                continue
            if not isinstance(raw_id, str) or not raw_id.strip():
                raise GraphError(f"$.objects[{index}].{field} must be a non-empty string")
            semantic = f"{semantic_type}::{name}"
            previous = maps[field].get(raw_id)
            if previous is not None and previous != semantic:
                raise GraphError(f"duplicate {field} {raw_id!r} for {previous!r} and {semantic!r}")
            maps[field][raw_id] = semantic
    return maps


def _semantic_reference(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [_semantic_reference(item, mapping) for item in value]
    return value


def _translate_references(
    value: Any,
    *,
    maps: dict[str, dict[str, str]],
    parent_key: str | None = None,
) -> Any:
    if isinstance(value, dict):
        translated: dict[str, Any] = {}
        for key, item in value.items():
            if key in REFERENCE_FIELDS:
                translated[key] = _semantic_reference(item, maps[REFERENCE_FIELDS[key]])
            elif key == "tagName" and parent_key in SEQUENCING_KEYS:
                translated[key] = _semantic_reference(item, maps["tagId"])
            else:
                translated[key] = _translate_references(item, maps=maps, parent_key=key)
        return translated
    if isinstance(value, list):
        return [_translate_references(item, maps=maps, parent_key=parent_key) for item in value]
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

    maps = _reference_maps(raw_objects)
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
        normalized[key] = _canonical(_translate_references(cleaned, maps=maps))
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
        print(json.dumps({"pass": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
