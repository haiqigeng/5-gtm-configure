"""Behavioral tests owned by native."""

from support import adapters as fixture_adapters
from support import field_binding as fixture_field_binding
from support import google_settings as fixture_google_settings
from support import native_boundaries as fixture_native_boundaries
from support import native_execution as fixture_native_execution
from support import transport_and_state as fixture_transport_and_state
from support import web_authority as fixture_web_authority


class TestNativeExecution(fixture_native_execution.NativeCorrectionsTestsFixture):
    def test_update_payload_retains_explicit_empty_parameter(self):
        req = fixture_native_execution.request()
        backend = fixture_native_execution.FakeGtm(req)
        adapter = fixture_native_execution.McpTargetAdapter(
            req["targets"][0], fixture_native_execution.PROFILE, backend.call
        )
        op = fixture_native_execution.operation("tag")
        op["intended"] = {"type": "gclidw", "parameter": []}
        adapter.mutate(op)
        op["object_id"] = adapter.known_ids[op["object_key"]]
        op["action"] = "update"
        adapter.read(op)
        adapter.mutate(op)
        self.assertEqual(backend.calls[-1][1]["createOrUpdateConfig"]["parameter"], [])

    def test_template_native_representation_preserves_provenance_and_comparison(self):
        op = fixture_native_execution.operation()
        saved = fixture_native_execution.expected_graph(op)
        saved["objects"][0]["templateData"] = fixture_native_execution.NATIVE.replace("\n", "\r\n")
        paths = fixture_native_execution.public_identifier_paths(saved, records=[op])
        self.assertIn("$.objects[0].templateData", paths)
        comparison, retained = fixture_native_execution.build_verification_comparison(op, saved)
        self.assertTrue(comparison["pass"], comparison)
        self.assertEqual(retained, saved)


class TestGoogleSettingsGoogleTagInheritance(
    fixture_google_settings.GoogleTagInheritanceTestFixture
):
    def test_source_and_resolution_are_still_proved(self):
        for mutation in ("source", "resolution", "case", "missing"):
            with self.subTest(mutation=mutation):
                _, operations, _, _, mapping = fixture_google_settings.inherited_mapping()
                if mutation == "source":
                    mapping["source"] = "other.source"
                elif mutation == "resolution":
                    mapping["gtm_resolution"] = "{{Other DLV}}"
                elif mutation == "case":
                    operations[-1]["intended"]["parameter"][0]["list"][0]["map"][0]["value"] = (
                        "LEAD_TYPE"
                    )
                else:
                    operations[-1]["intended"]["parameter"] = []
                self.assertTrue(self.check_mapping(operations, mapping))

    def test_compile_and_run_inherited_mapping_without_repeating_event_settings(self):
        value = fixture_google_settings.lead_request()
        table = value["objects"][0]["intended"]["parameter"].pop()
        base = fixture_google_settings.deepcopy(value["objects"][0])
        base.update(name="Google tag", action="reuse")
        base["intended"].update(type="googtag")
        base["intended"]["parameter"] = [
            fixture_google_settings.param("tagId", "G-TEST123"),
            fixture_google_settings.param("sendPageView", "false", "boolean"),
            fixture_google_settings.param("eventSettingsVariable", "{{Shared}}"),
        ]
        settings = fixture_google_settings.deepcopy(value["reuse_candidates"][-1])
        settings.update(name="Shared", intended={"type": "gtes", "parameter": [table]})
        value["reuse_candidates"].extend([base, settings])
        value["objects"][0]["depends_on"] = ["web-main::tag::Google tag"]
        topology = fixture_google_settings.deepcopy(value["execution_topologies"][0])
        topology["tag_object_key"] = "web-main::tag::Google tag"
        value["execution_topologies"].append(topology)
        value["requirements"][0]["parameters"]["lead_type"]["missing_behavior"] = "omit when absent"
        value["field_bindings"] = []
        contract = fixture_google_settings.compile_request(value)
        self.assertEqual(len(contract["implementation"]["field_bindings"]), 1)
        fixture_google_settings.create_from_contract(
            contract, run_id="BASE-INHERITANCE", source_locator="approved"
        )

    def test_event_settings_then_local_override_base_defaults_preserving_case(self):
        _, operations, event, _, _ = fixture_google_settings.inherited_mapping()
        variables = {
            item["name"]: item["intended"]
            for item in operations
            if item["resource_family"] == "variable"
        }
        event_settings = fixture_google_settings.deepcopy(variables["Shared"])
        event_settings["parameter"][0]["list"][0]["map"][1]["value"] = "{{Event-time DLV}}"
        variables["Event settings"] = event_settings
        event["intended"]["parameter"].append(
            fixture_google_settings.param("eventSettingsVariable", "{{Event settings}}")
        )

        def resolve(field="lead_type"):
            return fixture_google_settings.resolved_event_parameter(
                event, operations, variables, field
            )

        self.assertEqual(resolve(), "{{Event-time DLV}}")
        table = fixture_google_settings.deepcopy(event_settings["parameter"][0])
        table["list"][0]["map"][1]["value"] = ""
        event["intended"]["parameter"].append(table)
        self.assertEqual(resolve(), "")
        table["list"][0]["map"][0]["value"] = "LEAD_TYPE"
        self.assertEqual(resolve(), "{{Event-time DLV}}")
        self.assertEqual(resolve("LEAD_TYPE"), "")

    def test_explicit_field_does_not_consult_broken_unused_base_settings(self):
        for explicit in ("settings", "local"):
            with self.subTest(explicit=explicit):
                contract, operations, event, base, mapping = (
                    fixture_google_settings.inherited_mapping()
                )
                base["intended"]["parameter"][-1]["value"] = "{{Unresolved base settings}}"
                errors = self.check_mapping(operations, mapping)
                self.assertTrue(any("shared settings are unresolved" in error for error in errors))
                if explicit == "settings":
                    event["intended"]["parameter"].append(
                        fixture_google_settings.param("eventSettingsVariable", "{{Shared}}")
                    )
                else:
                    event["intended"]["parameter"].append(
                        fixture_google_settings.deepcopy(operations[-1]["intended"]["parameter"][0])
                    )
                compact = {
                    "requirements": contract["requirements"],
                    "execution_topologies": [],
                    "field_bindings": [],
                }
                compact["requirements"][0]["parameters"]["lead_type"]["missing_behavior"] = (
                    "omit when absent"
                )
                with fixture_google_settings.patch(
                    "gtm_configure.domain.web_native.associated_google_tag",
                    side_effect=AssertionError("unused base lookup"),
                ):
                    self.assertEqual(self.check_mapping(operations, mapping), [])
                    fixture_google_settings.derive_exact_declarations(compact, operations)
                self.assertEqual(
                    compact["field_bindings"][0]["gtm_resolution"], mapping["gtm_resolution"]
                )

    def test_constant_destination_identity(self):
        _, operations, event, base, mapping = fixture_google_settings.inherited_mapping()
        for owner, field, name in (
            (event, "measurementIdOverride", "Event ID"),
            (base, "tagId", "Base ID"),
        ):
            constant = fixture_google_settings.deepcopy(
                next(item for item in operations if item["resource_family"] == "variable")
            )
            constant.update(name=name, object_key=f"web-main::variable::{name}")
            constant["intended"] = {
                "type": "c",
                "parameter": [fixture_google_settings.param("value", "G-TEST123")],
            }
            operations.append(constant)
            next(row for row in owner["intended"]["parameter"] if row["key"] == field)["value"] = (
                "{{" + name + "}}"
            )
        self.assertEqual(self.check_mapping(operations, mapping), [])
        for item in operations[-2:]:
            item["intended"]["parameter"][0]["value"] = "{{Nested ID}}"
        self.assertTrue(self.check_mapping(operations, mapping))

    def test_wrong_target_destination_paused_removed_ambiguous_and_unresolved_bases(self):
        for mutation in ("target", "destination", "paused", "remove", "ambiguous", "unresolved"):
            with self.subTest(mutation=mutation):
                _, operations, event, base, mapping = fixture_google_settings.inherited_mapping()
                if mutation == "target":
                    base["target_id"] = "other-web"
                elif mutation == "destination":
                    base["intended"]["parameter"][0]["value"] = "G-OTHER"
                elif mutation == "paused":
                    base["intended"]["paused"] = True
                elif mutation == "remove":
                    base["action"] = "remove"
                elif mutation == "unresolved":
                    base["intended"]["parameter"][0]["value"] = "{{Missing ID}}"
                else:
                    duplicate = fixture_google_settings.deepcopy(base)
                    duplicate.update(name="Other base", object_key="web-main::tag::Other base")
                    operations.append(duplicate)
                self.assertTrue(self.check_mapping(operations, mapping))
                # Explicit event mappings remain valid without inherited defaults.
                event["intended"]["parameter"].append(
                    fixture_google_settings.param("eventSettingsVariable", "{{Shared}}")
                )
                self.assertEqual(self.check_mapping(operations, mapping), [])


class TestGoogleSettingsBuiltInTrigger(fixture_google_settings.BuiltInTriggerTestFixture):
    def test_registry_resolution_and_incompatible_roles(self):
        resolved = fixture_google_settings.resolved_trigger_types({}, {})
        for key, trigger_type in fixture_google_settings.BUILT_IN_TRIGGER_TYPES.items():
            reference = key.removeprefix("trigger::builtin::")
            row = {
                "trigger_object_key": reference,
                "role": "initialization-page-load",
                "type": trigger_type,
            }
            item = {"normal_triggers": [row]}
            target = {"firingTriggerId": [reference]}
            self.assertEqual(
                fixture_google_settings.validate_normal_trigger_bindings(
                    item, path="test", target=target, trigger_types=resolved
                )[0]["trigger_object_key"],
                key,
            )
            row["role"] = "cmp-readiness-grant"
            with self.assertRaises(ValueError):
                fixture_google_settings.validate_normal_trigger_bindings(
                    item, path="test", target=target, trigger_types=resolved
                )
        with self.assertRaises(ValueError):
            fixture_google_settings.validate_normal_trigger_bindings(
                {
                    "normal_triggers": [
                        {
                            "trigger_object_key": "trigger::builtin::999",
                            "role": "initialization-page-load",
                            "type": "initialization",
                        }
                    ]
                },
                path="test",
                target={"firingTriggerId": ["trigger::builtin::999"]},
                trigger_types=resolved,
            )


class TestWebAuthority(fixture_web_authority.EffectiveConfigurationGuardrailsTestFixture):
    def test_variable_delta_requires_type_in_both_snapshots(self):
        for field in ("pre_change", "intended"):
            contract = fixture_web_authority.settings_contract()
            contract["implementation"]["objects"][0][field].pop("type")
            fixture_web_authority.approve_mutations(contract)
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(
                    fixture_web_authority.ContractValidationError, field + r".type"
                ),
            ):
                fixture_web_authority.validate_document(contract)

    def test_settings_type_alone_does_not_require_high_impact(self):
        contract = fixture_web_authority.settings_contract()
        contract["implementation"]["objects"][0]["risk"] = "routine"
        fixture_web_authority.validate_document(contract)


class TestNativeBoundariesNativeBoundary(fixture_native_boundaries.NativeBoundaryTestsFixture):
    def test_reference_wrong_target_family_and_duplicates_fail_before_write(self):
        backend = fixture_native_boundaries.FakeGtm(fixture_native_boundaries.request())
        profile = fixture_native_boundaries.deepcopy(fixture_native_boundaries.PROFILE)
        profile["sequencing_reference"] = "tagId"
        profile["families"]["folder"] = {**profile["families"]["tag"], "list_path": ["folder"]}
        _, adapter = self.registry(fixture_native_boundaries.request(), backend.call, profile)
        adapter.cache["tag"] = [
            {
                "tagId": "77",
                "name": "Setup",
                "accountId": "account-1",
                "containerId": "GTM-WEBTEST",
                "workspaceId": "workspace-web",
            }
        ]
        adapter.complete_families.add("tag")
        adapter.known_ids["elsewhere::tag::Setup"] = "77"
        for field, value in (
            ("firingTriggerId", ["elsewhere::trigger::builtin::2147479572"]),
            ("parentFolderId", "2147479572"),
            ("setupTag", [{"tagName": "elsewhere::tag::Setup"}]),
            ("firingTriggerId", ["web-main::tag::Setup"]),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(fixture_native_boundaries.AdapterExecutionError):
                    adapter._serialize_references({field: value})
        self.assertIn("folder", adapter.complete_families)
        self.assertEqual(adapter.cache["folder"], [])
        adapter.cache["tag"].append(
            {
                "tagId": "78",
                "name": "Setup",
                "accountId": "account-1",
                "containerId": "GTM-WEBTEST",
                "workspaceId": "workspace-web",
            }
        )
        with self.assertRaisesRegex(
            fixture_native_boundaries.AdapterExecutionError, "Ambiguous GTM reference"
        ):
            adapter._serialize_references({"setupTag": [{"tagName": "web-main::tag::Setup"}]})
        self.assertFalse(backend.writes)

    def test_sequence_requires_inspection_only_for_semantic_values(self):
        _, adapter = self.registry(
            fixture_native_boundaries.request(),
            fixture_native_boundaries.FakeGtm(fixture_native_boundaries.request()).call,
        )
        adapter.cache["tag"] = [
            {
                "tagId": "77",
                "name": "Setup",
                "accountId": "account-1",
                "containerId": "GTM-WEBTEST",
                "workspaceId": "workspace-web",
            }
        ]
        adapter.complete_families.add("tag")
        for native in ("77", "Setup"):
            intended = {"setupTag": [{"tagName": native}]}
            adapter._serialize_references(intended)
            self.assertEqual(intended["setupTag"][0]["tagName"], native)
        with self.assertRaises(fixture_native_boundaries.AdapterExecutionError):
            adapter._serialize_references({"setupTag": [{"tagName": "web-main::tag::Setup"}]})

    def test_reordered_parameters_do_not_block_actual_update(self):
        req = fixture_native_boundaries.request()
        backend = fixture_native_boundaries.FakeGtm(req)
        registry, _ = self.start(req, backend.call)
        fixture_native_boundaries.execute_ready_operations(self.path, registry)
        saved = next(
            v for v in backend.data["tag"].values() if v["name"] == req["objects"][0]["name"]
        )
        update = fixture_native_boundaries.request()
        row = update["objects"][0]
        row.update(
            action="update",
            object_id=saved["tagId"],
            pre_change=fixture_native_boundaries.deepcopy(saved),
        )
        row["intended"]["notes"] = "Approved update"
        saved["parameter"].reverse()
        registry, _ = self.start(update, backend.call)
        fixture_native_boundaries.execute_ready_operations(self.path, registry)
        self.assert_configured(registry)
        self.assertEqual(len(backend.writes), 2)
        self.assertEqual(backend.data["tag"][saved["tagId"]]["notes"], "Approved update")


class TestNativeBoundariesPrewriteSemantic(fixture_native_boundaries.PrewriteSemanticTestsFixture):
    def test_keyed_maps_sort_but_real_drift_and_ordered_lists_remain_detected(self):
        before = {
            "name": "V",
            "type": "c",
            "parameter": [
                {
                    "key": "data",
                    "type": "map",
                    "map": [
                        {"key": "a", "type": "template", "value": "A"},
                        {"key": "b", "type": "template", "value": "B"},
                    ],
                },
                {
                    "key": "list",
                    "type": "list",
                    "list": [
                        {"type": "template", "value": "1"},
                        {"type": "template", "value": "2"},
                    ],
                },
            ],
        }
        operation = {
            "operation_id": "o",
            "target_id": "web-main",
            "resource_family": "variable",
            "name": "V",
            "pre_change": before,
        }
        reordered = fixture_native_boundaries.deepcopy(before)
        reordered["parameter"][0]["map"].reverse()
        reordered["parameter"].reverse()
        self.assertTrue(
            fixture_native_boundaries.build_pre_write_comparison(operation, reordered)[0]["pass"]
        )
        for change in ("value", "missing", "extra", "list", "unknown"):
            with self.subTest(change=change):
                saved = fixture_native_boundaries.deepcopy(before)
                if change == "value":
                    saved["parameter"][0]["map"][0]["value"] = "changed"
                elif change == "missing":
                    saved["parameter"].pop()
                elif change == "extra":
                    saved["parameter"].append({"key": "extra", "type": "template", "value": "X"})
                elif change == "list":
                    saved["parameter"][1]["list"].reverse()
                else:
                    saved["unknown"] = True
                self.assertFalse(
                    fixture_native_boundaries.build_pre_write_comparison(operation, saved)[0][
                        "pass"
                    ]
                )
        duplicate = fixture_native_boundaries.deepcopy(before)
        duplicate["parameter"].append(fixture_native_boundaries.deepcopy(duplicate["parameter"][0]))
        with self.assertRaises(fixture_native_boundaries.GraphError):
            fixture_native_boundaries.build_pre_write_comparison(operation, duplicate)


class TestAdapters(fixture_adapters.CurrentAdapterRuntimeTestFixture):
    def test_configuration_settings_mutation_requires_tag_consumer_inventory(self) -> None:
        operation = {
            "resource_family": "variable",
            "action": "update",
            "intended": {"type": "Google Tag Configuration Settings"},
        }
        self.assertEqual(
            fixture_adapters.required_baseline_families([operation], "web"),
            {"variable", "tag"},
        )


class TestFieldBinding(fixture_field_binding.NativeMappingTestFixture):
    def test_direct_dlv_native_table_and_run(self):
        contract = fixture_field_binding.compile_request(fixture_field_binding.lead_request())
        fixture_field_binding.create_from_contract(
            contract, run_id="MAPPING", source_locator="approved"
        )

    def test_inherited_event_settings(self):
        value = fixture_field_binding.lead_request()
        table = value["objects"][0]["intended"]["parameter"].pop()
        variable = fixture_field_binding.deepcopy(value["reuse_candidates"][-1])
        variable.update(name="Shared lead fields", intended={"type": "gtes", "parameter": [table]})
        value["reuse_candidates"].append(variable)
        value["objects"][0]["intended"]["parameter"].append(
            fixture_field_binding.param("eventSettingsVariable", "{{Shared lead fields}}")
        )
        fixture_field_binding.create_from_contract(
            fixture_field_binding.compile_request(value),
            run_id="INHERITED",
            source_locator="approved",
        )

    def test_native_event_table_and_assurance(self):
        value = fixture_field_binding.lead_request()
        table = value["objects"][0]["intended"]["parameter"][-1]
        self.assertEqual(
            fixture_field_binding.effective_collection_fields(value["objects"][0]["intended"], {}),
            {"lead_type": "{{DLV - lead_type}}"},
        )
        table["key"] = "eventParameters"
        table["list"][0]["map"][0]["key"] = "name"
        table["list"][0]["map"][1]["key"] = "value"
        self.assertEqual(
            fixture_field_binding.effective_collection_fields(value["objects"][0]["intended"], {}),
            {},
        )
        self.assertEqual(
            fixture_field_binding.effective_collection_fields(
                {"parameter": [fixture_field_binding.param("eventSettingsVariable", "{{Shared}}")]},
                {"Shared": {"type": "gtes", "parameter": [table]}},
            ),
            {},
        )
        with self.assertRaises(ValueError):
            fixture_field_binding.compile_request(value)
        run = fixture_field_binding.create_from_contract(
            fixture_field_binding.compile_request(fixture_field_binding.lead_request()),
            run_id="EXACT",
            source_locator="approved",
        )
        self.assertIn(
            "exact native event-parameter intention checked",
            fixture_field_binding.render_markdown(run),
        )

    def test_exact_shared_settings_resolution_and_local_override(self):
        table = fixture_field_binding.lead_request()["objects"][0]["intended"]["parameter"][-1]
        shared = {"Shared": {"type": "gtes", "parameter": [table]}}
        target = {
            "parameter": [
                fixture_field_binding.param("eventSettingsVariable", "{{Shared}}"),
                fixture_field_binding.deepcopy(table),
            ]
        }
        row = target["parameter"][-1]["list"][0]["map"]
        row[0]["value"] = "LEAD_TYPE"
        row[1]["value"] = "different"
        self.assertEqual(
            fixture_field_binding.effective_collection_fields(target, shared),
            {"lead_type": "{{DLV - lead_type}}", "LEAD_TYPE": "different"},
        )
        row[0]["value"] = "lead_type"
        row[1]["value"] = ""
        self.assertEqual(
            fixture_field_binding.effective_collection_fields(target, shared), {"lead_type": ""}
        )
        target["parameter"][-1]["list"].append(
            fixture_field_binding.deepcopy(target["parameter"][-1]["list"][0])
        )
        with self.assertRaises(fixture_field_binding.FieldResolutionError):
            fixture_field_binding.effective_collection_fields(target, shared)
        shared["Shared"]["parameter"].append(
            fixture_field_binding.param("eventSettingsVariable", "{{Shared}}")
        )
        with self.assertRaises(fixture_field_binding.FieldResolutionError):
            fixture_field_binding.effective_collection_fields(
                {"parameter": [fixture_field_binding.param("eventSettingsVariable", "{{Shared}}")]},
                shared,
            )

    def test_native_template_is_agent_reviewed_even_with_binding(self):
        for binding_present in (False, True):
            value = fixture_field_binding.lead_request()
            value["field_bindings"][0]["mapping_method"] = "native-template"
            if not binding_present:
                value["field_bindings"][0].pop("native_binding")
            value["objects"][0]["intended"]["parameter"].pop()
            run = fixture_field_binding.create_from_contract(
                fixture_field_binding.compile_request(value),
                run_id="PRODUCT",
                source_locator="approved",
            )
            self.assertIn(
                "agent-reviewed mapping declaration", fixture_field_binding.render_markdown(run)
            )
            self.assertNotIn(
                "exact native event-parameter intention checked",
                fixture_field_binding.render_markdown(run),
            )


class TestTransportAndState(fixture_transport_and_state.UtilityEvolutionTestFixture):
    def test_trigger_notes_do_not_establish_event_coverage(self):
        contract = fixture_transport_and_state.valid_server_contract()
        trigger = next(
            item
            for item in contract["implementation"]["objects"]
            if item["resource_family"] == "trigger"
        )
        trigger["intended"] = {
            "type": "customEvent",
            "customEventFilter": [fixture_transport_and_state.condition("equals", "purchase")],
            "notes": "page_view",
        }
        fixture_transport_and_state.approve_mutations(contract)
        with self.assertRaisesRegex(
            fixture_transport_and_state.ContractValidationError, "no firing trigger"
        ):
            fixture_transport_and_state.validate_document(contract)

    def test_trigger_operators_case_and_negation_are_respected(self):
        cases = [
            (fixture_transport_and_state.condition("equals", "purchase"), "purchase", True),
            (fixture_transport_and_state.condition("equals", ".*"), "purchase", False),
            (
                fixture_transport_and_state.condition("equals", "purchase", negate="true"),
                "purchase",
                False,
            ),
            (
                fixture_transport_and_state.condition(
                    "matchRegex", "^purchase$", ignore_case="true"
                ),
                "PURCHASE",
                True,
            ),
            (fixture_transport_and_state.condition("matchRegex", "^purchase$"), "PURCHASE", False),
            (fixture_transport_and_state.condition("matchRegex", "["), "purchase", False),
        ]
        for selector, name, expected in cases:
            with self.subTest(selector=selector, name=name):
                self.assertEqual(
                    fixture_transport_and_state.trigger_accepts_event(
                        {"customEventFilter": [selector]}, name
                    ),
                    expected,
                )

    def test_nested_types_zero_and_identifiers_are_preserved(self):
        data = [{"item_id": "001", "price": 0, "quantity": 1}, {"item_id": "002", "price": 8}]
        self.assertFalse(
            fixture_transport_and_state.differences(
                data, fixture_transport_and_state.deepcopy(data)
            )
        )
        for mutation in [{"item_id": 1}, {"price": False}, {"quantity": True}]:
            changed = fixture_transport_and_state.deepcopy(data)
            changed[0].update(mutation)
            self.assertTrue(fixture_transport_and_state.differences(data, changed))
        self.assertTrue(fixture_transport_and_state.differences(data, data[:1]))

    def test_ads_tag_wide_google_owner_retains_server_receiver_proof(self):
        contract = fixture_transport_and_state.ads_transport_contract()
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

        run = fixture_transport_and_state.create_from_contract(
            fixture_transport_and_state.approve_mutations(contract),
            run_id="ADS-TAG-WIDE",
            source_locator="synthetic",
        )

        self.assertEqual(
            run["first_party_data_routes"][0]["server_consumer_object_keys"],
            ["server-main::tag::Ads conversion"],
        )
