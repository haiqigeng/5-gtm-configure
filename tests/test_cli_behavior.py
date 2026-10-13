"""Behavioral tests owned by cli."""

from support import authenticated_delivery as fixture_authenticated_delivery
from support import input_integrity as fixture_input_integrity
from support import native_boundaries as fixture_native_boundaries
from support import phase_contracts as fixture_phase_contracts


class TestAuthenticatedDelivery(fixture_authenticated_delivery.Audit102FollowupFixture):
    def test_project_server_requires_trusted_approval_and_rejection_wins(self):
        with fixture_authenticated_delivery.tempfile.TemporaryDirectory() as directory:
            root = fixture_authenticated_delivery.Path(directory)
            config, approvals = root / ".mcp.json", root / "effective-approvals.json"
            config.write_text(
                fixture_authenticated_delivery.json.dumps(
                    {
                        "mcpServers": {
                            "gtm": {"command": fixture_authenticated_delivery.sys.executable}
                        },
                        "enableAllProjectMcpServers": True,
                    }
                )
            )
            with self.assertRaisesRegex(
                fixture_authenticated_delivery.HostSetupError, "approval-settings"
            ):
                fixture_authenticated_delivery.load_connection(config, "claude", "gtm", root)
            for settings, accepted in (
                ({}, False),
                ({"enabledMcpjsonServers": ["other"]}, False),
                ({"enabledMcpjsonServers": ["gtm"]}, True),
                ({"enableAllProjectMcpServers": True, "disabledMcpjsonServers": ["gtm"]}, False),
            ):
                approvals.write_text(fixture_authenticated_delivery.json.dumps(settings))
                if accepted:
                    self.assertEqual(
                        fixture_authenticated_delivery.load_connection(
                            config, "claude", "gtm", root, approvals
                        )["transport"],
                        "stdio",
                    )
                else:
                    with self.assertRaises(fixture_authenticated_delivery.HostSetupError):
                        fixture_authenticated_delivery.load_connection(
                            config, "claude", "gtm", root, approvals
                        )

    def test_real_http_401_is_actionable_without_leaking_challenge(self):
        class Handler(fixture_authenticated_delivery.BaseHTTPRequestHandler):
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
            fixture_authenticated_delivery.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server,
            fixture_authenticated_delivery.tempfile.TemporaryDirectory() as directory,
        ):
            thread = fixture_authenticated_delivery.threading.Thread(
                target=server.serve_forever, daemon=True
            )
            thread.start()
            try:
                path = fixture_authenticated_delivery.Path(directory) / "run.json"
                fixture_authenticated_delivery.atomic_write(
                    path, fixture_authenticated_delivery.run_document()
                )
                result = fixture_authenticated_delivery.asyncio.run(
                    fixture_authenticated_delivery.run_host(
                        path,
                        {"web-main": fixture_authenticated_delivery.PROFILE},
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
                self.assertNotIn("canary", fixture_authenticated_delivery.json.dumps(result))
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
            result = fixture_authenticated_delivery.connection_diagnostic(
                ExceptionGroup("private-canary", [error])
            )
            self.assertEqual(result[0], code)
            self.assertNotIn("private-canary", result[1])


class TestNativeBoundaries(fixture_native_boundaries.OutputAliasTestsFixture):
    def test_cli_rejects_input_aliases_before_setup_and_preserves_files(self):
        with fixture_native_boundaries.tempfile.TemporaryDirectory() as directory:
            base = fixture_native_boundaries.Path(directory)
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
                                    fixture_native_boundaries.sys.executable,
                                    str(
                                        fixture_native_boundaries.ROOT / "scripts/configure_gtm.py"
                                    ),
                                    "mcp-host" if host else "mcp",
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
                                result = fixture_native_boundaries.subprocess.run(
                                    args, capture_output=True, text=True, timeout=15
                                )
                                self.assertEqual(
                                    result.returncode, 2, result.stdout + result.stderr
                                )
                                self.assertIn("Generated output", result.stderr)
                                self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_output_output_input_and_hardlink_aliases(self):
        with fixture_native_boundaries.tempfile.TemporaryDirectory() as directory:
            source = fixture_native_boundaries.Path(directory) / "input.json"
            source.write_text("{}")
            other = source.with_name("other.json")
            for outputs in ([source], [other, other]):
                with self.assertRaises(ValueError):
                    fixture_native_boundaries.validate_output_paths(
                        inputs=[source], outputs=outputs
                    )
            fixture_native_boundaries.os.link(source, other)
            with self.assertRaises(ValueError):
                fixture_native_boundaries.validate_output_paths(inputs=[source], outputs=[other])
            if fixture_native_boundaries.os.name == "nt":
                with self.assertRaises(ValueError):
                    fixture_native_boundaries.validate_output_paths(
                        inputs=[source], outputs=[source.with_name("INPUT.JSON")]
                    )


class TestPhaseContracts(fixture_phase_contracts.CurrentContractAndRunTestFixture):
    def test_cli_rejects_caller_baseline_and_wraps_invalid_readback_as_coded_json(self) -> None:
        run = fixture_phase_contracts.create_from_contract(
            fixture_phase_contracts.valid_web_contract(),
            run_id="RUN-CLI-EVIDENCE",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        with fixture_phase_contracts.tempfile.TemporaryDirectory() as temporary:
            root = fixture_phase_contracts.Path(temporary)
            run_path = root / "run.json"
            invalid_readback_path = root / "invalid-readback.json"
            run_path.write_text(fixture_phase_contracts.json.dumps(run), encoding="utf-8")
            invalid_readback_path.write_text(
                fixture_phase_contracts.json.dumps({"name": "Google tag - Web transport"}),
                encoding="utf-8",
            )
            baseline = fixture_phase_contracts.subprocess.run(
                [
                    fixture_phase_contracts.sys.executable,
                    str(fixture_phase_contracts.ROOT / "scripts/configure_gtm.py"),
                    "run",
                    "baseline",
                ],
                cwd=fixture_phase_contracts.ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(baseline.returncode, 2)
            self.assertIn("invalid choice: 'baseline'", baseline.stderr)
            recorded = fixture_phase_contracts.record_target_baseline(
                run,
                target_id="web-main",
                resources={"tag": [], "trigger": [], "variable": []},
                captured_at="2026-08-18T00:00:01Z",
                preexisting_workspace_changes=[],
                capture_evidence=fixture_phase_contracts.complete_capture_evidence(
                    {"tag": [], "trigger": [], "variable": []}, run["run"]["targets"][0]
                ),
            )
            run_path.write_text(fixture_phase_contracts.json.dumps(recorded), encoding="utf-8")
            self.assertTrue(recorded["container_baselines"][0]["complete"])
            ready_operation = next(
                item for item in recorded["object_changes"] if not item["dependencies"]
            )
            checkpoint = fixture_phase_contracts.subprocess.run(
                [
                    fixture_phase_contracts.sys.executable,
                    str(fixture_phase_contracts.ROOT / "scripts/configure_gtm.py"),
                    "run",
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
                cwd=fixture_phase_contracts.ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(checkpoint.returncode, 2)
            error = fixture_phase_contracts.json.loads(checkpoint.stdout)
            self.assertEqual(error["error_code"], "invalid_run")
            self.assertIn("objects array", error["error"])


class TestInputIntegrity(fixture_input_integrity.RuntimeHardeningTestFixture):
    def test_run_cli_exposes_targeted_json_input_error_codes(self) -> None:
        with fixture_input_integrity.tempfile.TemporaryDirectory() as temporary:
            root = fixture_input_integrity.Path(temporary)
            cases = []
            missing = root / "missing.json"
            cases.append((missing, "io_error"))
            invalid_encoding = root / "encoding.json"
            invalid_encoding.write_bytes(b'{"value": \xff}')
            cases.append((invalid_encoding, "invalid_encoding"))
            deep = root / "deep.json"
            deep.write_text("[" * 258 + "0" + "]" * 258, encoding="utf-8")
            cases.append((deep, "json_depth"))

            for path, expected_code in cases:
                with self.subTest(path=path.name):
                    result = fixture_input_integrity.subprocess.run(
                        [
                            fixture_input_integrity.sys.executable,
                            str(fixture_input_integrity.ROOT / "scripts/configure_gtm.py"),
                            "run",
                            "validate",
                            "--run",
                            str(path),
                        ],
                        cwd=fixture_input_integrity.ROOT,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(
                        fixture_input_integrity.json.loads(result.stdout)["error_code"],
                        expected_code,
                    )

    def test_strict_json_accepts_bom_and_rejects_ambiguous_or_non_finite_json(self) -> None:
        with fixture_input_integrity.tempfile.TemporaryDirectory() as temporary:
            path = fixture_input_integrity.Path(temporary) / "input.json"
            path.write_bytes(b'\xef\xbb\xbf{"event": "purchase"}')
            self.assertEqual(fixture_input_integrity.load_json(path), {"event": "purchase"})

        for raw, message in (
            ('{"event": "a", "event": "b"}', "duplicate JSON key"),
            ('{"value": NaN}', "non-finite JSON number"),
            ('{"value": Infinity}', "non-finite JSON number"),
        ):
            with (
                self.subTest(raw=raw),
                self.assertRaisesRegex(fixture_input_integrity.StrictJsonError, message),
            ):
                fixture_input_integrity.loads_strict(raw)

        deeply_nested = "[" * 258 + "0" + "]" * 258
        with self.assertRaisesRegex(fixture_input_integrity.StrictJsonError, "nesting") as raised:
            fixture_input_integrity.loads_strict(deeply_nested)
        self.assertEqual(raised.exception.error_code, "json_depth")
