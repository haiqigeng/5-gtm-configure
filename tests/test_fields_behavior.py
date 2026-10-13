"""Behavioral tests owned by fields."""

from support import field_binding as fixture_field_binding
from support import phase_contracts as fixture_phase_contracts
from support import transport_and_state as fixture_transport_and_state


class TestFieldBinding(fixture_field_binding.NativeMappingTestFixture):
    def test_exact_event_names_at_compile_and_run_boundaries(self):
        for name in ("LEAD_TYPE", "leadtype", "lead-type"):
            for change_binding in (False, True):
                with self.subTest(name=name, change_binding=change_binding):
                    value = fixture_field_binding.lead_request()
                    contract = fixture_field_binding.compile_request(value)
                    for document, objects, bindings in (
                        (value, value["objects"], value["field_bindings"]),
                        (
                            contract,
                            contract["implementation"]["objects"],
                            contract["implementation"]["field_bindings"],
                        ),
                    ):
                        objects[0]["intended"]["parameter"][-1]["list"][0]["map"][0]["value"] = name
                        if change_binding:
                            bindings[0]["native_binding"]["field"] = name
                    with self.assertRaises(ValueError):
                        fixture_field_binding.compile_request(value)
                    with self.assertRaises(ValueError):
                        fixture_field_binding.create_from_contract(
                            contract, run_id="WRONG", source_locator="approved"
                        )

    def test_user_and_item_scopes_are_agent_reviewed_with_or_without_binding(self):
        for requirement_key, scope in (
            ("user_properties", "user-property"),
            ("item_parameters", "item-parameter"),
        ):
            for binding_present in (False, True):
                for event_row_present in (False, True):
                    with self.subTest(
                        scope=scope, binding=binding_present, event_row=event_row_present
                    ):
                        value = fixture_field_binding.lead_request()
                        value["requirements"][0][requirement_key] = value["requirements"][0].pop(
                            "parameters"
                        )
                        binding = value["field_bindings"][0]
                        binding["field_scope"] = scope
                        binding["template_field"] = "agent-inspected native route"
                        if not binding_present:
                            binding.pop("native_binding")
                        if not event_row_present:
                            value["objects"][0]["intended"]["parameter"].pop()
                        run = fixture_field_binding.create_from_contract(
                            fixture_field_binding.compile_request(value),
                            run_id="SCOPED",
                            source_locator="approved",
                        )
                        rendered = fixture_field_binding.render_markdown(run)
                        self.assertIn("agent-reviewed mapping declaration", rendered)
                        self.assertNotIn("exact native event-parameter intention checked", rendered)

    def test_automatic_page_location_needs_no_duplicate_parameter(self):
        fixture_field_binding.create_from_contract(
            fixture_field_binding.valid_pipeline_contract(),
            run_id="AUTOMATIC",
            source_locator="approved",
        )

    def test_missing_binding_field_variable_wrong_source_and_owner_fail(self):
        for mutation in ("field", "variable", "source", "owner", "metadata"):
            with self.subTest(mutation=mutation):
                value = fixture_field_binding.lead_request()
                binding = value["field_bindings"][0]
                if mutation == "binding":
                    binding.pop("native_binding")
                elif mutation == "field":
                    value["objects"][0]["intended"]["parameter"].pop()
                elif mutation == "variable":
                    value["reuse_candidates"].pop()
                elif mutation == "source":
                    value["reuse_candidates"][-1]["intended"]["parameter"][0]["value"] = (
                        "wrong.source"
                    )
                elif mutation == "owner":
                    binding["native_binding"]["object_key"] = "web-main::variable::DLV - lead_type"
                else:
                    binding["native_binding"]["field"] = "notes"
                    value["objects"][0]["intended"]["notes"] = binding["gtm_resolution"]
                with self.assertRaises(ValueError):
                    fixture_field_binding.compile_request(value)

    def test_other_namespaces_and_configuration_cannot_prove_event_field(self):
        for namespace in ("configSettingsTable", "userProperties", "itemParameters"):
            with self.subTest(namespace=namespace):
                value = fixture_field_binding.lead_request()
                # Deliberately wrong namespace, not a claimed valid native user/item shape.
                value["objects"][0]["intended"]["parameter"][-1]["key"] = namespace
                with self.assertRaises(ValueError):
                    fixture_field_binding.compile_request(value)


class TestPhaseContracts(fixture_phase_contracts.CurrentContractAndRunTestFixture):
    def test_non_scalar_shape_and_named_special_fields_are_not_inferred(self) -> None:
        contract = fixture_phase_contracts.valid_pipeline_contract()
        field = contract["pipelines"][0]["field_flows"][0]
        field["wire"] = {"path": "user_data", "shape": "array"}
        field["event_data"] = {"path": "user_data", "shape": "array"}
        field["source"] = {"path": "user_data", "shape": "array"}
        field["destination"] = {"path": "user_data", "shape": "array"}
        with self.assertRaisesRegex(
            fixture_phase_contracts.ContractValidationError, "user_data must be an object"
        ):
            fixture_phase_contracts.validate_contract(contract)

        contract = fixture_phase_contracts.valid_pipeline_contract()
        field = contract["pipelines"][0]["field_flows"][0]
        field["wire"]["shape"] = "object"
        with self.assertRaisesRegex(
            fixture_phase_contracts.ContractValidationError, "transformation owner"
        ):
            fixture_phase_contracts.validate_contract(contract)


class TestTransportAndState(fixture_transport_and_state.UtilityEvolutionTestFixture):
    def test_saved_ga4_event_must_match_approved_event(self):
        contract = fixture_transport_and_state.valid_server_contract()
        tag = next(
            item
            for item in contract["implementation"]["objects"]
            if item["resource_family"] == "tag"
        )
        tag["intended"]["event_name"] = "purchase"
        fixture_transport_and_state.approve_mutations(contract)
        with self.assertRaisesRegex(
            fixture_transport_and_state.ContractValidationError, "differs from approved"
        ):
            fixture_transport_and_state.validate_document(contract)
