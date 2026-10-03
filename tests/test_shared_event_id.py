from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from adapter_runtime import (  # noqa: E402
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from configuration_run import atomic_write, create_from_contract, load_document  # noqa: E402
from current_support import (  # noqa: E402
    add_nonpurchase_dual_dedup,
    approve_mutations,
    valid_pipeline_contract,
)
from shared_event_id import validate_generated_event_ids  # noqa: E402
from test_current_adapter_runtime import FakeAdapter, capabilities  # noqa: E402
from validate_configuration_contract import (  # noqa: E402
    ContractValidationError,
    validate_document,
)


def generated_contract():
    """Synthetic reviewed template premise, not a real GTM template export."""
    contract = add_nonpurchase_dual_dedup(valid_pipeline_contract())
    dedup = contract["dedup_contracts"][0]
    template_key = "web-main::template::Reviewed occurrence ID"
    template = {
        "target_id": "web-main",
        "resource_family": "template",
        "name": "Reviewed occurrence ID",
        "object_key": template_key,
        "object_id": "456",
        "action": "reuse",
        "requirement_ids": ["REQ-ATC"],
        "depends_on": [],
        "justification": "Reuse the inspected occurrence-scoped generator",
        "evidence": ["container-confirmed"],
        "risk": "routine",
        "intended": {"templateData": "Synthetic inspected template source"},
    }
    contract["implementation"]["objects"].append(template)
    variable = next(
        item
        for item in contract["implementation"]["objects"]
        if item["object_key"] == dedup["source_variable_key"]
    )
    variable["intended"] = {"type": "cvt_123_456"}
    variable["depends_on"] = [template_key]
    dedup["source_type"] = "generated-event-id"
    dedup["generation"] = {
        "template_object_key": template_key,
        "template_type": "cvt_123_456",
        "review_locator": "Synthetic source and permission review; same-event repeated reads stable",
        "consumer_bindings": [
            {"object_key": key, "field_path": ["event_id"]}
            for key in dedup["browser_consumer_keys"] + dedup["transporter_consumer_keys"]
        ],
    }
    return approve_mutations(contract)


class SharedEventIdTest(unittest.TestCase):
    def assert_generation_rejected(self, contract, message):
        with self.assertRaisesRegex(ContractValidationError, message):
            validate_document(approve_mutations(contract))
        # Run-phase checks must reject the same native graph before any mutation.
        errors = []
        validate_generated_event_ids(
            contract["dedup_contracts"],
            contract["implementation"]["objects"],
            contract["execution_topologies"],
            {item["target_id"]: item["container_type"] for item in contract["targets"]},
            errors.append,
        )
        self.assertTrue(any(message in error for error in errors), errors)

    def test_generated_route_schemas_execution_readback_and_noop(self):
        contract = generated_contract()
        run = create_from_contract(contract, run_id="generated", source_locator="synthetic")
        for value, filename in (
            (contract, "configuration-contract.schema.json"),
            (run, "configuration-run.schema.json"),
        ):
            schema = json.loads((ROOT / "schemas" / filename).read_text(encoding="utf-8"))
            Draft202012Validator(schema).validate(value)
        registry = TargetAdapterRegistry()
        adapters = []
        for target in run["run"]["targets"]:
            adapter = FakeAdapter(
                existing={
                    item["name"]
                    for item in run["object_changes"]
                    if item["target_id"] == target["target_id"] and item["action"] != "create"
                }
            )
            adapter.bind_target(target)
            registry.register(
                target, adapter, capabilities("tag", "trigger", "variable", "client", "template")
            )
            adapters.append(adapter)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry)
            writes = sum(len(adapter.mutations) for adapter in adapters)
            verify_idempotent_rerun(path, registry)
            result = load_document(path)
            self.assertEqual(result["run"]["status"], "Configured")
            self.assertEqual(writes, sum(len(adapter.mutations) for adapter in adapters))
            self.assertEqual(result["dedup_contracts"], contract["dedup_contracts"])

    def test_different_native_id_field_even_with_reference_elsewhere_is_rejected(self):
        contract = generated_contract()
        dedup = contract["dedup_contracts"][0]
        key = dedup["browser_consumer_keys"][0]
        tag = next(i for i in contract["implementation"]["objects"] if i["object_key"] == key)
        tag["intended"]["notes"] = dedup["source_reference"]
        tag["intended"]["event_id"] = "independent-id"
        self.assert_generation_rejected(contract, "consumer field does not use")

    def test_sequencing_on_either_consumer_is_rejected(self):
        for role in ("browser_consumer_keys", "transporter_consumer_keys"):
            for field in ("setupTag", "teardownTag"):
                with self.subTest(role=role, field=field):
                    contract = generated_contract()
                    key = contract["dedup_contracts"][0][role][0]
                    tag = next(
                        i for i in contract["implementation"]["objects"] if i["object_key"] == key
                    )
                    tag["intended"][field] = [{"tagName": "Other tag"}]
                    self.assert_generation_rejected(contract, "does not support tag sequencing")

    def test_consumer_as_sequenced_child_is_rejected(self):
        contract = generated_contract()
        contract["implementation"]["objects"][0]["intended"]["setupTag"] = [
            {"tagName": "Meta - add_to_cart"}
        ]
        self.assert_generation_rejected(contract, "consumer is sequenced")

    def test_inbound_sequence_in_existing_inventory_is_rejected(self):
        contract = generated_contract()
        errors = []
        baselines = [
            {
                "target_id": "web-main",
                "resources": {
                    "tag": [
                        {"name": "Meta - add_to_cart", "tagId": "71"},
                        {"name": "Unchanged tag", "setupTag": [{"tagName": "71"}]},
                    ]
                },
            }
        ]
        validate_generated_event_ids(
            contract["dedup_contracts"],
            contract["implementation"]["objects"],
            contract["execution_topologies"],
            {"web-main": "web", "server-main": "server"},
            errors.append,
            baselines,
        )
        self.assertTrue(any("consumer is sequenced" in error for error in errors), errors)

    def test_consent_replay_or_different_source_event_is_rejected(self):
        for change, message in (
            ({"role": "cmp-readiness-grant"}, "direct source-event"),
            ({"trigger_object_key": "web-main::trigger::Different event"}, "exact source-event"),
        ):
            contract = generated_contract()
            contract["execution_topologies"][-1]["normal_triggers"][0].update(change)
            self.assert_generation_rejected(contract, message)

    def test_purchase_stays_on_stable_order_identity(self):
        contract = generated_contract()
        contract["dedup_contracts"][0]["event_name"] = "Purchase"
        self.assert_generation_rejected(contract, "stable purchase/order")

    def test_template_type_code_and_dependency_are_bound(self):
        for change, message in (
            ("type", "reviewed web variable template type"),
            ("code", "readback-verifiable installed template"),
            ("dependency", "depend on its inspected template"),
        ):
            contract = generated_contract()
            dedup = contract["dedup_contracts"][0]
            by_key = {i["object_key"]: i for i in contract["implementation"]["objects"]}
            if change == "type":
                by_key[dedup["source_variable_key"]]["intended"]["type"] = "jsm"
            elif change == "code":
                by_key[dedup["generation"]["template_object_key"]]["intended"] = {
                    "name": "Reviewed occurrence ID"
                }
            else:
                by_key[dedup["source_variable_key"]]["depends_on"] = []
            self.assert_generation_rejected(contract, message)

    def test_native_keyed_parameter_binding_and_duplicate_rejection(self):
        contract = generated_contract()
        dedup = contract["dedup_contracts"][0]
        binding = dedup["generation"]["consumer_bindings"][0]
        tag = next(
            i
            for i in contract["implementation"]["objects"]
            if i["object_key"] == binding["object_key"]
        )
        binding["field_path"] = ["parameter", "eventId", "value"]
        tag["intended"].pop("event_id")
        tag["intended"]["parameter"] = [
            {"type": "template", "key": "eventId", "value": dedup["source_reference"]}
        ]
        validate_document(approve_mutations(contract))
        tag["intended"]["parameter"].append(deepcopy(tag["intended"]["parameter"][0]))
        self.assert_generation_rejected(contract, "does not resolve uniquely")


if __name__ == "__main__":
    unittest.main()
