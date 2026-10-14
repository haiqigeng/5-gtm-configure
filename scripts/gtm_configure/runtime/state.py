"""Deterministic creation, checkpoints, inspection, and finalization for the current run model."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gtm_configure.core.validation as validation
from gtm_configure.contract import ContractValidationError
from gtm_configure.contract import validate_document as validate_contract
from gtm_configure.core.json_io import StrictJsonError, load_json
from gtm_configure.core.model import (
    DELTA_ACTIONS,
    MATERIALIZATION_METHOD,
    PUBLICATION_ORDER,
    SCHEMA_VERSION,
    SERVER_RESOURCE_FAMILIES,
    WEB_RESOURCE_FAMILIES,
)
from gtm_configure.core.privacy import redact_for_persistence
from gtm_configure.core.public_identifiers import public_identifier_paths
from gtm_configure.core.schemas import definition_validator, schema_resolver, validator
from gtm_configure.core.validation import canonical_sha256
from gtm_configure.domain.graph import served_requirements
from gtm_configure.domain.resources import (
    ResourceRegistryError,
    required_baseline_families,
    validate_target_family,
)
from gtm_configure.runtime.readiness import operation_readiness
from gtm_configure.runtime.validation import transition_allowed, validate_document
from gtm_configure.runtime.verification import (
    build_pre_write_comparison,
    build_verification_comparison,
    materialization_fingerprints,
    materialization_projection,
    validate_verification_comparison,
)

RunValidationError = validation.RunValidationError
RunConflictError = validation.RunConflictError


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
    order = PUBLICATION_ORDER[mode]
    return [
        {
            "kind": kind,
            "owner": "external acceptance owner"
            if "recette" in kind or "smoke" in kind
            else "external deployment owner",
            "status": "open",
            "depends_on_kind": order[index - 1] if index else None,
            "blocks_saved_configuration": False,
        }
        for index, kind in enumerate(order)
    ]


def create_from_contract(
    contract: dict[str, Any],
    *,
    run_id: str,
    source_locator: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Materialize every active run section deterministically from the validated contract."""
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
            record["intended"] = redact_for_persistence(
                item["intended"],
                public_identifier_paths=public_identifier_paths(item["intended"], records=[item]),
            )
        for optional in (
            "pre_change",
            "object_id",
            "new_name",
            "approval",
            "replacement_reason",
            "permission_delta",
            "public_identifiers",
            "assertions",
        ):
            if optional in item:
                record[optional] = redact_for_persistence(
                    item[optional],
                    public_identifier_paths=public_identifier_paths(item[optional], records=[item]),
                )
        object_changes.append(record)
    serves = served_requirements({item["operation_id"]: item for item in object_changes})
    for record in object_changes:
        for requirement_id in serves[record["operation_id"]]:
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
    from gtm_configure.domain.fields import materialize_payload_mappings

    payload_mappings = materialize_payload_mappings(contract)
    pipelines = []
    for item in contract["pipelines"]:
        record = deepcopy(item)
        record["claiming_client_operation_id"] = operation_by_key[
            record["claiming_client"]["object_key"]
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
                "requirement_fingerprints": {
                    item["id"]: canonical_sha256(item) for item in contract["requirements"]
                },
            },
            "revisions": [],
            "publication": {"performed": False, "version_created": False},
            "materialization": {
                "method": MATERIALIZATION_METHOD,
                "owned_sections": [
                    "targets",
                    "requirements",
                    "pipelines",
                    "object_changes",
                    "payload_mappings",
                    "consent_policies",
                    "tag_policies",
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
        "consent_policies": deepcopy(contract["consent_policies"]),
        "tag_policies": deepcopy(contract["tag_policies"]),
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
                "supplemental_captures": [],
                "fingerprint": None,
            }
            for target in targets
        ],
        "dedup_contracts": deepcopy(contract["dedup_contracts"]),
        "final_inventories": [],
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


def _verified_policy_projection(document, keys):
    """Freeze records bound to verified native consumers by their semantic references."""
    from gtm_configure.domain.graph import object_references

    operations = {item["object_key"]: item for item in document["object_changes"]}
    references = keys | {operations[key]["operation_id"] for key in keys}
    projection = materialization_projection(document)

    def shape_layers(shape, resolver):
        layers = []
        if "$ref" in shape:
            resolved = resolver.lookup(shape["$ref"])
            layers.extend(shape_layers(resolved.contents, resolved.resolver))
        for layer in shape.get("allOf", []):
            layers.extend(shape_layers(layer, resolver))
        layers.append((shape, resolver))
        return layers

    def owned(value, shape, resolver, context):
        layers = shape_layers(shape, resolver)
        annotations = {key: child for layer, _ in layers for key, child in layer.items()}
        owner_paths = annotations.get("x-owner-paths")
        if owner_paths is not None:
            owner_values = []
            for path in owner_paths:
                resolved = context
                for part in path:
                    resolved = resolved.get(part, []) if isinstance(resolved, dict) else []
                owner_values.append(resolved)
            return deepcopy(value) if object_references(owner_values) & references else None
        if isinstance(value, list):
            item_shape, item_resolver = next(
                (
                    (layer["items"], origin)
                    for layer, origin in reversed(layers)
                    if "items" in layer
                ),
                ({}, resolver),
            )
            items = [owned(item, item_shape, item_resolver, item) for item in value]
            return [item for item in items if item is not None] or None
        if isinstance(value, dict):
            properties = {
                key: (child, origin)
                for layer, origin in layers
                for key, child in layer.get("properties", {}).items()
            }
            result = {
                key: selected
                for key, child in value.items()
                if (selected := owned(child, *properties.get(key, ({}, resolver)), value))
                is not None
            }
            if result and annotations.get("x-identity-key"):
                result[annotations["x-identity-key"]] = value[annotations["x-identity-key"]]
            return result or None
        return None

    phase_schema = validator("run").schema
    resolver = schema_resolver("run")
    protected = {
        name: owned(rows, phase_schema["properties"][name], resolver, rows) or []
        for name, rows in projection.items()
        if name not in {"object_changes", "requirements", "targets"} and isinstance(rows, list)
    }
    consent_ids = {item["consent_policy_id"] for item in protected["tag_policies"]}
    protected["consent_policies"] = [
        item
        for item in document["consent_policies"]
        if item["consent_policy_id"] in consent_ids or item in protected["consent_policies"]
    ]
    return protected


def _event_consumer(document, operation):
    """Event consumers own whole event semantics; shared field owners own field proofs."""
    return operation["resource_family"] == "tag" and (
        operation["container_type"] == "server"
        or any(
            row["tag_object_key"] == operation["object_key"]
            and row["lifecycle_role"] == "event-driven"
            for row in document["tag_policies"]
        )
    )


def revise_from_contract(document, contract, *, expected_fingerprint, note, timestamp=None):
    """Revise only the unsent graph while preserving verified current-run evidence."""
    current = deepcopy(validate_document(document))
    if canonical_sha256(current) != expected_fingerprint:
        raise RunConflictError("Current run changed since revision inspection")
    if not isinstance(note, str) or not note.strip():
        raise RunValidationError("Revision requires a durable rationale")
    if any(item["state"] not in {"planned", "verified"} for item in current["object_changes"]):
        raise RunValidationError(
            "Revision requires authoritative reconciliation of every dispatched operation"
        )
    now = timestamp or _utc_now()
    revised = create_from_contract(
        contract,
        run_id=current["run"]["id"],
        source_locator=current["run"]["contract"]["source_locator"],
        timestamp=now,
    )
    if revised["run"]["contract"]["fingerprint"] == current["run"]["contract"]["fingerprint"]:
        raise RunValidationError("Revision requires an approved change to the remaining graph")
    old_targets = {item["target_id"]: item for item in current["run"]["targets"]}
    new_targets = {item["target_id"]: item for item in revised["run"]["targets"]}

    def identity(row):
        return {key: value for key, value in row.items() if key != "adapter_capabilities"}

    if {key: identity(value) for key, value in old_targets.items()} != {
        key: identity(value) for key, value in new_targets.items()
    }:
        raise RunValidationError(
            "Revision preserves the current run's authorized target identities"
        )
    old_specs = {
        item["object_key"]: item for item in materialization_projection(current)["object_changes"]
    }
    new_specs = {
        item["object_key"]: item for item in materialization_projection(revised)["object_changes"]
    }
    old_ops = {item["object_key"]: item for item in current["object_changes"]}
    verified = {key for key, item in old_ops.items() if item["state"] == "verified"}
    for key in verified:
        if key not in new_specs or canonical_sha256(old_specs[key]) != canonical_sha256(
            new_specs[key]
        ):
            raise RunValidationError(
                "Verified operations retain their original intent and authority; use an authorized follow-on change"
            )
        consumer = _event_consumer(current, old_ops[key])
        for req in old_ops[key]["requirement_ids"] if consumer else []:
            if current["run"]["contract"]["requirement_fingerprints"][req] != revised["run"][
                "contract"
            ]["requirement_fingerprints"].get(req):
                raise RunValidationError(
                    "Revision preserves approved source semantics of verified consumers"
                )
    if canonical_sha256(_verified_policy_projection(current, verified)) != canonical_sha256(
        _verified_policy_projection(revised, verified)
    ):
        raise RunValidationError(
            "Revision preserves policies and field proofs of verified consumers"
        )
    new_ops = {item["object_key"]: item for item in revised["object_changes"]}

    def owned_intent(value, specs, ops, key):
        requirements = value["run"]["contract"]["requirement_fingerprints"]
        return {
            "native": specs.get(key),
            "policies": _verified_policy_projection(value, {key}) if key in ops else None,
            "requirements": {req: requirements.get(req) for req in ops[key]["requirement_ids"]}
            if key in ops and _event_consumer(value, ops[key])
            else {},
        }

    changed = sorted(
        key
        for key in old_specs.keys() | new_specs.keys()
        if canonical_sha256(owned_intent(current, old_specs, old_ops, key))
        != canonical_sha256(owned_intent(revised, new_specs, new_ops, key))
    )
    revised["object_changes"] = [
        deepcopy(old_ops[item["object_key"]])
        if item["object_key"] in old_ops
        and old_specs[item["object_key"]] == new_specs[item["object_key"]]
        else item
        for item in revised["object_changes"]
    ]
    for field in ("container_baselines", "target_results", "final_inventories"):
        revised[field] = deepcopy(current[field])
    revised["run"]["targets"] = deepcopy(current["run"]["targets"])
    revised["run"]["started_at"] = current["run"]["started_at"]
    revised["run"]["revisions"] = deepcopy(current["run"]["revisions"]) + [
        {
            "at": now,
            "note": note,
            "previous_contract_fingerprint": current["run"]["contract"]["fingerprint"],
            "contract_fingerprint": revised["run"]["contract"]["fingerprint"],
            "changed_operation_keys": changed,
        }
    ]
    revised["run"]["materialization"]["section_fingerprints"] = materialization_fingerprints(
        revised
    )
    derive_live_status(revised)
    return validate_document(revised)


def load_document(path: Path) -> dict[str, Any]:
    try:
        value = load_json(path)
    except StrictJsonError as exc:
        raise RunValidationError(str(exc), error_code=exc.error_code) from exc
    return validate_document(value)


def build_target_baseline(
    target: dict[str, Any],
    resources: dict[str, list[dict[str, Any]]],
    *,
    captured_at: str,
    preexisting_workspace_changes: list[dict[str, Any]],
    capture_evidence: dict[str, Any],
    operations: list[dict] | None = None,
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
    error = next(definition_validator("baselineCapture").iter_errors(capture_evidence), None)
    if error is not None:
        raise RunValidationError(f"baseline capture_evidence: {error.message}")
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
    container_type = target["container_type"]
    # References to credentials may cross families or pages. Classify the collected
    # graph together, before any baseline resource or workspace-change persistence.
    raw_graph = {"resources": resources, "changes": preexisting_workspace_changes}
    safe_graph = redact_for_persistence(
        raw_graph,
        public_identifier_paths=public_identifier_paths(raw_graph, records=operations or []),
    )
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
        normalized[validated_family] = safe_graph["resources"][family]
    safe_changes = safe_graph["changes"]
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
        "supplemental_captures": [],
        "fingerprint": canonical_sha256(
            {
                "resources": normalized,
                "workspace_changes": safe_changes,
                "capture_evidence": capture_evidence,
                "supplemental_captures": [],
            }
        ),
    }


def record_target_baseline(
    document: dict[str, Any],
    *,
    target_id: str,
    resources: dict[str, list[dict[str, Any]]],
    captured_at: str,
    preexisting_workspace_changes: list[dict[str, Any]],
    capture_evidence: dict[str, Any],
) -> dict[str, Any]:
    """Capture the initial target baseline or append proof for newly required families."""
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
    index = next(
        index
        for index, row in enumerate(value["container_baselines"])
        if row["target_id"] == target_id
    )
    current = value["container_baselines"][index]
    captured = set(current["resource_families"])
    supplemental = bool(current.get("capture_evidence"))
    if supplemental:
        if set(resources) != required_families - captured:
            raise RunConflictError(
                "Supplemental capture proves exactly the newly required resource families"
            )
    else:
        if not required_families <= set(resources):
            raise RunValidationError(
                f"baseline misses planned resource families: {sorted(required_families - set(resources))}"
            )
        if any(
            item["target_id"] == target_id and (item["state"] != "planned" or item["journal"])
            for item in value["object_changes"]
        ):
            raise RunConflictError(
                "Initial target baseline precedes the first dispatched operation"
            )
    if value["run"]["execution_mode"] == "refonte-durable":
        expected_families = (
            WEB_RESOURCE_FAMILIES if target["container_type"] == "web" else SERVER_RESOURCE_FAMILIES
        )
        if set(resources) | captured != expected_families:
            raise RunValidationError(
                "refonte baseline exhausts the complete target resource surface"
            )
    baseline = build_target_baseline(
        target,
        resources,
        captured_at=captured_at,
        preexisting_workspace_changes=preexisting_workspace_changes,
        capture_evidence=capture_evidence,
        operations=[item for item in value["object_changes"] if item["target_id"] == target_id],
    )
    if supplemental:
        extension = {"captured_at": captured_at, "capture_evidence": deepcopy(capture_evidence)}
        combined = deepcopy(current)
        for field in ("resources", "family_counts", "resource_identities"):
            combined[field].update(baseline[field])
        combined["resource_families"] = sorted(combined["resources"])
        combined["supplemental_captures"].append(extension)
        combined["complete"] = True
        combined["fingerprint"] = canonical_sha256(
            {
                "resources": combined["resources"],
                "workspace_changes": combined["preexisting_workspace_changes"],
                "capture_evidence": combined["capture_evidence"],
                "supplemental_captures": combined["supplemental_captures"],
            }
        )
        baseline = combined
    value["container_baselines"][index] = baseline
    value["run"]["updated_at"] = captured_at.strip()
    return validate_document(value)


def find_operation(document: dict[str, Any], operation_id: str) -> dict[str, Any]:
    for operation in document["object_changes"]:
        if operation["operation_id"] == operation_id:
            return operation
    raise RunValidationError(f"unknown operation_id {operation_id!r}")


def checkpoint_operation(document: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    value = deepcopy(validate_document(document))
    return validate_document(checkpoint_validated_operation(value, **kwargs))


def checkpoint_validated_operation(
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
    value = document
    operation = find_operation(value, operation_id)
    current = operation["state"]
    if state in {"in_progress", "saved", "verified"}:
        readiness = operation_readiness(value)[operation_id]
        blockers, waiting = readiness["blocked"], readiness["waiting"]
        if blockers or waiting:
            raise RunValidationError(
                "execution requires resolved fields, complete baseline and every dependency verified: "
                + "; ".join(blockers + waiting)
            )
    if not transition_allowed(current, state):
        raise RunValidationError(f"operation transition {current!r} -> {state!r} is not allowed")
    delta_actions = DELTA_ACTIONS
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
    safe_saved = (
        redact_for_persistence(
            saved,
            public_identifier_paths=public_identifier_paths(saved, records=[operation]),
        )
        if saved is not None
        else None
    )
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
        next(
            item for item in value["target_results"] if item["target_id"] == operation["target_id"]
        )["last_verified_operation_id"] = operation_id
    elif state == "saved":
        operation["saved_readback"] = safe_saved
    operation["state"] = state
    # Convergence observations prove an earlier verification generation. Journals
    # retain history; changed operations need a new complete convergence pass.
    value["idempotency"] = {
        "checked": False,
        "remaining_actions": [],
        "observations": [],
    }
    operation["journal"].append(
        {
            "at": timestamp or _utc_now(),
            "state": state,
            "note": note,
            "result": redact_for_persistence(
                result,
                public_identifier_paths=public_identifier_paths(result, records=[operation]),
            ),
            "error": redact_for_persistence(error),
        }
    )
    value["run"]["updated_at"] = timestamp or _utc_now()
    value["run"]["phase"] = "readback" if state in {"saved", "verified"} else "mutation"
    derive_live_status(value)
    return value


def reopen_failed_operation(
    document: dict[str, Any],
    *,
    operation_id: str,
    note: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    value = deepcopy(validate_document(document))
    operation = find_operation(value, operation_id)
    if operation["state"] != "failed":
        raise RunValidationError("only a known failed operation can be reopened")
    for field in (
        "comparison",
        "saved_readback",
        "pre_write_readback",
        "pre_write_comparison",
    ):
        operation.pop(field, None)
    operation["state"] = "planned"
    value["idempotency"] = {
        "checked": False,
        "remaining_actions": [],
        "observations": [],
    }
    operation["journal"].append(
        {
            "at": timestamp or _utc_now(),
            "state": "planned",
            "note": note,
            "reopened": True,
        }
    )
    value["run"]["updated_at"] = timestamp or _utc_now()
    derive_live_status(value)
    return validate_document(value)


def derive_live_status(document: dict[str, Any]) -> None:
    readiness = operation_readiness(document)
    for result in document["target_results"]:
        operations = [
            item for item in document["object_changes"] if item["target_id"] == result["target_id"]
        ]
        states = {item["state"] for item in operations}
        verified = [item for item in operations if item["state"] == "verified"]
        latest = max(verified, key=lambda item: item["journal"][-1]["at"], default=None)
        if result["last_verified_operation_id"] not in {item["operation_id"] for item in verified}:
            result["last_verified_operation_id"] = latest["operation_id"] if latest else None
        if result.get("baseline_error"):
            result["status"] = "Partial" if verified else "Blocked"
        elif states & {"uncertain"}:
            result["status"] = "Partial"
        elif states & {"failed"}:
            result["status"] = "Partial" if verified else "Blocked"
        elif "skipped" in states:
            result["status"] = "Partial" if verified else "Deferred"
        elif any(
            readiness[item["operation_id"]]["blocked"]
            for item in operations
            if item["state"] == "planned"
        ):
            result["status"] = "Partial" if verified else "Blocked"
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
            {
                "operation_ids": pending,
                "next_action": "authoritative readback before retry",
            }
            if pending
            else None
        )
    boundaries = [item for item in document["target_results"] if item["recovery_boundary"]]
    document["recovery_boundary"] = {"targets": deepcopy(boundaries)} if boundaries else None


def inspect_document(document: dict[str, Any]) -> dict[str, Any]:
    return inspect_validated_document(validate_document(document))


def inspect_validated_document(value: dict[str, Any]) -> dict[str, Any]:
    readiness = operation_readiness(value)
    ready: list[str] = []
    waiting: dict[str, list[str]] = {}
    blocked: dict[str, list[str]] = {}
    for operation in value["object_changes"]:
        if operation["state"] != "planned":
            continue
        row = readiness[operation["operation_id"]]
        blockers, dependencies = row["blocked"], row["waiting"]
        if blockers:
            blocked[operation["operation_id"]] = blockers
        elif dependencies:
            waiting[operation["operation_id"]] = dependencies
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
        "run_fingerprint": canonical_sha256(value),
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


def record_adapter_idempotency_observations(
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
            for field in (
                "account_id",
                "container_id",
                "workspace_id",
                "container_type",
            )
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
        derive_live_status(value)
    return validate_document(value)


def finalize_adapter_verified_document(
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
