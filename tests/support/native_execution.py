import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from fixtures.mcp_behavior_scenario import PROFILE, FakeGtm, bind, request
from gtm_configure.adapters.mcp import McpTargetAdapter
from gtm_configure.contract import ContractValidationError, validate_document
from gtm_configure.core.privacy import contains_redacted, redact_for_persistence, sensitive_findings
from gtm_configure.core.public_identifiers import canonical_template_source, public_identifier_paths
from gtm_configure.intake.request import compile_request
from gtm_configure.runtime.adapter_protocol import (
    AdapterExecutionError,
    AuthenticationError,
    atomic_write,
)
from gtm_configure.runtime.engine import (
    RateLimitError,
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from gtm_configure.runtime.state import create_from_contract, load_document
from gtm_configure.runtime.verification import (
    build_pre_write_comparison,
    build_verification_comparison,
    expected_graph,
)

from support.adapters import FakeAdapter, capabilities
from support.contracts import approve_mutations, valid_web_contract
from support.enhanced_conversions import event_override_contract  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

SOURCE = '\ufeff\ufeff___INFO___\n{"id":"original", "name":"Fixture"}\n\n___WEB_PERMISSIONS___\n[{"key":"read", "value":true}]\n\n___SANDBOXED_JS_FOR_WEB_TEMPLATE___\nconst x = 1;\n\n___TESTS___\nassertThat("test@example.org");\n'

NATIVE = '___INFO___\n{\n "name": "Fixture", "id": "original"\n}\n___WEB_PERMISSIONS___\n[ { "value": true, "key": "read" } ]\n___SANDBOXED_JS_FOR_WEB_TEMPLATE___\nconst x = 1;\n___TESTS___\nassertThat("test@example.org");\n'


def operation(family="template"):
    op = {
        "operation_id": "op",
        "target_id": "web-main",
        "resource_family": family,
        "action": "create",
        "name": "Fixture",
        "object_key": f"web-main::{family}::Fixture",
        "container_type": "web",
        "intended": {},
    }
    if family == "template":
        op["intended"] = {"templateData": SOURCE}
        op["public_identifiers"] = [
            {
                "classification": "inspected-template-source",
                "path": ["templateData"],
                "value_sha256": hashlib.sha256(SOURCE.encode()).hexdigest(),
            }
        ]
    return op


class NativeCorrectionsTestsFixture(unittest.TestCase):
    pass


class RecoveryCorrectionsTestsFixture(unittest.TestCase):
    pass


class NativeBindingTestsFixture(unittest.TestCase):
    pass


def meta_matching_contract(fields=("em", "ph")):
    contract = event_override_contract()
    req = contract["requirements"][0]
    req["destination"] = "Meta"
    original = deepcopy(req["parameters"]["user_data"])
    req["parameters"] = {}
    tag = contract["implementation"]["objects"][0]
    tag["intended"]["type"] = "cvt_meta"
    rows = []
    bindings = []
    routes = []
    original_route = deepcopy(contract["first_party_data_routes"][0])
    objects = contract["implementation"]["objects"]
    removed = {o["object_key"] for o in objects if o["intended"].get("type") == "awec"}
    objects[:] = [o for o in objects if o["object_key"] not in removed]
    tag["depends_on"] = [k for k in tag["depends_on"] if k not in removed]
    email = next(o for o in objects if o["name"] == "DLV - Approved email")
    tag["depends_on"].append(email["object_key"])
    if "ph" in fields:
        phone = deepcopy(email)
        phone.update(
            name="DLV - Approved phone", object_key="web-main::variable::DLV - Approved phone"
        )
        phone["intended"]["parameter"][0]["value"] = "customer.phone"
        objects.append(phone)
        tag["depends_on"].append(phone["object_key"])
    for index, name in enumerate(fields):
        source = "customer.email" if name == "em" else "customer.phone"
        reference = "{{DLV - Approved email}}" if name == "em" else "{{DLV - Approved phone}}"
        req["parameters"][name] = {
            **original,
            "source": source,
            "source_shape": "scalar:string",
            "destination_shape": "scalar:string",
        }
        rows.append(
            {
                "type": "map",
                "map": [
                    {"type": "template", "key": "name", "value": name},
                    {"type": "template", "key": "value", "value": reference},
                ],
            }
        )
        binding = deepcopy(contract["implementation"]["field_bindings"][0])
        binding.update(
            destination_field=name,
            gtm_resolution=reference,
            template_field="advancedMatchingList:" + name,
        )
        bindings.append(binding)
        route = deepcopy(original_route)
        route.update(
            feature="vendor-advanced-matching",
            destination_field=name,
            fields=[
                {
                    "name": name,
                    "source": source,
                    "normalization": ["native"],
                    "empty_behavior": "omit",
                }
            ],
        )
        route["consumer_bindings"][0].update(
            product="meta",
            implementation="installed-template",
            tag_type="cvt_meta",
            template_identity="cvt_meta",
            user_data_path=[
                "parameter",
                "advancedMatchingList",
                "list",
                index,
                "map",
                "value",
                "value",
            ],
            activation_paths=[["parameter", "advancedMatching", "value"]],
        )
        routes.append(route)
    tag["intended"]["parameter"] = [
        {"type": "boolean", "key": "advancedMatching", "value": "true"},
        {"type": "list", "key": "advancedMatchingList", "list": rows},
    ]
    contract["implementation"]["field_bindings"] = bindings
    contract["first_party_data_routes"] = routes
    contract["consent_topologies"][0]["destination"] = "Meta"
    contract["execution_topologies"][0]["built_in_consent_checks"] = []
    return approve_mutations(contract)


class MatchingCorrectionsTestsFixture(unittest.TestCase):
    pass


__all__ = [
    "AdapterExecutionError",
    "AuthenticationError",
    "ContractValidationError",
    "FakeAdapter",
    "FakeGtm",
    "MatchingCorrectionsTestsFixture",
    "McpTargetAdapter",
    "NATIVE",
    "NativeBindingTestsFixture",
    "NativeCorrectionsTestsFixture",
    "PROFILE",
    "Path",
    "ROOT",
    "RateLimitError",
    "RecoveryCorrectionsTestsFixture",
    "SOURCE",
    "TargetAdapterRegistry",
    "approve_mutations",
    "atomic_write",
    "bind",
    "build_pre_write_comparison",
    "build_verification_comparison",
    "canonical_template_source",
    "capabilities",
    "compile_request",
    "contains_redacted",
    "create_from_contract",
    "deepcopy",
    "execute_ready_operations",
    "expected_graph",
    "hashlib",
    "load_document",
    "meta_matching_contract",
    "operation",
    "os",
    "public_identifier_paths",
    "redact_for_persistence",
    "request",
    "sensitive_findings",
    "subprocess",
    "sys",
    "tempfile",
    "valid_web_contract",
    "validate_document",
    "verify_idempotent_rerun",
]
