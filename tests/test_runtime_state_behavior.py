"""Behavioral tests owned by runtime state."""

from support import durable_evidence as fixture_durable_evidence
from support import phase_contracts as fixture_phase_contracts
from support import transport_and_state as fixture_transport_and_state


class TestDurableEvidence(fixture_durable_evidence.CurrentRegressionHardeningTestFixture):
    def test_reopen_clears_stale_saved_evidence(self) -> None:
        run = fixture_durable_evidence.materialize(fixture_durable_evidence.valid_web_contract())
        operation = next(item for item in run["object_changes"] if not item["dependencies"])
        run = fixture_durable_evidence.checkpoint_operation(
            run,
            operation_id=operation["operation_id"],
            state="in_progress",
            note="write started",
        )
        saved = fixture_durable_evidence.expected_graph(operation)
        run = fixture_durable_evidence.checkpoint_operation(
            run,
            operation_id=operation["operation_id"],
            state="saved",
            note="saved before downstream rejection",
            saved=saved,
        )
        run = fixture_durable_evidence.checkpoint_operation(
            run,
            operation_id=operation["operation_id"],
            state="failed",
            note="downstream target rejected the object",
        )
        reopened = fixture_durable_evidence.reopen_failed_operation(
            run,
            operation_id=operation["operation_id"],
            note="approved retry",
        )
        current = next(
            item
            for item in reopened["object_changes"]
            if item["operation_id"] == operation["operation_id"]
        )
        self.assertEqual(current["state"], "planned")
        self.assertNotIn("saved_readback", current)
        self.assertNotIn("comparison", current)

    def test_target_sources_dependencies_and_web_decisions_are_materialization_owned(self) -> None:
        for mutation in (
            lambda run: run["run"]["targets"][0].__setitem__("container_id", "GTM-TAMPER"),
            lambda run: run["official_sources"][0].__setitem__("url", "https://example.test"),
            lambda run: run["tag_policies"][0].__setitem__("blocking_event_scope", "purchase"),
        ):
            run = fixture_durable_evidence.materialize(
                fixture_durable_evidence.valid_pipeline_contract()
            )
            mutation(run)
            with self.assertRaisesRegex(
                fixture_durable_evidence.RunValidationError,
                "differs from the authorized target|differ from deterministic materialization",
            ):
                fixture_durable_evidence.validate_run(run)

    def test_forged_verified_state_cannot_finalize(self) -> None:
        run = fixture_durable_evidence.materialize(fixture_durable_evidence.valid_web_contract())
        for operation in run["object_changes"]:
            operation["state"] = "verified"
        for baseline in run["container_baselines"]:
            baseline["complete"] = True
        with self.assertRaisesRegex(
            fixture_durable_evidence.RunValidationError, "comparison|saved_readback"
        ):
            fixture_durable_evidence.finalize_adapter_verified_document(run)

    def test_last_verified_follows_checkpoint_order_per_target(self) -> None:
        run = fixture_durable_evidence.materialize(
            fixture_durable_evidence.valid_pipeline_contract()
        )
        pending = {item["operation_id"]: item for item in run["object_changes"]}
        last_verified = {target["target_id"]: None for target in run["run"]["targets"]}
        while pending:
            operation = next(
                item
                for item in reversed(list(pending.values()))
                if not any(dependency in pending for dependency in item["dependencies"])
            )
            operation_id = operation["operation_id"]
            run = fixture_durable_evidence.checkpoint_operation(
                run,
                operation_id=operation_id,
                state="verified",
                note="Authoritative readback matched.",
                saved=fixture_durable_evidence.expected_graph(operation),
                timestamp="2026-09-28T14:00:00Z",
            )
            pending.pop(operation_id)
            last_verified[operation["target_id"]] = operation_id
            self.assertEqual(
                {
                    item["target_id"]: item["last_verified_operation_id"]
                    for item in run["target_results"]
                },
                last_verified,
            )

    def test_checkpoint_rejects_readback_that_its_state_would_discard(self) -> None:
        run = fixture_durable_evidence.materialize(fixture_durable_evidence.valid_web_contract())
        operation = run["object_changes"][0]
        with self.assertRaisesRegex(
            fixture_durable_evidence.RunValidationError, "saved readback is accepted only"
        ):
            fixture_durable_evidence.checkpoint_operation(
                run,
                operation_id=operation["operation_id"],
                state="failed",
                note="Rejected write with contradictory readback input.",
                saved=fixture_durable_evidence.expected_graph(operation),
            )


class TestTransportAndState(fixture_transport_and_state.UtilityEvolutionTestFixture):
    def test_skipped_work_cannot_release_dependencies_or_complete(self):
        run = fixture_transport_and_state.with_complete_baselines(
            fixture_transport_and_state.create_from_contract(
                fixture_transport_and_state.valid_web_contract(),
                run_id="SKIP",
                source_locator="synthetic",
            )
        )
        trigger = next(
            item for item in run["object_changes"] if item["resource_family"] == "trigger"
        )
        run = fixture_transport_and_state.checkpoint_operation(
            run, operation_id=trigger["operation_id"], state="skipped", note="Not implemented"
        )
        tag = next(item for item in run["object_changes"] if item["resource_family"] == "tag")
        self.assertIn(
            tag["operation_id"],
            fixture_transport_and_state.inspect_document(run)["blocked_operations"],
        )
        for operation in list(run["object_changes"]):
            if operation["state"] == "planned":
                run = fixture_transport_and_state.checkpoint_operation(
                    run,
                    operation_id=operation["operation_id"],
                    state="skipped",
                    note="Not implemented",
                )
        with self.assertRaisesRegex(fixture_transport_and_state.RunValidationError, "incomplete"):
            fixture_transport_and_state.run_state.finalize_adapter_verified_document(run)

    def test_valid_raw_rest_event_selector_materializes(self):
        contract = fixture_transport_and_state.valid_server_contract()
        trigger = next(
            item
            for item in contract["implementation"]["objects"]
            if item["resource_family"] == "trigger"
        )
        trigger["intended"]["customEventFilter"] = [
            fixture_transport_and_state.condition("equals", "page_view")
        ]
        fixture_transport_and_state.approve_mutations(contract)
        self.assertEqual(
            fixture_transport_and_state.create_from_contract(
                contract, run_id="RAW", source_locator="synthetic"
            )["run"]["mode"],
            "server",
        )

    def test_unknown_materialization_and_forged_completion_are_rejected(self):
        run = fixture_transport_and_state.create_from_contract(
            fixture_transport_and_state.valid_web_contract(),
            run_id="FORGE",
            source_locator="synthetic",
        )
        run["run"]["materialization"]["method"] = "arbitrary-method"
        with self.assertRaisesRegex(
            fixture_transport_and_state.RunValidationError, "materialization"
        ):
            fixture_transport_and_state.validate_run(run)
        run = fixture_transport_and_state.create_from_contract(
            fixture_transport_and_state.valid_web_contract(),
            run_id="FORGE",
            source_locator="synthetic",
        )
        run["run"]["status"] = "Configured"
        with self.assertRaisesRegex(fixture_transport_and_state.RunValidationError, "Configured"):
            fixture_transport_and_state.validate_run(run)

    def test_direct_checkpoint_cannot_bypass_dependencies(self):
        run = fixture_transport_and_state.with_complete_baselines(
            fixture_transport_and_state.create_from_contract(
                fixture_transport_and_state.valid_web_contract(),
                run_id="ORDER",
                source_locator="synthetic",
            )
        )
        consumer = next(item for item in run["object_changes"] if item["dependencies"])
        with self.assertRaisesRegex(
            fixture_transport_and_state.RunValidationError, "every dependency"
        ):
            fixture_transport_and_state.checkpoint_operation(
                run, operation_id=consumer["operation_id"], state="in_progress", note="Too early"
            )


class TestPhaseContracts(fixture_phase_contracts.CurrentContractAndRunTestFixture):
    def test_all_three_routes_validate_and_materialize(self) -> None:
        for builder, expected_operations in (
            (fixture_phase_contracts.valid_web_contract, 3),
            (fixture_phase_contracts.valid_server_contract, 3),
            (fixture_phase_contracts.valid_pipeline_contract, 5),
        ):
            with self.subTest(builder=builder.__name__):
                contract = fixture_phase_contracts.validate_contract(builder())
                run = fixture_phase_contracts.create_from_contract(
                    contract,
                    run_id=f"RUN-{contract['mode']}",
                    source_locator="approved input",
                    timestamp="2026-08-18T00:00:00Z",
                )
                self.assertEqual(run["schema_version"], "9.0")
                self.assertEqual(run["run"]["mode"], contract["mode"])
                self.assertEqual(len(run["object_changes"]), expected_operations)
                self.assertEqual(
                    {item["target_id"] for item in run["object_changes"]},
                    {item["target_id"] for item in contract["implementation"]["objects"]},
                )

    def test_materialization_is_deterministic_and_contract_owned(self) -> None:
        contract = fixture_phase_contracts.valid_pipeline_contract()
        first = fixture_phase_contracts.create_from_contract(
            contract,
            run_id="RUN-DETERMINISTIC",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        second = fixture_phase_contracts.create_from_contract(
            contract,
            run_id="RUN-DETERMINISTIC",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        self.assertEqual(first, second)
        tampered = fixture_phase_contracts.deepcopy(first)
        tampered["pipelines"][0]["transport_owner"] = "manual override"
        with self.assertRaisesRegex(
            fixture_phase_contracts.RunValidationError, "differ from deterministic materialization"
        ):
            from gtm_configure.runtime.validation import validate_document

            validate_document(tampered)
