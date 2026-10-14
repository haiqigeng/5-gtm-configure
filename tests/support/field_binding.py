import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from fixtures.mcp_behavior_scenario import param, request
from gtm_configure.cli.mcp import execute
from gtm_configure.domain.native import FieldResolutionError, effective_collection_fields
from gtm_configure.intake.request import compile_request
from gtm_configure.render import render_markdown
from gtm_configure.runtime.adapter_protocol import atomic_write
from gtm_configure.runtime.state import create_from_contract, load_document

from support.adapters import FakeAdapter, capabilities
from support.contracts import valid_pipeline_contract

ROOT = Path(__file__).resolve().parents[2]


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


class NativeMappingTestFixture(unittest.TestCase):
    pass


class StartupTestFixture(unittest.TestCase):
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
            with patch("gtm_configure.cli.mcp.McpTargetAdapter", Adapter):
                if invalid_profile:
                    with self.assertRaises(ValueError):
                        execute(path, profiles, transport)
                else:
                    execute(path, profiles, transport)
            return load_document(path), adapters, identities


__all__ = [
    "FieldResolutionError",
    "NativeMappingTestFixture",
    "StartupTestFixture",
    "compile_request",
    "create_from_contract",
    "deepcopy",
    "effective_collection_fields",
    "lead_request",
    "param",
    "render_markdown",
    "valid_pipeline_contract",
]
