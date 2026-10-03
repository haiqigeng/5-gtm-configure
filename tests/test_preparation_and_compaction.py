"""Preparation must preserve live checks; compact readbacks preserve comparison proof."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]

from adapter_support import AdapterExecutionError  # noqa: E402
from compile_configuration_request import compile_request  # noqa: E402
from configuration_run import atomic_write, create_from_contract, load_document  # noqa: E402
from diff_object_graph import GraphError, normalize_graph  # noqa: E402
from fixtures.mcp_behavior_scenario import PROFILE, FakeGtm, param, request  # noqa: E402
from mcp_adapter import McpTargetAdapter  # noqa: E402
from mcp_discovery import discover  # noqa: E402
from mcp_execute import execute  # noqa: E402
from redaction import redact_for_persistence  # noqa: E402
from verification import build_verification_comparison, expected_graph  # noqa: E402


class PreparationTests(unittest.TestCase):
    def assert_same_contract(self, actual, expected):
        # Inventory canonicalizes keyed Parameter arrays; compare native semantics.
        actual, expected = deepcopy(actual), deepcopy(expected)
        for contract in (actual, expected):
            for item in contract["implementation"]["objects"]:
                item["intended"] = normalize_graph(
                    expected_graph(item), allowed_semantic_references=set(item["depends_on"])
                )
        self.assertEqual(actual, expected)

    def inventory(self, backend=None):
        backend = backend or FakeGtm(request())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "inventory.json"
            result = discover(
                {
                    "mode": "web",
                    "targets": request()["targets"],
                    "resource_families": {"web-main": ["tag", "trigger", "variable"]},
                },
                {"web-main": PROFILE},
                backend.call,
                output,
            )
            self.assertEqual(result["status"], "Discovered")
            self.assertFalse(backend.writes)
            return json.loads(output.read_text()), backend

    def compact_request(self):
        req = request()
        for candidate in req["reuse_candidates"]:
            candidate.pop("intended")
        return req

    def test_inventory_compiles_same_contract_and_live_execution_still_checks(self):
        inventory, backend = self.inventory()
        before = len(backend.calls)
        contract = compile_request(self.compact_request(), inventory=inventory)
        self.assert_same_contract(contract, compile_request(request()))

        class Transport:
            calls = 0
            writes_attempted = 0

            def __call__(self, tool, arguments, **kwargs):
                self.calls += 1
                self.writes_attempted += arguments["action"] in {"create", "update", "remove"}
                return backend.call(tool, arguments)

        with tempfile.TemporaryDirectory() as directory:
            run_path = Path(directory) / "run.json"
            atomic_write(
                run_path,
                create_from_contract(
                    contract, run_id="inventory", source_locator="Synthetic approved input"
                ),
            )
            result = execute(run_path, {"web-main": PROFILE}, Transport())
            self.assertEqual(result["status"], "Configured")
            run = load_document(run_path)
            self.assertTrue(run["idempotency"]["checked"])
            baseline = run["container_baselines"][0]["resources"]["tag"]
            self.assertIn("parameter", next(o for o in baseline if o["tagId"] == "999"))
        actions = [args["action"] for _, args in backend.calls[before:]]
        self.assertIn("list", actions)
        self.assertIn("get", actions)
        self.assertIn("getStatus", actions)

    def test_wrong_workspace_ambiguous_match_and_incomplete_family_rejected(self):
        inventory, _ = self.inventory()
        for kind in ("workspace", "ambiguous", "incomplete", "scope"):
            changed = deepcopy(inventory)
            target = changed["targets"][0]
            if kind == "workspace":
                target["workspace_id"] = "another"
            elif kind == "ambiguous":
                target["objects"].append(
                    deepcopy(next(o for o in target["objects"] if o["object_type"] == "trigger"))
                )
            elif kind == "scope":
                for obj in target["objects"]:
                    obj["target_id"] = "another"
            else:
                target["pagination"]["trigger"]["exhausted"] = False
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                compile_request(self.compact_request(), inventory=changed)

    def test_stale_inventory_cannot_authorize_a_write(self):
        inventory, backend = self.inventory()
        contract = compile_request(self.compact_request(), inventory=inventory)
        # The saved CMP signal no longer matches the inspected compatibility target.
        backend.data["variable"]["103"]["parameter"][0]["value"] = "changed.signal"
        from adapter_runtime import TargetAdapterRegistry, execute_ready_operations

        registry = TargetAdapterRegistry()
        target = contract["targets"][0]
        adapter = McpTargetAdapter(target, PROFILE, backend.call)
        registry.register(target, adapter, adapter.capabilities())
        with tempfile.TemporaryDirectory() as directory:
            run_path = Path(directory) / "run.json"
            atomic_write(
                run_path, create_from_contract(contract, run_id="stale", source_locator="Synthetic")
            )
            execute_ready_operations(run_path, registry)
            self.assertNotEqual(load_document(run_path)["run"]["status"], "Configured")
            self.assertFalse(backend.writes)

    def test_inventory_cannot_fill_mutations_or_infer_policy(self):
        inventory, _ = self.inventory()
        for field in ("intended",):
            req = self.compact_request()
            req["objects"][0].pop(field)
            with self.assertRaises(ValueError):
                compile_request(req, inventory=inventory)
        req = self.compact_request()
        req["consent_topologies"] = []
        with self.assertRaises(ValueError):
            compile_request(req, inventory=inventory)

    def test_discovery_rejects_identity_drift_and_injected_mutation_without_artifact(self):
        req = {
            "mode": "web",
            "targets": request()["targets"],
            "resource_families": {"web-main": ["tag", "trigger", "variable"]},
        }
        expected = {
            f: req["targets"][0][f]
            for f in ("account_id", "container_id", "workspace_id", "container_type")
        }
        for kind in ("identity", "mutation", "conflict", "scope"):
            backend = FakeGtm(request())
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "inventory.json"
                if kind == "identity":
                    context = patch.object(
                        McpTargetAdapter,
                        "identity",
                        side_effect=[expected, {**expected, "workspace_id": "other"}],
                    )
                elif kind == "mutation":
                    context = patch.object(
                        McpTargetAdapter,
                        "list_resource_page",
                        lambda adapter, *args: adapter._call("gtm_tag", "create"),
                    )
                elif kind == "scope":
                    backend.data["tag"]["999"]["workspaceId"] = "other"
                    context = patch.object(McpTargetAdapter, "identity", return_value=expected)
                else:
                    context = patch.object(
                        McpTargetAdapter,
                        "list_workspace_changes_page",
                        side_effect=AdapterExecutionError("merge conflict"),
                    )
                with context, self.assertRaises(AdapterExecutionError):
                    discover(req, {"web-main": PROFILE}, backend.call, output)
                self.assertFalse(output.exists())
                self.assertFalse(backend.writes)

    def test_discovery_redacts_transitive_credentials_before_persistence(self):
        backend = FakeGtm(request())
        backend.data["tag"]["999"]["parameter"] = [param("apiSecret", "{{Neutral}}")]
        backend.data["variable"]["800"] = {
            **backend.scope,
            "variableId": "800",
            "name": "Neutral",
            "type": "c",
            "parameter": [param("value", "SYNTHETIC-TRANSITIVE-SECRET")],
        }
        inventory, _ = self.inventory(backend)
        self.assertNotIn("SYNTHETIC-TRANSITIVE-SECRET", json.dumps(inventory))

    def test_claude_and_gemini_discovery_through_real_sdk(self):
        for host in ("claude", "gemini"):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                config, source, profiles, output, state = [
                    root / f"{n}.json"
                    for n in ("config", "input", "profiles", "inventory", "state")
                ]
                config.write_text(
                    json.dumps(
                        {
                            "mcpServers": {
                                "synthetic": {
                                    "command": sys.executable,
                                    "args": [
                                        "-B",
                                        str(ROOT / "tests/fixtures/mcp_sdk_server.py"),
                                        "--state",
                                        str(state),
                                    ],
                                }
                            }
                        }
                    )
                )
                source.write_text(
                    json.dumps(
                        {
                            "mode": "web",
                            "targets": request()["targets"],
                            "resource_families": {"web-main": ["tag", "trigger", "variable"]},
                        }
                    )
                )
                profile = deepcopy(PROFILE)
                profile["tool_prefix"] = ""
                profile["families"] = {
                    k: v
                    for k, v in profile["families"].items()
                    if k in {"tag", "trigger", "variable"}
                }
                profiles.write_text(json.dumps({"web-main": profile}))
                result = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(ROOT / "scripts/mcp_host_execute.py"),
                        "--host",
                        host,
                        "--config",
                        str(config),
                        "--server",
                        "synthetic",
                        "--discover",
                        str(source),
                        "--output",
                        str(output),
                        "--profiles",
                        str(profiles),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["status"], "Discovered")
                self.assertFalse(json.loads(state.read_text())["writes"])
                self.assert_same_contract(
                    compile_request(
                        self.compact_request(), inventory=json.loads(output.read_text())
                    ),
                    compile_request(request()),
                )

    def test_codex_discovery_through_actual_relay(self):
        self.assertIsNotNone(shutil.which("node"), "Relay tests require Node")
        self.assertIsNotNone(shutil.which("pwsh"), "Relay tests require PowerShell 7")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture.json"
            fixture.write_text(
                json.dumps(
                    {
                        "request": {
                            "mode": "web",
                            "targets": request()["targets"],
                            "resource_families": {"web-main": ["tag", "trigger", "variable"]},
                        },
                        "profiles": {"web-main": PROFILE},
                        "data": FakeGtm(request()).data,
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    shutil.which("node"),
                    str(ROOT / "tests/fixtures/mcp_relay_scenario.cjs"),
                    str(root),
                    str(fixture),
                ],
                env={
                    **os.environ,
                    "TEST_PYTHON": sys.executable,
                    "TEST_PWSH": shutil.which("pwsh"),
                    "RELAY_DISCOVERY": "1",
                },
                capture_output=True,
                text=True,
                timeout=45,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("zero mutations", result.stdout)


class CompactReadbackTests(unittest.TestCase):
    def operation(self):
        return {
            "operation_id": "op",
            "target_id": "web-main",
            "resource_family": "tag",
            "name": "Event",
            "action": "create",
            "intended": {"type": "gaawe", "firingTriggerId": ["web-main::trigger::Ready"]},
        }

    def saved(self, operation):
        saved = expected_graph(operation)
        saved["objects"][0]["firingTriggerId"] = ["12"]
        saved["context_objects"] = [
            {
                "target_id": "web-main",
                "object_type": "trigger",
                "name": "Ready",
                "triggerId": "12",
                "type": "customEvent",
                "notes": "long native body " * 1000,
            }
        ]
        return saved

    def test_primary_fields_and_full_reference_index_are_preserved(self):
        op = self.operation()
        saved = self.saved(op)
        comparison, compact = build_verification_comparison(op, saved)
        self.assertTrue(comparison["pass"])
        self.assertEqual(compact["objects"], saved["objects"])
        self.assertNotIn("notes", compact["context_objects"][0])
        self.assertEqual(normalize_graph(redact_for_persistence(saved)), normalize_graph(compact))
        self.assertEqual(build_verification_comparison(op, compact), (comparison, compact))
        saved["objects"][0]["unexpectedNativeField"] = "must fail"
        comparison, compact = build_verification_comparison(op, saved)
        self.assertFalse(comparison["pass"])
        self.assertEqual(compact["objects"][0]["unexpectedNativeField"], "must fail")

    def test_ambiguous_and_missing_native_references_still_fail(self):
        op = self.operation()
        for kind in ("ambiguous", "missing"):
            saved = self.saved(op)
            if kind == "ambiguous":
                saved["context_objects"].append(
                    {**saved["context_objects"][0], "name": "Duplicate"}
                )
            else:
                saved["context_objects"] = []
            with self.subTest(kind=kind), self.assertRaises(GraphError):
                build_verification_comparison(op, saved)

    def test_context_taint_is_applied_to_primary_before_compaction(self):
        op = {
            "operation_id": "op",
            "target_id": "web-main",
            "resource_family": "variable",
            "name": "Neutral",
            "action": "reuse",
            "intended": {"type": "c", "parameter": [param("value", "SYNTHETIC-TRANSITIVE-SECRET")]},
        }
        saved = expected_graph(op)
        saved["context_objects"] = [
            {
                "target_id": "web-main",
                "object_type": "tag",
                "name": "Consumer",
                "tagId": "12",
                "type": "cvt_test",
                "parameter": [param("apiSecret", "{{Neutral}}")],
            }
        ]
        comparison, compact = build_verification_comparison(op, saved)
        self.assertNotIn("SYNTHETIC-TRANSITIVE-SECRET", json.dumps(compact))
        self.assertEqual(build_verification_comparison(op, compact), (comparison, compact))


if __name__ == "__main__":
    unittest.main()
