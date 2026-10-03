"""Client-container parity validation for contract@7.0 and run@4.0.

Validate one web target at a time after semantic keys are localized, then apply
cross-target rules separately without duplicating GTM-specific rules.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

import run_validation_web as web
from consent_conventions import ALTERNATIVE_GATES, validate_convention
from event_semantics import approved_event_name, trigger_accepts_event
from native_configuration import (
    USER_DATA_VARIABLE_TYPES,
    FieldResolutionError,
    effective_event_parameters,
    field_key,
    referenced_variable_closure,
    sensitive_fields,
    supports_native_mapping,
    variable_consumers,
    variable_name,
)
from resource_registry import requires_variable_consumer_check
from run_model import EXECUTION_MODES


def _contains_configuration_key(value: Any, keys: set[str]) -> bool:
    if isinstance(value, dict):
        row_key = value.get("key")
        if isinstance(row_key, str) and web._normalized_token(row_key) in keys:
            return True
        return any(
            web._normalized_token(str(key)) in keys or _contains_configuration_key(child, keys)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_configuration_key(child, keys) for child in value)
    return False


def materialize_payload_mappings(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Attach implementation decisions without rewriting approved source semantics."""
    mappings = [
        row for requirement in contract["requirements"] for row in web._field_mappings(requirement)
    ]
    by_key = {
        (row["requirement_id"], row["field_scope"], row["destination_field"]): row
        for row in mappings
    }
    bindings = contract["implementation"].get("field_bindings", [])
    if not isinstance(bindings, list):
        raise web.RunValidationError("implementation.field_bindings must be an array")
    seen = set()
    required = {
        "requirement_id",
        "field_scope",
        "destination_field",
        "shape_compatibility",
        "mapping_method",
        "gtm_resolution",
        "template_field",
        "missing_behavior",
        "status",
    }
    for binding in bindings:
        if (
            not isinstance(binding, dict)
            or not required <= set(binding)
            or set(binding) - required - {"native_binding"}
        ):
            raise web.RunValidationError("field binding has missing or unexpected fields")
        key = (
            binding["requirement_id"],
            binding["field_scope"],
            binding["destination_field"],
        )
        if key not in by_key or key in seen:
            raise web.RunValidationError("field binding is unknown or duplicated")
        seen.add(key)
        by_key[key].update(binding)
    return web._validate_payload_mappings(
        mappings, {item["id"] for item in contract["requirements"]}
    )


def validate_native_mappings(mappings, operations, fail):
    """Prove supported event mappings; leave other native structures agent-reviewed."""
    by_key = {item.get("object_key"): item for item in operations}
    for mapping in mappings:
        if mapping["status"] != "mapped":
            continue
        binding = mapping.get("native_binding")
        if binding is None and not any(
            mapping["requirement_id"] in item.get("requirement_ids", [])
            and supports_native_mapping(
                mapping, item.get("intended") or item.get("pre_change") or {}
            )
            for item in operations
        ):
            continue
        if (
            not isinstance(binding, dict)
            or set(binding) != {"object_key", "field"}
            or not all(isinstance(binding[key], str) and binding[key].strip() for key in binding)
        ):
            fail("mapped scalar GA4 event parameter requires native_binding object_key and field")
            continue
        owner = by_key.get(binding["object_key"], {})
        if (
            (owner.get("resource_family") or owner.get("object_type")) != "tag"
            or owner.get("action") in web.NON_EXECUTING_TAG_ACTIONS
            or mapping["requirement_id"] not in owner.get("requirement_ids", [])
        ):
            fail("native mapping owner must be an active tag for the approved requirement")
            continue
        variables = {
            item["name"]: item.get("intended") or item.get("pre_change") or {}
            for item in operations
            if item.get("target_id") == owner.get("target_id")
            and (item.get("resource_family") or item.get("object_type")) == "variable"
            and item.get("action") not in web.NON_EXECUTING_TAG_ACTIONS
        }
        try:
            field = binding["field"]
            if field != mapping["destination_field"]:
                raise ValueError(
                    "native mapping field must identify the approved destination field"
                )
            target = owner.get("intended") or owner.get("pre_change") or {}
            if target.get("paused") is True:
                raise ValueError("native mapping owner is paused")
            if not supports_native_mapping(mapping, target):
                continue
            value = effective_event_parameters(target, variables)[field]
            if value != mapping["gtm_resolution"]:
                raise ValueError("native mapping value differs from gtm_resolution")
            if mapping.get("mapping_method") == "direct-dlv":
                if (
                    not isinstance(value, str)
                    or not value.startswith("{{")
                    or not value.endswith("}}")
                ):
                    raise ValueError("direct-dlv requires a native variable reference")
                variable = variables[variable_name(value)]
                if variable.get("type") != "v":
                    raise ValueError("direct-dlv must reference a Data Layer Variable")
                # Native DLV source is parameter[name], not the resource display name.
                source = next(
                    (
                        row.get("value")
                        for row in variable.get("parameter", [])
                        if row.get("key") == "name"
                    ),
                    None,
                )
                if source != mapping["source"]:
                    raise ValueError("direct-dlv source differs from the approved source")
        except (ValueError, KeyError, TypeError) as exc:
            fail(f"native mapping {mapping['destination_field']!r} is unresolved: {exc}")


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
        # Intended references use target-scoped semantic keys.  Pre-change is an
        # authoritative GTM snapshot and therefore keeps native resource IDs.
        record["pre_change"] = deepcopy(source.get("pre_change"))
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
        if not isinstance(raw, dict):
            fail(f"{path} must be an object")
            continue
        dependency = raw
        expected_keys = {"id", "requirement_ids", "owner", "action", "status"}
        if set(dependency) != expected_keys:
            fail(f"{path} must contain exactly {sorted(expected_keys)!r}")
        dependency_id = _text(dependency.get("id"), f"{path}.id", fail)
        if dependency_id in output:
            fail(f"duplicate external dependency {dependency_id!r}")
        links = set(_array(dependency.get("requirement_ids"), f"{path}.requirement_ids", fail))
        if not links <= requirement_ids:
            fail(f"{path}.requirement_ids contains unknown IDs")
        _text(dependency.get("owner"), f"{path}.owner", fail)
        _text(dependency.get("action"), f"{path}.action", fail)
        if dependency.get("status") not in {"open", "resolved", "accepted"}:
            fail(f"{path}.status is unsupported")
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
                    *ALTERNATIVE_GATES,
                }
            )
            if mechanism not in allowed:
                fail(f"{path}.strict-basic consent mechanism differs from the tag's route role")
            if mechanism in ALTERNATIVE_GATES and topology.get("unknown_state_behavior") != "deny":
                fail("Alternative strict-basic conventions must fail closed on unknown consent")
        native_google_carrier = (
            is_transporter
            and mechanism == "transport-trigger-only"
            and topology.get("signal_authority") == "google-consent-mode"
            and topology.get("server_enforcement", {}).get("mechanism")
            in {"incoming-google-consent-native", "none"}
        )
        if (
            source.get("consent_mode") == "advanced-native"
            and not native_google_carrier
            and mechanism
            not in {
                "google-consent-mode",
                "product-native",
            }
        ):
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
    pipelines: list[dict[str, Any]],
    inventory_dispositions: list[dict[str, Any]],
    external_dependencies: list[Any],
    fail: Callable[[str], None],
    contract_phase: bool,
    baseline_in_scope_tags: dict[str, set[str]] | None = None,
    baseline_resources: dict[str, dict[str, list[dict[str, Any]]]] | None = None,
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
    requirement_by_id = {
        item["id"]: item
        for item in requirements
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    authorized_server_consumers = {
        key
        for route in first_party_data_routes
        if isinstance(route, dict)
        for key in route.get("server_consumer_object_keys", [])
        if isinstance(key, str)
    }
    for operation in operations:
        if (
            not isinstance(operation, dict)
            or target_types.get(operation.get("target_id")) != "server"
            or (operation.get("resource_family") or operation.get("object_type")) != "tag"
            or operation.get("action") in web.NON_EXECUTING_TAG_ACTIONS
        ):
            continue
        target = operation.get("intended") or operation.get("pre_change") or {}
        if _contains_configuration_key(target, {"userdata", "userid", "userprovideddata"}):
            if operation.get("object_key") not in authorized_server_consumers:
                fail(
                    f"server tag {operation.get('object_key')!r} configures first-party user "
                    "data without an authorized first-party-data route"
                )
    try:
        mappings = web._validate_payload_mappings(payload_mappings, set(requirement_ids))
    except web.RunValidationError as exc:
        fail(str(exc))
        return
    validate_native_mappings(mappings, operations, fail)
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
        if topology.get("transporter_destination_vendor_block") is False:
            transporter_keys.update(
                value
                for value in topology.get("transporter_tag_keys", [])
                if isinstance(value, str)
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
        server_feature = route.get("feature")
        if server_feature in {
            "google-ads-server-user-data-transport",
            "google-ads-server-user-provided-data-event",
        }:
            receiver_keys = route.get("server_consumer_object_keys")
            if set(target_types.values()) == {"web"}:
                dependency_id = route.get("external_receiver_dependency_id")
                dependency = dependencies.get(dependency_id, {})
                if (
                    server_feature != "google-ads-server-user-data-transport"
                    or route.get("timing") != "same-event"
                    or receiver_keys != []
                    or dependency_id not in route.get("external_dependency_ids", [])
                    or route.get("requirement_id") not in dependency.get("requirement_ids", [])
                ):
                    fail(
                        f"$.first_party_data_routes[{index}] sender-only user_data needs same-event scope and its explicit external receiver dependency"
                    )
                continue
            if route.get("external_receiver_dependency_id") is not None:
                fail(
                    f"$.first_party_data_routes[{index}] full pipeline requires in-scope receiver proof"
                )
            if (
                not isinstance(receiver_keys, list)
                or not receiver_keys
                or any(not isinstance(key, str) for key in receiver_keys)
            ):
                fail(f"$.first_party_data_routes[{index}] needs explicit server consumers")
                continue
            if len(set(receiver_keys)) != len(receiver_keys):
                fail(f"$.first_party_data_routes[{index}] has duplicate server consumers")
            operation_by_key = {item.get("object_key"): item for item in operations}
            expected_receiver_types = (
                {"googleadsuserprovideddataevent"}
                if server_feature == "google-ads-server-user-provided-data-event"
                else {"awct", "googleadsconversion", "googleadsconversiontracking"}
            )
            for receiver_key in receiver_keys:
                receiver = operation_by_key.get(receiver_key)
                receiver_type = web._normalized_token(
                    str((receiver or {}).get("intended", {}).get("type", ""))
                )
                if (
                    receiver is None
                    or target_types.get(receiver.get("target_id")) != "server"
                    or receiver.get("resource_family") != "tag"
                    or receiver_type not in expected_receiver_types
                ):
                    expected_owner = (
                        "Google Ads User-provided Data Event"
                        if server_feature == "google-ads-server-user-provided-data-event"
                        else "Google Ads Conversion Tracking"
                    )
                    fail(
                        f"$.first_party_data_routes[{index}] server consumer must be the "
                        f"{expected_owner} tag that consumes transported user_data"
                    )
            requirement_id = route.get("requirement_id")
            proved_receivers: set[str] = set()
            for pipeline in pipelines:
                if not target_ids <= set(pipeline.get("sending_target_ids", [])):
                    continue
                event_receivers = {
                    key
                    for flow in pipeline.get("event_flows", [])
                    if flow.get("requirement_id") == requirement_id
                    for key in flow.get("server_consumer_keys", [])
                }
                for field in pipeline.get("field_flows", []):
                    if (
                        field.get("status") == "proved"
                        and requirement_id in field.get("requirement_ids", [])
                        and field.get("wire") == {"path": "user_data", "shape": "object"}
                        and field.get("event_data") == {"path": "user_data", "shape": "object"}
                        and field.get("receiver_owner") in event_receivers
                    ):
                        proved_receivers.add(field["receiver_owner"])
            if proved_receivers != set(receiver_keys):
                fail(
                    f"$.first_party_data_routes[{index}] server user_data transport requires "
                    "proved pipeline fields for exactly its authorized receiving consumers"
                )

    for target_id in sorted(web_target_ids):
        local_operations = _local_operations(operations, target_id, fail)
        target_requirement_ids = {
            requirement_id
            for operation in local_operations.values()
            for requirement_id in operation.get("requirement_ids", [])
        }
        local_topologies = []
        consent_enforcements = {}
        for index, topology in enumerate(topologies_by_target[target_id]):
            path = f"$.execution_topologies[{index}]"
            _validate_topology_consent_binding(
                topology, consent_by_id=consent_by_id, path=path, fail=fail
            )
            local_topologies.append(_local_topology(topology, target_id, path, fail))
            enforcements = [
                consent_by_id[key]["web_enforcement"] for key in topology["consent_topology_ids"]
            ]
            if any(item.get("mechanism") in ALTERNATIVE_GATES for item in enforcements) and any(
                item != enforcements[0] for item in enforcements
            ):
                fail("One web tag must have one consistent consent enforcement declaration")
            enforcement = enforcements[0]
            validate_convention(
                topology, enforcement, {item["object_key"]: item for item in operations}, fail
            )
            consent_enforcements[local_topologies[-1]["tag_object_key"]] = enforcement["mechanism"]
        try:
            validated_topologies = web._validate_execution_topologies(
                local_topologies,
                requirement_ids=set(requirement_ids),
                operations=local_operations,
                baseline_trigger_types={},
                consent_enforcements=consent_enforcements,
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

        for topology in validated_topologies.values():
            operation = next(
                item
                for item in local_operations.values()
                if item["object_key"] == topology["tag_object_key"]
            )
            target = web._effective_target(operation, "$.execution_topologies[].bound_tag")
            tag_type = web._tag_type(target, "$.execution_topologies[].bound_tag")
            if topology["lifecycle_role"] == "event-driven" and tag_type in web.GA4_EVENT_TAG_TYPES:
                approved_names = {
                    requirement_by_id[requirement_id].get("event_name")
                    for requirement_id in operation.get("requirement_ids", [])
                    if requirement_id in requirement_by_id
                } - {None}
                present, configured_name = web._configuration_value(
                    target, {"event_name", "eventName"}
                )
                if approved_names and (
                    len(approved_names) != 1 or not present or configured_name not in approved_names
                ):
                    fail(
                        f"GA4 event tag {operation['object_key']!r} eventName must equal its "
                        f"single approved event name; approved={sorted(approved_names)}"
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
        decision_occurrences = {(item["destination"], item["occurrence"]) for item in decisions}
        expected_occurrences = {
            (destination, occurrence)
            for topology in validated_topologies.values()
            for destination in topology["page_view_destinations"]
            for occurrence in topology["page_view_occurrences"]
        }
        if decision_occurrences != expected_occurrences:
            fail(
                f"web target {target_id!r} page-view decisions must exactly cover capable "
                f"destination occurrences; missing={sorted(expected_occurrences - decision_occurrences)}, "
                f"extra={sorted(decision_occurrences - expected_occurrences)}"
            )
        topology_by_key = {item["tag_object_key"]: item for item in validated_topologies.values()}
        for decision in decisions:
            owner_key = decision.get("owner_object_key")
            if decision["owner"] not in {
                "google-tag-automatic",
                "dedicated-ga4-event",
                "internal-tag",
            }:
                continue
            owner_topology = topology_by_key.get(owner_key)
            if owner_topology is None:
                fail(f"page-view owner {owner_key!r} lacks an execution topology")
                continue
            if decision["destination"] not in owner_topology["page_view_destinations"]:
                fail(f"page-view owner {owner_key!r} does not declare the destination")
            if decision["occurrence"] not in owner_topology["page_view_occurrences"]:
                fail(f"page-view owner {owner_key!r} does not declare the occurrence")

        actual_emitters: dict[tuple[str, str], list[str]] = {}
        trigger_emitters: dict[tuple[str, str], set[str]] = {}
        for topology in validated_topologies.values():
            operation = next(
                item
                for item in local_operations.values()
                if item["object_key"] == topology["tag_object_key"]
            )
            target = web._effective_target(operation, "$.execution_topologies[].bound_tag")
            tag_type = web._tag_type(target, "$.execution_topologies[].bound_tag")
            emits_page_view = False
            if tag_type in web.GOOGLE_CONFIGURATION_TAG_TYPES:
                emits_page_view = web._send_page_view_value(
                    target, "$.execution_topologies[].bound_tag", local_operations
                )
            elif tag_type in web.GA4_EVENT_TAG_TYPES:
                _, event_name = web._configuration_value(target, {"event_name", "eventName"})
                emits_page_view = event_name == "page_view"
            elif topology["page_view_capable"]:
                emits_page_view = True
            if tag_type in web.GOOGLE_CONFIGURATION_TAG_TYPES | web.GA4_EVENT_TAG_TYPES:
                try:
                    configured_destinations = web._configured_destinations(
                        target, local_operations, "$.execution_topologies[].bound_tag"
                    )
                except web.RunValidationError as exc:
                    fail(str(exc))
                    return
                ga4_destinations = {
                    value for value in configured_destinations if value.startswith("G-")
                }
                if tag_type in web.GOOGLE_CONFIGURATION_TAG_TYPES:
                    if not configured_destinations or (
                        any(value.startswith("GT-") for value in configured_destinations)
                        and not ga4_destinations
                        and not any(
                            value.startswith(("AW-", "DC-")) for value in configured_destinations
                        )
                    ):
                        fail(
                            "Google tag needs inspected destination identities before page-view ownership can be resolved"
                        )
                    emits_page_view = emits_page_view and bool(ga4_destinations)
                elif emits_page_view and not ga4_destinations:
                    fail("GA4 page_view tag needs a resolved GA4 destination")
                if emits_page_view:
                    if (
                        not topology["page_view_capable"]
                        or set(topology["page_view_destinations"]) != ga4_destinations
                    ):
                        fail(
                            "page-view declarations must cover every effective Google page-view destination"
                        )
                    if tag_type in web.GOOGLE_CONFIGURATION_TAG_TYPES and topology[
                        "page_view_occurrences"
                    ] != ["initial-page-load"]:
                        fail(
                            "Google tag automatic page-view declarations must include its initial-page-load occurrence only"
                        )
                elif topology["page_view_capable"]:
                    fail(
                        "Google tag page-view declarations describe a tag that does not emit page_view"
                    )
            if not emits_page_view:
                continue
            for destination in topology["page_view_destinations"]:
                for trigger in topology["normal_triggers"]:
                    trigger_emitters.setdefault(
                        (destination, trigger["trigger_object_key"]), set()
                    ).add(topology["tag_object_key"])
                try:
                    if tag_type in web.GOOGLE_CONFIGURATION_TAG_TYPES | web.GA4_EVENT_TAG_TYPES:
                        web._validate_google_destination(
                            target,
                            destination,
                            "$.execution_topologies[].bound_tag",
                            local_operations,
                        )
                except web.RunValidationError as exc:
                    fail(str(exc))
                for occurrence in topology["page_view_occurrences"]:
                    if (
                        tag_type in web.GOOGLE_CONFIGURATION_TAG_TYPES
                        and occurrence != "initial-page-load"
                    ):
                        continue
                    if (
                        occurrence == "virtual-navigation"
                        and topology["firing_option"] == "once-per-page"
                    ):
                        fail(
                            f"page-view emitter {topology['tag_object_key']!r} cannot use "
                            "once-per-page for virtual navigation"
                        )
                    actual_emitters.setdefault((destination, occurrence), []).append(
                        topology["tag_object_key"]
                    )
        for (destination, trigger_key), emitter_keys in trigger_emitters.items():
            if len(emitter_keys) > 1:
                fail(
                    f"page-view emitters for {destination!r} share firing trigger {trigger_key!r}; "
                    "different occurrence labels do not establish disjoint firing"
                )
        for decision in decisions:
            identity = (decision["destination"], decision["occurrence"])
            emitters = actual_emitters.get(identity, [])
            expected_owner = (
                decision.get("owner_object_key")
                if decision["owner"]
                in {"google-tag-automatic", "dedicated-ga4-event", "internal-tag"}
                else None
            )
            if expected_owner is None and emitters:
                fail(
                    f"page-view decision {identity!r} declares no internal owner but emitters={emitters}"
                )
            elif expected_owner is not None and emitters != [expected_owner]:
                fail(
                    f"page-view decision {identity!r} must have exactly its declared emitter; "
                    f"emitters={emitters}"
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
            validated_routes = web._validate_first_party_data_routes(
                local_routes,
                requirement_ids=set(requirement_ids),
                operations=local_operations,
                external_dependencies=dependencies,
                payload_mappings=mappings,
            )
        except web.RunValidationError as exc:
            fail(str(exc))
            return

        for route in validated_routes:
            if route["feature"] == "google-ads-server-user-provided-data-event":
                requirement = requirement_by_id.get(route["requirement_id"], {})
                source_event = approved_event_name(requirement)
                operations_by_key = {item["object_key"]: item for item in local_operations.values()}
                for consumer_key in route["consumer_object_keys"]:
                    topology = validated_topologies.get(consumer_key, {})
                    triggers = topology.get("normal_triggers", [])
                    if (
                        not source_event
                        or not triggers
                        or not all(
                            trigger_accepts_event(
                                web._effective_target(
                                    operations_by_key.get(trigger["trigger_object_key"], {}),
                                    "$.first_party_data_routes[].capture_trigger",
                                ),
                                source_event,
                            )
                            for trigger in triggers
                        )
                    ):
                        fail(
                            f"first-party route {route['requirement_id']!r} prior-page user_data "
                            "must resolve on its approved source event, not only at initialization; "
                            "use the documented event-scoped sender when data becomes available later"
                        )
            if route["feature"] not in {
                "google-ads-user-provided-data-event",
                "google-ads-enhanced-conversions",
            }:
                continue
            if route["feature"] == "google-ads-user-provided-data-event":
                requirement = requirement_by_id.get(route["requirement_id"], {})
                if requirement.get("source_event") != "gtm.formSubmit":
                    fail(
                        f"first-party route {route['requirement_id']!r} must bind the "
                        "gtm.formSubmit source event for prior-page browser capture"
                    )
                for consumer_key in route["consumer_object_keys"]:
                    topology = validated_topologies.get(consumer_key)
                    if topology is None or {
                        trigger["type"] for trigger in topology["normal_triggers"]
                    } != {"form-submission"}:
                        fail(
                            f"first-party route {route['requirement_id']!r} must bind the "
                            "native Form Submission trigger for prior-page browser capture"
                        )
            for consumer_key in route["consumer_object_keys"]:
                consumer = next(
                    item for item in local_operations.values() if item["object_key"] == consumer_key
                )
                _, binding_value = web._first_party_binding_value(
                    route,
                    web._effective_target(consumer, "$.first_party_data_routes[].consumer"),
                    consumer_key,
                    "$.first_party_data_routes[]",
                    local_operations,
                )
                if not (
                    isinstance(binding_value, str)
                    and binding_value.startswith("{{")
                    and binding_value.endswith("}}")
                ):
                    fail(
                        f"first-party route {route['requirement_id']!r} must reference a "
                        "User-Provided Data variable"
                    )
                    continue
                variable_name = binding_value[2:-2].strip()
                variable = next(
                    (
                        item
                        for item in local_operations.values()
                        if item["object_type"] == "variable" and item["name"] == variable_name
                    ),
                    None,
                )
                variable_type = (
                    web._normalized_token(
                        str(
                            web._effective_target(
                                variable, "$.first_party_data_routes[].variable"
                            ).get("type", "")
                        )
                    )
                    if variable is not None
                    else ""
                )
                if variable_type not in USER_DATA_VARIABLE_TYPES:
                    fail(
                        f"first-party route {route['requirement_id']!r} must bind a native "
                        "User-Provided Data variable"
                    )

        variable_targets = {
            operation["name"]: web._effective_target(operation, "$.variable")
            for operation in local_operations.values()
            if operation["object_type"] == "variable"
            and operation["action"] not in web.NON_EXECUTING_TAG_ACTIONS
        }
        authorized_variable_names: set[str] = set()
        authorized_consumer_variables: dict[str, set[str]] = {}
        operations_by_key = {item["object_key"]: item for item in local_operations.values()}
        for route in validated_routes:
            for consumer_key in route["consumer_object_keys"]:
                consumer = operations_by_key.get(consumer_key)
                if consumer is None:
                    continue
                target = web._effective_target(consumer, "$.first_party_data_routes[].consumer")
                present, binding = web._first_party_binding_value(
                    route, target, consumer_key, "$.first_party_data_routes[]", local_operations
                )
                if (
                    present
                    and isinstance(binding, str)
                    and binding.startswith("{{")
                    and binding.endswith("}}")
                ):
                    try:
                        bound_variables = referenced_variable_closure(binding, variable_targets)
                        authorized_variable_names.update(bound_variables)
                        authorized_consumer_variables.setdefault(consumer_key, set()).update(
                            bound_variables
                        )
                    except FieldResolutionError as exc:
                        fail(str(exc))
        user_data_variables = {
            operation["name"]
            for operation in local_operations.values()
            if operation["object_type"] == "variable"
            and operation["action"] not in web.NON_EXECUTING_TAG_ACTIONS
            and web._normalized_token(
                str(web._effective_target(operation, "$.variable").get("type", ""))
            )
            in USER_DATA_VARIABLE_TYPES
        }
        for operation in local_operations.values():
            if operation["action"] in web.NON_EXECUTING_TAG_ACTIONS:
                continue
            target = web._effective_target(operation, "$.implementation.objects[].intended")
            if operation["object_type"] == "tag":
                try:
                    fields = web._resolved_fields(target, local_operations, "$.first_party_scope")
                    references = referenced_variable_closure(fields, variable_targets)
                except (FieldResolutionError, web.RunValidationError) as exc:
                    fail(str(exc))
                    return
                configured_sensitive_fields = sensitive_fields(fields)
                approved_fields = {
                    field_key(route["destination_field"])
                    for route in validated_routes
                    if operation["object_key"] in route["consumer_object_keys"]
                }
                if configured_sensitive_fields - approved_fields or (
                    (references & user_data_variables)
                    - authorized_consumer_variables.get(operation["object_key"], set())
                ):
                    fail(
                        f"web tag {operation['object_key']!r} configures first-party user data "
                        "without an authorized first-party-data route"
                    )
            if (
                operation["object_type"] == "variable"
                and web._normalized_token(str(target.get("type", ""))) in USER_DATA_VARIABLE_TYPES
            ):
                if operation["name"] not in authorized_variable_names:
                    fail(
                        f"User-Provided Data variable {operation['object_key']!r} is not owned "
                        "by an authorized first-party-data route"
                    )

        if baseline_resources is not None:
            target_baseline = baseline_resources.get(target_id, {})
            baseline_tags = target_baseline.get("tag", [])
            for operation in local_operations.values():
                if not requires_variable_consumer_check(operation):
                    continue
                consumers = {
                    f"tag::{name}"
                    for name in variable_consumers(
                        operation, baseline_tags, target_baseline.get("variable", [])
                    )
                }
                missing_consumers = sorted(consumers - set(operations_by_key))
                if missing_consumers:
                    fail(
                        f"shared variable mutation {operation['object_key']!r} "
                        "does not include every authenticated baseline consumer: "
                        + ", ".join(missing_consumers)
                    )

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
            {
                _local_key(
                    value, target_id, "$.container_baselines[].resource_identities.tag", fail
                )
                for value in baseline_in_scope_tags.get(target_id, set())
            }
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
