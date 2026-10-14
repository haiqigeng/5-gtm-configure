import json
import tempfile
from copy import deepcopy
from pathlib import Path

from gtm_configure.contract import ContractValidationError, validate_document  # noqa: E402
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
from support.contracts import approve_mutations  # noqa: E402
from support.enhanced_conversions import (
    ROOT,
    EnhancedConversionsTestsFixture,
    event_override_contract,
)
from support.schemas import schema_registry


class EnhancedConversionsTests(EnhancedConversionsTestsFixture):
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

    def test_saved_user_data_drift_cannot_report_configured(self):
        class UserDataDriftAdapter(FakeAdapter):
            def mutate(self, operation):
                result = super().mutate(operation)
                if operation["resource_family"] == "tag":
                    self.saved[operation["name"]]["parameter"][2]["list"][0]["map"][1]["value"] = (
                        "{{Wrong source}}"
                    )
                return result

        run = create_from_contract(
            event_override_contract(), run_id="ads-drift", source_locator="synthetic"
        )
        adapter = UserDataDriftAdapter()
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
                json.loads((ROOT / "schemas" / filename).read_text(encoding="utf-8")),
                registry=schema_registry(),
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
            ("user_data_path", ["notes"], "user_data_path"),
            ("user_data_path", ["parameter", "absent", "value"], "user_data_path"),
            ("user_data_path", ["parameter", "conversionLabel", "value"], "user_data_path"),
            ("activation_paths", [["parameter", "missingFlag", "value"]], "resolve uniquely"),
        ]:
            with self.subTest(field=field, value=value):
                contract = event_override_contract()
                contract["first_party_data_routes"][0]["consumer_bindings"][0][field] = value
                with self.assertRaisesRegex(ContractValidationError, message):
                    validate_document(contract)

    def test_wrong_event_field_and_duplicate_parameter_rejected(self):
        for duplicate in (False, True):
            contract = event_override_contract()
            parameters = contract["implementation"]["objects"][0]["intended"]["parameter"]
            if duplicate:
                parameters.append(deepcopy(parameters[2]))
                message = "resolve uniquely"
            else:
                parameters[2]["list"][0]["map"][0]["value"] = "unrelated_field"
                message = "native event field must be user_data"
            approve_mutations(contract)
            with self.assertRaisesRegex(ContractValidationError, message):
                validate_document(contract)

    def test_inspected_surface_without_boolean_control_does_not_invent_one(self):
        contract = event_override_contract()
        binding = contract["first_party_data_routes"][0]["consumer_bindings"][0]
        self.assertEqual(binding["activation_paths"], [])
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
        topology = deepcopy(contract["tag_policies"][0])
        topology["tag_object_key"] = extra["object_key"]
        contract["tag_policies"].append(topology)
        approve_mutations(contract)
        with self.assertRaisesRegex(ContractValidationError, "without an authorized first-party"):
            validate_document(contract)
