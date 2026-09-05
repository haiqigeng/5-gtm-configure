#!/usr/bin/env python3
"""Target-aware adapter execution with dependency-only failure containment."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import adapter_support
import run_state
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
from resource_registry import (
    capability_matrix,
    is_configuration_settings_mutation,
    required_baseline_families,
    unsupported_operation_reason,
)
from web_domain_validation import configuration_settings_consumers

AdapterExecutionError = adapter_support.AdapterExecutionError
RateLimitError = adapter_support.RateLimitError
AuthenticationError = adapter_support.AuthenticationError
AmbiguousWriteError = adapter_support.AmbiguousWriteError
ConfigurationAdapter = adapter_support.ConfigurationAdapter
collect_paginated = adapter_support.collect_paginated
collect_resource_baseline = adapter_support.collect_resource_baseline


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class TargetAdapter(Protocol):
    """Semantic adapter bound to exactly one authorized GTM target."""

    def identity(self) -> dict[str, str]: ...

    def read(self, operation: dict[str, Any]) -> dict[str, Any] | None: ...

    def mutate(self, operation: dict[str, Any]) -> dict[str, Any] | None: ...

    def list_resource_page(self, resource_family: str, cursor: str | None) -> dict[str, Any]: ...

    def list_workspace_changes_page(self, cursor: str | None) -> dict[str, Any]: ...


@dataclass(frozen=True)
class TargetBinding:
    adapter: TargetAdapter
    identity: dict[str, str]
    capabilities: dict[str, dict[str, bool]]
    secret_provider: SecretProvider | None


_IDENTITY_FIELDS = ("account_id", "container_id", "workspace_id", "container_type")


def _verified_adapter_identity(target: dict[str, Any], adapter: TargetAdapter) -> dict[str, str]:
    try:
        observed = adapter.identity()
    except Exception as exc:
        raise AdapterExecutionError(
            "target adapter identity could not be read",
            code="target_identity_unavailable",
        ) from exc
    if not isinstance(observed, dict) or set(observed) != set(_IDENTITY_FIELDS):
        raise AdapterExecutionError(
            "target adapter identity must contain only account_id, container_id, workspace_id, and container_type",
            code="target_identity_invalid",
        )
    normalized: dict[str, str] = {}
    for field in _IDENTITY_FIELDS:
        value = observed.get(field)
        if not isinstance(value, str) or not value.strip():
            raise AdapterExecutionError(
                f"target adapter identity {field!r} is missing",
                code="target_identity_invalid",
            )
        normalized[field] = value.strip()
    expected = {field: str(target[field]).strip() for field in _IDENTITY_FIELDS}
    if normalized != expected:
        raise AdapterExecutionError(
            "authenticated adapter identity differs from the authorized GTM target",
            code="target_identity_mismatch",
        )
    return normalized


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
        identity = _verified_adapter_identity(target, adapter)
        self._bindings[target_id] = TargetBinding(
            adapter=adapter,
            identity=identity,
            capabilities=capability_matrix(target, capabilities),
            secret_provider=secret_provider,
        )

    def binding(self, target_id: str) -> TargetBinding:
        try:
            binding = self._bindings[target_id]
        except KeyError as exc:
            raise AdapterExecutionError(
                f"no adapter is registered for target {target_id!r}", code="target_unavailable"
            ) from exc
        _verified_adapter_identity(binding.identity, binding.adapter)
        return binding

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
            delay = adapter_support._retry_delay(
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


def _capture_one_authenticated_baseline(
    document: dict[str, Any],
    target: dict[str, Any],
    binding: TargetBinding,
    *,
    captured_at: Callable[[], str],
    max_rate_limit_retries: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    sleep: Callable[[float], None],
    random_value: Callable[[], float],
) -> dict[str, Any]:
    target_id = target["target_id"]
    target_operations = [
        item for item in document["object_changes"] if item["target_id"] == target_id
    ]
    families = sorted(
        family
        for family, capabilities in binding.capabilities.items()
        if capabilities.get("list") is True
    )
    required_families = required_baseline_families(target_operations, target["container_type"])
    if not required_families <= set(families):
        missing = sorted(required_families - set(families))
        raise AdapterExecutionError(
            f"authenticated baseline cannot list required resource families: {missing}",
            code="baseline_capability_missing",
        )
    resources: dict[str, list[dict[str, Any]]] = {}
    resource_receipts: dict[str, dict[str, Any]] = {}
    for family in families:
        items, receipt = adapter_support.collect_paginated_with_receipt(
            lambda cursor, selected=family: binding.adapter.list_resource_page(selected, cursor),
            max_rate_limit_retries=max_rate_limit_retries,
            base_retry_delay_seconds=base_delay_seconds,
            max_retry_delay_seconds=max_delay_seconds,
            sleep=sleep,
            random_value=random_value,
        )
        resources[family] = items
        resource_receipts[family] = receipt
    workspace_changes, changes_receipt = adapter_support.collect_paginated_with_receipt(
        binding.adapter.list_workspace_changes_page,
        max_rate_limit_retries=max_rate_limit_retries,
        base_retry_delay_seconds=base_delay_seconds,
        max_retry_delay_seconds=max_delay_seconds,
        sleep=sleep,
        random_value=random_value,
    )
    value = deepcopy(document)
    for index, baseline in enumerate(value["container_baselines"]):
        if baseline["target_id"] == target_id:
            value["container_baselines"][index] = {
                "target_id": target_id,
                "captured_at": None,
                "complete": False,
                "resource_families": [],
                "family_counts": {},
                "resource_identities": {},
                "resources": {},
                "preexisting_workspace_changes": None,
                "capture_evidence": None,
                "fingerprint": None,
            }
            break
    return run_state._record_target_baseline(
        value,
        target_id=target_id,
        resources=resources,
        captured_at=captured_at(),
        preexisting_workspace_changes=workspace_changes,
        capture_evidence={
            "captured_by": "authenticated-adapter-runtime",
            "source_identity": deepcopy(binding.identity),
            "resource_pagination": resource_receipts,
            "workspace_changes_pagination": changes_receipt,
        },
    )


def _capture_authenticated_baselines(
    document: dict[str, Any],
    registry: TargetAdapterRegistry,
    **options: Any,
) -> dict[str, Any]:
    """Capture each target independently before any mutation on that target."""
    value = deepcopy(document)
    for target in value["run"]["targets"]:
        target_operations = [
            item for item in value["object_changes"] if item["target_id"] == target["target_id"]
        ]
        if not target_operations or any(item["state"] != "planned" for item in target_operations):
            continue
        try:
            binding = registry.binding(target["target_id"])
            value = _capture_one_authenticated_baseline(value, target, binding, **options)
        except Exception as exc:
            error = "baseline_capture_failed: " + (
                scrub_sensitive_text(str(exc), set()) or "authenticated baseline unavailable"
            )
            for operation in target_operations:
                value = checkpoint_operation(
                    value,
                    operation_id=operation["operation_id"],
                    state="failed",
                    note="Authenticated baseline capture failed; no write was attempted.",
                    timestamp=options["captured_at"](),
                    error=error,
                )
    return value


def _execute_current_locked(
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

    document = _capture_authenticated_baselines(
        document,
        registry,
        captured_at=timestamp,
        max_rate_limit_retries=max_rate_limit_retries,
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
        sleep=sleep,
        random_value=random_value,
    )
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
            if operation_id not in inspect_document(document)["ready_operations"]:
                continue
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
            write_accepted_or_ambiguous = False
            try:
                if operation["container_type"] == "web" and is_configuration_settings_mutation(
                    operation
                ):
                    if not binding.capabilities.get("tag", {}).get("list"):
                        raise AdapterExecutionError(
                            "shared Configuration Settings require tag-list capability"
                        )
                    current_tags = collect_paginated(
                        lambda cursor: binding.adapter.list_resource_page("tag", cursor),
                        max_rate_limit_retries=max_rate_limit_retries,
                        base_retry_delay_seconds=base_delay_seconds,
                        max_retry_delay_seconds=max_delay_seconds,
                        sleep=sleep,
                        random_value=random_value,
                    )
                    in_scope_names = {
                        item["name"]
                        for item in document["object_changes"]
                        if item["target_id"] == operation["target_id"]
                        and item["resource_family"] == "tag"
                    }
                    missing_consumers = (
                        configuration_settings_consumers(operation, current_tags) - in_scope_names
                    )
                    if missing_consumers:
                        raise AdapterExecutionError(
                            "shared Configuration Settings have unreviewed current consumers: "
                            + ", ".join(sorted(missing_consumers))
                        )
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
                    _verified_adapter_identity(binding.identity, binding.adapter)
                    _call_with_rate_limit(
                        lambda: binding.adapter.mutate(deepcopy(mutation_operation)),
                        max_retries=max_rate_limit_retries,
                        base_delay_seconds=base_delay_seconds,
                        max_delay_seconds=max_delay_seconds,
                        sleep=sleep,
                        random_value=random_value,
                    )
                    write_accepted_or_ambiguous = True
                except AmbiguousWriteError as exc:
                    write_accepted_or_ambiguous = True
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
                    error="authentication_required: "
                    + (
                        scrub_sensitive_text(str(exc), ephemeral_values)
                        or "target authorization unavailable"
                    ),
                )
                _save(run_path, latest)
                progress = True
            except ValueError as exc:
                latest = load_document(run_path)
                operation = _operation(latest, operation_id)
                state = "failed" if operation["state"] == "planned" else "uncertain"
                latest = checkpoint_operation(
                    latest,
                    operation_id=operation_id,
                    state=state,
                    note="Adapter readback could not be normalized or compared safely.",
                    timestamp=timestamp(),
                    error="invalid_adapter_readback: "
                    + scrub_sensitive_text(str(exc), ephemeral_values),
                )
                _save(run_path, latest)
                progress = True
            except RateLimitError as exc:
                latest = load_document(run_path)
                latest = checkpoint_operation(
                    latest,
                    operation_id=operation_id,
                    state="uncertain" if write_accepted_or_ambiguous else "failed",
                    note="Rate limit stopped this operation; preserve uncertainty if a write may have succeeded.",
                    timestamp=timestamp(),
                    error=scrub_sensitive_text(str(exc), ephemeral_values),
                )
                _save(run_path, latest)
                progress = True
            except AdapterExecutionError as exc:
                latest = load_document(run_path)
                latest = checkpoint_operation(
                    latest,
                    operation_id=operation_id,
                    state="uncertain" if write_accepted_or_ambiguous else "failed",
                    note="Adapter failure stopped this operation; preserve uncertainty if a write may have succeeded.",
                    timestamp=timestamp(),
                    error=scrub_sensitive_text(str(exc), ephemeral_values),
                )
                _save(run_path, latest)
                progress = True
            except Exception as exc:
                latest = load_document(run_path)
                operation = _operation(latest, operation_id)
                state = "failed" if operation["state"] == "planned" else "uncertain"
                latest = checkpoint_operation(
                    latest,
                    operation_id=operation_id,
                    state=state,
                    note="Unexpected adapter failure stopped this operation; dependents remain stopped.",
                    timestamp=timestamp(),
                    error="unexpected_adapter_failure: "
                    + scrub_sensitive_text(str(exc), ephemeral_values),
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
    """Execute independent target subtrees for the current run schema."""
    if not isinstance(adapter, TargetAdapterRegistry):
        raise AdapterExecutionError("configuration-run@4.0 requires a TargetAdapterRegistry")
    timestamp = kwargs.pop("timestamp", None) or _utc_now
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
            "unsupported current adapter option(s): " + ", ".join(sorted(kwargs))
        )
    try:
        with run_file_lock(run_path):
            return _execute_current_locked(
                run_path,
                adapter,
                timestamp=timestamp,
                max_rate_limit_retries=max_rate_limit_retries,
                base_delay_seconds=base_delay_seconds,
                max_delay_seconds=max_delay_seconds,
                sleep=sleep,
                random_value=random_value,
            )
    except adapter_support.RunConflictError as exc:
        raise AdapterExecutionError(str(exc), code="run_conflict") from exc


def verify_idempotent_rerun(
    run_path: Path,
    registry: TargetAdapterRegistry,
    *,
    timestamp: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Perform a read-only second pass and persist its convergence decisions."""
    now = timestamp or _utc_now
    try:
        with run_file_lock(run_path):
            document = load_document(run_path)
            if any(operation["state"] != "verified" for operation in document["object_changes"]):
                raise AdapterExecutionError(
                    "idempotency convergence requires every operation verified",
                    code="run_not_verified",
                )
            observations = []
            for operation in document["object_changes"]:
                binding = registry.binding(operation["target_id"])
                try:
                    saved = _read(binding.adapter, operation)
                except Exception as exc:
                    raise AdapterExecutionError(
                        "target adapter convergence read failed; no result was persisted",
                        code="convergence_read_failed",
                    ) from exc
                observations.append(
                    {
                        "operation_id": operation["operation_id"],
                        "target_id": operation["target_id"],
                        "source": "target-adapter-read",
                        "source_identity": deepcopy(binding.identity),
                        "observed_at": now(),
                        "saved": saved,
                    }
                )
            document = run_state._record_adapter_idempotency_observations(document, observations)
            if document["idempotency"]["checked"]:
                document = run_state._finalize_adapter_verified_document(document, timestamp=now())
            _save(run_path, document)
            return deepcopy(document["idempotency"])
    except adapter_support.RunConflictError as exc:
        raise AdapterExecutionError(str(exc), code="run_conflict") from exc
