#!/usr/bin/env python3
"""Strict, BOM-tolerant JSON loading for configure-gtm runtime artifacts."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_JSON_DEPTH = 256


class StrictJsonError(ValueError):
    """Raised when runtime JSON is unreadable, ambiguous, or excessively nested."""

    def __init__(self, message: str, *, error_code: str = "invalid_json") -> None:
        super().__init__(message)
        self.error_code = error_code


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise StrictJsonError(f"duplicate JSON key {key!r}")
        value[key] = item
    return value


def _reject_non_finite(value: str) -> None:
    raise StrictJsonError(f"non-finite JSON number {value!r} is not supported")


def _validate_depth(value: Any, *, max_depth: int) -> None:
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > max_depth:
            raise StrictJsonError(
                f"JSON nesting exceeds the {max_depth}-level safety limit",
                error_code="json_depth",
            )
        if isinstance(current, dict):
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)


def loads_strict(text: str, *, source: str = "JSON", max_depth: int = MAX_JSON_DEPTH) -> Any:
    """Parse standards-compliant JSON while rejecting duplicate keys and deep nesting."""
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
    except StrictJsonError:
        raise
    except json.JSONDecodeError as exc:
        raise StrictJsonError(f"invalid JSON in {source}: {exc}") from exc
    except RecursionError as exc:
        raise StrictJsonError(
            f"JSON nesting in {source} exceeds the parser safety limit",
            error_code="json_depth",
        ) from exc
    _validate_depth(value, max_depth=max_depth)
    return value


def load_json(path: Path, *, max_bytes: int = MAX_JSON_BYTES) -> Any:
    """Read UTF-8 JSON, consistently accepting an optional UTF-8 BOM."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise StrictJsonError(f"cannot read {path}: {exc}", error_code="io_error") from exc
    if len(data) > max_bytes:
        raise StrictJsonError(
            f"JSON file {path} exceeds the {max_bytes}-byte safety limit",
            error_code="json_size",
        )
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise StrictJsonError(
            f"{path} is not valid UTF-8: {exc}",
            error_code="invalid_encoding",
        ) from exc
    return loads_strict(text, source=str(path))


def write_json_atomic(path: Path, value: Any) -> None:
    """Write deterministic UTF-8 JSON without exposing a partially written artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(
                value,
                stream,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_text_atomic(path: Path, value: str) -> None:
    """Write UTF-8 text atomically with the same durability boundary as JSON artifacts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
