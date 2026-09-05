"""Current adapter, pagination, baseline, locking, and atomic-write primitives."""

from __future__ import annotations

import os
import random
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

from run_validation_web import RunConflictError
from strict_json import write_json_atomic


class AdapterExecutionError(RuntimeError):
    def __init__(self, message: str, *, code: str = "adapter_error") -> None:
        super().__init__(message)
        self.code = code


class RateLimitError(AdapterExecutionError):
    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message, code="rate_limited")
        if retry_after_seconds is not None and retry_after_seconds < 0:
            raise ValueError("retry_after_seconds must be non-negative")
        self.retry_after_seconds = retry_after_seconds


class AuthenticationError(AdapterExecutionError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="authentication_error")


class AmbiguousWriteError(AdapterExecutionError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="ambiguous_write")


class ConfigurationAdapter(Protocol):
    def read(self, operation: dict[str, Any]) -> dict[str, Any] | None: ...
    def mutate(self, operation: dict[str, Any]) -> dict[str, Any] | None: ...


def _retry_delay(
    error: RateLimitError,
    retry_index: int,
    *,
    base_delay_seconds: float,
    max_delay_seconds: float,
    random_value: Callable[[], float],
) -> float | None:
    if error.retry_after_seconds is not None:
        return error.retry_after_seconds if error.retry_after_seconds <= max_delay_seconds else None
    cap = min(base_delay_seconds * (2**retry_index), max_delay_seconds)
    return max(0.0, min(1.0, random_value())) * cap


def collect_paginated(
    fetch_page: Callable[[str | None], dict[str, Any]],
    *,
    max_pages: int = 1000,
    max_rate_limit_retries: int = 2,
    base_retry_delay_seconds: float = 0.5,
    max_retry_delay_seconds: float = 8.0,
    sleep: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> list[dict[str, Any]]:
    items, _ = collect_paginated_with_receipt(
        fetch_page,
        max_pages=max_pages,
        max_rate_limit_retries=max_rate_limit_retries,
        base_retry_delay_seconds=base_retry_delay_seconds,
        max_retry_delay_seconds=max_retry_delay_seconds,
        sleep=sleep,
        random_value=random_value,
    )
    return items


def collect_paginated_with_receipt(
    fetch_page: Callable[[str | None], dict[str, Any]],
    *,
    max_pages: int = 1000,
    max_rate_limit_retries: int = 2,
    base_retry_delay_seconds: float = 0.5,
    max_retry_delay_seconds: float = 8.0,
    sleep: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Collect one authenticated listing and create the exhaustion receipt internally."""
    if (
        max_pages < 1
        or max_rate_limit_retries < 0
        or base_retry_delay_seconds < 0
        or max_retry_delay_seconds < 0
    ):
        raise ValueError("page/retry limits and retry delays must be non-negative")
    cursor: str | None = None
    seen_cursors: set[str] = set()
    items: list[dict[str, Any]] = []
    pages_read = 0
    for _ in range(max_pages):
        retries = 0
        while True:
            try:
                page = fetch_page(cursor)
                break
            except RateLimitError as exc:
                if retries >= max_rate_limit_retries:
                    raise
                delay = _retry_delay(
                    exc,
                    retries,
                    base_delay_seconds=base_retry_delay_seconds,
                    max_delay_seconds=max_retry_delay_seconds,
                    random_value=random_value,
                )
                if delay is None:
                    raise
                retries += 1
                sleep(delay)
        pages_read += 1
        if not isinstance(page, dict) or not isinstance(page.get("items"), list):
            raise AdapterExecutionError("adapter page must contain an items array")
        for index, item in enumerate(page["items"]):
            if not isinstance(item, dict):
                raise AdapterExecutionError(f"adapter page item {index} must be an object")
            items.append(item)
        next_cursor = page.get("next_cursor")
        if next_cursor is None:
            return items, {"pages_read": pages_read, "exhausted": True}
        if not isinstance(next_cursor, str) or not next_cursor:
            raise AdapterExecutionError("next_cursor must be a non-empty string or null")
        if next_cursor in seen_cursors:
            raise AdapterExecutionError(f"pagination cursor loop at {next_cursor!r}")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    raise AdapterExecutionError(f"pagination exceeded the {max_pages}-page safety limit")


def collect_resource_baseline(
    fetch_page: Callable[[str, str | None], dict[str, Any]],
    resource_families: list[str],
    **kwargs: Any,
) -> dict[str, list[dict[str, Any]]]:
    normalized = []
    for index, family in enumerate(resource_families):
        if not isinstance(family, str) or not family.strip():
            raise ValueError(f"resource_families[{index}] must be a non-empty string")
        normalized.append(family.strip())
    if not normalized or len(set(normalized)) != len(normalized):
        raise ValueError("resource_families must be non-empty and unique")
    return {
        family: collect_paginated(
            lambda cursor, selected=family: fetch_page(selected, cursor), **kwargs
        )
        for family in normalized
    }


@contextmanager
def run_file_lock(path: Path) -> Iterator[None]:
    lock_path = path.with_name(f".{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    stream = lock_path.open("a+b")
    try:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RunConflictError(
                f"run artifact is already controlled by another process: {path}"
            ) from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    finally:
        stream.close()


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    write_json_atomic(path, value)
