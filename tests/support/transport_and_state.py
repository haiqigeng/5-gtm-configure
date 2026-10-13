from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import gtm_configure.runtime.state as run_state
from check_release import check_git_state
from gtm_configure.cli.run import RunValidationError
from gtm_configure.comparison.native import differences
from gtm_configure.contract import ContractValidationError, validate_document
from gtm_configure.domain.events import trigger_accepts_event
from gtm_configure.intake.ga4 import HandoffError, verify_delivery
from gtm_configure.runtime.state import checkpoint_operation, create_from_contract, inspect_document
from gtm_configure.runtime.validation import validate_document as validate_run
from gtm_configure.runtime.verification import build_pre_write_comparison

from support.contracts import (
    approve_mutations,
    complete_capture_evidence,
    valid_pipeline_contract,
    valid_server_contract,
    valid_web_contract,
    with_complete_baselines,
)

ROOT = Path(__file__).resolve().parents[2]


def condition(operator: str, value: str, **flags: object) -> dict:
    return {
        "type": operator,
        "parameter": [
            {"key": "arg0", "type": "template", "value": "{{_event}}"},
            {"key": "arg1", "type": "template", "value": value},
            *[{"key": key, "type": "boolean", "value": item} for key, item in flags.items()],
        ],
    }


def ads_transport_contract() -> dict:
    """Synthetic native-field model; not an export or installed-template certification."""
    contract = valid_pipeline_contract()
    contract["route"] = "combined"
    contract["requirements"][0]["kind"] = "analytics"
    requirement = deepcopy(contract["requirements"][0])
    requirement.update(
        id="REQ-ADS",
        kind="media",
        destination="Google Ads",
        event_name="purchase",
        source_event="purchase",
    )
    requirement["parameters"] = {
        "user_data": {
            "source": "customer",
            "source_shape": "object",
            "destination_shape": "object",
            "provenance": {
                "grade": "approved-input",
                "locator": "Synthetic Ads-only matching approval",
            },
        }
    }
    contract["requirements"].append(requirement)
    next(item for item in contract["evidence"] if item["grade"] == "official-current")[
        "supports"
    ].append("REQ-ADS")
    contract["implementation"]["field_bindings"] += [
        {
            "requirement_id": "REQ-ADS",
            "field_scope": "event-parameter",
            "destination_field": "user_data",
            "status": "mapped",
            "shape_compatibility": "compatible",
            "mapping_method": "native-template",
            "gtm_resolution": "{{UPD - Approved purchase}}",
            "template_field": "user_data",
            "missing_behavior": "Omit unavailable identifiers; never synthesize identity",
        }
    ]
    contract["scope"]["included"].append("REQ-ADS")
    objects = contract["implementation"]["objects"]
    sender_key = "web-main::tag::Ads identity sender"
    web_trigger_key = "web-main::trigger::Purchase"
    receiver_key = "server-main::tag::Ads conversion"
    server_trigger_key = "server-main::trigger::Purchase"
    client_key = contract["pipelines"][0]["claiming_client"]["object_key"]
    for target_id, family, name, key, intended, dependencies in [
        (
            "web-main",
            "trigger",
            "Purchase",
            web_trigger_key,
            {
                "type": "customEvent",
                "customEventFilter": [
                    {
                        "type": "equals",
                        "parameter": [
                            {"type": "template", "key": "arg0", "value": "{{_event}}"},
                            {"type": "template", "key": "arg1", "value": "purchase"},
                        ],
                    }
                ],
            },
            [],
        ),
        (
            "server-main",
            "trigger",
            "Purchase",
            server_trigger_key,
            {
                "type": "customEvent",
                "customEventFilter": [
                    {
                        "type": "equals",
                        "parameter": [
                            {"type": "template", "key": "arg0", "value": "{{_event}}"},
                            {"type": "template", "key": "arg1", "value": "purchase"},
                        ],
                    }
                ],
            },
            [],
        ),
        (
            "web-main",
            "tag",
            "Ads identity sender",
            sender_key,
            {
                "type": "gaawe",
                "measurement_id": "G-TEST123",
                "event_name": "purchase",
                "user_data": "{{UPD - Approved purchase}}",
                "firingTriggerId": [web_trigger_key],
                "blockingTriggerId": [],
                "tagFiringOption": "oncePerEvent",
            },
            [web_trigger_key],
        ),
        (
            "server-main",
            "tag",
            "Ads conversion",
            receiver_key,
            {
                "type": "Google Ads Conversion Tracking",
                "event_name": "purchase",
                "firingTriggerId": [server_trigger_key],
                "blockingTriggerId": [],
            },
            [client_key, server_trigger_key],
        ),
    ]:
        objects.append(
            {
                "target_id": target_id,
                "resource_family": family,
                "name": name,
                "object_key": key,
                "action": "create",
                "requirement_ids": ["REQ-ADS"],
                "depends_on": dependencies,
                "justification": "Explicit synthetic feature",
                "evidence": ["approved-input", "official-current"],
                "risk": "routine",
                "intended": intended,
            }
        )
    pipeline = contract["pipelines"][0]
    pipeline["event_flows"].append(
        {
            "requirement_id": "REQ-ADS",
            "source_event": "purchase",
            "transported_event": "purchase",
            "server_consumer_keys": [receiver_key],
        }
    )
    pipeline["field_flows"].append(
        {
            "status": "proved",
            "field_scope": "event-parameter",
            "destination_field": "user_data",
            "source": {"path": "customer", "shape": "object"},
            "wire": {"path": "user_data", "shape": "object"},
            "event_data": {"path": "user_data", "shape": "object"},
            "destination": {"path": "user_data", "shape": "object"},
            "requirement_ids": ["REQ-ADS"],
            "receiver_owner": receiver_key,
            "claiming_client_proof": "Synthetic Google Client shape premise",
            "missing_behavior": "Omit unavailable fields",
            "runtime_verification_note": "Verify actual Client decode and Ads-only visibility",
        }
    )
    pipeline["operation_dependencies"].extend(
        [web_trigger_key, server_trigger_key, receiver_key, sender_key]
    )
    transport_owner = next(
        item for item in objects if item["object_key"] == pipeline["cutover_operation_key"]
    )
    transport_owner["depends_on"].extend([server_trigger_key, receiver_key])
    consent = deepcopy(contract["consent_topologies"][0])
    consent.update(
        consent_topology_id="CONSENT-ADS",
        destination="Google Ads",
        requirement_ids=["REQ-ADS"],
        event_coverage=["purchase"],
        server_tag_keys=[receiver_key],
        transporter_tag_keys=[sender_key],
    )
    contract["consent_topologies"].append(consent)
    pipeline["consent_topology_ids"].append("CONSENT-ADS")
    topology = deepcopy(contract["execution_topologies"][0])
    topology.update(
        tag_object_key=sender_key,
        requirement_ids=["REQ-ADS"],
        lifecycle_role="event-driven",
        normal_triggers=[
            {"trigger_object_key": web_trigger_key, "role": "source-event", "type": "custom-event"}
        ],
        consent_topology_ids=["CONSENT-ADS"],
        page_view_capable=False,
        page_view_destinations=[],
        page_view_occurrences=[],
    )
    contract["execution_topologies"].append(topology)
    contract["external_dependencies"] = [
        {
            "id": "EXT-ADS",
            "requirement_ids": ["REQ-ADS"],
            "owner": "Ads owner",
            "action": "Confirm feature activation",
            "status": "open",
        }
    ]
    contract["first_party_data_routes"] = [
        {
            "requirement_id": "REQ-ADS",
            "feature": "google-ads-server-user-data-transport",
            "destination_field": "user_data",
            "consumer_object_keys": [sender_key],
            "server_consumer_object_keys": [receiver_key],
            "consumer_bindings": [
                {
                    "object_key": sender_key,
                    "product": "google-ads-transport",
                    "implementation": "native",
                    "tag_type": "gaawe",
                    "template_identity": None,
                    "evidence": ["Synthetic template premise"],
                }
            ],
            "source_priority": "data-layer",
            "timing": "same-event",
            "hashing_owner": "native-raw",
            "fields": [
                {
                    "name": "email",
                    "source": "customer.email",
                    "normalization": ["native normalization"],
                    "empty_behavior": "omit",
                }
            ],
            "consent_types": ["ad_user_data"],
            "external_dependency_ids": ["EXT-ADS"],
            "evidence": ["Synthetic authorized Ads-only transport"],
        }
    ]
    return approve_mutations(contract)


class UtilityEvolutionTestFixture(unittest.TestCase):
    pass


__all__ = [
    "ContractValidationError",
    "HandoffError",
    "Path",
    "RunValidationError",
    "UtilityEvolutionTestFixture",
    "ads_transport_contract",
    "approve_mutations",
    "build_pre_write_comparison",
    "check_git_state",
    "checkpoint_operation",
    "complete_capture_evidence",
    "condition",
    "create_from_contract",
    "deepcopy",
    "differences",
    "hashlib",
    "inspect_document",
    "json",
    "patch",
    "run_state",
    "subprocess",
    "tempfile",
    "trigger_accepts_event",
    "valid_pipeline_contract",
    "valid_server_contract",
    "valid_web_contract",
    "validate_document",
    "validate_run",
    "verify_delivery",
    "with_complete_baselines",
]
