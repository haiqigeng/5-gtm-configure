"""Shared configuration-run@4.0 structure, state, and target validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from action_contract import validate_action_contract
from redaction import sensitive_paths
from resource_registry import (
    ResourceRegistryError,
    required_baseline_families,
    semantic_object_key,
    validate_target_family,
)
from run_model import (
    ACTIONS,
    ALLOWED_TRANSITIONS,
    EXECUTION_MODES,
    MUTATING_ACTIONS,
    OPERATION_STATES,
    REQUIREMENT_STATUSES,
    RUN_MODES,
    RUN_PHASES,
    RUN_STATUSES,
    SCHEMA_VERSION,
    SERVER_RESOURCE_FAMILIES,
    TARGET_STATUSES,
    TARGET_TYPES,
    TOP_LEVEL_KEYS,
    WEB_RESOURCE_FAMILIES,
)
from run_validation_pipeline import validate_pipeline_run
from run_validation_server import validate_server_operations
from run_validation_web import RunValidationError, _timestamp
from verification import (
    build_pre_write_comparison,
    canonical_sha256,
    materialization_fingerprints,
    validate_verification_comparison,
)
from web_domain_validation import validate_web_domain


def _fail(message: str) -> None:
    raise RunValidationError(message)


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{path} must be an object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(f"{path} must be an array")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{path} must be a non-empty string")
    return value.strip()


def _unique(values: Any, path: str) -> list[str]:
    items = [_text(value, f"{path}[]") for value in _array(values, path)]
    if len(set(items)) != len(items):
        _fail(f"{path} contains duplicate values")
    return items


def _validate_header(document: dict[str, Any]) -> tuple[dict[str, str], set[str]]:
    if document.get("schema_version") != SCHEMA_VERSION:
        _fail(f"$.schema_version must be {SCHEMA_VERSION!r}")
    missing = sorted(TOP_LEVEL_KEYS - set(document))
    extra = sorted(set(document) - TOP_LEVEL_KEYS)
    if missing:
        _fail("missing top-level key(s): " + ", ".join(missing))
    if extra:
        _fail("unexpected top-level key(s): " + ", ".join(extra))
    run = _object(document["run"], "$.run")
    required_run = {
        "id",
        "mode",
        "execution_mode",
        "phase",
        "status",
        "started_at",
        "updated_at",
        "targets",
        "contract",
        "publication",
        "materialization",
    }
    if set(run) != required_run:
        _fail("$.run has missing or unexpected fields")
    _text(run["id"], "$.run.id")
    if run["mode"] not in RUN_MODES:
        _fail("$.run.mode is unsupported")
    if run["execution_mode"] not in EXECUTION_MODES:
        _fail("$.run.execution_mode is unsupported")
    if run["phase"] not in RUN_PHASES:
        _fail("$.run.phase is unsupported")
    if run["status"] not in RUN_STATUSES:
        _fail("$.run.status is unsupported")
    publication = _object(run["publication"], "$.run.publication")
    if publication != {"performed": False, "version_created": False}:
        _fail("$.run.publication must prove no publish and no version creation")
    contract = _object(run["contract"], "$.run.contract")
    for field in ("schema_version", "source_locator", "fingerprint"):
        _text(contract.get(field), f"$.run.contract.{field}")
    requirement_ids = set(
        _unique(contract.get("requirement_ids"), "$.run.contract.requirement_ids")
    )
    materialization = _object(run["materialization"], "$.run.materialization")
    _text(materialization.get("method"), "$.run.materialization.method")
    _text(
        materialization.get("contract_fingerprint"),
        "$.run.materialization.contract_fingerprint",
    )
    _array(materialization.get("owned_sections"), "$.run.materialization.owned_sections")
    _object(
        materialization.get("section_fingerprints"),
        "$.run.materialization.section_fingerprints",
    )
    target_types: dict[str, str] = {}
    for index, value in enumerate(_array(run["targets"], "$.run.targets")):
        path = f"$.run.targets[{index}]"
        target = _object(value, path)
        if set(target) != {
            "target_id",
            "container_type",
            "account_id",
            "container_id",
            "workspace_id",
            "adapter_capabilities",
        }:
            _fail(f"{path} has missing or unexpected fields")
        target_id = _text(target.get("target_id"), f"{path}.target_id")
        if target_id in target_types:
            _fail(f"duplicate target_id {target_id!r}")
        container_type = target.get("container_type")
        if container_type not in TARGET_TYPES:
            _fail(f"{path}.container_type is unsupported")
        for field in ("account_id", "container_id", "workspace_id"):
            _text(target.get(field), f"{path}.{field}")
        capabilities = _object(target.get("adapter_capabilities"), f"{path}.adapter_capabilities")
        if any(not isinstance(item, dict) for item in capabilities.values()):
            _fail(f"{path}.adapter_capabilities values must be objects")
        target_types[target_id] = container_type
    if not target_types:
        _fail("$.run.targets must not be empty")
    target_values = set(target_types.values())
    if run["mode"] == "web" and target_values != {"web"}:
        _fail("web mode requires only web targets")
    if run["mode"] == "server" and target_values != {"server"}:
        _fail("server mode requires only server targets")
    if run["mode"] == "pipeline" and target_values != TARGET_TYPES:
        _fail("pipeline mode requires web and server targets")
    return target_types, requirement_ids


def _validate_requirements(document: dict[str, Any], expected: set[str]) -> None:
    found: set[str] = set()
    for index, value in enumerate(_array(document["requirements"], "$.requirements")):
        path = f"$.requirements[{index}]"
        requirement = _object(value, path)
        requirement_id = _text(requirement.get("id"), f"{path}.id")
        if requirement_id in found:
            _fail(f"duplicate requirement id {requirement_id!r}")
        found.add(requirement_id)
        if requirement.get("status") not in REQUIREMENT_STATUSES:
            _fail(f"{path}.status is unsupported")
        object_keys = _unique(requirement.get("object_keys", []), f"{path}.object_keys")
        if not object_keys:
            _fail(f"{path}.object_keys must bind every included requirement to implementation")
    if found != expected:
        _fail("$.requirements IDs must equal $.run.contract.requirement_ids")


def _validate_operations(
    document: dict[str, Any], target_types: dict[str, str], requirement_ids: set[str]
) -> dict[str, dict[str, Any]]:
    requirement_locators = {item["id"]: item["source_locator"] for item in document["requirements"]}
    operations: dict[str, dict[str, Any]] = {}
    keys: set[str] = set()
    allowed_fields = {
        "operation_id",
        "target_id",
        "container_type",
        "resource_family",
        "name",
        "object_key",
        "action",
        "requirement_ids",
        "dependencies",
        "justification",
        "intended",
        "pre_change",
        "object_id",
        "new_name",
        "approval",
        "replacement_reason",
        "permission_delta",
        "scope",
        "evidence",
        "risk",
        "state",
        "journal",
        "comparison",
        "saved_readback",
        "pre_write_readback",
        "pre_write_comparison",
    }
    for index, value in enumerate(_array(document["object_changes"], "$.object_changes")):
        path = f"$.object_changes[{index}]"
        operation = _object(value, path)
        unexpected = sorted(set(operation) - allowed_fields)
        if unexpected:
            _fail(f"{path} has unexpected key(s): {', '.join(unexpected)}")
        operation_id = _text(operation.get("operation_id"), f"{path}.operation_id")
        _text(operation.get("justification"), f"{path}.justification")
        if operation_id in operations:
            _fail(f"duplicate operation_id {operation_id!r}")
        target_id = _text(operation.get("target_id"), f"{path}.target_id")
        if target_id not in target_types:
            _fail(f"{path}.target_id is unknown")
        if operation.get("container_type") != target_types[target_id]:
            _fail(f"{path}.container_type differs from its target")
        family = _text(operation.get("resource_family"), f"{path}.resource_family")
        try:
            family = validate_target_family(target_types[target_id], family)
        except ResourceRegistryError as exc:
            _fail(f"{path}: {exc}")
        name = _text(operation.get("name"), f"{path}.name")
        expected_key = semantic_object_key(target_id, family, name)
        if operation.get("object_key") != expected_key:
            _fail(f"{path}.object_key must equal {expected_key!r}")
        if expected_key in keys:
            _fail(f"duplicate object_key {expected_key!r}")
        keys.add(expected_key)
        if operation.get("action") not in ACTIONS:
            _fail(f"{path}.action is unsupported")
        if operation.get("action") in {"pause", "unpause"} and family != "tag":
            _fail(f"{path}.{operation['action']} is supported only for tag objects")
        if operation.get("state") not in OPERATION_STATES:
            _fail(f"{path}.state is unsupported")
        linked = set(_unique(operation.get("requirement_ids", []), f"{path}.requirement_ids"))
        if not linked <= requirement_ids:
            _fail(f"{path}.requirement_ids contains unknown IDs")
        if operation.get("action") in MUTATING_ACTIONS:
            if not linked:
                _fail(f"{path}.requirement_ids must bind every mutation to approved scope")
            evidence = set(_unique(operation.get("evidence", []), f"{path}.evidence"))
            if "approved-input" not in evidence:
                _fail(f"{path}.evidence needs 'approved-input' mutation authority")
        _array(operation.get("journal"), f"{path}.journal")
        risk = operation.get("risk")
        if risk not in {"routine", "high-impact"}:
            _fail(f"{path}.risk is unsupported")
        validate_action_contract(
            operation,
            path=path,
            fail=_fail,
            authority_locators={requirement_locators[value] for value in linked},
        )
        state = operation["state"]
        if state == "verified":
            comparison = _object(operation.get("comparison"), f"{path}.comparison")
            if comparison.get("pass") is not True:
                _fail(f"{path}.comparison.pass must be true for verified")
            if "saved_readback" not in operation:
                _fail(f"{path}.saved_readback is required for verified")
            try:
                validate_verification_comparison(
                    operation, comparison, operation.get("saved_readback")
                )
            except ValueError as exc:
                _fail(f"{path}.comparison is not bound to saved readback: {exc}")
        elif state == "saved" and "saved_readback" not in operation:
            _fail(f"{path}.saved_readback is required for saved")
        if "pre_write_comparison" in operation or "pre_write_readback" in operation:
            if not {
                "pre_write_comparison",
                "pre_write_readback",
            } <= set(operation):
                _fail(f"{path} needs both pre-write comparison and readback")
            rebuilt, _ = build_pre_write_comparison(operation, operation["pre_write_readback"])
            if operation["pre_write_comparison"] != rebuilt or rebuilt["pass"] is not True:
                _fail(f"{path}.pre_write_comparison is not bound to pre-change readback")
        operations[operation_id] = operation
    for operation_id, operation in operations.items():
        dependencies = _unique(
            operation.get("dependencies", []),
            f"$.object_changes[{operation_id!r}].dependencies",
        )
        for dependency in dependencies:
            if dependency not in operations:
                _fail(f"operation {operation_id!r} depends on unknown {dependency!r}")
            if dependency == operation_id:
                _fail(f"operation {operation_id!r} cannot depend on itself")
    _reject_dependency_cycle(operations)
    return operations


def _reject_dependency_cycle(operations: dict[str, dict[str, Any]]) -> None:
    remaining = {key: len(item.get("dependencies", [])) for key, item in operations.items()}
    dependents: dict[str, list[str]] = {key: [] for key in operations}
    for key, item in operations.items():
        for dependency in item.get("dependencies", []):
            dependents[dependency].append(key)
    ready = [key for key, count in remaining.items() if count == 0]
    seen = 0
    while ready:
        key = ready.pop()
        seen += 1
        for dependent in dependents[key]:
            remaining[dependent] -= 1
            if remaining[dependent] == 0:
                ready.append(dependent)
    if seen != len(operations):
        _fail("$.object_changes dependency graph contains a cycle")


def _validate_target_records(document: dict[str, Any], target_types: dict[str, str]) -> None:
    baselines = _array(document["container_baselines"], "$.container_baselines")
    baseline_ids = [item.get("target_id") for item in baselines if isinstance(item, dict)]
    if set(baseline_ids) != set(target_types) or len(baseline_ids) != len(target_types):
        _fail("$.container_baselines must contain exactly one record per target")
    for index, baseline in enumerate(baselines):
        path = f"$.container_baselines[{index}]"
        if not isinstance(baseline.get("complete"), bool):
            _fail(f"{path}.complete must be boolean")
        families = _array(baseline.get("resource_families"), f"{path}.resource_families")
        _object(baseline.get("family_counts"), f"{path}.family_counts")
        identities = _object(baseline.get("resource_identities"), f"{path}.resource_identities")
        resources = _object(baseline.get("resources"), f"{path}.resources")
        if set(identities) != set(families):
            _fail(f"{path}.resource_identities must cover exactly the captured families")
        if set(resources) != set(families):
            _fail(f"{path}.resources must cover exactly the captured families")
        for family, values in identities.items():
            _unique(values, f"{path}.resource_identities.{family}")
            family_resources = _array(resources[family], f"{path}.resources.{family}")
            for resource in family_resources:
                _object(resource, f"{path}.resources.{family}[]")
            if len(family_resources) != baseline["family_counts"].get(family):
                _fail(f"{path}.family_counts.{family} differs from retained resources")
            expected_identities = sorted(
                f"{baseline['target_id']}::{family}::{item['name'].strip()}"
                for item in family_resources
                if isinstance(item.get("name"), str) and item["name"].strip()
            )
            if values != expected_identities:
                _fail(f"{path}.resource_identities.{family} differs from retained resources")
        if baseline["complete"]:
            _text(baseline.get("captured_at"), f"{path}.captured_at")
            _text(baseline.get("fingerprint"), f"{path}.fingerprint")
            if not families:
                _fail(f"{path}.resource_families must not be empty when complete")
            if baseline.get("preexisting_workspace_changes") is None:
                _fail(f"{path}.preexisting_workspace_changes is required when complete")
            capture = _object(baseline.get("capture_evidence"), f"{path}.capture_evidence")
            if set(capture) != {
                "captured_by",
                "source_identity",
                "resource_pagination",
                "workspace_changes_pagination",
            }:
                _fail(f"{path}.capture_evidence has missing or unexpected fields")
            if capture.get("captured_by") != "authenticated-adapter-runtime":
                _fail(f"{path}.capture_evidence.captured_by is not adapter-authenticated")
            target = next(
                item
                for item in document["run"]["targets"]
                if item["target_id"] == baseline["target_id"]
            )
            expected_identity = {
                field: target[field]
                for field in ("account_id", "container_id", "workspace_id", "container_type")
            }
            if capture.get("source_identity") != expected_identity:
                _fail(f"{path}.capture_evidence.source_identity differs from the authorized target")
            expected_fingerprint = "sha256:" + canonical_sha256(
                {
                    "resources": resources,
                    "workspace_changes": baseline["preexisting_workspace_changes"],
                    "capture_evidence": capture,
                }
            )
            if baseline["fingerprint"] != expected_fingerprint:
                _fail(f"{path}.fingerprint differs from retained baseline evidence")
            pagination = _object(
                capture.get("resource_pagination"),
                f"{path}.capture_evidence.resource_pagination",
            )
            if set(pagination) != set(families):
                _fail(f"{path}.capture_evidence must cover exactly the captured families")
            receipts = [
                *pagination.items(),
                ("workspace changes", capture.get("workspace_changes_pagination")),
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
                    _fail(f"{path} has invalid pagination receipt for {family!r}")
            required_families = required_baseline_families(
                [
                    item
                    for item in document["object_changes"]
                    if item["target_id"] == baseline["target_id"]
                ],
                target["container_type"],
            )
            if not required_families <= set(families):
                _fail(f"{path} misses planned resource families")
            if document["run"]["execution_mode"] == "refonte-durable":
                expected_families = (
                    WEB_RESOURCE_FAMILIES
                    if target_types[baseline["target_id"]] == "web"
                    else SERVER_RESOURCE_FAMILIES
                )
                if set(families) != expected_families:
                    _fail(f"{path} refonte baseline does not cover the complete target surface")
        elif baseline.get("capture_evidence") is not None:
            _fail(f"{path}.capture_evidence must be null while incomplete")
    results = _array(document["target_results"], "$.target_results")
    result_ids = [item.get("target_id") for item in results if isinstance(item, dict)]
    if set(result_ids) != set(target_types) or len(result_ids) != len(target_types):
        _fail("$.target_results must contain exactly one record per target")
    for index, result in enumerate(results):
        if result.get("status") not in TARGET_STATUSES:
            _fail(f"$.target_results[{index}].status is unsupported")
    operation_by_id = {item["operation_id"]: item for item in document["object_changes"]}
    readback_by_operation: dict[str, dict[str, Any]] = {}
    for index, readback in enumerate(_array(document["saved_readback"], "$.saved_readback")):
        if not isinstance(readback, dict) or readback.get("target_id") not in target_types:
            _fail(f"$.saved_readback[{index}] has an unknown target_id")
        operation_id = readback.get("operation_id")
        if operation_id not in operation_by_id:
            _fail(f"$.saved_readback[{index}] has an unknown operation_id")
        if operation_id in readback_by_operation:
            _fail(f"$.saved_readback contains duplicate operation {operation_id!r}")
        operation = operation_by_id[operation_id]
        if readback.get("target_id") != operation["target_id"]:
            _fail(f"$.saved_readback[{index}].target_id differs from its operation")
        if readback.get("object_key") != operation["object_key"]:
            _fail(f"$.saved_readback[{index}].object_key differs from its operation")
        if readback.get("comparison") != operation.get("comparison"):
            _fail(f"$.saved_readback[{index}].comparison differs from its operation")
        if readback.get("saved") != operation.get("saved_readback"):
            _fail(f"$.saved_readback[{index}].saved differs from its operation")
        readback_by_operation[operation_id] = readback
    verified_ids = {
        operation_id
        for operation_id, operation in operation_by_id.items()
        if operation["state"] == "verified"
    }
    if set(readback_by_operation) != verified_ids:
        _fail("$.saved_readback must contain exactly one record per verified operation")


def validate_document(value: Any) -> dict[str, Any]:
    document = _object(value, "$")
    target_types, requirement_ids = _validate_header(document)
    _validate_requirements(document, requirement_ids)
    operations = _validate_operations(document, target_types, requirement_ids)
    for field in (
        "pipelines",
        "payload_mappings",
        "consent_topologies",
        "execution_topologies",
        "page_view_decisions",
        "first_party_data_routes",
        "inventory_dispositions",
        "container_baselines",
        "dedup_contracts",
        "saved_readback",
        "target_results",
        "official_sources",
        "external_dependencies",
        "publication_dependencies",
    ):
        _array(document[field], f"$.{field}")
    _validate_target_records(document, target_types)
    idempotency = _object(document["idempotency"], "$.idempotency")
    if set(idempotency) != {"checked", "remaining_actions", "observations"}:
        _fail("$.idempotency has missing or unexpected fields")
    if not isinstance(idempotency["checked"], bool):
        _fail("$.idempotency.checked must be boolean")
    if not isinstance(idempotency["remaining_actions"], list) or len(
        set(idempotency["remaining_actions"])
    ) != len(idempotency["remaining_actions"]):
        _fail("$.idempotency.remaining_actions must be a unique array")
    operation_by_id = {item["operation_id"]: item for item in document["object_changes"]}
    observations = idempotency["observations"]
    if not isinstance(observations, list):
        _fail("$.idempotency.observations must be an array")
    observed_ids: set[str] = set()
    mutation_required: set[str] = set()
    for index, observation in enumerate(observations):
        path = f"$.idempotency.observations[{index}]"
        if not isinstance(observation, dict) or set(observation) != {
            "operation_id",
            "target_id",
            "source",
            "source_identity",
            "observed_at",
            "decision",
            "saved",
            "comparison",
        }:
            _fail(f"{path} has missing or unexpected fields")
        operation_id = observation.get("operation_id")
        if operation_id in observed_ids or operation_id not in operation_by_id:
            _fail(f"{path}.operation_id is unknown or duplicated")
        observed_ids.add(operation_id)
        operation = operation_by_id[operation_id]
        if observation.get("target_id") != operation["target_id"]:
            _fail(f"{path}.target_id differs from its operation")
        if observation.get("source") != "target-adapter-read":
            _fail(f"{path}.source must be target-adapter-read")
        target = next(
            item
            for item in document["run"]["targets"]
            if item["target_id"] == operation["target_id"]
        )
        expected_identity = {
            field: target[field]
            for field in ("account_id", "container_id", "workspace_id", "container_type")
        }
        if observation.get("source_identity") != expected_identity:
            _fail(f"{path}.source_identity differs from the authorized target")
        try:
            observed_at_text = _timestamp(observation.get("observed_at"), f"{path}.observed_at")
            observed_at = datetime.fromisoformat(observed_at_text.replace("Z", "+00:00"))
            verified_at = max(
                datetime.fromisoformat(
                    _timestamp(entry.get("at"), f"{path}.verified_at").replace("Z", "+00:00")
                )
                for entry in operation["journal"]
                if entry.get("state") == "verified"
            )
            if observed_at <= verified_at:
                _fail(f"{path}.observed_at must be newer than operation verification")
        except (ValueError, TypeError):
            _fail(f"{path}.observed_at cannot be validated against verification")
        if observation.get("decision") not in {"no-op", "mutation-required"}:
            _fail(f"{path}.decision is unsupported")
        try:
            validate_verification_comparison(
                operation, observation.get("comparison"), observation.get("saved")
            )
        except ValueError as exc:
            _fail(f"{path}.comparison is invalid: {exc}")
        expected_decision = "no-op" if observation["comparison"]["pass"] else "mutation-required"
        if observation["decision"] != expected_decision:
            _fail(f"{path}.decision differs from its comparison")
        if expected_decision == "mutation-required":
            mutation_required.add(operation_id)
    if set(idempotency["remaining_actions"]) != mutation_required:
        _fail("$.idempotency.remaining_actions differs from convergence observations")
    if idempotency["checked"]:
        if observed_ids != set(operation_by_id) or mutation_required:
            _fail("checked idempotency requires one no-op observation per operation")
    if document["recovery_boundary"] is not None:
        _object(document["recovery_boundary"], "$.recovery_boundary")
    materialization = document["run"]["materialization"]
    if materialization["method"] != "contract-7.0-deterministic":
        _fail("unsupported materialization method")
    expected = materialization_fingerprints(document)
    if set(materialization["owned_sections"]) != set(expected):
        _fail("$.run.materialization.owned_sections differs from the owned projection")
    if materialization["section_fingerprints"] != expected:
        _fail("contract-owned run sections differ from deterministic materialization")
    validate_server_operations(
        list(operations.values()),
        target_types,
        _fail,
        pipelines=document["pipelines"],
        requirements=document["requirements"],
    )
    validate_pipeline_run(document, target_types, _fail)
    leaks = sensitive_paths(document)
    if leaks:
        _fail("run contains literal secret or user data at: " + ", ".join(leaks))
    validate_web_domain(
        execution_mode=document["run"]["execution_mode"],
        requirements=document["requirements"],
        operations=document["object_changes"],
        target_types=target_types,
        payload_mappings=document["payload_mappings"],
        consent_topologies=document["consent_topologies"],
        execution_topologies=document["execution_topologies"],
        page_view_decisions=document["page_view_decisions"],
        first_party_data_routes=document["first_party_data_routes"],
        pipelines=document["pipelines"],
        inventory_dispositions=document["inventory_dispositions"],
        external_dependencies=document["external_dependencies"],
        fail=_fail,
        contract_phase=False,
        baseline_in_scope_tags=(
            None
            if any(
                baseline.get("complete") is not True for baseline in document["container_baselines"]
            )
            else {
                baseline["target_id"]: set(baseline["resource_identities"].get("tag", []))
                for baseline in document["container_baselines"]
            }
        ),
        baseline_resources=(
            None
            if any(
                baseline.get("complete") is not True for baseline in document["container_baselines"]
            )
            else {
                baseline["target_id"]: baseline["resources"]
                for baseline in document["container_baselines"]
            }
        ),
    )
    if document["run"]["status"] == "Configured":
        if document["run"]["phase"] != "complete" or any(
            item["state"] != "verified" for item in document["object_changes"]
        ):
            _fail("Configured requires complete phase and every operation verified")
        if any(item.get("complete") is not True for item in document["container_baselines"]):
            _fail("Configured requires complete baselines")
        if (
            document["idempotency"].get("checked") is not True
            or document["idempotency"].get("remaining_actions") != []
        ):
            _fail("Configured requires an identical-rerun no-op check")
    return document


def transition_allowed(current: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())
