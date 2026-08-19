from __future__ import annotations

from copy import deepcopy

WEB_TARGET = {
    "target_id": "web-main",
    "container_type": "web",
    "account_id": "account-1",
    "container_id": "GTM-WEBTEST",
    "workspace_id": "workspace-web",
    "authority": {"grade": "approved-input", "locator": "User request / web target"},
}
SERVER_TARGET = {
    "target_id": "server-main",
    "container_type": "server",
    "account_id": "account-1",
    "container_id": "GTM-SERVERTEST",
    "workspace_id": "workspace-server",
    "authority": {"grade": "approved-input", "locator": "User request / server target"},
}


def valid_pipeline_contract(*, cutover: bool = False) -> dict:
    web_key = "web-main::tag::Google tag - Web transport"
    consent_trigger_key = "web-main::trigger::CMP - Analytics granted"
    client_key = "server-main::client::GA4 Client - Web transport"
    server_trigger_key = "server-main::trigger::Event Data - page_view"
    server_tag_key = "server-main::tag::GA4 - page_view"
    web_action = {
        "target_id": "web-main",
        "resource_family": "tag",
        "name": "Google tag - Web transport",
        "object_key": web_key,
        "action": "create",
        "requirement_ids": ["REQ-PAGE"],
        "depends_on": [consent_trigger_key],
        "justification": "Owns the approved GA4 web transport and page view",
        "evidence": ["approved-input", "official-current"],
        "risk": "routine",
        "intended": {
            "type": "googtag",
            "measurement_id": "G-TEST123",
            "server_container_url": "https://tags.example.test",
            "send_page_view": True,
            "firingTriggerId": [consent_trigger_key],
            "blockingTriggerId": [],
            "tagFiringOption": "oncePerEvent",
        },
    }
    if cutover:
        web_action.update(
            {
                "action": "update",
                "object_id": "tag-100",
                "depends_on": [
                    client_key,
                    server_trigger_key,
                    server_tag_key,
                    consent_trigger_key,
                ],
                "evidence": [
                    "approved-input",
                    "official-current",
                    "container-confirmed",
                ],
                "risk": "high-impact",
                "explicit_authority": True,
                "pre_change": {
                    "type": "googtag",
                    "measurement_id": "G-TEST123",
                    "send_page_view": True,
                },
            }
        )
    pipeline = {
        "pipeline_id": "PIPE-GA4",
        "sending_target_ids": ["web-main"],
        "receiving_target_id": "server-main",
        "request_class": "GA4 collect",
        "transport_owner": web_key,
        "endpoint_reference": "https://tags.example.test",
        "claiming_client": {
            "object_key": client_key,
            "claim_criteria": "Default GA4 Client claims GA4 collect requests",
        },
        "page_view_ownership": {
            "owner": web_key,
            "send_page_view": True,
        },
        "event_flows": [
            {
                "requirement_id": "REQ-PAGE",
                "source_event": "page_view",
                "transported_event": "page_view",
                "server_consumer_keys": [server_tag_key],
            }
        ],
        "field_flows": [
            {
                "status": "proved",
                "source": {"path": "page_location", "shape": "scalar"},
                "wire": {"path": "page_location", "shape": "scalar"},
                "event_data": {"path": "page_location", "shape": "scalar"},
                "destination": {"path": "page_location", "shape": "scalar"},
                "requirement_ids": ["REQ-PAGE"],
                "claiming_client_proof": "Current GA Client common Event Data documentation",
                "receiver_owner": server_tag_key,
                "missing_behavior": "Use the standard Google tag page location",
                "runtime_verification_note": "Server Preview Event Data page_location matches the web request",
            }
        ],
        "consent_topology_ids": ["CONSENT-GA4"],
        "dedup_contract_ids": [],
        "operation_dependencies": [
            client_key,
            server_trigger_key,
            server_tag_key,
            consent_trigger_key,
        ],
    }
    if cutover:
        pipeline["cutover_operation_key"] = web_key
    return {
        "schema_version": "6.0",
        "mode": "pipeline",
        "route": "analytics",
        "scope": {"included": ["REQ-PAGE"], "reference_only": [], "excluded": []},
        "requirements": [
            {
                "id": "REQ-PAGE",
                "authority": {
                    "grade": "approved-input",
                    "locator": "Tracking Plan / page_view",
                },
                "event_name": "page_view",
                "source_event": "page_view",
                "parameters": {
                    "page_location": {
                        "source": "page_location",
                        "source_shape": "scalar:string",
                        "destination_shape": "scalar:string",
                        "provenance": {
                            "grade": "approved-input",
                            "locator": "Tracking Plan / page_view / page_location",
                        },
                    }
                },
            }
        ],
        "targets": [deepcopy(WEB_TARGET), deepcopy(SERVER_TARGET)],
        "pipelines": [pipeline],
        "consent_topologies": [
            {
                "consent_topology_id": "CONSENT-GA4",
                "destination": "GA4",
                "requirement_ids": ["REQ-PAGE"],
                "consent_mode": "strict-basic",
                "transport_behavior": "always-transported",
                "web_enforcement": {"mechanism": "transport-trigger-only"},
                "server_enforcement": {"mechanism": "incoming-google-consent-native"},
                "signal_authority": "google-consent-mode",
                "signal_source": "Google Consent Mode parameters",
                "unknown_state_behavior": "native-product-behavior",
                "event_coverage": ["page_view"],
                "intentional_double_gate": False,
                "server_tag_keys": [server_tag_key],
                "transporter_tag_keys": [web_key],
                "transporter_destination_vendor_block": False,
            }
        ],
        "dedup_contracts": [],
        "implementation": {
            "execution_mode": "isolated-durable",
            "objects": [
                web_action,
                {
                    "target_id": "server-main",
                    "resource_family": "client",
                    "name": "GA4 Client - Web transport",
                    "object_key": client_key,
                    "action": "reuse",
                    "requirement_ids": ["REQ-PAGE"],
                    "depends_on": [],
                    "justification": "Reuses the compatible default GA4 claiming Client",
                    "evidence": ["official-current", "container-confirmed"],
                    "risk": "routine",
                    "intended": {
                        "type": "ga4-client",
                        "claim_criteria": "Default GA4 Client claims GA4 collect requests",
                        "priority": 10,
                    },
                },
                {
                    "target_id": "server-main",
                    "resource_family": "tag",
                    "name": "GA4 - page_view",
                    "object_key": server_tag_key,
                    "action": "create",
                    "requirement_ids": ["REQ-PAGE"],
                    "depends_on": [client_key, server_trigger_key],
                    "justification": "Forwards the approved page_view from Event Data to GA4",
                    "evidence": ["approved-input", "official-current"],
                    "risk": "routine",
                    "intended": {
                        "type": "gaawc",
                        "event_name": "page_view",
                        "firingTriggerId": [server_trigger_key],
                        "blockingTriggerId": [],
                    },
                },
                {
                    "target_id": "web-main",
                    "resource_family": "trigger",
                    "name": "CMP - Analytics granted",
                    "object_key": consent_trigger_key,
                    "action": "create",
                    "requirement_ids": ["REQ-PAGE"],
                    "depends_on": [],
                    "justification": "Runs the baseline Google tag after CMP analytics grant",
                    "evidence": ["approved-input", "official-current"],
                    "risk": "routine",
                    "intended": {
                        "type": "customEvent",
                        "customEventFilter": "cmp_analytics_granted",
                    },
                },
                {
                    "target_id": "server-main",
                    "resource_family": "trigger",
                    "name": "Event Data - page_view",
                    "object_key": server_trigger_key,
                    "action": "create",
                    "requirement_ids": ["REQ-PAGE"],
                    "depends_on": [],
                    "justification": "Matches the transported page_view Event Data event",
                    "evidence": ["approved-input", "official-current"],
                    "risk": "routine",
                    "intended": {
                        "type": "customEvent",
                        "customEventFilter": "page_view",
                    },
                },
            ],
        },
        "execution_topologies": [
            {
                "tag_object_key": web_key,
                "requirement_ids": ["REQ-PAGE"],
                "lifecycle_role": "baseline-page-load",
                "normal_triggers": [
                    {
                        "trigger_object_key": consent_trigger_key,
                        "role": "cmp-readiness-grant",
                        "type": "custom-event",
                    }
                ],
                "consent_mode": "strict-basic",
                "consent_topology_ids": ["CONSENT-GA4"],
                "blocking_trigger_keys": [],
                "blocking_event_scope": None,
                "built_in_consent_checks": ["analytics_storage"],
                "additional_consent_checks": [],
                "firing_option": "once-per-event",
                "may_precede_cmp": False,
                "pre_cmp_policy": "not-applicable",
                "page_view_capable": True,
                "page_view_destinations": ["G-TEST123"],
                "ecommerce_route": "not-applicable",
                "manual_ecommerce_fields": [],
                "evidence": ["official-current", "container-confirmed"],
            }
        ],
        "page_view_decisions": [
            {
                "target_id": "web-main",
                "destination": "G-TEST123",
                "requirement_ids": ["REQ-PAGE"],
                "owner": "google-tag-automatic",
                "owner_object_key": web_key,
                "google_tag_object_key": web_key,
                "send_page_view": True,
                "external_dependency_ids": [],
                "reason": "The Google tag is the single approved page_view owner.",
                "evidence": ["approved-input", "official-current"],
            }
        ],
        "first_party_data_routes": [],
        "inventory_dispositions": [],
        "evidence": [
            {
                "grade": "official-current",
                "locator": "https://developers.google.com/tag-platform/tag-manager/server-side/send-data",
                "title": "Send data to server-side Tag Manager",
                "accessed_on": "2026-08-18",
                "supports": ["REQ-PAGE"],
            },
            {
                "grade": "container-confirmed",
                "locator": "Authorized web and server workspace readback",
            },
        ],
        "external_dependencies": [],
    }


def valid_web_contract() -> dict:
    contract = valid_pipeline_contract()
    web_key = "web-main::tag::Google tag - Web transport"
    block_trigger_key = "web-main::trigger::CMP - Analytics denied"
    contract["mode"] = "web"
    contract["targets"] = [deepcopy(WEB_TARGET)]
    contract["pipelines"] = []
    contract["implementation"]["objects"] = [
        item for item in contract["implementation"]["objects"] if item["target_id"] == "web-main"
    ]
    web_tag = next(
        item for item in contract["implementation"]["objects"] if item["object_key"] == web_key
    )
    web_tag["depends_on"].append(block_trigger_key)
    web_tag["intended"]["blockingTriggerId"] = [block_trigger_key]
    contract["implementation"]["objects"].append(
        {
            "target_id": "web-main",
            "resource_family": "trigger",
            "name": "CMP - Analytics denied",
            "object_key": block_trigger_key,
            "action": "create",
            "requirement_ids": ["REQ-PAGE"],
            "depends_on": [],
            "justification": "Blocks the direct analytics destination when the vendor is denied",
            "evidence": ["approved-input", "official-current"],
            "risk": "routine",
            "intended": {"type": "customEvent", "customEventFilter": ".*"},
        }
    )
    topology = contract["consent_topologies"][0]
    topology.update(
        {
            "transport_behavior": "blocked",
            "web_enforcement": {"mechanism": "cmp-lifecycle-plus-vendor-block"},
            "server_enforcement": {"mechanism": "none"},
            "signal_authority": "third-party-cmp",
            "signal_source": "CMP vendor grant and denial lifecycle",
            "unknown_state_behavior": "deny",
            "server_tag_keys": [],
            "transporter_tag_keys": [],
        }
    )
    contract["execution_topologies"][0]["blocking_trigger_keys"] = [block_trigger_key]
    contract["execution_topologies"][0]["blocking_event_scope"] = ".*"
    return contract


def valid_server_contract() -> dict:
    contract = valid_pipeline_contract()
    contract["mode"] = "server"
    contract["targets"] = [deepcopy(SERVER_TARGET)]
    contract["pipelines"] = []
    contract["consent_topologies"][0].update(
        {
            "web_enforcement": {"mechanism": "not-applicable"},
            "server_tag_keys": ["server-main::tag::GA4 - page_view"],
            "transporter_tag_keys": [],
        }
    )
    contract["implementation"]["objects"] = [
        item for item in contract["implementation"]["objects"] if item["target_id"] == "server-main"
    ]
    contract["execution_topologies"] = []
    contract["page_view_decisions"] = []
    return contract


def add_nonpurchase_dual_dedup(contract: dict) -> dict:
    value = deepcopy(contract)
    value["route"] = "combined"
    for requirement in value["requirements"]:
        requirement.setdefault("kind", "analytics")
    value["scope"]["included"].append("REQ-ATC")
    value["requirements"].append(
        {
            "id": "REQ-ATC",
            "authority": {
                "grade": "approved-input",
                "locator": "Media brief / Meta / add_to_cart",
            },
            "kind": "media",
            "destination": "Meta",
            "event_name": "add_to_cart",
            "source_event": "add_to_cart",
            "parameters": {},
        }
    )
    web_key = "web-main::tag::Google tag - Web transport"
    variable_key = "web-main::variable::CJS - Shared Event ID"
    event_trigger_key = "web-main::trigger::CE - add_to_cart"
    web_block_key = "web-main::trigger::Block - Meta denied"
    browser_key = "web-main::tag::Meta - add_to_cart"
    transporter_key = "web-main::tag::Transport - add_to_cart"
    server_trigger_key = "server-main::trigger::Event Data - add_to_cart"
    server_block_key = "server-main::trigger::Block - Meta denied"
    server_tag_key = "server-main::tag::Meta CAPI - add_to_cart"
    shared_reference = "{{CJS - Shared Event ID}}"
    value["implementation"]["objects"].extend(
        [
            {
                "target_id": "web-main",
                "resource_family": "variable",
                "name": "CJS - Shared Event ID",
                "object_key": variable_key,
                "action": "create",
                "requirement_ids": ["REQ-ATC"],
                "depends_on": [],
                "justification": "Provides one occurrence-scoped ID to both Meta delivery routes",
                "evidence": ["approved-input", "official-current"],
                "risk": "routine",
                "intended": {
                    "type": "cjs",
                    "code": (
                        "function(){var gtmData=window.google_tag_manager[{{Container ID}}]"
                        ".dataLayer.get('gtm');return gtmData.start+'.'+gtmData.uniqueEventId;}"
                    ),
                },
            },
            {
                "target_id": "web-main",
                "resource_family": "trigger",
                "name": "CE - add_to_cart",
                "object_key": event_trigger_key,
                "action": "create",
                "requirement_ids": ["REQ-ATC"],
                "depends_on": [],
                "justification": "Matches the approved add_to_cart source event",
                "evidence": ["approved-input", "official-current"],
                "risk": "routine",
                "intended": {"type": "customEvent", "customEventFilter": "add_to_cart"},
            },
            {
                "target_id": "web-main",
                "resource_family": "trigger",
                "name": "Block - Meta denied",
                "object_key": web_block_key,
                "action": "create",
                "requirement_ids": ["REQ-ATC"],
                "depends_on": [],
                "justification": "Blocks the browser Meta destination when its vendor is denied",
                "evidence": ["approved-input", "official-current"],
                "risk": "routine",
                "intended": {"type": "customEvent", "customEventFilter": ".*"},
            },
            {
                "target_id": "web-main",
                "resource_family": "tag",
                "name": "Meta - add_to_cart",
                "object_key": browser_key,
                "action": "create",
                "requirement_ids": ["REQ-ATC"],
                "depends_on": [event_trigger_key, web_block_key, variable_key],
                "justification": "Sends the approved browser Meta event with the shared ID",
                "evidence": ["approved-input", "official-current"],
                "risk": "routine",
                "intended": {
                    "type": "meta-pixel",
                    "event_name": "AddToCart",
                    "event_id": shared_reference,
                    "firingTriggerId": [event_trigger_key],
                    "blockingTriggerId": [web_block_key],
                },
            },
            {
                "target_id": "web-main",
                "resource_family": "tag",
                "name": "Transport - add_to_cart",
                "object_key": transporter_key,
                "action": "create",
                "requirement_ids": ["REQ-ATC"],
                "depends_on": [web_key, event_trigger_key, variable_key],
                "justification": "Transports the same occurrence ID and CMP signal to sGTM",
                "evidence": ["approved-input", "official-current"],
                "risk": "routine",
                "intended": {
                    "type": "gaawe",
                    "event_name": "add_to_cart",
                    "event_id": shared_reference,
                    "cmp_meta_allowed": "{{DLV - consent.meta_allowed}}",
                    "firingTriggerId": [event_trigger_key],
                    "blockingTriggerId": [],
                },
            },
            {
                "target_id": "server-main",
                "resource_family": "trigger",
                "name": "Event Data - add_to_cart",
                "object_key": server_trigger_key,
                "action": "create",
                "requirement_ids": ["REQ-ATC"],
                "depends_on": [],
                "justification": "Matches transported add_to_cart Event Data",
                "evidence": ["approved-input", "official-current"],
                "risk": "routine",
                "intended": {"type": "customEvent", "customEventFilter": "add_to_cart"},
            },
            {
                "target_id": "server-main",
                "resource_family": "trigger",
                "name": "Block - Meta denied",
                "object_key": server_block_key,
                "action": "create",
                "requirement_ids": ["REQ-ATC"],
                "depends_on": [],
                "justification": "Denies missing, false, or unknown Meta vendor state",
                "evidence": ["approved-input", "official-current"],
                "risk": "routine",
                "intended": {
                    "type": "customEvent",
                    "customEventFilter": "cmp_meta_allowed=false|undefined|unknown",
                },
            },
            {
                "target_id": "server-main",
                "resource_family": "tag",
                "name": "Meta CAPI - add_to_cart",
                "object_key": server_tag_key,
                "action": "create",
                "requirement_ids": ["REQ-ATC"],
                "depends_on": [server_trigger_key, server_block_key],
                "justification": "Sends the approved server Meta event with the transported ID",
                "evidence": ["approved-input", "official-current"],
                "risk": "routine",
                "intended": {
                    "type": "meta-capi",
                    "event_name": "AddToCart",
                    "event_id": "{{Event Data - event_id}}",
                    "firingTriggerId": [server_trigger_key],
                    "blockingTriggerId": [server_block_key],
                },
            },
        ]
    )
    value["pipelines"][0]["event_flows"].append(
        {
            "requirement_id": "REQ-ATC",
            "source_event": "add_to_cart",
            "transported_event": "add_to_cart",
            "server_consumer_keys": [server_tag_key],
        }
    )
    for path in ("event_id", "cmp_meta_allowed"):
        value["pipelines"][0]["field_flows"].append(
            {
                "status": "proved",
                "requirement_ids": ["REQ-ATC"],
                "source": {"path": path, "shape": "scalar"},
                "wire": {"path": path, "shape": "scalar"},
                "event_data": {"path": path, "shape": "scalar"},
                "destination": {"path": path, "shape": "scalar"},
                "claiming_client_proof": "Current GA Client common Event Data documentation",
                "receiver_owner": server_tag_key,
                "missing_behavior": "Block the affected destination occurrence",
                "runtime_verification_note": f"Server Preview Event Data {path} matches the web request",
            }
        )
    value["consent_topologies"].extend(
        [
            {
                "consent_topology_id": "CONSENT-META-SERVER",
                "destination": "Meta CAPI",
                "requirement_ids": ["REQ-ATC"],
                "consent_mode": "strict-basic",
                "transport_behavior": "always-transported",
                "web_enforcement": {"mechanism": "transport-trigger-only"},
                "server_enforcement": {
                    "mechanism": "server-blocking-trigger",
                    "blocking_trigger_key": server_block_key,
                },
                "signal_authority": "third-party-cmp",
                "signal_source": "Documented CMP Meta vendor state",
                "server_signal_path": "cmp_meta_allowed",
                "unknown_state_behavior": "deny",
                "event_coverage": ["add_to_cart"],
                "intentional_double_gate": False,
                "server_tag_keys": [server_tag_key],
                "transporter_tag_keys": [web_key, transporter_key],
                "transporter_destination_vendor_block": False,
            },
            {
                "consent_topology_id": "CONSENT-META-BROWSER",
                "destination": "Meta browser",
                "requirement_ids": ["REQ-ATC"],
                "consent_mode": "strict-basic",
                "transport_behavior": "blocked",
                "web_enforcement": {"mechanism": "business-trigger-plus-vendor-block"},
                "server_enforcement": {"mechanism": "none"},
                "signal_authority": "third-party-cmp",
                "signal_source": "Documented CMP Meta vendor state",
                "unknown_state_behavior": "deny",
                "event_coverage": ["add_to_cart"],
                "intentional_double_gate": False,
                "server_tag_keys": [],
                "transporter_tag_keys": [],
                "transporter_destination_vendor_block": False,
            },
        ]
    )
    value["pipelines"][0]["consent_topology_ids"].append("CONSENT-META-SERVER")
    value["pipelines"][0]["operation_dependencies"].extend(
        [server_trigger_key, server_block_key, server_tag_key]
    )
    dedup = {
        "dedup_contract_id": "DEDUP-META-ATC",
        "requirement_id": "REQ-ATC",
        "event_name": "add_to_cart",
        "destination": "Meta",
        "strategy": "dual-shared-id",
        "source_type": "gtm-event-scoped-fallback",
        "source_reference": "{{CJS - Shared Event ID}}",
        "source_variable_key": variable_key,
        "browser_reference": "{{CJS - Shared Event ID}}",
        "transporter_reference": "{{CJS - Shared Event ID}}",
        "browser_consumer_keys": [browser_key],
        "transporter_consumer_keys": [transporter_key],
        "transported_parameter": "event_id",
        "server_event_data_path": "event_id",
        "server_generates_id": False,
        "same_gtm_event": True,
        "runtime_verification_note": "Both requests expose the same defined ID for one add_to_cart",
        "browser_field": "eventID",
        "server_field": "event_id",
        "occurrence_scope": "one add_to_cart dataLayer event",
        "companion_fields": ["event_name", "pixel_id"],
        "compatibility_classification": "guarded-internal-gtm-model",
    }
    value["dedup_contracts"] = [dedup]
    value["pipelines"][0]["dedup_contract_ids"] = ["DEDUP-META-ATC"]
    value["execution_topologies"].extend(
        [
            {
                "tag_object_key": browser_key,
                "requirement_ids": ["REQ-ATC"],
                "lifecycle_role": "event-driven",
                "normal_triggers": [
                    {
                        "trigger_object_key": event_trigger_key,
                        "role": "source-event",
                        "type": "custom-event",
                    }
                ],
                "consent_mode": "strict-basic",
                "consent_topology_ids": ["CONSENT-META-BROWSER"],
                "blocking_trigger_keys": [web_block_key],
                "blocking_event_scope": ".*",
                "built_in_consent_checks": ["ad_storage"],
                "additional_consent_checks": [],
                "firing_option": "once-per-event",
                "may_precede_cmp": False,
                "pre_cmp_policy": "not-applicable",
                "page_view_capable": False,
                "page_view_destinations": [],
                "ecommerce_route": "manual",
                "manual_ecommerce_fields": [],
                "evidence": ["official-current", "container-confirmed"],
            },
            {
                "tag_object_key": transporter_key,
                "requirement_ids": ["REQ-ATC"],
                "lifecycle_role": "event-driven",
                "normal_triggers": [
                    {
                        "trigger_object_key": event_trigger_key,
                        "role": "source-event",
                        "type": "custom-event",
                    }
                ],
                "consent_mode": "strict-basic",
                "consent_topology_ids": ["CONSENT-META-SERVER"],
                "blocking_trigger_keys": [],
                "blocking_event_scope": None,
                "built_in_consent_checks": [],
                "additional_consent_checks": [],
                "firing_option": "once-per-event",
                "may_precede_cmp": False,
                "pre_cmp_policy": "not-applicable",
                "page_view_capable": False,
                "page_view_destinations": [],
                "ecommerce_route": "manual",
                "manual_ecommerce_fields": [],
                "evidence": ["official-current", "container-confirmed"],
            },
        ]
    )
    for evidence in value["evidence"]:
        if evidence.get("grade") == "official-current":
            evidence.setdefault("supports", []).append("REQ-ATC")
    return value
