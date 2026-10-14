"""Behavioral tests owned by intake request."""

from support import consent_and_fields as fixture_consent_and_fields
from support import google_settings as fixture_google_settings
from support import input_and_execution as fixture_input_and_execution
from support import mutation_recovery as fixture_mutation_recovery
from support import native_boundaries as fixture_native_boundaries
from support import transport_and_state as fixture_transport_and_state


class TestInputAndExecution(fixture_input_and_execution.AuditRegressionsFixture):
    def test_compiler_roundtrip_and_missing_policy(self):
        original = fixture_input_and_execution.valid_web_contract()
        result = fixture_input_and_execution.compile_request(
            fixture_input_and_execution.compact(original)
        )
        self.assertEqual(result["tag_policies"], original["tag_policies"])
        self.assertEqual(result["consent_policies"], original["consent_policies"])
        self.assertEqual(len(result["implementation"]["objects"]), 3)
        broken = fixture_input_and_execution.compact(original)
        broken.pop("consent_policies")
        with self.assertRaises(ValueError):
            fixture_input_and_execution.compile_request(broken)

    def test_compiler_closes_reuse_without_unrelated_candidates(self):
        request = fixture_input_and_execution.compact(
            fixture_input_and_execution.valid_web_contract()
        )
        reused = request["objects"].pop()
        reused["action"] = "reuse"
        reused["evidence"].append("container-confirmed")
        unrelated = fixture_input_and_execution.deepcopy(reused)
        unrelated["name"] = "Unrelated trigger"
        request["reuse_candidates"] = [reused, unrelated]
        result = fixture_input_and_execution.compile_request(request)
        self.assertEqual(len(result["implementation"]["objects"]), 3)
        self.assertNotIn("Unrelated trigger", fixture_input_and_execution.json.dumps(result))

    def test_compiler_preserves_authority_and_derives_shared_dependency_demand(self):
        def item(name, requirements, dependencies):
            return {
                "name": name,
                "resource_family": "variable",
                "action": "reuse",
                "object_key": name,
                "target_id": "web",
                "requirement_ids": requirements,
                "depends_on": dependencies,
                "intended": {},
            }

        request = {
            "targets": [{"target_id": "web"}],
            "requirements": [
                {"id": key, "authority": {"locator": "synthetic"}} for key in ["A", "B"]
            ],
            "objects": [item("first", ["A"], ["shared"]), item("second", ["B"], ["detour"])],
            "reuse_candidates": [
                item("shared", [], ["leaf"]),
                item("leaf", [], []),
                item("detour", [], ["longer"]),
                item("longer", [], ["shared"]),
            ],
        }
        # Isolate closure attribution; full contract validity is exercised separately.
        with fixture_input_and_execution.patch(
            "gtm_configure.intake.request.validate_document", side_effect=lambda value: value
        ):
            result = fixture_input_and_execution.compile_request(request)
        objects = {item["name"]: item for item in result["implementation"]["objects"]}
        self.assertEqual(objects["shared"]["requirement_ids"], [])
        self.assertEqual(objects["leaf"]["requirement_ids"], [])
        from gtm_configure.domain.graph import served_requirements

        graph = {key: {**row, "dependencies": row["depends_on"]} for key, row in objects.items()}
        self.assertEqual(served_requirements(graph)["leaf"], {"A", "B"})


class TestNativeBoundaries(fixture_native_boundaries.NativeBoundaryTestsFixture):
    def test_sequencing_compiler_wire_readback_and_fresh_resume(self):
        for representation in ("name", "tagId"):
            with self.subTest(representation=representation):
                req = fixture_native_boundaries.additional_request()
                owner = next(
                    o
                    for o in req["objects"]
                    if o["action"] == "reuse" and o["resource_family"] == "tag"
                )
                owner["action"] = "create"
                main = req["objects"][0]
                main["intended"]["setupTag"] = [
                    {"tagName": "web-main::tag::CMP defaults", "stopOnSetupFailure": True}
                ]
                main["intended"]["teardownTag"] = [
                    {"tagName": "web-main::tag::CMP defaults", "stopTeardownOnFailure": False}
                ]
                profile = {
                    **fixture_native_boundaries.PROFILE,
                    "sequencing_reference": representation,
                }
                backend = fixture_native_boundaries.FakeGtm(req)

                def call(tool, args):
                    config = args.get("createOrUpdateConfig", {})
                    for field in ("setupTag", "teardownTag"):
                        for row in config.get(field, []):
                            expected = next(
                                t
                                for t in backend.data["tag"].values()
                                if t["name"] == "CMP defaults"
                            )
                            self.assertEqual(row["tagName"], expected[representation])
                    return backend.call(tool, args)

                registry, _ = self.start(req, call, profile)
                fixture_native_boundaries.execute_ready_operations(self.path, registry)
                self.assert_configured(registry)
                fresh, _ = self.registry(req, call, profile)
                fixture_native_boundaries.execute_ready_operations(self.path, fresh)
                self.assert_configured(fresh)
                self.assertEqual(len(backend.writes), 2)


class TestGoogleSettings(fixture_google_settings.GoogleTagInheritanceTestFixture):
    def test_inheritance_and_compiler_derivation(self):
        contract, operations, event, base, mapping = fixture_google_settings.inherited_mapping()
        self.assertEqual(self.check_mapping(operations, mapping), [])
        self.assertIs(
            fixture_google_settings.associated_google_tag(event, operations), base["intended"]
        )
        compact = {
            "requirements": contract["requirements"],
            "tag_policies": [],
            "field_bindings": [],
        }
        compact["requirements"][0]["parameters"]["lead_type"]["missing_behavior"] = (
            "omit when absent"
        )
        fixture_google_settings.derive_exact_declarations(compact, operations)
        self.assertEqual(
            compact["field_bindings"][0]["owner_object_key"], "web-main::variable::Shared"
        )
        self.assertEqual(compact["field_bindings"][0]["gtm_resolution"], "{{DLV - lead_type}}")


class TestMutationRecovery(fixture_mutation_recovery.NativeAndRecoveryTestsFixture):
    def test_native_authoring_rejects_known_bad_shapes(self):
        def reject(message):
            raise ValueError(message)

        bad = [
            ("trigger", {"type": "customEvent", "customEventFilter": "purchase"}),
            ("tag", {"type": "gaawe", "parameter": [{"key": "sendEcommerce", "value": "true"}]}),
            (
                "tag",
                {
                    "type": "gaawe",
                    "parameter": [
                        {
                            "key": "eventSettingsTable",
                            "type": "list",
                            "list": [
                                {
                                    "type": "map",
                                    "map": [
                                        {"key": "name", "value": "currency"},
                                        {"key": "value", "value": "EUR"},
                                    ],
                                }
                            ],
                        }
                    ],
                },
            ),
        ]
        for family, native in bad:
            with self.subTest(native=native), self.assertRaises(ValueError):
                fixture_mutation_recovery.validate_native_authoring(
                    family, native, path="test", fail=reject
                )
        fixture_mutation_recovery.validate_native_authoring(
            "tag",
            {
                "type": "gaawe",
                "parameter": [
                    {"key": "sendEcommerceData", "type": "boolean", "value": "true"},
                    {"key": "getEcommerceDataFrom", "type": "template", "value": "dataLayer"},
                ],
            },
            path="test",
            fail=reject,
        )


class TestConsentAndFields(fixture_consent_and_fields.UtilityCorrectionsFixture):
    def test_unbound_fields_rejected_by_compiler_and_contract_before_adapter(self):
        req = fixture_consent_and_fields.request()
        contract = fixture_consent_and_fields.compile_request(req)
        field = {
            "source": "form.id",
            "source_shape": "scalar:string",
            "destination_shape": "scalar:string",
            "provenance": {"grade": "approved-input", "locator": "Approved form ID"},
        }
        req["requirements"][0]["parameters"]["form_id"] = field
        contract["requirements"][0]["parameters"]["form_id"] = field
        for function, value in (
            (fixture_consent_and_fields.compile_request, req),
            (fixture_consent_and_fields.validate_document, contract),
        ):
            with (
                self.subTest(function=function.__name__),
                self.assertRaisesRegex(ValueError, "Bind approved fields before execution"),
            ):
                function(value)


class TestTransportAndState(fixture_transport_and_state.UtilityEvolutionTestFixture):
    def test_field_bindings_cannot_rewrite_approved_sources(self):
        contract = fixture_transport_and_state.ads_transport_contract()
        contract["implementation"]["field_bindings"][0]["source"] = "unapproved.path"
        with self.assertRaisesRegex(
            fixture_transport_and_state.ContractValidationError, "source.*unexpected"
        ):
            fixture_transport_and_state.validate_document(contract)
