"""Deterministic creation, checkpoints, inspection, and finalization for run@4.0."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import run_validation_web as web_support
from redaction import redact_for_persistence
from resource_registry import (
    ResourceRegistryError,
    required_baseline_families,
    validate_target_family,
)
from run_model import SCHEMA_VERSION, SERVER_RESOURCE_FAMILIES, WEB_RESOURCE_FAMILIES
from run_validation_core import transition_allowed, validate_document
from strict_json import StrictJsonError, load_json
from validate_configuration_contract import ContractValidationError
from validate_configuration_contract import validate_document as validate_contract
from verification import (
    build_pre_write_comparison,
    build_verification_comparison,
    canonical_sha256,
    materialization_fingerprints,
    validate_verification_comparison,
)

RunValidationError = web_support.RunValidationError
RunConflictError = web_support.RunConflictError


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _operation_id(object_key: str) -> str:
    return "OP-" + hashlib.sha256(object_key.encode("utf-8")).hexdigest()[:16].upper()


def _official_sources(contract: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for evidence in contract["evidence"]:
        if evidence["grade"] != "official-current":
            continue
        output.append(
            {
                "url": evidence["locator"],
                "title": evidence["title"],
                "access_date": evidence["accessed_on"],
                "supports": evidence["supports"],
                "decision": evidence["decision"],
            }
        )
    return output


def _external_dependencies(contract: dict[str, Any]) -> list[dict[str, Any]]:
    return deepcopy(contract["external_dependencies"])


def _publication_dependencies(mode: str) -> list[dict[str, Any]]:
    if mode == "web":
        return []
    dependencies = [
        {
            "kind": "server-publication",
            "owner": "external",
            "status": "open",
            "depends_on_kind": None,
            "blocks_saved_configuration": False,
        },
        {
            "kind": "server-recette",
            "owner": "external runtime acceptance owner",
            "status": "open",
            "depends_on_kind": "server-publication",
            "blocks_saved_configuration": False,
        },
    ]
    if mode == "server":
        return dependencies
    return dependencies + [
        {
            "kind": "web-cutover-publication",
            "owner": "external",
            "status": "open",
            "depends_on_kind": "server-recette",
            "blocks_saved_configuration": False,
        },
        {
            "kind": "web-pipeline-recette",
            "owner": "external web/server acceptance owner",
            "status": "open",
            "depends_on_kind": "web-cutover-publication",
            "blocks_saved_configuration": False,
        },
    ]


def create_from_contract(
    contract: dict[str, Any],
    *,
    run_id: str,
    source_locator: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Materialize every active v4 run section deterministically from contract@7.0."""
    try:
        contract = validate_contract(deepcopy(contract))
    except ContractValidationError as exc:
        raise RunValidationError(str(exc), error_code=exc.error_code) from exc
    now = timestamp or _utc_now()
    targets = [
        {
            "target_id": target["target_id"],
            "container_type": target["container_type"],
            "account_id": target["account_id"],
            "container_id": target["container_id"],
            "workspace_id": target["workspace_id"],
            "adapter_capabilities": {},
        }
        for target in contract["targets"]
    ]
    requirement_ids = [item["id"] for item in contract["requirements"]]
    object_items = contract["implementation"]["objects"]
    operation_by_key = {
        item["object_key"]: _operation_id(item["object_key"]) for item in object_items
    }
    object_changes = []
    target_types = {item["target_id"]: item["container_type"] for item in targets}
    requirement_objects: dict[str, list[str]] = {value: [] for value in requirement_ids}
    for item in object_items:
        record = {
            "operation_id": operation_by_key[item["object_key"]],
            "target_id": item["target_id"],
            "container_type": target_types[item["target_id"]],
            "resource_family": item["resource_family"],
            "name": item["name"],
            "object_key": item["object_key"],
            "action": item["action"],
            "requirement_ids": item.get("requirement_ids", []),
            "dependencies": [operation_by_key[value] for value in item.get("depends_on", [])],
            "justification": item["justification"],
            "evidence": item["evidence"],
            "risk": item.get("risk", "routine"),
            "state": "planned",
            "journal": [],
        }
        if "intended" in item:
            record["intended"] = redact_for_persistence(item["intended"])
        for optional in (
            "pre_change",
            "object_id",
            "new_name",
            "approval",
            "replacement_reason",
            "permission_delta",
            "scope",
        ):
            if optional in item:
                record[optional] = redact_for_persistence(item[optional])
        object_changes.append(record)
        for requirement_id in record["requirement_ids"]:
            requirement_objects[requirement_id].append(record["object_key"])
    requirements = []
    for item in contract["requirements"]:
        requirements.append(
            {
                "id": item["id"],
                "kind": item.get("kind", contract["route"]),
                "source_locator": item["authority"]["locator"],
                "source_event": item.get("source_event"),
                "event_name": item.get("event_name"),
                "destination": item.get("destination") or item.get("event_name"),
                "status": "In progress",
                "object_keys": sorted(requirement_objects[item["id"]]),
            }
        )
    from web_domain_validation import materialize_payload_mappings

    payload_mappings = materialize_payload_mappings(contract)
    pipelines = []
    for item in contract["pipelines"]:
        record = deepcopy(item)
        record["claiming_client_operation_id"] = operation_by_key[
            record.pop("claiming_client")["object_key"]
        ]
        record["operation_dependencies"] = [
            operation_by_key[value] for value in record.get("operation_dependencies", [])
        ]
        if "cutover_operation_key" in record:
            record["cutover_operation_id"] = operation_by_key[record.pop("cutover_operation_key")]
        for flow in record.get("event_flows", []):
            flow["server_consumer_operation_ids"] = [
                operation_by_key[value] for value in flow.get("server_consumer_keys", [])
            ]
        pipelines.append(record)
    inventory_dispositions = []
    for item in contract["inventory_dispositions"]:
        record = deepcopy(item)
        operation_keys = record.pop("operation_keys")
        record["operation_ids"] = [operation_by_key[value] for value in operation_keys]
        inventory_dispositions.append(record)
    run = {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "id": run_id,
            "mode": contract["mode"],
            "execution_mode": contract["implementation"]["execution_mode"],
            "phase": "preflight",
            "status": "In progress",
            "started_at": now,
            "updated_at": now,
            "targets": targets,
            "contract": {
                "schema_version": contract["schema_version"],
                "requirement_ids": requirement_ids,
                "source_locator": source_locator,
                "fingerprint": canonical_sha256(contract),
            },
            "publication": {"performed": False, "version_created": False},
            "materialization": {
                "method": "contract-7.0-deterministic",
                "owned_sections": [
                    "targets",
                    "requirements",
                    "pipelines",
                    "object_changes",
                    "payload_mappings",
                    "consent_topologies",
                    "execution_topologies",
                    "page_view_decisions",
                    "first_party_data_routes",
                    "inventory_dispositions",
                    "dedup_contracts",
                    "official_sources",
                    "external_dependencies",
                    "publication_dependencies",
                ],
                "contract_fingerprint": canonical_sha256(contract),
                "section_fingerprints": {},
            },
        },
        "requirements": requirements,
        "pipelines": pipelines,
        "object_changes": object_changes,
        "payload_mappings": payload_mappings,
        "consent_topologies": deepcopy(contract["consent_topologies"]),
        "execution_topologies": deepcopy(contract["execution_topologies"]),
        "page_view_decisions": deepcopy(contract["page_view_decisions"]),
        "first_party_data_routes": deepcopy(contract["first_party_data_routes"]),
        "inventory_dispositions": inventory_dispositions,
        "container_baselines": [
            {
                "target_id": target["target_id"],
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
            for target in targets
        ],
        "dedup_contracts": deepcopy(contract["dedup_contracts"]),
        "saved_readback": [],
        "target_results": [
            {
                "target_id": target["target_id"],
                "status": "In progress",
                "last_verified_operation_id": None,
                "recovery_boundary": None,
            }
            for target in targets
        ],
        "official_sources": _official_sources(contract),
        "external_dependencies": _external_dependencies(contract),
        "publication_dependencies": _publication_dependencies(contract["mode"]),
        "recovery_boundary": None,
        "idempotency": {"checked": False, "remaining_actions": [], "observations": []},
    }
    run["run"]["materialization"]["section_fingerprints"] = materialization_fingerprints(run)
    return validate_document(run)


def load_document(path: Path) -> dict[str, Any]:
    try:
        value = load_json(path)
    except StrictJsonError as exc:
        raise RunValidationError(str(exc), error_code=exc.error_code) from exc
    return validate_document(value)


def _build_target_baseline(
    target: dict[str, Any],
    resources: dict[str, list[dict[str, Any]]],
    *,
    captured_at: str,
    preexisting_workspace_changes: list[dict[str, Any]],
    capture_evidence: dict[str, Any],
) -> dict[str, Any]:
    """Build one redacted, deterministic baseline from exhausted target-family reads."""
    if not isinstance(captured_at, str) or not captured_at.strip():
        raise RunValidationError("baseline captured_at must be a non-empty timestamp")
    if not isinstance(resources, dict) or not resources:
        raise RunValidationError("baseline resources must contain at least one family")
    if not isinstance(preexisting_workspace_changes, list) or any(
        not isinstance(item, dict) for item in preexisting_workspace_changes
    ):
        raise RunValidationError("baseline workspace changes must be an array of objects")
    if not isinstance(capture_evidence, dict) or set(capture_evidence) != {
        "captured_by",
        "source_identity",
        "resource_pagination",
        "workspace_changes_pagination",
    }:
        raise RunValidationError("baseline capture_evidence has missing or unexpected fields")
    if capture_evidence.get("captured_by") != "authenticated-adapter-runtime":
        raise RunValidationError("baseline must be captured by the authenticated adapter runtime")
    source_identity = capture_evidence.get("source_identity")
    expected_identity = {
        field: target[field]
        for field in ("account_id", "container_id", "workspace_id", "container_type")
    }
    if source_identity != expected_identity:
        raise RunValidationError(
            "baseline capture_evidence.source_identity must match the authorized GTM target"
        )
    resource_pagination = capture_evidence.get("resource_pagination")
    if not isinstance(resource_pagination, dict) or set(resource_pagination) != set(resources):
        raise RunValidationError("baseline pagination receipts must cover exactly the resources")
    receipts = [
        *resource_pagination.items(),
        ("workspace changes", capture_evidence.get("workspace_changes_pagination")),
    ]
    for family, receipt in receipts:
        if (
            not isinstance(receipt, dict)
            or set(receipt) != {"pages_read", "exhausted"}
            or not isinstance(receipt.get("pages_read"), int)
            or isinstance(receipt.get("pages_read"), bool)
            or receipt["pages_read"] < 1
            or receipt.get("exhausted") is not True
        ):
            raise RunValidationError(
                f"baseline pagination receipt for {family!r} must prove positive pages and exhaustion"
            )
    container_type = target["container_type"]
    normalized: dict[str, list[dict[str, Any]]] = {}
    for family in sorted(resources):
        try:
            validated_family = validate_target_family(container_type, family)
        except ResourceRegistryError as exc:
            raise RunValidationError(f"baseline resource family is invalid: {exc}") from exc
        items = resources[family]
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise RunValidationError(
                f"baseline resources.{validated_family} must be an array of objects"
            )
        normalized[validated_family] = redact_for_persistence(items)
    safe_changes = redact_for_persistence(preexisting_workspace_changes)
    resource_identities = {
        family: sorted(
            f"{target['target_id']}::{family}::{item['name'].strip()}"
            for item in normalized[family]
            if isinstance(item.get("name"), str) and item["name"].strip()
        )
        for family in sorted(normalized)
    }
    return {
        "target_id": target["target_id"],
        "captured_at": captured_at.strip(),
        "complete": True,
        "resource_families": sorted(normalized),
        "family_counts": {family: len(normalized[family]) for family in sorted(normalized)},
        "resource_identities": resource_identities,
        "resources": normalized,
        "preexisting_workspace_changes": safe_changes,
        "capture_evidence": deepcopy(capture_evidence),
        "fingerprint": f"sha256:{canonical_sha256({'resources': normalized, 'workspace_changes': safe_changes, 'capture_evidence': capture_evidence})}",
    }


def _record_target_baseline(
    document: dict[str, Any],
    *,
    target_id: str,
    resources: dict[str, list[dict[str, Any]]],
    captured_at: str,
    preexisting_workspace_changes: list[dict[str, Any]],
    capture_evidence: dict[str, Any],
) -> dict[str, Any]:
    """Record one baseline before the first write; repeated identical input is a no-op."""
    value = deepcopy(validate_document(document))
    target = next(
        (item for item in value["run"]["targets"] if item["target_id"] == target_id),
        None,
    )
    if target is None:
        raise RunValidationError(f"unknown target_id {target_id!r}")
    required_families = required_baseline_families(
        [item for item in value["object_changes"] if item["target_id"] == target_id],
        target["container_type"],
    )
    if not required_families <= set(resources):
        raise RunValidationError(
            f"baseline misses planned resource families: {sorted(required_families - set(resources))}"
        )
    if value["run"]["execution_mode"] == "refonte-durable":
        expected_families = (
            WEB_RESOURCE_FAMILIES if target["container_type"] == "web" else SERVER_RESOURCE_FAMILIES
        )
        if set(resources) != expected_families:
            raise RunValidationError(
                "refonte baseline must exhaust the complete target resource surface; "
                f"missing={sorted(expected_families - set(resources))}, "
                f"extra={sorted(set(resources) - expected_families)}"
            )
    started = [
        item["operation_id"]
        for item in value["object_changes"]
        if item["target_id"] == target_id and (item["state"] != "planned" or item["journal"])
    ]
    if started:
        raise RunConflictError(
            "target baseline must be recorded before mutation: " + ", ".join(started)
        )
    baseline = _build_target_baseline(
        target,
        resources,
        captured_at=captured_at,
        preexisting_workspace_changes=preexisting_workspace_changes,
        capture_evidence=capture_evidence,
    )
    index = next(
        index
        for index, item in enumerate(value["container_baselines"])
        if item["target_id"] == target_id
    )
    current = value["container_baselines"][index]
    if current.get("complete") is True:
        if current == baseline:
            return value
        raise RunConflictError(f"target {target_id!r} already has a different complete baseline")
    value["container_baselines"][index] = baseline
    value["run"]["updated_at"] = captured_at.strip()
    return validate_document(value)


def _operation(document: dict[str, Any], operation_id: str) -> dict[str, Any]:
    for operation in document["object_changes"]:
        if operation["operation_id"] == operation_id:
            return operation
    raise RunValidationError(f"unknown operation_id {operation_id!r}")


def checkpoint_operation(
    document: dict[str, Any],
    *,
    operation_id: str,
    state: str,
    note: str,
    timestamp: str | None = None,
    result: dict[str, Any] | None = None,
    comparison: dict[str, Any] | None = None,
    pre_write_comparison: dict[str, Any] | None = None,
    pre_write_saved: Any = None,
    saved: Any = None,
    error: str | None = None,
) -> dict[str, Any]:
    value = deepcopy(validate_document(document))
    operation = _operation(value, operation_id)
    current = operation["state"]
    if state in {"in_progress", "saved", "verified"} and not any(
        baseline["target_id"] == operation["target_id"] and baseline.get("complete") is True
        for baseline in value["container_baselines"]
    ):
        raise RunValidationError(
            "target baseline must be complete before execution or verification"
        )
    if state in {"in_progress", "saved", "verified"}:
        dependency_states = {
            item["operation_id"]: item["state"] for item in value["object_changes"]
        }
        if any(dependency_states[key] != "verified" for key in operation["dependencies"]):
            raise RunValidationError("every dependency must be verified before execution")
    if not transition_allowed(current, state):
        raise RunValidationError(f"operation transition {current!r} -> {state!r} is not allowed")
    delta_actions = {
        "update",
        "replace",
        "rename",
        "pause",
        "unpause",
        "remove",
    }
    if (
        current == "planned"
        and state in {"in_progress", "saved", "verified"}
        and operation["action"] in delta_actions
    ):
        rebuilt, safe_pre_write = build_pre_write_comparison(operation, pre_write_saved)
        if pre_write_comparison is not None and rebuilt != pre_write_comparison:
            raise RunValidationError(
                "supplied pre-write comparison is not bound to authoritative readback"
            )
        if not rebuilt["pass"]:
            raise RunValidationError("fresh saved state does not match pre_change")
        operation["pre_write_readback"] = safe_pre_write
        operation["pre_write_comparison"] = rebuilt
    elif pre_write_comparison is not None or pre_write_saved is not None:
        raise RunValidationError(
            "pre-write evidence is accepted only for a planned delta write boundary"
        )
    if state not in {"saved", "verified"} and saved is not None:
        raise RunValidationError("saved readback is accepted only for saved or verified states")
    if state != "verified" and comparison is not None:
        raise RunValidationError("comparison evidence is accepted only for a verified state")
    if state == "saved" and saved is None:
        raise RunValidationError("saved requires authoritative saved readback")
    if state == "verified" and saved is None and operation["action"] != "remove":
        raise RunValidationError("verified requires authoritative saved readback")
    if (
        state == "verified"
        and operation["action"] in delta_actions
        and "pre_write_comparison" not in operation
    ):
        raise RunValidationError("verified delta operation lacks pre-write drift evidence")
    safe_saved = redact_for_persistence(saved) if saved is not None else None
    if state == "verified":
        try:
            if comparison is None:
                comparison, safe_saved = build_verification_comparison(operation, saved)
            validate_verification_comparison(operation, comparison, saved)
        except ValueError as exc:
            raise RunValidationError(str(exc)) from exc
        if comparison["pass"] is not True:
            raise RunValidationError("verified comparison must pass")
        operation["comparison"] = deepcopy(comparison)
        operation["saved_readback"] = safe_saved
        value["saved_readback"].append(
            {
                "target_id": operation["target_id"],
                "operation_id": operation_id,
                "object_key": operation["object_key"],
                "saved": safe_saved,
                "comparison": deepcopy(comparison),
            }
        )
    elif state == "saved":
        operation["saved_readback"] = safe_saved
    operation["state"] = state
    operation["journal"].append(
        {
            "at": timestamp or _utc_now(),
            "state": state,
            "note": note,
            "result": redact_for_persistence(result),
            "error": redact_for_persistence(error),
        }
    )
    value["run"]["updated_at"] = timestamp or _utc_now()
    value["run"]["phase"] = "readback" if state in {"saved", "verified"} else "mutation"
    _derive_live_status(value)
    return validate_document(value)


def reopen_failed_operation(
    document: dict[str, Any],
    *,
    operation_id: str,
    note: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    value = deepcopy(validate_document(document))
    operation = _operation(value, operation_id)
    if operation["state"] != "failed":
        raise RunValidationError("only a known failed operation can be reopened")
    for field in (
        "comparison",
        "saved_readback",
        "pre_write_readback",
        "pre_write_comparison",
    ):
        operation.pop(field, None)
    value["saved_readback"] = [
        item for item in value["saved_readback"] if item.get("operation_id") != operation_id
    ]
    operation["state"] = "planned"
    operation["journal"].append(
        {"at": timestamp or _utc_now(), "state": "planned", "note": note, "reopened": True}
    )
    value["run"]["updated_at"] = timestamp or _utc_now()
    _derive_live_status(value)
    return validate_document(value)


def _derive_live_status(document: dict[str, Any]) -> None:
    for result in document["target_results"]:
        operations = [
            item for item in document["object_changes"] if item["target_id"] == result["target_id"]
        ]
        states = {item["state"] for item in operations}
        verified = [item for item in operations if item["state"] == "verified"]
        result["last_verified_operation_id"] = verified[-1]["operation_id"] if verified else None
        if states & {"uncertain"}:
            result["status"] = "Partial"
        elif states & {"failed"}:
            result["status"] = "Partial" if verified else "Blocked"
        elif "skipped" in states:
            result["status"] = "Partial" if verified else "Deferred"
        elif states <= {"verified"} and operations:
            result["status"] = "In progress"
        else:
            result["status"] = "In progress"
    statuses = {item["status"] for item in document["target_results"]}
    if "Partial" in statuses:
        document["run"]["status"] = "Partial"
    elif "Blocked" in statuses:
        any_progress = any(
            item["state"] in {"verified", "saved", "in_progress"}
            for item in document["object_changes"]
        )
        document["run"]["status"] = "Partial" if any_progress else "Blocked"
    elif "Deferred" in statuses:
        any_progress = any(
            item["state"] in {"verified", "saved", "in_progress"}
            for item in document["object_changes"]
        )
        document["run"]["status"] = "Partial" if any_progress else "Deferred"
    else:
        document["run"]["status"] = "In progress"
    for result in document["target_results"]:
        pending = [
            item["operation_id"]
            for item in document["object_changes"]
            if item["target_id"] == result["target_id"]
            and item["state"] in {"failed", "uncertain", "saved", "in_progress"}
        ]
        result["recovery_boundary"] = (
            {"operation_ids": pending, "next_action": "authoritative readback before retry"}
            if pending
            else None
        )
    boundaries = [item for item in document["target_results"] if item["recovery_boundary"]]
    document["recovery_boundary"] = {"targets": deepcopy(boundaries)} if boundaries else None


def inspect_document(document: dict[str, Any]) -> dict[str, Any]:
    value = validate_document(document)
    states = {item["operation_id"]: item["state"] for item in value["object_changes"]}
    ready: list[str] = []
    waiting: dict[str, list[str]] = {}
    blocked: dict[str, list[str]] = {}
    missing_baselines = {
        item["target_id"]
        for item in value["container_baselines"]
        if item.get("complete") is not True
    }
    authentication_blocked = {
        item["target_id"]
        for item in value["object_changes"]
        if item["state"] in {"failed", "uncertain"}
        and item.get("journal")
        and str(item["journal"][-1].get("error", "")).startswith("authentication_required:")
    }
    for operation in value["object_changes"]:
        if operation["state"] != "planned":
            continue
        if operation["target_id"] in missing_baselines:
            blocked[operation["operation_id"]] = ["complete target baseline required"]
            continue
        if operation["target_id"] in authentication_blocked:
            blocked[operation["operation_id"]] = ["target authentication requires revalidation"]
            continue
        dependencies = operation["dependencies"]
        failed = [
            value for value in dependencies if states[value] in {"failed", "uncertain", "skipped"}
        ]
        pending = [value for value in dependencies if states[value] != "verified"]
        if failed:
            blocked[operation["operation_id"]] = failed
        elif pending:
            waiting[operation["operation_id"]] = pending
        else:
            ready.append(operation["operation_id"])
    unsafe = [
        item["operation_id"]
        for item in value["object_changes"]
        if item["state"] in {"in_progress", "saved", "uncertain"}
    ]
    return {
        "pass": value["run"]["status"] == "Configured",
        "valid": True,
        "schema_version": value["schema_version"],
        "mode": value["run"]["mode"],
        "status": value["run"]["status"],
        "ready_operations": sorted(ready),
        "waiting_operations": waiting,
        "blocked_operations": blocked,
        "unsafe_operations": unsafe,
        "target_results": deepcopy(value["target_results"]),
        "resumable": not unsafe,
    }


def _parse_instant(value: Any, path: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise RunValidationError(f"{path} is required")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise RunValidationError(f"{path} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise RunValidationError(f"{path} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _record_adapter_idempotency_observations(
    document: dict[str, Any],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist convergence reads produced by the target-verified adapter runtime."""
    value = deepcopy(validate_document(document))
    operations = {item["operation_id"]: item for item in value["object_changes"]}
    if any(item["state"] != "verified" for item in operations.values()):
        raise RunValidationError("idempotency convergence requires every operation verified")
    if not isinstance(observations, list) or len(observations) != len(operations):
        raise RunValidationError("idempotency convergence requires one observation per operation")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    remaining: list[str] = []
    for index, observation in enumerate(observations):
        if not isinstance(observation, dict) or set(observation) != {
            "operation_id",
            "target_id",
            "source",
            "source_identity",
            "observed_at",
            "saved",
        }:
            raise RunValidationError(
                f"idempotency observation {index} has missing or unexpected fields"
            )
        operation_id = observation["operation_id"]
        if operation_id in seen or operation_id not in operations:
            raise RunValidationError(f"idempotency observation {index} is unknown or duplicated")
        seen.add(operation_id)
        operation = operations[operation_id]
        if observation["target_id"] != operation["target_id"]:
            raise RunValidationError(f"idempotency observation {index} target differs")
        if observation["source"] != "target-adapter-read":
            raise RunValidationError(
                f"idempotency observation {index} must come from a target adapter read"
            )
        observed_at = observation["observed_at"]
        observed_instant = _parse_instant(
            observed_at, f"idempotency observation {index} observed_at"
        )
        latest_verified = max(
            _parse_instant(entry["at"], f"operation {operation_id!r} journal timestamp")
            for entry in operation["journal"]
            if entry.get("state") == "verified"
        )
        if observed_instant <= latest_verified:
            raise RunValidationError(
                f"idempotency observation {index} must be newer than verification"
            )
        source_identity = observation["source_identity"]
        expected_identity = {
            field: target[field]
            for target in value["run"]["targets"]
            if target["target_id"] == operation["target_id"]
            for field in ("account_id", "container_id", "workspace_id", "container_type")
        }
        if source_identity != expected_identity:
            raise RunValidationError(
                f"idempotency observation {index} source identity differs from its authorized target"
            )
        comparison, safe_saved = build_verification_comparison(operation, observation["saved"])
        decision = "no-op" if comparison["pass"] else "mutation-required"
        if decision != "no-op":
            remaining.append(operation_id)
        records.append(
            {
                "operation_id": operation_id,
                "target_id": operation["target_id"],
                "source": "target-adapter-read",
                "source_identity": deepcopy(source_identity),
                "observed_at": observed_at,
                "decision": decision,
                "saved": safe_saved,
                "comparison": comparison,
            }
        )
    if seen != set(operations):
        raise RunValidationError("idempotency convergence did not cover every operation")
    value["idempotency"] = {
        "checked": not remaining,
        "remaining_actions": sorted(remaining),
        "observations": records,
    }
    if remaining:
        remaining_set = set(remaining)
        value["saved_readback"] = [
            item
            for item in value["saved_readback"]
            if item.get("operation_id") not in remaining_set
        ]
        for operation_id in remaining:
            operation = operations[operation_id]
            for field in (
                "comparison",
                "saved_readback",
                "pre_write_readback",
                "pre_write_comparison",
            ):
                operation.pop(field, None)
            operation["state"] = "planned"
            operation["journal"].append(
                {
                    "at": next(
                        record["observed_at"]
                        for record in records
                        if record["operation_id"] == operation_id
                    ),
                    "state": "planned",
                    "note": "Fresh convergence readback requires the authorized operation again.",
                    "convergence_repair": True,
                }
            )
        _derive_live_status(value)
    return validate_document(value)


def _finalize_adapter_verified_document(
    document: dict[str, Any],
    *,
    timestamp: str | None = None,
) -> dict[str, Any]:
    value = deepcopy(validate_document(document))
    incomplete = [
        item["operation_id"] for item in value["object_changes"] if item["state"] != "verified"
    ]
    if incomplete:
        raise RunValidationError(
            "cannot finalize with incomplete operations: " + ", ".join(incomplete)
        )
    incomplete_baselines = [
        item["target_id"]
        for item in value["container_baselines"]
        if item.get("complete") is not True
    ]
    if incomplete_baselines:
        raise RunValidationError(
            "cannot finalize without complete target baselines: " + ", ".join(incomplete_baselines)
        )
    if value["idempotency"]["checked"] is not True or value["idempotency"]["remaining_actions"]:
        raise RunValidationError("Configured requires adapter-backed identical-rerun no-op proof")
    unresolved = [
        f"{row['requirement_id']}::{row['destination_field']}"
        for row in value["payload_mappings"]
        if row["status"] in {"pending", "blocked"}
    ]
    unresolved.extend(
        f"{pipeline['pipeline_id']}::{field['destination']['path']}"
        for pipeline in value["pipelines"]
        for field in pipeline["field_flows"]
        if field["status"] != "proved"
    )
    if unresolved:
        raise RunValidationError(
            "cannot finalize unresolved field mappings: " + ", ".join(unresolved)
        )
    for result in value["target_results"]:
        result["status"] = "Configured"
        result["recovery_boundary"] = None
    for requirement in value["requirements"]:
        requirement["status"] = "Configured"
    value["run"]["phase"] = "complete"
    value["run"]["status"] = "Configured"
    value["run"]["updated_at"] = timestamp or _utc_now()
    value["recovery_boundary"] = None
    return validate_document(value)
