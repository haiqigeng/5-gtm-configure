"""Cross-target transport, consent, shape, ordering, and dedup validation."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Callable

from gtm_configure.core.model import (
    PUBLICATION_ORDER,
)
from gtm_configure.domain.context import ConfigurationGraph
from gtm_configure.domain.deduplication import (
    validate_generated_event_ids,
    validate_pipeline_dedup,
    validate_sender_dedup,
)
from gtm_configure.domain.events import approved_event_name
from gtm_configure.domain.graph import active_tag, reference_name
from gtm_configure.domain.pipeline_declarations import (
    consent_transporters,
    validate_consent_policies,
    validate_dedup_contracts,
    validate_field_flow,
)
from gtm_configure.domain.web_native import (
    configured_destinations,
    configured_transport_endpoint,
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


def validate_pipeline(
    graph: ConfigurationGraph,
    fail: Callable[[str], None],
) -> None:
    mode = graph.mode
    target_types = graph.target_types
    pipelines = graph.pipelines
    if mode != "pipeline" and pipelines:
        fail("$.pipelines must be empty outside pipeline mode")
    if mode == "pipeline" and not pipelines:
        fail("pipeline mode requires at least one pipeline")
    by_operation = graph.by_id
    by_object_key = graph.by_key
    requirement_by_id = {item["id"]: item for item in graph.requirements}
    requirement_ids = set(requirement_by_id)
    objects = graph.by_key
    targets = {key: {"container_type": value} for key, value in target_types.items()}
    try:
        consent_by_id = validate_consent_policies(
            graph.consent_policies, requirement_ids, objects, targets, mode, graph.tag_policies
        )
        dedup_by_id = validate_dedup_contracts(graph.dedup_contracts, requirement_ids)
    except ValueError as exc:
        fail(str(exc))
        return
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
        transport_owner, transport_operation, resolved_endpoint, owner_destinations = (
            _validate_transport_owner(
                by_object_key=by_object_key,
                fail=fail,
                path=path,
                pipeline=pipeline,
                senders=senders,
            )
        )
        client_operation = pipeline.get("claiming_client_operation_id")
        if client_operation not in by_operation:
            fail(f"{path}.claiming_client_operation_id is unknown")
        elif by_operation[client_operation]["resource_family"] != "client":
            fail(f"{path}.claiming_client_operation_id must reference a Client")
        else:
            client = by_operation[client_operation]
            claiming = pipeline.get("claiming_client", {})
            if client["target_id"] != receiver:
                fail(f"{path}.claiming_client must belong to the receiver")
            if claiming.get("object_key") != client["object_key"] or claiming.get(
                "claim_criteria"
            ) != client.get("assertions", {}).get("client_claim", {}).get("description"):
                fail(f"{path}.claiming_client must bind the reviewed native Client assertion")
        request_class = pipeline.get("request_class")
        receiver_claims[(str(receiver), str(request_class))].add(str(client_operation))
        event_flows, flow_requirements = _validate_event_flows(
            by_operation=by_operation,
            fail=fail,
            path=path,
            pipeline=pipeline,
            receiver=receiver,
            requirement_by_id=requirement_by_id,
        )
        field_flows = _validate_field_flows(
            by_object_key=by_object_key,
            fail=fail,
            flow_requirements=flow_requirements,
            graph=graph,
            path=path,
            pipeline=pipeline,
            receiver=receiver,
            requirement_ids=requirement_ids,
        )
        topology_ids, pipeline_consumer_ids = _validate_pipeline_consent(
            by_object_key=by_object_key,
            by_operation=by_operation,
            tag_policies=graph.tag_policies,
            consent_by_id=consent_by_id,
            event_flows=event_flows,
            fail=fail,
            field_flows=field_flows,
            owner_destinations=owner_destinations,
            path=path,
            pipeline=pipeline,
            resolved_endpoint=resolved_endpoint,
            senders=senders,
            transport_owner=transport_owner,
        )
        _validate_dedup_bindings(
            by_object_key=by_object_key,
            dedup_by_id=dedup_by_id,
            event_flows=event_flows,
            fail=fail,
            linked_dedup_ids=linked_dedup_ids,
            path=path,
            pipeline=pipeline,
            senders=senders,
            transport_operation=transport_operation,
        )
        _validate_cutover(
            by_object_key=by_object_key,
            by_operation=by_operation,
            client_operation=client_operation,
            consent_by_id=consent_by_id,
            fail=fail,
            field_flows=field_flows,
            path=path,
            pipeline=pipeline,
            pipeline_consumer_ids=pipeline_consumer_ids,
            topology_ids=topology_ids,
            transport_operation=transport_operation,
        )
    for (target_id, request_class), clients in receiver_claims.items():
        if len(clients) != 1:
            fail(
                f"server target {target_id!r} request class {request_class!r} has "
                f"{len(clients)} intended claiming Clients"
            )
    if mode == "pipeline" and set(dedup_by_id) != linked_dedup_ids:
        fail(
            "dedup contracts must be linked to one pipeline; unlinked="
            + ", ".join(sorted(set(dedup_by_id) - linked_dedup_ids))
        )
    if mode == "web":
        validate_sender_dedup(
            graph.dedup_contracts,
            list(by_object_key.values()),
            graph.external_dependencies,
            fail,
        )
    elif mode == "server" and graph.dedup_contracts:
        fail("server-only runs cannot configure sender dedup contracts")
    if mode == "pipeline":
        validate_pipeline_dedup(
            graph.dedup_contracts,
            list(by_object_key.values()),
            graph.pipelines,
            fail,
        )
    validate_generated_event_ids(
        graph.dedup_contracts,
        list(by_object_key.values()),
        graph.tag_policies,
        target_types,
        fail,
        graph.container_baselines,
    )


def validate_publication_dependencies(
    dependencies: list[dict[str, Any]], mode: str, fail: Callable[[str], None]
) -> None:
    order = PUBLICATION_ORDER[mode]
    by_kind = {item.get("kind"): item for item in dependencies}
    if len(by_kind) != len(dependencies) or set(by_kind) != set(order):
        fail(
            "$.publication_dependencies must contain exactly the required acceptance/deployment steps"
        )
        return
    for index, kind in enumerate(order):
        expected = order[index - 1] if index else None
        if by_kind[kind].get("depends_on_kind") != expected:
            fail(f"{kind} must depend on {expected!r}; runtime acceptance precedes publication")
    if any(item.get("blocks_saved_configuration") is True for item in dependencies):
        fail("publication dependencies cannot block saved configuration status")


def _validate_transport_owner(*, by_object_key, fail, path, pipeline, senders):
    transport_owner = pipeline.get("transport_owner")
    transport_operation = by_object_key.get(transport_owner)
    if (
        transport_operation is None
        or transport_operation.get("resource_family") != "tag"
        or transport_operation.get("target_id") not in senders
    ):
        fail(f"{path}.transport_owner must reference a sender web tag")
    if transport_operation is None:
        return transport_owner, None, None, set()
    try:
        resolved_endpoint = configured_transport_endpoint(
            transport_operation, by_object_key, f"{path}.transport_owner"
        )
        if not resolved_endpoint:
            fail(f"{path}.transport_owner requires a resolved native transport endpoint")
        owner_destinations = configured_destinations(
            transport_operation.get("intended", {}), by_object_key, f"{path}.transport_owner"
        )
    except ValueError as exc:
        fail(str(exc))
        resolved_endpoint, owner_destinations = None, set()
    return transport_owner, transport_operation, resolved_endpoint, owner_destinations


def _validate_event_flows(*, by_operation, fail, path, pipeline, receiver, requirement_by_id):
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
                if (
                    requirement.get("kind") == "analytics"
                    and requirement.get("event_name")
                    and transported_event != requirement["event_name"]
                ):
                    fail(f"{flow_path}.transported_event differs from the approved analytics event")
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
    return event_flows, flow_requirements


def _validate_field_flows(
    *, by_object_key, fail, flow_requirements, graph, path, pipeline, receiver, requirement_ids
):
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
        validate_field_flow(field, field_path, requirement_ids)
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
                fail(f"{field_path}.transformation_owner must reference a receiver Transformation")
            elif transformation.get("assertions", {}).get("transformation", {}).get(
                "mode"
            ) == "allow" and field.get("wire", {}).get("path") not in set(
                transformation.get("assertions", {})
                .get("transformation", {})
                .get("allowed_parameters", [])
            ):
                fail(f"{field_path}.transformation_owner allowlist removes the proved wire field")
    mapped_identities = {
        (
            mapping["requirement_id"],
            mapping["field_scope"],
            mapping["destination_field"],
        )
        for mapping in graph.payload_mappings
        if mapping.get("status") == "mapped" and mapping.get("requirement_id") in flow_requirements
    }
    missing_field_flows = sorted(mapped_identities - field_flow_identities)
    if missing_field_flows:
        fail(f"{path}.field_flows misses mapped fields: {missing_field_flows}")
    return field_flows


def _validate_pipeline_consent(
    *,
    by_object_key,
    by_operation,
    consent_by_id,
    tag_policies,
    event_flows,
    fail,
    field_flows,
    owner_destinations,
    path,
    pipeline,
    resolved_endpoint,
    senders,
    transport_owner,
):
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
    topology_ids = [
        key
        for key, policy in consent_by_id.items()
        if pipeline_consumer_keys & set(policy["server_tag_keys"])
    ]
    topology_consumer_keys: set[str] = set()
    for topology_id in topology_ids:
        topology = consent_by_id.get(topology_id)
        if topology is None:
            fail(f"{path} references unknown consent topology {topology_id!r}")
            continue
        transporter_keys = consent_transporters(topology, tag_policies, "pipeline") | {
            transport_owner
        }
        if not transporter_keys:
            fail(f"{path} consent topology {topology_id!r} does not bind its transporter")
        if any(
            by_object_key.get(key, {}).get("target_id") not in senders for key in transporter_keys
        ):
            fail(f"{path} consent topology {topology_id!r} binds a non-sender transporter")
        for key in transporter_keys:
            operation = by_object_key.get(key)
            if operation is None:
                continue
            if key == transport_owner:
                continue
            try:
                direct_endpoint = configured_transport_endpoint(
                    operation,
                    by_object_key,
                    f"{path}.transporter_tag_keys[{key!r}]",
                )
                destinations = configured_destinations(
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
        server_keys = set(topology["server_tag_keys"]) & pipeline_consumer_keys
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
        missing = sorted(topology_events - set(topology.get("event_coverage", [])))
        if missing:
            fail(
                f"{path} consent topology {topology_id!r} is missing transported event "
                "coverage: " + ", ".join(missing)
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
    return topology_ids, pipeline_consumer_ids


def _validate_dedup_bindings(
    *,
    by_object_key,
    dedup_by_id,
    event_flows,
    fail,
    linked_dedup_ids,
    path,
    pipeline,
    senders,
    transport_operation,
):
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
            and dedup.get("event_name") in {flow.get("source_event"), flow.get("transported_event")}
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
            resolved_name = reference_name(str(dedup.get("source_reference", "")))
            if resolved_name is not None and variable.get("name") != resolved_name:
                fail(f"{path} dedup source reference differs from its variable object")
        browser_keys = set(dedup.get("browser_consumer_keys", []))
        transporter_keys = set(dedup.get("transporter_consumer_keys", []))
        if browser_keys & transporter_keys:
            fail(f"{path} browser and transporter dedup consumers must be distinct")
        for role, keys in (
            ("browser", browser_keys),
            ("transporter", transporter_keys),
        ):
            for key in keys:
                consumer = by_object_key.get(key)
                if (
                    consumer is None
                    or not active_tag(consumer)
                    or consumer.get("target_id") not in senders
                ):
                    fail(f"{path} {role} dedup consumers must be active sender tags")
                    continue
                if dedup.get("requirement_id") not in consumer.get("requirement_ids", []):
                    fail(f"{path} {role} dedup consumer lacks the dedup requirement")

                if role == "transporter" and transport_operation is not None:
                    if transport_operation["operation_id"] not in consumer.get("dependencies", []):
                        fail(f"{path} transporter dedup consumer lacks transport dependency")


def _validate_cutover(
    *,
    by_object_key,
    by_operation,
    client_operation,
    consent_by_id,
    fail,
    field_flows,
    path,
    pipeline,
    pipeline_consumer_ids,
    topology_ids,
    transport_operation,
):
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
        for owner_key in (
            field.get("receiver_owner"),
            field.get("transformation_owner"),
        ):
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
