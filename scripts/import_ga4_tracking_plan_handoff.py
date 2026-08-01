#!/usr/bin/env python3
"""Import an approved GA4 tracking-plan delivery without reinterpreting its workbook."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


class HandoffError(ValueError):
    """Raised when the upstream delivery cannot authorize configuration."""


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise HandoffError(f"Cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise HandoffError(f"Expected a JSON object: {path}")
    return value


def _safe_artifact(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise HandoffError(
            f"Handoff artifact escapes the delivery directory: {relative}"
        ) from error
    return path


def verify_delivery(delivery: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    root = delivery.resolve()
    handoff = _load(root / "handoff.json")
    if handoff.get("handoff_version") != "1.0.0":
        raise HandoffError("Unsupported GA4 tracking-plan handoff version.")
    if handoff.get("skill", {}).get("name") != "ga4-tracking-plan":
        raise HandoffError("The handoff does not come from ga4-tracking-plan.")
    if handoff.get("approval", {}).get("state") != "approved":
        raise HandoffError("GTM mutation requires handoff approval.state=approved.")
    artifacts = handoff.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise HandoffError("The handoff contains no artifact inventory.")
    by_role: dict[str, Path] = {}
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise HandoffError("Invalid handoff artifact record.")
        path = _safe_artifact(root, str(artifact.get("path", "")))
        if not path.is_file():
            raise HandoffError(f"Missing handoff artifact: {path}")
        if _digest(path) != artifact.get("sha256"):
            raise HandoffError(f"Handoff hash mismatch: {path.name}")
        by_role[str(artifact.get("role", ""))] = path
    plan_path = by_role.get("canonical_tracking_plan")
    if plan_path is None:
        raise HandoffError("The handoff has no canonical_tracking_plan artifact.")
    if _digest(plan_path) != handoff.get("plan", {}).get("canonical_sha256"):
        raise HandoffError("The canonical plan hash differs from handoff.plan.canonical_sha256.")
    return handoff, _load(plan_path)


def normalized_approved_semantics(handoff: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    requirements: list[dict[str, Any]] = []
    included: list[str] = []
    for order, event in enumerate(plan.get("events", []), start=1):
        if not isinstance(event, dict):
            continue
        event_name = str(event.get("event_name", ""))
        requirement_id = f"GA4::{order:03d}::{event_name}"
        included.append(requirement_id)
        parameters: dict[str, Any] = {}
        for parameter in event.get("parameters", []):
            if not isinstance(parameter, dict):
                continue
            key = f"{parameter.get('scope')}::{parameter.get('name')}"
            provenance = {
                "grade": "approved-input",
                "locator": (
                    f"plan.json / events[{order - 1}] / parameters / "
                    f"{parameter.get('scope')}::{parameter.get('name')}"
                ),
            }
            parameters[key] = {
                "name": parameter.get("name"),
                "scope": parameter.get("scope"),
                "source": parameter.get("data_layer_path"),
                "type": parameter.get("type"),
                "source_shape": parameter.get("type"),
                "destination_shape": parameter.get("type"),
                "requirement": parameter.get("requirement"),
                **({"condition": parameter.get("condition")} if parameter.get("condition") else {}),
                "destination": parameter.get("destination"),
                "source_authority": provenance,
                "provenance": provenance,
            }
        requirements.append(
            {
                "id": requirement_id,
                "authority": {
                    "grade": "approved-input",
                    "locator": f"plan.json / events[{order - 1}]",
                },
                "event_name": event_name,
                "classification": event.get("classification"),
                "source_event": event_name,
                "trigger": event.get("trigger"),
                "journey_ids": event.get("journey_ids", []),
                "measurement_opportunity_ids": event.get("measurement_opportunity_ids", []),
                "clear_before_push": event.get("data_layer", {}).get("clear", []),
                "parameters": parameters,
            }
        )
    if not requirements:
        raise HandoffError("The canonical plan contains no event requirements.")
    return {
        "source_contract": "ga4-tracking-plan-delivery@1.0.0",
        "source_skill_version": handoff.get("skill", {}).get("version"),
        "source_plan_sha256": handoff.get("plan", {}).get("canonical_sha256"),
        "source_approval": handoff.get("approval"),
        "scope": {"included": included, "reference_only": [], "excluded": []},
        "requirements": requirements,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("delivery", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    args = parser.parse_args()
    try:
        handoff, plan = verify_delivery(args.delivery)
        result = normalized_approved_semantics(handoff, plan)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except HandoffError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
