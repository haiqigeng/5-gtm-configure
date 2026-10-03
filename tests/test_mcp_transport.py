# ruff: noqa: E402
from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]
from adapter_support import AdapterExecutionError, AmbiguousWriteError, collect_paginated
from configuration_run import atomic_write, create_from_contract
from current_support import valid_web_contract
from mcp_adapter import FAMILIES, McpTargetAdapter
from mcp_transport import StdioTransport


def profile(*families):
    return {
        "tool_prefix": "synthetic__",
        "workspace_path": [],
        "container_path": [],
        "status_path": [],
        "families": {
            family: {
                "actions": ["get", "list", "create", "update", "remove"],
                "first_page": 1,
                "page_size": 2,
                "list_path": [family],
                "object_path": [],
            }
            for family in families
        },
    }


class McpTransportTests(unittest.TestCase):
    def test_cold_read_builtin_trigger_needs_no_trigger_tool(self):
        calls = []
        raw = {
            "accountId": "account-1",
            "containerId": "GTM-WEBTEST",
            "workspaceId": "workspace-web",
            "name": "All pages",
            "tagId": "42",
            "type": "googtag",
            "firingTriggerId": ["2147479553"],
        }

        def call(tool, args):
            calls.append(tool)
            return deepcopy(raw)

        adapter = McpTargetAdapter(valid_web_contract()["targets"][0], profile("tag"), call)
        result = adapter.read(
            {
                "name": "All pages",
                "object_key": "web-main::tag::All pages",
                "target_id": "web-main",
                "resource_family": "tag",
                "object_id": "42",
                "action": "reuse",
            }
        )
        self.assertEqual(calls, ["synthetic__gtm_tag"])
        self.assertEqual(result["objects"][0]["firingTriggerId"], ["2147479553"])

    def test_fresh_fingerprints_all_supported_native_families(self):
        target = valid_web_contract()["targets"][0]
        for family, (_, id_field) in FAMILIES.items():
            with self.subTest(family=family):
                raw = {
                    "accountId": target["account_id"],
                    "containerId": target["container_id"],
                    "workspaceId": target["workspace_id"],
                    "name": "Native fixture",
                    "type": "inspected-fixture-type",
                    id_field: "42",
                    "fingerprint": "fresh",
                    "notes": "Équipe d’O’Brien — 日本語",
                }
                calls = []

                def call(tool, args):
                    calls.append(deepcopy(args))
                    if args["action"] == "get":
                        return deepcopy(raw)
                    if args["action"] == "list":
                        return {family: [deepcopy(raw)]}
                    if args["action"] in {"update", "remove"}:
                        self.assertEqual(args["fingerprint"], "fresh")
                    return deepcopy(raw)

                adapter = McpTargetAdapter(target, profile(family), call)
                op = {
                    "name": raw["name"],
                    "object_key": f"web-main::{family}::{raw['name']}",
                    "target_id": "web-main",
                    "resource_family": family,
                    "object_id": "42",
                    "action": "update",
                    "pre_change": {**raw, "fingerprint": "stale"},
                    "intended": deepcopy(raw),
                }
                adapter.read(op)
                adapter.mutate(op)
                self.assertEqual(calls[-1]["createOrUpdateConfig"]["notes"], raw["notes"])
                self.assertNotIn("fingerprint", calls[-1]["createOrUpdateConfig"])
                with self.assertRaisesRegex(AdapterExecutionError, "preceding scoped read"):
                    adapter.mutate(op)
                op["action"] = "remove"
                adapter.read(op)
                adapter.mutate(op)

    def test_explicit_more_flag_overrides_short_page_and_empty_more_fails(self):
        p = profile("tag")
        p["families"]["tag"]["has_more_path"] = ["has_more"]
        target = valid_web_contract()["targets"][0]
        adapter = McpTargetAdapter(
            target,
            p,
            lambda tool, args: {
                "tag": [
                    {
                        "name": str(args["page"]),
                        "accountId": target["account_id"],
                        "containerId": target["container_id"],
                        "workspaceId": target["workspace_id"],
                    }
                ],
                "has_more": args["page"] == 1,
            },
        )
        self.assertEqual(
            len(collect_paginated(lambda cursor: adapter.list_resource_page("tag", cursor))), 2
        )
        bad = McpTargetAdapter(target, p, lambda tool, args: {"tag": [], "has_more": True})
        with self.assertRaisesRegex(AdapterExecutionError, "continuation"):
            bad.list_resource_page("tag", None)

    def test_required_reference_list_capability_fails_before_dispatch(self):
        target = valid_web_contract()["targets"][0]
        for inspected in (profile("tag"), profile("tag", "folder")):
            if "folder" in inspected["families"]:
                inspected["families"]["folder"]["actions"] = ["get"]
            with self.subTest(families=inspected["families"]):
                adapter = McpTargetAdapter(
                    target, inspected, lambda *args: self.fail("Unexpected dispatch")
                )
                with self.assertRaisesRegex(AdapterExecutionError, "list capability"):
                    adapter._serialize_references({"parentFolderId": "17"})
                self.assertNotIn("folder", adapter.complete_families)

    def test_invalid_profiles_fail_before_a_call(self):
        target = valid_web_contract()["targets"][0]
        cases = [{}, {**profile("tag"), "status_path": None}, profile("destination")]
        malformed = profile("tag")
        malformed["families"]["tag"]["actions"] = ["publish"]
        cases.append(malformed)
        for item in cases:
            with self.assertRaises(AdapterExecutionError):
                McpTargetAdapter(target, item, lambda *args: self.fail("Unexpected call"))

    def test_stream_rejects_mismatched_reply_and_accepts_data_without_files(self):
        for identifier in ("a" * 32, "b" * 32):
            reply = (
                json.dumps(
                    {"id": identifier, "result": {"name": "d’O’Brien", "large": "日" * 40000}}
                )
                .encode("utf-16-be")
                .hex()
            )
            stream = io.BytesIO((reply + "\n.\n").encode())
            output = io.StringIO()
            with patch("mcp_transport.uuid4", return_value=SimpleNamespace(hex="a" * 32)):
                transport = StdioTransport(input_stream=stream, output_stream=output)
                if identifier.startswith("a"):
                    self.assertEqual(
                        transport("synthetic__gtm_tag", {"action": "get"})["large"], "日" * 40000
                    )
                else:
                    with self.assertRaisesRegex(
                        AdapterExecutionError, "read transport failed"
                    ) as caught:
                        transport("synthetic__gtm_tag", {"action": "get"})
                    self.assertEqual(caught.exception.code, "read_failed")

    def test_stream_mismatched_write_reply_remains_ambiguous(self):
        reply = json.dumps({"id": "b" * 32, "result": {}}).encode("utf-16-be").hex()
        transport = StdioTransport(
            input_stream=io.BytesIO((reply + "\n.\n").encode()), output_stream=io.StringIO()
        )
        with patch("mcp_transport.uuid4", return_value=SimpleNamespace(hex="a" * 32)):
            with self.assertRaisesRegex(AmbiguousWriteError, "identity mismatch"):
                transport("synthetic__gtm_tag", {"action": "create"})

    def test_missing_profile_diagnostic_does_not_claim_a_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            profiles = Path(directory) / "profiles.json"
            atomic_write(
                path,
                create_from_contract(
                    valid_web_contract(), run_id="setup", source_locator="Synthetic"
                ),
            )
            profiles.write_text("{}")
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/mcp_execute.py"),
                    "--run",
                    str(path),
                    "--profiles",
                    str(profiles),
                ],
                input="",
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 1)
            diagnostic = json.loads(path.with_suffix(".execution.json").read_text())
            self.assertEqual((diagnostic["status"], diagnostic["writes_attempted"]), ("Blocked", 0))
            self.assertIn("Missing MCP profile", diagnostic["error"])
            self.assertNotIn("uncertain", diagnostic["next_action"])
