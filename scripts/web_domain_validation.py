"""Client-container parity validation for contract@6.0 and run@3.0.

The v9 envelope is target scoped.  The mature v8.1 web validators are reused on
one web target at a time after semantic keys are localized; this keeps the
client-side contract strict without duplicating a second implementation of its
GTM-specific rules.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

import run_validation_web as web
from run_model import EXECUTION_MODES


def _text(value: Any, path: str, fail: Callable[[str], None]) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{path} must be a non-empty string")
        return ""
    return value.strip()


def _array(value: Any, path: str, fail: Callable[[str], None]) -> list[Any]:
    if not isinstance(value, list):
        fail(f"{path} must be an array")
        return []
    return value


def _local_key(value: Any, target_id: str, path: str, fail: Callable[[str], None]) -> str:
    key = _text(value, path, fail)
    prefix = f"{target_id}::"
    if not key.startswith(prefix):
        fail(f"{path} must reference target {target_id!r}")
        return key
    return key[len(prefix) :]


def _local_trigger_reference(
    value: Any, target_id: str, path: str, fail: Callable[[str], None]
) -> str:
    reference = _text(value, path, fail)
    if reference in {"2147479553", "2147479572", "2147479573"}:
        return reference
    return _local_key(reference, target_id, path, fail)


def _local_target(
    raw: Any, target_id: str, path: str, fail: Callable[[str], None]
) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        fail(f"{path} must be an object")
        return None
    target = deepcopy(raw)
    for field in ("firingTriggerId", "blockingTriggerId"):
        if field not in target:
            continue
        values = _array(target[field], f"{path}.{field}", fail)
        target[field] = [
            _local_trigger_reference(item, target_id, f"{path}.{field}[]", fail) for item in values
        ]
    return target


def _local_operations(
    operations: list[dict[str, Any]], target_id: str, fail: Callable[[str], None]
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(operations):
        if source.get("target_id") != target_id:
            continue
        path = f"$.implementation.objects[{index}]"
        record = deepcopy(source)
        record["operation_id"] = source.get("operation_id") or source["object_key"]
        record["object_type"] = source.get("resource_family") or source.get("object_type")
        record["object_key"] = _local_key(source["object_key"], target_id, path, fail)
        record["dependencies"] = list(source.get("dependencies", source.get("depends_on", [])))
        record["intended"] = _local_target(
            source.get("intended"), target_id, f"{path}.intended", fail
        )
        record["pre_change"] = _local_target(
            source.get("pre_change"), target_id, f"{path}.pre_change", fail
        )
        for snapshot_name in ("intended", "pre_change"):
            snapshot = record.get(snapshot_name)
            if isinstance(snapshot, dict):
                snapshot.setdefault("object_type", record["object_type"])
                snapshot.setdefault(
                    "name",
                    source.get("new_name", source["name"])
                    if snapshot_name == "intended"
                    else source["name"],
                )
        output[record["operation_id"]] = record
    return output


def _local_topology(
    source: dict[str, Any], target_id: str, path: str, fail: Callable[[str], None]
) -> dict[str, Any]:
    record = deepcopy(source)
    record.pop("consent_topology_ids", None)
    record["tag_object_key"] = _local_key(
        source.get("tag_object_key"), target_id, f"{path}.tag_object_key", fail
    )
    for index, trigger in enumerate(record.get("normal_triggers", [])):
        trigger["trigger_object_key"] = _local_trigger_reference(
            trigger.get("trigger_object_key"),
            target_id,
            f"{path}.normal_triggers[{index}].trigger_object_key",
            fail,
        )
    record["blocking_trigger_keys"] = [
        _local_trigger_reference(value, target_id, f"{path}.blocking_trigger_keys[]", fail)
        for value in record.get("blocking_trigger_keys", [])
    ]
    return record


def _local_page_decision(
    source: dict[str, Any], target_id: str, path: str, fail: Callable[[str], None]
) -> dict[str, Any]:
    record = deepcopy(source)
    record.pop("target_id", None)
    for field in ("owner_object_key", "google_tag_object_key"):
        if record.get(field) is not None:
            record[field] = _local_key(record[field], target_id, f"{path}.{field}", fail)
    return record


def _local_first_party_route(
    source: dict[str, Any], target_id: str, path: str, fail: Callable[[str], None]
) -> dict[str, Any]:
    record = deepcopy(source)
    record["consumer_object_keys"] = [
        _local_key(value, target_id, f"{path}.consumer_object_keys[]", fail)
        for value in record.get("consumer_object_keys", [])
    ]
    for index, binding in enumerate(record.get("consumer_bindings", [])):
        binding["object_key"] = _local_key(
            binding.get("object_key"),
            target_id,
            f"{path}.consumer_bindings[{index}].object_key",
            fail,
        )
    return record


def _external_dependency_index(
    dependencies: list[Any], requirement_ids: set[str], fail: Callable[[str], None]
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(dependencies, start=1):
        path = f"$.external_dependencies[{index - 1}]"
        if isinstance(raw, str):
            dependency = {
                "id": f"EXT-{index:03d}",
                "requirement_ids": sorted(requirement_ids),
                "owner": "external",
                "action": raw,
                "status": "open",
            }
        elif isinstance(raw, dict):
            dependency = raw
        else:
            fail(f"{path} must be text or an object")
            continue
        dependency_id = _text(dependency.get("id"), f"{path}.id", fail)
        if dependency_id in output:
            fail(f"duplicate external dependency {dependency_id!r}")
        links = set(_array(dependency.get("requirement_ids"), f"{path}.requirement_ids", fail))
        if not links <= requirement_ids:
            fail(f"{path}.requirement_ids contains unknown IDs")
        output[dependency_id] = deepcopy(dependency)
    return output


def _validate_topology_consent_binding(
    source: dict[str, Any],
    *,
    consent_by_id: dict[str, dict[str, Any]],
    path: str,
    fail: Callable[[str], None],
) -> None:
    tag_key = source.get("tag_object_key")
    topology_ids = _array(source.get("consent_topology_ids"), f"{path}.consent_topology_ids", fail)
    if not topology_ids:
        fail(f"{path}.consent_topology_ids must not be empty")
    if len(set(topology_ids)) != len(topology_ids):
        fail(f"{path}.consent_topology_ids contains duplicates")
    linked_requirements = set(source.get("requirement_ids", []))
    for topology_id in topology_ids:
        topology = consent_by_id.get(topology_id)
        if topology is None:
            fail(f"{path} references unknown consent topology {topology_id!r}")
            continue
        if not linked_requirements <= set(topology.get("requirement_ids", [])):
            fail(f"{path} consent topology {topology_id!r} does not cover its requirements")
        if source.get("consent_mode") != topology.get("consent_mode"):
            fail(f"{path}.consent_mode differs from consent topology {topology_id!r}")
        mechanism = topology.get("web_enforcement", {}).get("mechanism")
        is_transporter = tag_key in set(topology.get("transporter_tag_keys", []))
        if source.get("consent_mode") == "strict-basic":
            allowed = (
                {"transport-trigger-only"}
                if is_transporter and topology.get("transporter_destination_vendor_block") is False
                else {
                    "cmp-lifecycle-plus-vendor-block",
                    "business-trigger-plus-vendor-block",
                }
            )
            if mechanism not in allowed:
                fail(f"{path}.strict-basic consent mechanism differs from the tag's route role")
        if source.get("consent_mode") == "advanced-native" and mechanism not in {
            "google-consent-mode",
            "product-native",
        }:
            fail(f"{path}.advanced-native needs a documented native consent mechanism")


def _web_sections_by_target(
    sections: list[dict[str, Any]], field: str, web_target_ids: set[str]
) -> dict[str, list[dict[str, Any]]]:
    output = {target_id: [] for target_id in web_target_ids}
    for source in sections:
        key = source.get(field)
        if not isinstance(key, str):
            continue
        target_id = key.split("::", 1)[0]
        if target_id in output:
            output[target_id].append(source)
    return output


def validate_web_domain(
    *,
    execution_mode: str,
    requirements: list[dict[str, Any]],
    operations: list[dict[str, Any]],
    target_types: dict[str, str],
    payload_mappings: list[dict[str, Any]],
    consent_topologies: list[dict[str, Any]],
    execution_topologies: list[dict[str, Any]],
    page_view_decisions: list[dict[str, Any]],
    first_party_data_routes: list[dict[str, Any]],
    inventory_dispositions: list[dict[str, Any]],
    external_dependencies: list[Any],
    fail: Callable[[str], None],
    contract_phase: bool,
    baseline_in_scope_tags: dict[str, set[str]] | None = None,
) -> None:
    """Validate the complete client-side decision surface for each web target."""
    if execution_mode not in EXECUTION_MODES:
        fail(f"execution_mode has unsupported value {execution_mode!r}")
    requirement_ids = {item.get("id") for item in requirements if isinstance(item, dict)}
    requirement_ids.discard(None)
    non_consent_requirement_ids = {
        item.get("id")
        for item in requirements
        if isinstance(item, dict) and item.get("kind") != "consent"
    }
    try:
        mappings = web._validate_payload_mappings(payload_mappings, set(requirement_ids))
    except web.RunValidationError as exc:
        fail(str(exc))
        return
    dependencies = _external_dependency_index(external_dependencies, set(requirement_ids), fail)
    consent_by_id: dict[str, dict[str, Any]] = {}
    transporter_keys: set[str] = set()
    for index, topology in enumerate(consent_topologies):
        if not isinstance(topology, dict):
            fail(f"$.consent_topologies[{index}] must be an object")
            continue
        topology_id = topology.get("consent_topology_id")
        if isinstance(topology_id, str):
            consent_by_id[topology_id] = topology
        transporter_keys.update(
            value for value in topology.get("transporter_tag_keys", []) if isinstance(value, str)
        )

    web_target_ids = {
        target_id for target_id, container_type in target_types.items() if container_type == "web"
    }
    for index, topology in enumerate(execution_topologies):
        if not isinstance(topology, dict):
            fail(f"$.execution_topologies[{index}] must be an object")
            continue
        key = topology.get("tag_object_key")
        target_id = key.split("::", 1)[0] if isinstance(key, str) else None
        if target_id not in web_target_ids:
            fail(f"$.execution_topologies[{index}] must reference a web target tag")
    for index, decision in enumerate(page_view_decisions):
        if not isinstance(decision, dict) or decision.get("target_id") not in web_target_ids:
            fail(f"$.page_view_decisions[{index}].target_id must reference a web target")
    valid_inventory_links = {
        item.get("object_key") if contract_phase else item.get("operation_id")
        for item in operations
    }
    inventory_link_field = "operation_keys" if contract_phase else "operation_ids"
    for index, row in enumerate(inventory_dispositions):
        if not isinstance(row, dict):
            fail(f"$.inventory_dispositions[{index}] must be an object")
            continue
        links = row.get(inventory_link_field)
        if not isinstance(links, list) or not links:
            fail(f"$.inventory_dispositions[{index}].{inventory_link_field} must not be empty")
            continue
        if any(value not in valid_inventory_links for value in links):
            fail(f"$.inventory_dispositions[{index}] references an unknown object action")
    topologies_by_target = _web_sections_by_target(
        execution_topologies, "tag_object_key", web_target_ids
    )
    for index, route in enumerate(first_party_data_routes):
        if not isinstance(route, dict):
            fail(f"$.first_party_data_routes[{index}] must be an object")
            continue
        consumers = route.get("consumer_object_keys")
        if not isinstance(consumers, list) or not consumers:
            fail(f"$.first_party_data_routes[{index}].consumer_object_keys must not be empty")
            continue
        target_ids = {value.split("::", 1)[0] for value in consumers if isinstance(value, str)}
        if len(target_ids) != 1 or not target_ids <= web_target_ids:
            fail(f"$.first_party_data_routes[{index}] must stay inside one web target")

    for target_id in sorted(web_target_ids):
        local_operations = _local_operations(operations, target_id, fail)
        target_requirement_ids = {
            requirement_id
            for operation in local_operations.values()
            for requirement_id in operation.get("requirement_ids", [])
        }
        local_topologies = []
        for index, topology in enumerate(topologies_by_target[target_id]):
            path = f"$.execution_topologies[{index}]"
            _validate_topology_consent_binding(
                topology, consent_by_id=consent_by_id, path=path, fail=fail
            )
            local_topologies.append(_local_topology(topology, target_id, path, fail))
        try:
            validated_topologies = web._validate_execution_topologies(
                local_topologies,
                requirement_ids=set(requirement_ids),
                operations=local_operations,
                baseline_trigger_types={},
                transporter_tag_keys={
                    _local_key(
                        value,
                        target_id,
                        "$.consent_topologies[].transporter_tag_keys",
                        fail,
                    )
                    for value in transporter_keys
                    if value.startswith(f"{target_id}::")
                },
            )
        except web.RunValidationError as exc:
            fail(str(exc))
            return

        executable_tags = {
            item["object_key"]
            for item in local_operations.values()
            if item["object_type"] == "tag"
            and item["action"] not in web.NON_EXECUTING_TAG_ACTIONS
            and set(item.get("requirement_ids", [])) & non_consent_requirement_ids
        }
        if set(validated_topologies) != executable_tags:
            missing = sorted(executable_tags - set(validated_topologies))
            extra = sorted(set(validated_topologies) - executable_tags)
            fail(
                f"web target {target_id!r} needs exactly one execution topology per executing "
                f"tag; missing={missing}, extra={extra}"
            )

        local_decisions = []
        for index, decision in enumerate(page_view_decisions):
            if not isinstance(decision, dict) or decision.get("target_id") != target_id:
                continue
            local_decisions.append(
                _local_page_decision(decision, target_id, f"$.page_view_decisions[{index}]", fail)
            )
        try:
            decisions = web._validate_page_view_decisions(
                local_decisions,
                requirement_ids=set(requirement_ids),
                operations=local_operations,
                external_dependencies=dependencies,
            )
        except web.RunValidationError as exc:
            fail(str(exc))
            return
        decision_destinations = {item["destination"] for item in decisions}
        expected_destinations = {
            destination
            for topology in validated_topologies.values()
            for destination in topology["page_view_destinations"]
        }
        if decision_destinations != expected_destinations:
            fail(
                f"web target {target_id!r} page-view decisions must exactly cover capable "
                f"destinations; missing={sorted(expected_destinations - decision_destinations)}, "
                f"extra={sorted(decision_destinations - expected_destinations)}"
            )

        local_routes = []
        for index, route in enumerate(first_party_data_routes):
            if not isinstance(route, dict):
                continue
            consumers = route.get("consumer_object_keys", [])
            if not isinstance(consumers, list) or not consumers:
                fail(f"$.first_party_data_routes[{index}].consumer_object_keys must not be empty")
                continue
            target_ids = {value.split("::", 1)[0] for value in consumers if isinstance(value, str)}
            if target_id in target_ids:
                local_routes.append(
                    _local_first_party_route(
                        route, target_id, f"$.first_party_data_routes[{index}]", fail
                    )
                )
        try:
            web._validate_first_party_data_routes(
                local_routes,
                requirement_ids=set(requirement_ids),
                operations=local_operations,
                external_dependencies=dependencies,
                payload_mappings=mappings,
                schema_version=web.SCHEMA_VERSION,
            )
        except web.RunValidationError as exc:
            fail(str(exc))
            return

        first_party_fields = {
            (item["requirement_id"], item["destination_field"]) for item in local_routes
        }
        required_first_party = {
            (item["requirement_id"], item["destination_field"])
            for item in mappings
            if item["status"] == "mapped"
            and item["destination_field"] in {"user_data", "user_id"}
            and item["requirement_id"] in target_requirement_ids
        }
        if not required_first_party <= first_party_fields:
            fail(
                f"web target {target_id!r} lacks first-party routes for "
                f"{sorted(required_first_party - first_party_fields)}"
            )

        local_inventory = []
        for index, row in enumerate(inventory_dispositions):
            if not isinstance(row, dict):
                continue
            source_keys = row.get("operation_keys") if contract_phase else None
            operation_ids = row.get("operation_ids") if not contract_phase else None
            if contract_phase:
                if not isinstance(source_keys, list):
                    fail(f"$.inventory_dispositions[{index}].operation_keys must be an array")
                    continue
                matching_ids = [
                    key
                    for key in source_keys
                    if isinstance(key, str) and key.startswith(f"{target_id}::")
                ]
                if not matching_ids:
                    continue
                local_ids = matching_ids
            else:
                if not isinstance(operation_ids, list):
                    fail(f"$.inventory_dispositions[{index}].operation_ids must be an array")
                    continue
                local_ids = [value for value in operation_ids if value in local_operations]
                if not local_ids:
                    continue
            record = deepcopy(row)
            record.pop("operation_keys", None)
            record["operation_ids"] = local_ids
            if record.get("before_object_key") is not None:
                record["before_object_key"] = _local_key(
                    record["before_object_key"],
                    target_id,
                    f"$.inventory_dispositions[{index}].before_object_key",
                    fail,
                )
            local_inventory.append(record)
        local_scope = (
            baseline_in_scope_tags.get(target_id, set())
            if baseline_in_scope_tags is not None
            else {
                item["object_key"]
                for item in local_operations.values()
                if item["object_type"] == "tag" and item["action"] != "create"
            }
        )
        try:
            web._validate_inventory_dispositions(
                local_inventory,
                execution_mode=execution_mode,
                in_scope_tag_keys=local_scope,
                operations=local_operations,
            )
        except web.RunValidationError as exc:
            fail(str(exc))
            return

    if not web_target_ids and any(
        (execution_topologies, page_view_decisions, first_party_data_routes, inventory_dispositions)
    ):
        fail("server-only mode must not contain client-side decision sections")
