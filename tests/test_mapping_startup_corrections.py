"""Offline regression tests for native mapping and target startup containment."""
# ruff: noqa: E402

import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests"), str(ROOT / "tests/fixtures")]
from compile_configuration_request import compile_request
from configuration_run import atomic_write, create_from_contract, load_document
from current_support import valid_pipeline_contract
from mcp_behavior_scenario import param, request
from mcp_execute import execute
from native_configuration import FieldResolutionError, effective_event_parameters
from run_render import render_markdown
from test_current_adapter_runtime import FakeAdapter, capabilities


def lead_request():
    value = request()
    value["requirements"][0]["parameters"] = {
        "lead_type": {
            "source": "form.lead_type",
            "source_shape": "scalar:string",
            "destination_shape": "scalar:string",
            "provenance": {"grade": "approved-input", "locator": "Approved lead field"},
        }
    }
    value["field_bindings"] = [
        {
            "requirement_id": "REQ-LEAD",
            "field_scope": "event-parameter",
            "destination_field": "lead_type",
            "shape_compatibility": "compatible",
            "mapping_method": "direct-dlv",
            "gtm_resolution": "{{DLV - lead_type}}",
            "template_field": "eventSettingsTable.lead_type",
            "missing_behavior": "omit when absent",
            "status": "mapped",
            "native_binding": {
                "object_key": "web-main::tag::GA4 - generate_lead",
                "field": "lead_type",
            },
        }
    ]
    variable = deepcopy(value["reuse_candidates"][2])
    variable.update(
        name="DLV - lead_type",
        intended={
            "type": "v",
            "parameter": [
                param("name", "form.lead_type"),
                param("dataLayerVersion", "2", "integer"),
            ],
        },
    )
    value["reuse_candidates"].append(variable)
    value["objects"][0]["intended"]["parameter"].append(
        {
            "key": "eventSettingsTable",
            "type": "list",
            "list": [
                {
                    "type": "map",
                    "map": [
                        param("parameter", "lead_type"),
                        param("parameterValue", "{{DLV - lead_type}}"),
                    ],
                }
            ],
        }
    )
    return value


class NativeMappingTest(unittest.TestCase):
    def test_direct_dlv_native_table_and_run(self):
        contract = compile_request(lead_request())
        create_from_contract(contract, run_id="MAPPING", source_locator="approved")

    def test_inherited_event_settings(self):
        value = lead_request()
        table = value["objects"][0]["intended"]["parameter"].pop()
        variable = deepcopy(value["reuse_candidates"][-1])
        variable.update(name="Shared lead fields", intended={"type": "gtes", "parameter": [table]})
        value["reuse_candidates"].append(variable)
        value["objects"][0]["intended"]["parameter"].append(
            param("eventSettingsVariable", "{{Shared lead fields}}")
        )
        create_from_contract(compile_request(value), run_id="INHERITED", source_locator="approved")

    def test_missing_binding_field_variable_wrong_source_and_owner_fail(self):
        for mutation in ("field", "variable", "source", "owner", "metadata"):
            with self.subTest(mutation=mutation):
                value = lead_request()
                binding = value["field_bindings"][0]
                if mutation == "binding":
                    binding.pop("native_binding")
                elif mutation == "field":
                    value["objects"][0]["intended"]["parameter"].pop()
                elif mutation == "variable":
                    value["reuse_candidates"].pop()
                elif mutation == "source":
                    value["reuse_candidates"][-1]["intended"]["parameter"][0]["value"] = (
                        "wrong.source"
                    )
                elif mutation == "owner":
                    binding["native_binding"]["object_key"] = "web-main::variable::DLV - lead_type"
                else:
                    binding["native_binding"]["field"] = "notes"
                    value["objects"][0]["intended"]["notes"] = binding["gtm_resolution"]
                with self.assertRaises(ValueError):
                    compile_request(value)

    def test_exact_event_names_at_compile_and_run_boundaries(self):
        for name in ("LEAD_TYPE", "leadtype", "lead-type"):
            for change_binding in (False, True):
                with self.subTest(name=name, change_binding=change_binding):
                    value = lead_request()
                    contract = compile_request(value)
                    for document, objects, bindings in (
                        (value, value["objects"], value["field_bindings"]),
                        (
                            contract,
                            contract["implementation"]["objects"],
                            contract["implementation"]["field_bindings"],
                        ),
                    ):
                        objects[0]["intended"]["parameter"][-1]["list"][0]["map"][0]["value"] = name
                        if change_binding:
                            bindings[0]["native_binding"]["field"] = name
                    with self.assertRaises(ValueError):
                        compile_request(value)
                    with self.assertRaises(ValueError):
                        create_from_contract(contract, run_id="WRONG", source_locator="approved")

    def test_other_namespaces_and_configuration_cannot_prove_event_field(self):
        for namespace in ("configSettingsTable", "userProperties", "itemParameters"):
            with self.subTest(namespace=namespace):
                value = lead_request()
                # Deliberately wrong namespace, not a claimed valid native user/item shape.
                value["objects"][0]["intended"]["parameter"][-1]["key"] = namespace
                with self.assertRaises(ValueError):
                    compile_request(value)

    def test_user_and_item_scopes_are_agent_reviewed_with_or_without_binding(self):
        for requirement_key, scope in (
            ("user_properties", "user-property"),
            ("item_parameters", "item-parameter"),
        ):
            for binding_present in (False, True):
                for event_row_present in (False, True):
                    with self.subTest(
                        scope=scope, binding=binding_present, event_row=event_row_present
                    ):
                        value = lead_request()
                        value["requirements"][0][requirement_key] = value["requirements"][0].pop(
                            "parameters"
                        )
                        binding = value["field_bindings"][0]
                        binding["field_scope"] = scope
                        binding["template_field"] = "agent-inspected native route"
                        if not binding_present:
                            binding.pop("native_binding")
                        if not event_row_present:
                            value["objects"][0]["intended"]["parameter"].pop()
                        run = create_from_contract(
                            compile_request(value), run_id="SCOPED", source_locator="approved"
                        )
                        rendered = render_markdown(run)
                        self.assertIn("agent-reviewed mapping declaration", rendered)
                        self.assertNotIn("exact native event-parameter intention checked", rendered)

    def test_native_event_table_and_assurance(self):
        value = lead_request()
        table = value["objects"][0]["intended"]["parameter"][-1]
        self.assertEqual(
            effective_event_parameters(value["objects"][0]["intended"], {}),
            {"lead_type": "{{DLV - lead_type}}"},
        )
        table["key"] = "eventParameters"
        table["list"][0]["map"][0]["key"] = "name"
        table["list"][0]["map"][1]["key"] = "value"
        self.assertEqual(effective_event_parameters(value["objects"][0]["intended"], {}), {})
        self.assertEqual(
            effective_event_parameters(
                {"parameter": [param("eventSettingsVariable", "{{Shared}}")]},
                {"Shared": {"type": "gtes", "parameter": [table]}},
            ),
            {},
        )
        with self.assertRaises(ValueError):
            compile_request(value)
        run = create_from_contract(
            compile_request(lead_request()), run_id="EXACT", source_locator="approved"
        )
        self.assertIn("exact native event-parameter intention checked", render_markdown(run))

    def test_exact_shared_settings_resolution_and_local_override(self):
        table = lead_request()["objects"][0]["intended"]["parameter"][-1]
        shared = {"Shared": {"type": "gtes", "parameter": [table]}}
        target = {"parameter": [param("eventSettingsVariable", "{{Shared}}"), deepcopy(table)]}
        row = target["parameter"][-1]["list"][0]["map"]
        row[0]["value"] = "LEAD_TYPE"
        row[1]["value"] = "different"
        self.assertEqual(
            effective_event_parameters(target, shared),
            {"lead_type": "{{DLV - lead_type}}", "LEAD_TYPE": "different"},
        )
        row[0]["value"] = "lead_type"
        row[1]["value"] = ""
        self.assertEqual(effective_event_parameters(target, shared), {"lead_type": ""})
        target["parameter"][-1]["list"].append(deepcopy(target["parameter"][-1]["list"][0]))
        with self.assertRaises(FieldResolutionError):
            effective_event_parameters(target, shared)
        shared["Shared"]["parameter"].append(param("eventSettingsVariable", "{{Shared}}"))
        with self.assertRaises(FieldResolutionError):
            effective_event_parameters(
                {"parameter": [param("eventSettingsVariable", "{{Shared}}")]}, shared
            )

    def test_native_template_is_agent_reviewed_even_with_binding(self):
        for binding_present in (False, True):
            value = lead_request()
            value["field_bindings"][0]["mapping_method"] = "native-template"
            if not binding_present:
                value["field_bindings"][0].pop("native_binding")
            value["objects"][0]["intended"]["parameter"].pop()
            run = create_from_contract(
                compile_request(value), run_id="PRODUCT", source_locator="approved"
            )
            self.assertIn("agent-reviewed mapping declaration", render_markdown(run))
            self.assertNotIn("exact native event-parameter intention checked", render_markdown(run))

    def test_automatic_page_location_needs_no_duplicate_parameter(self):
        create_from_contract(
            valid_pipeline_contract(), run_id="AUTOMATIC", source_locator="approved"
        )


class StartupTest(unittest.TestCase):
    def run_startup(self, *, invalid_profile=False, unavailable=False):
        contract = valid_pipeline_contract(cutover=True)
        document = create_from_contract(contract, run_id="STARTUP", source_locator="approved")
        adapters = {}
        identities = []

        class Adapter(FakeAdapter):
            def __init__(self, target, profile, transport):
                if profile.get("invalid"):
                    raise ValueError("invalid profile")
                existing = {
                    op["name"]
                    for op in document["object_changes"]
                    if op["target_id"] == target["target_id"]
                    and op["action"] in {"reuse", "update", "pause", "remove"}
                }
                super().__init__(existing=existing)
                self.bind_target(target)
                self.target_id = target["target_id"]
                adapters[self.target_id] = self

            def identity(self):
                identities.append(self.target_id)
                if unavailable and self.target_id == "server-main":
                    raise RuntimeError("authentication unavailable")
                return super().identity()

            def capabilities(self):
                return capabilities("tag", "trigger", "variable", "client")

        profiles = {target["target_id"]: {} for target in document["run"]["targets"]}
        if invalid_profile:
            profiles["server-main"] = {"invalid": True}
        transport = type("Transport", (), {"calls": 0, "writes_attempted": 0})()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            atomic_write(path, document)
            with patch("mcp_execute.McpTargetAdapter", Adapter):
                if invalid_profile:
                    with self.assertRaises(ValueError):
                        execute(path, profiles, transport)
                else:
                    execute(path, profiles, transport)
            return load_document(path), adapters, identities

    def test_auth_failure_contained_and_dependent_cutover_blocked(self):
        run, adapters, _ = self.run_startup(unavailable=True)
        server = [o for o in run["object_changes"] if o["target_id"] == "server-main"]
        self.assertTrue(all(o["state"] == "planned" for o in server))
        web = {o["name"]: o["state"] for o in run["object_changes"] if o["target_id"] == "web-main"}
        self.assertEqual(web["Google tag - Web transport"], "planned")
        self.assertIn("verified", web.values())
        self.assertEqual(adapters["server-main"].mutations, [])
        self.assertTrue(adapters["web-main"].mutations)

    def test_invalid_later_profile_prevents_all_authenticated_calls(self):
        _, adapters, identities = self.run_startup(invalid_profile=True)
        self.assertEqual(identities, [])
        self.assertTrue(all(not adapter.mutations for adapter in adapters.values()))

    def test_all_available_targets_converge(self):
        run, _, _ = self.run_startup()
        self.assertTrue(all(o["state"] == "verified" for o in run["object_changes"]))
        self.assertTrue(run["idempotency"]["checked"])


if __name__ == "__main__":
    unittest.main()
