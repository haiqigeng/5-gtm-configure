import unittest
from pathlib import Path

from support.contracts import approve_mutations, valid_web_contract  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


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


class EnhancedConversionsTestsFixture(unittest.TestCase):
    pass
