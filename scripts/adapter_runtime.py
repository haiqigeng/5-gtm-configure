#!/usr/bin/env python3
"""Adapter-neutral pagination and mutation safety state machine for configure-gtm."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any, Protocol

from configuration_run import (
    RunConflictError,
    atomic_write,
    build_pre_write_comparison,
    canonical_sha256,
    checkpoint_operation,
    inspect_document,
    load_document,
    run_file_lock,
    validate_verification_comparison,
)


class AdapterExecutionError(RuntimeError):
    """Raised when adapter behavior cannot be interpreted safely."""

    def __init__(self, message: str, *, code: str = "adapter_error") -> None:
        super().__init__(message)
        self.code = code


class RateLimitError(AdapterExecutionError):
    """A documented rejection that did not apply the requested operation."""

    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message, code="rate_limited")
        if retry_after_seconds is not None and retry_after_seconds < 0:
            raise ValueError("retry_after_seconds must be non-negative")
        self.retry_after_seconds = retry_after_seconds


class AuthenticationError(AdapterExecutionError):
    """Authentication expired or resolved to the wrong account/container."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="authentication_error")


class AmbiguousWriteError(AdapterExecutionError):
    """The adapter cannot prove whether the requested mutation was saved."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="ambiguous_write")


class ConfigurationAdapter(Protocol):
    """Small semantic boundary implemented by a programmatic GTM adapter."""

    def read(self, operation: dict[str, Any]) -> dict[str, Any] | None: ...

    def compare(
        self,
        operation: dict[str, Any],
        saved: dict[str, Any] | None,
    ) -> dict[str, Any]: ...

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
        if error.retry_after_seconds > max_delay_seconds:
            return None
        return error.retry_after_seconds
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
    """Exhaust cursor pagination; reject loops, malformed pages, and unbounded retries."""
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
        if not isinstance(page, dict) or not isinstance(page.get("items"), list):
            raise AdapterExecutionError("adapter page must contain an items array")
        for index, item in enumerate(page["items"]):
            if not isinstance(item, dict):
                raise AdapterExecutionError(f"adapter page item {index} must be an object")
            items.append(item)
        next_cursor = page.get("next_cursor")
        if next_cursor is None:
            return items
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
    *,
    max_pages_per_family: int = 1000,
    max_rate_limit_retries: int = 2,
    base_retry_delay_seconds: float = 0.5,
    max_retry_delay_seconds: float = 8.0,
    sleep: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> dict[str, list[dict[str, Any]]]:
    """Collect each requested resource family exactly once through complete pagination."""
    normalized = []
    for index, family in enumerate(resource_families):
        if not isinstance(family, str) or not family.strip():
            raise ValueError(f"resource_families[{index}] must be a non-empty string")
        normalized.append(family.strip())
    if not normalized:
        raise ValueError("resource_families must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError("resource_families must not contain duplicates")

    baseline: dict[str, list[dict[str, Any]]] = {}
    for family in normalized:
        baseline[family] = collect_paginated(
            lambda cursor, selected=family: fetch_page(selected, cursor),
            max_pages=max_pages_per_family,
            max_rate_limit_retries=max_rate_limit_retries,
            base_retry_delay_seconds=base_retry_delay_seconds,
            max_retry_delay_seconds=max_retry_delay_seconds,
            sleep=sleep,
            random_value=random_value,
        )
    return baseline


def build_container_baseline(
    resources: dict[str, list[dict[str, Any]]],
    *,
    strategy: str,
    captured_at: str,
    in_scope_tag_keys: list[str],
    preexisting_workspace_changes: int,
) -> dict[str, Any]:
    """Build the bound run-baseline record from one completed paginated collection."""
    if strategy not in {"relevant-families", "full-paginated"}:
        raise ValueError("strategy must be relevant-families or full-paginated")
    if not isinstance(resources, dict) or not resources:
        raise ValueError("resources must contain at least one collected family")
    for family, items in resources.items():
        if not isinstance(family, str) or not family.strip() or not isinstance(items, list):
            raise ValueError("resources must map non-empty family names to item arrays")
        if any(not isinstance(item, dict) for item in items):
            raise ValueError(f"resources.{family} contains a non-object item")
    trigger_index = []
    for index, trigger in enumerate(resources.get("trigger", [])):
        if not isinstance(trigger, dict):
            raise ValueError(f"resources.trigger[{index}] must be an object")
        trigger_id = trigger.get("triggerId")
        object_key = trigger.get("object_key")
        if isinstance(trigger_id, str) and trigger_id in {
            "2147479553",
            "2147479572",
            "2147479573",
        }:
            continue
        if not isinstance(object_key, str) or not object_key.startswith("trigger::"):
            name = trigger.get("name")
            if isinstance(name, str) and name.strip():
                object_key = f"trigger::{name.strip()}"
            else:
                raise ValueError(f"resources.trigger[{index}] needs a semantic object key or name")
        trigger_type = trigger.get("type")
        if not isinstance(trigger_type, str) or not trigger_type.strip():
            raise ValueError(f"resources.trigger[{index}].type must be a non-empty string")
        fingerprint = trigger.get("fingerprint")
        if fingerprint is not None and not isinstance(fingerprint, str):
            raise ValueError(f"resources.trigger[{index}].fingerprint must be a string or null")
        if isinstance(fingerprint, str):
            if len(fingerprint) != 71 or not fingerprint.startswith("sha256:"):
                raise ValueError(
                    f"resources.trigger[{index}].fingerprint must be a sha256 fingerprint"
                )
            try:
                int(fingerprint.removeprefix("sha256:"), 16)
            except ValueError as exc:
                raise ValueError(
                    f"resources.trigger[{index}].fingerprint must be a sha256 fingerprint"
                ) from exc
        trigger_index.append(
            {
                "object_key": object_key,
                "type": trigger_type,
                "fingerprint": fingerprint,
            }
        )
    return {
        "strategy": strategy,
        "captured_at": captured_at,
        "complete": True,
        "resource_families": list(resources),
        "family_counts": {family: len(items) for family, items in resources.items()},
        "in_scope_tag_keys": list(in_scope_tag_keys),
        "trigger_index": trigger_index,
        "preexisting_workspace_changes": preexisting_workspace_changes,
        "fingerprint": canonical_sha256(resources),
    }


def _result(saved: dict[str, Any] | None, response: dict[str, Any] | None) -> dict[str, Any]:
    source = saved or response or {}
    return {
        "object_id": source.get("object_id")
        or source.get("tagId")
        or source.get("triggerId")
        or source.get("variableId")
        or source.get("folderId")
        or source.get("templateId")
        or source.get("zoneId")
        or source.get("environmentId"),
        "fingerprint": source.get("fingerprint"),
    }


def _save(path: Path, document: dict[str, Any]) -> None:
    atomic_write(path, document)


def _operation(document: dict[str, Any], operation_id: str) -> dict[str, Any]:
    by_id = {item["operation_id"]: item for item in document["object_changes"]}
    try:
        return by_id[operation_id]
    except KeyError as exc:
        raise AdapterExecutionError(
            f"run artifact no longer contains operation {operation_id!r}",
            code="invalid_run",
        ) from exc


def _read(adapter: ConfigurationAdapter, operation: dict[str, Any]) -> dict[str, Any] | None:
    saved = adapter.read(deepcopy(operation))
    if saved is not None and not isinstance(saved, dict):
        raise AdapterExecutionError(
            "adapter.read must return an object or null",
            code="adapter_schema_error",
        )
    return deepcopy(saved)


def _compare(
    adapter: ConfigurationAdapter,
    operation: dict[str, Any],
    saved: dict[str, Any] | None,
) -> dict[str, Any]:
    comparison = adapter.compare(deepcopy(operation), deepcopy(saved))
    try:
        return validate_verification_comparison(
            comparison,
            operation=operation,
            saved=saved,
        )
    except ValueError as exc:
        raise AdapterExecutionError(
            f"adapter comparison evidence is invalid: {exc}",
            code="adapter_schema_error",
        ) from exc


def _execute_ready_operations_locked(
    run_path: Path,
    adapter: ConfigurationAdapter,
    *,
    max_rate_limit_retries: int = 2,
    timestamp: Callable[[], str] | None = None,
    base_retry_delay_seconds: float = 0.5,
    max_retry_delay_seconds: float = 8.0,
    sleep: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> dict[str, Any]:
    """Execute currently ready operations with durable checkpoints and no blind write retry."""
    document = load_document(run_path)
    if max_rate_limit_retries < 0 or base_retry_delay_seconds < 0 or max_retry_delay_seconds < 0:
        raise ValueError("retry limits and retry delays must be non-negative")
    inspection = inspect_document(document)
    if not inspection["resumable"]:
        raise AdapterExecutionError(
            "run contains failed, in-progress, or uncertain operations; resolve or explicitly "
            "reopen them before execution",
            code="unsafe_resume",
        )
    now = timestamp or (lambda: None)

    while True:
        inspection = inspect_document(document)
        if inspection["unsafe_operations"]:
            break
        if not inspection["ready_operations"]:
            break
        operation_id = inspection["ready_operations"][0]
        operation = _operation(document, operation_id)
        at = now()
        try:
            existing = _read(adapter, operation)
        except AuthenticationError as exc:
            document = checkpoint_operation(
                document,
                operation_id=operation_id,
                state="failed",
                note="Authentication failed before mutation; no write attempted.",
                timestamp=at,
                error=str(exc),
            )
            _save(run_path, document)
            break
        except AdapterExecutionError as exc:
            document = checkpoint_operation(
                document,
                operation_id=operation_id,
                state="failed",
                note="Adapter read failed before mutation; no write attempted.",
                timestamp=at,
                error=f"{exc.code}: {exc}",
            )
            _save(run_path, document)
            break

        try:
            comparison = _compare(adapter, operation, existing)
        except AdapterExecutionError as exc:
            document = checkpoint_operation(
                document,
                operation_id=operation_id,
                state="failed",
                note="Adapter comparison failed before mutation; no write attempted.",
                timestamp=at,
                error=f"{exc.code}: {exc}",
            )
            _save(run_path, document)
            break
        if comparison["pass"]:
            document = checkpoint_operation(
                document,
                operation_id=operation_id,
                state="verified",
                note="Existing saved state already matches; mutation skipped.",
                timestamp=at,
                result=_result(existing, None),
                comparison=comparison,
                saved=existing,
            )
            _save(run_path, document)
            continue

        if operation["action"] in {"reuse", "untouched"}:
            document = checkpoint_operation(
                document,
                operation_id=operation_id,
                state="failed",
                note="Expected reusable object does not match saved state.",
                timestamp=at,
                error="semantic readback mismatch",
            )
            _save(run_path, document)
            break

        if operation["action"] == "create" and existing is not None:
            document = checkpoint_operation(
                document,
                operation_id=operation_id,
                state="failed",
                note="Create target already exists with different saved state; no write attempted.",
                timestamp=at,
                error="create_conflict: semantic object identity is already occupied",
            )
            _save(run_path, document)
            break

        pre_write_comparison = None
        if operation["action"] in {"update", "replace", "rename", "pause", "unpause", "remove"}:
            try:
                pre_write_comparison = build_pre_write_comparison(operation, existing)
            except ValueError as exc:
                document = checkpoint_operation(
                    document,
                    operation_id=operation_id,
                    state="failed",
                    note="Pre-write drift comparison could not be built; no write attempted.",
                    timestamp=at,
                    error=f"adapter_schema_error: {exc}",
                )
                _save(run_path, document)
                break
            if not pre_write_comparison["pass"]:
                document = checkpoint_operation(
                    document,
                    operation_id=operation_id,
                    state="failed",
                    note="Saved object drifted from pre_change; no write attempted.",
                    timestamp=at,
                    pre_write_comparison=pre_write_comparison,
                    pre_write_saved=existing,
                    error="container_drift: live saved state differs from approved pre_change",
                )
                _save(run_path, document)
                break

        pre_write_checkpoint = {}
        if pre_write_comparison is not None:
            pre_write_checkpoint = {
                "pre_write_comparison": pre_write_comparison,
                "pre_write_saved": existing,
            }
        document = checkpoint_operation(
            document,
            operation_id=operation_id,
            state="in_progress",
            note="Read-before-write completed; starting one mutation.",
            timestamp=at,
            **pre_write_checkpoint,
        )
        _save(run_path, document)

        response: dict[str, Any] | None = None
        retries = 0
        while True:
            try:
                response = adapter.mutate(deepcopy(operation))
                if response is not None and not isinstance(response, dict):
                    raise AdapterExecutionError(
                        "adapter.mutate must return an object or null",
                        code="adapter_schema_error",
                    )
                response = deepcopy(response)
                break
            except RateLimitError as exc:
                if retries >= max_rate_limit_retries:
                    document = checkpoint_operation(
                        document,
                        operation_id=operation_id,
                        state="failed",
                        note="Bounded rate-limit retries exhausted; all remaining writes stopped.",
                        timestamp=now(),
                        error=str(exc),
                    )
                    _save(run_path, document)
                    break
                delay = _retry_delay(
                    exc,
                    retries,
                    base_delay_seconds=base_retry_delay_seconds,
                    max_delay_seconds=max_retry_delay_seconds,
                    random_value=random_value,
                )
                if delay is None:
                    document = checkpoint_operation(
                        document,
                        operation_id=operation_id,
                        state="failed",
                        note="Server retry window exceeds the configured bound; no retry attempted.",
                        timestamp=now(),
                        error=str(exc),
                    )
                    _save(run_path, document)
                    break
                retries += 1
                sleep(delay)
            except AuthenticationError as exc:
                document = checkpoint_operation(
                    document,
                    operation_id=operation_id,
                    state="failed",
                    note="Authentication failed during mutation; all remaining writes stopped.",
                    timestamp=now(),
                    error=str(exc),
                )
                _save(run_path, document)
                break
            except AmbiguousWriteError as exc:
                try:
                    saved = _read(adapter, operation)
                except AuthenticationError as readback_exc:
                    document = checkpoint_operation(
                        document,
                        operation_id=operation_id,
                        state="uncertain",
                        note="Ambiguous response could not be resolved because readback authentication failed.",
                        timestamp=now(),
                        error=f"{exc}; authoritative readback failed: {readback_exc}",
                    )
                    _save(run_path, document)
                    break
                except AdapterExecutionError as readback_exc:
                    document = checkpoint_operation(
                        document,
                        operation_id=operation_id,
                        state="uncertain",
                        note="Ambiguous response could not be resolved by authoritative readback.",
                        timestamp=now(),
                        error=f"{exc}; {readback_exc.code}: {readback_exc}",
                    )
                    _save(run_path, document)
                    break
                try:
                    comparison = _compare(adapter, operation, saved)
                except AdapterExecutionError as compare_exc:
                    document = checkpoint_operation(
                        document,
                        operation_id=operation_id,
                        state="uncertain",
                        note="Ambiguous response could not be resolved because comparison evidence was invalid.",
                        timestamp=now(),
                        error=f"{exc}; {compare_exc.code}: {compare_exc}",
                    )
                    _save(run_path, document)
                    break
                if comparison["pass"]:
                    document = checkpoint_operation(
                        document,
                        operation_id=operation_id,
                        state="verified",
                        note="Ambiguous response resolved by matching authoritative readback.",
                        timestamp=now(),
                        result=_result(saved, response),
                        comparison=comparison,
                        saved=saved,
                    )
                else:
                    document = checkpoint_operation(
                        document,
                        operation_id=operation_id,
                        state="uncertain",
                        note="Ambiguous response was not resolved; mutation was not retried.",
                        timestamp=now(),
                        error=str(exc),
                    )
                _save(run_path, document)
                break
            except AdapterExecutionError as exc:
                document = checkpoint_operation(
                    document,
                    operation_id=operation_id,
                    state="uncertain",
                    note="The adapter response was invalid after the mutation call; no retry attempted.",
                    timestamp=now(),
                    error=f"{exc.code}: {exc}",
                )
                _save(run_path, document)
                break
        current_state = _operation(document, operation_id)["state"]
        if current_state in {"failed", "uncertain", "verified"}:
            if current_state != "verified":
                break
            continue

        try:
            saved = _read(adapter, operation)
        except AuthenticationError as exc:
            document = checkpoint_operation(
                document,
                operation_id=operation_id,
                state="uncertain",
                note="Mutation returned but authoritative readback failed; no retry attempted.",
                timestamp=now(),
                error=str(exc),
            )
            _save(run_path, document)
            break
        except AdapterExecutionError as exc:
            document = checkpoint_operation(
                document,
                operation_id=operation_id,
                state="uncertain",
                note="Mutation returned but authoritative readback was invalid; no retry attempted.",
                timestamp=now(),
                error=f"{exc.code}: {exc}",
            )
            _save(run_path, document)
            break
        try:
            comparison = _compare(adapter, operation, saved)
        except AdapterExecutionError as exc:
            document = checkpoint_operation(
                document,
                operation_id=operation_id,
                state="uncertain",
                note="Mutation returned but comparison evidence was invalid; no retry attempted.",
                timestamp=now(),
                error=f"{exc.code}: {exc}",
            )
            _save(run_path, document)
            break
        if comparison["pass"]:
            document = checkpoint_operation(
                document,
                operation_id=operation_id,
                state="verified",
                note="Authoritative saved readback matches the intended object.",
                timestamp=now(),
                result=_result(saved, response),
                comparison=comparison,
                saved=saved,
            )
        else:
            document = checkpoint_operation(
                document,
                operation_id=operation_id,
                state="uncertain",
                note="Mutation returned but saved readback does not match; no retry attempted.",
                timestamp=now(),
                error="saved readback mismatch",
            )
        _save(run_path, document)
        if _operation(document, operation_id)["state"] != "verified":
            break

    return inspect_document(document)


def execute_ready_operations(
    run_path: Path,
    adapter: ConfigurationAdapter,
    *,
    max_rate_limit_retries: int = 2,
    timestamp: Callable[[], str] | None = None,
    base_retry_delay_seconds: float = 0.5,
    max_retry_delay_seconds: float = 8.0,
    sleep: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> dict[str, Any]:
    """Execute one run under an exclusive artifact lock."""
    try:
        with run_file_lock(run_path):
            return _execute_ready_operations_locked(
                run_path,
                adapter,
                max_rate_limit_retries=max_rate_limit_retries,
                timestamp=timestamp,
                base_retry_delay_seconds=base_retry_delay_seconds,
                max_retry_delay_seconds=max_retry_delay_seconds,
                sleep=sleep,
                random_value=random_value,
            )
    except RunConflictError as exc:
        raise AdapterExecutionError(str(exc), code="run_conflict") from exc
