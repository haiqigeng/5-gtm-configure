from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from configuration_run import (  # noqa: E402
    RunValidationError,
    atomic_write,
    build_verification_comparison,
    checkpoint_operation,
    create_from_contract,
    inspect_document,
    render_markdown,
    reopen_failed_operation,
    run_file_lock,
    validate_document,
)


def contract() -> dict:
    return {
        "schema_version": "5.0",
        "route": "analytics",
        "scope": {
            "included": ["TP::Events::12::generate_lead"],
            "reference_only": [],
            "excluded": [],
        },
        "requirements": [
            {
                "id": "TP::Events::12::generate_lead",
                "authority": {
                    "grade": "approved-input",
                    "locator": "Tracking Plan / Events / row 12",
                },
                "event_name": "generate_lead",
                "source_event": "form_success",
                "parameters": {
                    "method": {
                        "source": "event.method",
                        "source_shape": "scalar:string",
                        "destination_shape": "scalar:string",
                        "provenance": {
                            "grade": "approved-input",
                            "locator": "Tracking Plan / Events / row 12 / method",
                        },
                    }
                },
            }
        ],
        "implementation": {
            "workspace": {
                "account_id": "1",
                "container_id": "2",
                "id": "3",
                "container_type": "web",
            },
            "objects": [
                {
                    "action": "create",
                    "object_type": "tag",
                    "name": "GA4 - Event - generate_lead",
                    "requirement_ids": ["TP::Events::12::generate_lead"],
                    "justification": "Implements the approved event.",
                    "evidence": [
                        "approved-input",
                        "official-current",
                        "container-confirmed",
                    ],
                    "intended": {
                        "object_type": "tag",
                        "name": "GA4 - Event - generate_lead",
                        "type": "gaawe",
                        "firingTriggerId": ["trigger::CE - form_success"],
                        "blockingTriggerId": ["trigger::Block - Didomi - GA4 denied"],
                        "fields": {"method": "{{DLV - event.method}}"},
                    },
                }
            ],
        },
        "evidence": [
            {
                "grade": "official-current",
                "locator": "GA4 event schema",
                "url": "https://developers.google.com/example",
                "title": "GA4 event schema",
                "access_date": "2026-08-01",
            },
            {"grade": "container-confirmed", "locator": "Workspace stable IDs"},
        ],
        "external_dependencies": ["Publish only after separate recette and approval."],
    }


def run_document() -> dict:
    return create_from_contract(
        contract(),
        run_id="RUN-001",
        source_locator="Tracking Plan / Events",
        timestamp="2026-08-01T10:00:00Z",
    )


def ready_run_document() -> dict:
    document = run_document()
    document["payload_mappings"][0].update(
        {
            "shape_compatibility": "compatible",
            "mapping_method": "direct-dlv",
            "gtm_resolution": "DLV - event.method",
            "template_field": "Event parameter - method",
            "missing_behavior": "Leave the field unset and record a recette dependency.",
            "status": "mapped",
        }
    )
    document["consent_routes"] = [
        {
            "requirement_id": "TP::Events::12::generate_lead",
            "product": "GA4",
            "mode": "strict-basic",
            "mechanism": "blocking-trigger",
            "normal_trigger": "trigger::CE - form_success",
            "blocking_triggers": ["trigger::Block - Didomi - GA4 denied"],
            "built_in_consent_checks": ["analytics_storage"],
            "additional_consent_checks": [],
            "blocking_event_scope": "regex:.*",
            "scope_exception_reason": None,
            "unknown_behavior": "block",
            "evidence": ["official-current", "container-confirmed"],
        }
    ]
    document["container_baseline"] = {
        "strategy": "relevant-families",
        "captured_at": "2026-08-01T10:00:30Z",
        "complete": True,
        "resource_families": ["tag", "trigger", "variable"],
        "family_counts": {"tag": 0, "trigger": 2, "variable": 0},
        "in_scope_tag_keys": [],
        "trigger_index": [
            {
                "object_key": "trigger::CE - form_success",
                "type": "customEvent",
                "fingerprint": "sha256:" + "2" * 64,
            },
            {
                "object_key": "trigger::Block - Didomi - GA4 denied",
                "type": "customEvent",
                "fingerprint": "sha256:" + "3" * 64,
            },
        ],
        "preexisting_workspace_changes": 0,
        "fingerprint": "sha256:" + "1" * 64,
    }
    document["execution_topologies"] = [
        {
            "tag_object_key": "tag::GA4 - Event - generate_lead",
            "requirement_ids": ["TP::Events::12::generate_lead"],
            "lifecycle_role": "event-driven",
            "normal_triggers": [
                {
                    "trigger_object_key": "trigger::CE - form_success",
                    "role": "source-event",
                    "type": "custom-event",
                }
            ],
            "consent_mode": "strict-basic",
            "blocking_trigger_keys": ["trigger::Block - Didomi - GA4 denied"],
            "blocking_event_scope": "regex:.*",
            "built_in_consent_checks": ["analytics_storage"],
            "additional_consent_checks": [],
            "firing_option": "once-per-event",
            "may_precede_cmp": False,
            "pre_cmp_policy": "not-applicable",
            "page_view_capable": False,
            "page_view_destinations": [],
            "ecommerce_route": "not-applicable",
            "manual_ecommerce_fields": [],
            "evidence": ["official-current", "container-confirmed"],
        }
    ]
    return validate_document(document)


def saved_object(document: dict) -> dict:
    operation = document["object_changes"][0]
    return {"object_id": "9", "fingerprint": "abc", **operation["intended"]}


def verification(document: dict, saved: dict | None = None) -> dict:
    operation = document["object_changes"][0]
    value = saved if saved is not None else saved_object(document)
    return build_verification_comparison(
        operation,
        value,
        comparator="test-semantic-v1",
        compared_fields=sorted(operation["intended"]),
        differences=[],
    )


class ConfigurationRunTest(unittest.TestCase):
    def test_contract_ingestion_preserves_stable_requirement_identity(self) -> None:
        document = run_document()
        requirement_id = "TP::Events::12::generate_lead"
        self.assertEqual(document["run"]["contract"]["requirement_ids"], [requirement_id])
        self.assertEqual(document["requirements"][0]["id"], requirement_id)
        self.assertEqual(document["object_changes"][0]["requirement_ids"], [requirement_id])
        self.assertTrue(document["run"]["contract"]["fingerprint"].startswith("sha256:"))

    def test_multi_requirement_contract_requires_explicit_object_links(self) -> None:
        value = contract()
        second = deepcopy(value["requirements"][0])
        second["id"] = "TP::Events::13::sign_up"
        second["authority"]["locator"] = "Tracking Plan / Events / row 13"
        value["requirements"].append(second)
        value["scope"]["included"].append(second["id"])
        del value["implementation"]["objects"][0]["requirement_ids"]
        with self.assertRaisesRegex(RunValidationError, "multi-requirement"):
            create_from_contract(
                value,
                run_id="RUN-002",
                source_locator="Tracking Plan / Events",
                timestamp="2026-08-01T10:00:00Z",
            )

    def test_canonical_object_dependencies_become_operation_ids(self) -> None:
        value = contract()
        value["implementation"]["objects"].insert(
            0,
            {
                "action": "create",
                "object_type": "trigger",
                "name": "CE - form_success",
                "requirement_ids": ["TP::Events::12::generate_lead"],
                "justification": "Implements the approved source event.",
                "evidence": ["approved-input", "container-confirmed"],
                "intended": {
                    "object_type": "trigger",
                    "name": "CE - form_success",
                    "type": "customEvent",
                },
            },
        )
        value["implementation"]["objects"][1]["dependencies"] = ["trigger::CE - form_success"]
        document = create_from_contract(
            value,
            run_id="RUN-DEPS",
            source_locator="Tracking Plan / Events",
            timestamp="2026-08-01T10:00:00Z",
        )
        self.assertEqual(document["object_changes"][1]["dependencies"], ["OP-001"])

        invalid = contract()
        invalid["implementation"]["objects"][0]["dependencies"] = ["trigger::Missing"]
        with self.assertRaisesRegex(RunValidationError, "unknown canonical object keys"):
            create_from_contract(
                invalid,
                run_id="RUN-BAD-DEPS",
                source_locator="Tracking Plan / Events",
                timestamp="2026-08-01T10:00:00Z",
            )

    def test_checkpoint_requires_readback_proof_and_exposes_resume_state(self) -> None:
        document = ready_run_document()
        document = checkpoint_operation(
            document,
            operation_id="OP-001",
            state="in_progress",
            note="Starting mutation.",
            timestamp="2026-08-01T10:01:00Z",
        )
        self.assertFalse(inspect_document(document)["resumable"])

        with self.assertRaisesRegex(RunValidationError, "comparison must be an object"):
            checkpoint_operation(
                document,
                operation_id="OP-001",
                state="verified",
                note="Unproven claim.",
                timestamp="2026-08-01T10:02:00Z",
                result={"object_id": "9", "fingerprint": "abc"},
                saved=saved_object(document),
            )

        with self.assertRaisesRegex(RunValidationError, "authoritative saved readback"):
            checkpoint_operation(
                document,
                operation_id="OP-001",
                state="verified",
                note="Comparison is not bound to readback.",
                timestamp="2026-08-01T10:02:00Z",
                result={"object_id": "9", "fingerprint": "abc"},
                comparison=verification(document),
            )

        saved = saved_object(document)
        document = checkpoint_operation(
            document,
            operation_id="OP-001",
            state="verified",
            note="Authoritative readback matched.",
            timestamp="2026-08-01T10:02:00Z",
            result={"object_id": "9", "fingerprint": "abc"},
            comparison=verification(document, saved),
            saved=saved,
        )
        self.assertTrue(inspect_document(document)["resumable"])
        self.assertFalse(inspect_document(document)["pass"])
        self.assertEqual(inspect_document(document)["error_code"], "finalization_required")
        self.assertEqual(document["saved_readback"][0]["operation_id"], "OP-001")

    def test_verified_checkpoint_binds_complete_comparison_to_saved_payload(self) -> None:
        document = ready_run_document()
        operation = document["object_changes"][0]
        saved = saved_object(document)

        with self.assertRaisesRegex(RunValidationError, "does not cover intended field"):
            build_verification_comparison(
                operation,
                saved,
                comparator="incomplete-comparator",
                compared_fields=["name"],
                differences=[],
            )

        different_readback = deepcopy(saved)
        different_readback["type"] = "wrong"
        with self.assertRaisesRegex(RunValidationError, "saved_sha256 does not match"):
            checkpoint_operation(
                document,
                operation_id="OP-001",
                state="verified",
                note="The proof belongs to another readback.",
                timestamp="2026-08-01T10:02:00Z",
                result={"object_id": "9", "fingerprint": "abc"},
                comparison=verification(document, saved),
                saved=different_readback,
            )

    def test_known_failed_operation_requires_explicit_reopen_before_retry(self) -> None:
        document = checkpoint_operation(
            ready_run_document(),
            operation_id="OP-001",
            state="failed",
            note="Authentication expired before any write.",
            timestamp="2026-08-01T10:01:00Z",
            error="authentication expired",
        )
        failed_inspection = inspect_document(document)
        self.assertEqual(failed_inspection["ready_operations"], [])
        self.assertFalse(failed_inspection["pass"])
        self.assertFalse(failed_inspection["successful"])
        self.assertEqual(failed_inspection["suggested_status"], "Blocked")
        document = reopen_failed_operation(
            document,
            operation_id="OP-001",
            note="Authentication renewed and target identity revalidated.",
            timestamp="2026-08-01T10:02:00Z",
        )
        self.assertEqual(inspect_document(document)["ready_operations"], ["OP-001"])
        self.assertNotIn("error", document["object_changes"][0])

        with self.assertRaisesRegex(RunValidationError, "only a failed"):
            reopen_failed_operation(
                document,
                operation_id="OP-001",
                note="No second reopen.",
                timestamp="2026-08-01T10:03:00Z",
            )

    def test_configured_requires_complete_readback_and_idempotency(self) -> None:
        document = ready_run_document()
        saved = saved_object(document)
        document = checkpoint_operation(
            document,
            operation_id="OP-001",
            state="verified",
            note="Existing state matched exactly.",
            timestamp="2026-08-01T10:02:00Z",
            result={"object_id": "9", "fingerprint": "abc"},
            comparison=verification(document, saved),
            saved=saved,
        )
        document["run"]["phase"] = "complete"
        document["run"]["status"] = "Configured"
        document["requirements"][0]["status"] = "Configured"
        document["idempotency"] = {"checked": True, "remaining_actions": []}
        self.assertEqual(validate_document(document)["run"]["status"], "Configured")
        configured = inspect_document(document)
        self.assertTrue(configured["pass"])
        self.assertTrue(configured["successful"])
        self.assertIsNone(configured["error_code"])

        invalid = deepcopy(document)
        invalid["saved_readback"] = []
        with self.assertRaisesRegex(RunValidationError, "lacks verified readback"):
            validate_document(invalid)

    def test_cmp_grant_event_and_vendor_block_have_independent_roles(self) -> None:
        document = ready_run_document()
        document["consent_routes"] = [
            {
                "requirement_id": "TP::Events::12::generate_lead",
                "product": "GA4",
                "mode": "strict-basic",
                "mechanism": "blocking-trigger",
                "normal_trigger": "trigger::CE - form_success",
                "blocking_triggers": ["trigger::Block - Didomi - GA4 denied"],
                "built_in_consent_checks": ["analytics_storage"],
                "additional_consent_checks": [],
                "blocking_event_scope": "regex:.*",
                "scope_exception_reason": None,
                "unknown_behavior": "block",
                "evidence": ["official-current", "container-confirmed"],
            }
        ]
        self.assertEqual(
            validate_document(document)["consent_routes"][0]["mechanism"], "blocking-trigger"
        )

        without_block = deepcopy(document)
        without_block["consent_routes"][0]["blocking_triggers"] = []
        with self.assertRaisesRegex(RunValidationError, "must not be empty"):
            validate_document(without_block)

    def test_vendor_wide_block_defaults_to_regex_all_events(self) -> None:
        document = ready_run_document()
        route = document["consent_routes"][0]
        route["blocking_event_scope"] = "regex:^(purchase|add_to_cart)$"
        with self.assertRaisesRegex(RunValidationError, "scope_exception_reason"):
            validate_document(document)

        route["scope_exception_reason"] = (
            "The vendor block intentionally serves this event family only."
        )
        self.assertEqual(validate_document(document)["run"]["status"], "In progress")

    def test_mutation_waits_for_complete_field_and_consent_preflight(self) -> None:
        pending = run_document()
        inspection = inspect_document(pending)
        self.assertEqual(inspection["ready_operations"], [])
        self.assertIn("OP-001", inspection["preflight_blockers"])
        with self.assertRaisesRegex(RunValidationError, "preflight is incomplete"):
            checkpoint_operation(
                pending,
                operation_id="OP-001",
                state="in_progress",
                note="Attempt before the mapping and consent decisions are complete.",
                timestamp="2026-08-01T10:01:00Z",
            )

        resolved = ready_run_document()
        self.assertEqual(inspect_document(resolved)["ready_operations"], ["OP-001"])

    def test_mapping_method_must_match_shape_decision(self) -> None:
        document = ready_run_document()
        mapping = document["payload_mappings"][0]
        mapping["shape_compatibility"] = "conversion-required"
        with self.assertRaisesRegex(RunValidationError, "requires compatible"):
            validate_document(document)

        mapping["mapping_method"] = "custom-javascript"
        mapping["gtm_resolution"] = "CJS - Vendor - method"
        self.assertEqual(validate_document(document)["run"]["status"], "In progress")

    def test_destination_name_cannot_silently_become_a_datalayer_source(self) -> None:
        value = contract()
        field = value["requirements"][0]["parameters"].pop("method")
        del field["source"]
        del field["source_shape"]
        field["destination_shape"] = "array:string"
        value["requirements"][0]["parameters"]["PRODUCT_LIST"] = field
        document = create_from_contract(
            value,
            run_id="RUN-DESTINATION-SOURCE",
            source_locator="Media brief / PRODUCT_LIST",
            timestamp="2026-08-01T10:00:00Z",
        )
        mapping = document["payload_mappings"][0]
        mapping.update(
            {
                "source": "PRODUCT_LIST",
                "source_shape": "array:string",
                "shape_compatibility": "compatible",
                "mapping_method": "direct-dlv",
                "gtm_resolution": "DLV - PRODUCT_LIST",
                "template_field": "PRODUCT_LIST",
                "missing_behavior": "Leave unset when unavailable.",
                "status": "mapped",
            }
        )
        with self.assertRaisesRegex(RunValidationError, "source_authority_grade"):
            validate_document(document)

    def test_template_mutation_requires_permission_delta(self) -> None:
        document = run_document()
        item = document["object_changes"][0]
        item["object_type"] = "template"
        item["name"] = "Vendor template"
        item["object_key"] = "template::Vendor template"
        with self.assertRaisesRegex(RunValidationError, "permission_delta"):
            validate_document(document)
        item["permission_delta"] = {
            "added": ["inject_script:https://vendor.example"],
            "removed": [],
            "evidence_locator": "Installed template permission diff",
        }
        self.assertEqual(validate_document(document)["schema_version"], "2.0")

    def test_long_dependency_chain_is_validated_iteratively(self) -> None:
        value = contract()
        requirement_id = "TP::Events::12::generate_lead"
        objects = []
        for index in range(1200):
            name = f"Variable {index:04d}"
            item = {
                "action": "create",
                "object_type": "variable",
                "name": name,
                "requirement_ids": [requirement_id],
                "justification": "Implements the approved dependency graph.",
                "evidence": ["approved-input", "container-confirmed"],
                "intended": {"object_type": "variable", "name": name},
            }
            if index:
                item["dependencies"] = [f"variable::Variable {index - 1:04d}"]
            objects.append(item)
        value["implementation"]["objects"] = objects
        document = create_from_contract(
            value,
            run_id="RUN-LONG-CHAIN",
            source_locator="Tracking Plan / Events",
            timestamp="2026-08-01T10:00:00Z",
        )
        self.assertEqual(len(document["object_changes"]), 1200)

    def test_renderer_has_preflight_human_and_machine_layers(self) -> None:
        rendered = render_markdown(run_document(), embed_machine=True)
        self.assertIn("# Pre-mutation impact preview", rendered)
        self.assertIn("## Executive summary", rendered)
        self.assertIn("## Analyst and developer change log", rendered)
        self.assertIn("## Machine handoff", rendered)
        self.assertIn('"schema_version": "2.0"', rendered)
        self.assertIn("resolve mapping/consent blockers", rendered)

    def test_cli_init_validate_inspect_and_render(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract_path = root / "contract.json"
            run_path = root / "run.json"
            handoff_path = root / "handoff.md"
            contract_path.write_text(json.dumps(contract()), encoding="utf-8")
            commands = [
                [
                    "init",
                    "--contract",
                    str(contract_path),
                    "--run-id",
                    "RUN-CLI",
                    "--source-locator",
                    "Tracking Plan / Events",
                    "--timestamp",
                    "2026-08-01T10:00:00Z",
                    "--output",
                    str(run_path),
                ],
                ["validate", "--run", str(run_path)],
                ["inspect", "--run", str(run_path)],
                ["render", "--run", str(run_path), "--output", str(handoff_path)],
            ]
            for command in commands:
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "configuration_run.py"), *command],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            duplicate_init = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "configuration_run.py"),
                    *commands[0],
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(duplicate_init.returncode, 2)
            self.assertEqual(json.loads(duplicate_init.stdout)["error_code"], "invalid_run")

            replacement = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "configuration_run.py"),
                    *commands[0],
                    "--replace-planned",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(replacement.returncode, 0, replacement.stdout + replacement.stderr)
            self.assertTrue(handoff_path.exists())
            self.assertIn("Executive summary", handoff_path.read_text(encoding="utf-8"))

    def test_run_file_lock_rejects_a_competing_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.json"
            atomic_write(path, ready_run_document())
            with run_file_lock(path):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts" / "configuration_run.py"),
                        "checkpoint",
                        "--run",
                        str(path),
                        "--operation",
                        "OP-001",
                        "--state",
                        "in_progress",
                        "--note",
                        "Competing writer",
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["error_code"], "run_conflict")

    def test_strict_basic_rejects_redundant_additional_consent_checks(self) -> None:
        document = ready_run_document()
        document["consent_routes"][0]["additional_consent_checks"] = ["analytics_storage"]
        with self.assertRaisesRegex(RunValidationError, "must be empty"):
            validate_document(document)

    def test_native_trigger_types_are_bound_to_the_saved_trigger_graph(self) -> None:
        click = ready_run_document()
        click["container_baseline"]["trigger_index"][0]["type"] = "click"
        click["execution_topologies"][0]["normal_triggers"][0]["type"] = "click-all-elements"
        self.assertEqual(validate_document(click)["run"]["status"], "In progress")

        lie = deepcopy(click)
        lie["execution_topologies"][0]["normal_triggers"][0]["type"] = "custom-event"
        with self.assertRaisesRegex(RunValidationError, "differs from bound trigger type"):
            validate_document(lie)

    def test_all_supported_engagement_trigger_types_remain_configurable(self) -> None:
        cases = {
            "click": "click-all-elements",
            "linkClick": "click-just-links",
            "formSubmission": "form-submission",
            "elementVisibility": "element-visibility",
            "scrollDepth": "scroll-depth",
            "youTubeVideo": "youtube-video",
            "historyChange": "history-change",
            "timer": "timer",
            "javascriptError": "javascript-error",
            "triggerGroup": "trigger-group",
        }
        for raw_type, normalized_type in cases.items():
            with self.subTest(raw_type=raw_type):
                document = ready_run_document()
                document["container_baseline"]["trigger_index"][0]["type"] = raw_type
                document["execution_topologies"][0]["normal_triggers"][0]["type"] = normalized_type
                self.assertEqual(
                    validate_document(document)["run"]["status"],
                    "In progress",
                )

    def test_event_and_page_load_topologies_require_the_correct_trigger_role(self) -> None:
        mislabeled = ready_run_document()
        mislabeled["object_changes"][0]["intended"]["firingTriggerId"] = [
            "trigger::builtin::2147479553"
        ]
        mislabeled["execution_topologies"][0]["normal_triggers"] = [
            {
                "trigger_object_key": "trigger::builtin::2147479553",
                "role": "source-event",
                "type": "page-view",
            }
        ]
        mislabeled["consent_routes"][0]["normal_trigger"] = "trigger::builtin::2147479553"
        with self.assertRaisesRegex(RunValidationError, "require baseline-page-load"):
            validate_document(mislabeled)

        baseline = ready_run_document()
        topology = baseline["execution_topologies"][0]
        topology["lifecycle_role"] = "baseline-page-load"
        with self.assertRaisesRegex(RunValidationError, "cmp-readiness-grant"):
            validate_document(baseline)

        topology["normal_triggers"][0]["role"] = "cmp-readiness-grant"
        self.assertEqual(validate_document(baseline)["run"]["status"], "In progress")

        advanced = ready_run_document()
        route = advanced["consent_routes"][0]
        route.update(
            {
                "mode": "advanced-native",
                "mechanism": "native-advanced",
                "normal_trigger": "trigger::builtin::2147479573",
                "blocking_triggers": [],
                "blocking_event_scope": None,
                "built_in_consent_checks": ["analytics_storage"],
                "additional_consent_checks": [],
            }
        )
        operation = advanced["object_changes"][0]
        operation["intended"]["firingTriggerId"] = ["trigger::builtin::2147479573"]
        operation["intended"]["blockingTriggerId"] = []
        topology = advanced["execution_topologies"][0]
        topology.update(
            {
                "lifecycle_role": "baseline-page-load",
                "normal_triggers": [
                    {
                        "trigger_object_key": "trigger::builtin::2147479573",
                        "role": "initialization-page-load",
                        "type": "initialization",
                    }
                ],
                "consent_mode": "advanced-native",
                "blocking_trigger_keys": [],
                "blocking_event_scope": None,
            }
        )
        self.assertEqual(validate_document(advanced)["run"]["status"], "In progress")

    def test_pre_cmp_business_event_requires_an_explicit_recovery_policy(self) -> None:
        document = ready_run_document()
        topology = document["execution_topologies"][0]
        topology["may_precede_cmp"] = True
        with self.assertRaisesRegex(RunValidationError, "must resolve"):
            validate_document(document)
        topology["pre_cmp_policy"] = "external-dependency"
        self.assertEqual(validate_document(document)["run"]["status"], "In progress")

    def test_removed_legacy_tag_uses_pre_change_without_target_topology(self) -> None:
        document = ready_run_document()
        operation = document["object_changes"][0]
        operation.update(
            {
                "action": "remove",
                "pre_change": deepcopy(operation["intended"]),
                "destructive_authorization": True,
            }
        )
        operation.pop("intended")
        document["run"]["execution_mode"] = "isolated-durable"
        document["container_baseline"]["family_counts"]["tag"] = 1
        document["container_baseline"]["in_scope_tag_keys"] = [operation["object_key"]]
        document["execution_topologies"] = []
        document["consent_routes"] = []
        document["payload_mappings"][0]["status"] = "pending"
        self.assertEqual(inspect_document(document)["ready_operations"], ["OP-001"])

    def test_topology_must_equal_the_bound_tag_trigger_arrays(self) -> None:
        document = ready_run_document()
        document["object_changes"][0]["intended"]["firingTriggerId"] = []
        with self.assertRaisesRegex(RunValidationError, "must equal bound firingTriggerId"):
            validate_document(document)

    def test_page_view_capable_tag_requires_exactly_one_owner_before_mutation(self) -> None:
        document = ready_run_document()
        document["execution_topologies"][0]["page_view_capable"] = True
        document["execution_topologies"][0]["page_view_destinations"] = ["G-TEST"]
        blockers = inspect_document(document)["preflight_blockers"]["OP-001"]
        self.assertTrue(any("page-view ownership" in blocker for blocker in blockers))
        document["page_view_decisions"] = [
            {
                "destination": "G-TEST",
                "requirement_ids": ["TP::Events::12::generate_lead"],
                "owner": "google-tag-automatic",
                "owner_object_key": "tag::GA4 - Event - generate_lead",
                "google_tag_object_key": "tag::GA4 - Event - generate_lead",
                "send_page_view": True,
                "external_dependency_ids": [],
                "reason": "The inspected automatic owner satisfies the approved page-load contract.",
                "evidence": ["official-current", "container-confirmed"],
            }
        ]
        with self.assertRaisesRegex(RunValidationError, "owner is not a Google tag"):
            validate_document(document)
        document["object_changes"][0]["intended"]["type"] = "googtag"
        document["object_changes"][0]["intended"]["fields"]["send_page_view"] = True
        document["object_changes"][0]["intended"]["fields"]["tagId"] = "G-TEST"
        document["execution_topologies"][0]["lifecycle_role"] = "baseline-page-load"
        document["execution_topologies"][0]["normal_triggers"][0]["role"] = "cmp-readiness-grant"
        self.assertEqual(inspect_document(document)["ready_operations"], ["OP-001"])
        document["object_changes"][0]["intended"]["fields"].update(
            {"tagId": "GT-TEST", "destinations": ["G-TEST"]}
        )
        self.assertEqual(inspect_document(document)["ready_operations"], ["OP-001"])

    def test_native_ecommerce_cannot_mix_with_manual_items(self) -> None:
        document = ready_run_document()
        topology = document["execution_topologies"][0]
        topology["ecommerce_route"] = "native-data-layer"
        mapping = document["payload_mappings"][0]
        mapping["destination_field"] = "items"
        blockers = inspect_document(document)["preflight_blockers"]["OP-001"]
        self.assertTrue(any("mixes a native route" in blocker for blocker in blockers))

    def test_user_data_cannot_use_event_settings_and_needs_a_feature_route(self) -> None:
        document = ready_run_document()
        mapping = document["payload_mappings"][0]
        mapping["destination_field"] = "user_data"
        mapping["mapping_method"] = "settings-variable"
        with self.assertRaisesRegex(RunValidationError, "shared Event Settings"):
            validate_document(document)

        mapping["mapping_method"] = "native-template"
        blockers = inspect_document(document)["preflight_blockers"]["OP-001"]
        self.assertTrue(any("first-party-data route" in blocker for blocker in blockers))

    def test_google_ads_enhanced_conversion_requires_ad_user_data(self) -> None:
        document = ready_run_document()
        document["payload_mappings"][0]["destination_field"] = "user_data"
        document["payload_mappings"][0]["mapping_method"] = "native-template"
        document["payload_mappings"][0]["template_field"] = "user_data"
        document["object_changes"][0]["intended"]["type"] = "awct"
        document["object_changes"][0]["intended"]["fields"]["user_data"] = "{{UPD - Lead}}"
        document["first_party_data_routes"] = [
            {
                "requirement_id": "TP::Events::12::generate_lead",
                "feature": "google-ads-enhanced-conversions",
                "destination_field": "user_data",
                "consumer_object_keys": ["tag::GA4 - Event - generate_lead"],
                "source_priority": "data-layer",
                "timing": "same-event",
                "hashing_owner": "native-raw",
                "fields": [
                    {
                        "name": "email",
                        "source": "user.email",
                        "normalization": ["trim", "lowercase"],
                        "empty_behavior": "omit",
                    }
                ],
                "consent_types": ["ad_storage"],
                "external_dependency_ids": ["EXT-001"],
                "evidence": ["approved-input", "official-current"],
            }
        ]
        with self.assertRaisesRegex(RunValidationError, "requires ad_user_data"):
            validate_document(document)

    def test_first_party_route_cannot_claim_the_wrong_product_tag(self) -> None:
        document = ready_run_document()
        mapping = document["payload_mappings"][0]
        mapping.update(
            {
                "destination_field": "user_data",
                "mapping_method": "native-template",
                "template_field": "user_data",
            }
        )
        document["object_changes"][0]["intended"]["fields"]["user_data"] = "{{UPD - Lead}}"
        document["first_party_data_routes"] = [
            {
                "requirement_id": "TP::Events::12::generate_lead",
                "feature": "google-ads-enhanced-conversions",
                "destination_field": "user_data",
                "consumer_object_keys": ["tag::GA4 - Event - generate_lead"],
                "source_priority": "data-layer",
                "timing": "same-event",
                "hashing_owner": "native-raw",
                "fields": [
                    {
                        "name": "email",
                        "source": "user.email",
                        "normalization": ["trim", "lowercase"],
                        "empty_behavior": "omit",
                    }
                ],
                "consent_types": ["ad_user_data"],
                "external_dependency_ids": ["EXT-001"],
                "evidence": ["approved-input", "official-current"],
            }
        ]
        with self.assertRaisesRegex(RunValidationError, "must not bind a GA4"):
            validate_document(document)

    def test_google_ads_tag_wide_user_data_binds_the_google_tag_field(self) -> None:
        document = ready_run_document()
        mapping = document["payload_mappings"][0]
        mapping.update(
            {
                "destination_field": "user_data",
                "mapping_method": "native-template",
                "template_field": "user_data",
            }
        )
        target = document["object_changes"][0]["intended"]
        target["type"] = "googtag"
        target["fields"]["userDataVariable"] = "{{UPD - Lead}}"
        document["first_party_data_routes"] = [
            {
                "requirement_id": "TP::Events::12::generate_lead",
                "feature": "google-ads-tag-wide-user-data",
                "destination_field": "user_data",
                "consumer_object_keys": ["tag::GA4 - Event - generate_lead"],
                "source_priority": "data-layer",
                "timing": "tag-wide",
                "hashing_owner": "native-raw",
                "fields": [
                    {
                        "name": "email",
                        "source": "user.email",
                        "normalization": ["trim", "lowercase"],
                        "empty_behavior": "omit",
                    }
                ],
                "consent_types": ["ad_user_data"],
                "external_dependency_ids": ["EXT-001"],
                "evidence": ["approved-input", "official-current"],
            }
        ]
        self.assertEqual(validate_document(document)["run"]["status"], "In progress")

    def test_refonte_requires_full_baseline_and_exact_inventory_coverage(self) -> None:
        document = ready_run_document()
        document["run"]["execution_mode"] = "refonte-durable"
        document["object_changes"][0]["action"] = "update"
        document["object_changes"][0]["pre_change"] = {
            "object_type": "tag",
            "name": "GA4 - Event - generate_lead",
            "type": "gaawe",
            "trigger": "CE - legacy_lead",
        }
        document["container_baseline"]["strategy"] = "full-paginated"
        document["container_baseline"]["family_counts"]["tag"] = 1
        document["container_baseline"]["in_scope_tag_keys"] = ["tag::GA4 - Event - generate_lead"]
        with self.assertRaisesRegex(RunValidationError, "must cover every in-scope"):
            validate_document(document)
        document["inventory_dispositions"] = [
            {
                "row_id": "inventory-row-12",
                "source_order": 12,
                "source_locator": "Client inventory / row 12 / GA4 lead",
                "before_object_key": "tag::GA4 - Event - generate_lead",
                "before_tag_name": "GA4 - Event - generate_lead",
                "disposition": "remap",
                "after_tag_name": "GA4 - Event - generate_lead",
                "trigger_before": ["CE - legacy_lead"],
                "trigger_after": ["CE - form_success", "Block - Didomi - GA4 denied"],
                "variable_changes": ["method remapped to DLV - event.method"],
                "parameter_changes": [],
                "consent_changes": ["Additional checks unset; vendor block retained"],
                "rationale": "New tracking plan and client keep instruction.",
                "operation_ids": ["OP-001"],
            }
        ]
        self.assertEqual(validate_document(document)["run"]["execution_mode"], "refonte-durable")
        rendered = render_markdown(document)
        self.assertIn("## Inventory-aligned tag change log", rendered)
        self.assertIn("inventory-row-12", rendered)

        mismatch = deepcopy(document)
        mismatch["inventory_dispositions"][0]["disposition"] = "keep"
        with self.assertRaisesRegex(RunValidationError, "incompatible with tag action"):
            validate_document(mismatch)


if __name__ == "__main__":
    unittest.main()
