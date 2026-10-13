"""One phase-neutral graph for domain validation.

Contract keys and durable run IDs enter through separate constructors. Domain
validators consume operation IDs, dependency edges and target identities only.
Native GTM bodies and authority records retain their original representation.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConfigurationGraph:
    mode: str
    target_types: dict[str, str]
    requirements: list[dict[str, Any]]
    operations: list[dict[str, Any]]
    pipelines: list[dict[str, Any]]
    inventory_dispositions: list[dict[str, Any]]
    payload_mappings: list[dict[str, Any]]
    consent_topologies: list[dict[str, Any]]
    dedup_contracts: list[dict[str, Any]]
    external_dependencies: list[dict[str, Any]]
    execution_topologies: list[dict[str, Any]]
    container_baselines: list[dict[str, Any]]
    by_id: dict[str, dict[str, Any]] = field(init=False)
    by_key: dict[str, dict[str, Any]] = field(init=False)

    def __post_init__(self):
        self.by_id = {item["operation_id"]: item for item in self.operations}
        self.by_key = {item["object_key"]: item for item in self.operations}

    @classmethod
    def from_contract(cls, contract, payload_mappings):
        operations = [
            {**item, "operation_id": item["object_key"], "dependencies": item["depends_on"]}
            for item in contract["implementation"]["objects"]
        ]
        pipelines = [
            {
                **item,
                "claiming_client_operation_id": item["claiming_client"]["object_key"],
                "cutover_operation_id": item.get("cutover_operation_key"),
                "event_flows": [
                    {**flow, "server_consumer_operation_ids": flow["server_consumer_keys"]}
                    for flow in item["event_flows"]
                ],
            }
            for item in contract["pipelines"]
        ]
        inventory = [
            {
                **{k: v for k, v in item.items() if k != "operation_keys"},
                "operation_ids": item["operation_keys"],
            }
            for item in contract["inventory_dispositions"]
        ]
        return cls(
            contract["mode"],
            {t["target_id"]: t["container_type"] for t in contract["targets"]},
            [
                {**item, "kind": item.get("kind", contract["route"])}
                for item in contract["requirements"]
            ],
            operations,
            pipelines,
            inventory,
            payload_mappings,
            contract["consent_topologies"],
            contract["dedup_contracts"],
            contract["external_dependencies"],
            contract["execution_topologies"],
            [],
        )

    @classmethod
    def from_run(cls, document):
        return cls(
            document["run"]["mode"],
            {t["target_id"]: t["container_type"] for t in document["run"]["targets"]},
            document["requirements"],
            document["object_changes"],
            document["pipelines"],
            document["inventory_dispositions"],
            document["payload_mappings"],
            document["consent_topologies"],
            document["dedup_contracts"],
            document["external_dependencies"],
            document["execution_topologies"],
            document["container_baselines"],
        )
