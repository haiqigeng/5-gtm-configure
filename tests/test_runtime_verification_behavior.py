"""Behavioral tests owned by runtime verification."""

from support import adapters as fixture_adapters
from support import durable_evidence as fixture_durable_evidence
from support import native_execution as fixture_native_execution
from support import phase_contracts as fixture_phase_contracts
from support import transport_and_state as fixture_transport_and_state


class TestPhaseContracts(fixture_phase_contracts.CurrentContractAndRunTestFixture):
    def test_manual_checkpoints_cannot_reach_configured_without_adapter_convergence(self) -> None:
        run = fixture_phase_contracts.create_from_contract(
            fixture_phase_contracts.valid_pipeline_contract(cutover=True),
            run_id="RUN-CONTROLLER-WORKFLOW",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        for target in run["run"]["targets"]:
            families = sorted(
                {
                    operation["resource_family"]
                    for operation in run["object_changes"]
                    if operation["target_id"] == target["target_id"]
                }
            )
            resources = {family: [] for family in families}
            run = fixture_phase_contracts.record_target_baseline(
                run,
                target_id=target["target_id"],
                resources=resources,
                captured_at="2026-08-18T00:00:01Z",
                preexisting_workspace_changes=[],
                capture_evidence=fixture_phase_contracts.complete_capture_evidence(
                    resources, target
                ),
            )
        pending = {item["operation_id"]: item for item in run["object_changes"]}
        while pending:
            progressed = False
            for operation_id, operation in list(pending.items()):
                if any(dependency in pending for dependency in operation["dependencies"]):
                    continue
                pre_write = None
                if operation["action"] in {
                    "update",
                    "replace",
                    "rename",
                    "pause",
                    "unpause",
                    "remove",
                }:
                    pre_write = {"name": operation["name"], **operation["pre_change"]}
                    pre_write["tagId"] = operation.get("object_id", "tag-100")
                run = fixture_phase_contracts.checkpoint_operation(
                    run,
                    operation_id=operation_id,
                    state="verified",
                    note="Authoritative readback matched.",
                    pre_write_saved=pre_write,
                    saved=fixture_phase_contracts.expected_graph(operation),
                )
                pending.pop(operation_id)
                progressed = True
            self.assertTrue(progressed)
        self.assertNotEqual(run["run"]["status"], "Configured")


class TestAdapters(fixture_adapters.CurrentAdapterRuntimeTestFixture):
    def test_fresh_read_only_convergence_is_required_for_finalization(self) -> None:
        run = fixture_adapters.with_complete_baselines(
            fixture_adapters.create_from_contract(
                fixture_adapters.valid_web_contract(),
                run_id="RUN-CONVERGENCE",
                source_locator="approved input",
                timestamp="2026-08-18T00:00:00Z",
            )
        )
        target = run["run"]["targets"][0]
        adapter = fixture_adapters.FakeAdapter()
        adapter.bind_target(target)
        registry = fixture_adapters.TargetAdapterRegistry()
        registry.register(target, adapter, fixture_adapters.capabilities("tag", "trigger"))
        with fixture_adapters.tempfile.TemporaryDirectory() as temporary:
            path = fixture_adapters.Path(temporary) / "run.json"
            fixture_adapters.atomic_write(path, run)
            fixture_adapters.execute_ready_operations(
                path,
                registry,
                timestamp=lambda: "2026-08-18T00:00:01Z",
                sleep=lambda _: None,
            )
            mutation_count = len(adapter.mutations)
            proof = fixture_adapters.verify_idempotent_rerun(
                path, registry, timestamp=lambda: "2026-08-18T00:00:02Z"
            )
            self.assertTrue(proof["checked"])
            self.assertEqual(len(proof["observations"]), len(run["object_changes"]))
            self.assertEqual(len(adapter.mutations), mutation_count)
            configured = fixture_adapters.load_document(path)
            self.assertEqual(configured["run"]["status"], "Configured")

    def test_convergence_mismatch_records_required_action_and_blocks_finalization(self) -> None:
        run = fixture_adapters.with_complete_baselines(
            fixture_adapters.create_from_contract(
                fixture_adapters.valid_web_contract(),
                run_id="RUN-DRIFT",
                source_locator="approved input",
            )
        )
        target = run["run"]["targets"][0]
        adapter = fixture_adapters.FakeAdapter()
        adapter.bind_target(target)
        registry = fixture_adapters.TargetAdapterRegistry()
        registry.register(target, adapter, fixture_adapters.capabilities("tag", "trigger"))
        with fixture_adapters.tempfile.TemporaryDirectory() as temporary:
            path = fixture_adapters.Path(temporary) / "run.json"
            fixture_adapters.atomic_write(path, run)
            fixture_adapters.execute_ready_operations(path, registry, sleep=lambda _: None)
            drifted_operation = run["object_changes"][0]
            drifted_name = drifted_operation["name"]
            drifted = fixture_adapters.expected_graph(drifted_operation)
            drifted["objects"][0]["type"] = "drifted-type"
            adapter.read_overrides[drifted_name] = drifted
            proof = fixture_adapters.verify_idempotent_rerun(path, registry)
            self.assertFalse(proof["checked"])
            self.assertTrue(proof["remaining_actions"])
            self.assertNotEqual(fixture_adapters.load_document(path)["run"]["status"], "Configured")

    def test_convergence_timestamp_must_follow_operation_verification(self) -> None:
        run = fixture_adapters.with_complete_baselines(
            fixture_adapters.create_from_contract(
                fixture_adapters.valid_web_contract(),
                run_id="RUN-STALE-CONVERGENCE",
                source_locator="approved",
            )
        )
        target = run["run"]["targets"][0]
        adapter = fixture_adapters.FakeAdapter()
        adapter.bind_target(target)
        registry = fixture_adapters.TargetAdapterRegistry()
        registry.register(target, adapter, fixture_adapters.capabilities("tag", "trigger"))
        with fixture_adapters.tempfile.TemporaryDirectory() as temporary:
            path = fixture_adapters.Path(temporary) / "run.json"
            fixture_adapters.atomic_write(path, run)
            fixture_adapters.execute_ready_operations(
                path,
                registry,
                timestamp=lambda: "2026-08-18T00:00:01Z",
                sleep=lambda _: None,
            )
            with self.assertRaisesRegex(Exception, "newer than verification"):
                fixture_adapters.verify_idempotent_rerun(
                    path, registry, timestamp=lambda: "2026-08-18T00:00:01Z"
                )


class TestDurableEvidence(fixture_durable_evidence.CurrentRegressionHardeningTestFixture):
    def test_remove_is_verified_by_authoritative_absence(self) -> None:
        contract = fixture_durable_evidence.valid_web_contract()
        action = contract["implementation"]["objects"][0]
        # Removing this tag does not require creating its former trigger references.
        action["depends_on"] = []
        pre_change = fixture_durable_evidence.deepcopy(action["intended"])
        action.update(
            {
                "action": "remove",
                "object_id": "tag-100",
                "pre_change": pre_change,
                "evidence": ["approved-input", "official-current", "container-confirmed"],
                "risk": "high-impact",
            }
        )
        action.pop("intended")
        contract["execution_topologies"] = []
        contract["page_view_decisions"] = []
        fixture_durable_evidence.approve_mutations(contract)
        run = fixture_durable_evidence.materialize(contract)
        operation = run["object_changes"][0]
        prewrite, safe_pre_change = fixture_durable_evidence.build_pre_write_comparison(
            operation, {"name": operation["name"], **pre_change}
        )
        comparison, safe_saved = fixture_durable_evidence.build_verification_comparison(
            operation, None
        )
        self.assertTrue(prewrite["pass"])
        self.assertTrue(comparison["pass"])
        verified = fixture_durable_evidence.checkpoint_operation(
            run,
            operation_id=operation["operation_id"],
            state="verified",
            note="Authoritative get returned not found after remove.",
            pre_write_comparison=prewrite,
            pre_write_saved=safe_pre_change,
            comparison=comparison,
            saved=safe_saved,
        )
        self.assertIsNone(verified["object_changes"][0]["saved_readback"])


class TestNativeExecutionNativeCorrections(fixture_native_execution.NativeCorrectionsTestsFixture):
    def test_empty_optional_parameter_readback_and_prewrite_only(self):
        op = fixture_native_execution.operation("tag")
        op["intended"] = {"type": "gclidw", "parameter": []}
        original = fixture_native_execution.deepcopy(op)
        saved = fixture_native_execution.expected_graph(op)
        del saved["objects"][0]["parameter"]
        self.assertTrue(
            fixture_native_execution.build_verification_comparison(op, saved)[0]["pass"]
        )
        self.assertEqual(op, original)
        op["action"] = "update"
        op["pre_change"] = {"type": "gclidw", "parameter": []}
        self.assertTrue(
            fixture_native_execution.build_pre_write_comparison(
                op, {"name": "Fixture", "type": "gclidw"}
            )[0]["pass"]
        )
        saved["objects"][0]["parameter"] = [{"type": "template", "key": "retained", "value": "yes"}]
        self.assertFalse(
            fixture_native_execution.build_verification_comparison(op, saved)[0]["pass"]
        )
        for field in ("firingTriggerId", "blockingTriggerId"):
            op["intended"][field] = []
            self.assertFalse(
                fixture_native_execution.build_verification_comparison(
                    op, fixture_native_execution.expected_graph(original)
                )[0]["pass"]
            )
            del op["intended"][field]


class TestNativeExecutionRecoveryCorrections(
    fixture_native_execution.RecoveryCorrectionsTestsFixture
):
    def test_recovered_drift_requires_fresh_convergence_without_losing_journal(self):
        with fixture_native_execution.tempfile.TemporaryDirectory() as directory:
            run = fixture_native_execution.create_from_contract(
                fixture_native_execution.valid_web_contract(),
                run_id="recovery",
                source_locator="synthetic",
            )
            path = fixture_native_execution.Path(directory) / "run.json"
            fixture_native_execution.atomic_write(path, run)
            adapter = fixture_native_execution.FakeAdapter()
            adapter.bind_target(run["run"]["targets"][0])
            registry = fixture_native_execution.TargetAdapterRegistry()
            registry.register(
                run["run"]["targets"][0],
                adapter,
                fixture_native_execution.capabilities("tag", "trigger"),
            )
            fixture_native_execution.execute_ready_operations(path, registry)
            before = fixture_native_execution.deepcopy(adapter.saved)
            name = next(iter(adapter.saved))
            adapter.saved[name]["objects"][0]["notes"] = "drift"
            fixture_native_execution.verify_idempotent_rerun(path, registry)
            failed_convergence = fixture_native_execution.load_document(path)
            self.assertFalse(failed_convergence["idempotency"]["checked"])
            adapter.saved = before
            fixture_native_execution.execute_ready_operations(path, registry)
            recovered = fixture_native_execution.load_document(path)
            self.assertTrue(all(o["state"] == "verified" for o in recovered["object_changes"]))
            self.assertEqual(
                recovered["idempotency"],
                {"checked": False, "remaining_actions": [], "observations": []},
            )
            self.assertTrue(
                any(
                    j.get("convergence_repair")
                    for o in recovered["object_changes"]
                    for j in o["journal"]
                )
            )
            fixture_native_execution.verify_idempotent_rerun(path, registry)
            self.assertTrue(fixture_native_execution.load_document(path)["idempotency"]["checked"])


class TestTransportAndState(fixture_transport_and_state.UtilityEvolutionTestFixture):
    def test_prewrite_ignores_only_root_metadata(self):
        operation = {
            "operation_id": "OP",
            "target_id": "web",
            "resource_family": "tag",
            "name": "Tag",
            "pre_change": {"name": "Tag", "fields": {"value": 1}},
        }
        self.assertTrue(
            fixture_transport_and_state.build_pre_write_comparison(
                operation, {"name": "Tag", "tagId": "1", "fields": {"value": 1}}
            )[0]["pass"]
        )
        self.assertFalse(
            fixture_transport_and_state.build_pre_write_comparison(
                operation, {"name": "Tag", "fields": {"value": True}}
            )[0]["pass"]
        )
        self.assertFalse(
            fixture_transport_and_state.build_pre_write_comparison(
                operation, {"name": "Tag", "fields": {"value": 1, "path": "changed-business-path"}}
            )[0]["pass"]
        )
