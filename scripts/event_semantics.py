"""Read event selectors from actual GTM fields, never names, notes, or arbitrary strings."""

from __future__ import annotations

import re
from typing import Any


def approved_event_name(requirement: dict[str, Any]) -> str | None:
    """Return the single approved source event used by every validation layer."""
    value = requirement.get("source_event") or requirement.get("event_name")
    return value.strip() if isinstance(value, str) and value.strip() else None


def configured_event_name(intended: dict[str, Any]) -> str | None:
    """Return a literal selected event name; dynamic/native passthrough needs separate proof."""
    for key in ("event_name", "eventName"):
        value = intended.get(key)
        if isinstance(value, str) and "{{" not in value:
            return value
    for parameter in intended.get("parameter", []):
        if isinstance(parameter, dict) and parameter.get("key") in {"event_name", "eventName"}:
            value = parameter.get("value")
            if isinstance(value, str) and "{{" not in value:
                return value
    return None


def trigger_accepts_event(intended: dict[str, Any], event_name: str) -> bool:
    """Check only the event-name selector, not runtime business/consent eligibility.

    The contract's compact selector is a regex. GTM REST Condition arrays carry their own
    operator, case, and negate settings. Unsupported selectors cannot establish event coverage.
    """
    selector = intended.get("customEventFilter")
    if isinstance(selector, str):
        try:
            return re.fullmatch(selector, event_name) is not None
        except re.error:
            return False
    if not isinstance(selector, list) or not selector:
        return False
    for condition in selector:
        if not isinstance(condition, dict):
            return False
        parameters = condition.get("parameter", [])
        if not isinstance(parameters, list):
            return False
        fields = {
            item.get("key"): item.get("value") for item in parameters if isinstance(item, dict)
        }
        if fields.get("arg0") not in {"{{_event}}", "{{Event}}"}:
            return False
        operand = fields.get("arg1")
        if not isinstance(operand, str) or "{{" in operand:
            return False
        operator = str(condition.get("type", "")).lower()
        if operator == "equals":
            matches = event_name == operand
        elif operator == "matchregex":
            flags = re.IGNORECASE if fields.get("ignore_case") in {True, "true"} else 0
            try:
                matches = re.search(operand, event_name, flags) is not None
            except re.error:
                return False
        else:
            return False
        if fields.get("negate") in {True, "true"}:
            matches = not matches
        if not matches:
            return False
    return True
