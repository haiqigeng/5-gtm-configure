from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from adapter_runtime import (  # noqa: E402
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from compile_configuration_request import compile_request  # noqa: E402
from configuration_run import (  # noqa: E402
    atomic_write,
    create_from_contract,
    load_document,
    validate_document,
)
from current_support import approve_mutations, valid_web_contract  # noqa: E402
from import_ga4_tracking_plan_handoff import (  # noqa: E402
    normalized_approved_semantics,
    verify_delivery,
)
from mcp_queue_adapter import QueueTransport, unwrap  # noqa: E402
from redaction import is_redacted, redact_for_persistence, sensitive_paths  # noqa: E402
from run_render import render_markdown  # noqa: E402
from test_current_adapter_runtime import FakeAdapter, capabilities  # noqa: E402
from validate_configuration_contract import validate_document as validate_contract  # noqa: E402

CANARY = "CANARYsecretVALUE_7f3a9c1e5b2d8f4a6c0e"


def row(name, value=CANARY, name_key="parameter", value_key="parameterValue"):
    return {
        "type": "map",
        "map": [
            {"type": "template", "key": name_key, "value": name},
            {"type": "template", "key": value_key, "value": value},
        ],
    }


def compact(contract):
    value = deepcopy(contract)
    implementation = value.pop("implementation")
    value.update(implementation)
    value.pop("scope")
    for item in value["objects"]:
        for key in ("object_key", "target_id", "requirement_ids", "approval"):
            item.pop(key, None)
    return value


class AuditRegressions(unittest.TestCase):
    def test_actual_generated_delivery_imports_without_rewriting_inventory(self):
        fixture = ROOT / "tests/fixtures/tracking-plan-delivery"
        handoff, plan = verify_delivery(fixture)
        self.assertEqual(
            sum(item["role"] == "shared_machine_contract" for item in handoff["artifacts"]), 10
        )
        imported = normalized_approved_semantics(handoff, plan)
        self.assertEqual(len(imported["requirements"]), 3)
        self.assertEqual(
            [item["event_name"] for item in imported["requirements"]],
            [item["event_name"] for item in plan["events"]],
        )
        self.assertEqual(imported["source_contract"], "ga4-tracking-plan-delivery@1.1.0")

    def test_intake_still_rejects_old_versions_and_duplicate_singletons(self):
        fixture = ROOT / "tests/fixtures/tracking-plan-delivery"
        with tempfile.TemporaryDirectory() as temp:
            delivery = Path(temp) / "delivery"
            shutil.copytree(fixture, delivery)
            handoff_path = delivery / "handoff.json"
            handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
            handoff["handoff_version"] = "1.0.0"
            handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                verify_delivery(delivery)
            handoff["handoff_version"] = "1.1.0"
            singleton = next(
                item for item in handoff["artifacts"] if item["role"] == "canonical_tracking_plan"
            )
            handoff["artifacts"].append(deepcopy(singleton))
            handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate handoff artifact role"):
                verify_delivery(delivery)

    def test_redaction_matrix_and_non_secret_controls(self):
        for name in (
            "consumer_secret",
            "token_secret",
            "access_token",
            "consumer_key",
            "ck",
            "cs",
            "oauth_token",
            "email",
        ):
            for name_key, value_key in (
                ("parameter", "parameterValue"),
                ("name", "value"),
                ("headerName", "headerValue"),
                ("fieldName", "defaultValue"),
            ):
                with self.subTest(name=name, keys=(name_key, value_key)):
                    value = row(name, name_key=name_key, value_key=value_key)
                    self.assertTrue(sensitive_paths(value))
                    self.assertNotIn(CANARY, json.dumps(redact_for_persistence(value)))
                    self.assertEqual(sensitive_paths(redact_for_persistence(value)), [])
        for name in ("Authorization", "Proxy-Authorization", "X-Api-Key", "Cookie", "Set-Cookie"):
            self.assertNotIn(
                CANARY,
                json.dumps(redact_for_persistence(row(name, name_key="name", value_key="value"))),
            )
        for value in (
            row("currency", "EUR"),
            row("value", "0"),
            row("token_secret", "{{Secret reference}}"),
        ):
            self.assertEqual(redact_for_persistence(value), value)
            self.assertEqual(sensitive_paths(value), [])

    def test_custom_code_and_error_redaction(self):
        from redaction import scrub_sensitive_text

        for code in (
            f'var consumer_secret = "{CANARY}";',
            f'const data = {{"access_token": "{CANARY}"}}',
            f"var token_secret = '{CANARY} with spaces';",
        ):
            self.assertTrue(is_redacted(redact_for_persistence(code)))
            self.assertNotIn(CANARY, scrub_sensitive_text(code, set()))

    def test_both_validators_reject_structural_leaks(self):
        contract = valid_web_contract()
        contract["implementation"]["objects"][0]["intended"]["parameter"] = [row("access_token")]
        with self.assertRaisesRegex(ValueError, "literal secret"):
            validate_contract(approve_mutations(contract))
        run = create_from_contract(
            valid_web_contract(), run_id="canary", source_locator="Synthetic request"
        )
        run["run"]["id"] = 'access_token = "' + CANARY + '"'
        with self.assertRaisesRegex(ValueError, "literal secret"):
            validate_document(run)

    def test_runtime_to_render_has_no_canary_bytes(self):
        class Source(FakeAdapter):
            def list_resource_page(self, family, cursor):
                return {
                    "items": [
                        {
                            "name": "Existing sensitive tag",
                            "type": "gaawe",
                            "parameter": [row("token_secret")],
                        }
                    ]
                    if family == "tag"
                    else [],
                    "next_cursor": None,
                }

        adapter = Source()
        run = create_from_contract(
            valid_web_contract(), run_id="end-to-end", source_locator="Synthetic request"
        )
        target = run["run"]["targets"][0]
        adapter.bind_target(target)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, capabilities("tag", "trigger"))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry)
            verify_idempotent_rerun(path, registry)
            result = load_document(path)
            self.assertEqual(result["run"]["status"], "Configured")
            output = render_markdown(result, embed_machine=True)
            (Path(temp) / "result.md").write_text(output, encoding="utf-8")
            self.assertIn("Sensitive literals", output)
            for artifact in Path(temp).rglob("*"):
                if artifact.is_file():
                    self.assertNotIn(CANARY.encode(), artifact.read_bytes(), str(artifact))

    def test_compiler_roundtrip_and_missing_policy(self):
        original = valid_web_contract()
        result = compile_request(compact(original))
        self.assertEqual(result["execution_topologies"], original["execution_topologies"])
        self.assertEqual(result["consent_topologies"], original["consent_topologies"])
        self.assertEqual(len(result["implementation"]["objects"]), 3)
        broken = compact(original)
        broken.pop("consent_topologies")
        with self.assertRaises(ValueError):
            compile_request(broken)

    def test_compiler_closes_reuse_without_unrelated_candidates(self):
        request = compact(valid_web_contract())
        reused = request["objects"].pop()
        reused["action"] = "reuse"
        reused["evidence"].append("container-confirmed")
        unrelated = deepcopy(reused)
        unrelated["name"] = "Unrelated trigger"
        request["reuse_candidates"] = [reused, unrelated]
        result = compile_request(request)
        self.assertEqual(len(result["implementation"]["objects"]), 3)
        self.assertNotIn("Unrelated trigger", json.dumps(result))

    def test_compiler_propagates_late_requirement_through_shared_dependency(self):
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
        with patch(
            "compile_configuration_request.validate_document", side_effect=lambda value: value
        ):
            result = compile_request(request)
        objects = {item["name"]: item for item in result["implementation"]["objects"]}
        self.assertEqual(objects["shared"]["requirement_ids"], ["A", "B"])
        self.assertEqual(objects["leaf"]["requirement_ids"], ["A", "B"])

    def test_isolated_runtime_does_not_list_unrelated_capabilities(self):
        class Source(FakeAdapter):
            def list_resource_page(self, family, cursor):
                if family == "variable":
                    raise AssertionError("Unrelated variable inventory requested")
                return super().list_resource_page(family, cursor)

        adapter = Source()
        run = create_from_contract(
            valid_web_contract(), run_id="scoped-baseline", source_locator="Synthetic request"
        )
        target = run["run"]["targets"][0]
        adapter.bind_target(target)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, capabilities("tag", "trigger", "variable"))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry)
            self.assertEqual(
                set(load_document(path)["container_baselines"][0]["resource_families"]),
                {"tag", "trigger"},
            )

    def test_delta_report_summarizes_unchanged_objects(self):
        run = create_from_contract(
            valid_web_contract(), run_id="render", source_locator="Synthetic request"
        )
        prototype = deepcopy(run["object_changes"][0])
        prototype["action"] = "reuse"
        prototype["name"] = "UNCHANGED_DETAIL"
        run["object_changes"].extend(deepcopy(prototype) for _ in range(80))
        output = render_markdown(run)
        self.assertIn("Unchanged objects: 80", output)
        self.assertNotIn("UNCHANGED_DETAIL", output)
        self.assertIn("before → intended", output)

    def test_queue_rejects_credential_writes_before_disk(self):
        with tempfile.TemporaryDirectory() as temp:
            transport = QueueTransport(Path(temp), timeout=0.1)
            with self.assertRaisesRegex(Exception, "secure in-memory adapter"):
                transport(
                    "mcp__gtm__gtm_tag",
                    {"createOrUpdateConfig": {"parameter": [row("access_token")]}},
                )
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_mcp_text_response_is_parsed_before_redaction(self):
        response = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"tag": [{"parameter": [row("consumer_secret")]}]}),
                }
            ]
        }
        self.assertNotIn(CANARY, json.dumps(redact_for_persistence(unwrap(response))))

    def test_reply_command_redacts_every_written_file(self):
        with tempfile.TemporaryDirectory() as temp:
            queue = Path(temp)
            identifier = "a" * 32
            (queue / f"{identifier}.request.claimed").write_text("{}", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/mcp_queue_adapter.py"),
                    "reply",
                    "--queue",
                    str(queue),
                ],
                input=json.dumps(
                    {
                        "id": identifier,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(
                                        {"tag": [{"parameter": [row("consumer_secret")]}]}
                                    ),
                                }
                            ]
                        },
                    }
                ),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            for artifact in queue.iterdir():
                self.assertNotIn(CANARY.encode(), artifact.read_bytes())

    def test_reply_error_reaches_worker_without_a_secret_or_stalled_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            queue = Path(temp)
            identifier = "b" * 32
            (queue / f"{identifier}.request.claimed").write_text("{}", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/mcp_queue_adapter.py"),
                    "reply",
                    "--queue",
                    str(queue),
                ],
                input=json.dumps(
                    {
                        "id": identifier,
                        "result": {"isError": True, "content": [{"type": "text", "text": CANARY}]},
                    }
                ),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((queue / f"{identifier}.request.claimed").exists())
            record = json.loads((queue / f"{identifier}.response.json").read_text(encoding="utf-8"))
            self.assertIn("error", record)
            self.assertNotIn(CANARY, json.dumps(record))


if __name__ == "__main__":
    unittest.main()
