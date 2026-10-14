"""Behavioral tests owned by first party data."""

from support import consent_and_fields as fixture_consent_and_fields
from support import mutation_recovery as fixture_mutation_recovery
from support import native_execution as fixture_native_execution
from support import transport_and_state as fixture_transport_and_state


class TestNativeExecution(fixture_native_execution.MatchingCorrectionsTestsFixture):
    def test_complete_contract_single_and_two_matching_fields(self):
        for fields in (("em",), ("em", "ph")):
            contract = fixture_native_execution.meta_matching_contract(fields)
            fixture_native_execution.validate_document(contract)
            run = fixture_native_execution.create_from_contract(
                contract, run_id="matching", source_locator="synthetic"
            )
            self.assertEqual(len(run["first_party_data_routes"]), len(fields))

    def test_matching_duplicates_wrong_row_source_timing_and_disabled_control_rejected(self):
        for flaw in ("duplicate", "row", "source", "timing", "disabled", "table-alias", "value"):
            contract = fixture_native_execution.meta_matching_contract()
            route = contract["first_party_data_routes"][0]
            if flaw == "duplicate":
                contract["first_party_data_routes"].append(fixture_native_execution.deepcopy(route))
            elif flaw == "row":
                route["consumer_bindings"][0]["user_data_path"][3] = 1
            elif flaw == "source":
                route["fields"][0]["source"] = "wrong.source"
            elif flaw == "timing":
                route["timing"] = "prior-page"
            elif flaw == "disabled":
                contract["implementation"]["objects"][0]["intended"]["parameter"][0]["value"] = (
                    "false"
                )
            elif flaw == "table-alias":
                route["destination_field"] = "advancedMatchingList"
            else:
                contract["implementation"]["field_bindings"][0]["gtm_resolution"] = (
                    "{{Wrong variable}}"
                )
            with (
                self.subTest(flaw=flaw),
                self.assertRaises(fixture_native_execution.ContractValidationError),
            ):
                fixture_native_execution.validate_document(
                    fixture_native_execution.approve_mutations(contract)
                )


class TestMutationRecovery(fixture_mutation_recovery.NativeAndRecoveryTestsFixture):
    def test_sender_user_data_requires_explicit_external_receiver(self):
        contract = fixture_mutation_recovery.sender_user_data_contract()
        fixture_mutation_recovery.validate_document(contract)
        run = fixture_mutation_recovery.create_from_contract(
            contract, run_id="sender-data", source_locator="test"
        )
        self.assertFalse(run["pipelines"])
        for mutation in (
            lambda r: r.pop("external_receiver_dependency_id"),
            lambda r: r.update(timing="tag-wide"),
            lambda r: r.update(server_consumer_object_keys=["server::tag::invented"]),
        ):
            broken = fixture_mutation_recovery.deepcopy(contract)
            mutation(broken["first_party_data_routes"][0])
            with self.assertRaises(fixture_mutation_recovery.ContractValidationError):
                fixture_mutation_recovery.validate_document(
                    fixture_mutation_recovery.approve_mutations(broken)
                )

    def test_supplied_sender_identity_must_bind_actual_fields_not_notes(self):
        contract = fixture_mutation_recovery.sender_generated_contract()
        dedup = contract["dedup_contracts"][0]
        dedup["source_type"] = "approved-event-id"
        dedup["consumer_bindings"] = dedup.pop("generation")["consumer_bindings"]
        variable = next(
            o
            for o in contract["implementation"]["objects"]
            if o["object_key"] == dedup["source_variable_key"]
        )
        variable["intended"] = {
            "type": "v",
            "parameter": [{"key": "name", "type": "template", "value": "occurrence_id"}],
        }
        fixture_mutation_recovery.validate_document(
            fixture_mutation_recovery.approve_mutations(contract)
        )
        tag = next(
            o
            for o in contract["implementation"]["objects"]
            if o["object_key"] == dedup["browser_consumer_keys"][0]
        )
        tag["intended"]["notes"] = tag["intended"].pop("event_id")
        dedup["consumer_bindings"][0]["field_path"] = ["notes"]
        with self.assertRaisesRegex(
            fixture_mutation_recovery.ContractValidationError, "identity binding"
        ):
            fixture_mutation_recovery.validate_document(
                fixture_mutation_recovery.approve_mutations(contract)
            )

    def test_meta_native_matching_cell_and_activation_are_bound(self):
        tag = {
            "type": "cvt_meta",
            "parameter": [
                {"key": "advancedMatching", "type": "boolean", "value": "true"},
                {
                    "key": "advancedMatchingList",
                    "type": "list",
                    "list": [
                        {
                            "type": "map",
                            "map": [
                                {"key": "name", "type": "template", "value": "em"},
                                {"key": "value", "type": "template", "value": "{{Email}}"},
                            ],
                        }
                    ],
                },
            ],
        }
        route = {
            "feature": "vendor-advanced-matching",
            "destination_field": "em",
            "fields": [{"name": "em"}],
            "consumer_bindings": [
                {
                    "object_key": "tag",
                    "field_review": "Inspected Meta matching email cell",
                    "user_data_path": [
                        "parameter",
                        "advancedMatchingList",
                        "list",
                        0,
                        "map",
                        "value",
                        "value",
                    ],
                    "activation_paths": [["parameter", "advancedMatching", "value"]],
                }
            ],
        }
        self.assertEqual(
            fixture_mutation_recovery.first_party_binding_value(route, tag, "tag", "test"),
            (True, "{{Email}}"),
        )
        for altered in ("false", "{{Unknown}}"):
            tag["parameter"][0]["value"] = altered
            with self.assertRaises(fixture_mutation_recovery.RunValidationError):
                fixture_mutation_recovery.first_party_binding_value(route, tag, "tag", "test")
        tag["parameter"][0]["value"] = "true"
        route["fields"].append({"name": "ph"})
        with self.assertRaisesRegex(
            fixture_mutation_recovery.RunValidationError, "exactly its one"
        ):
            fixture_mutation_recovery.first_party_binding_value(route, tag, "tag", "test")
        route["fields"].pop()
        tag["parameter"][1]["list"][0]["map"][0]["value"] = "ph"
        with self.assertRaises(fixture_mutation_recovery.RunValidationError):
            fixture_mutation_recovery.first_party_binding_value(route, tag, "tag", "test")


class TestConsentAndFields(fixture_consent_and_fields.UtilityCorrectionsFixture):
    def test_firing_gate_rejects_unknown_matching_and_negation(self):
        for grant in (
            fixture_consent_and_fields.condition("{{CMP Analytics}}", "undefined"),
            fixture_consent_and_fields.condition("{{CMP Analytics}}", "", "contains"),
        ):
            req = fixture_consent_and_fields.firing_request()
            req["consent_policies"][0]["web_enforcement"]["grant_condition"] = grant
            with self.assertRaisesRegex(ValueError, "reject missing and denied"):
                fixture_consent_and_fields.compile_request(req)


class TestTransportAndState(fixture_transport_and_state.UtilityEvolutionTestFixture):
    def test_prior_page_browser_user_data_requires_native_form_submission(self):
        contract = fixture_transport_and_state.ads_transport_contract()
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
        route["consumer_bindings"][0].update(product="google-ads")
        fixture_transport_and_state.approve_mutations(contract)
        with self.assertRaisesRegex(
            fixture_transport_and_state.ContractValidationError, "gtm.formSubmit source event"
        ):
            fixture_transport_and_state.validate_document(contract)

    def test_ads_only_event_transport_materializes_without_ga4_matching_activation(self):
        contract = fixture_transport_and_state.ads_transport_contract()
        run = fixture_transport_and_state.create_from_contract(
            contract, run_id="ADS", source_locator="synthetic"
        )
        self.assertEqual(
            run["first_party_data_routes"][0]["feature"], "google-ads-server-user-data-transport"
        )

    def test_prior_page_server_user_provided_data_event_route_materializes(self):
        contract = fixture_transport_and_state.ads_transport_contract()
        requirement = next(item for item in contract["requirements"] if item["id"] == "REQ-ADS")
        requirement.update(event_name="form_submit", source_event="form_submit")
        for item in contract["implementation"]["objects"]:
            if item.get("requirement_ids") != ["REQ-ADS"]:
                continue
            intended = item.get("intended", {})
            for condition in intended.get("customEventFilter", []):
                for parameter in condition.get("parameter", []):
                    if parameter.get("key") == "arg1" and parameter.get("value") == "purchase":
                        parameter["value"] = "form_submit"
            if intended.get("event_name") == "purchase":
                intended["event_name"] = "form_submit"
            for parameter in intended.get("parameter", []):
                if parameter.get("key") == "eventName" and parameter.get("value") == "purchase":
                    parameter["value"] = "form_submit"
        ads_flow = next(
            item
            for item in contract["pipelines"][0]["event_flows"]
            if item["requirement_id"] == "REQ-ADS"
        )
        ads_flow.update(source_event="form_submit", transported_event="form_submit")
        for consent in contract["consent_policies"]:
            if consent["consent_policy_id"] == contract["tag_policies"][-1]["consent_policy_id"]:
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

        run = fixture_transport_and_state.create_from_contract(
            fixture_transport_and_state.approve_mutations(contract),
            run_id="ADS-UPD-SERVER",
            source_locator="synthetic",
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
            for item in contract["tag_policies"]
            if item["tag_object_key"] == sender["object_key"]
        )
        topology["trigger_roles"][0]["trigger_object_key"] = sender["intended"]["firingTriggerId"][
            0
        ]
        with self.assertRaisesRegex(
            fixture_transport_and_state.ContractValidationError,
            "must resolve on its approved source event",
        ):
            fixture_transport_and_state.validate_document(
                fixture_transport_and_state.approve_mutations(contract)
            )
