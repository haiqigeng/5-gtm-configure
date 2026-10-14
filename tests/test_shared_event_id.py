from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from pathlib import Path

from gtm_configure.contract import ContractValidationError, validate_document
from gtm_configure.domain.deduplication import validate_generated_event_ids  # noqa: E402
from gtm_configure.runtime.adapter_protocol import atomic_write
from gtm_configure.runtime.engine import (
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from gtm_configure.runtime.state import (
    create_from_contract,
    load_document,  # noqa: E402
)
from jsonschema import Draft202012Validator
from support.adapters import FakeAdapter, capabilities  # noqa: E402
from support.contracts import (  # noqa: E402
    approve_mutations,
)
from support.schemas import schema_registry
from support.shared_event_id import ROOT, SharedEventIdTestFixture, generated_contract


class SharedEventIdTest(SharedEventIdTestFixture):
    def test_generated_route_schemas_execution_readback_and_noop(self):
        contract = generated_contract()
        run = create_from_contract(contract, run_id="generated", source_locator="synthetic")
        for value, filename in (
            (contract, "configuration-contract.schema.json"),
            (run, "configuration-run.schema.json"),
        ):
            schema = json.loads((ROOT / "schemas" / filename).read_text(encoding="utf-8"))
            Draft202012Validator(schema, registry=schema_registry()).validate(value)
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
        self.assert_generation_rejected(
            contract,
            "consumer field does not use",
            contract_message="native identity field does not use",
        )

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
            contract["tag_policies"],
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
            contract["tag_policies"][-1]["trigger_roles"][0].update(change)
            self.assert_generation_rejected(contract, message)

    def test_purchase_stays_on_stable_order_identity(self):
        contract = generated_contract()
        contract["dedup_contracts"][0]["event_name"] = "Purchase"
        self.assert_generation_rejected(
            contract, "stable purchase/order", contract_message="detached from its event flow"
        )

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

    def test_installed_source_identity_owns_generator_type(self):
        contract = generated_contract()
        generation = contract["dedup_contracts"][0]["generation"]
        template = next(
            row
            for row in contract["implementation"]["objects"]
            if row["object_key"] == generation["template_object_key"]
        )
        template["intended"]["templateData"] = template["intended"]["templateData"].replace(
            "cvt_123_456", "cvt_999_456"
        )
        with self.assertRaisesRegex(ContractValidationError, "matching installed source"):
            validate_document(approve_mutations(contract))

    def test_generation_rejects_authored_native_type_copy(self):
        contract = generated_contract()
        contract["dedup_contracts"][0]["generation"]["template_type"] = "cvt_123_456"
        with self.assertRaisesRegex(ContractValidationError, "template_type.*unexpected"):
            validate_document(contract)

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
