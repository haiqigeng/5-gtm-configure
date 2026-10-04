# ruff: noqa: E402
"""Observable acceptance for the current evidence-reuse runtime."""

import sys
import tempfile
import unittest
from collections import Counter
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]
from adapter_runtime import (
    TargetAdapterRegistry,
    _complete_observation,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from adapter_support import AdapterExecutionError, RateLimitError, collect_paginated
from compile_configuration_request import compile_request
from configuration_run import atomic_write, create_from_contract, load_document
from fixtures.mcp_behavior_scenario import PROFILE, FakeGtm, request
from mcp_adapter import McpTargetAdapter, unwrap
from test_mapping_startup_corrections import lead_request
from verification import expected_graph


class MachineryAdoption(unittest.TestCase):
    def run_native(self, transform=None):
        req = request()
        backend = FakeGtm(req)
        calls = Counter()

        def call(tool, args):
            calls[tool.removeprefix("synthetic__"), args["action"]] += 1
            result = backend.call(tool, args)
            return transform(tool, args, result) if transform else result

        contract = compile_request(req)
        run = create_from_contract(
            contract, run_id="machinery", source_locator="Synthetic approval"
        )
        target = run["run"]["targets"][0]
        adapter = McpTargetAdapter(target, deepcopy(PROFILE), call)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, adapter.capabilities())
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "run.json"
        atomic_write(path, run)
        execute_ready_operations(path, registry)
        return backend, calls, adapter, registry, path

    def test_no_hint_quota_waits_100_seconds_at_most_twice(self):
        delays, attempts = [], []

        def fetch(cursor):
            attempts.append(cursor)
            raise RateLimitError("recognized rejection")

        with self.assertRaises(RateLimitError):
            collect_paginated(fetch, max_rate_limit_retries=9, sleep=delays.append)
        self.assertEqual(delays, [100, 100])
        self.assertEqual(len(attempts), 3)

    def test_numeric_and_date_retry_after_preserved(self):
        for header, expected in [("17", 17), ("Wed, 01 Jan 2098 00:00:00 GMT", None)]:
            with self.assertRaises(RateLimitError) as caught:
                unwrap(
                    {
                        "isError": True,
                        "structuredContent": {
                            "error": {"code": 429},
                            "headers": {"Retry-After": header},
                        },
                    }
                )
            if expected is None:
                self.assertGreater(caught.exception.retry_after_seconds, 100)
            else:
                self.assertEqual(caught.exception.retry_after_seconds, expected)

    def test_full_response_and_final_listing_avoid_tag_get(self):
        backend, calls, _, registry, path = self.run_native()
        verify_idempotent_rerun(path, registry)
        run = load_document(path)
        self.assertEqual(run["run"]["status"], "Configured")
        self.assertEqual(calls["gtm_tag", "get"], 0)
        self.assertEqual(len(backend.writes), 1)
        self.assertNotIn("saved_readback", run)
        self.assertEqual(len(run["final_inventories"]), 1)
        tag = next(op for op in run["object_changes"] if op["resource_family"] == "tag")
        names = {item["name"] for item in tag["saved_readback"]["context_objects"]}
        self.assertNotIn("Unrelated existing tag", names)
        self.assertLess(len(names), 5)

    def test_partial_write_response_needs_read(self):
        def partial(tool, args, result):
            if args["action"] == "create":
                result = deepcopy(result)
                result.pop("parameter", None)
            return result

        _, calls, _, registry, path = self.run_native(partial)
        verify_idempotent_rerun(path, registry)
        self.assertEqual(load_document(path)["run"]["status"], "Configured")
        self.assertEqual(calls["gtm_tag", "get"], 1)

    def test_complete_wrong_response_cannot_be_replaced_by_get(self):
        def wrong(tool, args, result):
            if args["action"] == "create":
                result = deepcopy(result)
                result["parameter"][0]["value"] = "wrong_event"
            return result

        _, calls, _, _, path = self.run_native(wrong)
        tag = next(
            op for op in load_document(path)["object_changes"] if op["resource_family"] == "tag"
        )
        self.assertEqual(tag["state"], "uncertain")
        self.assertEqual(calls["gtm_tag", "get"], 0)

    def test_nested_parameter_evidence_is_distinguished_from_conflict(self):
        operation = next(
            op
            for op in create_from_contract(
                compile_request(lead_request()), run_id="nested", source_locator="test"
            )["object_changes"]
            if op["resource_family"] == "tag"
        )
        saved = expected_graph(operation)
        self.assertTrue(_complete_observation(operation, saved))
        partial = deepcopy(saved)
        partial["objects"][0]["parameter"][-1]["list"][0]["map"].pop()
        self.assertFalse(_complete_observation(operation, partial))
        wrong = deepcopy(saved)
        wrong["objects"][0]["parameter"][0]["value"] = "wrong"
        self.assertTrue(_complete_observation(operation, wrong))

    def test_relevant_duplicate_names_fail_even_with_known_ids(self):
        for family in ("tag", "trigger", "variable"):
            with self.subTest(family=family):
                backend, _, adapter, registry, path = self.run_native()
                run = load_document(path)
                op = next(op for op in run["object_changes"] if op["resource_family"] == family)
                self.assertIn(op["object_key"], adapter.known_ids)
                native = next(
                    raw for raw in backend.data[family].values() if raw["name"] == op["name"]
                )
                backend.data[family]["duplicate"] = {**deepcopy(native), family + "Id": "duplicate"}
                with self.assertRaisesRegex(AdapterExecutionError, "Ambiguous"):
                    verify_idempotent_rerun(path, registry)
                self.assertNotEqual(load_document(path)["run"]["status"], "Configured")

    def test_trimmed_final_listing_requires_get_but_retains_conflict_evidence(self):
        backend, calls, adapter, registry, path = self.run_native()
        original = adapter.list_resource_page

        def trimmed(family, cursor):
            page = original(family, cursor)
            page["items"] = [
                {
                    key: value
                    for key, value in item.items()
                    if key in {"name", family + "Id", "accountId", "containerId", "workspaceId"}
                }
                for item in page["items"]
            ]
            return page

        adapter.list_resource_page = trimmed
        verify_idempotent_rerun(path, registry)
        self.assertEqual(load_document(path)["run"]["status"], "Configured")
        self.assertEqual(calls["gtm_tag", "get"], 1)

    def test_exact_compiler_derivations_and_ambiguous_trigger_stays_explicit(self):
        req = lead_request()
        req["field_bindings"][0] = {
            key: value
            for key, value in req["field_bindings"][0].items()
            if key in {"requirement_id", "field_scope", "destination_field", "missing_behavior"}
        }
        req["execution_topologies"][0].pop("normal_triggers")
        contract = compile_request(req)
        self.assertEqual(
            contract["implementation"]["field_bindings"][0]["mapping_method"], "direct-dlv"
        )
        self.assertEqual(
            contract["execution_topologies"][0]["normal_triggers"][0]["role"], "source-event"
        )
        req["reuse_candidates"][0]["intended"]["filter"] = [
            {
                "type": "equals",
                "parameter": [
                    {"key": "arg0", "type": "template", "value": "{{Extra}}"},
                    {"key": "arg1", "type": "template", "value": "yes"},
                ],
            }
        ]
        with self.assertRaises(ValueError):
            compile_request(req)

    def test_transformed_or_non_v2_dlv_is_not_derived(self):
        for mutation in ("format", "v1"):
            req = lead_request()
            req["field_bindings"][0].pop("native_binding")
            variable = req["reuse_candidates"][-1]["intended"]
            if mutation == "format":
                variable["formatValue"] = {"caseConversionType": "UPPERCASE"}
            else:
                next(row for row in variable["parameter"] if row["key"] == "dataLayerVersion")[
                    "value"
                ] = "1"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                compile_request(req)

    def test_small_stable_id_update_keeps_targeted_final_read(self):
        from test_current_adapter_runtime import FakeAdapter, capabilities
        from test_effective_configuration_guardrails import settings_contract

        class Adapter(FakeAdapter):
            lists = 0
            reads = 0

            def list_resource_page(self, family, cursor):
                self.lists += 1
                return super().list_resource_page(family, cursor)

            def read(self, operation):
                self.reads += 1
                return super().read(operation)

        run = create_from_contract(
            settings_contract(), run_id="small-update", source_locator="test"
        )
        target = run["run"]["targets"][0]
        adapter = Adapter(existing={"Google Settings"})
        adapter.bind_target(target)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, capabilities("variable", "tag"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry)
            lists, reads = adapter.lists, adapter.reads
            verify_idempotent_rerun(path, registry)
            self.assertEqual(adapter.lists, lists)
            self.assertEqual(adapter.reads, reads + 1)
            self.assertEqual(load_document(path)["run"]["status"], "Configured")

    def test_final_inventory_boundaries_reject_bad_metadata(self):
        from run_state import validate_document

        _, _, _, registry, path = self.run_native()
        verify_idempotent_rerun(path, registry)
        run = load_document(path)
        for change in ("target", "duplicate", "time", "pagination", "identity"):
            changed = deepcopy(run)
            inventory = changed["final_inventories"][0]
            if change == "target":
                inventory["target_id"] = "other"
            elif change == "duplicate":
                changed["final_inventories"].append(deepcopy(inventory))
            elif change == "time":
                inventory["observed_at"] = "not-a-time"
            elif change == "pagination":
                inventory["resource_pagination"]["tag"]["exhausted"] = False
            else:
                inventory["source_identity"]["workspace_id"] = "other"
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_document(changed)

    def test_locked_execution_does_not_revalidate_every_checkpoint(self):
        import run_state

        with patch("run_state.validate_document", wraps=run_state.validate_document) as validate:
            _, _, _, _, path = self.run_native()
        self.assertLessEqual(validate.call_count, 8)
        self.assertTrue(
            all(op["state"] == "verified" for op in load_document(path)["object_changes"])
        )


if __name__ == "__main__":
    unittest.main()
