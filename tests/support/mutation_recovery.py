import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from gtm_configure.adapters.mcp import McpTargetAdapter, unwrap
from gtm_configure.contract import ContractValidationError, validate_document
from gtm_configure.core.privacy import redact_for_persistence, sensitive_paths
from gtm_configure.core.public_identifiers import (
    public_identifier_paths,
    validate_public_identifiers,
)
from gtm_configure.core.validation import RunValidationError
from gtm_configure.domain.actions import validate_native_authoring
from gtm_configure.domain.first_party_data import first_party_binding_value
from gtm_configure.domain.resources import requires_variable_consumer_check
from gtm_configure.runtime.adapter_protocol import (
    AdapterExecutionError,
    AmbiguousWriteError,
    AuthenticationError,
    RateLimitError,
    atomic_write,
)
from gtm_configure.runtime.engine import TargetAdapterRegistry, execute_ready_operations
from gtm_configure.runtime.state import create_from_contract, load_document
from gtm_configure.runtime.verification import build_verification_comparison, expected_graph

from support.adapters import FakeAdapter, capabilities
from support.contracts import approve_mutations, valid_web_contract
from support.enhanced_conversions import event_override_contract  # noqa: E402
from support.shared_event_id import generated_contract  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def sender_generated_contract():
    contract = generated_contract()
    contract["mode"] = "web"
    contract["targets"] = [t for t in contract["targets"] if t["container_type"] == "web"]
    contract["pipelines"] = []
    objects = contract["implementation"]["objects"]
    objects[:] = [o for o in objects if o["target_id"] == "web-main"]
    for obj in objects:
        obj["depends_on"] = [k for k in obj["depends_on"] if k.startswith("web-main::")]
    for topology in contract["consent_policies"]:
        topology["server_tag_keys"] = []
        topology["server_enforcement"] = {"mechanism": "none"}
    contract["external_dependencies"].append(
        {
            "id": "receiver",
            "requirement_ids": ["REQ-ATC"],
            "owner": "External server owner",
            "action": "Verify receipt and reuse of event_id; sender save does not certify receiver",
            "status": "accepted",
        }
    )
    contract["dedup_contracts"][0]["external_receiver_dependency_id"] = "receiver"
    return approve_mutations(contract)


def sender_user_data_contract():
    contract = event_override_contract()
    tag = contract["implementation"]["objects"][0]
    tag["intended"]["type"] = "gaawe"
    tag["intended"]["parameter"] = [
        {"key": "measurementIdOverride", "type": "template", "value": "G-TEST123"},
        {"key": "eventName", "type": "template", "value": "purchase"},
        {
            "key": "eventSettingsTable",
            "type": "list",
            "list": [
                {
                    "type": "map",
                    "map": [
                        {"key": "parameter", "type": "template", "value": "user_data"},
                        {
                            "key": "parameterValue",
                            "type": "template",
                            "value": "{{UPD - Approved conversion}}",
                        },
                    ],
                }
            ],
        },
    ]
    route = contract["first_party_data_routes"][0]
    route.update(
        feature="google-ads-server-user-data-transport",
        server_consumer_object_keys=[],
        external_receiver_dependency_id="EXT-ADS",
    )
    binding = route["consumer_bindings"][0]
    binding.update(product="google-ads-transport")
    for key in ("user_data_path", "activation_paths", "field_review"):
        binding.pop(key)
    contract["implementation"]["field_bindings"][0]["template_field"] = "user_data"
    return approve_mutations(contract)


class NativeAndRecoveryTestsFixture(unittest.TestCase):
    pass


__all__ = [
    "AdapterExecutionError",
    "AmbiguousWriteError",
    "AuthenticationError",
    "ContractValidationError",
    "FakeAdapter",
    "McpTargetAdapter",
    "NativeAndRecoveryTestsFixture",
    "Path",
    "RateLimitError",
    "RunValidationError",
    "TargetAdapterRegistry",
    "approve_mutations",
    "atomic_write",
    "build_verification_comparison",
    "capabilities",
    "create_from_contract",
    "deepcopy",
    "execute_ready_operations",
    "expected_graph",
    "first_party_binding_value",
    "hashlib",
    "json",
    "load_document",
    "public_identifier_paths",
    "redact_for_persistence",
    "requires_variable_consumer_check",
    "sender_generated_contract",
    "sender_user_data_contract",
    "sensitive_paths",
    "tempfile",
    "unwrap",
    "valid_web_contract",
    "validate_document",
    "validate_native_authoring",
    "validate_public_identifiers",
]
