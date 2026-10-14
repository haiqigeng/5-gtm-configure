#!/usr/bin/env python3
"""Compare two normalized analytics collection contracts deterministically."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from gtm_configure.comparison.json_values import differences
from gtm_configure.contract import ContractValidationError, validate_document
from gtm_configure.core.json_io import StrictJsonError, load_json
from gtm_configure.core.schemas import validate_definition
from gtm_configure.domain.requirements import validate_scope_and_requirements


class ContractError(ValueError):
    """Raised when a normalized contract does not satisfy the comparison schema."""

    def __init__(self, message: str, *, error_code: str = "invalid_contract") -> None:
        super().__init__(message)
        self.error_code = error_code


def _validate_unversioned_comparison(value: Any) -> None:
    """Validate the same approved projection used by configuration preflight."""
    if not isinstance(value, dict) or "scope" not in value or "requirements" not in value:
        raise ContractError("normalized comparison input needs explicit $.scope and $.requirements")

    def fail(message):
        raise ContractError(message)

    try:
        validate_definition(
            {"scope": value["scope"], "requirements": value["requirements"]},
            "approvedProjection",
            fail,
        )
        route = value.get(
            "route", "combined" if any("kind" in r for r in value["requirements"]) else "analytics"
        )
        validate_scope_and_requirements(value, route)
    except ValueError as exc:
        raise ContractError(str(exc)) from exc


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


def requirement_index(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index an already validated approved projection."""
    return {row["id"]: canonical(row) for row in contract["requirements"]}


def compare(approved: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    _validate_unversioned_comparison(approved)
    _validate_unversioned_comparison(candidate)
    approved_requirements = requirement_index(approved)
    candidate_requirements = requirement_index(candidate)
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
        "proof": "semantic-projection-equality",
        "source_independence_established": False,
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
