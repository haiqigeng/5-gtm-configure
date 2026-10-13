import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from fixtures.mcp_behavior_scenario import param
from gtm_configure.domain.execution import validate_normal_trigger_bindings
from gtm_configure.domain.fields import validate_native_mappings
from gtm_configure.domain.web_model import BUILT_IN_TRIGGER_TYPES
from gtm_configure.domain.web_native import (
    associated_google_tag,
    resolved_event_parameter,
    resolved_trigger_types,
)
from gtm_configure.intake.request import compile_request, derive_exact_declarations
from gtm_configure.runtime.state import create_from_contract

from support.contracts import approve_mutations, valid_pipeline_contract
from support.field_binding import lead_request

ROOT = Path(__file__).resolve().parents[2]


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


class GoogleTagInheritanceTestFixture(unittest.TestCase):
    def check_mapping(self, operations, mapping):
        errors = []
        validate_native_mappings([mapping], operations, errors.append)
        return errors


class BuiltInTriggerTestFixture(unittest.TestCase):
    pass


__all__ = [
    "BUILT_IN_TRIGGER_TYPES",
    "BuiltInTriggerTestFixture",
    "GoogleTagInheritanceTestFixture",
    "approve_mutations",
    "associated_google_tag",
    "compile_request",
    "create_from_contract",
    "deepcopy",
    "derive_exact_declarations",
    "inherited_mapping",
    "lead_request",
    "param",
    "patch",
    "resolved_event_parameter",
    "resolved_trigger_types",
    "valid_pipeline_contract",
    "validate_normal_trigger_bindings",
]
