#!/usr/bin/env python3
"""Compare two normalized analytics collection contracts deterministically."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from strict_json import StrictJsonError, load_json
from validate_configuration_contract import ContractValidationError, validate_document


class ContractError(ValueError):
    """Raised when a normalized contract does not satisfy the comparison schema."""

    def __init__(self, message: str, *, error_code: str = "invalid_contract") -> None:
        super().__init__(message)
        self.error_code = error_code


def _validate_unversioned_comparison(value: Any) -> None:
    """Accept the current normalized collection projection, never a mutation contract."""
    if not isinstance(value, dict):
        raise ContractError("unversioned comparison input must be an object")
    scope = value.get("scope")
    requirements = value.get("requirements")
    if not isinstance(scope, dict):
        raise ContractError("unversioned comparison input needs $.scope as an object")
    if not isinstance(requirements, list):
        raise ContractError("unversioned comparison input needs $.requirements as an array")


def load_contract(path: Path) -> dict[str, Any]:
    try:
        value = load_json(path)
    except StrictJsonError as exc:
        raise ContractError(str(exc), error_code=exc.error_code) from exc
    if isinstance(value, dict) and "schema_version" not in value:
        _validate_unversioned_comparison(value)
    else:
        try:
            validate_document(value)
        except ContractValidationError as exc:
            raise ContractError(f"{path}: {exc}", error_code=exc.error_code) from exc
    return value


def canonical(value: Any, *, sort_lists: bool = False) -> Any:
    """Canonicalize mappings and optionally set-like arrays without changing types."""
    if isinstance(value, dict):
        return {key: canonical(value[key], sort_lists=sort_lists) for key in sorted(value)}
    if isinstance(value, list):
        normalized = [canonical(item, sort_lists=sort_lists) for item in value]
        if sort_lists:
            return sorted(
                normalized,
                key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True),
            )
        return normalized
    return value


def requirement_index(contract: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for position, requirement in enumerate(contract["requirements"]):
        if not isinstance(requirement, dict):
            raise ContractError(f"{label}: requirement at index {position} must be an object")
        requirement_id = requirement.get("id")
        if not isinstance(requirement_id, str) or not requirement_id.strip():
            raise ContractError(
                f"{label}: requirement at index {position} needs a non-empty string id"
            )
        if requirement_id in index:
            raise ContractError(f"{label}: duplicate requirement id {requirement_id!r}")
        index[requirement_id] = canonical(requirement)
    return index


def differences(expected: Any, actual: Any, path: str = "$") -> list[dict[str, Any]]:
    if type(expected) is not type(actual):
        return [
            {
                "path": path,
                "kind": "type_mismatch",
                "expected": expected,
                "actual": actual,
            }
        ]
    if isinstance(expected, dict):
        output: list[dict[str, Any]] = []
        expected_keys = set(expected)
        actual_keys = set(actual)
        for key in sorted(expected_keys - actual_keys):
            output.append(
                {
                    "path": f"{path}.{key}",
                    "kind": "missing",
                    "expected": expected[key],
                }
            )
        for key in sorted(actual_keys - expected_keys):
            output.append(
                {
                    "path": f"{path}.{key}",
                    "kind": "extra",
                    "actual": actual[key],
                }
            )
        for key in sorted(expected_keys & actual_keys):
            output.extend(differences(expected[key], actual[key], f"{path}.{key}"))
        return output
    if isinstance(expected, list):
        if expected == actual:
            return []
        return [
            {
                "path": path,
                "kind": "array_mismatch",
                "expected": expected,
                "actual": actual,
            }
        ]
    if expected != actual:
        return [
            {
                "path": path,
                "kind": "value_mismatch",
                "expected": expected,
                "actual": actual,
            }
        ]
    return []


def compare(approved: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    approved_requirements = requirement_index(approved, "approved")
    candidate_requirements = requirement_index(candidate, "candidate")
    approved_ids = set(approved_requirements)
    candidate_ids = set(candidate_requirements)

    scope_mismatches = differences(
        canonical(approved["scope"], sort_lists=True),
        canonical(candidate["scope"], sort_lists=True),
        "$.scope",
    )
    requirement_mismatches = []
    for requirement_id in sorted(approved_ids & candidate_ids):
        found = differences(
            approved_requirements[requirement_id],
            candidate_requirements[requirement_id],
            f"$.requirements[{requirement_id!r}]",
        )
        if found:
            requirement_mismatches.append({"id": requirement_id, "differences": found})

    report = {
        "pass": False,
        "expected_requirement_count": len(approved_requirements),
        "actual_requirement_count": len(candidate_requirements),
        "missing_requirements": sorted(approved_ids - candidate_ids),
        "extra_requirements": sorted(candidate_ids - approved_ids),
        "scope_mismatches": scope_mismatches,
        "requirement_mismatches": requirement_mismatches,
    }
    report["pass"] = not any(
        (
            report["missing_requirements"],
            report["extra_requirements"],
            report["scope_mismatches"],
            report["requirement_mismatches"],
        )
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare normalized approved and candidate collection contracts."
    )
    parser.add_argument("--approved", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()

    try:
        report = compare(load_contract(args.approved), load_contract(args.candidate))
    except ContractError as exc:
        print(json.dumps({"pass": False, "error_code": exc.error_code, "error": str(exc)}))
        return 2

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
