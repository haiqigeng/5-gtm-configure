"""Validation primitives: shared across preparation and execution."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any


class RunValidationError(ValueError):
    """Raised when a configuration-run manifest violates the operational contract."""

    def __init__(self, message: str, *, error_code: str = "invalid_run") -> None:
        super().__init__(message)
        self.error_code = error_code


class RunConflictError(RunValidationError):
    """Raised when another controller owns the same run artifact."""


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RunValidationError(f"{path} must be an object")
    return value


def _exact_keys(
    value: dict[str, Any],
    path: str,
    *,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    allowed = required | (optional or set())
    missing = sorted(required - set(value))
    unexpected = sorted(set(value) - allowed)
    if missing:
        raise RunValidationError(f"{path} is missing key(s): {', '.join(missing)}")
    if unexpected:
        raise RunValidationError(f"{path} contains unexpected key(s): {', '.join(unexpected)}")


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise RunValidationError(f"{path} must be an array")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RunValidationError(f"{path} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _text(value, path)


def canonical_sha256(value: Any) -> str:
    """Hash one JSON-compatible value with one stable Unicode representation."""
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise RunValidationError(f"value cannot be fingerprinted safely: {exc}") from exc
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _unique_texts(value: Any, path: str, *, allow_empty: bool = True) -> list[str]:
    items = _array(value, path)
    normalized = [_text(item, f"{path}[]") for item in items]
    if len(set(normalized)) != len(normalized):
        raise RunValidationError(f"{path} contains duplicate values")
    if not allow_empty and not normalized:
        raise RunValidationError(f"{path} must not be empty")
    return normalized


def _timestamp(value: Any, path: str) -> str:
    text = _text(value, path)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RunValidationError(f"{path} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise RunValidationError(f"{path} must include a timezone")
    return text


def _date(value: Any, path: str) -> str:
    text = _text(value, path)
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise RunValidationError(f"{path} must use YYYY-MM-DD") from exc
    return text
