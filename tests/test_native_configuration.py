"""Native parameter and consumer-closure regressions, using synthetic offline surfaces."""

import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]

from adapter_runtime import (  # noqa: E402
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from configuration_run import atomic_write, create_from_contract, load_document  # noqa: E402
from current_support import approve_mutations  # noqa: E402
from native_configuration import (  # noqa: E402
    FieldResolutionError,
    effective_fields,
    local_fields,
    referenced_variable_closure,
    sensitive_fields,
    variable_consumers,
)
from run_validation_web import (  # noqa: E402
    _configured_destinations,
    _effective_configuration_value,
)
from test_current_adapter_runtime import FakeAdapter, capabilities  # noqa: E402
from test_effective_configuration_guardrails import settings_contract  # noqa: E402
from test_google_ads_enhanced_conversions import event_override_contract  # noqa: E402
from test_utility_evolution import ads_transport_contract  # noqa: E402
from validate_configuration_contract import ContractValidationError, validate_document  # noqa: E402


def table(key, name="user_data", value="{{UPD - Approved conversion}}"):
    name_key, value_key = (
        ("name", "value") if key == "eventParameters" else ("parameter", "parameterValue")
    )
    return {
        "type": "list",
        "key": key,
        "list": [
            {
                "type": "map",
                "map": [
                    {"type": "template", "key": name_key, "value": name},
                    {"type": "template", "key": value_key, "value": value},
                ],
            }
        ],
    }


def shared_contract(*, authorized):
    contract = event_override_contract()
    objects = contract["implementation"]["objects"]
    settings = deepcopy(objects[3])
    settings.update(
        name="Shared event settings",
        object_key="web-main::variable::Shared event settings",
        risk="high-impact",
    )
    settings["intended"] = {"type": "gtes", "parameter": [table("eventSettingsTable")]}
    settings["depends_on"] = [objects[3]["object_key"]]
    objects.append(settings)
    tag = objects[0] if authorized else deepcopy(objects[0])
    if not authorized:
        tag.update(name="Unapproved Google tag", object_key="web-main::tag::Unapproved Google tag")
        objects.append(tag)
        topology = deepcopy(contract["execution_topologies"][0])
        topology["tag_object_key"] = tag["object_key"]
        contract["execution_topologies"].append(topology)
    tag["intended"]["type"] = "googtag"
    tag["intended"]["parameter"] = [
        {"type": "template", "key": "tagId", "value": "AW-123456789"},
        {"type": "template", "key": "eventSettingsVariable", "value": "{{Shared event settings}}"},
    ]
    tag["depends_on"].append(settings["object_key"])
    if authorized:
        route = contract["first_party_data_routes"][0]
        route.update(feature="google-ads-tag-wide-user-data", timing="tag-wide")
        binding = route["consumer_bindings"][0]
        binding["tag_type"] = "googtag"
        for field in ("user_data_path", "activation_paths", "field_review"):
            binding.pop(field)
    return approve_mutations(contract)


class NativeConfigurationTests(unittest.TestCase):
    def test_saved_native_ga4_destination_is_not_the_gtm_resource_id(self):
        target = {
            "type": "gaawe",
            "tagId": "321",
            "parameter": [
                {"type": "template", "key": "measurementIdOverride", "value": "G-TEST123"},
                table("eventParameters"),
            ],
        }
        self.assertEqual(_configured_destinations(target, {}, "$.tag"), {"G-TEST123"})

    def test_all_native_tables_preserve_values_and_do_not_mutate_payload(self):
        for name in ("configSettingsTable", "eventSettingsTable", "eventParameters"):
            target = {"parameter": [table(name)]}
            before = deepcopy(target)
            self.assertEqual(local_fields(target)["userdata"], "{{UPD - Approved conversion}}")
            self.assertEqual(target, before)
        payload = {"value": "keep", "user_id": "{{Approved ID}}"}
        self.assertEqual(local_fields({"payload": payload})["payload"], payload)
        self.assertEqual(sensitive_fields(local_fields({"payload": payload})), {"userid"})

    def test_inheritance_and_explicit_empty_override(self):
        settings = {"Shared": {"type": "gtes", "parameter": [table("eventSettingsTable")]}}
        for key in ("eventSettingsVariable", "inheritedEventSettings"):
            target = {"type": "gaawe", key: "{{Shared}}"}
            self.assertIn("userdata", effective_fields(target, settings))
            target["parameter"] = [table("eventParameters", value="")]
            fields = effective_fields(target, settings)
            self.assertEqual(fields["userdata"], "")
            self.assertEqual(referenced_variable_closure(fields, settings), set())
            self.assertEqual(sensitive_fields(fields), set())

    def test_config_fields_do_not_inherit_event_settings(self):
        operations = {
            "config": {
                "name": "Config",
                "object_type": "variable",
                "action": "create",
                "intended": {
                    "type": "gtcs",
                    "object_type": "variable",
                    "variableId": "101",
                    "user_id": "{{ID}}",
                },
            },
            "event": {
                "name": "Event",
                "object_type": "variable",
                "action": "create",
                "intended": {
                    "type": "gtes",
                    "object_type": "variable",
                    "variableId": "102",
                    "user_id": "{{Wrong ID}}",
                },
            },
        }
        target = {"configSettingsVariable": "{{Config}}", "eventSettingsVariable": "{{Event}}"}
        self.assertEqual(
            _effective_configuration_value(target, {"user_id"}, operations, "$.tag"),
            (True, "{{ID}}"),
        )

    def test_unresolved_wrong_type_and_cyclic_settings_reject(self):
        for variables in (
            {},
            {"Shared": {"type": "c", "value": "unknown"}},
            {"Shared": {"type": "gtes", "eventSettingsVariable": "{{Shared}}"}},
        ):
            with self.assertRaises(FieldResolutionError):
                effective_fields({"eventSettingsVariable": "{{Shared}}"}, variables)

    def test_duplicate_table_rows_map_keys_and_field_aliases_reject(self):
        duplicate_row = table("eventParameters")
        duplicate_row["list"] *= 2
        duplicate_map = table("eventParameters")
        duplicate_map["list"][0]["map"].append(deepcopy(duplicate_map["list"][0]["map"][0]))
        for target in (
            {"parameter": [duplicate_row]},
            {"parameter": [duplicate_map]},
            {"user_data": "a", "userDataVariable": "b"},
        ):
            with self.assertRaises(FieldResolutionError):
                local_fields(target)

    def test_nested_references_and_cycles_are_not_lost_in_name_fields(self):
        variables = {
            "Helper": {"type": "jsm", "payload": {"name": "{{UPD}}"}},
            "UPD": {"type": "awec"},
        }
        self.assertEqual(referenced_variable_closure("{{Helper}}", variables), {"Helper", "UPD"})
        variables["UPD"]["value"] = "{{Helper}}"
        with self.assertRaisesRegex(FieldResolutionError, "cyclic"):
            referenced_variable_closure("{{Helper}}", variables)

    def test_consumers_follow_transitive_references_and_both_rename_names(self):
        operation = {"name": "Old", "new_name": "New"}
        variables = [{"name": "Helper", "type": "jsm", "payload": {"name": "{{Old}}"}}]
        tags = [
            {"name": "Indirect", "type": "html", "html": "{{Helper}}"},
            {"name": "Renamed", "type": "googtag", "configSettingsVariable": "New"},
            {"name": "Notes only", "notes": "{{Old}}"},
        ]
        self.assertEqual(variable_consumers(operation, tags, variables), {"Indirect", "Renamed"})


class NativeScopeExecutionTests(unittest.TestCase):
    def execute(self, contract, adapter_factory=FakeAdapter):
        run = create_from_contract(contract, run_id="NATIVE-FIELDS", source_locator="synthetic")
        registry, adapters = TargetAdapterRegistry(), []
        for target in run["run"]["targets"]:
            adapter = adapter_factory()
            adapter.existing.update(
                item["name"]
                for item in run["object_changes"]
                if item["target_id"] == target["target_id"]
                and item["action"] in {"reuse", "untouched"}
            )
            adapter.bind_target(target)
            registry.register(
                target,
                adapter,
                capabilities("tag", "trigger", "variable", "client", "transformation"),
            )
            adapters.append(adapter)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry)
            result = load_document(path)
            if all(item["state"] == "verified" for item in result["object_changes"]):
                writes = sum(len(adapter.mutations) for adapter in adapters)
                verify_idempotent_rerun(path, registry)
                result = load_document(path)
                self.assertEqual(sum(len(adapter.mutations) for adapter in adapters), writes)
        return result, adapters

    def test_unapproved_inherited_consumer_is_rejected_with_current_approval(self):
        with self.assertRaisesRegex(ContractValidationError, "without an authorized first-party"):
            validate_document(shared_contract(authorized=False))

    def test_unapproved_indirect_helper_consumer_is_rejected(self):
        contract = shared_contract(authorized=False)
        helper = contract["implementation"]["objects"][-2]
        helper["intended"] = {
            "type": "jsm",
            "javascript": "function(){return {{UPD - Approved conversion}};}",
        }
        contract["implementation"]["objects"][-1]["intended"]["parameter"][-1] = {
            "type": "template",
            "key": "unknownNativeField",
            "value": "{{Shared event settings}}",
        }
        with self.assertRaisesRegex(ContractValidationError, "without an authorized first-party"):
            validate_document(approve_mutations(contract))

    def test_authorized_inherited_settings_save_readback_and_converge(self):
        result, _ = self.execute(shared_contract(authorized=True))
        self.assertEqual(result["run"]["status"], "Configured")

    def test_one_authorized_source_cannot_authorize_another_consumers_upd(self):
        contract = event_override_contract()
        objects = contract["implementation"]["objects"]
        requirement = deepcopy(contract["requirements"][0])
        requirement["id"] = "REQ-SECOND"
        contract["requirements"].append(requirement)
        contract["scope"]["included"].append("REQ-SECOND")
        for evidence in contract["evidence"]:
            if "supports" in evidence:
                evidence["supports"].append("REQ-SECOND")
        for item in objects:
            if item["resource_family"] != "tag":
                item["requirement_ids"].append("REQ-SECOND")
        for item in contract["external_dependencies"] + contract["consent_topologies"]:
            item["requirement_ids"].append("REQ-SECOND")
        variable = deepcopy(objects[3])
        variable.update(
            name="Second UPD",
            object_key="web-main::variable::Second UPD",
            requirement_ids=["REQ-SECOND"],
        )
        objects.append(variable)
        tag = deepcopy(objects[0])
        tag.update(
            name="Second conversion",
            object_key="web-main::tag::Second conversion",
            requirement_ids=["REQ-SECOND"],
        )
        tag["intended"]["parameter"][2]["value"] = "{{Second UPD}}"
        tag["depends_on"].append(variable["object_key"])
        objects.append(tag)
        topology = deepcopy(contract["execution_topologies"][0])
        topology.update(tag_object_key=tag["object_key"], requirement_ids=["REQ-SECOND"])
        contract["execution_topologies"].append(topology)
        mapping = deepcopy(contract["implementation"]["field_bindings"][0])
        mapping.update(requirement_id="REQ-SECOND", gtm_resolution="{{Second UPD}}")
        contract["implementation"]["field_bindings"].append(mapping)
        route = deepcopy(contract["first_party_data_routes"][0])
        route.update(requirement_id="REQ-SECOND", consumer_object_keys=[tag["object_key"]])
        route["consumer_bindings"][0]["object_key"] = tag["object_key"]
        contract["first_party_data_routes"].append(route)
        validate_document(approve_mutations(contract))
        objects[0]["intended"]["parameter"].append(
            {"type": "template", "key": "unexpectedNativeField", "value": "{{Second UPD}}"}
        )
        objects[0]["depends_on"].append(variable["object_key"])
        with self.assertRaisesRegex(ContractValidationError, "without an authorized first-party"):
            validate_document(approve_mutations(contract))

    def test_empty_local_override_does_not_expand_first_party_scope(self):
        contract = shared_contract(authorized=False)
        contract["implementation"]["objects"][-1]["intended"]["parameter"].append(
            table("eventSettingsTable", value="")
        )
        result, _ = self.execute(approve_mutations(contract))
        self.assertEqual(result["run"]["status"], "Configured")

    def test_native_ga4_event_carrier_save_readback_and_converge(self):
        contract = ads_transport_contract()
        key = contract["first_party_data_routes"][0]["consumer_object_keys"][0]
        sender = next(
            item for item in contract["implementation"]["objects"] if item["object_key"] == key
        )
        value = sender["intended"].pop("user_data")
        sender["intended"].setdefault("parameter", []).append(
            table("eventSettingsTable", value=value)
        )
        for key, native_key in (
            ("measurement_id", "measurementIdOverride"),
            ("event_name", "eventName"),
        ):
            sender["intended"]["parameter"].append(
                {"type": "template", "key": native_key, "value": sender["intended"].pop(key)}
            )
        result, _ = self.execute(approve_mutations(contract))
        self.assertEqual(result["run"]["status"], "Configured")

    def test_existing_and_late_indirect_consumers_prevent_mutation(self):
        for late in (False, True):

            class ConsumerAdapter(FakeAdapter):
                def __init__(self):
                    super().__init__(existing={"Google Settings"})
                    self.tag_lists = 0

                def list_resource_page(self, family, cursor):
                    if family == "tag":
                        self.tag_lists += 1
                        items = (
                            []
                            if late and self.tag_lists == 1
                            else [
                                {
                                    "name": "Unreviewed",
                                    "type": "googtag",
                                    "eventSettingsVariable": "{{Indirect settings}}",
                                }
                            ]
                        )
                    elif family == "variable":
                        items = [
                            {
                                "name": "Indirect settings",
                                "type": "gtes",
                                "parameter": [
                                    table(
                                        "eventSettingsTable",
                                        name="campaign_source",
                                        value="{{Google Settings}}",
                                    )
                                ],
                            }
                        ]
                    else:
                        items = []
                    return {"items": items, "next_cursor": None}

            contract = settings_contract()
            # Existing ordinary variable mutations also affect indirect consumers.
            for field in ("pre_change", "intended"):
                contract["implementation"]["objects"][0][field] = {
                    "type": "c",
                    "value": "old" if field == "pre_change" else "new",
                }
            result, adapters = self.execute(approve_mutations(contract), ConsumerAdapter)
            self.assertEqual(adapters[0].mutations, [])
            self.assertEqual(result["object_changes"][0]["state"], "failed")
            expected = (
                "unreviewed current consumers" if late else "every authenticated baseline consumer"
            )
            self.assertIn(expected, str(result["object_changes"][0]["journal"]))


if __name__ == "__main__":
    unittest.main()
