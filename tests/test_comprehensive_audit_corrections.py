"""Exercise the audit failures through native boundaries, including negative controls."""
# ruff: noqa: E402

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]
from adapter_runtime import TargetAdapterRegistry, execute_ready_operations, verify_idempotent_rerun
from adapter_support import AdapterExecutionError
from compile_configuration_request import compile_request
from configuration_run import (
    atomic_write,
    checkpoint_operation,
    create_from_contract,
    load_document,
)
from diff_object_graph import GraphError
from fixtures.mcp_behavior_scenario import PROFILE, FakeGtm, request
from mcp_adapter import McpTargetAdapter
from strict_json import validate_output_paths
from test_utility_audit_corrections import additional_request
from verification import build_pre_write_comparison, build_verification_comparison


class NativeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "run.json"

    def start(self, req, call, profile=PROFILE):
        contract = compile_request(req)
        atomic_write(
            self.path,
            create_from_contract(
                contract, run_id="audit", source_locator="Synthetic approved request"
            ),
        )
        return self.registry(req, call, profile)

    def registry(self, req, call, profile=PROFILE):
        target = req["targets"][0]
        adapter = McpTargetAdapter(target, profile, call)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, adapter.capabilities())
        return registry, adapter

    def assert_configured(self, registry):
        verify_idempotent_rerun(self.path, registry)
        self.assertEqual(load_document(self.path)["run"]["status"], "Configured")

    def test_applied_write_invalid_reply_is_read_back_without_duplicate(self):
        for shape in ("empty", "invalid-json", "missing-id", "wrong-scope", "missing-path"):
            with self.subTest(shape=shape):
                req = request()
                backend = FakeGtm(req)
                profile = deepcopy(PROFILE)
                if shape == "missing-path":
                    profile["families"]["tag"]["object_path"] = ["saved"]

                def call(tool, args):
                    result = backend.call(tool, args)
                    if args["action"] == "create":
                        if shape == "empty":
                            return {"content": []}
                        if shape == "invalid-json":
                            return {"content": [{"type": "text", "text": "invalid"}]}
                        if shape == "missing-id":
                            return {k: v for k, v in result.items() if k != "tagId"}
                        if shape == "wrong-scope":
                            return {**result, "workspaceId": "other"}
                        return result
                    return (
                        {"saved": result}
                        if shape == "missing-path"
                        and tool.endswith("gtm_tag")
                        and args["action"] == "get"
                        else result
                    )

                registry, _ = self.start(req, call, profile)
                execute_ready_operations(self.path, registry)
                self.assert_configured(registry)
                self.assertEqual(len(backend.writes), 1)
                create_index = next(
                    i for i, (_, a) in enumerate(backend.calls) if a["action"] == "create"
                )
                self.assertTrue(
                    any(a["action"] == "get" for _, a in backend.calls[create_index + 1 :])
                )
                fresh, _ = self.registry(req, backend.call)
                execute_ready_operations(self.path, fresh)
                self.assert_configured(fresh)
                self.assertEqual(len(backend.writes), 1)

    def test_failed_recovery_stays_uncertain_until_fresh_authoritative_read(self):
        req = request()
        backend = FakeGtm(req)

        def call(tool, args):
            result = backend.call(tool, args)
            if args["action"] == "create":
                backend.hide_once = True
                return {"content": []}
            return result

        registry, _ = self.start(req, call)
        execute_ready_operations(self.path, registry)
        document = load_document(self.path)
        operation = next(o for o in document["object_changes"] if o["resource_family"] == "tag")
        self.assertEqual(operation["state"], "uncertain")
        fresh, adapter = self.registry(req, backend.call)
        execute_ready_operations(self.path, fresh)
        self.assertEqual(len(backend.writes), 1)
        comparison, saved = build_verification_comparison(operation, adapter.read(operation))
        atomic_write(
            self.path,
            checkpoint_operation(
                load_document(self.path),
                operation_id=operation["operation_id"],
                state="verified",
                note="Fresh recovery read",
                comparison=comparison,
                saved=saved,
            ),
        )
        self.assert_configured(fresh)
        self.assertEqual(len(backend.writes), 1)

    def test_predispatch_failure_remains_failed(self):
        req = request()
        backend = FakeGtm(req)

        def call(tool, args):
            if args["action"] == "create":
                raise AdapterExecutionError("Local schema refused dispatch")
            return backend.call(tool, args)

        registry, _ = self.start(req, call)
        execute_ready_operations(self.path, registry)
        self.assertFalse(backend.writes)
        self.assertEqual(
            next(
                o
                for o in load_document(self.path)["object_changes"]
                if o["resource_family"] == "tag"
            )["state"],
            "failed",
        )

    def test_builtin_semantic_consent_initialization_executes_and_converges(self):
        for ref in ("2147479572", "web-main::trigger::builtin::2147479572"):
            with self.subTest(reference=ref):
                req = additional_request()
                owner = next(
                    o
                    for o in req["objects"]
                    if o["resource_family"] == "tag" and o["action"] == "reuse"
                )
                owner["action"] = "create"
                owner["intended"]["firingTriggerId"] = [ref]
                backend = FakeGtm(req)
                registry, _ = self.start(req, backend.call)
                execute_ready_operations(self.path, registry)
                self.assert_configured(registry)
                self.assertEqual(len(backend.writes), 2)
                saved = next(v for v in backend.data["tag"].values() if v["name"] == owner["name"])
                self.assertEqual(saved["firingTriggerId"], ["2147479572"])

    def test_sequencing_compiler_wire_readback_and_fresh_resume(self):
        for representation in ("name", "tagId"):
            with self.subTest(representation=representation):
                req = additional_request()
                owner = next(
                    o
                    for o in req["objects"]
                    if o["action"] == "reuse" and o["resource_family"] == "tag"
                )
                owner["action"] = "create"
                main = req["objects"][0]
                main["intended"]["setupTag"] = [
                    {"tagName": "web-main::tag::CMP defaults", "stopOnSetupFailure": True}
                ]
                main["intended"]["teardownTag"] = [
                    {"tagName": "web-main::tag::CMP defaults", "stopTeardownOnFailure": False}
                ]
                profile = {**PROFILE, "sequencing_reference": representation}
                backend = FakeGtm(req)

                def call(tool, args):
                    config = args.get("createOrUpdateConfig", {})
                    for field in ("setupTag", "teardownTag"):
                        for row in config.get(field, []):
                            expected = next(
                                t
                                for t in backend.data["tag"].values()
                                if t["name"] == "CMP defaults"
                            )
                            self.assertEqual(row["tagName"], expected[representation])
                    return backend.call(tool, args)

                registry, _ = self.start(req, call, profile)
                execute_ready_operations(self.path, registry)
                self.assert_configured(registry)
                fresh, _ = self.registry(req, call, profile)
                execute_ready_operations(self.path, fresh)
                self.assert_configured(fresh)
                self.assertEqual(len(backend.writes), 2)

    def test_reference_wrong_target_family_and_duplicates_fail_before_write(self):
        backend = FakeGtm(request())
        profile = deepcopy(PROFILE)
        profile["sequencing_reference"] = "tagId"
        profile["families"]["folder"] = {**profile["families"]["tag"], "list_path": ["folder"]}
        _, adapter = self.registry(request(), backend.call, profile)
        adapter.cache["tag"] = [
            {
                "tagId": "77",
                "name": "Setup",
                "accountId": "account-1",
                "containerId": "GTM-WEBTEST",
                "workspaceId": "workspace-web",
            }
        ]
        adapter.complete_families.add("tag")
        adapter.known_ids["elsewhere::tag::Setup"] = "77"
        for field, value in (
            ("firingTriggerId", ["elsewhere::trigger::builtin::2147479572"]),
            ("parentFolderId", "2147479572"),
            ("setupTag", [{"tagName": "elsewhere::tag::Setup"}]),
            ("firingTriggerId", ["web-main::tag::Setup"]),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(AdapterExecutionError):
                    adapter._serialize_references({field: value})
        self.assertIn("folder", adapter.complete_families)
        self.assertEqual(adapter.cache["folder"], [])
        adapter.cache["tag"].append(
            {
                "tagId": "78",
                "name": "Setup",
                "accountId": "account-1",
                "containerId": "GTM-WEBTEST",
                "workspaceId": "workspace-web",
            }
        )
        with self.assertRaisesRegex(AdapterExecutionError, "Ambiguous GTM reference"):
            adapter._serialize_references({"setupTag": [{"tagName": "web-main::tag::Setup"}]})
        self.assertFalse(backend.writes)

    def test_sequence_requires_inspection_only_for_semantic_values(self):
        _, adapter = self.registry(request(), FakeGtm(request()).call)
        adapter.cache["tag"] = [
            {
                "tagId": "77",
                "name": "Setup",
                "accountId": "account-1",
                "containerId": "GTM-WEBTEST",
                "workspaceId": "workspace-web",
            }
        ]
        adapter.complete_families.add("tag")
        for native in ("77", "Setup"):
            intended = {"setupTag": [{"tagName": native}]}
            adapter._serialize_references(intended)
            self.assertEqual(intended["setupTag"][0]["tagName"], native)
        with self.assertRaises(AdapterExecutionError):
            adapter._serialize_references({"setupTag": [{"tagName": "web-main::tag::Setup"}]})

    def test_reordered_parameters_do_not_block_actual_update(self):
        req = request()
        backend = FakeGtm(req)
        registry, _ = self.start(req, backend.call)
        execute_ready_operations(self.path, registry)
        saved = next(
            v for v in backend.data["tag"].values() if v["name"] == req["objects"][0]["name"]
        )
        update = request()
        row = update["objects"][0]
        row.update(action="update", object_id=saved["tagId"], pre_change=deepcopy(saved))
        row["intended"]["notes"] = "Approved update"
        saved["parameter"].reverse()
        registry, _ = self.start(update, backend.call)
        execute_ready_operations(self.path, registry)
        self.assert_configured(registry)
        self.assertEqual(len(backend.writes), 2)
        self.assertEqual(backend.data["tag"][saved["tagId"]]["notes"], "Approved update")


class PrewriteSemanticTests(unittest.TestCase):
    def test_keyed_maps_sort_but_real_drift_and_ordered_lists_remain_detected(self):
        before = {
            "name": "V",
            "type": "c",
            "parameter": [
                {
                    "key": "data",
                    "type": "map",
                    "map": [
                        {"key": "a", "type": "template", "value": "A"},
                        {"key": "b", "type": "template", "value": "B"},
                    ],
                },
                {
                    "key": "list",
                    "type": "list",
                    "list": [
                        {"type": "template", "value": "1"},
                        {"type": "template", "value": "2"},
                    ],
                },
            ],
        }
        operation = {
            "operation_id": "o",
            "target_id": "web-main",
            "resource_family": "variable",
            "name": "V",
            "pre_change": before,
        }
        reordered = deepcopy(before)
        reordered["parameter"][0]["map"].reverse()
        reordered["parameter"].reverse()
        self.assertTrue(build_pre_write_comparison(operation, reordered)[0]["pass"])
        for change in ("value", "missing", "extra", "list", "unknown"):
            with self.subTest(change=change):
                saved = deepcopy(before)
                if change == "value":
                    saved["parameter"][0]["map"][0]["value"] = "changed"
                elif change == "missing":
                    saved["parameter"].pop()
                elif change == "extra":
                    saved["parameter"].append({"key": "extra", "type": "template", "value": "X"})
                elif change == "list":
                    saved["parameter"][1]["list"].reverse()
                else:
                    saved["unknown"] = True
                self.assertFalse(build_pre_write_comparison(operation, saved)[0]["pass"])
        duplicate = deepcopy(before)
        duplicate["parameter"].append(deepcopy(duplicate["parameter"][0]))
        with self.assertRaises(GraphError):
            build_pre_write_comparison(operation, duplicate)


class OutputAliasTests(unittest.TestCase):
    def test_cli_rejects_input_aliases_before_setup_and_preserves_files(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for host in (False, True):
                for mode in ("run", "discover"):
                    for field in (
                        ("profiles", "config", "approval-settings") if host else ("profiles",)
                    ):
                        for suffix in (
                            (".execution.json", ".md") if mode == "run" else (".execution.json",)
                        ):
                            with self.subTest(host=host, mode=mode, field=field, suffix=suffix):
                                input_path = base / "request.json"
                                paths = {
                                    "profiles": base / "profiles.json",
                                    "config": base / "config.json",
                                    "approval-settings": base / "approval.json",
                                }
                                paths[field] = input_path.with_suffix(suffix)
                                for path in [input_path, *paths.values()]:
                                    path.write_text('{"sentinel": true}\n', encoding="utf-8")
                                before = {p: p.read_bytes() for p in [input_path, *paths.values()]}
                                args = [
                                    sys.executable,
                                    str(
                                        ROOT
                                        / "scripts"
                                        / ("mcp_host_execute.py" if host else "mcp_execute.py")
                                    ),
                                    "--" + mode,
                                    str(input_path),
                                    "--profiles",
                                    str(paths["profiles"]),
                                ]
                                if mode == "discover":
                                    args += ["--output", str(base / "inventory.json")]
                                if host:
                                    args += [
                                        "--host",
                                        "gemini",
                                        "--server",
                                        "missing",
                                        "--config",
                                        str(paths["config"]),
                                        "--approval-settings",
                                        str(paths["approval-settings"]),
                                    ]
                                result = subprocess.run(
                                    args, capture_output=True, text=True, timeout=15
                                )
                                self.assertEqual(
                                    result.returncode, 2, result.stdout + result.stderr
                                )
                                self.assertIn("Generated output", result.stderr)
                                self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_output_output_input_and_hardlink_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            source.write_text("{}")
            other = source.with_name("other.json")
            for outputs in ([source], [other, other]):
                with self.assertRaises(ValueError):
                    validate_output_paths(inputs=[source], outputs=outputs)
            os.link(source, other)
            with self.assertRaises(ValueError):
                validate_output_paths(inputs=[source], outputs=[other])
            if os.name == "nt":
                with self.assertRaises(ValueError):
                    validate_output_paths(inputs=[source], outputs=[source.with_name("INPUT.JSON")])


if __name__ == "__main__":
    unittest.main()
