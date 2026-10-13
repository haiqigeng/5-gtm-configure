"""Behavioral tests owned by privacy."""

from support import adapters as fixture_adapters
from support import authenticated_delivery as fixture_authenticated_delivery
from support import consent_and_fields as fixture_consent_and_fields
from support import durable_evidence as fixture_durable_evidence
from support import input_and_execution as fixture_input_and_execution
from support import mutation_recovery as fixture_mutation_recovery
from support import native_execution as fixture_native_execution
from support import phase_contracts as fixture_phase_contracts


class TestNativeExecutionNativeCorrections(fixture_native_execution.NativeCorrectionsTestsFixture):
    def test_code_permissions_info_arrays_and_bad_digest_never_gain_exemption(self):
        for changed in (
            fixture_native_execution.NATIVE.replace("x = 1", "x = 2"),
            fixture_native_execution.NATIVE.replace('"read"', '"write"'),
            fixture_native_execution.NATIVE.replace('"original"', '"different"'),
            fixture_native_execution.NATIVE + "___INFO___\n{}",
            fixture_native_execution.NATIVE.replace(
                '"id": "original"', '"id": "original", "id": "other"'
            ),
        ):
            with self.subTest(changed=changed):
                op = fixture_native_execution.operation()
                saved = fixture_native_execution.expected_graph(op)
                saved["objects"][0]["templateData"] = changed
                self.assertFalse(
                    fixture_native_execution.public_identifier_paths(saved, records=[op])
                )
                self.assertFalse(
                    fixture_native_execution.build_verification_comparison(op, saved)[0]["pass"]
                )
        op = fixture_native_execution.operation()
        op["public_identifiers"][0]["value_sha256"] = "0" * 64
        self.assertFalse(
            fixture_native_execution.public_identifier_paths(
                {"templateData": fixture_native_execution.NATIVE}, records=[op]
            )
        )
        self.assertNotEqual(
            fixture_native_execution.canonical_template_source(
                fixture_native_execution.NATIVE.replace(
                    '[ { "value": true, "key": "read" } ]', "[1,2]"
                )
            ),
            fixture_native_execution.canonical_template_source(
                fixture_native_execution.NATIVE.replace(
                    '[ { "value": true, "key": "read" } ]', "[2,1]"
                )
            ),
        )

    def test_omission_descriptor_prose_but_not_personal_or_unknown_values(self):
        descriptor = {
            "source": "user_data",
            "source_shape": "object:matching",
            "destination_shape": "object:matching",
            "provenance": {"grade": "approved-input", "locator": "inputs/TASK.md"},
            "missing_behavior": "Omit absent fields.",
        }
        self.assertFalse(fixture_native_execution.sensitive_findings({"user_data": descriptor}))
        for key, value in (
            ("missing_behavior", "Send to person@example.org"),
            ("unrecognized", "some value"),
            ("email", "person@example.org"),
        ):
            altered = {**descriptor, key: value}
            self.assertTrue(fixture_native_execution.sensitive_findings({"user_data": altered}))

    def test_reviewed_template_still_redacts_real_credential(self):
        op = fixture_native_execution.operation()
        source = fixture_native_execution.SOURCE.replace(
            "const x = 1;", "const headers = {Authorization: 'Bearer secret-token-value'};"
        )
        op["intended"]["templateData"] = source
        op["public_identifiers"][0]["value_sha256"] = fixture_native_execution.hashlib.sha256(
            source.encode()
        ).hexdigest()
        doc = fixture_native_execution.expected_graph(op)
        self.assertTrue(
            fixture_native_execution.contains_redacted(
                fixture_native_execution.redact_for_persistence(
                    doc,
                    public_identifier_paths=fixture_native_execution.public_identifier_paths(
                        doc, records=[op]
                    ),
                )
            )
        )


class TestAuthenticatedDelivery(fixture_authenticated_delivery.Audit102FollowupFixture):
    def test_public_loader_declarations_preserve_value_binding_and_secret_guards(self):
        safe = '<script src="https://maps.example.test/js?key=PUBLIC_IDENTIFIER"></script>'
        for literal, blocked in (
            (safe, False),
            (safe + '<script>var api_secret="private-value";</script>', True),
            (safe + " API key: https://example.test/private-value", True),
            (safe + '<script src="https://user:private@example.test/a"></script>', True),
            (safe + '<script src="https://hooks.slack.test/services/T/B/private"></script>', True),
            (safe + '<script>var email="person@example.test";</script>', True),
            (
                "https://example.test/?key="
                + fixture_authenticated_delivery.quote("sk_live_SYNTHETIC12345678", safe=""),
                True,
            ),
            ("https://example.test/?key=PUBLIC&email=person%40example.test", True),
            (
                "https://example.test/?key=PUBLIC&next="
                + fixture_authenticated_delivery.quote(
                    "https://user:private@example.test", safe=""
                ),
                True,
            ),
        ):
            with self.subTest(blocked=blocked, shape=len(literal)):
                contract = fixture_authenticated_delivery.public_contract()
                record = contract["implementation"]["objects"][-1]
                record["intended"]["parameter"][0]["value"] = literal
                record["public_identifiers"][0]["value_sha256"] = (
                    fixture_authenticated_delivery.hashlib.sha256(literal.encode()).hexdigest()
                )
                fixture_authenticated_delivery.validate_public_identifiers(contract)
                public = fixture_authenticated_delivery.public_identifier_paths(contract)
                self.assertEqual(
                    bool(
                        fixture_authenticated_delivery.sensitive_findings(
                            contract, public_identifier_paths=public
                        )
                    ),
                    blocked,
                )
                self.assertEqual(
                    fixture_authenticated_delivery.contains_redacted(
                        fixture_authenticated_delivery.redact_for_persistence(
                            contract, public_identifier_paths=public
                        )
                    ),
                    blocked,
                )
        self.assertTrue(fixture_authenticated_delivery.sensitive_findings({"html": safe}))


class TestInputAndExecution(fixture_input_and_execution.AuditRegressionsFixture):
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
                    value = fixture_input_and_execution.row(
                        name, name_key=name_key, value_key=value_key
                    )
                    self.assertTrue(fixture_input_and_execution.sensitive_paths(value))
                    self.assertNotIn(
                        fixture_input_and_execution.CANARY,
                        fixture_input_and_execution.json.dumps(
                            fixture_input_and_execution.redact_for_persistence(value)
                        ),
                    )
                    self.assertEqual(
                        fixture_input_and_execution.sensitive_paths(
                            fixture_input_and_execution.redact_for_persistence(value)
                        ),
                        [],
                    )
        for name in ("Authorization", "Proxy-Authorization", "X-Api-Key", "Cookie", "Set-Cookie"):
            self.assertNotIn(
                fixture_input_and_execution.CANARY,
                fixture_input_and_execution.json.dumps(
                    fixture_input_and_execution.redact_for_persistence(
                        fixture_input_and_execution.row(name, name_key="name", value_key="value")
                    )
                ),
            )
        for value in (
            fixture_input_and_execution.row("currency", "EUR"),
            fixture_input_and_execution.row("value", "0"),
            fixture_input_and_execution.row("token_secret", "{{Secret reference}}"),
        ):
            self.assertEqual(fixture_input_and_execution.redact_for_persistence(value), value)
            self.assertEqual(fixture_input_and_execution.sensitive_paths(value), [])

    def test_custom_code_and_error_redaction(self):
        from gtm_configure.core.privacy import scrub_sensitive_text

        for code in (
            f'var consumer_secret = "{fixture_input_and_execution.CANARY}";',
            f'const data = {{"access_token": "{fixture_input_and_execution.CANARY}"}}',
            f"var token_secret = '{fixture_input_and_execution.CANARY} with spaces';",
        ):
            self.assertTrue(
                fixture_input_and_execution.is_redacted(
                    fixture_input_and_execution.redact_for_persistence(code)
                )
            )
            self.assertNotIn(fixture_input_and_execution.CANARY, scrub_sensitive_text(code, set()))

    def test_transport_rejects_credential_writes_before_dispatch(self):
        output = fixture_input_and_execution.io.StringIO()
        transport = fixture_input_and_execution.StdioTransport(
            input_stream=fixture_input_and_execution.io.BytesIO(), output_stream=output
        )
        with self.assertRaisesRegex(Exception, "no write was dispatched"):
            transport(
                "mcp__gtm__gtm_tag",
                {
                    "action": "create",
                    "createOrUpdateConfig": {
                        "parameter": [fixture_input_and_execution.row("access_token")]
                    },
                },
            )
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(transport.writes_attempted, 0)

    def test_mcp_text_response_is_parsed_before_redaction(self):
        response = {
            "content": [
                {
                    "type": "text",
                    "text": fixture_input_and_execution.json.dumps(
                        {
                            "tag": [
                                {"parameter": [fixture_input_and_execution.row("consumer_secret")]}
                            ]
                        }
                    ),
                }
            ]
        }
        self.assertNotIn(
            fixture_input_and_execution.CANARY,
            fixture_input_and_execution.json.dumps(
                fixture_input_and_execution.redact_for_persistence(
                    fixture_input_and_execution.unwrap(response)
                )
            ),
        )


class TestAdapters(fixture_adapters.CurrentAdapterRuntimeTestFixture):
    def test_secret_is_resolved_only_for_mutation_and_never_persisted(self) -> None:
        contract = fixture_adapters.valid_server_contract()
        server_tag = contract["implementation"]["objects"][1]
        server_tag["intended"]["apiAccessToken"] = fixture_adapters.redacted_marker(
            reference="vault://meta/token"
        )
        adapter = fixture_adapters.FakeAdapter(existing={"GA4 Client - Web transport"})
        provider = fixture_adapters.StaticSecretProvider(
            {"vault://meta/token": "runtime-secret-token"}
        )
        run, _ = self._execute(
            contract,
            {
                "server-main": (
                    adapter,
                    fixture_adapters.capabilities("client", "tag", "trigger"),
                    provider,
                )
            },
        )
        self.assertEqual(run["object_changes"][1]["state"], "verified")
        self.assertEqual(adapter.received[-1]["intended"]["apiAccessToken"], "runtime-secret-token")
        self.assertNotIn("secret_fields", adapter.received[-1]["intended"])
        serialized = fixture_adapters.json.dumps(run)
        self.assertNotIn("runtime-secret-token", serialized)
        comparison = run["object_changes"][1]["comparison"]
        self.assertFalse(comparison["report"]["secret_comparison"]["value_equality_claimed"])

    def test_missing_secret_provider_blocks_only_the_affected_operation(self) -> None:
        contract = fixture_adapters.valid_server_contract()
        contract["implementation"]["objects"][1]["intended"]["access_token"] = (
            fixture_adapters.redacted_marker(reference="vault://meta/token")
        )
        adapter = fixture_adapters.FakeAdapter(existing={"GA4 Client - Web transport"})
        run, _ = self._execute(
            contract,
            {
                "server-main": (
                    adapter,
                    fixture_adapters.capabilities("client", "tag", "trigger"),
                    None,
                )
            },
        )
        states = {item["name"]: item["state"] for item in run["object_changes"]}
        self.assertEqual(states["GA4 Client - Web transport"], "verified")
        self.assertEqual(states["GA4 - page_view"], "failed")
        self.assertEqual(adapter.mutations, ["Event Data - page_view"])


class TestPhaseContracts(fixture_phase_contracts.CurrentContractAndRunTestFixture):
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
            "access_token": fixture_phase_contracts.redacted_marker(reference="vault://meta/token"),
        }
        safe = fixture_phase_contracts.redact_for_persistence(mapped)
        self.assertEqual(safe["email"], "{{DLV - user.email}}")
        self.assertEqual(safe["phone_number"], mapped["phone_number"])
        self.assertEqual(fixture_phase_contracts.sensitive_paths(safe), [])
        self.assertFalse(
            fixture_phase_contracts.safe_equal(
                fixture_phase_contracts.redacted_marker(), fixture_phase_contracts.redacted_marker()
            )
        )

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
        comparison, persisted = fixture_phase_contracts.build_verification_comparison(
            operation, saved
        )
        self.assertTrue(comparison["pass"])
        secret = comparison["report"]["secret_comparison"]
        self.assertEqual(secret["state"], fixture_phase_contracts.REDACTED_STATE)
        self.assertFalse(secret["value_equality_claimed"])
        self.assertNotIn(
            "ephemeral-token-value", fixture_phase_contracts.json.dumps([comparison, persisted])
        )


class TestDurableEvidence(fixture_durable_evidence.CurrentRegressionHardeningTestFixture):
    def test_prewrite_allows_adapter_metadata_but_never_claims_secret_equality(self) -> None:
        operation = {
            "operation_id": "OP-DELTA",
            "target_id": "server-main",
            "container_type": "server",
            "resource_family": "tag",
            "name": "Meta - Purchase",
            "object_key": "server-main::tag::Meta - Purchase",
            "action": "update",
            "pre_change": {
                "type": "meta-capi",
                "access_token": fixture_durable_evidence.redacted_marker(
                    reference="vault://meta/v1"
                ),
            },
        }
        comparison, persisted = fixture_durable_evidence.build_pre_write_comparison(
            operation,
            {
                "name": "Meta - Purchase",
                "type": "meta-capi",
                "access_token": "runtime-secret",
                "tagId": "2",
                "transformationId": "9",
                "tagManagerUrl": "server/accounts/1/tags/2",
            },
        )
        self.assertFalse(comparison["pass"])
        self.assertFalse(comparison["secret_comparison"]["reference_proved"])
        self.assertFalse(comparison["secret_comparison"]["value_equality_claimed"])
        self.assertNotIn("runtime-secret", str(persisted))
        proved, _ = fixture_durable_evidence.build_pre_write_comparison(
            operation,
            {
                "name": "Meta - Purchase",
                "type": "meta-capi",
                "access_token": fixture_durable_evidence.redacted_marker(
                    reference="vault://meta/v1"
                ),
            },
        )
        self.assertTrue(proved["pass"])
        renamed, _ = fixture_durable_evidence.build_pre_write_comparison(
            operation,
            {
                "name": "Meta - Renamed elsewhere",
                "type": "meta-capi",
                "access_token": "runtime-secret",
            },
        )
        self.assertFalse(renamed["pass"])
        self.assertIn("$.name: value differs", renamed["differences"])

    def test_verification_canonicalizes_secret_bearing_keyed_rows(self) -> None:
        operation = {
            "operation_id": "OP-SECRET-ROWS",
            "target_id": "server-main",
            "container_type": "server",
            "resource_family": "tag",
            "name": "Vendor - Purchase",
            "object_key": "server-main::tag::Vendor - Purchase",
            "action": "create",
            "intended": {
                "type": "vendor-api",
                "parameter": [
                    {
                        "type": "template",
                        "key": "apiSecret",
                        "value": fixture_durable_evidence.redacted_marker(
                            reference="vault://vendor/api-secret"
                        ),
                    },
                    {"type": "template", "key": "eventName", "value": "purchase"},
                ],
            },
        }
        saved = fixture_durable_evidence.expected_graph(operation)
        saved["objects"][0]["parameter"].reverse()
        saved["objects"][0]["parameter"][1]["value"] = "runtime-secret"

        comparison, persisted = fixture_durable_evidence.build_verification_comparison(
            operation, saved
        )

        self.assertTrue(comparison["pass"])
        self.assertTrue(comparison["report"]["secret_comparison"]["presence_paths_match"])
        self.assertFalse(comparison["report"]["secret_comparison"]["value_equality_claimed"])
        self.assertNotIn("runtime-secret", str(persisted))

    def test_redaction_handles_template_rows_and_compact_phone(self) -> None:
        source = {
            "parameter": [{"key": "apiSecret", "value": "sk_live_example"}],
            "mobile": "0101010101",
            "governance_note": "approved mutation",
        }
        persisted = fixture_durable_evidence.redact_for_persistence(source)
        self.assertNotEqual(persisted["parameter"][0]["value"], "sk_live_example")
        self.assertNotEqual(persisted["mobile"], "0101010101")
        self.assertEqual(persisted["governance_note"], "approved mutation")
        self.assertEqual(fixture_durable_evidence.sensitive_paths(persisted), [])

    def test_redaction_covers_real_authorization_header_shapes(self) -> None:
        source = {
            "authorization": "Bearer sk_live_direct_123456",
            "headers": [
                {"key": "name", "value": "Authorization"},
                {"key": "value", "value": "Bearer sk_live_flattened_123456"},
            ],
            "rows": [
                {"name": "Authorization", "value": "Basic YWJjZGVmZ2hpamts"},
            ],
            "governance_note": "approved mutation",
        }
        persisted = fixture_durable_evidence.redact_for_persistence(source)
        serialized = str(persisted)
        self.assertNotIn("sk_live_direct", serialized)
        self.assertNotIn("sk_live_flattened", serialized)
        self.assertNotIn("YWJjZGVm", serialized)
        self.assertEqual(persisted["governance_note"], "approved mutation")
        self.assertEqual(fixture_durable_evidence.sensitive_paths(persisted), [])


class TestNativeExecutionNativeBinding(fixture_native_execution.NativeBindingTestsFixture):
    def test_native_identity_is_verified_once_and_public_binding_is_immutable(self):
        req = fixture_native_execution.request()
        backend = fixture_native_execution.FakeGtm(req)
        target, profile = (
            fixture_native_execution.deepcopy(req["targets"][0]),
            fixture_native_execution.deepcopy(fixture_native_execution.PROFILE),
        )
        adapter = fixture_native_execution.McpTargetAdapter(target, profile, backend.call)
        expected = adapter.identity()
        target["workspace_id"] = "wrong"
        profile["tool_prefix"] = "wrong__"
        adapter.target["workspace_id"] = "wrong"
        adapter.profile["families"].clear()
        for name, replacement in (
            ("target", target),
            ("profile", profile),
            ("call", lambda *a: None),
        ):
            with self.assertRaises(AttributeError):
                setattr(adapter, name, replacement)
        for _ in range(124):
            self.assertEqual(adapter.identity(), expected)
        self.assertEqual(len(backend.calls), 2)
        adapter.list_resource_page("tag", None)
        self.assertEqual(backend.calls[-1][1]["workspaceId"], expected["workspace_id"])
        self.assertEqual(backend.calls[-1][0], "synthetic__gtm_tag")
        new_adapter = fixture_native_execution.McpTargetAdapter(
            req["targets"][0], fixture_native_execution.PROFILE, backend.call
        )
        new_adapter.identity()
        self.assertEqual(sum(a["action"] == "get" for _, a in backend.calls), 4)
        with self.assertRaises(fixture_native_execution.AdapterExecutionError):
            adapter._call("gtm_tag", "get", workspaceId="wrong")


class TestMutationRecovery(fixture_mutation_recovery.NativeAndRecoveryTestsFixture):
    def test_exact_source_template_test_examples_preserve_bytes_and_reject_runtime_secrets(self):
        source = "___SANDBOXED_JS_FOR_WEB_TEMPLATE___\ndata.gtmOnSuccess();\n___TESTS___\nconst email = 'fixture@example.test';\n___WEB_PERMISSIONS___\n[]"
        record = {
            "resource_family": "template",
            "target_id": "w",
            "name": "Template",
            "action": "create",
            "intended": {"templateData": source},
            "public_identifiers": [
                {
                    "path": ["templateData"],
                    "classification": "inspected-template-source",
                    "value_sha256": fixture_mutation_recovery.hashlib.sha256(
                        source.encode()
                    ).hexdigest(),
                    "source_url": "https://example.test/source",
                    "reason": "Inspected test-only sample; unchanged code and permissions",
                }
            ],
        }
        document = {
            "objects": [record],
            "official_sources": [{"url": "https://example.test/source"}],
        }
        fixture_mutation_recovery.validate_public_identifiers(document)
        raw = {"name": "Template", "templateData": source}
        paths = fixture_mutation_recovery.public_identifier_paths(raw, records=[record])
        self.assertFalse(
            fixture_mutation_recovery.sensitive_paths(raw, public_identifier_paths=paths)
        )
        self.assertEqual(
            fixture_mutation_recovery.redact_for_persistence(raw, public_identifier_paths=paths),
            raw,
        )
        for changed in (
            source.replace("data.gtmOnSuccess();", "const email = 'fixture@example.test';"),
            source.replace("const email", "const access_token"),
        ):
            raw["templateData"] = changed
            self.assertTrue(
                fixture_mutation_recovery.sensitive_paths(
                    raw,
                    public_identifier_paths=fixture_mutation_recovery.public_identifier_paths(
                        raw, records=[record]
                    ),
                )
            )
        for changed in (
            source + "\n___TESTS___\nfixture@example.test",
            source.replace(
                "const email = 'fixture@example.test';", "const access_token = 'opaque-secret';"
            ),
        ):
            # Even newly inspected exact source never exempts duplicated sections or credentials.
            record["intended"]["templateData"] = changed
            record["public_identifiers"][0]["value_sha256"] = (
                fixture_mutation_recovery.hashlib.sha256(changed.encode()).hexdigest()
            )
            raw["templateData"] = changed
            self.assertTrue(
                fixture_mutation_recovery.sensitive_paths(
                    raw,
                    public_identifier_paths=fixture_mutation_recovery.public_identifier_paths(
                        raw, records=[record]
                    ),
                )
            )
        bad = fixture_mutation_recovery.deepcopy(document)
        bad["objects"][0]["public_identifiers"][0]["path"] = ["notes"]
        with self.assertRaises(ValueError):
            fixture_mutation_recovery.validate_public_identifiers(bad)
        bad = fixture_mutation_recovery.deepcopy(document)
        bad["objects"][0]["public_identifiers"][0]["source_url"] = "https://unknown.test/source"
        with self.assertRaises(ValueError):
            fixture_mutation_recovery.validate_public_identifiers(bad)


class TestConsentAndFields(fixture_consent_and_fields.UtilityCorrectionsFixture):
    def test_scan_cache_preserves_context_changes_and_return_isolation(self):
        value = {"value": "ordinary"}
        self.assertEqual(fixture_consent_and_fields.sensitive_findings(value), [])
        self.assertTrue(
            fixture_consent_and_fields.sensitive_findings(value, exact_secret_paths={"$.value"})
        )
        value["api_secret"] = "not-public"
        findings = fixture_consent_and_fields.sensitive_findings(value)
        self.assertTrue(findings)
        findings.clear()
        self.assertTrue(fixture_consent_and_fields.sensitive_findings(value))
        graph = [
            {
                "name": "Delivery",
                "type": "c",
                "parameter": [fixture_consent_and_fields.param("value", "opaque-literal")],
            }
        ]
        self.assertEqual(fixture_consent_and_fields.sensitive_findings(graph), [])
        graph.append({"api_secret": "{{Delivery}}"})
        self.assertTrue(
            any(
                "value" in row["path"]
                for row in fixture_consent_and_fields.sensitive_findings(graph)
            )
        )
