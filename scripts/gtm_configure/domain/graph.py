"""Small semantic graph predicates shared by domain validators."""

import re
from typing import Any


def _reference_values(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {item for child in value.values() for item in _reference_values(child)}
    if isinstance(value, list):
        return {item for child in value for item in _reference_values(child)}
    return {value} if isinstance(value, str) else set()


def _active_tag(item: dict[str, Any]) -> bool:
    intended = item.get("intended") if isinstance(item.get("intended"), dict) else {}
    return (
        item.get("resource_family") == "tag"
        and item.get("action") not in {"remove", "pause"}
        and intended.get("paused") is not True
    )


def _reference_name(value: str) -> str | None:
    match = re.fullmatch(r"\{\{\s*(.+?)\s*\}\}", value)
    return match.group(1) if match else None
