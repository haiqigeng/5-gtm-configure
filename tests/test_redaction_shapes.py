# ruff: noqa: E402
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]
from adapter_runtime import TargetAdapterRegistry, execute_ready_operations, verify_idempotent_rerun
from configuration_run import atomic_write, create_from_contract, load_document
from current_support import approve_mutations, complete_capture_evidence, valid_web_contract
from mcp_adapter import McpTargetAdapter
from public_identifiers import public_identifier_paths, validate_public_identifiers
from redaction import exposure_findings, is_redacted, redact_for_persistence, sensitive_paths
from run_render import render_markdown, semantic_field_changes
from run_state import _build_target_baseline
from test_current_adapter_runtime import FakeAdapter, capabilities
from test_mcp_transport import profile
from validate_configuration_contract import validate_document

PUBLIC = "synthetic-public-browser-project"
SOURCE = "https://amplitude.com/docs/apis/keys-and-tokens"


def public_contract():
    contract = valid_web_contract()
    contract["evidence"].append(
        {
            "grade": "official-current",
            "locator": SOURCE,
            "title": "Synthetic evidence fixture",
            "decision": "Fixture represents inspected public browser key semantics, not a live vendor check",
            "accessed_on": "2026-09-28",
            "supports": ["REQ-PAGE"],
        }
    )
    contract["implementation"]["objects"].append(
        {
            "object_key": "web-main::variable::Amplitude API Key",
            "target_id": "web-main",
            "resource_family": "variable",
            "name": "Amplitude API Key",
            "action": "create",
            "requirement_ids": ["REQ-PAGE"],
            "depends_on": [],
            "justification": "Synthetic approved public key fixture",
            "evidence": ["approved-input", "official-current"],
            "risk": "routine",
            "intended": {
                "type": "c",
                "parameter": [{"key": "value", "type": "template", "value": PUBLIC}],
            },
            "public_identifiers": [
                {
                    "path": ["parameter", "value", "value"],
                    "value_sha256": hashlib.sha256(PUBLIC.encode()).hexdigest(),
                    "source_url": SOURCE,
                    "reason": "Inspected browser collection identifier, not an authentication secret",
                }
            ],
        }
    )
    return approve_mutations(contract)


class RedactionShapeTests(unittest.TestCase):
    def test_source_authority_descriptor_metadata_is_scanned_without_false_positive(self):
        from copy import deepcopy

        from requirement_validation import validate_requirement

        descriptor = {
            "source": "user_data.email",
            "source_shape": "string",
            "destination_shape": "string",
            "provenance": {
                "grade": "official-current",
                "locator": "https://support.google.com/google-ads/answer/13262500",
            },
            "source_authority": {
                "grade": "approved-input",
                "locator": "synthetic-fixtures.json#user_data.email",
            },
        }
        requirement = {
            "id": "REQ-EMAIL",
            "authority": {"grade": "approved-input", "locator": "approved source"},
            "parameters": {"email": descriptor},
        }
        self.assertEqual(validate_requirement(requirement, index=0, route="media"), "REQ-EMAIL")
        self.assertEqual(sensitive_paths(requirement), [])
        for key, value in (("locator", "person@example.test"), ("access_token", "private-value")):
            changed = deepcopy(requirement)
            changed["parameters"]["email"]["source_authority"][key] = value
            self.assertIn(f"$.parameters.email.source_authority.{key}", sensitive_paths(changed))
        for key in ("literal", "value", "type"):
            changed = deepcopy(requirement)
            changed["parameters"]["email"][key] = "person@example.test"
            self.assertIn(f"$.parameters.email.{key}", sensitive_paths(changed))
        changed = deepcopy(requirement)
        changed["parameters"]["email"]["type"] = "string"
        self.assertIn("$.parameters.email.type", sensitive_paths(changed))

    def test_reported_native_shapes_and_control_families(self):
        fixture = json.loads(
            (ROOT / "tests/fixtures/redaction-shapes.json").read_text(encoding="utf-8")
        )
        for group in ("leaks", "controls"):
            for name, item in fixture[group].items():
                with self.subTest(group=group, name=name):
                    result = redact_for_persistence(item)
                    if group == "leaks":
                        self.assertTrue(sensitive_paths(item))
                        self.assertNotIn(fixture["canary"], json.dumps(result))
                    else:
                        self.assertEqual(sensitive_paths(item), [])
                        self.assertEqual(result, item)

    def test_cross_family_reference_closure_precedes_baseline_persistence(self):
        target = valid_web_contract()["targets"][0]
        resources = {
            "tag": [
                {
                    "name": "Server consumer",
                    "type": "cvt_test",
                    "parameter": [{"key": "accessToken", "value": "{{Routing value}}"}],
                }
            ],
            "variable": [
                {
                    "name": "Routing value",
                    "type": "c",
                    "parameter": [{"key": "value", "value": "{{Opaque output}}"}],
                },
                {
                    "name": "Opaque output",
                    "type": "c",
                    "parameter": [{"key": "value", "value": "SYNTHETIC-OPAQUE-SECRET"}],
                },
            ],
        }
        baseline = _build_target_baseline(
            target,
            resources,
            captured_at="2026-09-28T00:00:00Z",
            preexisting_workspace_changes=[],
            capture_evidence=complete_capture_evidence(resources, target),
        )
        self.assertNotIn("SYNTHETIC-OPAQUE-SECRET", json.dumps(baseline))
        findings = exposure_findings(baseline["resources"])
        self.assertEqual(findings[0]["category"], "credential")
        self.assertIn("variable[1]", findings[0]["path"])

    def test_public_identifier_contract_runtime_readback_and_transport(self):
        contract = public_contract()
        validate_document(contract)
        run = create_from_contract(
            contract, run_id="public", source_locator="Synthetic scoped request"
        )
        target = run["run"]["targets"][0]
        adapter = FakeAdapter()
        adapter.bind_target(target)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, capabilities("tag", "trigger", "variable"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry)
            verify_idempotent_rerun(path, registry)
            current = load_document(path)
            self.assertEqual(current["run"]["status"], "Configured")
            self.assertIn(PUBLIC, path.read_text(encoding="utf-8"))
            self.assertNotIn("Credential-like literal", render_markdown(current))
        operation = next(
            item for item in run["object_changes"] if item["resource_family"] == "variable"
        )
        observed = []

        def call(tool, arguments, **kwargs):
            observed.append((arguments, kwargs))
            self.assertEqual(sensitive_paths(arguments, **kwargs), [])
            return {
                **arguments["createOrUpdateConfig"],
                "variableId": "42",
                "accountId": target["account_id"],
                "containerId": target["container_id"],
                "workspaceId": target["workspace_id"],
            }

        native = McpTargetAdapter(target, profile("variable"), call)
        native.mutate(operation)
        self.assertEqual(observed[0][0]["createOrUpdateConfig"]["parameter"][0]["value"], PUBLIC)

    def test_public_declarations_cannot_suppress_strong_credentials_or_unrelated_fields(self):
        contract = public_contract()
        obj = contract["implementation"]["objects"][-1]
        for value in (
            "Bearer SYNTHETIC-SECRET-VALUE",
            "sk_live_SYNTHETICONLY123456",
            "person@example.test",
            "https://user:private@example.test/?key=SYNTHETICVALUE",
        ):
            with self.subTest(value_type=value.split("_")[0]):
                obj["intended"]["parameter"][0]["value"] = value
                obj["public_identifiers"][0]["value_sha256"] = hashlib.sha256(
                    value.encode()
                ).hexdigest()
                with self.assertRaisesRegex(ValueError, "literal secret"):
                    validate_document(approve_mutations(contract))
        obj["public_identifiers"][0]["source_url"] = "https://unrecorded.example.test"
        with self.assertRaisesRegex(ValueError, "official-current"):
            validate_public_identifiers(contract)

    def test_public_identifier_binding_survives_parameter_order_and_detects_value_drift(self):
        contract = public_contract()
        operation = contract["implementation"]["objects"][-1]
        native = {"name": operation["name"], **deepcopy(operation["intended"])}
        native["parameter"].insert(0, {"key": "format", "value": "string"})
        paths = public_identifier_paths(native, records=[operation])
        self.assertEqual(paths, {"$.parameter[1].value"})
        self.assertEqual(sensitive_paths(native, public_identifier_paths=paths), [])
        native["parameter"][1]["value"] = "unexpected-value"
        self.assertEqual(public_identifier_paths(native, records=[operation]), set())
        self.assertTrue(sensitive_paths(native))

    def test_public_classification_cannot_override_private_fields_or_their_references(self):
        for field in (
            "Authorization",
            "Proxy-Authorization",
            "Cookie",
            "Set-Cookie",
            "accessToken",
            "refresh_token",
            "clientSecret",
            "password",
            "privateKey",
            "X-API-Secret",
        ):
            with self.subTest(field=field):
                native = {"parameter": [{"key": field, "value": "opaque-synthetic-value"}]}
                paths = {"$.parameter[0].value"}
                self.assertEqual(
                    sensitive_paths(native, public_identifier_paths=paths), list(paths)
                )
                self.assertNotIn(
                    "opaque-synthetic-value",
                    json.dumps(redact_for_persistence(native, public_identifier_paths=paths)),
                )
        graph = {
            "tag": [{"name": "Consumer", "type": "cvt_test", "Authorization": "{{Route}}"}],
            "variable": [
                {
                    "name": "Route",
                    "type": "c",
                    "parameter": [{"key": "value", "value": "{{Project API Key}}"}],
                },
                {
                    "name": "Project API Key",
                    "type": "c",
                    "parameter": [{"key": "value", "value": PUBLIC}],
                },
            ],
        }
        paths = {"$.variable[1].parameter[0].value"}
        self.assertEqual(sensitive_paths(graph, public_identifier_paths=paths), list(paths))
        contract = public_contract()
        contract["implementation"]["objects"][-1]["name"] = "Private API Secret"
        contract["implementation"]["objects"][-1]["object_key"] = (
            "web-main::variable::Private API Secret"
        )
        with self.assertRaisesRegex(ValueError, "literal secret"):
            validate_document(approve_mutations(contract))

    def test_inspected_native_browser_keys_and_previous_public_value(self):
        for field in ("apiKey", "token"):
            with self.subTest(field=field):
                contract = public_contract()
                operation = contract["implementation"]["objects"][-1]
                operation["intended"] = {
                    "type": "cvt_public_collection_fixture",
                    "parameter": [{"key": field, "value": PUBLIC}],
                }
                declaration = operation["public_identifiers"][0]
                declaration["path"] = ["parameter", field, "value"]
                validate_public_identifiers(contract)
                native = {"name": operation["name"], **deepcopy(operation["intended"])}
                self.assertTrue(sensitive_paths(native))
                paths = public_identifier_paths(native, records=[operation])
                self.assertEqual(sensitive_paths(native, public_identifier_paths=paths), [])
                previous = "synthetic-previous-public-project"
                operation["action"] = "update"
                operation["pre_change"] = deepcopy(native)
                operation["pre_change"]["parameter"][0]["value"] = previous
                declaration["previous_value_sha256"] = hashlib.sha256(previous.encode()).hexdigest()
                validate_public_identifiers(contract)
                paths = public_identifier_paths(operation["pre_change"], records=[operation])
                self.assertEqual(
                    sensitive_paths(operation["pre_change"], public_identifier_paths=paths), []
                )
                declaration["previous_value_sha256"] = "0" * 64
                with self.assertRaisesRegex(ValueError, "pre_change"):
                    validate_public_identifiers(contract)

    def test_exposure_report_distinguishes_pii_from_credential_and_locates_field(self):
        run = create_from_contract(
            valid_web_contract(), run_id="report", source_locator="Synthetic"
        )
        run["container_baselines"][0]["resources"] = {
            "tag": [
                {
                    "name": "Personal field fixture",
                    "type": "cvt_test",
                    "email": "person@example.test",
                }
            ]
        }
        output = render_markdown(run)
        self.assertIn("Personal data: Personal field fixture", output)
        self.assertIn(r"$.tag\[0\].email", output)
        self.assertNotIn("Credential-like literal", output)
        self.assertNotIn("rotate", output.lower())
        self.assertNotIn("person@example.test", output)

    def test_delta_uses_semantic_references_and_ignores_fingerprint(self):
        run = create_from_contract(valid_web_contract(), run_id="delta", source_locator="Synthetic")
        op = run["object_changes"][0]
        op.update(
            action="update",
            pre_change={
                "type": "googtag",
                "name": op["name"],
                "fingerprint": "old",
                "firingTriggerId": ["42"],
            },
            intended={"type": "googtag", "firingTriggerId": ["web-main::trigger::Ready"]},
        )
        run["container_baselines"][0]["resources"] = {
            "trigger": [{"name": "Ready", "type": "customEvent", "triggerId": "42"}]
        }
        self.assertEqual(semantic_field_changes(op, run), ["No semantic field changes"])

    def test_invalid_marker_extra_content_does_not_escape_scanner(self):
        value = {
            "secret_state": "present-not-compared",
            "reference": "secret://fixture",
            "unexpected": "SYNTHETIC-SECRET",
        }
        self.assertTrue(sensitive_paths(value))
        self.assertTrue(is_redacted(redact_for_persistence(value)))
        self.assertNotIn("SYNTHETIC-SECRET", json.dumps(redact_for_persistence(value)))
