"""Behavioral tests owned by page views."""

from support import durable_evidence as fixture_durable_evidence
from support import transport_and_state as fixture_transport_and_state
from support import web_authority as fixture_web_authority


class TestDurableEvidence(fixture_durable_evidence.CurrentRegressionHardeningTestFixture):
    def test_web_contract_cannot_drop_topology_or_page_view_ownership(self) -> None:
        contract = fixture_durable_evidence.valid_web_contract()
        contract["execution_topologies"] = []
        with self.assertRaisesRegex(
            fixture_durable_evidence.ContractValidationError, "execution topology"
        ):
            fixture_durable_evidence.validate_contract(contract)

    def test_page_view_ownership_is_occurrence_scoped_and_supports_internal_tags(self) -> None:
        contract = fixture_durable_evidence.valid_web_contract()
        topology = contract["execution_topologies"][0]
        topology["page_view_occurrences"] = ["initial-page-load", "virtual-navigation"]
        decision = contract["page_view_decisions"][0]
        decision.update(
            owner="internal-tag",
            google_tag_object_key=None,
            send_page_view=None,
            reason="The internal analytics tag owns this occurrence.",
        )
        contract["page_view_decisions"].append(
            {
                **fixture_durable_evidence.deepcopy(decision),
                "occurrence": "virtual-navigation",
                "reason": "The same internal tag owns virtual navigation without overlapping initial load.",
            }
        )
        with self.assertRaisesRegex(
            fixture_durable_evidence.ContractValidationError, "initial-page-load occurrence"
        ):
            fixture_durable_evidence.validate_contract(contract)

        # An internal owner must be a real page-view emitter, not a Google tag
        # relabelled in the decision record.
        topology["page_view_occurrences"] = ["initial-page-load"]
        contract["page_view_decisions"] = [decision]
        decision.update(
            owner="google-tag-automatic",
            google_tag_object_key=decision["owner_object_key"],
            send_page_view=True,
        )
        self.assertEqual(
            len(fixture_durable_evidence.validate_contract(contract)["page_view_decisions"]), 1
        )

        duplicate = fixture_durable_evidence.deepcopy(contract)
        duplicate["page_view_decisions"].append(
            fixture_durable_evidence.deepcopy(duplicate["page_view_decisions"][0])
        )
        with self.assertRaisesRegex(
            fixture_durable_evidence.ContractValidationError, "duplicate page-view decision"
        ):
            fixture_durable_evidence.validate_contract(duplicate)

        missing = fixture_durable_evidence.deepcopy(contract)
        missing["page_view_decisions"].pop()
        with self.assertRaisesRegex(
            fixture_durable_evidence.ContractValidationError, "page-view decisions"
        ):
            fixture_durable_evidence.validate_contract(missing)


class TestTransportAndState(fixture_transport_and_state.UtilityEvolutionTestFixture):
    def test_correct_automatic_page_view_owner_remains_valid(self):
        self.assertEqual(
            fixture_transport_and_state.validate_document(
                fixture_transport_and_state.valid_web_contract()
            )["page_view_decisions"][0]["owner"],
            "google-tag-automatic",
        )


class TestWebAuthority(fixture_web_authority.EffectiveConfigurationGuardrailsTestFixture):
    def test_separate_initial_and_disjoint_virtual_page_views_are_valid(self):
        for virtual in (False, True):
            contract = fixture_web_authority.separate_page_view_contract(virtual=virtual)
            run = fixture_web_authority.create_from_contract(
                contract, run_id="MANUAL", source_locator="approved"
            )
            self.assertEqual(len(run["page_view_decisions"]), 2 if virtual else 1)

    def test_two_page_view_tags_cannot_claim_disjoint_occurrences_on_the_same_trigger(self):
        contract = fixture_web_authority.separate_page_view_contract(virtual=True)
        initial_topology = contract["execution_topologies"][1]
        virtual_topology = contract["execution_topologies"][2]
        trigger_key = initial_topology["normal_triggers"][0]["trigger_object_key"]
        virtual_tag = contract["implementation"]["objects"][-1]
        virtual_tag["intended"]["firingTriggerId"] = [trigger_key]
        virtual_topology["normal_triggers"] = [
            {"trigger_object_key": trigger_key, "type": "custom-event", "role": "source-event"}
        ]
        fixture_web_authority.approve_mutations(contract)
        with self.assertRaisesRegex(
            fixture_web_authority.ContractValidationError, "different occurrence labels"
        ):
            fixture_web_authority.validate_document(contract)

    def test_automatic_page_views_cannot_be_hidden_by_empty_declarations(self):
        for explicit in (True, False):
            contract = fixture_web_authority.valid_web_contract()
            if not explicit:
                contract["implementation"]["objects"][0]["intended"].pop("send_page_view")
                fixture_web_authority.approve_mutations(contract)
            contract["execution_topologies"][0].update(
                page_view_capable=False, page_view_destinations=[], page_view_occurrences=[]
            )
            contract["page_view_decisions"] = []
            with (
                self.subTest(explicit=explicit),
                self.assertRaisesRegex(
                    fixture_web_authority.ContractValidationError,
                    "every effective Google page-view destination",
                ),
            ):
                fixture_web_authority.validate_document(contract)

    def test_page_view_declarations_cannot_omit_a_configured_destination(self):
        contract = fixture_web_authority.valid_web_contract()
        contract["implementation"]["objects"][0]["intended"]["destinations"] = ["G-SECOND"]
        fixture_web_authority.approve_mutations(contract)
        with self.assertRaisesRegex(
            fixture_web_authority.ContractValidationError,
            "every effective Google page-view destination",
        ):
            fixture_web_authority.validate_document(contract)

    def test_ads_only_google_tag_does_not_require_a_ga4_page_view(self):
        contract = fixture_web_authority.valid_web_contract()
        contract["implementation"]["objects"][0]["intended"]["measurement_id"] = "AW-123456"
        contract["execution_topologies"][0].update(
            page_view_capable=False, page_view_destinations=[], page_view_occurrences=[]
        )
        contract["page_view_decisions"] = []
        fixture_web_authority.approve_mutations(contract)
        fixture_web_authority.validate_document(contract)
