from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from configuration_run import (  # noqa: E402
    checkpoint_operation,
    create_from_contract,
)
from current_support import (  # noqa: E402
    add_nonpurchase_dual_dedup,
    complete_capture_evidence,
    valid_pipeline_contract,
    valid_server_contract,
    valid_web_contract,
)
from redaction import (  # noqa: E402
    REDACTED_STATE,
    redact_for_persistence,
    redacted_marker,
    safe_equal,
    sensitive_paths,
)
from run_state import _record_target_baseline  # noqa: E402
from run_validation_web import RunValidationError  # noqa: E402
from validate_configuration_contract import (  # noqa: E402
    ContractValidationError,
)
from validate_configuration_contract import (  # noqa: E402
    validate_document as validate_contract,
)
from verification import build_verification_comparison, expected_graph  # noqa: E402


class CurrentContractAndRunTest(unittest.TestCase):
    def test_all_three_routes_validate_and_materialize(self) -> None:
        for builder, expected_operations in (
            (valid_web_contract, 3),
            (valid_server_contract, 3),
            (valid_pipeline_contract, 5),
        ):
            with self.subTest(builder=builder.__name__):
                contract = validate_contract(builder())
                run = create_from_contract(
                    contract,
                    run_id=f"RUN-{contract['mode']}",
                    source_locator="approved input",
                    timestamp="2026-08-18T00:00:00Z",
                )
                self.assertEqual(run["schema_version"], "4.0")
                self.assertEqual(run["run"]["mode"], contract["mode"])
                self.assertEqual(len(run["object_changes"]), expected_operations)
                self.assertEqual(
                    {item["target_id"] for item in run["object_changes"]},
                    {item["target_id"] for item in contract["implementation"]["objects"]},
                )

    def test_contract_and_run_schemas_accept_the_canonical_pipeline(self) -> None:
        contract_schema = json.loads(
            (ROOT / "schemas" / "configuration-contract.schema.json").read_text(encoding="utf-8")
        )
        run_schema = json.loads(
            (ROOT / "schemas" / "configuration-run.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(contract_schema)
        Draft202012Validator.check_schema(run_schema)
        contract = valid_pipeline_contract()
        self.assertEqual(list(Draft202012Validator(contract_schema).iter_errors(contract)), [])
        run = create_from_contract(
            contract,
            run_id="RUN-SCHEMA",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        self.assertEqual(list(Draft202012Validator(run_schema).iter_errors(run)), [])

    def test_materialization_is_deterministic_and_contract_owned(self) -> None:
        contract = valid_pipeline_contract()
        first = create_from_contract(
            contract,
            run_id="RUN-DETERMINISTIC",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        second = create_from_contract(
            contract,
            run_id="RUN-DETERMINISTIC",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        self.assertEqual(first, second)
        tampered = deepcopy(first)
        tampered["pipelines"][0]["transport_owner"] = "manual override"
        with self.assertRaisesRegex(
            RunValidationError, "differ from deterministic materialization"
        ):
            from run_validation_core import validate_document

            validate_document(tampered)

    def test_target_identity_and_resource_family_are_isolated(self) -> None:
        contract = valid_pipeline_contract()
        duplicate = deepcopy(contract["targets"][0])
        duplicate["container_id"] = "GTM-OTHER"
        contract["targets"].append(duplicate)
        with self.assertRaisesRegex(ContractValidationError, "duplicate target_id"):
            validate_contract(contract)

        contract = valid_pipeline_contract()
        contract["implementation"]["objects"][2]["resource_family"] = "client"
        with self.assertRaisesRegex(
            ContractValidationError, "duplicate object identity|object_key"
        ):
            validate_contract(contract)

    def test_receiver_dependencies_are_required_before_cutover(self) -> None:
        contract = valid_pipeline_contract(cutover=True)
        run = create_from_contract(
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

        broken = valid_pipeline_contract(cutover=True)
        broken["implementation"]["objects"][0]["depends_on"] = []
        with self.assertRaisesRegex(RunValidationError, "cutover does not depend"):
            create_from_contract(
                broken,
                run_id="RUN-BROKEN",
                source_locator="approved input",
                timestamp="2026-08-18T00:00:00Z",
            )

    def test_reused_claiming_client_requires_exact_readback_contract(self) -> None:
        contract = valid_pipeline_contract()
        client = contract["implementation"]["objects"][1]
        client.pop("intended")
        with self.assertRaisesRegex(ContractValidationError, "intended"):
            validate_contract(contract)

        contract = valid_pipeline_contract()
        contract["implementation"]["objects"][1]["intended"]["claim_criteria"] = (
            "Different request claim"
        )
        with self.assertRaisesRegex(ContractValidationError, "claim criteria differs"):
            validate_contract(contract)

    def test_consent_rejects_accidental_double_gate_and_missing_event_coverage(self) -> None:
        contract = valid_pipeline_contract()
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
        with self.assertRaisesRegex(ContractValidationError, "duplicates a transport block"):
            validate_contract(contract)

        contract = valid_pipeline_contract()
        contract["consent_topologies"][0]["event_coverage"] = ["purchase"]
        with self.assertRaisesRegex(RunValidationError, "missing transported event coverage"):
            create_from_contract(
                contract,
                run_id="RUN-CONSENT",
                source_locator="approved input",
                timestamp="2026-08-18T00:00:00Z",
            )

    def test_non_scalar_shape_and_named_special_fields_are_not_inferred(self) -> None:
        contract = valid_pipeline_contract()
        field = contract["pipelines"][0]["field_flows"][0]
        field["wire"] = {"path": "user_data", "shape": "array"}
        field["event_data"] = {"path": "user_data", "shape": "array"}
        field["source"] = {"path": "user_data", "shape": "array"}
        field["destination"] = {"path": "user_data", "shape": "array"}
        with self.assertRaisesRegex(ContractValidationError, "user_data must be an object"):
            validate_contract(contract)

        contract = valid_pipeline_contract()
        field = contract["pipelines"][0]["field_flows"][0]
        field["wire"]["shape"] = "object"
        with self.assertRaisesRegex(ContractValidationError, "transformation owner"):
            validate_contract(contract)

    def test_dual_delivery_requires_one_approved_stable_occurrence_id(self) -> None:
        contract = add_nonpurchase_dual_dedup(valid_pipeline_contract())
        self.assertEqual(
            validate_contract(contract)["dedup_contracts"][0]["event_name"], "add_to_cart"
        )
        create_from_contract(
            contract,
            run_id="RUN-DEDUP",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )

        internal_fallback = deepcopy(contract)
        internal_fallback["dedup_contracts"][0]["source_type"] = "gtm-event-scoped-fallback"
        with self.assertRaisesRegex(ContractValidationError, "source_type is unsupported"):
            validate_contract(internal_fallback)

        separate = deepcopy(contract)
        separate["dedup_contracts"][0]["browser_reference"] = "{{DLV - Another ID}}"
        with self.assertRaisesRegex(ContractValidationError, "one occurrence source"):
            validate_contract(separate)

    def test_redaction_preserves_configuration_references_and_never_claims_secret_equality(
        self,
    ) -> None:
        mapped = {
            "email": "{{DLV - user.email}}",
            "phone_number": {
                "source": "user.phone_number",
                "source_shape": "scalar:string",
                "destination_shape": "scalar:string",
            },
            "access_token": redacted_marker(reference="vault://meta/token"),
        }
        safe = redact_for_persistence(mapped)
        self.assertEqual(safe["email"], "{{DLV - user.email}}")
        self.assertEqual(safe["phone_number"], mapped["phone_number"])
        self.assertEqual(sensitive_paths(safe), [])
        self.assertFalse(safe_equal(redacted_marker(), redacted_marker()))

        operation = {
            "operation_id": "OP-SECRET",
            "target_id": "server-main",
            "resource_family": "tag",
            "name": "Meta - Purchase",
            "intended": {"type": "meta-capi", "access_token": safe["access_token"]},
        }
        saved = {
            "objects": [
                {
                    "target_id": "server-main",
                    "object_type": "tag",
                    "name": "Meta - Purchase",
                    "type": "meta-capi",
                    "access_token": "ephemeral-token-value",
                }
            ]
        }
        comparison, persisted = build_verification_comparison(operation, saved)
        self.assertTrue(comparison["pass"])
        secret = comparison["report"]["secret_comparison"]
        self.assertEqual(secret["state"], REDACTED_STATE)
        self.assertFalse(secret["value_equality_claimed"])
        self.assertNotIn("ephemeral-token-value", json.dumps([comparison, persisted]))

    def test_configuration_run_has_no_recette_consumer_contract(self) -> None:
        run = create_from_contract(
            valid_pipeline_contract(),
            run_id="RUN-NO-RECETTE-COUPLING",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        self.assertNotIn("recette_handoff", run)

    def test_manual_checkpoints_cannot_reach_configured_without_adapter_convergence(self) -> None:
        run = create_from_contract(
            valid_pipeline_contract(cutover=True),
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
            run = _record_target_baseline(
                run,
                target_id=target["target_id"],
                resources=resources,
                captured_at="2026-08-18T00:00:01Z",
                preexisting_workspace_changes=[],
                capture_evidence=complete_capture_evidence(resources, target),
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
                run = checkpoint_operation(
                    run,
                    operation_id=operation_id,
                    state="verified",
                    note="Authoritative readback matched.",
                    pre_write_saved=pre_write,
                    saved=expected_graph(operation),
                )
                pending.pop(operation_id)
                progressed = True
            self.assertTrue(progressed)
        self.assertNotEqual(run["run"]["status"], "Configured")

    def test_cli_rejects_caller_baseline_and_wraps_invalid_readback_as_coded_json(self) -> None:
        run = create_from_contract(
            valid_web_contract(),
            run_id="RUN-CLI-EVIDENCE",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_path = root / "run.json"
            invalid_readback_path = root / "invalid-readback.json"
            run_path.write_text(json.dumps(run), encoding="utf-8")
            invalid_readback_path.write_text(
                json.dumps({"name": "Google tag - Web transport"}), encoding="utf-8"
            )
            baseline = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "configuration_run.py"),
                    "baseline",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(baseline.returncode, 2)
            self.assertIn("invalid choice: 'baseline'", baseline.stderr)
            recorded = _record_target_baseline(
                run,
                target_id="web-main",
                resources={"tag": [], "trigger": [], "variable": []},
                captured_at="2026-08-18T00:00:01Z",
                preexisting_workspace_changes=[],
                capture_evidence=complete_capture_evidence(
                    {"tag": [], "trigger": [], "variable": []}, run["run"]["targets"][0]
                ),
            )
            run_path.write_text(json.dumps(recorded), encoding="utf-8")
            self.assertTrue(recorded["container_baselines"][0]["complete"])
            ready_operation = next(
                item for item in recorded["object_changes"] if not item["dependencies"]
            )
            checkpoint = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "configuration_run.py"),
                    "checkpoint",
                    "--run",
                    str(run_path),
                    "--operation",
                    ready_operation["operation_id"],
                    "--state",
                    "verified",
                    "--note",
                    "Malformed adapter readback probe.",
                    "--saved-readback",
                    str(invalid_readback_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(checkpoint.returncode, 2)
            error = json.loads(checkpoint.stdout)
            self.assertEqual(error["error_code"], "invalid_run")
            self.assertIn("objects array", error["error"])


if __name__ == "__main__":
    unittest.main()
