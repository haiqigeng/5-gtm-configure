from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from configuration_run import (  # noqa: E402
    build_pre_write_comparison,
    build_verification_comparison,
    checkpoint_operation,
    create_from_contract,
    finalize_document,
    reopen_failed_operation,
)
from redaction import (  # noqa: E402
    redact_for_persistence,
    redacted_marker,
    sensitive_paths,
)
from run_render import render_markdown  # noqa: E402
from run_validation_core import validate_document as validate_run  # noqa: E402
from run_validation_web import RunValidationError  # noqa: E402
from v9_support import (  # noqa: E402
    add_nonpurchase_dual_dedup,
    valid_pipeline_contract,
    valid_server_contract,
    valid_web_contract,
)
from validate_configuration_contract import (  # noqa: E402
    ContractValidationError,
)
from validate_configuration_contract import validate_document as validate_contract  # noqa: E402
from verification import expected_graph, materialization_fingerprints  # noqa: E402


def materialize(contract: dict) -> dict:
    return create_from_contract(
        contract,
        run_id="RUN-HARDENING",
        source_locator="approved input",
        timestamp="2026-08-18T00:00:00Z",
    )


class V9RegressionHardeningTest(unittest.TestCase):
    def test_web_contract_cannot_drop_topology_or_page_view_ownership(self) -> None:
        contract = valid_web_contract()
        contract["execution_topologies"] = []
        with self.assertRaisesRegex(ContractValidationError, "execution topology"):
            validate_contract(contract)

        contract = valid_web_contract()
        contract["implementation"]["objects"][0]["intended"]["send_page_view"] = False
        with self.assertRaisesRegex(ContractValidationError, "send_page_view"):
            validate_contract(contract)

    def test_action_semantics_fail_closed_for_every_high_risk_shape(self) -> None:
        cases = []
        remove = valid_web_contract()
        action = remove["implementation"]["objects"][0]
        action.update(
            {
                "action": "remove",
                "object_id": "tag-100",
                "pre_change": deepcopy(action["intended"]),
                "evidence": ["approved-input", "official-current", "container-confirmed"],
                "risk": "high-impact",
                "explicit_authority": True,
            }
        )
        action.pop("intended")
        remove["execution_topologies"] = []
        remove["page_view_decisions"] = []
        cases.append((remove, "destructive_authorization"))

        rename = valid_web_contract()
        action = rename["implementation"]["objects"][0]
        action.update(
            {
                "action": "rename",
                "object_id": "tag-100",
                "pre_change": deepcopy(action["intended"]),
                "evidence": ["approved-input", "official-current", "container-confirmed"],
            }
        )
        cases.append((rename, "new_name"))

        reuse = valid_web_contract()
        action = reuse["implementation"]["objects"][0]
        action.update(
            {
                "action": "reuse",
                "evidence": ["official-current", "container-confirmed"],
            }
        )
        action.pop("intended")
        cases.append((reuse, "intended"))

        for contract, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ContractValidationError, message):
                    validate_contract(contract)

    def test_target_sources_dependencies_and_web_decisions_are_materialization_owned(self) -> None:
        for mutation in (
            lambda run: run["run"]["targets"][0].__setitem__("container_id", "GTM-TAMPER"),
            lambda run: run["official_sources"][0].__setitem__("url", "https://example.test"),
            lambda run: run["execution_topologies"][0].__setitem__(
                "blocking_event_scope", "purchase"
            ),
        ):
            run = materialize(valid_pipeline_contract())
            mutation(run)
            with self.assertRaisesRegex(
                RunValidationError, "differ from deterministic materialization"
            ):
                validate_run(run)

    def test_forged_verified_state_cannot_finalize(self) -> None:
        run = materialize(valid_web_contract())
        for operation in run["object_changes"]:
            operation["state"] = "verified"
        for baseline in run["container_baselines"]:
            baseline["complete"] = True
        with self.assertRaisesRegex(RunValidationError, "comparison|saved_readback"):
            finalize_document(run, idempotency_evidence=["forged no-op claim"])

    def test_remove_is_verified_by_authoritative_absence(self) -> None:
        contract = valid_web_contract()
        action = contract["implementation"]["objects"][0]
        pre_change = deepcopy(action["intended"])
        action.update(
            {
                "action": "remove",
                "object_id": "tag-100",
                "pre_change": pre_change,
                "destructive_authorization": True,
                "evidence": ["approved-input", "official-current", "container-confirmed"],
                "risk": "high-impact",
                "explicit_authority": True,
            }
        )
        action.pop("intended")
        contract["execution_topologies"] = []
        contract["page_view_decisions"] = []
        run = materialize(contract)
        operation = run["object_changes"][0]
        prewrite, safe_pre_change = build_pre_write_comparison(
            operation, {"name": operation["name"], **pre_change}
        )
        comparison, safe_saved = build_verification_comparison(operation, None)
        self.assertTrue(prewrite["pass"])
        self.assertTrue(comparison["pass"])
        verified = checkpoint_operation(
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

    def test_prewrite_allows_adapter_metadata_but_never_claims_secret_equality(self) -> None:
        operation = {
            "operation_id": "OP-DELTA",
            "target_id": "server-main",
            "container_type": "server",
            "resource_family": "tag",
            "name": "Meta - Purchase",
            "object_key": "server-main::tag::Meta - Purchase",
            "action": "update",
            "pre_change": {
                "type": "meta-capi",
                "access_token": redacted_marker(reference="vault://meta/v1"),
            },
        }
        comparison, persisted = build_pre_write_comparison(
            operation,
            {
                "name": "Meta - Purchase",
                "type": "meta-capi",
                "access_token": "runtime-secret",
                "tagId": "2",
                "transformationId": "9",
                "tagManagerUrl": "server/accounts/1/tags/2",
            },
        )
        self.assertTrue(comparison["pass"])
        self.assertFalse(comparison["secret_comparison"]["value_equality_claimed"])
        self.assertNotIn("runtime-secret", str(persisted))
        renamed, _ = build_pre_write_comparison(
            operation,
            {
                "name": "Meta - Renamed elsewhere",
                "type": "meta-capi",
                "access_token": "runtime-secret",
            },
        )
        self.assertFalse(renamed["pass"])
        self.assertIn("$.name: value differs", renamed["differences"])

    def test_redaction_handles_template_rows_compact_phone_and_governance_flags(self) -> None:
        source = {
            "parameter": [{"key": "apiSecret", "value": "sk_live_example"}],
            "mobile": "0101010101",
            "destructive_authorization": True,
        }
        persisted = redact_for_persistence(source)
        self.assertNotEqual(persisted["parameter"][0]["value"], "sk_live_example")
        self.assertNotEqual(persisted["mobile"], "0101010101")
        self.assertIs(persisted["destructive_authorization"], True)
        self.assertEqual(sensitive_paths(persisted), [])

    def test_redaction_covers_real_authorization_header_shapes(self) -> None:
        source = {
            "authorization": "Bearer sk_live_direct_123456",
            "headers": [
                {"key": "name", "value": "Authorization"},
                {"key": "value", "value": "Bearer sk_live_flattened_123456"},
            ],
            "rows": [
                {"name": "Authorization", "value": "Basic YWJjZGVmZ2hpamts"},
            ],
            "destructive_authorization": True,
        }
        persisted = redact_for_persistence(source)
        serialized = str(persisted)
        self.assertNotIn("sk_live_direct", serialized)
        self.assertNotIn("sk_live_flattened", serialized)
        self.assertNotIn("YWJjZGVm", serialized)
        self.assertIs(persisted["destructive_authorization"], True)
        self.assertEqual(sensitive_paths(persisted), [])

    def test_pipeline_owners_dedup_and_consent_must_bind_real_objects(self) -> None:
        contract = valid_pipeline_contract()
        contract["pipelines"][0]["field_flows"][0]["receiver_owner"] = (
            "server-main::tag::Forged receiver"
        )
        with self.assertRaisesRegex(ContractValidationError, "receiver_owner"):
            validate_contract(contract)

        contract = valid_pipeline_contract()
        field = contract["pipelines"][0]["field_flows"][0]
        field["wire"]["shape"] = "object"
        field["transformation_owner"] = "server-main::transformation::Forged"
        with self.assertRaisesRegex(ContractValidationError, "transformation_owner"):
            validate_contract(contract)

        contract = add_nonpurchase_dual_dedup(valid_pipeline_contract())
        contract["dedup_contracts"][0]["source_variable_key"] = (
            "web-main::variable::Missing shared ID"
        )
        with self.assertRaisesRegex(ContractValidationError, "sender web variable"):
            validate_contract(contract)

        contract = add_nonpurchase_dual_dedup(valid_pipeline_contract())
        transporter_key = contract["dedup_contracts"][0]["transporter_consumer_keys"][0]
        transporter = next(
            item
            for item in contract["implementation"]["objects"]
            if item["object_key"] == transporter_key
        )
        transporter["intended"].pop("event_id")
        with self.assertRaisesRegex(ContractValidationError, "does not use the shared ID"):
            validate_contract(contract)

    def test_server_tags_require_real_firing_and_consent_bindings(self) -> None:
        contract = valid_server_contract()
        contract["implementation"]["objects"][1]["intended"]["firingTriggerId"] = []
        with self.assertRaisesRegex(ContractValidationError, "firingTriggerId"):
            validate_contract(contract)

        contract = valid_server_contract()
        contract["consent_topologies"] = []
        with self.assertRaisesRegex(ContractValidationError, "consent topology"):
            validate_contract(contract)

        contract = add_nonpurchase_dual_dedup(valid_pipeline_contract())
        contract["pipelines"][0]["field_flows"] = [
            field
            for field in contract["pipelines"][0]["field_flows"]
            if field["event_data"]["path"] != "cmp_meta_allowed"
        ]
        with self.assertRaisesRegex(ContractValidationError, "CMP signal"):
            validate_contract(contract)

    def test_transporter_is_not_vendor_blocked_by_default(self) -> None:
        contract = valid_pipeline_contract()
        transporter = contract["implementation"]["objects"][0]
        transporter["intended"]["blockingTriggerId"] = [
            "web-main::trigger::CMP - Analytics granted"
        ]
        with self.assertRaisesRegex(ContractValidationError, "must not carry"):
            validate_contract(contract)

        contract = valid_pipeline_contract()
        contract["consent_topologies"][0]["transporter_destination_vendor_block"] = True
        with self.assertRaisesRegex(ContractValidationError, "double-gate authority"):
            validate_contract(contract)

    def test_markdown_preserves_analyst_operational_detail_without_recette_coupling(self) -> None:
        run = materialize(valid_pipeline_contract())
        markdown = render_markdown(run)
        for heading in (
            "## Executive summary",
            "## Analyst and developer object change log",
            "## Requirement, payload, and consent mapping",
            "## Per-tag web execution topology",
            "## Client-to-server pipeline proof",
            "## External actions, publication, and recette",
        ):
            self.assertIn(heading, markdown)
        self.assertIn("Rationale:", markdown)

    def test_server_only_run_has_ordered_publication_dependencies(self) -> None:
        run = materialize(valid_server_contract())
        self.assertEqual(
            [item["kind"] for item in run["publication_dependencies"]],
            ["server-publication", "server-recette"],
        )

    def test_reopen_clears_stale_saved_evidence(self) -> None:
        run = materialize(valid_web_contract())
        operation = run["object_changes"][0]
        run = checkpoint_operation(
            run,
            operation_id=operation["operation_id"],
            state="in_progress",
            note="write started",
        )
        saved = expected_graph(operation)
        run = checkpoint_operation(
            run,
            operation_id=operation["operation_id"],
            state="saved",
            note="saved before downstream rejection",
            saved=saved,
        )
        run = checkpoint_operation(
            run,
            operation_id=operation["operation_id"],
            state="failed",
            note="downstream target rejected the object",
        )
        reopened = reopen_failed_operation(
            run,
            operation_id=operation["operation_id"],
            note="approved retry",
        )
        current = reopened["object_changes"][0]
        self.assertEqual(current["state"], "planned")
        self.assertNotIn("saved_readback", current)
        self.assertNotIn("comparison", current)

    def test_checkpoint_rejects_readback_that_its_state_would_discard(self) -> None:
        run = materialize(valid_web_contract())
        operation = run["object_changes"][0]
        with self.assertRaisesRegex(RunValidationError, "saved readback is accepted only"):
            checkpoint_operation(
                run,
                operation_id=operation["operation_id"],
                state="failed",
                note="Rejected write with contradictory readback input.",
                saved=expected_graph(operation),
            )

    def test_malformed_pipeline_records_fail_as_validation_errors_not_key_errors(self) -> None:
        for field in ("consent_topologies", "dedup_contracts"):
            run = materialize(valid_pipeline_contract())
            run[field] = [{}]
            run["run"]["materialization"]["section_fingerprints"] = materialization_fingerprints(
                run
            )
            with self.subTest(field=field):
                with self.assertRaises(RunValidationError):
                    validate_run(run)

    def test_server_rejects_web_builtin_triggers_and_google_generic_dedup(self) -> None:
        contract = valid_server_contract()
        contract["implementation"]["objects"][1]["intended"]["firingTriggerId"] = ["2147479553"]
        with self.assertRaisesRegex(RunValidationError, "web built-in trigger"):
            materialize(contract)

        contract = valid_pipeline_contract()
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
        with self.assertRaisesRegex(ContractValidationError, "generic dual-shared-id"):
            validate_contract(contract)


if __name__ == "__main__":
    unittest.main()
