"""Exercise native-field contracts with synthetic data, not a live Google UI certification."""

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
from current_support import approve_mutations, valid_web_contract  # noqa: E402
from test_current_adapter_runtime import FakeAdapter, capabilities  # noqa: E402
from validate_configuration_contract import ContractValidationError, validate_document  # noqa: E402


def event_override_contract() -> dict:
    """Inspected fields are a test premise; real runs must inspect their actual native surface."""
    contract = valid_web_contract()
    contract["route"] = "media"
    contract["page_view_decisions"] = []
    requirement = contract["requirements"][0]
    requirement.update(
        kind="media", destination="Google Ads", event_name="purchase", source_event="purchase"
    )
    requirement["parameters"] = {
        "user_data": {
            "source": "customer",
            "source_shape": "object",
            "destination_shape": "object",
            "provenance": {
                "grade": "approved-input",
                "locator": "Synthetic authorized Ads identity",
            },
        }
    }
    contract["implementation"]["field_bindings"] = [
        {
            "requirement_id": "REQ-PAGE",
            "field_scope": "event-parameter",
            "destination_field": "user_data",
            "status": "mapped",
            "shape_compatibility": "compatible",
            "mapping_method": "native-template",
            "gtm_resolution": "{{UPD - Approved conversion}}",
            "template_field": "userDataVariable",
            "missing_behavior": "Omit missing identifiers",
        }
    ]
    objects = contract["implementation"]["objects"]
    tag, trigger, block = objects
    variable_key = "web-main::variable::UPD - Approved conversion"
    email_key = "web-main::variable::DLV - Approved email"
    tag["intended"] = {
        "type": "awct",
        "parameter": [
            {"type": "template", "key": "conversionId", "value": "123456789"},
            {"type": "template", "key": "conversionLabel", "value": "synthetic-label"},
            {
                "type": "template",
                "key": "userDataVariable",
                "value": "{{UPD - Approved conversion}}",
            },
            {"type": "boolean", "key": "enableEnhancedConversions", "value": "true"},
        ],
        "firingTriggerId": [trigger["object_key"]],
        "blockingTriggerId": [block["object_key"]],
        "tagFiringOption": "oncePerEvent",
    }
    tag["depends_on"].append(variable_key)
    trigger["intended"]["customEventFilter"] = [
        {
            "type": "equals",
            "parameter": [
                {"type": "template", "key": "arg0", "value": "{{_event}}"},
                {"type": "template", "key": "arg1", "value": "purchase"},
            ],
        }
    ]
    block["intended"] = {
        "type": "customEvent",
        "customEventFilter": [
            {
                "type": "matchRegex",
                "parameter": [
                    {"type": "template", "key": "arg0", "value": "{{_event}}"},
                    {"type": "template", "key": "arg1", "value": ".*"},
                ],
            }
        ],
        "filter": [
            {
                "type": "equals",
                "parameter": [
                    {"type": "template", "key": "arg0", "value": "{{CMP - Ads blocked}}"},
                    {"type": "template", "key": "arg1", "value": "true"},
                ],
            }
        ],
    }
    for name, key, intended, dependencies in [
        (
            "UPD - Approved conversion",
            variable_key,
            {
                "type": "awec",
                "parameter": [
                    {"type": "template", "key": "mode", "value": "MANUAL"},
                    {"type": "template", "key": "email", "value": "{{DLV - Approved email}}"},
                ],
            },
            [email_key],
        ),
        (
            "DLV - Approved email",
            email_key,
            {
                "type": "v",
                "parameter": [
                    {"type": "template", "key": "name", "value": "customer.email"},
                    {"type": "integer", "key": "dataLayerVersion", "value": "2"},
                ],
            },
            [],
        ),
        (
            "CMP - Ads blocked",
            "web-main::variable::CMP - Ads blocked",
            {
                "type": "v",
                "parameter": [
                    {"type": "template", "key": "name", "value": "cmp.ads_blocked"},
                    {"type": "integer", "key": "dataLayerVersion", "value": "2"},
                ],
            },
            [],
        ),
    ]:
        objects.append(
            {
                "target_id": "web-main",
                "resource_family": "variable",
                "name": name,
                "object_key": key,
                "action": "create",
                "requirement_ids": ["REQ-PAGE"],
                "depends_on": dependencies,
                "justification": "Synthetic approved source; CMP field true for unknown or denied",
                "evidence": ["approved-input", "container-confirmed"],
                "risk": "routine",
                "intended": intended,
            }
        )
    block["depends_on"] = [objects[-1]["object_key"]]
    topology = contract["execution_topologies"][0]
    topology.update(
        lifecycle_role="event-driven",
        page_view_capable=False,
        page_view_destinations=[],
        page_view_occurrences=[],
        built_in_consent_checks=["ad_storage", "ad_user_data", "ad_personalization"],
    )
    topology["normal_triggers"][0]["role"] = "source-event"
    consent = contract["consent_topologies"][0]
    consent.update(
        destination="Google Ads",
        event_coverage=["purchase"],
        signal_source="cmp.ads_blocked: true for unknown/denied, false only for explicit Ads grant",
    )
    contract["external_dependencies"] = [
        {
            "id": "EXT-ADS",
            "requirement_ids": ["REQ-PAGE"],
            "owner": "Ads owner",
            "action": "Verify unified EC activation, terms, Google tag destination/capability and live delivery",
            "status": "open",
        }
    ]
    contract["first_party_data_routes"] = [
        {
            "requirement_id": "REQ-PAGE",
            "feature": "google-ads-enhanced-conversions",
            "destination_field": "user_data",
            "consumer_object_keys": [tag["object_key"]],
            "consumer_bindings": [
                {
                    "object_key": tag["object_key"],
                    "product": "google-ads",
                    "implementation": "native",
                    "tag_type": "awct",
                    "template_identity": None,
                    "evidence": ["Synthetic native-surface premise; no live GTM claim"],
                    "user_data_path": ["parameter", "userDataVariable", "value"],
                    "activation_paths": [["parameter", "enableEnhancedConversions", "value"]],
                    "field_review": "Synthetic native field review for event-level override and required control",
                }
            ],
            "source_priority": "data-layer",
            "timing": "same-event",
            "hashing_owner": "native-raw",
            "fields": [
                {
                    "name": "email",
                    "source": "customer.email",
                    "normalization": ["native"],
                    "empty_behavior": "omit",
                }
            ],
            "consent_types": ["ad_user_data"],
            "external_dependency_ids": ["EXT-ADS"],
            "evidence": ["Synthetic event-only authority; data available on purchase"],
        }
    ]
    source = next(item for item in contract["evidence"] if item["grade"] == "official-current")
    source.update(
        locator="https://support.google.com/google-ads/answer/13262500?hl=en",
        title="Enhanced conversions with GTM",
        accessed_on="2026-09-28",
        decision="Documented event override, reconciled with inspected native fields",
    )
    return approve_mutations(contract)


class EnhancedConversionsTests(unittest.TestCase):
    def test_authorized_removal_does_not_need_a_user_data_consumer(self):
        contract = event_override_contract()
        removed = deepcopy(contract["implementation"]["objects"][3])
        removed.update(
            name="Unused UPD",
            object_key="web-main::variable::Unused UPD",
            action="remove",
            object_id="synthetic-old-variable",
            depends_on=[],
            risk="high-impact",
        )
        removed["pre_change"] = removed.pop("intended")
        contract["implementation"]["objects"].append(removed)
        validate_document(approve_mutations(contract))

    def test_saved_disabled_control_cannot_report_configured(self):
        class DisabledControlAdapter(FakeAdapter):
            def mutate(self, operation):
                result = super().mutate(operation)
                if operation["resource_family"] == "tag":
                    self.saved[operation["name"]]["parameter"][-1]["value"] = "false"
                return result

        run = create_from_contract(
            event_override_contract(), run_id="ads-drift", source_locator="synthetic"
        )
        adapter = DisabledControlAdapter()
        adapter.bind_target(run["run"]["targets"][0])
        registry = TargetAdapterRegistry()
        registry.register(
            run["run"]["targets"][0], adapter, capabilities("tag", "trigger", "variable")
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry)
            result = load_document(path)
            self.assertNotEqual(result["run"]["status"], "Configured")
            tag = next(
                item for item in result["object_changes"] if item["resource_family"] == "tag"
            )
            self.assertNotEqual(tag["state"], "verified")

    def test_event_override_executes_readback_and_rerun_without_additional_writes(self):
        contract = event_override_contract()
        run = create_from_contract(contract, run_id="ads-event", source_locator="synthetic")
        for value, filename in [
            (contract, "configuration-contract.schema.json"),
            (run, "configuration-run.schema.json"),
        ]:
            Draft202012Validator(
                json.loads((ROOT / "schemas" / filename).read_text(encoding="utf-8"))
            ).validate(value)
        adapter = FakeAdapter()
        adapter.bind_target(run["run"]["targets"][0])
        registry = TargetAdapterRegistry()
        registry.register(
            run["run"]["targets"][0], adapter, capabilities("tag", "trigger", "variable")
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry)
            writes = len(adapter.mutations)
            self.assertGreater(writes, 0)
            verify_idempotent_rerun(path, registry)
            result = load_document(path)
            self.assertEqual(result["run"]["status"], "Configured")
            self.assertEqual(writes, len(adapter.mutations))
            self.assertEqual(result["first_party_data_routes"], contract["first_party_data_routes"])

    def test_missing_native_inspection_or_wrong_paths_rejected(self):
        for field, value, message in [
            ("field_review", "", "field_review"),
            ("user_data_path", ["notes"], "inspected native parameter"),
            ("user_data_path", ["parameter", "absent", "value"], "resolve uniquely"),
            ("user_data_path", ["parameter", "conversionLabel", "value"], "binding differs"),
            ("activation_paths", [["parameter", "missingFlag", "value"]], "resolve uniquely"),
        ]:
            with self.subTest(field=field, value=value):
                contract = event_override_contract()
                contract["first_party_data_routes"][0]["consumer_bindings"][0][field] = value
                with self.assertRaisesRegex(ContractValidationError, message):
                    validate_document(contract)

    def test_disabled_required_control_and_duplicate_parameter_rejected(self):
        for duplicate in (False, True):
            contract = event_override_contract()
            parameters = contract["implementation"]["objects"][0]["intended"]["parameter"]
            if duplicate:
                parameters.append(deepcopy(parameters[2]))
                message = "resolve uniquely"
            else:
                parameters[-1]["value"] = "false"
                message = "control is not enabled"
            approve_mutations(contract)
            with self.assertRaisesRegex(ContractValidationError, message):
                validate_document(contract)

    def test_inspected_surface_without_boolean_control_does_not_invent_one(self):
        contract = event_override_contract()
        contract["implementation"]["objects"][0]["intended"]["parameter"].pop()
        binding = contract["first_party_data_routes"][0]["consumer_bindings"][0]
        binding.update(
            activation_paths=[],
            field_review="Synthetic inspected native event field without a separate boolean control",
        )
        validate_document(approve_mutations(contract))

    def test_wrong_product_scope_source_or_consent_rejected(self):
        for alteration, message in [
            ("google-tag", "destination identities"),
            ("ga4-event", "native Ads"),
            ("custom-source", "native User-Provided Data"),
            ("consent", "ad_user_data"),
            ("activation-dependency", "external administration"),
            ("timing", "same-event"),
        ]:
            with self.subTest(alteration=alteration):
                contract = event_override_contract()
                route = contract["first_party_data_routes"][0]
                if alteration in {"google-tag", "ga4-event"}:
                    tag_type = "googtag" if alteration == "google-tag" else "gaawe"
                    contract["implementation"]["objects"][0]["intended"]["type"] = tag_type
                    if alteration == "ga4-event":
                        contract["implementation"]["objects"][0]["intended"].update(
                            event_name="purchase", measurement_id="G-TEST123"
                        )
                    route["consumer_bindings"][0]["tag_type"] = tag_type
                elif alteration == "custom-source":
                    contract["implementation"]["objects"][3]["intended"]["type"] = "jsm"
                elif alteration == "consent":
                    route["consent_types"] = []
                elif alteration == "activation-dependency":
                    route["external_dependency_ids"] = []
                else:
                    route["timing"] = "tag-wide"
                approve_mutations(contract)
                with self.assertRaisesRegex(ContractValidationError, message):
                    validate_document(contract)

    def test_unrelated_tag_cannot_receive_upd_through_an_unrecognized_native_key(self):
        contract = event_override_contract()
        extra = deepcopy(contract["implementation"]["objects"][0])
        extra.update(name="Unrelated conversion", object_key="web-main::tag::Unrelated conversion")
        extra["intended"]["parameter"][2]["key"] = "anotherNativeField"
        contract["implementation"]["objects"].append(extra)
        topology = deepcopy(contract["execution_topologies"][0])
        topology["tag_object_key"] = extra["object_key"]
        contract["execution_topologies"].append(topology)
        approve_mutations(contract)
        with self.assertRaisesRegex(ContractValidationError, "without an authorized first-party"):
            validate_document(contract)


if __name__ == "__main__":
    unittest.main()
