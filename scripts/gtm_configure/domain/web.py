"""Client-container parity validation for contract and run.

Validate one web target at a time after semantic keys are localized, then apply
cross-target rules separately without duplicating GTM-specific rules.
"""

from __future__ import annotations

from typing import Any, Callable

import gtm_configure.core.validation as validation
import gtm_configure.domain.execution as execution
import gtm_configure.domain.fields as field_rules
import gtm_configure.domain.first_party_data as first_party_data
import gtm_configure.domain.inventory as inventory
import gtm_configure.domain.page_views as page_views
from gtm_configure.core.model import EXECUTION_MODES
from gtm_configure.domain.context import ConfigurationGraph
from gtm_configure.domain.graph import external_dependency_index
from gtm_configure.domain.localization import (
    localize_operations,
    web_sections_by_target,
)


def validate_web_domain(
    *,
    execution_mode: str,
    graph: ConfigurationGraph,
    execution_topologies: list[dict[str, Any]],
    page_view_decisions: list[dict[str, Any]],
    first_party_data_routes: list[dict[str, Any]],
    external_dependencies: list[Any],
    fail: Callable[[str], None],
    baseline_in_scope_tags: dict[str, set[str]] | None = None,
    baseline_resources: dict[str, dict[str, list[dict[str, Any]]]] | None = None,
) -> None:
    """Validate the complete client-side decision surface for each web target."""
    requirements, operations, target_types = (
        graph.requirements,
        graph.operations,
        graph.target_types,
    )
    payload_mappings, consent_topologies = graph.payload_mappings, graph.consent_topologies
    pipelines, inventory_dispositions = graph.pipelines, graph.inventory_dispositions
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
    first_party_data.validate_server_identity_consumers(
        fail=fail,
        first_party_data_routes=first_party_data_routes,
        operations=operations,
        target_types=target_types,
    )

    try:
        mappings = field_rules.validate_payload_mappings(payload_mappings, set(requirement_ids))
    except validation.RunValidationError as exc:
        fail(str(exc))
        return
    field_rules.validate_native_mappings(mappings, operations, fail)
    dependencies = external_dependency_index(external_dependencies, set(requirement_ids), fail)
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
    valid_inventory_links = {item.get("operation_id") for item in operations}
    inventory_link_field = "operation_ids"
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
    topologies_by_target = web_sections_by_target(
        execution_topologies, "tag_object_key", web_target_ids
    )
    first_party_data.validate_transport_routes(
        dependencies=dependencies,
        fail=fail,
        first_party_data_routes=first_party_data_routes,
        operations=operations,
        pipelines=pipelines,
        target_types=target_types,
        web_target_ids=web_target_ids,
    )

    for target_id in sorted(web_target_ids):
        local_operations = localize_operations(operations, target_id, fail)
        target_requirement_ids = {
            requirement_id
            for operation in local_operations.values()
            for requirement_id in operation.get("requirement_ids", [])
        }
        validated_topologies = execution.validate_target_execution(
            local_operations=local_operations,
            consent_by_id=consent_by_id,
            fail=fail,
            non_consent_requirement_ids=non_consent_requirement_ids,
            operations=operations,
            requirement_by_id=requirement_by_id,
            requirement_ids=requirement_ids,
            target_id=target_id,
            topologies_by_target=topologies_by_target,
            transporter_keys=transporter_keys,
        )

        page_views.validate_target_page_views(
            local_operations=local_operations,
            dependencies=dependencies,
            fail=fail,
            page_view_decisions=page_view_decisions,
            requirement_ids=requirement_ids,
            target_id=target_id,
            validated_topologies=validated_topologies,
        )

        local_routes, validated_routes = first_party_data.validate_target_routes(
            local_operations=local_operations,
            dependencies=dependencies,
            fail=fail,
            first_party_data_routes=first_party_data_routes,
            mappings=mappings,
            requirement_by_id=requirement_by_id,
            requirement_ids=requirement_ids,
            target_id=target_id,
            validated_topologies=validated_topologies,
        )

        operations_by_key = first_party_data.validate_consumer_scope(
            local_operations=local_operations, fail=fail, validated_routes=validated_routes
        )

        inventory.validate_shared_variable_consumers(
            local_operations=local_operations,
            baseline_resources=baseline_resources,
            fail=fail,
            operations_by_key=operations_by_key,
            target_id=target_id,
        )

        first_party_data.validate_required_routes(
            fail=fail,
            local_routes=local_routes,
            mappings=mappings,
            target_id=target_id,
            target_requirement_ids=target_requirement_ids,
        )

        inventory.validate_target_inventory(
            local_operations=local_operations,
            baseline_in_scope_tags=baseline_in_scope_tags,
            execution_mode=execution_mode,
            fail=fail,
            inventory_dispositions=inventory_dispositions,
            target_id=target_id,
        )

    if not web_target_ids and any(
        (
            execution_topologies,
            page_view_decisions,
            first_party_data_routes,
            inventory_dispositions,
        )
    ):
        fail("server-only mode must not contain client-side decision sections")
