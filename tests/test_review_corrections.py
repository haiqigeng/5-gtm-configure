"""Reproduced native/recovery boundaries; all remote services here are offline doubles."""

import hashlib
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]

from action_contract import validate_native_authoring  # noqa: E402
from adapter_runtime import TargetAdapterRegistry, execute_ready_operations  # noqa: E402
from adapter_support import (  # noqa: E402
    AdapterExecutionError,
    AmbiguousWriteError,
    AuthenticationError,
    RateLimitError,
)
from configuration_run import atomic_write, create_from_contract, load_document  # noqa: E402
from current_support import approve_mutations, valid_web_contract  # noqa: E402
from mcp_adapter import McpTargetAdapter, unwrap  # noqa: E402
from public_identifiers import public_identifier_paths, validate_public_identifiers  # noqa: E402
from redaction import redact_for_persistence, sensitive_paths  # noqa: E402
from resource_registry import requires_variable_consumer_check  # noqa: E402
from run_state import reopen_failed_operation  # noqa: E402
from run_validation_web import RunValidationError, _first_party_binding_value  # noqa: E402
from test_current_adapter_runtime import FakeAdapter, capabilities  # noqa: E402
from test_google_ads_enhanced_conversions import event_override_contract  # noqa: E402
from test_shared_event_id import generated_contract  # noqa: E402
from validate_configuration_contract import ContractValidationError, validate_document  # noqa: E402
from verification import build_verification_comparison, expected_graph  # noqa: E402


def sender_generated_contract():
    contract = generated_contract()
    contract["mode"] = "web"
    contract["targets"] = [t for t in contract["targets"] if t["container_type"] == "web"]
    contract["pipelines"] = []
    objects = contract["implementation"]["objects"]
    objects[:] = [o for o in objects if o["target_id"] == "web-main"]
    for obj in objects:
        obj["depends_on"] = [k for k in obj["depends_on"] if k.startswith("web-main::")]
    for topology in contract["consent_topologies"]:
        topology["server_tag_keys"] = []
        topology["server_enforcement"] = {"mechanism": "none"}
    contract["external_dependencies"].append(
        {
            "id": "receiver",
            "requirement_ids": ["REQ-ATC"],
            "owner": "External server owner",
            "action": "Verify receipt and reuse of event_id; sender save does not certify receiver",
            "status": "accepted",
        }
    )
    contract["dedup_contracts"][0]["external_receiver_dependency_id"] = "receiver"
    return approve_mutations(contract)


def sender_user_data_contract():
    contract = event_override_contract()
    tag = contract["implementation"]["objects"][0]
    tag["intended"]["type"] = "gaawe"
    tag["intended"]["parameter"] = [
        {"key": "measurementIdOverride", "type": "template", "value": "G-TEST123"},
        {"key": "eventName", "type": "template", "value": "purchase"},
        {
            "key": "eventSettingsTable",
            "type": "list",
            "list": [
                {
                    "type": "map",
                    "map": [
                        {"key": "parameter", "type": "template", "value": "user_data"},
                        {
                            "key": "parameterValue",
                            "type": "template",
                            "value": "{{UPD - Approved conversion}}",
                        },
                    ],
                }
            ],
        },
    ]
    route = contract["first_party_data_routes"][0]
    route.update(
        feature="google-ads-server-user-data-transport",
        server_consumer_object_keys=[],
        external_receiver_dependency_id="EXT-ADS",
    )
    binding = route["consumer_bindings"][0]
    binding.update(product="google-ads-transport", tag_type="gaawe")
    for key in ("user_data_path", "activation_paths", "field_review"):
        binding.pop(key)
    contract["implementation"]["field_bindings"][0]["template_field"] = "user_data"
    return approve_mutations(contract)


class NativeAndRecoveryTests(unittest.TestCase):
    def test_consent_default_equivalence_is_exact_and_evidence_is_retained(self):
        operation = {
            "operation_id": "o",
            "target_id": "web",
            "resource_family": "tag",
            "container_type": "web",
            "name": "tag",
            "action": "create",
            "intended": {"type": "gaawe"},
        }
        saved = expected_graph(operation)
        saved["objects"][0]["consentSettings"] = {"consentStatus": "notSet"}
        comparison, evidence = build_verification_comparison(operation, saved)
        self.assertTrue(comparison["pass"])
        self.assertIn("consentSettings", evidence["objects"][0])
        for consent in (
            {"consentStatus": "needed"},
            {"consentStatus": "notSet", "extra": True},
            {},
        ):
            saved["objects"][0]["consentSettings"] = consent
            self.assertFalse(build_verification_comparison(operation, saved)[0]["pass"])

    def test_native_authoring_rejects_known_bad_shapes(self):
        def reject(message):
            raise ValueError(message)

        bad = [
            ("trigger", {"type": "customEvent", "customEventFilter": "purchase"}),
            ("tag", {"type": "gaawe", "parameter": [{"key": "sendEcommerce", "value": "true"}]}),
            (
                "tag",
                {
                    "type": "gaawe",
                    "parameter": [
                        {
                            "key": "eventSettingsTable",
                            "type": "list",
                            "list": [
                                {
                                    "type": "map",
                                    "map": [
                                        {"key": "name", "value": "currency"},
                                        {"key": "value", "value": "EUR"},
                                    ],
                                }
                            ],
                        }
                    ],
                },
            ),
        ]
        for family, native in bad:
            with self.subTest(native=native), self.assertRaises(ValueError):
                validate_native_authoring(family, native, path="test", fail=reject)
        validate_native_authoring(
            "tag",
            {
                "type": "gaawe",
                "parameter": [
                    {"key": "sendEcommerceData", "type": "boolean", "value": "true"},
                    {"key": "getEcommerceDataFrom", "type": "template", "value": "dataLayer"},
                ],
            },
            path="test",
            fail=reject,
        )

    def test_structured_mcp_rejections_and_unknown_outcomes(self):
        for mutation in (False, True):
            for code, cls in (
                (401, AuthenticationError),
                (429, RateLimitError),
                (400, AdapterExecutionError),
                (403, AdapterExecutionError),
            ):
                response = {
                    "isError": True,
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {"error": {"code": code, "message": "must not persist raw detail"}}
                            ),
                        }
                    ],
                }
                with self.subTest(code=code, mutation=mutation), self.assertRaises(cls) as caught:
                    unwrap(response, mutation=mutation)
                self.assertNotIn("raw detail", str(caught.exception))
                self.assertNotIsInstance(caught.exception, AmbiguousWriteError)
            with self.assertRaises(
                AmbiguousWriteError if mutation else AdapterExecutionError
            ) as caught:
                unwrap(
                    {
                        "isError": True,
                        "content": [{"type": "text", "text": "HTTP 401, safe to retry"}],
                    },
                    mutation=mutation,
                )
            if not mutation:
                self.assertNotIsInstance(caught.exception, AmbiguousWriteError)

    def test_cold_reference_loads_missing_family_and_retains_complete_cache(self):
        calls = []
        target = {"target_id": "w", "account_id": "1", "container_id": "2", "workspace_id": "3"}
        profile = {
            "tool_prefix": "",
            "workspace_path": [],
            "container_path": [],
            "status_path": [],
            "families": {
                "folder": {
                    "actions": ["list"],
                    "page_size": 10,
                    "first_page": 1,
                    "list_path": [],
                    "object_path": [],
                }
            },
        }

        def call(tool, arguments):
            calls.append((tool, arguments["action"]))
            return [
                {
                    "folderId": "4",
                    "name": "Folder",
                    "accountId": "1",
                    "containerId": "2",
                    "workspaceId": "3",
                }
            ]

        # MCP returns a structured list inside a response object.
        adapter = McpTargetAdapter(target, profile, lambda t, a: {"structuredContent": call(t, a)})
        adapter.cache["folder"] = []  # incomplete cache must never imply absence
        self.assertEqual(adapter._resolve_reference("w::folder::Folder", "folderId"), "4")
        self.assertEqual(adapter._resolve_reference("w::folder::Folder", "folderId"), "4")
        self.assertEqual(calls, [("gtm_folder", "list")])
        adapter.cache["folder"] = []
        adapter.known_ids["w::folder::Folder"] = "stale"
        with self.assertRaises(AdapterExecutionError):
            adapter._resolve_reference("w::folder::Folder", "folderId")

    def test_read_only_baseline_failure_can_resume_normally(self):
        class Once(FakeAdapter):
            failed = False

            def list_resource_page(self, family, cursor):
                if not self.failed:
                    self.failed = True
                    raise AdapterExecutionError("read-only failure")
                return {"items": [], "next_cursor": None}

        run = create_from_contract(valid_web_contract(), run_id="recovery", source_locator="test")
        adapter = Once()
        adapter.bind_target(run["run"]["targets"][0])
        registry = TargetAdapterRegistry()
        registry.register(run["run"]["targets"][0], adapter, capabilities("tag", "trigger"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry)
            self.assertFalse(adapter.mutations)
            failed = load_document(path)
            for operation in list(failed["object_changes"]):
                failed = reopen_failed_operation(
                    failed, operation_id=operation["operation_id"], note="Read-only outage resolved"
                )
            atomic_write(path, failed)
            execute_ready_operations(path, registry)
            result = load_document(path)
            self.assertTrue(all(o["state"] == "verified" for o in result["object_changes"]))
            self.assertTrue(
                any(
                    "read-only failure" in (e.get("error") or "")
                    for o in result["object_changes"]
                    for e in o["journal"]
                )
            )

    def test_only_complete_notes_delta_skips_consumer_scan(self):
        before = {"type": "c", "parameter": [{"key": "value", "type": "template", "value": "a"}]}
        operation = {
            "resource_family": "variable",
            "action": "update",
            "pre_change": before,
            "intended": {**deepcopy(before), "notes": "reviewed"},
        }
        self.assertFalse(requires_variable_consumer_check(operation))
        operation["intended"]["parameter"][0]["value"] = "b"
        self.assertTrue(requires_variable_consumer_check(operation))
        operation["intended"] = {"notes": "partial snapshot"}
        self.assertTrue(requires_variable_consumer_check(operation))

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
                    "value_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "source_url": "https://example.test/source",
                    "reason": "Inspected test-only sample; unchanged code and permissions",
                }
            ],
        }
        document = {
            "objects": [record],
            "official_sources": [{"url": "https://example.test/source"}],
        }
        validate_public_identifiers(document)
        raw = {"name": "Template", "templateData": source}
        paths = public_identifier_paths(raw, records=[record])
        self.assertFalse(sensitive_paths(raw, public_identifier_paths=paths))
        self.assertEqual(redact_for_persistence(raw, public_identifier_paths=paths), raw)
        for changed in (
            source.replace("data.gtmOnSuccess();", "const email = 'fixture@example.test';"),
            source.replace("const email", "const access_token"),
        ):
            raw["templateData"] = changed
            self.assertTrue(
                sensitive_paths(
                    raw, public_identifier_paths=public_identifier_paths(raw, records=[record])
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
            record["public_identifiers"][0]["value_sha256"] = hashlib.sha256(
                changed.encode()
            ).hexdigest()
            raw["templateData"] = changed
            self.assertTrue(
                sensitive_paths(
                    raw, public_identifier_paths=public_identifier_paths(raw, records=[record])
                )
            )
        bad = deepcopy(document)
        bad["objects"][0]["public_identifiers"][0]["path"] = ["notes"]
        with self.assertRaises(ValueError):
            validate_public_identifiers(bad)
        bad = deepcopy(document)
        bad["objects"][0]["public_identifiers"][0]["source_url"] = "https://unknown.test/source"
        with self.assertRaises(ValueError):
            validate_public_identifiers(bad)

    def test_sender_generated_contract_materializes_without_server(self):
        contract = sender_generated_contract()
        validate_document(contract)
        run = create_from_contract(contract, run_id="sender", source_locator="test")
        self.assertEqual({t["container_type"] for t in run["run"]["targets"]}, {"web"})
        self.assertFalse(run["pipelines"])
        for mutate in (
            lambda c: c["dedup_contracts"][0].pop("external_receiver_dependency_id"),
            lambda c: c["dedup_contracts"][0].update(event_name="purchase"),
            lambda c: c["dedup_contracts"][0].update(server_generates_id=True),
        ):
            broken = deepcopy(contract)
            mutate(broken)
            with self.assertRaises(ContractValidationError):
                validate_document(approve_mutations(broken))

    def test_sender_user_data_requires_explicit_external_receiver(self):
        contract = sender_user_data_contract()
        validate_document(contract)
        run = create_from_contract(contract, run_id="sender-data", source_locator="test")
        self.assertFalse(run["pipelines"])
        for mutation in (
            lambda r: r.pop("external_receiver_dependency_id"),
            lambda r: r.update(timing="tag-wide"),
            lambda r: r.update(server_consumer_object_keys=["server::tag::invented"]),
        ):
            broken = deepcopy(contract)
            mutation(broken["first_party_data_routes"][0])
            with self.assertRaises(ContractValidationError):
                validate_document(approve_mutations(broken))

    def test_supplied_sender_identity_must_bind_actual_fields_not_notes(self):
        contract = sender_generated_contract()
        dedup = contract["dedup_contracts"][0]
        dedup["source_type"] = "approved-event-id"
        dedup["consumer_bindings"] = dedup.pop("generation")["consumer_bindings"]
        variable = next(
            o
            for o in contract["implementation"]["objects"]
            if o["object_key"] == dedup["source_variable_key"]
        )
        variable["intended"] = {
            "type": "v",
            "parameter": [{"key": "name", "type": "template", "value": "occurrence_id"}],
        }
        validate_document(approve_mutations(contract))
        tag = next(
            o
            for o in contract["implementation"]["objects"]
            if o["object_key"] == dedup["browser_consumer_keys"][0]
        )
        tag["intended"]["notes"] = tag["intended"].pop("event_id")
        dedup["consumer_bindings"][0]["field_path"] = ["notes"]
        with self.assertRaisesRegex(ContractValidationError, "identity binding"):
            validate_document(approve_mutations(contract))

    def test_meta_native_matching_cell_and_activation_are_bound(self):
        tag = {
            "type": "cvt_meta",
            "parameter": [
                {"key": "advancedMatching", "type": "boolean", "value": "true"},
                {
                    "key": "advancedMatchingList",
                    "type": "list",
                    "list": [
                        {
                            "type": "map",
                            "map": [
                                {"key": "name", "type": "template", "value": "em"},
                                {"key": "value", "type": "template", "value": "{{Email}}"},
                            ],
                        }
                    ],
                },
            ],
        }
        route = {
            "feature": "vendor-advanced-matching",
            "destination_field": "em",
            "fields": [{"name": "em"}],
            "consumer_bindings": [
                {
                    "object_key": "tag",
                    "field_review": "Inspected Meta matching email cell",
                    "user_data_path": [
                        "parameter",
                        "advancedMatchingList",
                        "list",
                        0,
                        "map",
                        "value",
                        "value",
                    ],
                    "activation_paths": [["parameter", "advancedMatching", "value"]],
                }
            ],
        }
        self.assertEqual(_first_party_binding_value(route, tag, "tag", "test"), (True, "{{Email}}"))
        for altered in ("false", "{{Unknown}}"):
            tag["parameter"][0]["value"] = altered
            with self.assertRaises(RunValidationError):
                _first_party_binding_value(route, tag, "tag", "test")
        tag["parameter"][0]["value"] = "true"
        route["fields"].append({"name": "ph"})
        with self.assertRaisesRegex(RunValidationError, "exactly its one"):
            _first_party_binding_value(route, tag, "tag", "test")
        route["fields"].pop()
        tag["parameter"][1]["list"][0]["map"][0]["value"] = "ph"
        with self.assertRaises(RunValidationError):
            _first_party_binding_value(route, tag, "tag", "test")


if __name__ == "__main__":
    unittest.main()
