from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]
from adapter_runtime import (  # noqa: E402
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from compile_configuration_request import compile_request  # noqa: E402
from configuration_run import atomic_write, create_from_contract, load_document  # noqa: E402
from consent_conventions import validate_convention  # noqa: E402
from fixtures.mcp_behavior_scenario import (  # noqa: E402
    PROFILE,
    FakeGtm,
    condition,
    param,
    request,
)
from mcp_adapter import McpTargetAdapter  # noqa: E402
from redaction import sensitive_findings  # noqa: E402
from run_render import analyst_field_changes, render_markdown  # noqa: E402
from validate_configuration_contract import validate_document  # noqa: E402


def ungated_request():
    req = request()
    req["objects"][0]["intended"].pop("blockingTriggerId")
    req["execution_topologies"][0].update(
        consent_mode="client-policy-ungated",
        blocking_trigger_keys=[],
        blocking_event_scope=None,
        may_precede_cmp=False,
        pre_cmp_policy="not-applicable",
    )
    req["consent_topologies"][0].update(
        consent_mode="client-policy-ungated",
        signal_authority="none",
        signal_source="Approved client collection policy",
        unknown_state_behavior="explicit-policy",
        transport_behavior="always-transported",
        web_enforcement={
            "mechanism": "none",
            "client_policy": {
                "grade": "approved-input",
                "locator": "Synthetic approved client instruction",
                "scope": "This test website and GA4 destination",
            },
        },
    )
    return req


def firing_request():
    req = request()
    req["objects"][0]["intended"].pop("blockingTriggerId")
    top = req["execution_topologies"][0]
    top.update(blocking_trigger_keys=[], blocking_event_scope=None)
    grant = condition("{{CMP Analytics}}", "granted")
    req["reuse_candidates"][0]["intended"]["filter"] = [grant]
    req["consent_topologies"][0]["web_enforcement"] = {
        "mechanism": "firing-trigger-condition",
        "grant_condition": grant,
        "evidence": "Inspected normalized CMP signal: unknown and denied are not granted",
    }
    return req


def additional_request():
    req = request()
    req["route"] = "combined"
    req["requirements"][0]["kind"] = "analytics"
    req["requirements"].append(
        {
            "id": "REQ-CMP",
            "kind": "consent",
            "authority": {"grade": "approved-input", "locator": "Reuse inspected CMP default"},
            "parameters": {},
        }
    )
    for evidence in req["evidence"]:
        if evidence["grade"] == "official-current":
            evidence["supports"].append("REQ-CMP")
    for obj in req["objects"] + req["reuse_candidates"]:
        obj["requirement_ids"] = ["REQ-LEAD"]
    owner_key = "web-main::tag::CMP defaults"
    tag = req["objects"][0]
    tag["depends_on"] = [owner_key]
    tag["intended"].pop("blockingTriggerId")
    tag["intended"]["consentSettings"] = {
        "consentStatus": "needed",
        "consentType": {
            "type": "list",
            "list": [{"type": "template", "value": "analytics_storage"}],
        },
    }
    req["objects"].append(
        {
            "resource_family": "tag",
            "name": "CMP defaults",
            "action": "reuse",
            "requirement_ids": ["REQ-CMP"],
            "intended": {
                "type": "cvt_42",
                "firingTriggerId": ["2147479572"],
                "parameter": [param("analytics_storage", "denied")],
            },
            "justification": "Reuse inspected consent default owner",
            "risk": "routine",
            "evidence": ["approved-input", "container-confirmed", "official-current"],
        }
    )
    req["execution_topologies"][0].update(
        blocking_trigger_keys=[],
        blocking_event_scope=None,
        additional_consent_checks=["analytics_storage"],
    )
    req["consent_topologies"][0]["web_enforcement"] = {
        "mechanism": "additional-consent-checks",
        "evidence": "Inspected native template default and update fields",
        "default_bindings": {
            "analytics_storage": {
                "object_key": owner_key,
                "field_path": ["parameter", "analytics_storage", "value"],
            }
        },
    }
    return req


def execute(req):
    contract = compile_request(req)
    backend = FakeGtm(req)
    for index, obj in enumerate(req["objects"], 800):
        if obj["action"] == "reuse" and obj["resource_family"] == "tag":
            backend.data["tag"][str(index)] = {
                **backend.scope,
                **obj["intended"],
                "name": obj["name"],
                "tagId": str(index),
                "fingerprint": "1",
            }
    target = contract["targets"][0]
    adapter = McpTargetAdapter(target, PROFILE, backend.call)
    registry = TargetAdapterRegistry()
    registry.register(target, adapter, adapter.capabilities())
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "run.json"
        atomic_write(
            path,
            create_from_contract(contract, run_id="utility", source_locator="Synthetic request"),
        )
        execute_ready_operations(path, registry)
        verify_idempotent_rerun(path, registry)
        return load_document(path), backend


class UtilityCorrections(unittest.TestCase):
    def test_ungated_policy_is_not_limited_to_google_tags(self):
        req = ungated_request()
        req["route"] = "media"
        req["requirements"][0].update(destination="Meta", event_name="Lead")
        req["consent_topologies"][0]["destination"] = "Meta"
        req["objects"][0]["intended"].update(
            type="cvt_42", parameter=[param("pixelId", "123456"), param("eventName", "Lead")]
        )
        req["execution_topologies"][0]["built_in_consent_checks"] = []
        doc, backend = execute(req)
        self.assertEqual(doc["run"]["status"], "Configured")
        self.assertEqual(len(backend.writes), 1)

    def test_additional_convention_executes_through_contract_and_runtime(self):
        doc, backend = execute(additional_request())
        self.assertEqual(doc["run"]["status"], "Configured")
        self.assertEqual(len(backend.writes), 1)

    def test_unbound_fields_rejected_by_compiler_and_contract_before_adapter(self):
        req = request()
        contract = compile_request(req)
        field = {
            "source": "form.id",
            "source_shape": "scalar:string",
            "destination_shape": "scalar:string",
            "provenance": {"grade": "approved-input", "locator": "Approved form ID"},
        }
        req["requirements"][0]["parameters"]["form_id"] = field
        contract["requirements"][0]["parameters"]["form_id"] = field
        for function, value in ((compile_request, req), (validate_document, contract)):
            with (
                self.subTest(function=function.__name__),
                self.assertRaisesRegex(ValueError, "Bind approved fields before execution"),
            ):
                function(value)

    def test_ungated_policy_executes_and_is_plain_in_report(self):
        doc, backend = execute(ungated_request())
        self.assertEqual(doc["run"]["status"], "Configured")
        self.assertEqual(len(backend.writes), 1)
        self.assertIn("No consent gating", render_markdown(doc))

    def test_ungated_policy_requires_authority_and_scope(self):
        for field in ("locator", "scope", "grade"):
            req = ungated_request()
            del req["consent_topologies"][0]["web_enforcement"]["client_policy"][field]
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(ValueError, "approved-input client_policy"),
            ):
                compile_request(req)

    def test_ungated_policy_rejects_cmp_behavior(self):
        req = ungated_request()
        req["execution_topologies"][0].update(may_precede_cmp=True, pre_cmp_policy="drop")
        with self.assertRaisesRegex(ValueError, "CMP-dependent"):
            compile_request(req)

    def test_existing_firing_convention_executes(self):
        doc, backend = execute(firing_request())
        self.assertEqual(doc["run"]["status"], "Configured")
        self.assertEqual(len(backend.writes), 1)

    def test_firing_proof_cannot_cover_an_ungated_trigger(self):
        req = firing_request()
        del req["reuse_candidates"][0]["intended"]["filter"]
        with self.assertRaisesRegex(ValueError, "Every firing trigger"):
            compile_request(req)

    def test_firing_gate_rejects_unknown_matching_and_negation(self):
        for grant in (
            condition("{{CMP Analytics}}", "undefined"),
            condition("{{CMP Analytics}}", "", "contains"),
        ):
            req = firing_request()
            req["consent_topologies"][0]["web_enforcement"]["grant_condition"] = grant
            with self.assertRaisesRegex(ValueError, "reject missing and denied"):
                compile_request(req)

    def test_additional_checks_require_real_denied_default_and_initialization(self):
        execution = {
            "tag_object_key": "event",
            "blocking_trigger_keys": [],
            "blocking_event_scope": None,
            "lifecycle_role": "event-driven",
            "firing_option": "once-per-event",
            "additional_consent_checks": ["analytics_storage"],
        }
        enforcement = {
            "mechanism": "additional-consent-checks",
            "evidence": "Inspected CMP template default and updates",
            "default_bindings": {
                "analytics_storage": {
                    "object_key": "cmp",
                    "field_path": ["parameter", "analytics_storage", "value"],
                }
            },
        }
        operations = {
            "event": {"depends_on": ["cmp"]},
            "cmp": {
                "action": "reuse",
                "resource_family": "tag",
                "intended": {
                    "type": "cvt_42",
                    "firingTriggerId": ["2147479572"],
                    "parameter": [param("analytics_storage", "denied")],
                },
            },
        }

        def fail(message):
            raise ValueError(message)

        validate_convention(execution, enforcement, operations, fail)
        operations["cmp"]["intended"]["parameter"][0]["value"] = "granted"
        with self.assertRaisesRegex(ValueError, "resolve to denied"):
            validate_convention(execution, enforcement, operations, fail)
        operations["cmp"]["intended"]["parameter"][0]["value"] = "denied"
        operations["cmp"]["intended"]["firingTriggerId"] = ["2147479573"]
        with self.assertRaisesRegex(ValueError, "Consent Initialization"):
            validate_convention(execution, enforcement, operations, fail)

    def test_scan_cache_preserves_context_changes_and_return_isolation(self):
        value = {"value": "ordinary"}
        self.assertEqual(sensitive_findings(value), [])
        self.assertTrue(sensitive_findings(value, exact_secret_paths={"$.value"}))
        value["api_secret"] = "not-public"
        findings = sensitive_findings(value)
        self.assertTrue(findings)
        findings.clear()
        self.assertTrue(sensitive_findings(value))
        graph = [{"name": "Delivery", "type": "c", "parameter": [param("value", "opaque-literal")]}]
        self.assertEqual(sensitive_findings(graph), [])
        graph.append({"api_secret": "{{Delivery}}"})
        self.assertTrue(any("value" in row["path"] for row in sensitive_findings(graph)))

    def test_analyst_report_labels_parameters_and_retains_unknown_fields(self):
        after = {
            "object_type": "tag",
            "target_id": "web-main",
            "parameter": [
                param("eventName", "generate_lead"),
                {
                    "key": "eventSettingsTable",
                    "type": "list",
                    "list": [
                        {
                            "type": "map",
                            "map": [
                                param("parameter", "form_id"),
                                param("parameterValue", "{{DLV - form.id}}"),
                            ],
                        }
                    ],
                },
            ],
            "unknownFeature": {"enabled": True},
        }
        changes = "; ".join(analyst_field_changes({}, after))
        self.assertIn("Event name: absent → generate_lead", changes)
        self.assertIn("form_id = {{DLV - form.id}}", changes)
        self.assertIn("unknownFeature", changes)
        self.assertNotIn("target_id", changes)
        self.assertNotIn("object_type", changes)


if __name__ == "__main__":
    unittest.main()
