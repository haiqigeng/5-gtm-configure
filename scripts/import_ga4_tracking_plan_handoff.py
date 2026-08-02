#!/usr/bin/env python3
"""Import an approved GA4 tracking-plan delivery without reinterpreting its workbook."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

from strict_json import StrictJsonError, load_json, write_json_atomic


class HandoffError(ValueError):
    """Raised when the upstream delivery cannot authorize configuration."""


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = load_json(path)
    except StrictJsonError as error:
        raise HandoffError(str(error)) from error
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
    seen_paths: set[Path] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise HandoffError("Invalid handoff artifact record.")
        path = _safe_artifact(root, str(artifact.get("path", "")))
        role = str(artifact.get("role", ""))
        if not role:
            raise HandoffError("A handoff artifact has no non-empty role.")
        if role in by_role:
            raise HandoffError(f"Duplicate handoff artifact role: {role}")
        if path in seen_paths:
            raise HandoffError(f"Duplicate handoff artifact path: {path}")
        if not path.is_file():
            raise HandoffError(f"Missing handoff artifact: {path}")
        expected_bytes = artifact.get("bytes")
        if not isinstance(expected_bytes, int) or expected_bytes < 1:
            raise HandoffError(f"Invalid handoff byte count: {path.name}")
        if path.stat().st_size != expected_bytes:
            raise HandoffError(f"Handoff byte-count mismatch: {path.name}")
        if _digest(path) != artifact.get("sha256"):
            raise HandoffError(f"Handoff hash mismatch: {path.name}")
        seen_paths.add(path)
        by_role[role] = path
    plan_path = by_role.get("canonical_tracking_plan")
    if plan_path is None:
        raise HandoffError("The handoff has no canonical_tracking_plan artifact.")
    if _digest(plan_path) != handoff.get("plan", {}).get("canonical_sha256"):
        raise HandoffError("The canonical plan hash differs from handoff.plan.canonical_sha256.")
    return handoff, _load(plan_path)


EVENT_NAME = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
PARAMETER_NAME = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
CLASSIFICATIONS = {"official", "official_ecommerce", "custom", "context"}
PARAMETER_SCOPES = {"event", "item", "user", "implementation"}
PARAMETER_TYPES = {"string", "integer", "number", "boolean", "array", "object"}
PARAMETER_REQUIREMENTS = {"required", "conditional", "optional"}
PARAMETER_DESTINATIONS = {
    "ga4_event_parameter",
    "ga4_item_parameter",
    "ga4_user_property",
    "ga4_user_id",
    "implementation_only",
    "other",
}


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HandoffError(f"{path} must be a non-empty string.")
    return value.strip()


def _text_array(value: Any, path: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise HandoffError(f"{path} must be an array.")
    items = [_text(item, f"{path}[]") for item in value]
    if not allow_empty and not items:
        raise HandoffError(f"{path} must not be empty.")
    if len(set(items)) != len(items):
        raise HandoffError(f"{path} contains duplicate values.")
    return items


def _requirement_id(event: dict[str, Any], event_name: str, path: str) -> str:
    supplied = event.get("requirement_id")
    if supplied is not None:
        return _text(supplied, f"{path}.requirement_id")
    return f"GA4::{event_name}"


def _validated_events(plan: dict[str, Any]) -> list[dict[str, Any]]:
    events = plan.get("events")
    if not isinstance(events, list) or not events:
        raise HandoffError("$.events must be a non-empty array.")
    validated: list[dict[str, Any]] = []
    event_names: set[str] = set()
    for event_index, event in enumerate(events):
        path = f"$.events[{event_index}]"
        if not isinstance(event, dict):
            raise HandoffError(f"{path} must be an object.")
        event_name = _text(event.get("event_name"), f"{path}.event_name")
        if not EVENT_NAME.fullmatch(event_name):
            raise HandoffError(f"{path}.event_name is not a valid GA4 event name.")
        if event_name in event_names:
            raise HandoffError(f"{path}.event_name duplicates {event_name!r}.")
        event_names.add(event_name)
        classification = _text(event.get("classification"), f"{path}.classification")
        if classification not in CLASSIFICATIONS:
            raise HandoffError(f"{path}.classification is unsupported.")
        _text(event.get("trigger"), f"{path}.trigger")
        _text_array(event.get("journey_ids"), f"{path}.journey_ids", allow_empty=False)
        measurement_opportunity_ids = _text_array(
            event.get("measurement_opportunity_ids", []),
            f"{path}.measurement_opportunity_ids",
        )
        if classification != "context" and not measurement_opportunity_ids:
            raise HandoffError(
                f"{path}.measurement_opportunity_ids must not be empty outside context events."
            )
        data_layer = event.get("data_layer")
        if not isinstance(data_layer, dict):
            raise HandoffError(f"{path}.data_layer must be an object.")
        _text_array(data_layer.get("clear", []), f"{path}.data_layer.clear")
        push = data_layer.get("push")
        if not isinstance(push, dict) or not push:
            raise HandoffError(f"{path}.data_layer.push must be a non-empty object.")
        parameters = event.get("parameters")
        if not isinstance(parameters, list):
            raise HandoffError(f"{path}.parameters must be an array.")
        parameter_keys: set[tuple[str, str]] = set()
        for parameter_index, parameter in enumerate(parameters):
            parameter_path = f"{path}.parameters[{parameter_index}]"
            if not isinstance(parameter, dict):
                raise HandoffError(f"{parameter_path} must be an object.")
            name = _text(parameter.get("name"), f"{parameter_path}.name")
            if not PARAMETER_NAME.fullmatch(name):
                raise HandoffError(f"{parameter_path}.name is not a valid GA4 parameter name.")
            scope = _text(parameter.get("scope"), f"{parameter_path}.scope")
            if scope not in PARAMETER_SCOPES:
                raise HandoffError(f"{parameter_path}.scope is unsupported.")
            parameter_type = _text(parameter.get("type"), f"{parameter_path}.type")
            if parameter_type not in PARAMETER_TYPES:
                raise HandoffError(f"{parameter_path}.type is unsupported.")
            requirement = _text(parameter.get("requirement"), f"{parameter_path}.requirement")
            if requirement not in PARAMETER_REQUIREMENTS:
                raise HandoffError(f"{parameter_path}.requirement is unsupported.")
            if requirement == "conditional":
                _text(parameter.get("condition"), f"{parameter_path}.condition")
            _text(parameter.get("data_layer_path"), f"{parameter_path}.data_layer_path")
            destination = _text(parameter.get("destination"), f"{parameter_path}.destination")
            if destination not in PARAMETER_DESTINATIONS:
                raise HandoffError(f"{parameter_path}.destination is unsupported.")
            key = (scope, name)
            if key in parameter_keys:
                raise HandoffError(f"{parameter_path} duplicates parameter {scope}::{name}.")
            parameter_keys.add(key)
        validated.append(event)
    return validated


def normalized_approved_semantics(handoff: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    requirements: list[dict[str, Any]] = []
    included: list[str] = []
    requirement_ids: set[str] = set()
    for order, event in enumerate(_validated_events(plan), start=1):
        event_name = str(event.get("event_name", ""))
        requirement_id = _requirement_id(event, event_name, f"$.events[{order - 1}]")
        if requirement_id in requirement_ids:
            raise HandoffError(
                f"$.events[{order - 1}] duplicates requirement ID {requirement_id!r}."
            )
        requirement_ids.add(requirement_id)
        included.append(requirement_id)
        parameters: dict[str, Any] = {}
        for parameter in event["parameters"]:
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
                "source_order": order,
                "classification": event.get("classification"),
                "source_event": event_name,
                "trigger": event.get("trigger"),
                "journey_ids": event.get("journey_ids", []),
                "measurement_opportunity_ids": event.get("measurement_opportunity_ids", []),
                "clear_before_push": event.get("data_layer", {}).get("clear", []),
                "parameters": parameters,
            }
        )
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
        write_json_atomic(args.output, result)
    except (HandoffError, OSError, UnicodeError) as error:
        sys.stderr.reconfigure(errors="backslashreplace")
        print(str(error), file=sys.stderr)
        return 2
    sys.stdout.reconfigure(errors="backslashreplace")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
