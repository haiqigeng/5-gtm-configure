from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]
from adapter_support import AdapterExecutionError  # noqa: E402
from compile_configuration_request import compile_request  # noqa: E402
from configuration_run import atomic_write, create_from_contract, load_document  # noqa: E402
from fixtures.mcp_behavior_scenario import PROFILE, request  # noqa: E402
from mcp_host_execute import HostSetupError, SdkTransport, load_connection  # noqa: E402

SERVER = ROOT / "tests/fixtures/mcp_sdk_server.py"
RUNNER = ROOT / "scripts/mcp_host_execute.py"


class McpHostTests(unittest.TestCase):
    def test_selected_host_config_expansion_and_filters(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"GTM_TEST_VALUE": "a'b $()"}),
        ):
            root = Path(directory)
            for host, source in (("claude", "${GTM_TEST_VALUE}"), ("gemini", "$GTM_TEST_VALUE")):
                config = root / (host + ".json")
                config.write_text(
                    json.dumps(
                        {
                            "mcpServers": {
                                "gtm": {
                                    "command": sys.executable,
                                    "args": [],
                                    "env": {"KEY": source},
                                    "cwd": "server",
                                    "includeTools": ["gtm_tag"],
                                    "excludeTools": ["gtm_folder"],
                                }
                            }
                        }
                    )
                )
                value = load_connection(config, host, "gtm", root)
                self.assertEqual(value["env"], {"KEY": "a'b $()"})
                self.assertEqual(value["cwd"], str((root / "server").resolve()))
                self.assertEqual(value["include_tools"], ["gtm_tag"])
                self.assertEqual(value["exclude_tools"], ["gtm_folder"])

    def test_disabled_and_host_managed_auth_fail_before_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            for extra in (
                {"disabled": True},
                {"oauth": {"enabled": True}},
                {"headersHelper": "do-not-run"},
                {"authProviderType": "google_credentials"},
            ):
                config.write_text(
                    json.dumps({"mcpServers": {"gtm": {"command": sys.executable, **extra}}})
                )
                with self.assertRaises(HostSetupError):
                    load_connection(config, "claude", "gtm", root)
            config.write_text(
                json.dumps(
                    {
                        "mcp": {"excluded": ["gtm"]},
                        "mcpServers": {"gtm": {"command": sys.executable}},
                    }
                )
            )
            with self.assertRaises(HostSetupError):
                load_connection(config, "gemini", "gtm", root)

    def test_forbidden_calls_and_secrets_never_reach_session(self):
        tools = {"gtm_tag": SimpleNamespace(inputSchema={"type": "object"})}
        transport = SdkTransport(None, None, tools, {"gtm_tag": {"get", "create"}}, 1)
        for tool, arguments in (
            ("gtm_tag", {"action": "publish"}),
            ("gtm_version", {"action": "create"}),
            ("gtm_tag", {"action": "create", "api_secret": "never-send"}),
        ):
            with self.assertRaises(AdapterExecutionError):
                transport(tool, arguments)
        self.assertEqual(transport.calls, 0)
        self.assertEqual(transport.writes_attempted, 0)

    def test_unknown_claude_transport_is_not_treated_as_http(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "gtm": {"type": "unknown", "url": "https://example.invalid/mcp"}
                        }
                    }
                )
            )
            with self.assertRaises(HostSetupError):
                load_connection(config, "claude", "gtm", root)

    def exercise(self, host, protocol="stdio", *, uncertain=False, configured_protocol=None):
        with tempfile.TemporaryDirectory(prefix="GTM d'O'Brien ") as directory:
            root = Path(directory)
            run_path, state_path = root / "run.json", root / "service.json"
            atomic_write(
                run_path,
                create_from_contract(
                    compile_request(request()),
                    run_id="HOST-TEST",
                    source_locator="Approved synthetic request",
                ),
            )
            profile = deepcopy(PROFILE)
            profile["tool_prefix"] = ""
            profiles = root / "profiles.json"
            profiles.write_text(json.dumps({"web-main": profile}))
            marker = "d’O’Brien 日本語 $() `literal`"
            server_args = ["-B", str(SERVER), "--state", str(state_path), "--marker", marker]
            if uncertain:
                server_args.append("--uncertain")
            child = None
            try:
                if protocol == "stdio":
                    definition = {
                        "command": sys.executable,
                        "args": server_args,
                        "env": {"SYNTHETIC_TOKEN": "host-test-private-diagnostic"},
                        "timeout": 8000,
                    }
                else:
                    with socket.socket() as sock:
                        sock.bind(("127.0.0.1", 0))
                        port = sock.getsockname()[1]
                    child = subprocess.Popen(
                        [
                            sys.executable,
                            *server_args,
                            "--transport",
                            protocol,
                            "--port",
                            str(port),
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    deadline = time.monotonic() + 10
                    while True:
                        try:
                            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                                break
                        except OSError:
                            if child.poll() is not None or time.monotonic() > deadline:
                                self.fail("Synthetic HTTP server did not start")
                            time.sleep(0.1)
                    url = f"http://127.0.0.1:{port}/{'mcp' if protocol == 'http' else 'sse'}"
                    definition = (
                        {"type": configured_protocol or protocol, "url": url}
                        if host == "claude"
                        else {"httpUrl" if protocol == "http" else "url": url}
                    )
                    definition["timeout"] = 8000
                config = root / (".mcp.json" if host == "claude" else "settings.json")
                config.write_text(
                    json.dumps({"mcpServers": {"synthetic-gtm": definition}}, ensure_ascii=False),
                    encoding="utf-8",
                )
                command = [
                    sys.executable,
                    "-B",
                    str(RUNNER),
                    "--host",
                    host,
                    "--config",
                    str(config),
                    "--server",
                    "synthetic-gtm",
                    "--run",
                    str(run_path),
                    "--profiles",
                    str(profiles),
                ]
                if host == "claude":
                    approvals = root / "effective-approvals.json"
                    approvals.write_text(json.dumps({"enabledMcpjsonServers": ["synthetic-gtm"]}))
                    command.extend(["--approval-settings", str(approvals)])
                result = subprocess.run(
                    command, capture_output=True, text=True, encoding="utf-8", timeout=40
                )
                self.assertNotIn("host-test-private-diagnostic", result.stdout + result.stderr)
                self.assertEqual(
                    result.returncode, 1 if uncertain else 0, result.stdout + result.stderr
                )
                run = load_document(run_path)
                state = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual(len(state["writes"]), 1)
                self.assertEqual(state["marker"], marker)
                self.assertEqual(state["data"]["tag"]["999"]["fingerprint"], "7")
                self.assertEqual(run["run"]["status"], "Partial" if uncertain else "Configured")
                if uncertain:
                    self.assertTrue(any(op["state"] == "uncertain" for op in run["object_changes"]))
                else:
                    self.assertTrue(run["idempotency"]["checked"])
                    self.assertEqual(state["data"]["tag"]["501"]["blockingTriggerId"], ["102"])
                    second = subprocess.run(
                        command, capture_output=True, text=True, encoding="utf-8", timeout=40
                    )
                    self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
                    self.assertEqual(json.loads(second.stdout)["writes_attempted"], 0)
                    second_state = json.loads(state_path.read_text(encoding="utf-8"))
                    self.assertEqual(second_state["data"], state["data"])
                    self.assertEqual(len(second_state["writes"]), 1)
            finally:
                if child is not None:
                    child.terminate()
                    child.wait(timeout=10)

    def test_claude_stdio(self):
        self.exercise("claude")

    def test_gemini_stdio(self):
        self.exercise("gemini")

    def test_claude_http(self):
        self.exercise("claude", "http")

    def test_claude_streamable_http(self):
        self.exercise("claude", "http", configured_protocol="streamable-http")

    def test_gemini_http(self):
        self.exercise("gemini", "http")

    def test_claude_sse(self):
        self.exercise("claude", "sse")

    def test_gemini_sse(self):
        self.exercise("gemini", "sse")

    def test_interrupted_save_stays_uncertain_without_duplicate(self):
        self.exercise("claude", uncertain=True)


if __name__ == "__main__":
    unittest.main()
