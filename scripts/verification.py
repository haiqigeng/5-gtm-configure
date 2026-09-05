"""Target-scoped saved-state comparison helpers for configuration-run@4.0."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from diff_object_graph import (
    ROOT_METADATA_KEYS,
    differences,
    normalize_graph,
    semantic_references,
)
from redaction import REDACTED_STATE, is_redacted, redact_for_persistence
from run_model import VERIFICATION_SCHEMA_VERSION


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def expected_graph(operation: dict[str, Any]) -> dict[str, Any]:
    intended = deepcopy(operation.get("intended") or {})
    intended.update(
        {
            "target_id": operation["target_id"],
            "object_type": operation["resource_family"],
            "name": operation.get("new_name", operation["name"]),
        }
    )
    return {"objects": [intended]}


def _redacted_presence_projection(value: Any, *, path: str = "$") -> tuple[Any, list[str]]:
    """Project redacted fields to path-only presence evidence, never value equality."""
    if is_redacted(value):
        return {"secret_state": REDACTED_STATE, "path_only": True}, [path]
    if isinstance(value, dict):
        projected: dict[str, Any] = {}
        paths: list[str] = []
        for key, child in value.items():
            item, item_paths = _redacted_presence_projection(child, path=f"{path}.{key}")
            projected[key] = item
            paths.extend(item_paths)
        return projected, paths
    if isinstance(value, list):
        projected_items = []
        paths = []
        for index, child in enumerate(value):
            item, item_paths = _redacted_presence_projection(child, path=f"{path}[{index}]")
            projected_items.append(item)
            paths.extend(item_paths)
        return projected_items, paths
    return deepcopy(value), []


def build_verification_comparison(
    operation: dict[str, Any], saved: Any
) -> tuple[dict[str, Any], Any]:
    """Redact first, then compare one intended operation with authoritative readback."""
    safe_saved = redact_for_persistence(saved)
    if operation.get("action") == "remove":
        expected_absence = {
            "target_id": operation["target_id"],
            "object_key": operation["object_key"],
            "absent": True,
        }
        passed = saved is None
        report = {
            "pass": passed,
            "expected_absence": True,
            "saved_absence": saved is None,
            "secret_comparison": {
                "state": "absent",
                "expected_paths": [],
                "saved_paths": [],
                "value_equality_claimed": False,
                "presence_paths_match": True,
            },
        }
        return (
            {
                "schema_version": VERIFICATION_SCHEMA_VERSION,
                "method": "target-object-absence",
                "operation_id": operation["operation_id"],
                "target_id": operation["target_id"],
                "expected_sha256": canonical_sha256(expected_absence),
                "saved_sha256": canonical_sha256(safe_saved),
                "pass": passed,
                "report": report,
            },
            safe_saved,
        )
    safe_expected = redact_for_persistence(expected_graph(operation))
    target_types = {operation["target_id"]: operation.get("container_type", "web")}
    allowed_references = semantic_references(safe_expected)
    normalized_expected = normalize_graph(
        safe_expected,
        target_types=target_types,
        allowed_semantic_references=allowed_references,
    )
    normalized_saved = normalize_graph(
        safe_saved,
        target_types=target_types,
        allowed_semantic_references=allowed_references,
    )
    comparable_expected, expected_redacted_paths = _redacted_presence_projection(
        normalized_expected
    )
    comparable_saved, saved_redacted_paths = _redacted_presence_projection(normalized_saved)
    expected_keys = set(comparable_expected)
    saved_keys = set(comparable_saved)
    object_differences = []
    for key in sorted(expected_keys & saved_keys):
        found = differences(comparable_expected[key], comparable_saved[key], f"$.objects[{key!r}]")
        if found:
            object_differences.append({"identity": key, "differences": found})
    report = {
        "pass": not any(
            (expected_keys - saved_keys, saved_keys - expected_keys, object_differences)
        ),
        "missing_objects": sorted(expected_keys - saved_keys),
        "extra_objects": sorted(saved_keys - expected_keys),
        "object_differences": object_differences,
        "normalized_expected_count": len(comparable_expected),
        "normalized_saved_count": len(comparable_saved),
    }
    same_secret_presence = expected_redacted_paths == saved_redacted_paths
    report["pass"] = report["pass"] and same_secret_presence
    report["secret_comparison"] = {
        "state": REDACTED_STATE if expected_redacted_paths or saved_redacted_paths else "absent",
        "expected_paths": expected_redacted_paths,
        "saved_paths": saved_redacted_paths,
        "value_equality_claimed": False,
        "presence_paths_match": same_secret_presence,
    }
    comparison = {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "method": "target-scoped-object-graph",
        "operation_id": operation["operation_id"],
        "target_id": operation["target_id"],
        "expected_sha256": canonical_sha256(comparable_expected),
        "saved_sha256": canonical_sha256(comparable_saved),
        "pass": report["pass"],
        "report": report,
    }
    return comparison, safe_saved


def validate_verification_comparison(
    operation: dict[str, Any], comparison: Any, saved: Any
) -> dict[str, Any]:
    if not isinstance(comparison, dict):
        raise ValueError("comparison must be an object")
    required = {
        "schema_version",
        "method",
        "operation_id",
        "target_id",
        "expected_sha256",
        "saved_sha256",
        "pass",
        "report",
    }
    if set(comparison) != required:
        raise ValueError("comparison has missing or unexpected fields")
    if comparison["schema_version"] != VERIFICATION_SCHEMA_VERSION:
        raise ValueError("comparison schema_version is unsupported")
    if comparison["operation_id"] != operation["operation_id"]:
        raise ValueError("comparison operation_id does not match")
    if comparison["target_id"] != operation["target_id"]:
        raise ValueError("comparison target_id does not match")
    rebuilt, safe_saved = build_verification_comparison(operation, saved)
    if rebuilt != comparison:
        raise ValueError("comparison is not bound to the intended object and saved readback")
    secret_comparison = comparison["report"].get("secret_comparison", {})
    if secret_comparison.get("value_equality_claimed") is not False:
        raise ValueError("redacted secret fields cannot be treated as value equality")
    return comparison


_MUTABLE_OPERATION_FIELDS = {
    "state",
    "journal",
    "pre_write_readback",
    "pre_write_comparison",
    "comparison",
    "saved_readback",
}


def materialization_projection(document: dict[str, Any]) -> dict[str, Any]:
    """Return only contract-owned run data; adapters may mutate no field in this projection."""
    requirements = [
        {key: deepcopy(value) for key, value in item.items() if key != "status"}
        for item in document["requirements"]
    ]
    operations = [
        {
            key: deepcopy(value)
            for key, value in item.items()
            if key not in _MUTABLE_OPERATION_FIELDS
        }
        for item in document["object_changes"]
    ]
    targets = [
        {key: deepcopy(value) for key, value in item.items() if key != "adapter_capabilities"}
        for item in document["run"]["targets"]
    ]
    return {
        "targets": targets,
        "requirements": requirements,
        "pipelines": deepcopy(document["pipelines"]),
        "object_changes": operations,
        "payload_mappings": deepcopy(document["payload_mappings"]),
        "consent_topologies": deepcopy(document["consent_topologies"]),
        "execution_topologies": deepcopy(document["execution_topologies"]),
        "page_view_decisions": deepcopy(document["page_view_decisions"]),
        "first_party_data_routes": deepcopy(document["first_party_data_routes"]),
        "inventory_dispositions": deepcopy(document["inventory_dispositions"]),
        "dedup_contracts": deepcopy(document["dedup_contracts"]),
        "official_sources": deepcopy(document["official_sources"]),
        "external_dependencies": deepcopy(document["external_dependencies"]),
        "publication_dependencies": deepcopy(document["publication_dependencies"]),
    }


def materialization_fingerprints(document: dict[str, Any]) -> dict[str, str]:
    return {
        section: canonical_sha256(value)
        for section, value in materialization_projection(document).items()
    }


def _redacted_references(value: Any, *, path: str = "$") -> dict[str, str | None]:
    if is_redacted(value):
        reference = value.get("reference")
        return {path: reference if isinstance(reference, str) and reference.strip() else None}
    output: dict[str, str | None] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            output.update(_redacted_references(child, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            output.update(_redacted_references(child, path=f"{path}[{index}]"))
    return output


_PREWRITE_METADATA_KEYS = ROOT_METADATA_KEYS


def _subset_differences(expected: Any, actual: Any, *, path: str = "$") -> list[str]:
    if type(expected) is not type(actual):
        return [f"{path}: type differs"]
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected object"]
        differences: list[str] = []
        metadata = _PREWRITE_METADATA_KEYS if path == "$" else set()
        for key in sorted(set(actual) - set(expected) - metadata):
            differences.append(f"{path}.{key}: unexpected")
        for key, value in expected.items():
            if key not in actual:
                differences.append(f"{path}.{key}: missing")
            else:
                differences.extend(_subset_differences(value, actual[key], path=f"{path}.{key}"))
        return differences
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return [f"{path}: array length differs"]
        return [
            difference
            for index, (left, right) in enumerate(zip(expected, actual))
            for difference in _subset_differences(left, right, path=f"{path}[{index}]")
        ]
    return [] if expected == actual else [f"{path}: value differs"]


def build_pre_write_comparison(operation: dict[str, Any], saved: Any) -> tuple[dict[str, Any], Any]:
    safe_saved = redact_for_persistence(saved)
    expected = redact_for_persistence(operation.get("pre_change"))
    if isinstance(expected, dict) and "name" not in expected:
        # A GTM object's name is semantic identity, not server-generated metadata. Bind the
        # pre-write proof to the named object while still ignoring generated IDs/fingerprints.
        expected = {"name": operation["name"], **expected}
    comparable_expected, expected_paths = _redacted_presence_projection(expected)
    comparable_saved, saved_paths = _redacted_presence_projection(safe_saved)
    differences = _subset_differences(comparable_expected, comparable_saved)
    references = _redacted_references(expected)
    saved_references = _redacted_references(safe_saved)
    reference_proved = references == saved_references and all(
        reference is not None for reference in references.values()
    )
    same_secret_presence = set(expected_paths) <= set(saved_paths)
    passed = not differences and same_secret_presence and reference_proved
    comparison = {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "method": "pre-change-subset",
        "operation_id": operation["operation_id"],
        "target_id": operation["target_id"],
        "expected_sha256": canonical_sha256(comparable_expected),
        "saved_sha256": canonical_sha256(comparable_saved),
        "pass": passed,
        "differences": differences,
        "secret_comparison": {
            "state": REDACTED_STATE if expected_paths or saved_paths else "absent",
            "expected_paths": expected_paths,
            "saved_paths": saved_paths,
            "value_equality_claimed": False,
            "presence_paths_match": same_secret_presence,
            "reference_proved": reference_proved,
        },
    }
    return comparison, safe_saved
