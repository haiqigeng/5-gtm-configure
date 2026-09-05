"""Cross-target transport, consent, shape, ordering, and dedup validation."""

from __future__ import annotations

import re
from collections import defaultdict, deque
from typing import Any, Callable

from event_semantics import approved_event_name
from run_model import (
    CONSENT_SIGNAL_AUTHORITIES,
    DEDUP_SOURCE_TYPES,
    DEDUP_STRATEGIES,
    FIELD_FLOW_STATUSES,
    PUBLICATION_DEPENDENCY_KINDS,
    SERVER_CONSENT_MECHANISMS,
    SHAPES,
    TRANSPORT_BEHAVIORS,
    UNKNOWN_STATE_BEHAVIORS,
    WEB_CONSENT_MECHANISMS,
)
from run_validation_web import (
    GOOGLE_CONFIGURATION_TAG_TYPES,
    _configured_destinations,
    _configured_transport_endpoint,
    _normalize_transport_endpoint,
    _resolve_constant_reference,
    _send_page_view_value,
    _tag_type,
)


def validate_transport_consent(topology: dict[str, Any], fail: Callable[[str], None]) -> None:
    if (
        topology.get("consent_mode") == "strict-basic"
        and topology.get("transport_behavior") == "always-transported"
        and topology.get("server_enforcement", {}).get("mechanism")
        == "incoming-google-consent-native"
    ):
        fail(
            "strict-basic cannot use always-transported Google native denied-state behavior as a no-request gate"
        )


def _reference_values(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {item for child in value.values() for item in _reference_values(child)}
    if isinstance(value, list):
        return {item for child in value for item in _reference_values(child)}
    return {value} if isinstance(value, str) else set()


def _reference_name(value: str) -> str | None:
    match = re.fullmatch(r"\{\{\s*(.+?)\s*\}\}", value)
    return match.group(1) if match else None


def _active_tag(operation: dict[str, Any]) -> bool:
    intended = operation.get("intended") if isinstance(operation.get("intended"), dict) else {}
    return (
        operation.get("resource_family") == "tag"
        and operation.get("action") not in {"remove", "pause"}
        and intended.get("paused") is not True
    )


def _dependency_closure(operation_id: str, by_id: dict[str, dict[str, Any]]) -> set[str]:
    found: set[str] = set()
    queue = deque(by_id[operation_id].get("dependencies", []))
    while queue:
        dependency = queue.popleft()
        if dependency in found:
            continue
        found.add(dependency)
        queue.extend(by_id[dependency].get("dependencies", []))
    return found


def _validate_field_flow(
    field: dict[str, Any],
    path: str,
    requirement_ids: set[str],
    fail: Callable[[str], None],
) -> None:
    if field.get("field_scope") not in {
        "event-parameter",
        "user-property",
        "item-parameter",
        "control",
    }:
        fail(f"{path}.field_scope is unsupported")
    if (
        not isinstance(field.get("destination_field"), str)
        or not field["destination_field"].strip()
    ):
        fail(f"{path}.destination_field must be a non-empty string")
    if field.get("status") not in FIELD_FLOW_STATUSES:
        fail(f"{path}.status is unsupported")
    linked = field.get("requirement_ids")
    if not isinstance(linked, list) or not linked:
        fail(f"{path}.requirement_ids must be a non-empty array")
    elif len(set(linked)) != len(linked) or not set(linked) <= requirement_ids:
        fail(f"{path}.requirement_ids contains duplicate or unknown IDs")
    nodes = []
    for name in ("source", "wire", "event_data", "destination"):
        node = field.get(name)
        if not isinstance(node, dict):
            fail(f"{path}.{name} must be an object")
            return
        if not isinstance(node.get("path"), str) or not node["path"].strip():
            fail(f"{path}.{name}.path must be a non-empty string")
        if node.get("shape") not in SHAPES:
            fail(f"{path}.{name}.shape is unsupported")
        nodes.append(node)
    if field.get("status") == "proved":
        if not field.get("claiming_client_proof"):
            fail(f"{path}.claiming_client_proof is required")
        if not field.get("receiver_owner"):
            fail(f"{path}.receiver_owner is required")
        if len({node.get("shape") for node in nodes}) > 1 and not field.get("transformation_owner"):
            fail(f"{path}.transformation_owner is required when shapes differ")
    if field.get("status") == "blocked" and not field.get("blocker"):
        fail(f"{path}.blocker is required for a blocked field")
    if field.get("status") == "external" and not field.get("external_dependency"):
        fail(f"{path}.external_dependency is required for an external field")


def validate_pipeline_run(
    document: dict[str, Any],
    target_types: dict[str, str],
    fail: Callable[[str], None],
) -> None:
    mode = document["run"]["mode"]
    pipelines = document["pipelines"]
    if mode != "pipeline" and pipelines:
        fail("$.pipelines must be empty outside pipeline mode")
    if mode == "pipeline" and not pipelines:
        fail("pipeline mode requires at least one pipeline")
    by_operation = {item["operation_id"]: item for item in document["object_changes"]}
    by_object_key = {item["object_key"]: item for item in document["object_changes"]}
    requirement_by_id = {item["id"]: item for item in document["requirements"]}
    requirement_ids = set(requirement_by_id)
    consent_by_id: dict[str, dict[str, Any]] = {}
    server_tag_bindings: dict[str, list[str]] = defaultdict(list)
    for index, item in enumerate(document["consent_topologies"]):
        if not isinstance(item, dict):
            fail(f"$.consent_topologies[{index}] must be an object")
            continue
        topology_id = item.get("consent_topology_id")
        validate_transport_consent(item, fail)
        if not isinstance(topology_id, str) or not topology_id:
            fail(f"$.consent_topologies[{index}].consent_topology_id is required")
            continue
        if topology_id in consent_by_id:
            fail(f"duplicate consent topology {topology_id!r}")
        consent_by_id[topology_id] = item
        signal_authority = item.get("signal_authority")
        if signal_authority not in CONSENT_SIGNAL_AUTHORITIES:
            fail(f"$.consent_topologies[{index}].signal_authority is unsupported")
        server_tag_keys = item.get("server_tag_keys")
        transporter_tag_keys = item.get("transporter_tag_keys")
        if not isinstance(server_tag_keys, list):
            fail(f"$.consent_topologies[{index}].server_tag_keys must be an array")
            server_tag_keys = []
        if not isinstance(transporter_tag_keys, list):
            fail(f"$.consent_topologies[{index}].transporter_tag_keys must be an array")
            transporter_tag_keys = []
        if mode == "server" and not server_tag_keys:
            fail(f"$.consent_topologies[{index}].server_tag_keys must not be empty")
        if mode == "pipeline" and transporter_tag_keys and not server_tag_keys:
            fail(f"$.consent_topologies[{index}] transporter lacks server destination tags")
        if mode == "web" and (server_tag_keys or transporter_tag_keys):
            fail(f"$.consent_topologies[{index}] web-only topology binds server transport")
        if mode == "server" and transporter_tag_keys:
            fail(f"$.consent_topologies[{index}] server-only topology binds web transporters")
        vendor_block = item.get("transporter_destination_vendor_block")
        if not isinstance(vendor_block, bool):
            fail(
                f"$.consent_topologies[{index}].transporter_destination_vendor_block "
                "must be boolean"
            )
        for key in server_tag_keys:
            operation = by_object_key.get(key)
            if (
                operation is None
                or not _active_tag(operation)
                or target_types.get(operation.get("target_id")) != "server"
            ):
                fail(f"$.consent_topologies[{index}].server_tag_keys is invalid")
                continue
            server_tag_bindings[key].append(str(topology_id))
        for key in transporter_tag_keys:
            operation = by_object_key.get(key)
            if (
                operation is None
                or not _active_tag(operation)
                or target_types.get(operation.get("target_id")) != "web"
            ):
                fail(f"$.consent_topologies[{index}].transporter_tag_keys is invalid")
                continue
            if not vendor_block and operation.get("intended", {}).get("blockingTriggerId", []):
                fail(f"$.consent_topologies[{index}] transporter inherits a vendor block")
        web_mechanism = item.get("web_enforcement", {}).get("mechanism")
        transport_behavior = item.get("transport_behavior")
        if transporter_tag_keys and not vendor_block:
            if web_mechanism != "transport-trigger-only":
                fail(f"$.consent_topologies[{index}] needs transport-trigger-only enforcement")
            if transport_behavior == "blocked":
                fail(
                    f"$.consent_topologies[{index}] unblocked transporter declares blocked transport"
                )
        if vendor_block:
            if transport_behavior != "blocked":
                fail(f"$.consent_topologies[{index}] transporter block needs blocked transport")
            if web_mechanism not in {
                "cmp-lifecycle-plus-vendor-block",
                "business-trigger-plus-vendor-block",
            }:
                fail(f"$.consent_topologies[{index}] lacks a vendor-block web mechanism")
            if any(
                not by_object_key.get(key, {}).get("intended", {}).get("blockingTriggerId", [])
                for key in transporter_tag_keys
            ):
                fail(f"$.consent_topologies[{index}] lacks a saved transporter block")
        mechanism = item.get("server_enforcement", {}).get("mechanism")
        if signal_authority == "third-party-cmp":
            if server_tag_keys and not item.get("server_signal_path"):
                fail(f"$.consent_topologies[{index}].server_signal_path is required")
            if item.get("unknown_state_behavior") != "deny":
                fail(f"$.consent_topologies[{index}] third-party CMP must fail unknown closed")
            if server_tag_keys and mechanism not in {
                "server-blocking-trigger",
                "server-template-native-consent",
            }:
                fail(f"$.consent_topologies[{index}] third-party CMP lacks a server vendor gate")
        if signal_authority == "google-consent-mode" and server_tag_keys:
            if mechanism != "incoming-google-consent-native":
                fail(f"$.consent_topologies[{index}] Google consent lacks native enforcement")
            if item.get("unknown_state_behavior") != "native-product-behavior":
                fail(f"$.consent_topologies[{index}] Google consent behavior is inconsistent")
        if mechanism == "server-blocking-trigger":
            blocking_key = item.get("server_enforcement", {}).get("blocking_trigger_key")
            blocking_operation = by_object_key.get(blocking_key)
            if blocking_operation is None or blocking_operation.get("resource_family") != "trigger":
                fail(f"$.consent_topologies[{index}] server blocking trigger is unresolved")
            else:
                for tag_key in server_tag_keys:
                    tag = by_object_key.get(tag_key, {})
                    if blocking_operation.get("target_id") != tag.get("target_id"):
                        fail(f"$.consent_topologies[{index}] server blocking target differs")
                    if blocking_key not in tag.get("intended", {}).get("blockingTriggerId", []):
                        fail(f"$.consent_topologies[{index}] server tag lacks vendor block")
        elif server_tag_keys:
            for tag_key in server_tag_keys:
                if by_object_key.get(tag_key, {}).get("intended", {}).get("blockingTriggerId", []):
                    fail(f"$.consent_topologies[{index}] native/no-gate tag has a custom block")
    active_server_tags = {
        key
        for key, operation in by_object_key.items()
        if _active_tag(operation) and target_types.get(operation.get("target_id")) == "server"
    }
    missing_server_consent = sorted(active_server_tags - set(server_tag_bindings))
    duplicate_server_consent = sorted(
        key for key, links in server_tag_bindings.items() if len(links) != 1
    )
    if missing_server_consent or duplicate_server_consent:
        fail(
            "server destination tags need exactly one consent topology; "
            f"missing={missing_server_consent}, duplicates={duplicate_server_consent}"
        )
    dedup_by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(document["dedup_contracts"]):
        if not isinstance(item, dict):
            fail(f"$.dedup_contracts[{index}] must be an object")
            continue
        contract_id = item.get("dedup_contract_id")
        if not isinstance(contract_id, str) or not contract_id:
            fail(f"$.dedup_contracts[{index}].dedup_contract_id is required")
            continue
        if contract_id in dedup_by_id:
            fail(f"duplicate dedup contract {contract_id!r}")
        dedup_by_id[contract_id] = item
    pipeline_ids: set[str] = set()
    linked_dedup_ids: set[str] = set()
    receiver_claims: dict[tuple[str, str], set[str]] = defaultdict(set)
    for index, pipeline in enumerate(pipelines):
        path = f"$.pipelines[{index}]"
        pipeline_id = pipeline.get("pipeline_id")
        if not isinstance(pipeline_id, str) or not pipeline_id:
            fail(f"{path}.pipeline_id must be a non-empty string")
            continue
        if pipeline_id in pipeline_ids:
            fail(f"duplicate pipeline_id {pipeline_id!r}")
        pipeline_ids.add(pipeline_id)
        senders = pipeline.get("sending_target_ids", [])
        receiver = pipeline.get("receiving_target_id")
        if not senders or any(target_types.get(value) != "web" for value in senders):
            fail(f"{path}.sending_target_ids must contain web targets")
        if target_types.get(receiver) != "server":
            fail(f"{path}.receiving_target_id must be a server target")
        transport_owner = pipeline.get("transport_owner")
        transport_operation = by_object_key.get(transport_owner)
        if (
            transport_operation is None
            or transport_operation.get("resource_family") != "tag"
            or transport_operation.get("target_id") not in senders
        ):
            fail(f"{path}.transport_owner must reference a sender web tag")
        endpoint_reference = pipeline.get("endpoint_reference")
        if not isinstance(endpoint_reference, str) or not endpoint_reference.strip():
            fail(f"{path}.endpoint_reference must be a non-empty string")
            resolved_endpoint = None
        else:
            try:
                resolved_endpoint = _normalize_transport_endpoint(
                    _resolve_constant_reference(
                        endpoint_reference, by_object_key, f"{path}.endpoint_reference"
                    ),
                    f"{path}.endpoint_reference",
                )
            except ValueError as exc:
                fail(str(exc))
                resolved_endpoint = None
        if transport_operation is not None:
            try:
                owner_endpoint = _configured_transport_endpoint(
                    transport_operation, by_object_key, f"{path}.transport_owner"
                )
                owner_destinations = _configured_destinations(
                    transport_operation.get("intended", {}),
                    by_object_key,
                    f"{path}.transport_owner",
                )
            except ValueError as exc:
                fail(str(exc))
                owner_endpoint = None
                owner_destinations = set()
            if owner_endpoint != resolved_endpoint:
                fail(f"{path}.endpoint_reference differs from its transport owner")
        else:
            owner_destinations = set()
        page_view = pipeline.get("page_view_ownership")
        if not isinstance(page_view, dict) or not page_view.get("owner"):
            fail(f"{path}.page_view_ownership must name the owner")
        else:
            if page_view.get("occurrence") != "initial-page-load":
                fail(f"{path}.page_view_ownership.occurrence must be 'initial-page-load'")
            owner_operation = by_object_key.get(page_view["owner"])
            if (
                owner_operation is None
                or owner_operation.get("resource_family") != "tag"
                or owner_operation.get("target_id") not in senders
            ):
                fail(f"{path}.page_view_ownership.owner must reference a sender web tag")
            else:
                intended = owner_operation.get("intended")
                if not isinstance(intended, dict):
                    fail(f"{path}.page_view_ownership owner lacks intended state")
                else:
                    owner_type = _tag_type(intended, path)
                    if owner_type in GOOGLE_CONFIGURATION_TAG_TYPES:
                        if page_view.get("send_page_view") not in {True, False}:
                            fail(
                                f"{path}.page_view_ownership.send_page_view must be boolean "
                                "for a Google tag"
                            )
                        elif (
                            _send_page_view_value(intended, path, by_object_key)
                            != page_view["send_page_view"]
                        ):
                            fail(f"{path}.page_view_ownership differs from its bound Google tag")
                    elif page_view.get("send_page_view") is not None:
                        fail(
                            f"{path}.page_view_ownership.send_page_view must be null for a "
                            "non-Google sender"
                        )
        client_operation = pipeline.get("claiming_client_operation_id")
        if client_operation not in by_operation:
            fail(f"{path}.claiming_client_operation_id is unknown")
        elif by_operation[client_operation]["resource_family"] != "client":
            fail(f"{path}.claiming_client_operation_id must reference a Client")
        request_class = pipeline.get("request_class")
        receiver_claims[(str(receiver), str(request_class))].add(str(client_operation))
        event_flows = pipeline.get("event_flows")
        if not isinstance(event_flows, list) or not event_flows:
            fail(f"{path}.event_flows must be a non-empty array")
            event_flows = []
        flow_requirements: set[str] = set()
        for flow_index, flow in enumerate(event_flows):
            flow_path = f"{path}.event_flows[{flow_index}]"
            if not isinstance(flow, dict):
                fail(f"{flow_path} must be an object")
                continue
            source_event = flow.get("source_event")
            if not isinstance(source_event, str) or not source_event:
                fail(f"{flow_path}.source_event is required")
            transported_event = flow.get("transported_event")
            requirement_id = flow.get("requirement_id")
            if not isinstance(transported_event, str) or not transported_event:
                fail(f"{flow_path}.transported_event is required")
            if not isinstance(requirement_id, str) or not requirement_id:
                fail(f"{flow_path}.requirement_id is required")
            else:
                flow_requirements.add(requirement_id)
                requirement = requirement_by_id.get(requirement_id)
                if requirement is None:
                    fail(f"{flow_path}.requirement_id is unknown")
                else:
                    approved_event = approved_event_name(requirement)
                    if approved_event and flow.get("source_event") != approved_event:
                        fail(f"{flow_path}.source_event differs from its approved requirement")
            consumers = flow.get("server_consumer_operation_ids")
            if not isinstance(consumers, list) or not consumers:
                fail(f"{flow_path}.server_consumer_operation_ids must not be empty")
                continue
            for consumer_id in consumers:
                consumer = by_operation.get(consumer_id)
                if (
                    consumer is None
                    or consumer.get("target_id") != receiver
                    or consumer.get("resource_family") != "tag"
                ):
                    fail(f"{flow_path} references a non-receiver server tag")
        field_flows = pipeline.get("field_flows")
        if not isinstance(field_flows, list):
            fail(f"{path}.field_flows must be an array")
            field_flows = []
        field_flow_identities: set[tuple[str, str, str]] = set()
        for field_index, field in enumerate(field_flows):
            field_path = f"{path}.field_flows[{field_index}]"
            if not isinstance(field, dict):
                fail(f"{field_path} must be an object")
                continue
            _validate_field_flow(field, field_path, requirement_ids, fail)
            if not set(field.get("requirement_ids", [])) <= flow_requirements:
                fail(f"{field_path}.requirement_ids must belong to this pipeline")
            for requirement_id in field.get("requirement_ids", []):
                identity = (
                    requirement_id,
                    str(field.get("field_scope")),
                    str(field.get("destination_field")),
                )
                if identity in field_flow_identities:
                    fail(f"{field_path} duplicates pipeline field flow {identity!r}")
                field_flow_identities.add(identity)
            if field.get("status") != "proved":
                continue
            owner = by_object_key.get(field.get("receiver_owner"))
            if (
                owner is None
                or owner.get("resource_family") != "tag"
                or owner.get("target_id") != receiver
            ):
                fail(f"{field_path}.receiver_owner must reference a receiver tag")
            elif not set(field.get("requirement_ids", [])) <= set(owner.get("requirement_ids", [])):
                fail(f"{field_path}.receiver_owner misses field requirements")
            transformation_key = field.get("transformation_owner")
            if transformation_key:
                transformation = by_object_key.get(transformation_key)
                if (
                    transformation is None
                    or transformation.get("resource_family") != "transformation"
                    or transformation.get("target_id") != receiver
                ):
                    fail(
                        f"{field_path}.transformation_owner must reference a receiver "
                        "Transformation"
                    )
                elif transformation.get("intended", {}).get("mode") == "allow" and field.get(
                    "wire", {}
                ).get("path") not in set(
                    transformation.get("intended", {}).get("allowed_parameters", [])
                ):
                    fail(
                        f"{field_path}.transformation_owner allowlist removes the proved wire field"
                    )
        mapped_identities = {
            (
                mapping["requirement_id"],
                mapping["field_scope"],
                mapping["destination_field"],
            )
            for mapping in document["payload_mappings"]
            if mapping.get("status") == "mapped"
            and mapping.get("requirement_id") in flow_requirements
        }
        missing_field_flows = sorted(mapped_identities - field_flow_identities)
        if missing_field_flows:
            fail(f"{path}.field_flows misses mapped fields: {missing_field_flows}")
        topology_ids = pipeline.get("consent_topology_ids")
        if not isinstance(topology_ids, list) or not topology_ids:
            fail(f"{path}.consent_topology_ids must be a non-empty array")
            topology_ids = []
        pipeline_consumer_ids = {
            consumer_id
            for flow in event_flows
            for consumer_id in flow.get("server_consumer_operation_ids", [])
        }
        pipeline_consumer_keys = {
            by_operation[operation_id]["object_key"]
            for operation_id in pipeline_consumer_ids
            if operation_id in by_operation
        }
        topology_consumer_keys: set[str] = set()
        for topology_id in topology_ids:
            topology = consent_by_id.get(topology_id)
            if topology is None:
                fail(f"{path} references unknown consent topology {topology_id!r}")
                continue
            transporter_keys = set(topology.get("transporter_tag_keys", []))
            if not transporter_keys:
                fail(f"{path} consent topology {topology_id!r} does not bind its transporter")
            if any(
                by_object_key.get(key, {}).get("target_id") not in senders
                for key in transporter_keys
            ):
                fail(f"{path} consent topology {topology_id!r} binds a non-sender transporter")
            for key in transporter_keys:
                operation = by_object_key.get(key)
                if operation is None:
                    continue
                if key == transport_owner:
                    continue
                try:
                    direct_endpoint = _configured_transport_endpoint(
                        operation, by_object_key, f"{path}.transporter_tag_keys[{key!r}]"
                    )
                    destinations = _configured_destinations(
                        operation.get("intended", {}),
                        by_object_key,
                        f"{path}.transporter_tag_keys[{key!r}]",
                    )
                except ValueError as exc:
                    fail(str(exc))
                    continue
                if direct_endpoint != resolved_endpoint and not (
                    destinations and destinations & owner_destinations
                ):
                    fail(
                        f"{path} consent topology {topology_id!r} transporter {key!r} "
                        "does not inherit the proved endpoint"
                    )
            server_keys = set(topology.get("server_tag_keys", []))
            topology_consumer_keys.update(server_keys)
            if not server_keys <= pipeline_consumer_keys:
                fail(f"{path} consent topology {topology_id!r} binds a tag outside its flows")
            topology_consumer_ids = {
                by_object_key[key]["operation_id"] for key in server_keys if key in by_object_key
            }
            topology_flows = [
                flow
                for flow in event_flows
                if topology_consumer_ids & set(flow.get("server_consumer_operation_ids", []))
            ]
            topology_requirements = {
                flow.get("requirement_id") for flow in topology_flows if flow.get("requirement_id")
            }
            sender_requirements = {
                requirement_id
                for key in transporter_keys
                for requirement_id in by_object_key.get(key, {}).get("requirement_ids", [])
            }
            if not topology_requirements <= sender_requirements:
                fail(f"{path} consent topology {topology_id!r} does not bind its event senders")
            topology_events = {
                flow.get("transported_event")
                for flow in topology_flows
                if flow.get("transported_event")
            }
            if not topology_requirements <= set(topology.get("requirement_ids", [])):
                fail(f"{path} consent topology {topology_id!r} misses destination requirements")
            missing = sorted(topology_events - set(topology.get("event_coverage", [])))
            if missing:
                fail(
                    f"{path} consent topology {topology_id!r} is missing transported event "
                    "coverage: " + ", ".join(missing)
                )
            mechanism = topology.get("server_enforcement", {}).get("mechanism")
            if mechanism not in SERVER_CONSENT_MECHANISMS:
                fail(f"consent topology {topology_id!r} has an unsupported server mechanism")
            if topology.get("transport_behavior") not in TRANSPORT_BEHAVIORS:
                fail(f"consent topology {topology_id!r} has unsupported transport behavior")
            if topology.get("unknown_state_behavior") not in UNKNOWN_STATE_BEHAVIORS:
                fail(f"consent topology {topology_id!r} has unsupported unknown-state behavior")
            if topology.get("consent_mode") not in {
                "strict-basic",
                "advanced-native",
                "product-specific",
            }:
                fail(f"consent topology {topology_id!r} has unsupported consent mode")
            if topology.get("web_enforcement", {}).get("mechanism") not in WEB_CONSENT_MECHANISMS:
                fail(f"consent topology {topology_id!r} has unsupported web mechanism")
            if mechanism == "server-additional-consent-check" and not topology.get(
                "server_enforcement", {}
            ).get("template_support"):
                fail(
                    f"consent topology {topology_id!r} lacks exact Additional Consent Check support"
                )
            if topology.get("intentional_double_gate") and not topology.get(
                "double_gate_justification"
            ):
                fail(f"consent topology {topology_id!r} lacks double-gate justification")
            if (
                topology.get("transport_behavior") == "blocked"
                and mechanism
                in {
                    "server-template-native-consent",
                    "server-additional-consent-check",
                    "server-blocking-trigger",
                }
                and not topology.get("intentional_double_gate")
            ):
                fail(f"consent topology {topology_id!r} has an accidental double gate")
            if (
                not (
                    topology.get("transport_behavior") == "blocked"
                    and mechanism
                    in {
                        "server-template-native-consent",
                        "server-additional-consent-check",
                        "server-blocking-trigger",
                    }
                )
                and topology.get("intentional_double_gate") is True
            ):
                fail(f"consent topology {topology_id!r} declares a double gate without two gates")
            if mechanism in {"server-blocking-trigger", "server-template-native-consent"}:
                if topology.get("transporter_destination_vendor_block") is True:
                    fail(
                        f"consent topology {topology_id!r} repeats the destination vendor gate "
                        "on the transporter"
                    )
            if topology.get("signal_authority") == "third-party-cmp":
                signal_path = topology.get("server_signal_path")
                covered_requirements = {
                    requirement_id
                    for field in field_flows
                    if field.get("status") == "proved"
                    and field.get("event_data", {}).get("path") == signal_path
                    for requirement_id in field.get("requirement_ids", [])
                }
                if not topology_requirements <= covered_requirements:
                    fail(f"{path} third-party CMP signal is not proved on every destination flow")
        if pipeline_consumer_keys != topology_consumer_keys:
            missing_keys = sorted(pipeline_consumer_keys - topology_consumer_keys)
            extra_keys = sorted(topology_consumer_keys - pipeline_consumer_keys)
            fail(
                f"{path} consent topology bindings differ from server consumers; "
                f"missing={missing_keys}, extra={extra_keys}"
            )
        for dedup_id in pipeline.get("dedup_contract_ids", []):
            if dedup_id not in dedup_by_id:
                fail(f"{path} references unknown dedup contract {dedup_id!r}")
                continue
            linked_dedup_ids.add(dedup_id)
            dedup = dedup_by_id[dedup_id]
            matching_flows = [
                flow
                for flow in event_flows
                if flow.get("requirement_id") == dedup.get("requirement_id")
                and dedup.get("event_name")
                in {flow.get("source_event"), flow.get("transported_event")}
            ]
            if not matching_flows:
                fail(f"{path} dedup contract {dedup_id!r} is detached from its event flow")
            if dedup.get("strategy") != "dual-shared-id":
                continue
            variable_key = dedup.get("source_variable_key")
            variable = by_object_key.get(variable_key)
            if (
                variable is None
                or variable.get("resource_family") != "variable"
                or variable.get("target_id") not in senders
            ):
                fail(f"{path} dedup contract {dedup_id!r} needs a sender web variable")
            else:
                reference_name = _reference_name(str(dedup.get("source_reference", "")))
                if reference_name is not None and variable.get("name") != reference_name:
                    fail(f"{path} dedup source reference differs from its variable object")
            browser_keys = set(dedup.get("browser_consumer_keys", []))
            transporter_keys = set(dedup.get("transporter_consumer_keys", []))
            if browser_keys & transporter_keys:
                fail(f"{path} browser and transporter dedup consumers must be distinct")
            for role, keys in (("browser", browser_keys), ("transporter", transporter_keys)):
                for key in keys:
                    consumer = by_object_key.get(key)
                    if (
                        consumer is None
                        or not _active_tag(consumer)
                        or consumer.get("target_id") not in senders
                    ):
                        fail(f"{path} {role} dedup consumers must be active sender tags")
                        continue
                    if dedup.get("requirement_id") not in consumer.get("requirement_ids", []):
                        fail(f"{path} {role} dedup consumer lacks the dedup requirement")
                    if dedup.get("source_reference") not in _reference_values(
                        consumer.get("intended", {})
                    ):
                        fail(f"{path} {role} dedup consumer does not use the shared ID")
                    if role == "transporter" and transport_operation is not None:
                        if transport_operation["operation_id"] not in consumer.get(
                            "dependencies", []
                        ):
                            fail(f"{path} transporter dedup consumer lacks transport dependency")
        cutover = pipeline.get("cutover_operation_id")
        required = set(pipeline.get("operation_dependencies", []))
        unknown_dependencies = sorted(required - set(by_operation))
        if unknown_dependencies:
            fail(
                f"{path}.operation_dependencies references unknown operations: "
                + ", ".join(unknown_dependencies)
            )
        required_receivers = {client_operation} if client_operation in by_operation else set()
        required_receivers.update(pipeline_consumer_ids)
        for field in field_flows:
            if field.get("status") != "proved":
                continue
            for owner_key in (field.get("receiver_owner"), field.get("transformation_owner")):
                owner = by_object_key.get(owner_key)
                if owner is not None:
                    required_receivers.add(owner["operation_id"])
        for topology_id in topology_ids:
            blocking_key = (
                consent_by_id.get(topology_id, {})
                .get("server_enforcement", {})
                .get("blocking_trigger_key")
            )
            blocking = by_object_key.get(blocking_key)
            if blocking is not None:
                required_receivers.add(blocking["operation_id"])
        missing_dependencies = sorted(required_receivers - required)
        if missing_dependencies:
            fail(
                f"{path}.operation_dependencies misses receiver prerequisites: "
                + ", ".join(missing_dependencies)
            )
        if cutover is None:
            fail(f"{path}.cutover_operation_id is required")
        elif cutover not in by_operation:
            fail(f"{path}.cutover_operation_id is unknown")
        else:
            if transport_operation is None or cutover != transport_operation["operation_id"]:
                fail(f"{path}.cutover_operation_id must be the pipeline transport owner")
            closure = _dependency_closure(cutover, by_operation)
            missing = sorted(required_receivers - closure)
            if missing:
                fail(
                    f"{path} cutover does not depend on every receiver prerequisite: "
                    + ", ".join(missing)
                )
            if by_operation[cutover].get("risk") != "high-impact":
                fail(f"{path}.cutover_operation_id must be high-impact")
    for (target_id, request_class), clients in receiver_claims.items():
        if len(clients) != 1:
            fail(
                f"server target {target_id!r} request class {request_class!r} has "
                f"{len(clients)} intended claiming Clients"
            )
    if set(dedup_by_id) != linked_dedup_ids:
        fail(
            "dedup contracts must be linked to one pipeline; unlinked="
            + ", ".join(sorted(set(dedup_by_id) - linked_dedup_ids))
        )
    _validate_dedup(document["dedup_contracts"], requirement_ids, fail)
    _validate_publication_dependencies(document["publication_dependencies"], mode, fail)


def _validate_dedup(
    contracts: list[dict[str, Any]],
    requirement_ids: set[str],
    fail: Callable[[str], None],
) -> None:
    seen: set[str] = set()
    for index, contract in enumerate(contracts):
        path = f"$.dedup_contracts[{index}]"
        contract_id = contract.get("dedup_contract_id")
        if not isinstance(contract_id, str) or not contract_id:
            fail(f"{path}.dedup_contract_id must be a non-empty string")
            continue
        if contract_id in seen:
            fail(f"duplicate dedup contract {contract_id!r}")
        seen.add(contract_id)
        if contract.get("requirement_id") not in requirement_ids:
            fail(f"{path}.requirement_id is unknown")
        strategy = contract.get("strategy")
        source_type = contract.get("source_type")
        if strategy not in DEDUP_STRATEGIES:
            fail(f"{path}.strategy is unsupported")
        if source_type not in DEDUP_SOURCE_TYPES:
            fail(f"{path}.source_type is unsupported")
        if strategy == "dual-shared-id":
            normalized_destination = "".join(
                character
                for character in str(contract.get("destination", "")).casefold()
                if character.isalnum()
            )
            if normalized_destination in {"googleads", "floodlight", "campaignmanager360"}:
                fail(
                    f"{path} cannot apply generic dual-shared-id to {contract.get('destination')!r}"
                )
            if contract.get("server_generates_id") is True:
                fail(f"{path} regenerates an identifier in the server")
            if not contract.get("source_variable_key"):
                fail(f"{path}.source_variable_key is required")
            for field in ("browser_consumer_keys", "transporter_consumer_keys"):
                values = contract.get(field)
                if not isinstance(values, list) or not values:
                    fail(f"{path}.{field} must be a non-empty array")
                elif len(values) != len(set(values)):
                    fail(f"{path}.{field} contains duplicates")
            if contract.get("server_event_data_path") != contract.get("transported_parameter"):
                fail(f"{path} does not consume the transported identifier")
            if (
                len(
                    {
                        contract.get("source_reference"),
                        contract.get("browser_reference"),
                        contract.get("transporter_reference"),
                    }
                )
                != 1
            ):
                fail(f"{path} does not bind both routes to one occurrence source")
            for field in ("browser_field", "server_field", "occurrence_scope"):
                if not contract.get(field):
                    fail(f"{path}.{field} is required")


def _validate_publication_dependencies(
    dependencies: list[dict[str, Any]], mode: str, fail: Callable[[str], None]
) -> None:
    if mode == "web":
        if dependencies:
            fail("$.publication_dependencies must be empty in web-only mode")
        return
    by_kind = {item.get("kind"): item for item in dependencies}
    if len(by_kind) != len(dependencies):
        fail("$.publication_dependencies contains duplicate kinds")
    expected = (
        {"server-publication", "server-recette"}
        if mode == "server"
        else PUBLICATION_DEPENDENCY_KINDS
    )
    missing = sorted(expected - set(by_kind))
    if missing:
        fail("$.publication_dependencies misses: " + ", ".join(missing))
        return
    extra = sorted(set(by_kind) - expected)
    if extra:
        fail("$.publication_dependencies has unexpected kinds: " + ", ".join(extra))
    if by_kind["server-recette"].get("depends_on_kind") != "server-publication":
        fail("server recette must depend on server publication")
    if mode == "server":
        if any(item.get("blocks_saved_configuration") is True for item in dependencies):
            fail("publication dependencies cannot block saved configuration status")
        return
    if by_kind["web-cutover-publication"].get("depends_on_kind") != "server-recette":
        fail("web cutover publication must depend on server recette")
    if by_kind["web-pipeline-recette"].get("depends_on_kind") != "web-cutover-publication":
        fail("web/end-to-end recette must depend on web cutover publication")
    if any(item.get("blocks_saved_configuration") is True for item in dependencies):
        fail("publication dependencies cannot block saved configuration status")
