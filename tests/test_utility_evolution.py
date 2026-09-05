from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import run_state  # noqa: E402
from check_release import check_git_state  # noqa: E402
from configuration_run import (  # noqa: E402
    RunValidationError,
    checkpoint_operation,
    create_from_contract,
    inspect_document,
)
from current_support import (  # noqa: E402
    approve_mutations,
    complete_capture_evidence,
    valid_pipeline_contract,
    valid_server_contract,
    valid_web_contract,
    with_complete_baselines,
)
from diff_object_graph import differences  # noqa: E402
from event_semantics import trigger_accepts_event  # noqa: E402
from import_ga4_tracking_plan_handoff import HandoffError, verify_delivery  # noqa: E402
from run_validation_core import validate_document as validate_run  # noqa: E402
from validate_configuration_contract import ContractValidationError, validate_document  # noqa: E402
from verification import build_pre_write_comparison  # noqa: E402


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
    contract["implementation"]["field_bindings"] = [
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
            {"type": "customEvent", "customEventFilter": "purchase"},
            [],
        ),
        (
            "server-main",
            "trigger",
            "Purchase",
            server_trigger_key,
            {"type": "customEvent", "customEventFilter": "purchase"},
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


class UtilityEvolutionTest(unittest.TestCase):
    def test_prior_page_browser_user_data_requires_native_form_submission(self):
        contract = ads_transport_contract()
        route = contract["first_party_data_routes"][0]
        route.update(
            feature="google-ads-user-provided-data-event",
            timing="prior-page",
        )
        route.pop("server_consumer_object_keys")
        sender = next(
            item
            for item in contract["implementation"]["objects"]
            if item["object_key"] == route["consumer_object_keys"][0]
        )
        sender["intended"]["type"] = "Google Ads User-Provided Data Event"
        route["consumer_bindings"][0].update(
            product="google-ads", tag_type="Google Ads User-Provided Data Event"
        )
        approve_mutations(contract)
        with self.assertRaisesRegex(ContractValidationError, "gtm.formSubmit source event"):
            validate_document(contract)

    def test_trigger_notes_do_not_establish_event_coverage(self):
        contract = valid_server_contract()
        trigger = next(
            item
            for item in contract["implementation"]["objects"]
            if item["resource_family"] == "trigger"
        )
        trigger["intended"] = {
            "type": "customEvent",
            "customEventFilter": [condition("equals", "purchase")],
            "notes": "page_view",
        }
        approve_mutations(contract)
        with self.assertRaisesRegex(ContractValidationError, "no firing trigger"):
            validate_document(contract)

    def test_trigger_operators_case_and_negation_are_respected(self):
        cases = [
            (condition("equals", "purchase"), "purchase", True),
            (condition("equals", ".*"), "purchase", False),
            (condition("equals", "purchase", negate="true"), "purchase", False),
            (condition("matchRegex", "^purchase$", ignore_case="true"), "PURCHASE", True),
            (condition("matchRegex", "^purchase$"), "PURCHASE", False),
            (condition("matchRegex", "["), "purchase", False),
        ]
        for selector, name, expected in cases:
            with self.subTest(selector=selector, name=name):
                self.assertEqual(
                    trigger_accepts_event({"customEventFilter": [selector]}, name), expected
                )

    def test_saved_ga4_event_must_match_approved_event(self):
        contract = valid_server_contract()
        tag = next(
            item
            for item in contract["implementation"]["objects"]
            if item["resource_family"] == "tag"
        )
        tag["intended"]["event_name"] = "purchase"
        approve_mutations(contract)
        with self.assertRaisesRegex(ContractValidationError, "differs from approved"):
            validate_document(contract)

    def test_valid_raw_rest_event_selector_materializes(self):
        contract = valid_server_contract()
        trigger = next(
            item
            for item in contract["implementation"]["objects"]
            if item["resource_family"] == "trigger"
        )
        trigger["intended"]["customEventFilter"] = [condition("equals", "page_view")]
        approve_mutations(contract)
        self.assertEqual(
            create_from_contract(contract, run_id="RAW", source_locator="synthetic")["run"]["mode"],
            "server",
        )

    def test_nested_types_zero_and_identifiers_are_preserved(self):
        data = [{"item_id": "001", "price": 0, "quantity": 1}, {"item_id": "002", "price": 8}]
        self.assertFalse(differences(data, deepcopy(data)))
        for mutation in [{"item_id": 1}, {"price": False}, {"quantity": True}]:
            changed = deepcopy(data)
            changed[0].update(mutation)
            self.assertTrue(differences(data, changed))
        self.assertTrue(differences(data, data[:1]))

    def test_prewrite_ignores_only_root_metadata(self):
        operation = {
            "operation_id": "OP",
            "target_id": "web",
            "name": "Tag",
            "pre_change": {"name": "Tag", "fields": {"value": 1}},
        }
        self.assertTrue(
            build_pre_write_comparison(
                operation, {"name": "Tag", "tagId": "1", "fields": {"value": 1}}
            )[0]["pass"]
        )
        self.assertFalse(
            build_pre_write_comparison(operation, {"name": "Tag", "fields": {"value": True}})[0][
                "pass"
            ]
        )
        self.assertFalse(
            build_pre_write_comparison(
                operation, {"name": "Tag", "fields": {"value": 1, "path": "changed-business-path"}}
            )[0]["pass"]
        )

    def test_current_handoff_accepts_multiple_event_schemas_not_legacy_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifacts = []
            for name, role in [
                ("plan.json", "canonical_tracking_plan"),
                ("lead.json", "event_push_schema"),
                ("purchase.json", "event_push_schema"),
            ]:
                path = root / name
                path.write_text("{}", encoding="utf-8")
                artifacts.append(
                    {
                        "path": name,
                        "role": role,
                        "bytes": 2,
                        "sha256": hashlib.sha256(b"{}").hexdigest(),
                    }
                )
            handoff = {
                "handoff_version": "1.1.0",
                "skill": {"name": "ga4-tracking-plan"},
                "approval": {"state": "approved"},
                "artifacts": artifacts,
                "plan": {"canonical_sha256": artifacts[0]["sha256"]},
            }
            (root / "handoff.json").write_text(json.dumps(handoff), encoding="utf-8")
            self.assertEqual(verify_delivery(root)[1], {})
            handoff["handoff_version"] = "1.0.0"
            (root / "handoff.json").write_text(json.dumps(handoff), encoding="utf-8")
            with self.assertRaises(HandoffError):
                verify_delivery(root)

    def test_ads_only_event_transport_materializes_without_ga4_matching_activation(self):
        contract = ads_transport_contract()
        run = create_from_contract(contract, run_id="ADS", source_locator="synthetic")
        self.assertEqual(
            run["first_party_data_routes"][0]["feature"], "google-ads-server-user-data-transport"
        )

    def test_ads_tag_wide_google_owner_retains_server_receiver_proof(self):
        contract = ads_transport_contract()
        web_key = "web-main::tag::Google tag - Web transport"
        web_tag = next(
            item for item in contract["implementation"]["objects"] if item["object_key"] == web_key
        )
        web_tag["requirement_ids"].append("REQ-ADS")
        web_tag["intended"]["user_data"] = "{{UPD - Approved purchase}}"
        original_sender = next(
            item
            for item in contract["implementation"]["objects"]
            if item["object_key"] == "web-main::tag::Ads identity sender"
        )
        original_sender["intended"].pop("user_data")
        topology = next(
            item for item in contract["execution_topologies"] if item["tag_object_key"] == web_key
        )
        topology["requirement_ids"].append("REQ-ADS")
        contract["consent_topologies"][0]["requirement_ids"].append("REQ-ADS")
        contract["consent_topologies"][0]["event_coverage"].append("purchase")
        route = contract["first_party_data_routes"][0]
        route.update(timing="tag-wide", consumer_object_keys=[web_key])
        route["consumer_bindings"][0].update(object_key=web_key, tag_type="googtag")
        receiver = next(
            item
            for item in contract["implementation"]["objects"]
            if item["object_key"] == "server-main::tag::Ads conversion"
        )
        receiver["intended"]["type"] = "Google Ads Conversion Tracking"

        run = create_from_contract(
            approve_mutations(contract), run_id="ADS-TAG-WIDE", source_locator="synthetic"
        )

        self.assertEqual(
            run["first_party_data_routes"][0]["server_consumer_object_keys"],
            ["server-main::tag::Ads conversion"],
        )

    def test_prior_page_server_user_provided_data_event_route_materializes(self):
        contract = ads_transport_contract()
        requirement = next(item for item in contract["requirements"] if item["id"] == "REQ-ADS")
        requirement.update(event_name="form_submit", source_event="form_submit")
        for item in contract["implementation"]["objects"]:
            if item.get("requirement_ids") != ["REQ-ADS"]:
                continue
            intended = item.get("intended", {})
            if intended.get("customEventFilter") == "purchase":
                intended["customEventFilter"] = "form_submit"
            if intended.get("event_name") == "purchase":
                intended["event_name"] = "form_submit"
        ads_flow = next(
            item
            for item in contract["pipelines"][0]["event_flows"]
            if item["requirement_id"] == "REQ-ADS"
        )
        ads_flow.update(source_event="form_submit", transported_event="form_submit")
        for consent in contract["consent_topologies"]:
            if "REQ-ADS" in consent["requirement_ids"]:
                consent["event_coverage"] = [
                    "form_submit" if event == "purchase" else event
                    for event in consent["event_coverage"]
                ]
        route = contract["first_party_data_routes"][0]
        route.update(
            feature="google-ads-server-user-provided-data-event",
            timing="prior-page",
        )
        receiver = next(
            item
            for item in contract["implementation"]["objects"]
            if item["object_key"] == "server-main::tag::Ads conversion"
        )
        receiver["intended"]["type"] = "Google Ads User-provided Data Event"

        run = create_from_contract(
            approve_mutations(contract), run_id="ADS-UPD-SERVER", source_locator="synthetic"
        )

        self.assertEqual(
            run["first_party_data_routes"][0]["feature"],
            "google-ads-server-user-provided-data-event",
        )
        sender = next(
            item
            for item in contract["implementation"]["objects"]
            if item["object_key"] == route["consumer_object_keys"][0]
        )
        sender["intended"]["firingTriggerId"] = ["web-main::trigger::CMP - Analytics granted"]
        topology = next(
            item
            for item in contract["execution_topologies"]
            if item["tag_object_key"] == sender["object_key"]
        )
        topology["normal_triggers"][0]["trigger_object_key"] = sender["intended"][
            "firingTriggerId"
        ][0]
        with self.assertRaisesRegex(
            ContractValidationError, "must resolve on its approved source event"
        ):
            validate_document(approve_mutations(contract))

    def test_ads_transport_rejects_unproved_and_unauthorized_receivers(self):
        for mutation in ("missing-flow", "wrong-receiver", "wrong-type", "no-ad-user-data"):
            contract = ads_transport_contract()
            if mutation == "missing-flow":
                contract["pipelines"][0]["field_flows"].pop()
            elif mutation == "wrong-receiver":
                contract["first_party_data_routes"][0]["server_consumer_object_keys"] = [
                    "server-main::tag::GA4 - page_view"
                ]
            elif mutation == "wrong-type":
                contract["pipelines"][0]["field_flows"][-1]["wire"]["shape"] = "array"
            else:
                contract["first_party_data_routes"][0]["consent_types"] = []
            with self.subTest(mutation=mutation), self.assertRaises(ContractValidationError):
                validate_document(contract)

    def test_correct_automatic_page_view_owner_remains_valid(self):
        self.assertEqual(
            validate_document(valid_web_contract())["page_view_decisions"][0]["owner"],
            "google-tag-automatic",
        )

    def test_execution_needs_a_complete_relevant_baseline(self):
        run = create_from_contract(
            valid_web_contract(), run_id="BASELINE", source_locator="synthetic"
        )
        self.assertEqual(inspect_document(run)["ready_operations"], [])
        with self.assertRaisesRegex(RunValidationError, "baseline"):
            checkpoint_operation(
                run,
                operation_id=run["object_changes"][1]["operation_id"],
                state="in_progress",
                note="synthetic",
            )
        with self.assertRaisesRegex(RunValidationError, "resource families"):
            resources = {"folder": []}
            run_state._record_target_baseline(
                run,
                target_id="web-main",
                resources=resources,
                captured_at="2026-09-05",
                preexisting_workspace_changes=[],
                capture_evidence=complete_capture_evidence(resources, run["run"]["targets"][0]),
            )
        self.assertTrue(inspect_document(with_complete_baselines(run))["ready_operations"])

    def test_skipped_work_cannot_release_dependencies_or_complete(self):
        run = with_complete_baselines(
            create_from_contract(valid_web_contract(), run_id="SKIP", source_locator="synthetic")
        )
        trigger = next(
            item for item in run["object_changes"] if item["resource_family"] == "trigger"
        )
        run = checkpoint_operation(
            run, operation_id=trigger["operation_id"], state="skipped", note="Not implemented"
        )
        tag = next(item for item in run["object_changes"] if item["resource_family"] == "tag")
        self.assertIn(tag["operation_id"], inspect_document(run)["blocked_operations"])
        for operation in list(run["object_changes"]):
            if operation["state"] == "planned":
                run = checkpoint_operation(
                    run,
                    operation_id=operation["operation_id"],
                    state="skipped",
                    note="Not implemented",
                )
        with self.assertRaisesRegex(RunValidationError, "incomplete"):
            run_state._finalize_adapter_verified_document(run)

    def test_unknown_materialization_and_forged_completion_are_rejected(self):
        run = create_from_contract(valid_web_contract(), run_id="FORGE", source_locator="synthetic")
        run["run"]["materialization"]["method"] = "arbitrary-method"
        with self.assertRaisesRegex(RunValidationError, "materialization"):
            validate_run(run)
        run = create_from_contract(valid_web_contract(), run_id="FORGE", source_locator="synthetic")
        run["run"]["status"] = "Configured"
        with self.assertRaisesRegex(RunValidationError, "Configured"):
            validate_run(run)

    def test_basic_cannot_mean_always_on_google_native_transport(self):
        contract = valid_pipeline_contract()
        contract["consent_topologies"][0]["consent_mode"] = "strict-basic"
        contract["execution_topologies"][0]["consent_mode"] = "strict-basic"
        with self.assertRaisesRegex(ContractValidationError, "strict-basic cannot"):
            validate_document(contract)
        self.assertEqual(
            validate_document(valid_pipeline_contract())["consent_topologies"][0]["consent_mode"],
            "advanced-native",
        )

    def test_field_bindings_cannot_rewrite_approved_sources(self):
        contract = ads_transport_contract()
        contract["implementation"]["field_bindings"][0]["source"] = "unapproved.path"
        with self.assertRaisesRegex(ContractValidationError, "unexpected fields"):
            validate_document(contract)

    def test_explicit_basic_blocked_transport_remains_feasible(self):
        contract = valid_pipeline_contract()
        web = valid_web_contract()
        block = deepcopy(web["implementation"]["objects"][-1])
        contract["implementation"]["objects"].append(block)
        sender = contract["implementation"]["objects"][0]
        sender["intended"]["blockingTriggerId"] = [block["object_key"]]
        sender["depends_on"].append(block["object_key"])
        topology = contract["consent_topologies"][0]
        topology.update(
            consent_mode="strict-basic",
            transport_behavior="blocked",
            web_enforcement={"mechanism": "cmp-lifecycle-plus-vendor-block"},
            transporter_destination_vendor_block=True,
            intentional_double_gate=False,
        )
        topology.pop("double_gate_justification", None)
        execution = contract["execution_topologies"][0]
        execution.update(
            consent_mode="strict-basic",
            blocking_trigger_keys=[block["object_key"]],
            blocking_event_scope=".*",
        )
        approve_mutations(contract)
        run = create_from_contract(
            contract, run_id="BASIC", source_locator="synthetic explicit basic authority"
        )
        self.assertEqual(run["consent_topologies"][0]["consent_mode"], "strict-basic")

    def test_authentication_failure_stops_the_target(self):
        run = with_complete_baselines(
            create_from_contract(valid_web_contract(), run_id="AUTH", source_locator="synthetic")
        )
        operation_id = inspect_document(run)["ready_operations"][0]
        run = checkpoint_operation(
            run,
            operation_id=operation_id,
            state="failed",
            note="Target reauthentication needed",
            error="authentication_required: synthetic",
        )
        self.assertEqual(inspect_document(run)["ready_operations"], [])

    def test_direct_checkpoint_cannot_bypass_dependencies(self):
        run = with_complete_baselines(
            create_from_contract(valid_web_contract(), run_id="ORDER", source_locator="synthetic")
        )
        consumer = next(item for item in run["object_changes"] if item["dependencies"])
        with self.assertRaisesRegex(RunValidationError, "every dependency"):
            checkpoint_operation(
                run, operation_id=consumer["operation_id"], state="in_progress", note="Too early"
            )

    def test_all_skipped_reports_deferred_not_progress(self):
        run = with_complete_baselines(
            create_from_contract(valid_web_contract(), run_id="DEFER", source_locator="synthetic")
        )
        for operation in run["object_changes"]:
            run = checkpoint_operation(
                run, operation_id=operation["operation_id"], state="skipped", note="Not implemented"
            )
        self.assertEqual(run["run"]["status"], "Deferred")

    def test_git_failure_is_not_a_clean_release(self):
        with patch("check_release.subprocess.run") as command:
            command.return_value = subprocess.CompletedProcess(
                ["git"], 128, "", "synthetic failure"
            )
            errors = check_git_state(tag="v10.0.0", require_tag=True, require_clean=True)
        self.assertEqual(len(errors), 2)
        self.assertTrue(all("git exited 128" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
