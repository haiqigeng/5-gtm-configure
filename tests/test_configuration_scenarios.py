from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "configuration_scenarios.json"


class ConfigurationScenarioFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.scenarios = cls.payload["scenarios"]

    def scenario(self, scenario_id: str) -> dict:
        return next(item for item in self.scenarios if item["id"] == scenario_id)

    def test_scenario_corpus_has_expected_operational_coverage(self) -> None:
        self.assertEqual(self.payload["version"], 7)
        self.assertIn("not model-output or runtime tests", self.payload["description"])
        expected_ids = {
            "ga4-tracking-plan-configured",
            "media-brief-meta-ecommerce",
            "meta-runtime-missing-data-no-eligibility-guard",
            "compound-cmp-predicate",
            "explicit-google-advanced-consent",
            "shared-google-incompatible-routes",
            "missing-source-contract",
            "tool-unavailable-blocked",
            "partial-mutation-journal",
            "idempotent-rerun",
            "ga4-external-administration",
            "unlisted-browser-vendor",
            "tracking-plan-valid-custom-advisory",
            "tracking-plan-blocking-schema-error",
            "tracking-plan-optional-field-omitted",
            "tracking-plan-source-scope-manifest",
            "legacy-container-pattern-rejected",
            "conflicting-existing-implementation-blocked",
            "adapter-pagination-capability-discovery",
            "workspace-change-attribution",
            "lut-folder-organization",
            "installed-template-schema-conflict",
            "first-party-data-narrow-consumer-scope",
            "server-side-deduplication-deferred",
            "google-page-view-single-owner",
            "strict-page-load-topology",
            "strict-business-event-topology",
            "pre-cmp-business-event-not-replayed",
            "ga4-ecommerce-single-native-route",
            "microsoft-uet-not-gtag",
            "cmp-event-name-must-be-proved",
            "media-shape-requires-projection",
            "refonte-inventory-complete-disposition",
            "ga4-upd-selected-event-only",
            "google-ads-ec-same-event",
            "google-ads-upd-prior-page",
            "ga4-user-id-lifecycle",
            "ga4-pii-outside-sanctioned-feature",
            "browser-server-transport-in-scope",
            "mcp-single-authoritative-baseline",
        }
        self.assertEqual({scenario["id"] for scenario in self.scenarios}, expected_ids)

    def test_every_scenario_is_a_well_formed_operational_contract(self) -> None:
        allowed_routes = {"analytics", "media", "consent", "combined"}
        allowed_evidence = {
            "approved-input",
            "official-current",
            "container-confirmed",
            "contract-sample",
            "assumption",
        }
        allowed_actions = {
            "create",
            "update",
            "rename",
            "pause",
            "unpause",
            "reuse",
            "untouched",
            "remove",
        }
        allowed_statuses = set(self.payload["allowed_statuses"])
        self.assertEqual(allowed_statuses, {"Configured", "Partial", "Blocked", "Deferred"})

        for scenario in self.scenarios:
            with self.subTest(scenario=scenario["id"]):
                self.assertIn(scenario["route"], allowed_routes)
                self.assertTrue(scenario["request"].startswith("Use configure-gtm"))
                self.assertNotIn("read-only specification", scenario["request"].lower())
                self.assertIn(scenario["expected_status"], allowed_statuses)
                self.assertTrue(set(scenario["evidence_grades"]) <= allowed_evidence)
                self.assertIsInstance(scenario["external_dependencies"], list)
                self.assertGreaterEqual(len(scenario["external_dependencies"]), 1)
                self.assertGreaterEqual(len(scenario["expected_invariants"]), 1)
                self.assertGreaterEqual(len(scenario["forbidden_invariants"]), 1)
                self.assertFalse(
                    set(scenario["expected_invariants"]) & set(scenario["forbidden_invariants"])
                )

                for action in scenario["expected_actions"]:
                    self.assertIn(action["action"], allowed_actions)
                    self.assertTrue(action["object_type"])
                    self.assertTrue(action["name"])
                    self.assertTrue(action["justification"])

                for discrepancy in scenario.get("discrepancies", []):
                    self.assertIn(
                        discrepancy["class"],
                        {"blocking-error", "advisory", "implementation-note"},
                    )
                    self.assertTrue(discrepancy["approved"])
                    self.assertTrue(discrepancy["documented"])
                    self.assertTrue(discrepancy["default_action"])

    def test_status_specific_evidence_prevents_false_completion(self) -> None:
        for scenario in self.scenarios:
            with self.subTest(scenario=scenario["id"]):
                status = scenario["expected_status"]
                if status == "Configured":
                    self.assertTrue(scenario["live_state_claim"])
                    self.assertTrue(scenario["saved_object_readback"])
                    self.assertTrue(scenario["idempotent_second_execution"])
                elif status == "Partial":
                    self.assertTrue(scenario["live_state_claim"])
                    self.assertTrue(scenario["saved_partial_state"])
                    self.assertTrue(scenario["recovery_boundary"])
                else:
                    self.assertFalse(scenario["live_state_claim"])
                    self.assertEqual(scenario["expected_actions"], [])

    def test_scenario_corpus_covers_every_result_type(self) -> None:
        self.assertEqual(
            {scenario["expected_status"] for scenario in self.scenarios},
            {"Configured", "Partial", "Blocked", "Deferred"},
        )

    def test_exact_analytics_contract_adds_nothing(self) -> None:
        scenario = self.scenario("ga4-tracking-plan-configured")
        names = {action["name"] for action in scenario["expected_actions"]}
        self.assertEqual(
            {name for name in names if name.startswith("DLV -")},
            {"DLV - event.method", "DLV - event.form_location"},
        )
        self.assertIn("lead_type remains absent", scenario["expected_invariants"])
        self.assertIn("lead_type added", scenario["forbidden_invariants"])

    def test_meta_ecommerce_preserves_catalog_items_without_payload_guards(self) -> None:
        ecommerce = self.scenario("media-brief-meta-ecommerce")
        names = {action["name"] for action in ecommerce["expected_actions"]}
        self.assertIn("CJS - Meta contents", names)
        self.assertIn("CJS - Meta content_ids", names)
        self.assertIn("all approved items preserved", ecommerce["expected_invariants"])
        self.assertIn("CE - purchase", names)
        self.assertFalse(any("valid" in name.lower() for name in names))

        invalid = self.scenario("meta-runtime-missing-data-no-eligibility-guard")
        self.assertIn(
            "runtime missing data recorded as a dependency",
            invalid["expected_invariants"],
        )
        self.assertIn(
            "CJS eligibility guard",
            invalid["forbidden_invariants"],
        )

    def test_compound_consent_uses_or_denial_without_helper_code(self) -> None:
        scenario = self.scenario("compound-cmp-predicate")
        blocks = [
            action
            for action in scenario["expected_actions"]
            if action["object_type"] == "blocking trigger"
        ]
        self.assertEqual(len(blocks), 2)
        forbidden = " ".join(scenario["forbidden_invariants"]).lower()
        self.assertIn("consent cjs", forbidden)
        self.assertIn("mutually exclusive and", forbidden)

    def test_advanced_consent_requires_explicit_product_proof(self) -> None:
        scenario = self.scenario("explicit-google-advanced-consent")
        self.assertIn("advanced mode was explicit", scenario["expected_invariants"])
        self.assertIn(
            "advanced mode enabled from vendor name alone",
            scenario["forbidden_invariants"],
        )
        conflict = self.scenario("shared-google-incompatible-routes")
        self.assertEqual(conflict["expected_status"], "Blocked")

    def test_tracking_plan_scenarios_never_silently_redesign_collection(self) -> None:
        advisory = self.scenario("tracking-plan-valid-custom-advisory")
        action_names = {action["name"] for action in advisory["expected_actions"]}
        self.assertIn("GA4 - Event - account_created", action_names)
        self.assertNotIn("GA4 - Event - sign_up", action_names)
        self.assertEqual(advisory["discrepancies"][0]["class"], "advisory")

        blocked = self.scenario("tracking-plan-blocking-schema-error")
        self.assertEqual(blocked["expected_status"], "Blocked")
        self.assertEqual(blocked["expected_actions"], [])
        self.assertEqual(blocked["discrepancies"][0]["class"], "blocking-error")

        optional = self.scenario("tracking-plan-optional-field-omitted")
        self.assertIn("recommended field remains absent", optional["expected_invariants"])

    def test_container_state_is_integration_evidence_not_architecture_authority(self) -> None:
        legacy = self.scenario("legacy-container-pattern-rejected")
        actions = {action["name"]: action["action"] for action in legacy["expected_actions"]}
        self.assertEqual(actions["DLV - event.plan_type"], "create")
        self.assertEqual(actions["Existing broad Custom JavaScript helper"], "untouched")

        conflict = self.scenario("conflicting-existing-implementation-blocked")
        self.assertEqual(conflict["expected_status"], "Blocked")
        self.assertIn("parallel tag added", conflict["forbidden_invariants"])

    def test_mutation_access_and_template_compatibility_are_real_blockers(self) -> None:
        unavailable = self.scenario("tool-unavailable-blocked")
        self.assertEqual(unavailable["expected_status"], "Blocked")
        self.assertIn("planning-only success", unavailable["forbidden_invariants"])

        template = self.scenario("installed-template-schema-conflict")
        self.assertEqual(template["expected_status"], "Blocked")
        self.assertIn("required field dropped", template["forbidden_invariants"])

    def test_lut_and_folder_are_used_only_for_a_real_configuration(self) -> None:
        scenario = self.scenario("lut-folder-organization")
        types = {action["object_type"] for action in scenario["expected_actions"]}
        self.assertIn("folder", types)
        self.assertIn("lookup table", types)
        self.assertIn("three duplicated tags", scenario["forbidden_invariants"])
        self.assertIn("unrelated objects reorganized", scenario["forbidden_invariants"])

    def test_adapter_pagination_and_partial_write_safety_are_explicit(self) -> None:
        adapter = self.scenario("adapter-pagination-capability-discovery")
        self.assertIn("all relevant pages exhausted", adapter["expected_invariants"])
        self.assertIn("first page treated as complete", adapter["forbidden_invariants"])

        partial = self.scenario("partial-mutation-journal")
        self.assertEqual(partial["expected_status"], "Partial")
        self.assertIn("blind create retry", partial["forbidden_invariants"])

    def test_workspace_change_attribution_is_explicit(self) -> None:
        scenario = self.scenario("workspace-change-attribution")
        self.assertEqual(scenario["preexisting_workspace_changes"], 2)
        self.assertEqual(scenario["current_run_changes"], 1)
        self.assertEqual(scenario["final_workspace_changes"], 3)

    def test_first_party_data_uses_the_narrowest_authorized_owner_and_scope(self) -> None:
        scenario = self.scenario("first-party-data-narrow-consumer-scope")
        actions = {action["name"]: action for action in scenario["expected_actions"]}
        self.assertEqual(actions["Google tag - Primary"]["action"], "update")
        self.assertEqual(actions["UPD - GA4 - Lead"]["object_type"], "variable")
        self.assertIn(
            "user_data attached only to generate_lead",
            scenario["expected_invariants"],
        )
        self.assertIn(
            "user_data attached to all events",
            scenario["forbidden_invariants"],
        )

    def test_new_operational_regressions_cover_topology_refonte_and_user_data(self) -> None:
        self.assertIn(
            "send_page_view false by default",
            self.scenario("google-page-view-single-owner")["forbidden_invariants"],
        )
        self.assertIn(
            "Trigger Group used as replay queue",
            self.scenario("pre-cmp-business-event-not-replayed")["forbidden_invariants"],
        )
        self.assertIn(
            "gtag consent command used for Bing",
            self.scenario("microsoft-uet-not-gtag")["forbidden_invariants"],
        )
        self.assertIn(
            "every inventory tag has one disposition",
            self.scenario("refonte-inventory-complete-disposition")["expected_invariants"],
        )
        self.assertIn(
            "user_data in shared Event Settings",
            self.scenario("ga4-upd-selected-event-only")["forbidden_invariants"],
        )
        self.assertIn(
            "ad_user_data consent",
            self.scenario("google-ads-ec-same-event")["expected_invariants"],
        )
        self.assertIn(
            "hashed email registered as custom dimension",
            self.scenario("ga4-pii-outside-sanctioned-feature")["forbidden_invariants"],
        )


if __name__ == "__main__":
    unittest.main()
