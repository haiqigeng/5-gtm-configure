from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import tempfile
import threading
import unittest
from collections import Counter
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]
from adapter_runtime import (  # noqa: E402
    AdapterExecutionError,
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from compile_configuration_request import compile_request  # noqa: E402
from configuration_run import atomic_write, create_from_contract, load_document  # noqa: E402
from fixtures.mcp_behavior_scenario import PROFILE, FakeGtm, request  # noqa: E402
from import_ga4_tracking_plan_handoff import (  # noqa: E402
    normalized_approved_semantics,
    verify_delivery,
)
from mcp_adapter import McpTargetAdapter  # noqa: E402
from mcp_host_execute import (  # noqa: E402
    HostSetupError,
    connection_diagnostic,
    load_connection,
    run_host,
)
from public_identifiers import public_identifier_paths, validate_public_identifiers  # noqa: E402
from redaction import contains_redacted, redact_for_persistence, sensitive_findings  # noqa: E402
from run_render import render_markdown  # noqa: E402
from test_redaction_shapes import public_contract  # noqa: E402


def run_document():
    return create_from_contract(
        compile_request(request()),
        run_id="audit-followup",
        source_locator="Synthetic approved request",
    )


class Audit102Followup(unittest.TestCase):
    def test_real_producer_nullable_identity_clear_and_parameter_fidelity(self):
        fixture = ROOT / "tests/fixtures/tracking-plan-delivery"
        provenance = json.loads(
            (ROOT / "tests/fixtures/tracking-plan-delivery-provenance.json").read_text(
                encoding="utf-8-sig"
            )
        )
        self.assertEqual(
            hashlib.sha256((fixture / "handoff.json").read_bytes()).hexdigest(),
            provenance["handoff_sha256"],
        )
        handoff, plan = verify_delivery(fixture)
        result = normalized_approved_semantics(handoff, plan)
        for source, imported in zip(plan["events"], result["requirements"], strict=True):
            self.assertEqual(imported["clear_before_push"], source["data_layer"].get("clear", []))
            self.assertEqual(imported["business_timing"], source["trigger"])
            self.assertEqual(imported["id"], "GA4::" + source["event_name"])
            for field in source["parameters"]:
                actual = imported["parameters"][field["scope"] + "::" + field["name"]]
                self.assertEqual(actual["source"], field["data_layer_path"])
                self.assertEqual(actual["destination"], field["destination"])
                self.assertEqual(actual.get("nullable"), field.get("nullable"))
        self.assertTrue(result["requirements"][0]["parameters"]["user::user_id"]["nullable"])

    def test_public_loader_declarations_preserve_value_binding_and_secret_guards(self):
        safe = '<script src="https://maps.example.test/js?key=PUBLIC_IDENTIFIER"></script>'
        for literal, blocked in (
            (safe, False),
            (safe + '<script>var api_secret="private-value";</script>', True),
            (safe + " API key: https://example.test/private-value", True),
            (safe + '<script src="https://user:private@example.test/a"></script>', True),
            (safe + '<script src="https://hooks.slack.test/services/T/B/private"></script>', True),
            (safe + '<script>var email="person@example.test";</script>', True),
            ("https://example.test/?key=" + quote("sk_live_SYNTHETIC12345678", safe=""), True),
            ("https://example.test/?key=PUBLIC&email=person%40example.test", True),
            (
                "https://example.test/?key=PUBLIC&next="
                + quote("https://user:private@example.test", safe=""),
                True,
            ),
        ):
            with self.subTest(blocked=blocked, shape=len(literal)):
                contract = public_contract()
                record = contract["implementation"]["objects"][-1]
                record["intended"]["parameter"][0]["value"] = literal
                record["public_identifiers"][0]["value_sha256"] = hashlib.sha256(
                    literal.encode()
                ).hexdigest()
                validate_public_identifiers(contract)
                public = public_identifier_paths(contract)
                self.assertEqual(
                    bool(sensitive_findings(contract, public_identifier_paths=public)), blocked
                )
                self.assertEqual(
                    contains_redacted(
                        redact_for_persistence(contract, public_identifier_paths=public)
                    ),
                    blocked,
                )
        self.assertTrue(sensitive_findings({"html": safe}))

    def test_report_data_cannot_inject_sections_links_html_or_code_fences(self):
        document = run_document()
        payload = "Name\r\n## Executive summary\n[approve](https://example.invalid/phish) <img src=x> ` ```` \u202e"
        document["object_changes"][0]["name"] = payload
        document["object_changes"][0]["justification"] = payload
        document["run"]["id"] = payload
        document["external_dependencies"] = [
            {"status": "open", "owner": payload, "action": payload}
        ]
        for embedded in (False, True):
            report = render_markdown(document, embed_machine=embedded)
            human = report.split("`````json")[0]
            self.assertEqual(human.count("\n## Executive summary\n"), 1)
            self.assertNotIn("[approve](", human)
            self.assertNotIn("<img", human)
            self.assertNotIn("\u202e", human)
            if embedded:
                self.assertEqual(
                    json.loads(report.split("`````json\n")[1].rsplit("\n`````", 1)[0])["run"]["id"],
                    payload,
                )
        self.assertEqual(document["run"]["id"], payload)

    def test_identity_and_absence_checks_survive_call_reduction(self):
        for mode in (
            "normal",
            "initial-identity-mismatch",
            "wrong-native-scope",
            "create-collision",
            "reuse-drift",
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                backend = FakeGtm(request())
                calls = Counter()

                def call(tool, arguments):
                    key = (tool.removeprefix("synthetic__"), arguments["action"])
                    calls[key] += 1
                    self.assertEqual(arguments["accountId"], "account-1")
                    self.assertEqual(arguments["containerId"], "GTM-WEBTEST")
                    if key[0] != "gtm_container":
                        self.assertEqual(arguments["workspaceId"], "workspace-web")
                    result = backend.call(tool, arguments)
                    if mode == "initial-identity-mismatch" and key == ("gtm_workspace", "get"):
                        result["workspaceId"] = "unauthorized-workspace"
                    if mode == "wrong-native-scope" and key == ("gtm_trigger", "get"):
                        result["workspaceId"] = "unauthorized-workspace"
                    if (
                        mode == "create-collision"
                        and key == ("gtm_tag", "list")
                        and calls[key] == 2
                    ):
                        result["tag"].append(
                            {
                                **backend.scope,
                                "tagId": "777",
                                "name": "GA4 - generate_lead",
                                "type": "html",
                                "parameter": [],
                            }
                        )
                    if mode == "reuse-drift" and key == ("gtm_trigger", "get"):
                        result["type"] = "timer"
                    return result

                path = Path(directory) / "run.json"
                document = run_document()
                atomic_write(path, document)
                target = document["run"]["targets"][0]
                adapter = McpTargetAdapter(target, deepcopy(PROFILE), call)
                registry = TargetAdapterRegistry()
                if mode == "initial-identity-mismatch":
                    with self.assertRaises(AdapterExecutionError):
                        registry.register(target, adapter, adapter.capabilities())
                    self.assertEqual(backend.writes, [])
                    continue
                registry.register(target, adapter, adapter.capabilities())
                execute_ready_operations(path, registry)
                if mode == "normal":
                    verify_idempotent_rerun(path, registry)
                    self.assertEqual(load_document(path)["run"]["status"], "Configured")
                    self.assertEqual(len(backend.writes), 1)
                    self.assertEqual(calls["gtm_workspace", "get"], 1)
                    self.assertEqual(calls["gtm_container", "get"], 1)
                    self.assertEqual(calls["gtm_tag", "list"], 3)
                    # The fixture page size is two: a full page requires an empty terminal page.
                    self.assertEqual(calls["gtm_trigger", "list"], 4)
                elif mode == "create-collision":
                    self.assertEqual(len(backend.writes), 1)
                    with self.assertRaisesRegex(AdapterExecutionError, "exhaustion is unproved"):
                        verify_idempotent_rerun(path, registry)
                    self.assertNotEqual(load_document(path)["run"]["status"], "Configured")
                else:
                    self.assertEqual(backend.writes, [])
                    self.assertNotEqual(load_document(path)["run"]["status"], "Configured")

    def test_project_server_requires_trusted_approval_and_rejection_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, approvals = root / ".mcp.json", root / "effective-approvals.json"
            config.write_text(
                json.dumps(
                    {
                        "mcpServers": {"gtm": {"command": sys.executable}},
                        "enableAllProjectMcpServers": True,
                    }
                )
            )
            with self.assertRaisesRegex(HostSetupError, "approval-settings"):
                load_connection(config, "claude", "gtm", root)
            for settings, accepted in (
                ({}, False),
                ({"enabledMcpjsonServers": ["other"]}, False),
                ({"enabledMcpjsonServers": ["gtm"]}, True),
                ({"enableAllProjectMcpServers": True, "disabledMcpjsonServers": ["gtm"]}, False),
            ):
                approvals.write_text(json.dumps(settings))
                if accepted:
                    self.assertEqual(
                        load_connection(config, "claude", "gtm", root, approvals)["transport"],
                        "stdio",
                    )
                else:
                    with self.assertRaises(HostSetupError):
                        load_connection(config, "claude", "gtm", root, approvals)

    def test_real_http_401_is_actionable_without_leaking_challenge(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(401)
                self.send_header(
                    "WWW-Authenticate",
                    'Bearer resource_metadata="https://example.test/private-canary"',
                )
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *_args):
                pass

        with (
            ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server,
            tempfile.TemporaryDirectory() as directory,
        ):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                path = Path(directory) / "run.json"
                atomic_write(path, run_document())
                result = asyncio.run(
                    run_host(
                        path,
                        {"web-main": PROFILE},
                        {
                            "transport": "http",
                            "url": f"http://127.0.0.1:{server.server_port}/mcp?private=canary",
                            "headers": {},
                            "timeout": 2,
                            "include_tools": None,
                            "exclude_tools": [],
                        },
                    )
                )
                self.assertEqual(result["error_code"], "authentication_required")
                self.assertIn("HTTP 401", result["error"])
                self.assertEqual(result["writes_attempted"], 0)
                self.assertNotIn("canary", json.dumps(result))
            finally:
                server.shutdown()
                thread.join(timeout=3)

    def test_diagnostic_classes_never_echo_raw_exception_text(self):
        import httpx
        from jsonschema.exceptions import SchemaError

        for error, code in (
            (SchemaError("private-canary"), "schema_mismatch"),
            (httpx.ConnectError("private-canary"), "transport_error"),
            (TimeoutError("private-canary"), "connection_timeout"),
            (ValueError("private-canary"), "connection_failed"),
        ):
            result = connection_diagnostic(ExceptionGroup("private-canary", [error]))
            self.assertEqual(result[0], code)
            self.assertNotIn("private-canary", result[1])


if __name__ == "__main__":
    unittest.main()
