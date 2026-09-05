from __future__ import annotations

import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import run_validation_web as web  # noqa: E402
from adapter_runtime import AdapterExecutionError, TargetAdapterRegistry  # noqa: E402
from configuration_run import create_from_contract  # noqa: E402
from current_support import (  # noqa: E402
    approve_mutations,
    complete_capture_evidence,
    valid_pipeline_contract,
    valid_server_contract,
    valid_web_contract,
)
from diff_object_graph import GraphError, normalize_graph  # noqa: E402
from import_ga4_tracking_plan_handoff import normalized_approved_semantics  # noqa: E402
from redaction import (  # noqa: E402
    REDACTED_STATE,
    redact_for_persistence,
    redacted_marker,
    scrub_sensitive_text,
    sensitive_paths,
)
from run_state import _record_target_baseline  # noqa: E402
from validate_configuration_contract import (  # noqa: E402
    ContractValidationError,
    validate_document,
)
from verification import build_pre_write_comparison  # noqa: E402


class ReleaseFieldGatesTest(unittest.TestCase):
    def test_mutations_require_approved_requirement_authority(self):
        for mutation in ("no-requirement", "official-only", "payload-drift", "wrong-locator"):
            contract = valid_web_contract()
            operation = contract["implementation"]["objects"][0]
            if mutation == "no-requirement":
                operation["requirement_ids"] = []
            elif mutation == "official-only":
                operation["evidence"] = ["official-current"]
            else:
                if mutation == "payload-drift":
                    operation["intended"]["name"] = "Unapproved payload change"
                else:
                    operation["approval"]["locator"] = "Unlinked approval source"
            with self.subTest(mutation=mutation), self.assertRaises(ContractValidationError):
                validate_document(contract)

    def test_new_official_host_is_not_a_skill_release_dependency(self) -> None:
        # Isolate locator acceptance; this does not certify a Mixpanel configuration
        # or assert that its guide establishes Google product mechanics.
        contract = valid_web_contract()
        evidence = next(
            item for item in contract["evidence"] if item["grade"] == "official-current"
        )
        evidence.update(
            locator="https://docs.mixpanel.com/docs/tracking-methods/integrations/google-tag-manager",
            title="Google Tag Manager - Mixpanel",
            decision="Official template initialization and SDK integration; applicability remains source review",
        )
        validate_document(contract)

    def test_official_evidence_requires_authoritative_current_locator(self):
        for locator, accessed_on in (
            ("http://developers.google.com/tag-platform", "2026-09-05"),
            ("https:///missing-host", "2026-09-05"),
            ("https://reviewer:example@developers.google.com/tag-platform", "2026-09-05"),
            (
                "https://developers.google.com/tag-platform/tag-manager/datalayer",
                "2099-12-31",
            ),
            (
                "https://developers.google.com/tag-platform/tag-manager/datalayer",
                "2020-01-01",
            ),
        ):
            contract = valid_web_contract()
            evidence = next(
                item for item in contract["evidence"] if item["grade"] == "official-current"
            )
            evidence.update(locator=locator, accessed_on=accessed_on)
            with (
                self.subTest(locator=locator, accessed_on=accessed_on),
                self.assertRaises(ContractValidationError),
            ):
                validate_document(contract)

    def test_first_party_configuration_requires_an_explicit_route(self):
        for raw_parameter_row in (False, True):
            contract = valid_web_contract()
            google_tag = next(
                item
                for item in contract["implementation"]["objects"]
                if item["resource_family"] == "tag"
            )
            if raw_parameter_row:
                google_tag["intended"]["parameter"] = [
                    {
                        "key": "user_data",
                        "type": "template",
                        "value": "{{UPD - Unauthorized}}",
                    }
                ]
            else:
                google_tag["intended"]["user_data"] = "{{UPD - Unauthorized}}"
            contract["implementation"]["objects"].append(
                {
                    "target_id": "web-main",
                    "resource_family": "variable",
                    "name": "UPD - Unauthorized",
                    "object_key": "web-main::variable::UPD - Unauthorized",
                    "action": "create",
                    "requirement_ids": ["REQ-PAGE"],
                    "depends_on": [],
                    "justification": "Adversarial unauthorized first-party data",
                    "evidence": ["approved-input", "official-current"],
                    "risk": "routine",
                    "intended": {
                        "type": "User-Provided Data Variable",
                        "email": "{{DLV - customer.email}}",
                    },
                }
            )
            approve_mutations(contract)
            with (
                self.subTest(raw_parameter_row=raw_parameter_row),
                self.assertRaisesRegex(ContractValidationError, "first-party user data"),
            ):
                validate_document(contract)

    def test_shared_configuration_settings_require_complete_consumer_closure(self):
        contract = valid_web_contract()
        contract["implementation"]["objects"].append(
            {
                "target_id": "web-main",
                "resource_family": "variable",
                "name": "Google Settings",
                "object_key": "web-main::variable::Google Settings",
                "action": "update",
                "object_id": "variable-7",
                "requirement_ids": ["REQ-PAGE"],
                "depends_on": [],
                "justification": "Update shared Google settings",
                "evidence": ["approved-input", "official-current", "container-confirmed"],
                "risk": "high-impact",
                "pre_change": {"type": "gtcs", "send_page_view": True},
                "intended": {"type": "gtcs", "send_page_view": False},
            }
        )
        approve_mutations(contract)
        run = create_from_contract(contract, run_id="SETTINGS-CLOSURE", source_locator="approved")
        resources = {
            "tag": [
                {
                    "name": "Unrelated Google tag",
                    "type": "googtag",
                    "configSettingsVariable": "{{Google Settings}}",
                }
            ],
            "trigger": [],
            "variable": [{"name": "Google Settings", "type": "gtcs", "send_page_view": True}],
        }
        with self.assertRaisesRegex(
            web.RunValidationError, "does not include every authenticated baseline consumer"
        ):
            _record_target_baseline(
                run,
                target_id="web-main",
                resources=resources,
                captured_at="2026-09-05T00:00:00Z",
                preexisting_workspace_changes=[],
                capture_evidence=complete_capture_evidence(resources, run["run"]["targets"][0]),
            )

    def test_adapter_registration_requires_authenticated_target_identity(self) -> None:
        class WrongTargetAdapter:
            def identity(self):
                return {
                    "account_id": "wrong-account",
                    "container_id": "wrong-container",
                    "workspace_id": "wrong-workspace",
                    "container_type": "web",
                }

            def read(self, operation):
                return None

            def mutate(self, operation):
                return None

        target = valid_web_contract()["targets"][0]
        with self.assertRaisesRegex(AdapterExecutionError, "differs from the authorized"):
            TargetAdapterRegistry().register(target, WrongTargetAdapter(), {})

    def test_every_included_requirement_needs_an_implementation_object(self) -> None:
        contract = valid_web_contract()
        orphan = deepcopy(contract["requirements"][0])
        orphan.update(id="REQ-ORPHAN", event_name="generate_lead", source_event="lead_success")
        contract["requirements"].append(orphan)
        contract["scope"]["included"].append("REQ-ORPHAN")
        with self.assertRaisesRegex(ContractValidationError, "missing=.*REQ-ORPHAN"):
            validate_document(contract)

    def test_pause_requires_authority_and_paused_true(self) -> None:
        contract = valid_web_contract()
        tag = contract["implementation"]["objects"][0]
        tag.update(
            action="pause",
            object_id="100",
            pre_change=deepcopy(tag["intended"]),
            risk="high-impact",
        )
        tag["evidence"].append("container-confirmed")
        tag["intended"]["paused"] = False
        contract["execution_topologies"] = []
        contract["page_view_decisions"] = []
        approve_mutations(contract)
        with self.assertRaisesRegex(ContractValidationError, "intended.paused must be true"):
            validate_document(contract)

    def test_secret_reference_drift_and_embedded_authorization_fail_closed(self) -> None:
        operation = {
            "operation_id": "OP-1",
            "target_id": "server-main",
            "name": "Vendor",
            "pre_change": {
                "name": "Vendor",
                "token": redacted_marker(reference="vault://vendor/v1"),
            },
        }
        comparison, _ = build_pre_write_comparison(
            operation,
            {
                "name": "Vendor",
                "token": redacted_marker(reference="vault://vendor/v2"),
            },
        )
        self.assertFalse(comparison["pass"])
        message = "HTTP 401 Authorization: Bearer TEST_CREDENTIAL_123456 rejected"
        self.assertNotIn("TEST_CREDENTIAL_123456", scrub_sensitive_text(message, set()))
        cleaned = redact_for_persistence(
            {
                "secret_state": REDACTED_STATE,
                "reference": "vault://vendor/v1",
                "unexpected": "must-not-survive",
            }
        )
        self.assertEqual(cleaned, redacted_marker(reference="vault://vendor/v1"))
        with self.assertRaisesRegex(Exception, "opaque"):
            redacted_marker(reference="Bearer ABCDEFGHIJKLMNOP")

    def test_native_nested_send_page_view_and_constant_destination_resolve(self) -> None:
        target = {
            "type": "googtag",
            "tagId": "{{GA4 ID}}",
            "parameter": [
                {
                    "type": "list",
                    "key": "configSettingsTable",
                    "list": [
                        {
                            "type": "map",
                            "map": [
                                {
                                    "type": "template",
                                    "key": "parameter",
                                    "value": "send_page_view",
                                },
                                {
                                    "type": "template",
                                    "key": "parameterValue",
                                    "value": "false",
                                },
                            ],
                        }
                    ],
                }
            ],
        }
        operations = {
            "OP-CONSTANT": {
                "operation_id": "OP-CONSTANT",
                "object_type": "variable",
                "name": "GA4 ID",
                "action": "create",
                "intended": {"type": "c", "value": "G-TEST123"},
            }
        }
        self.assertFalse(web._send_page_view_value(target, "$.tag"))
        web._validate_google_destination(target, "G-TEST123", "$.tag", operations)

    def test_google_configuration_settings_variable_is_resolved(self) -> None:
        settings_key = "web-main::variable::Google configuration settings"
        operations = {
            settings_key: {
                "object_key": settings_key,
                "resource_family": "variable",
                "name": "Google configuration settings",
                "action": "create",
                "intended": {
                    "type": "googtag_config_settings",
                    "parameters": {
                        "send_page_view": False,
                        "server_container_url": "https://tags.example.test",
                    },
                },
            }
        }
        tag_operation = {
            "object_key": "web-main::tag::Google tag",
            "resource_family": "tag",
            "name": "Google tag",
            "action": "create",
            "intended": {
                "type": "googtag",
                "configSettingsVariable": "{{Google configuration settings}}",
            },
        }
        operations[tag_operation["object_key"]] = tag_operation
        self.assertFalse(web._send_page_view_value(tag_operation["intended"], "$.tag", operations))
        self.assertEqual(
            web._configured_transport_endpoint(tag_operation, operations, "$.tag"),
            "https://tags.example.test",
        )

    def test_importer_uses_current_business_timing_and_cli_blocks_forged_convergence(self) -> None:
        imported = normalized_approved_semantics(
            {},
            {
                "events": [
                    {
                        "event_name": "page_view",
                        "classification": "context",
                        "trigger": "after CMP readiness",
                        "journey_ids": ["J-1"],
                        "measurement_opportunity_ids": ["MO-1"],
                        "data_layer": {"push": {"event": "page_view"}},
                        "parameters": [],
                    }
                ]
            },
        )
        requirement = imported["requirements"][0]
        self.assertEqual(requirement["business_timing"], "after CMP readiness")
        self.assertNotIn("trigger", requirement)
        help_result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "configuration_run.py"), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(help_result.returncode, 0)
        self.assertNotIn("converge", help_result.stdout)
        self.assertNotIn("finalize", help_result.stdout)

    def test_retired_web_controller_is_absent(self) -> None:
        self.assertFalse(hasattr(web, "main"))
        self.assertFalse(hasattr(web, "finalize_document"))

    def test_materialized_baseline_shape_contains_identity_registry(self) -> None:
        run = create_from_contract(
            valid_web_contract(), run_id="RELEASE-GATE", source_locator="approved input"
        )
        self.assertEqual(run["container_baselines"][0]["resource_identities"], {})

    def test_raw_prewrite_trigger_ids_compare_without_semantic_rewriting(self) -> None:
        operation = {
            "operation_id": "OP-RAW",
            "target_id": "web-main",
            "name": "GA4 - purchase",
            "pre_change": {
                "name": "GA4 - purchase",
                "firingTriggerId": ["71"],
                "blockingTriggerId": ["72"],
            },
        }
        comparison, _ = build_pre_write_comparison(
            operation,
            {
                "name": "GA4 - purchase",
                "firingTriggerId": ["71"],
                "blockingTriggerId": ["72"],
                "fingerprint": "server-generated",
            },
        )
        self.assertTrue(comparison["pass"])

    def test_untrusted_dangling_semantic_reference_is_rejected(self) -> None:
        graph = {
            "objects": [
                {
                    "target_id": "web-main",
                    "object_type": "tag",
                    "name": "Dangling",
                    "firingTriggerId": ["web-main::trigger::Missing"],
                }
            ]
        }
        with self.assertRaises(GraphError):
            normalize_graph(graph, target_types={"web-main": "web"})

    def test_server_event_resolution_never_falls_back_to_destination(self) -> None:
        contract = valid_server_contract()
        contract["route"] = "media"
        requirement = contract["requirements"][0]
        requirement.pop("source_event")
        requirement.update(kind="media", destination="Meta", event_name="page_view")
        validate_document(contract)
        create_from_contract(
            contract,
            run_id="EVENT-RESOLUTION",
            source_locator="approved input",
        )

    def test_nested_reference_descriptor_cannot_hide_a_raw_credential(self) -> None:
        source = {
            "api_key": {
                "variable_reference": "{{Secure API Key}}",
                "value": "sk_live_ABC123XYZ",
            }
        }
        persisted = redact_for_persistence(source)
        self.assertNotIn("sk_live_ABC123XYZ", str(persisted))
        self.assertEqual(sensitive_paths(persisted), [])
        self.assertIn("$.api_key", sensitive_paths(source))

    def test_pipeline_endpoint_and_consent_carrier_are_bound_to_transport_owner(self) -> None:
        contract = valid_pipeline_contract()
        contract["pipelines"][0]["endpoint_reference"] = "https://wrong.example.test"
        with self.assertRaisesRegex(ContractValidationError, "differs from its transport owner"):
            validate_document(contract)

    def test_pipeline_requires_transport_owner_cutover_and_receiver_dependencies(self) -> None:
        contract = valid_pipeline_contract()
        contract["pipelines"][0].pop("cutover_operation_key")
        with self.assertRaisesRegex(ContractValidationError, "cutover_operation_key"):
            validate_document(contract)

    def test_pipeline_consent_carrier_must_inherit_transport_route(self) -> None:
        contract = valid_pipeline_contract()
        wrong_key = "web-main::tag::Unrelated transport"
        wrong = deepcopy(contract["implementation"]["objects"][0])
        wrong.update(name="Unrelated transport", object_key=wrong_key)
        wrong["intended"] = {
            "type": "vendor-transport",
            "firingTriggerId": ["web-main::trigger::CMP - Analytics granted"],
            "blockingTriggerId": [],
        }
        contract["implementation"]["objects"].append(wrong)
        topology = deepcopy(contract["execution_topologies"][0])
        topology.update(
            tag_object_key=wrong_key,
            lifecycle_role="event-driven",
            page_view_capable=False,
            page_view_destinations=[],
            page_view_occurrences=[],
        )
        contract["execution_topologies"].append(topology)
        contract["consent_topologies"][0]["transporter_tag_keys"] = [wrong_key]
        approve_mutations(contract)
        with self.assertRaisesRegex(
            ContractValidationError, "does not inherit the proved endpoint"
        ):
            validate_document(contract)

    def test_server_user_data_transport_supports_explicit_tag_wide_google_owner(self) -> None:
        web._validate_first_party_feature_contract(
            path="$.first_party_data_routes[0]",
            feature="google-ads-server-user-data-transport",
            destination_field="user_data",
            timing="tag-wide",
            hashing_owner="native-raw",
            field_names={"email"},
            consumer_targets=[{"type": "googtag"}],
            dependency_ids={"EXT-ADS"},
            consent_types={"ad_user_data"},
        )

    def test_client_enhanced_conversions_use_the_associated_google_tag(self) -> None:
        common = {
            "path": "$.first_party_data_routes[0]",
            "feature": "google-ads-enhanced-conversions",
            "destination_field": "user_data",
            "timing": "same-event",
            "hashing_owner": "native-raw",
            "field_names": {"email"},
            "dependency_ids": {"EXT-ADS"},
            "consent_types": {"ad_user_data"},
        }
        web._validate_first_party_feature_contract(**common, consumer_targets=[{"type": "googtag"}])
        with self.assertRaisesRegex(Exception, "associated with the Ads conversion action"):
            web._validate_first_party_feature_contract(
                **common, consumer_targets=[{"type": "awct"}]
            )

    def test_external_dependencies_use_only_the_structured_current_form(self) -> None:
        contract = valid_web_contract()
        contract["external_dependencies"] = ["legacy shorthand"]
        with self.assertRaisesRegex(ContractValidationError, "must be an object"):
            validate_document(contract)

    def test_generic_token_keys_are_redacted_in_objects_rows_and_errors(self) -> None:
        source = {
            "token": "live-token-value",
            "refreshToken": "refresh-token-value",
            "headers": {"X-API-Key": "header-token-value"},
            "endpoint": "https://example.test/collect?access_token=url-token-value",
            "parameter": [{"key": "auth_token", "value": "row-token-value"}],
        }
        persisted = redact_for_persistence(source)
        for secret in (
            "live-token-value",
            "refresh-token-value",
            "header-token-value",
            "url-token-value",
            "row-token-value",
        ):
            self.assertNotIn(secret, str(persisted))
        self.assertEqual(sensitive_paths(persisted), [])

    def test_nested_user_data_address_is_redacted_as_one_sensitive_payload(self) -> None:
        source = {
            "user_data": {
                "email": "person@example.test",
                "address": {"city": "Paris", "country": "FR"},
            }
        }
        persisted = redact_for_persistence(source)
        self.assertTrue(isinstance(persisted["user_data"], dict))
        self.assertEqual(persisted["user_data"].get("secret_state"), REDACTED_STATE)
        self.assertEqual(sensitive_paths(persisted), [])

    def test_baseline_requires_exhaustion_receipts_and_full_refonte_surface(self) -> None:
        contract = valid_web_contract()
        run = create_from_contract(contract, run_id="BASELINE-RECEIPT", source_locator="approved")
        resources = {"tag": [], "trigger": []}
        with self.assertRaisesRegex(Exception, "capture_evidence"):
            _record_target_baseline(
                run,
                target_id="web-main",
                resources=resources,
                captured_at="2026-09-05T00:00:00Z",
                preexisting_workspace_changes=[],
                capture_evidence={},
            )
        wrong_identity = complete_capture_evidence(resources, run["run"]["targets"][0])
        wrong_identity["source_identity"]["container_id"] = "GTM-WRONG"
        with self.assertRaisesRegex(Exception, "authorized GTM target"):
            _record_target_baseline(
                run,
                target_id="web-main",
                resources=resources,
                captured_at="2026-09-05T00:00:00Z",
                preexisting_workspace_changes=[],
                capture_evidence=wrong_identity,
            )

        contract["implementation"]["execution_mode"] = "refonte-durable"
        tag = next(
            item
            for item in contract["implementation"]["objects"]
            if item["resource_family"] == "tag"
        )
        contract["inventory_dispositions"] = [
            {
                "row_id": "INV-ADDED-GOOGLE-TAG",
                "source_order": 0,
                "source_locator": "approved empty-container inventory",
                "before_object_key": None,
                "before_tag_name": None,
                "disposition": "added",
                "after_tag_name": tag["name"],
                "trigger_before": [],
                "trigger_after": ["CMP - Analytics granted"],
                "variable_changes": [],
                "parameter_changes": [],
                "consent_changes": ["strict-basic vendor blocking"],
                "rationale": "The approved empty baseline requires the new Google tag.",
                "operation_keys": [tag["object_key"]],
            }
        ]
        run = create_from_contract(contract, run_id="REFONTE-RECEIPT", source_locator="approved")
        planned_families = {
            item["resource_family"]: []
            for item in run["object_changes"]
            if item["target_id"] == "web-main"
        }
        with self.assertRaisesRegex(Exception, "complete target resource surface"):
            _record_target_baseline(
                run,
                target_id="web-main",
                resources=planned_families,
                captured_at="2026-09-05T00:00:00Z",
                preexisting_workspace_changes=[],
                capture_evidence=complete_capture_evidence(
                    planned_families, run["run"]["targets"][0]
                ),
            )


if __name__ == "__main__":
    unittest.main()
