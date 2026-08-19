"""Shared configuration-run@3.0 structure, state, and target validation."""

from __future__ import annotations

from typing import Any

from action_contract import validate_action_contract
from redaction import sensitive_paths
from resource_registry import ResourceRegistryError, semantic_object_key, validate_target_family
from run_model import (
    ACTIONS,
    ALLOWED_TRANSITIONS,
    EXECUTION_MODES,
    OPERATION_STATES,
    REQUIREMENT_STATUSES,
    RUN_MODES,
    RUN_PHASES,
    RUN_STATUSES,
    SCHEMA_VERSION,
    TARGET_STATUSES,
    TARGET_TYPES,
    TOP_LEVEL_KEYS,
)
from run_validation_pipeline import validate_pipeline_run
from run_validation_server import validate_server_operations
from run_validation_web import RunValidationError
from verification import (
    build_pre_write_comparison,
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
        _unique(requirement.get("object_keys", []), f"{path}.object_keys")
    if found != expected:
        _fail("$.requirements IDs must equal $.run.contract.requirement_ids")


def _validate_operations(
    document: dict[str, Any], target_types: dict[str, str], requirement_ids: set[str]
) -> dict[str, dict[str, Any]]:
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
        "destructive_authorization",
        "replacement_reason",
        "permission_delta",
        "scope",
        "evidence",
        "risk",
        "explicit_authority",
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
        _array(operation.get("journal"), f"{path}.journal")
        risk = operation.get("risk")
        if risk not in {"routine", "high-impact"}:
            _fail(f"{path}.risk is unsupported")
        if risk == "high-impact" and operation.get("explicit_authority") is not True:
            _fail(f"{path}.explicit_authority must be true")
        validate_action_contract(operation, path=path, fail=_fail)
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
        if baseline["complete"]:
            _text(baseline.get("captured_at"), f"{path}.captured_at")
            _text(baseline.get("fingerprint"), f"{path}.fingerprint")
            if not families:
                _fail(f"{path}.resource_families must not be empty when complete")
            if baseline.get("preexisting_workspace_changes") is None:
                _fail(f"{path}.preexisting_workspace_changes is required when complete")
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
    _object(document["idempotency"], "$.idempotency")
    if document["recovery_boundary"] is not None:
        _object(document["recovery_boundary"], "$.recovery_boundary")
    materialization = document["run"]["materialization"]
    if materialization["method"] == "contract-6.0-deterministic":
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
    if materialization["method"] == "contract-6.0-deterministic":
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
            inventory_dispositions=document["inventory_dispositions"],
            external_dependencies=document["external_dependencies"],
            fail=_fail,
            contract_phase=False,
        )
    return document


def transition_allowed(current: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())
