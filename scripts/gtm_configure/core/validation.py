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


def object(value: Any, path: str, *, error_type=RunValidationError) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise error_type(f"{path} must be an object")
    return value


def array(value: Any, path: str, *, error_type=RunValidationError) -> list[Any]:
    if not isinstance(value, list):
        raise error_type(f"{path} must be an array")
    return value


def text(value: Any, path: str, *, error_type=RunValidationError) -> str:
    if not isinstance(value, str) or not value.strip():
        raise error_type(f"{path} must be a non-empty string")
    return value.strip()


def optional_text(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return text(value, path)


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


def unique_texts(
    value: Any, path: str, *, allow_empty: bool = True, error_type=RunValidationError
) -> list[str]:
    items = array(value, path, error_type=error_type)
    normalized = [text(item, f"{path}[]", error_type=error_type) for item in items]
    if len(set(normalized)) != len(normalized):
        raise error_type(f"{path} contains duplicate values")
    if not allow_empty and not normalized:
        raise error_type(f"{path} must not be empty")
    return normalized


def timestamp(value: Any, path: str) -> str:
    value_text = text(value, path)
    try:
        parsed = datetime.fromisoformat(value_text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RunValidationError(f"{path} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise RunValidationError(f"{path} must include a timezone")
    return value_text


def normalized_token(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())
