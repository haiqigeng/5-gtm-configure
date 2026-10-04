"""Static regressions for built-in triggers and associated Google-tag defaults."""
# ruff: noqa: E402

import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests"), str(ROOT / "tests/fixtures")]
from compile_configuration_request import _derive_exact_declarations, compile_request
from configuration_run import create_from_contract
from current_support import approve_mutations, valid_pipeline_contract
from mcp_behavior_scenario import param
from run_model_web import BUILT_IN_TRIGGER_TYPES
from run_validation_web import (
    _associated_google_tag,
    _resolved_event_parameter,
    _resolved_trigger_types,
    _validate_normal_trigger_bindings,
)
from test_mapping_startup_corrections import lead_request
from web_domain_validation import validate_native_mappings


def inherited_mapping():
    contract = compile_request(lead_request())
    operations = contract["implementation"]["objects"]
    event = next(item for item in operations if item["resource_family"] == "tag")
    table = event["intended"]["parameter"].pop()
    base = deepcopy(event)
    base.update(name="Google tag", object_key="web-main::tag::Google tag", action="reuse")
    base["intended"] = {
        "type": "googtag",
        "parameter": [param("tagId", "G-TEST123"), param("eventSettingsVariable", "{{Shared}}")],
    }
    settings = deepcopy(next(item for item in operations if item["resource_family"] == "variable"))
    settings.update(name="Shared", object_key="web-main::variable::Shared")
    settings["intended"] = {"type": "gtes", "parameter": [table]}
    operations.extend([base, settings])
    mapping = contract["implementation"]["field_bindings"][0]
    mapping.update(source="form.lead_type", destination_shape="scalar:string")
    return contract, operations, event, base, mapping


class GoogleTagInheritanceTest(unittest.TestCase):
    def check_mapping(self, operations, mapping):
        errors = []
        validate_native_mappings([mapping], operations, errors.append)
        return errors

    def test_inheritance_and_compiler_derivation(self):
        contract, operations, event, base, mapping = inherited_mapping()
        self.assertEqual(self.check_mapping(operations, mapping), [])
        self.assertIs(_associated_google_tag(event, operations), base["intended"])
        compact = {
            "requirements": contract["requirements"],
            "execution_topologies": [],
            "field_bindings": [],
        }
        compact["requirements"][0]["parameters"]["lead_type"]["missing_behavior"] = (
            "omit when absent"
        )
        _derive_exact_declarations(compact, operations)
        self.assertEqual(compact["field_bindings"][0]["native_binding"], mapping["native_binding"])
        self.assertEqual(compact["field_bindings"][0]["gtm_resolution"], "{{DLV - lead_type}}")

    def test_compile_and_run_inherited_mapping_without_repeating_event_settings(self):
        value = lead_request()
        table = value["objects"][0]["intended"]["parameter"].pop()
        base = deepcopy(value["objects"][0])
        base.update(name="Google tag", action="reuse")
        base["intended"].update(type="googtag")
        base["intended"]["parameter"] = [
            param("tagId", "G-TEST123"),
            param("sendPageView", "false", "boolean"),
            param("eventSettingsVariable", "{{Shared}}"),
        ]
        settings = deepcopy(value["reuse_candidates"][-1])
        settings.update(name="Shared", intended={"type": "gtes", "parameter": [table]})
        value["reuse_candidates"].extend([base, settings])
        value["objects"][0]["depends_on"] = ["web-main::tag::Google tag"]
        topology = deepcopy(value["execution_topologies"][0])
        topology["tag_object_key"] = "web-main::tag::Google tag"
        value["execution_topologies"].append(topology)
        value["requirements"][0]["parameters"]["lead_type"]["missing_behavior"] = "omit when absent"
        value["field_bindings"] = []
        contract = compile_request(value)
        self.assertEqual(len(contract["implementation"]["field_bindings"]), 1)
        create_from_contract(contract, run_id="BASE-INHERITANCE", source_locator="approved")

    def test_constant_destination_identity(self):
        _, operations, event, base, mapping = inherited_mapping()
        for owner, field, name in (
            (event, "measurementIdOverride", "Event ID"),
            (base, "tagId", "Base ID"),
        ):
            constant = deepcopy(
                next(item for item in operations if item["resource_family"] == "variable")
            )
            constant.update(name=name, object_key=f"web-main::variable::{name}")
            constant["intended"] = {"type": "c", "parameter": [param("value", "G-TEST123")]}
            operations.append(constant)
            next(row for row in owner["intended"]["parameter"] if row["key"] == field)["value"] = (
                "{{" + name + "}}"
            )
        self.assertEqual(self.check_mapping(operations, mapping), [])
        for item in operations[-2:]:
            item["intended"]["parameter"][0]["value"] = "{{Nested ID}}"
        self.assertTrue(self.check_mapping(operations, mapping))

    def test_wrong_target_destination_paused_removed_ambiguous_and_unresolved_bases(self):
        for mutation in ("target", "destination", "paused", "remove", "ambiguous", "unresolved"):
            with self.subTest(mutation=mutation):
                _, operations, event, base, mapping = inherited_mapping()
                if mutation == "target":
                    base["target_id"] = "other-web"
                elif mutation == "destination":
                    base["intended"]["parameter"][0]["value"] = "G-OTHER"
                elif mutation == "paused":
                    base["intended"]["paused"] = True
                elif mutation == "remove":
                    base["action"] = "remove"
                elif mutation == "unresolved":
                    base["intended"]["parameter"][0]["value"] = "{{Missing ID}}"
                else:
                    duplicate = deepcopy(base)
                    duplicate.update(name="Other base", object_key="web-main::tag::Other base")
                    operations.append(duplicate)
                self.assertTrue(self.check_mapping(operations, mapping))
                # Explicit event mappings remain valid without inherited defaults.
                event["intended"]["parameter"].append(param("eventSettingsVariable", "{{Shared}}"))
                self.assertEqual(self.check_mapping(operations, mapping), [])

    def test_source_and_resolution_are_still_proved(self):
        for mutation in ("source", "resolution", "case", "missing"):
            with self.subTest(mutation=mutation):
                _, operations, _, _, mapping = inherited_mapping()
                if mutation == "source":
                    mapping["source"] = "other.source"
                elif mutation == "resolution":
                    mapping["gtm_resolution"] = "{{Other DLV}}"
                elif mutation == "case":
                    operations[-1]["intended"]["parameter"][0]["list"][0]["map"][0]["value"] = (
                        "LEAD_TYPE"
                    )
                else:
                    operations[-1]["intended"]["parameter"] = []
                self.assertTrue(self.check_mapping(operations, mapping))

    def test_event_settings_then_local_override_base_defaults_preserving_case(self):
        _, operations, event, _, _ = inherited_mapping()
        variables = {
            item["name"]: item["intended"]
            for item in operations
            if item["resource_family"] == "variable"
        }
        event_settings = deepcopy(variables["Shared"])
        event_settings["parameter"][0]["list"][0]["map"][1]["value"] = "{{Event-time DLV}}"
        variables["Event settings"] = event_settings
        event["intended"]["parameter"].append(param("eventSettingsVariable", "{{Event settings}}"))

        def resolve(field="lead_type"):
            return _resolved_event_parameter(event, operations, variables, field)

        self.assertEqual(resolve(), "{{Event-time DLV}}")
        table = deepcopy(event_settings["parameter"][0])
        table["list"][0]["map"][1]["value"] = ""
        event["intended"]["parameter"].append(table)
        self.assertEqual(resolve(), "")
        table["list"][0]["map"][0]["value"] = "LEAD_TYPE"
        self.assertEqual(resolve(), "{{Event-time DLV}}")
        self.assertEqual(resolve("LEAD_TYPE"), "")

    def test_explicit_field_does_not_consult_broken_unused_base_settings(self):
        for explicit in ("settings", "local"):
            with self.subTest(explicit=explicit):
                contract, operations, event, base, mapping = inherited_mapping()
                base["intended"]["parameter"][-1]["value"] = "{{Unresolved base settings}}"
                errors = self.check_mapping(operations, mapping)
                self.assertTrue(
                    any("shared event settings are unresolved" in error for error in errors)
                )
                if explicit == "settings":
                    event["intended"]["parameter"].append(
                        param("eventSettingsVariable", "{{Shared}}")
                    )
                else:
                    event["intended"]["parameter"].append(
                        deepcopy(operations[-1]["intended"]["parameter"][0])
                    )
                compact = {
                    "requirements": contract["requirements"],
                    "execution_topologies": [],
                    "field_bindings": [],
                }
                compact["requirements"][0]["parameters"]["lead_type"]["missing_behavior"] = (
                    "omit when absent"
                )
                with patch(
                    "run_validation_web._associated_google_tag",
                    side_effect=AssertionError("unused base lookup"),
                ):
                    self.assertEqual(self.check_mapping(operations, mapping), [])
                    _derive_exact_declarations(compact, operations)
                self.assertEqual(
                    compact["field_bindings"][0]["gtm_resolution"], mapping["gtm_resolution"]
                )


class BuiltInTriggerTest(unittest.TestCase):
    def test_registry_resolution_and_incompatible_roles(self):
        resolved = _resolved_trigger_types({}, {})
        for key, trigger_type in BUILT_IN_TRIGGER_TYPES.items():
            reference = key.removeprefix("trigger::builtin::")
            row = {
                "trigger_object_key": reference,
                "role": "initialization-page-load",
                "type": trigger_type,
            }
            item = {"normal_triggers": [row]}
            target = {"firingTriggerId": [reference]}
            self.assertEqual(
                _validate_normal_trigger_bindings(
                    item, path="test", target=target, trigger_types=resolved
                )[0]["trigger_object_key"],
                key,
            )
            row["role"] = "cmp-readiness-grant"
            with self.assertRaises(ValueError):
                _validate_normal_trigger_bindings(
                    item, path="test", target=target, trigger_types=resolved
                )
        with self.assertRaises(ValueError):
            _validate_normal_trigger_bindings(
                {
                    "normal_triggers": [
                        {
                            "trigger_object_key": "trigger::builtin::999",
                            "role": "initialization-page-load",
                            "type": "initialization",
                        }
                    ]
                },
                path="test",
                target={"firingTriggerId": ["trigger::builtin::999"]},
                trigger_types=resolved,
            )

    def test_builtin_initialization_at_full_contract_boundary(self):
        contract = valid_pipeline_contract()
        owner = contract["implementation"]["objects"][0]
        owner["intended"]["firingTriggerId"] = ["2147479573"]
        contract["execution_topologies"][0]["normal_triggers"] = [
            {
                "trigger_object_key": "2147479573",
                "role": "initialization-page-load",
                "type": "initialization",
            }
        ]
        approve_mutations(contract)
        create_from_contract(contract, run_id="BUILTIN", source_locator="approved")


if __name__ == "__main__":
    unittest.main()
