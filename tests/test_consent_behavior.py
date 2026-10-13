"""Behavioral tests owned by consent."""

from support import consent_and_fields as fixture_consent_and_fields
from support import durable_evidence as fixture_durable_evidence
from support import google_settings as fixture_google_settings
from support import mutation_recovery as fixture_mutation_recovery
from support import native_boundaries as fixture_native_boundaries
from support import phase_contracts as fixture_phase_contracts
from support import transport_and_state as fixture_transport_and_state


class TestNativeBoundaries(fixture_native_boundaries.NativeBoundaryTestsFixture):
    def test_builtin_semantic_consent_initialization_executes_and_converges(self):
        for ref in ("2147479572", "web-main::trigger::builtin::2147479572"):
            with self.subTest(reference=ref):
                req = fixture_native_boundaries.additional_request()
                owner = next(
                    o
                    for o in req["objects"]
                    if o["resource_family"] == "tag" and o["action"] == "reuse"
                )
                owner["action"] = "create"
                owner["intended"]["firingTriggerId"] = [ref]
                backend = fixture_native_boundaries.FakeGtm(req)
                registry, _ = self.start(req, backend.call)
                fixture_native_boundaries.execute_ready_operations(self.path, registry)
                self.assert_configured(registry)
                self.assertEqual(len(backend.writes), 2)
                saved = next(v for v in backend.data["tag"].values() if v["name"] == owner["name"])
                self.assertEqual(saved["firingTriggerId"], ["2147479572"])


class TestPhaseContracts(fixture_phase_contracts.CurrentContractAndRunTestFixture):
    def test_consent_rejects_accidental_double_gate_and_missing_event_coverage(self) -> None:
        contract = fixture_phase_contracts.valid_pipeline_contract()
        topology = contract["consent_topologies"][0]
        topology.update(
            {
                "signal_authority": "third-party-cmp",
                "server_signal_path": "cmp.analytics.allowed",
                "unknown_state_behavior": "deny",
                "transport_behavior": "blocked",
                "transporter_tag_keys": [],
                "server_enforcement": {"mechanism": "server-template-native-consent"},
            }
        )
        with self.assertRaisesRegex(
            fixture_phase_contracts.ContractValidationError, "duplicates a transport block"
        ):
            fixture_phase_contracts.validate_contract(contract)

        contract = fixture_phase_contracts.valid_pipeline_contract()
        contract["consent_topologies"][0]["event_coverage"] = ["purchase"]
        with self.assertRaisesRegex(
            fixture_phase_contracts.RunValidationError, "missing transported event coverage"
        ):
            fixture_phase_contracts.create_from_contract(
                contract,
                run_id="RUN-CONSENT",
                source_locator="approved input",
                timestamp="2026-08-18T00:00:00Z",
            )


class TestDurableEvidence(fixture_durable_evidence.CurrentRegressionHardeningTestFixture):
    def test_pipeline_owners_dedup_and_consent_must_bind_real_objects(self) -> None:
        contract = fixture_durable_evidence.valid_pipeline_contract()
        contract["pipelines"][0]["field_flows"][0]["receiver_owner"] = (
            "server-main::tag::Forged receiver"
        )
        with self.assertRaisesRegex(
            fixture_durable_evidence.ContractValidationError, "receiver_owner"
        ):
            fixture_durable_evidence.validate_contract(contract)

        contract = fixture_durable_evidence.valid_pipeline_contract()
        field = contract["pipelines"][0]["field_flows"][0]
        field["wire"]["shape"] = "object"
        field["transformation_owner"] = "server-main::transformation::Forged"
        with self.assertRaisesRegex(
            fixture_durable_evidence.ContractValidationError, "transformation_owner"
        ):
            fixture_durable_evidence.validate_contract(contract)

        contract = fixture_durable_evidence.add_nonpurchase_dual_dedup(
            fixture_durable_evidence.valid_pipeline_contract()
        )
        contract["dedup_contracts"][0]["source_variable_key"] = (
            "web-main::variable::Missing shared ID"
        )
        with self.assertRaisesRegex(
            fixture_durable_evidence.ContractValidationError, "sender web variable"
        ):
            fixture_durable_evidence.validate_contract(contract)

        contract = fixture_durable_evidence.add_nonpurchase_dual_dedup(
            fixture_durable_evidence.valid_pipeline_contract()
        )
        transporter_key = contract["dedup_contracts"][0]["transporter_consumer_keys"][0]
        transporter = next(
            item
            for item in contract["implementation"]["objects"]
            if item["object_key"] == transporter_key
        )
        transporter["intended"].pop("event_id")
        fixture_durable_evidence.approve_mutations(contract)
        with self.assertRaisesRegex(
            fixture_durable_evidence.ContractValidationError, "does not use the shared ID"
        ):
            fixture_durable_evidence.validate_contract(contract)

    def test_server_tags_require_real_firing_and_consent_bindings(self) -> None:
        contract = fixture_durable_evidence.valid_server_contract()
        contract["implementation"]["objects"][1]["intended"]["firingTriggerId"] = []
        fixture_durable_evidence.approve_mutations(contract)
        with self.assertRaisesRegex(
            fixture_durable_evidence.ContractValidationError, "firingTriggerId"
        ):
            fixture_durable_evidence.validate_contract(contract)

        contract = fixture_durable_evidence.valid_server_contract()
        contract["consent_topologies"] = []
        with self.assertRaisesRegex(
            fixture_durable_evidence.ContractValidationError, "consent topology"
        ):
            fixture_durable_evidence.validate_contract(contract)

        contract = fixture_durable_evidence.add_nonpurchase_dual_dedup(
            fixture_durable_evidence.valid_pipeline_contract()
        )
        contract["pipelines"][0]["field_flows"] = [
            field
            for field in contract["pipelines"][0]["field_flows"]
            if field["event_data"]["path"] != "cmp_meta_allowed"
        ]
        with self.assertRaisesRegex(fixture_durable_evidence.ContractValidationError, "CMP signal"):
            fixture_durable_evidence.validate_contract(contract)

    def test_transporter_is_not_vendor_blocked_by_default(self) -> None:
        contract = fixture_durable_evidence.valid_pipeline_contract()
        transporter = contract["implementation"]["objects"][0]
        transporter["intended"]["blockingTriggerId"] = [
            "web-main::trigger::CMP - Analytics granted"
        ]
        fixture_durable_evidence.approve_mutations(contract)
        with self.assertRaisesRegex(
            fixture_durable_evidence.ContractValidationError, "must not carry"
        ):
            fixture_durable_evidence.validate_contract(contract)

        contract = fixture_durable_evidence.valid_pipeline_contract()
        topology = contract["consent_topologies"][0]
        topology["intentional_double_gate"] = True
        topology["double_gate_justification"] = "Declared twice without two configurable gates."
        with self.assertRaisesRegex(
            fixture_durable_evidence.ContractValidationError, "without two configurable gates"
        ):
            fixture_durable_evidence.validate_contract(contract)


class TestMutationRecovery(fixture_mutation_recovery.NativeAndRecoveryTestsFixture):
    def test_consent_default_equivalence_is_exact_and_evidence_is_retained(self):
        operation = {
            "operation_id": "o",
            "target_id": "web",
            "resource_family": "tag",
            "container_type": "web",
            "name": "tag",
            "action": "create",
            "intended": {"type": "gaawe"},
        }
        saved = fixture_mutation_recovery.expected_graph(operation)
        saved["objects"][0]["consentSettings"] = {"consentStatus": "notSet"}
        comparison, evidence = fixture_mutation_recovery.build_verification_comparison(
            operation, saved
        )
        self.assertTrue(comparison["pass"])
        self.assertIn("consentSettings", evidence["objects"][0])
        for consent in (
            {"consentStatus": "needed"},
            {"consentStatus": "notSet", "extra": True},
            {},
        ):
            saved["objects"][0]["consentSettings"] = consent
            self.assertFalse(
                fixture_mutation_recovery.build_verification_comparison(operation, saved)[0]["pass"]
            )


class TestConsentAndFields(fixture_consent_and_fields.UtilityCorrectionsFixture):
    def test_ungated_policy_is_not_limited_to_google_tags(self):
        req = fixture_consent_and_fields.ungated_request()
        req["route"] = "media"
        req["requirements"][0].update(destination="Meta", event_name="Lead")
        req["consent_topologies"][0]["destination"] = "Meta"
        req["objects"][0]["intended"].update(
            type="cvt_42",
            parameter=[
                fixture_consent_and_fields.param("pixelId", "123456"),
                fixture_consent_and_fields.param("eventName", "Lead"),
            ],
        )
        req["execution_topologies"][0]["built_in_consent_checks"] = []
        doc, backend = fixture_consent_and_fields.execute(req)
        self.assertEqual(doc["run"]["status"], "Configured")
        self.assertEqual(len(backend.writes), 1)

    def test_additional_convention_executes_through_contract_and_runtime(self):
        doc, backend = fixture_consent_and_fields.execute(
            fixture_consent_and_fields.additional_request()
        )
        self.assertEqual(doc["run"]["status"], "Configured")
        self.assertEqual(len(backend.writes), 1)

    def test_ungated_policy_requires_authority_and_scope(self):
        for field in ("locator", "scope", "grade"):
            req = fixture_consent_and_fields.ungated_request()
            del req["consent_topologies"][0]["web_enforcement"]["client_policy"][field]
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(ValueError, "approved-input client_policy"),
            ):
                fixture_consent_and_fields.compile_request(req)

    def test_ungated_policy_rejects_cmp_behavior(self):
        req = fixture_consent_and_fields.ungated_request()
        req["execution_topologies"][0].update(may_precede_cmp=True, pre_cmp_policy="drop")
        with self.assertRaisesRegex(ValueError, "pre_cmp_policy"):
            fixture_consent_and_fields.compile_request(req)

    def test_existing_firing_convention_executes(self):
        doc, backend = fixture_consent_and_fields.execute(
            fixture_consent_and_fields.firing_request()
        )
        self.assertEqual(doc["run"]["status"], "Configured")
        self.assertEqual(len(backend.writes), 1)

    def test_firing_proof_cannot_cover_an_ungated_trigger(self):
        req = fixture_consent_and_fields.firing_request()
        del req["reuse_candidates"][0]["intended"]["filter"]
        with self.assertRaisesRegex(ValueError, "Every firing trigger"):
            fixture_consent_and_fields.compile_request(req)

    def test_additional_checks_require_real_denied_default_and_initialization(self):
        execution = {
            "tag_object_key": "event",
            "blocking_trigger_keys": [],
            "blocking_event_scope": None,
            "lifecycle_role": "event-driven",
            "firing_option": "once-per-event",
            "additional_consent_checks": ["analytics_storage"],
        }
        enforcement = {
            "mechanism": "additional-consent-checks",
            "evidence": "Inspected CMP template default and updates",
            "default_bindings": {
                "analytics_storage": {
                    "object_key": "cmp",
                    "field_path": ["parameter", "analytics_storage", "value"],
                }
            },
        }
        operations = {
            "event": {"depends_on": ["cmp"]},
            "cmp": {
                "action": "reuse",
                "resource_family": "tag",
                "intended": {
                    "type": "cvt_42",
                    "firingTriggerId": ["2147479572"],
                    "parameter": [fixture_consent_and_fields.param("analytics_storage", "denied")],
                },
            },
        }

        def fail(message):
            raise ValueError(message)

        fixture_consent_and_fields.validate_convention(execution, enforcement, operations, fail)
        operations["cmp"]["intended"]["parameter"][0]["value"] = "granted"
        with self.assertRaisesRegex(ValueError, "resolve to denied"):
            fixture_consent_and_fields.validate_convention(execution, enforcement, operations, fail)
        operations["cmp"]["intended"]["parameter"][0]["value"] = "denied"
        operations["cmp"]["intended"]["firingTriggerId"] = ["2147479573"]
        with self.assertRaisesRegex(ValueError, "Consent Initialization"):
            fixture_consent_and_fields.validate_convention(execution, enforcement, operations, fail)


class TestTransportAndState(fixture_transport_and_state.UtilityEvolutionTestFixture):
    def test_basic_cannot_mean_always_on_google_native_transport(self):
        contract = fixture_transport_and_state.valid_pipeline_contract()
        contract["consent_topologies"][0]["consent_mode"] = "strict-basic"
        contract["execution_topologies"][0]["consent_mode"] = "strict-basic"
        with self.assertRaisesRegex(
            fixture_transport_and_state.ContractValidationError, "strict-basic cannot"
        ):
            fixture_transport_and_state.validate_document(contract)
        self.assertEqual(
            fixture_transport_and_state.validate_document(
                fixture_transport_and_state.valid_pipeline_contract()
            )["consent_topologies"][0]["consent_mode"],
            "advanced-native",
        )

    def test_explicit_basic_blocked_transport_remains_feasible(self):
        contract = fixture_transport_and_state.valid_pipeline_contract()
        web = fixture_transport_and_state.valid_web_contract()
        block = fixture_transport_and_state.deepcopy(web["implementation"]["objects"][-1])
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
        fixture_transport_and_state.approve_mutations(contract)
        run = fixture_transport_and_state.create_from_contract(
            contract, run_id="BASIC", source_locator="synthetic explicit basic authority"
        )
        self.assertEqual(run["consent_topologies"][0]["consent_mode"], "strict-basic")


class TestGoogleSettings(fixture_google_settings.BuiltInTriggerTestFixture):
    def test_builtin_initialization_at_full_contract_boundary(self):
        contract = fixture_google_settings.valid_pipeline_contract()
        owner = contract["implementation"]["objects"][0]
        owner["intended"]["firingTriggerId"] = ["2147479573"]
        contract["execution_topologies"][0]["normal_triggers"] = [
            {
                "trigger_object_key": "2147479573",
                "role": "initialization-page-load",
                "type": "initialization",
            }
        ]
        fixture_google_settings.approve_mutations(contract)
        fixture_google_settings.create_from_contract(
            contract, run_id="BUILTIN", source_locator="approved"
        )
