"""Behavioral tests owned by deduplication."""

from support import durable_evidence as fixture_durable_evidence
from support import mutation_recovery as fixture_mutation_recovery


class TestDurableEvidence(fixture_durable_evidence.CurrentRegressionHardeningTestFixture):
    def test_server_rejects_web_builtin_triggers_and_google_generic_dedup(self) -> None:
        contract = fixture_durable_evidence.valid_server_contract()
        contract["implementation"]["objects"][1]["intended"]["firingTriggerId"] = ["2147479553"]
        with self.assertRaisesRegex(
            fixture_durable_evidence.RunValidationError, "web built-in trigger"
        ):
            fixture_durable_evidence.materialize(contract)

        contract = fixture_durable_evidence.valid_pipeline_contract()
        contract["dedup_contracts"] = [
            {
                "dedup_contract_id": "DEDUP-GADS",
                "requirement_id": "REQ-PAGE",
                "event_name": "page_view",
                "destination": "Google Ads",
                "strategy": "dual-shared-id",
                "source_type": "approved-event-id",
                "source_reference": "{{DLV - event_id}}",
                "browser_reference": "{{DLV - event_id}}",
                "transporter_reference": "{{DLV - event_id}}",
                "transported_parameter": "event_id",
                "server_event_data_path": "event_id",
                "server_generates_id": False,
                "browser_field": "event_id",
                "server_field": "event_id",
                "occurrence_scope": "one event",
                "companion_fields": [],
            }
        ]
        contract["pipelines"][0]["dedup_contract_ids"] = ["DEDUP-GADS"]
        with self.assertRaisesRegex(
            fixture_durable_evidence.ContractValidationError, "generic dual-shared-id"
        ):
            fixture_durable_evidence.validate_contract(contract)


class TestMutationRecovery(fixture_mutation_recovery.NativeAndRecoveryTestsFixture):
    def test_sender_generated_contract_materializes_without_server(self):
        contract = fixture_mutation_recovery.sender_generated_contract()
        fixture_mutation_recovery.validate_document(contract)
        run = fixture_mutation_recovery.create_from_contract(
            contract, run_id="sender", source_locator="test"
        )
        self.assertEqual({t["container_type"] for t in run["run"]["targets"]}, {"web"})
        self.assertFalse(run["pipelines"])
        for mutate in (
            lambda c: c["dedup_contracts"][0].pop("external_receiver_dependency_id"),
            lambda c: c["dedup_contracts"][0].update(event_name="purchase"),
            lambda c: c["dedup_contracts"][0].update(server_generates_id=True),
        ):
            broken = fixture_mutation_recovery.deepcopy(contract)
            mutate(broken)
            with self.assertRaises(fixture_mutation_recovery.ContractValidationError):
                fixture_mutation_recovery.validate_document(
                    fixture_mutation_recovery.approve_mutations(broken)
                )
