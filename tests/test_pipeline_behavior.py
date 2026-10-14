"""Behavioral tests owned by pipeline."""

from support import adapters as fixture_adapters
from support import durable_evidence as fixture_durable_evidence
from support import field_binding as fixture_field_binding
from support import phase_contracts as fixture_phase_contracts
from support import transport_and_state as fixture_transport_and_state


class TestDurableEvidence(fixture_durable_evidence.CurrentRegressionHardeningTestFixture):
    def test_server_only_run_has_ordered_publication_dependencies(self) -> None:
        run = fixture_durable_evidence.materialize(fixture_durable_evidence.valid_server_contract())
        self.assertEqual(
            [item["kind"] for item in run["publication_dependencies"]],
            ["server-recette", "server-publication", "post-publication-smoke"],
        )

    def test_pipeline_requires_exactly_one_flow_for_every_mapped_field_identity(self) -> None:
        contract = fixture_durable_evidence.valid_pipeline_contract()
        contract["pipelines"][0]["field_flows"] = []
        with self.assertRaisesRegex(
            fixture_durable_evidence.ContractValidationError, "misses mapped fields"
        ):
            fixture_durable_evidence.validate_contract(contract)

        contract = fixture_durable_evidence.valid_pipeline_contract()
        contract["pipelines"][0]["field_flows"].append(
            fixture_durable_evidence.deepcopy(contract["pipelines"][0]["field_flows"][0])
        )
        with self.assertRaisesRegex(
            fixture_durable_evidence.ContractValidationError, "duplicates pipeline field flow"
        ):
            fixture_durable_evidence.validate_contract(contract)

        contract = fixture_durable_evidence.valid_web_contract()
        contract["implementation"]["objects"][0]["intended"]["send_page_view"] = False
        fixture_durable_evidence.approve_mutations(contract)
        with self.assertRaisesRegex(
            fixture_durable_evidence.ContractValidationError, "native page_view"
        ):
            fixture_durable_evidence.validate_contract(contract)

    def test_malformed_pipeline_records_fail_as_validation_errors_not_key_errors(self) -> None:
        for field in ("consent_policies", "dedup_contracts"):
            run = fixture_durable_evidence.materialize(
                fixture_durable_evidence.valid_pipeline_contract()
            )
            run[field] = [{}]
            run["run"]["materialization"]["section_fingerprints"] = (
                fixture_durable_evidence.materialization_fingerprints(run)
            )
            with self.subTest(field=field):
                with self.assertRaises(fixture_durable_evidence.RunValidationError):
                    fixture_durable_evidence.validate_run(run)


class TestTransportAndState(fixture_transport_and_state.UtilityEvolutionTestFixture):
    def test_ads_transport_rejects_unproved_and_unauthorized_receivers(self):
        for mutation in ("missing-flow", "wrong-receiver", "wrong-type", "no-ad-user-data"):
            contract = fixture_transport_and_state.ads_transport_contract()
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
            with (
                self.subTest(mutation=mutation),
                self.assertRaises(fixture_transport_and_state.ContractValidationError),
            ):
                fixture_transport_and_state.validate_document(contract)


class TestAdapters(fixture_adapters.CurrentAdapterRuntimeTestFixture):
    def test_cutover_executes_only_after_receiver_operations(self) -> None:
        contract = fixture_adapters.valid_pipeline_contract(cutover=True)
        server = fixture_adapters.FakeAdapter(existing={"GA4 Client - Web transport"})
        web = fixture_adapters.FakeAdapter(existing={"Google tag - Web transport"})
        run, adapters = self._execute(
            contract,
            {
                "web-main": (web, fixture_adapters.capabilities("tag", "trigger"), None),
                "server-main": (
                    server,
                    fixture_adapters.capabilities("client", "tag", "trigger"),
                    None,
                ),
            },
        )
        states = {item["name"]: item["state"] for item in run["object_changes"]}
        self.assertEqual(set(states.values()), {"verified"})
        self.assertEqual(
            adapters["server-main"].mutations,
            ["Event Data - page_view", "GA4 - page_view"],
        )
        self.assertIn("Google tag - Web transport", adapters["web-main"].mutations)
        target_capabilities = {
            target["target_id"]: target["adapter_capabilities"] for target in run["run"]["targets"]
        }
        self.assertTrue(target_capabilities["server-main"]["client"]["get"])
        self.assertTrue(target_capabilities["web-main"]["tag"]["update"])

    def test_container_drift_blocks_only_the_stale_cutover_object(self) -> None:
        contract = fixture_adapters.valid_pipeline_contract(cutover=True)
        server = fixture_adapters.FakeAdapter(existing={"GA4 Client - Web transport"})
        web = fixture_adapters.FakeAdapter(
            read_overrides={
                "Google tag - Web transport": {
                    "type": "googtag",
                    "measurement_id": "G-CHANGED",
                    "native page_view": True,
                    "tagManagerUrl": "https://tagmanager.google.com/ignored-metadata",
                }
            }
        )
        run, adapters = self._execute(
            contract,
            {
                "web-main": (web, fixture_adapters.capabilities("tag", "trigger"), None),
                "server-main": (
                    server,
                    fixture_adapters.capabilities("client", "tag", "trigger"),
                    None,
                ),
            },
        )
        states = {item["name"]: item["state"] for item in run["object_changes"]}
        self.assertEqual(states["Google tag - Web transport"], "failed")
        self.assertEqual(states["GA4 - page_view"], "verified")
        self.assertNotIn("Google tag - Web transport", adapters["web-main"].mutations)
        stale = next(
            item for item in run["object_changes"] if item["name"] == "Google tag - Web transport"
        )
        self.assertEqual(stale["journal"][-1]["error"], "container_drift")


class TestPhaseContracts(fixture_phase_contracts.CurrentContractAndRunTestFixture):
    def test_contract_and_run_schemas_accept_the_canonical_pipeline(self) -> None:
        contract_schema = fixture_phase_contracts.json.loads(
            (
                fixture_phase_contracts.ROOT / "schemas" / "configuration-contract.schema.json"
            ).read_text(encoding="utf-8")
        )
        run_schema = fixture_phase_contracts.json.loads(
            (fixture_phase_contracts.ROOT / "schemas" / "configuration-run.schema.json").read_text(
                encoding="utf-8"
            )
        )
        fixture_phase_contracts.Draft202012Validator.check_schema(contract_schema)
        fixture_phase_contracts.Draft202012Validator.check_schema(run_schema)
        contract = fixture_phase_contracts.valid_pipeline_contract()
        self.assertEqual(
            list(
                fixture_phase_contracts.Draft202012Validator(
                    contract_schema, registry=fixture_phase_contracts.schema_registry()
                ).iter_errors(contract)
            ),
            [],
        )
        run = fixture_phase_contracts.create_from_contract(
            contract,
            run_id="RUN-SCHEMA",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        self.assertEqual(
            list(
                fixture_phase_contracts.Draft202012Validator(
                    run_schema, registry=fixture_phase_contracts.schema_registry()
                ).iter_errors(run)
            ),
            [],
        )

    def test_receiver_dependencies_are_required_before_cutover(self) -> None:
        contract = fixture_phase_contracts.valid_pipeline_contract(cutover=True)
        run = fixture_phase_contracts.create_from_contract(
            contract,
            run_id="RUN-CUTOVER",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        pipeline = run["pipelines"][0]
        cutover = next(
            item
            for item in run["object_changes"]
            if item["operation_id"] == pipeline["cutover_operation_id"]
        )
        self.assertEqual(set(cutover["dependencies"]), set(pipeline["operation_dependencies"]))

        broken = fixture_phase_contracts.valid_pipeline_contract(cutover=True)
        broken["implementation"]["objects"][0]["depends_on"] = []
        with self.assertRaisesRegex(
            fixture_phase_contracts.RunValidationError, "cutover does not depend"
        ):
            fixture_phase_contracts.create_from_contract(
                broken,
                run_id="RUN-BROKEN",
                source_locator="approved input",
                timestamp="2026-08-18T00:00:00Z",
            )

    def test_reused_claiming_client_requires_exact_readback_contract(self) -> None:
        contract = fixture_phase_contracts.valid_pipeline_contract()
        client = contract["implementation"]["objects"][1]
        client.pop("intended")
        with self.assertRaisesRegex(fixture_phase_contracts.ContractValidationError, "intended"):
            fixture_phase_contracts.validate_contract(contract)

        contract = fixture_phase_contracts.valid_pipeline_contract()
        contract["implementation"]["objects"][1]["assertions"]["client_claim"]["description"] = (
            "Different request claim"
        )
        with self.assertRaisesRegex(
            fixture_phase_contracts.ContractValidationError,
            "claiming_client must bind the reviewed native Client assertion",
        ):
            fixture_phase_contracts.validate_contract(contract)


class TestFieldBinding(fixture_field_binding.StartupTestFixture):
    def test_auth_failure_contained_and_dependent_cutover_blocked(self):
        run, adapters, _ = self.run_startup(unavailable=True)
        server = [o for o in run["object_changes"] if o["target_id"] == "server-main"]
        self.assertTrue(all(o["state"] == "planned" for o in server))
        web = {o["name"]: o["state"] for o in run["object_changes"] if o["target_id"] == "web-main"}
        self.assertEqual(web["Google tag - Web transport"], "planned")
        self.assertIn("verified", web.values())
        self.assertEqual(adapters["server-main"].mutations, [])
        self.assertTrue(adapters["web-main"].mutations)
