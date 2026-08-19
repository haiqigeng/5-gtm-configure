#!/usr/bin/env python3
"""Target-aware adapter execution with dependency-only failure containment."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import adapter_runtime_web as legacy
from configuration_run import (
    atomic_write,
    build_pre_write_comparison,
    build_verification_comparison,
    checkpoint_operation,
    inspect_document,
    load_document,
    run_file_lock,
)
from redaction import (
    SecretProvider,
    SecretResolutionError,
    redact_for_persistence,
    resolve_for_mutation,
    scrub_sensitive_text,
)
from resource_registry import capability_matrix, unsupported_operation_reason
from run_state import build_target_baseline as build_target_baseline

AdapterExecutionError = legacy.AdapterExecutionError
RateLimitError = legacy.RateLimitError
AuthenticationError = legacy.AuthenticationError
AmbiguousWriteError = legacy.AmbiguousWriteError
ConfigurationAdapter = legacy.ConfigurationAdapter
collect_paginated = legacy.collect_paginated
collect_resource_baseline = legacy.collect_resource_baseline
build_container_baseline = legacy.build_container_baseline


class TargetAdapter(Protocol):
    """Semantic adapter bound to exactly one authorized GTM target."""

    def read(self, operation: dict[str, Any]) -> dict[str, Any] | None: ...

    def mutate(self, operation: dict[str, Any]) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class TargetBinding:
    adapter: TargetAdapter
    capabilities: dict[str, dict[str, bool]]
    secret_provider: SecretProvider | None


class TargetAdapterRegistry:
    """Bind adapters and discovered capabilities to stable run target IDs."""

    def __init__(self) -> None:
        self._bindings: dict[str, TargetBinding] = {}

    def register(
        self,
        target: dict[str, Any],
        adapter: TargetAdapter,
        capabilities: dict[str, Any],
        *,
        secret_provider: SecretProvider | None = None,
    ) -> None:
        target_id = target["target_id"]
        if target_id in self._bindings:
            raise AdapterExecutionError(f"duplicate target adapter {target_id!r}")
        self._bindings[target_id] = TargetBinding(
            adapter=adapter,
            capabilities=capability_matrix(target, capabilities),
            secret_provider=secret_provider,
        )

    def binding(self, target_id: str) -> TargetBinding:
        try:
            return self._bindings[target_id]
        except KeyError as exc:
            raise AdapterExecutionError(
                f"no adapter is registered for target {target_id!r}", code="target_unavailable"
            ) from exc

    def discovered_capabilities(self, target_id: str) -> dict[str, dict[str, bool]] | None:
        """Return a copy of a registered target's normalized capability matrix."""
        binding = self._bindings.get(target_id)
        return deepcopy(binding.capabilities) if binding else None


def _read(adapter: TargetAdapter, operation: dict[str, Any]) -> dict[str, Any] | None:
    saved = adapter.read(deepcopy(operation))
    if saved is not None and not isinstance(saved, dict):
        raise AdapterExecutionError(
            "target adapter read must return an object or null",
            code="adapter_schema_error",
        )
    return saved


def _call_with_rate_limit(
    callback: Callable[[], Any],
    *,
    max_retries: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    sleep: Callable[[float], None],
    random_value: Callable[[], float],
) -> Any:
    """Retry only a documented non-applied rate-limit response within a strict bound."""
    for retry_index in range(max_retries + 1):
        try:
            return callback()
        except RateLimitError as exc:
            if retry_index >= max_retries:
                raise
            delay = legacy._retry_delay(
                exc,
                retry_index,
                base_delay_seconds=base_delay_seconds,
                max_delay_seconds=max_delay_seconds,
                random_value=random_value,
            )
            if delay is None:
                raise
            sleep(delay)
    raise AssertionError("bounded retry loop exhausted without returning or raising")


def _save(path: Path, document: dict[str, Any]) -> None:
    atomic_write(path, redact_for_persistence(document))


def _operation(document: dict[str, Any], operation_id: str) -> dict[str, Any]:
    for operation in document["object_changes"]:
        if operation["operation_id"] == operation_id:
            return operation
    raise AdapterExecutionError(f"unknown operation {operation_id!r}")


def _target(document: dict[str, Any], target_id: str) -> dict[str, Any]:
    for target in document["run"]["targets"]:
        if target["target_id"] == target_id:
            return target
    raise AdapterExecutionError(f"unknown target {target_id!r}")


def _execute_v3_locked(
    run_path: Path,
    registry: TargetAdapterRegistry,
    *,
    timestamp: Callable[[], str],
    max_rate_limit_retries: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    sleep: Callable[[float], None],
    random_value: Callable[[], float],
) -> dict[str, Any]:
    document = load_document(run_path)
    capabilities_changed = False
    for target in document["run"]["targets"]:
        discovered = registry.discovered_capabilities(target["target_id"])
        if discovered is not None and target["adapter_capabilities"] != discovered:
            target["adapter_capabilities"] = discovered
            capabilities_changed = True
    if capabilities_changed:
        _save(run_path, document)

    while True:
        document = load_document(run_path)
        inspection = inspect_document(document)
        ready = inspection["ready_operations"]
        if not ready:
            return inspection
        progress = False
        for operation_id in ready:
            document = load_document(run_path)
            operation = _operation(document, operation_id)
            _target(document, operation["target_id"])
            try:
                binding = registry.binding(operation["target_id"])
            except AdapterExecutionError as exc:
                document = checkpoint_operation(
                    document,
                    operation_id=operation_id,
                    state="failed",
                    note="Target adapter is unavailable; dependents remain stopped.",
                    timestamp=timestamp(),
                    error=str(exc),
                )
                _save(run_path, document)
                progress = True
                continue
            reason = unsupported_operation_reason(operation, binding.capabilities)
            if reason:
                document = checkpoint_operation(
                    document,
                    operation_id=operation_id,
                    state="failed",
                    note="Required adapter family capability is unavailable.",
                    timestamp=timestamp(),
                    error=reason,
                )
                _save(run_path, document)
                progress = True
                continue
            ephemeral_values: set[str] = set()
            try:
                current = _call_with_rate_limit(
                    lambda: _read(binding.adapter, operation),
                    max_retries=max_rate_limit_retries,
                    base_delay_seconds=base_delay_seconds,
                    max_delay_seconds=max_delay_seconds,
                    sleep=sleep,
                    random_value=random_value,
                )
                if operation["action"] == "create" and current is not None:
                    comparison, safe_current = build_verification_comparison(operation, current)
                    if comparison["pass"]:
                        document = checkpoint_operation(
                            document,
                            operation_id=operation_id,
                            state="verified",
                            note="Existing semantic object already matches; no write performed.",
                            timestamp=timestamp(),
                            comparison=comparison,
                            saved=safe_current,
                        )
                    else:
                        document = checkpoint_operation(
                            document,
                            operation_id=operation_id,
                            state="failed",
                            note="Create conflict; existing semantic object was not overwritten.",
                            timestamp=timestamp(),
                            error="create_conflict",
                        )
                    _save(run_path, document)
                    progress = True
                    continue
                if operation["action"] in {"reuse", "untouched"}:
                    if current is None:
                        document = checkpoint_operation(
                            document,
                            operation_id=operation_id,
                            state="failed",
                            note="Required existing object was not found; no write performed.",
                            timestamp=timestamp(),
                            error="existing_object_missing",
                        )
                    else:
                        comparison, safe_current = build_verification_comparison(operation, current)
                        if comparison["pass"]:
                            document = checkpoint_operation(
                                document,
                                operation_id=operation_id,
                                state="verified",
                                note="Existing object compatibility verified; no write performed.",
                                timestamp=timestamp(),
                                comparison=comparison,
                                saved=safe_current,
                            )
                        else:
                            document = checkpoint_operation(
                                document,
                                operation_id=operation_id,
                                state="failed",
                                note="Existing object does not match the approved reuse contract.",
                                timestamp=timestamp(),
                                error="reuse_mismatch",
                            )
                    _save(run_path, document)
                    progress = True
                    continue
                kwargs: dict[str, Any] = {}
                if operation["action"] in {
                    "update",
                    "replace",
                    "rename",
                    "pause",
                    "unpause",
                    "remove",
                }:
                    pre_write_comparison, safe_current = build_pre_write_comparison(
                        operation, current
                    )
                    if not pre_write_comparison["pass"]:
                        document = checkpoint_operation(
                            document,
                            operation_id=operation_id,
                            state="failed",
                            note="Fresh target state differs from the approved pre-change snapshot; no write performed.",
                            timestamp=timestamp(),
                            error="container_drift",
                        )
                        _save(run_path, document)
                        progress = True
                        continue
                    kwargs = {
                        "pre_write_comparison": pre_write_comparison,
                        "pre_write_saved": safe_current,
                    }
                try:
                    mutation_operation, ephemeral_values = resolve_for_mutation(
                        operation, binding.secret_provider
                    )
                except SecretResolutionError as exc:
                    document = checkpoint_operation(
                        document,
                        operation_id=operation_id,
                        state="failed",
                        note="Secure mutation input could not be resolved.",
                        timestamp=timestamp(),
                        error=str(exc),
                    )
                    _save(run_path, document)
                    progress = True
                    continue
                document = checkpoint_operation(
                    document,
                    operation_id=operation_id,
                    state="in_progress",
                    note="Write boundary entered after fresh target readback.",
                    timestamp=timestamp(),
                    **kwargs,
                )
                _save(run_path, document)
                operation = _operation(document, operation_id)
                try:
                    _call_with_rate_limit(
                        lambda: binding.adapter.mutate(deepcopy(mutation_operation)),
                        max_retries=max_rate_limit_retries,
                        base_delay_seconds=base_delay_seconds,
                        max_delay_seconds=max_delay_seconds,
                        sleep=sleep,
                        random_value=random_value,
                    )
                except AmbiguousWriteError as exc:
                    saved = _call_with_rate_limit(
                        lambda: _read(binding.adapter, operation),
                        max_retries=max_rate_limit_retries,
                        base_delay_seconds=base_delay_seconds,
                        max_delay_seconds=max_delay_seconds,
                        sleep=sleep,
                        random_value=random_value,
                    )
                    if saved is None and operation["action"] != "remove":
                        document = checkpoint_operation(
                            document,
                            operation_id=operation_id,
                            state="uncertain",
                            note="Mutation outcome is ambiguous; no retry was attempted.",
                            timestamp=timestamp(),
                            error=scrub_sensitive_text(str(exc), ephemeral_values)
                            or "ambiguous_write",
                        )
                    else:
                        comparison, safe_saved = build_verification_comparison(operation, saved)
                        if comparison["pass"]:
                            document = checkpoint_operation(
                                document,
                                operation_id=operation_id,
                                state="verified",
                                note="Ambiguous response resolved by authoritative readback.",
                                timestamp=timestamp(),
                                comparison=comparison,
                                saved=safe_saved,
                            )
                        else:
                            document = checkpoint_operation(
                                document,
                                operation_id=operation_id,
                                state="uncertain",
                                note="Ambiguous response did not match saved target; no retry.",
                                timestamp=timestamp(),
                                error="ambiguous_write_mismatch",
                            )
                    _save(run_path, document)
                    progress = True
                    continue
                saved = _call_with_rate_limit(
                    lambda: _read(binding.adapter, operation),
                    max_retries=max_rate_limit_retries,
                    base_delay_seconds=base_delay_seconds,
                    max_delay_seconds=max_delay_seconds,
                    sleep=sleep,
                    random_value=random_value,
                )
                if saved is None and operation["action"] != "remove":
                    document = checkpoint_operation(
                        document,
                        operation_id=operation_id,
                        state="uncertain",
                        note="Write returned without authoritative readback; no retry.",
                        timestamp=timestamp(),
                        error="missing_readback",
                    )
                else:
                    comparison, safe_saved = build_verification_comparison(operation, saved)
                    if comparison["pass"]:
                        document = checkpoint_operation(
                            document,
                            operation_id=operation_id,
                            state="verified",
                            note="Saved object verified by target readback.",
                            timestamp=timestamp(),
                            comparison=comparison,
                            saved=safe_saved,
                        )
                    else:
                        document = checkpoint_operation(
                            document,
                            operation_id=operation_id,
                            state="uncertain",
                            note="Saved readback differs from the intended object; no retry.",
                            timestamp=timestamp(),
                            error="saved_readback_mismatch",
                        )
                _save(run_path, document)
                progress = True
            except AuthenticationError as exc:
                latest = load_document(run_path)
                operation = _operation(latest, operation_id)
                state = "failed" if operation["state"] == "planned" else "uncertain"
                latest = checkpoint_operation(
                    latest,
                    operation_id=operation_id,
                    state=state,
                    note="Authentication failed for this target; independent targets may continue.",
                    timestamp=timestamp(),
                    error=scrub_sensitive_text(str(exc), ephemeral_values),
                )
                _save(run_path, latest)
                progress = True
            except RateLimitError as exc:
                latest = load_document(run_path)
                operation = _operation(latest, operation_id)
                state = "failed" if operation["state"] == "planned" else "uncertain"
                latest = checkpoint_operation(
                    latest,
                    operation_id=operation_id,
                    state=state,
                    note="Rate limit stopped this operation without a blind retry.",
                    timestamp=timestamp(),
                    error=scrub_sensitive_text(str(exc), ephemeral_values),
                )
                _save(run_path, latest)
                progress = True
            except AdapterExecutionError as exc:
                latest = load_document(run_path)
                operation = _operation(latest, operation_id)
                state = "failed" if operation["state"] == "planned" else "uncertain"
                latest = checkpoint_operation(
                    latest,
                    operation_id=operation_id,
                    state=state,
                    note="Target adapter rejected the operation; dependents remain stopped.",
                    timestamp=timestamp(),
                    error=scrub_sensitive_text(str(exc), ephemeral_values),
                )
                _save(run_path, latest)
                progress = True
        if not progress:
            return inspect_document(load_document(run_path))


def execute_ready_operations(
    run_path: Path,
    adapter: ConfigurationAdapter | TargetAdapterRegistry,
    **kwargs: Any,
) -> dict[str, Any]:
    """Dispatch legacy web runs or execute independent v3 target subtrees."""
    document = load_document(run_path)
    if document.get("schema_version") != "3.0":
        return legacy.execute_ready_operations(run_path, adapter, **kwargs)
    if not isinstance(adapter, TargetAdapterRegistry):
        raise AdapterExecutionError("configuration-run@3.0 requires a TargetAdapterRegistry")
    timestamp = kwargs.pop("timestamp", None) or (
        lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )
    max_rate_limit_retries = kwargs.pop("max_rate_limit_retries", 2)
    base_delay_seconds = kwargs.pop("base_delay_seconds", 0.25)
    max_delay_seconds = kwargs.pop("max_delay_seconds", 2.0)
    sleep = kwargs.pop("sleep", time.sleep)
    random_value = kwargs.pop("random_value", random.random)
    if max_rate_limit_retries < 0:
        raise AdapterExecutionError("max_rate_limit_retries must be non-negative")
    if base_delay_seconds < 0 or max_delay_seconds < 0:
        raise AdapterExecutionError("rate-limit delays must be non-negative")
    if kwargs:
        raise AdapterExecutionError(
            "unsupported v3 adapter option(s): " + ", ".join(sorted(kwargs))
        )
    try:
        with run_file_lock(run_path):
            return _execute_v3_locked(
                run_path,
                adapter,
                timestamp=timestamp,
                max_rate_limit_retries=max_rate_limit_retries,
                base_delay_seconds=base_delay_seconds,
                max_delay_seconds=max_delay_seconds,
                sleep=sleep,
                random_value=random_value,
            )
    except legacy.RunConflictError as exc:
        raise AdapterExecutionError(str(exc), code="run_conflict") from exc
