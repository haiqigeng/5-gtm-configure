"""Server-container object and Event Data validation for configuration-run@4.0."""

from __future__ import annotations

from typing import Any, Callable

from event_semantics import approved_event_name
from event_semantics import trigger_accepts_event as matches_event
from run_model import SERVER_RESOURCE_FAMILIES

_WEB_ONLY_TRIGGER_MARKERS = {
    "click",
    "dom-ready",
    "element-visibility",
    "form-submission",
    "history-change",
    "javascript-error",
    "scroll-depth",
    "timer",
    "window-loaded",
    "youtube-video",
}
_BROWSER_CODE_TYPES = {"custom-html", "custom-javascript", "html", "cjs"}
_WEB_BUILT_IN_TRIGGER_IDS = {"2147479553", "2147479572", "2147479573"}


def validate_server_operations(
    operations: list[dict[str, Any]],
    target_types: dict[str, str],
    fail: Callable[[str], None],
    *,
    pipelines: list[dict[str, Any]],
    requirements: list[dict[str, Any]],
) -> None:
    """Reject browser semantics and ungoverned shared server resources."""
    operation_by_reference: dict[str, dict[str, Any]] = {}
    for operation in operations:
        for reference in (
            operation.get("operation_id"),
            operation.get("object_key"),
            operation.get("object_id"),
        ):
            if isinstance(reference, str) and reference:
                operation_by_reference[reference] = operation
    requirement_by_id = {item["id"]: item for item in requirements}
    expected_events: dict[str, set[str]] = {
        item["operation_id"]: set()
        for item in operations
        if target_types[item["target_id"]] == "server" and item["resource_family"] == "tag"
    }
    for pipeline in pipelines:
        for flow in pipeline.get("event_flows", []):
            for operation_id in flow.get("server_consumer_operation_ids", []):
                if operation_id in expected_events:
                    expected_events[operation_id].add(flow.get("transported_event"))

    def trigger_accepts_event(trigger: dict[str, Any], event_name: str) -> bool:
        return matches_event(trigger.get("intended", {}), event_name)

    for index, operation in enumerate(operations):
        target_id = operation["target_id"]
        if target_types[target_id] != "server":
            continue
        path = f"$.object_changes[{index}]"
        family = operation["resource_family"]
        if family not in SERVER_RESOURCE_FAMILIES:
            fail(f"{path}.resource_family is unavailable in a server container")
        intended = operation.get("intended") or {}
        raw_type = str(intended.get("type", intended.get("trigger_type", ""))).casefold()
        if family == "trigger" and any(marker in raw_type for marker in _WEB_ONLY_TRIGGER_MARKERS):
            fail(f"{path} uses a web lifecycle trigger in a server container")
        for field in ("firingTriggerId", "blockingTriggerId"):
            references = intended.get(field, [])
            if not isinstance(references, list):
                fail(f"{path}.intended.{field} must be an array")
                continue
            if any(str(value) in _WEB_BUILT_IN_TRIGGER_IDS for value in references):
                fail(f"{path}.intended.{field} uses a web built-in trigger in a server container")
        if raw_type in _BROWSER_CODE_TYPES:
            fail(f"{path} uses a browser Custom HTML/Custom JavaScript escape hatch")
        if (
            family == "tag"
            and operation["action"] not in {"remove", "pause"}
            and intended.get("paused") is not True
        ):
            firing_references = intended.get("firingTriggerId")
            if not isinstance(firing_references, list) or not firing_references:
                fail(f"{path}.intended.firingTriggerId must bind an active server trigger")
                firing_references = []
            blocking_references = intended.get("blockingTriggerId", [])
            if not isinstance(blocking_references, list):
                fail(f"{path}.intended.blockingTriggerId must be an array")
                blocking_references = []
            if set(firing_references) & set(blocking_references):
                fail(f"{path} reuses one trigger for firing and blocking")
            resolved_firing = []
            for reference in firing_references + blocking_references:
                trigger = operation_by_reference.get(reference)
                if (
                    trigger is None
                    or trigger.get("resource_family") != "trigger"
                    or trigger.get("target_id") != target_id
                ):
                    fail(f"{path} trigger references must resolve inside the server target")
                    continue
                if trigger["operation_id"] not in operation.get("dependencies", []):
                    fail(f"{path} must depend on every firing and blocking trigger")
                if reference in firing_references:
                    resolved_firing.append(trigger)
            events = {
                value for value in expected_events.get(operation["operation_id"], set()) if value
            }
            if not events:
                for requirement_id in operation.get("requirement_ids", []):
                    requirement = requirement_by_id.get(requirement_id, {})
                    event = approved_event_name(requirement)
                    if event:
                        events.add(event)
            for event in events:
                if not any(trigger_accepts_event(trigger, event) for trigger in resolved_firing):
                    fail(f"{path} has no firing trigger for {event!r}")
        if family == "client":
            if operation["action"] == "create":
                if not intended.get("claim_criteria"):
                    fail(f"{path}.intended.claim_criteria is required for a new Client")
                if intended.get("priority") is None:
                    fail(f"{path}.intended.priority is required for a new Client")
            if operation["action"] in {"create", "update", "replace"}:
                if operation.get("risk") != "high-impact":
                    fail(f"{path}.risk must be high-impact for Client claim behavior")
        if family == "transformation":
            scope = operation.get("scope") or intended.get("scope")
            if not scope:
                fail(f"{path}.scope must name the Transformation blast radius")
            if scope != "single-destination" and operation.get("risk") != "high-impact":
                fail(f"{path}.risk must be high-impact for a shared Transformation")
            if not intended.get("mode"):
                fail(f"{path}.intended.mode must identify allow, augment, or exclude")
        if family == "variable" and intended.get("variable_type") == "event-data":
            if not intended.get("key_path"):
                fail(f"{path}.intended.key_path is required for an Event Data variable")
            if not intended.get("claiming_client_proof"):
                fail(f"{path}.intended.claiming_client_proof is required")
        secret_fields = intended.get("secret_fields", [])
        if not isinstance(secret_fields, list):
            fail(f"{path}.intended.secret_fields must be an array")
        elif secret_fields and not all(isinstance(value, str) and value for value in secret_fields):
            fail(f"{path}.intended.secret_fields must contain exact template field paths")
