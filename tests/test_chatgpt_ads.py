"""Pinned official native fields and saved-graph proof, not live Pixel/SDK certification."""

import hashlib
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]
from adapter_runtime import (  # noqa: E402
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from configuration_run import atomic_write, create_from_contract, load_document  # noqa: E402
from current_support import approve_mutations  # noqa: E402
from public_identifiers import public_identifier_paths  # noqa: E402
from redaction import sensitive_paths  # noqa: E402
from test_current_adapter_runtime import FakeAdapter, capabilities  # noqa: E402
from test_google_ads_enhanced_conversions import event_override_contract  # noqa: E402
from verification import build_verification_comparison, expected_graph  # noqa: E402


def chatgpt_contract():
    contract = event_override_contract()
    requirement = contract["requirements"][0]
    requirement.update(
        destination="ChatGPT Ads",
        event_name="order_created",
        source_event="purchase",
        parameters={},
    )
    contract["implementation"]["field_bindings"] = []
    contract["first_party_data_routes"] = []
    objects = contract["implementation"]["objects"]
    objects[:] = objects[:3]
    tag, trigger, block = objects
    block["depends_on"] = []
    # Retain the synthetic explicit-denial gate premise, not an SDK consent claim.
    block["intended"]["filter"][0]["parameter"][0]["value"] = "{{CMP - ChatGPT denied}}"
    template_key = "web-main::template::OpenAI Measurement Pixel"
    tag["depends_on"] = [trigger["object_key"], block["object_key"], template_key]

    def param(key, value, type="template"):
        return {"key": key, "type": type, "value": value}

    tag["intended"]["type"] = "cvt_1_123"
    tag["intended"]["parameter"] = [
        param("pixelId", "synthetic-pixel"),
        param("sendEvent", "true", "boolean"),
        param("eventName", "order_created"),
        param("eventId", "{{Order occurrence}}"),
        param("amount", "2500"),
        param("currency", "EUR"),
        {
            "key": "contents",
            "type": "list",
            "list": [
                {"type": "map", "map": [param("id", identity), param("quantity", quantity)]}
                for identity, quantity in [("item-one", "2"), ("item-two", "1")]
            ],
        },
    ]
    source = (ROOT / "tests/fixtures/openai-web-template.tpl").read_text(encoding="utf-8")
    objects.append(
        {
            "target_id": "web-main",
            "resource_family": "template",
            "name": "OpenAI Measurement Pixel",
            "object_key": template_key,
            "object_id": "123",
            "action": "reuse",
            "requirement_ids": ["REQ-PAGE"],
            "depends_on": [],
            "justification": "Inspected installed official template; import is outside this fixture",
            "evidence": ["container-confirmed"],
            "risk": "routine",
            "intended": {"templateData": source},
        }
    )
    source_url = "https://github.com/openai/ads-measurement-pixel-gtm-template/blob/01c709eebb3c1d00e87cb779762b90690a064940/template.tpl"
    objects[-1]["public_identifiers"] = [
        {
            "path": ["templateData"],
            "classification": "inspected-template-source",
            "value_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "source_url": source_url,
            "reason": "Inspected CACHE_TOKEN is used only as the injectScript cache key; code and permissions retained",
        }
    ]
    contract["evidence"].append(
        {
            "grade": "official-current",
            "locator": source_url,
            "title": "Pinned official OpenAI template",
            "decision": "Inspected actual native fields and source cache-key purpose",
            "accessed_on": "2026-09-30",
            "supports": ["REQ-PAGE"],
        }
    )
    topology = contract["execution_topologies"][0]
    topology["built_in_consent_checks"] = []
    contract["consent_topologies"][0].update(
        destination="ChatGPT Ads",
        event_coverage=["purchase"],
        signal_source="Synthetic CMP ChatGPT gate, denied includes unknown",
    )
    contract["external_dependencies"] = [
        {
            "id": "EXT-CHATGPT",
            "requirement_ids": ["REQ-PAGE"],
            "owner": "Media and CMP owners",
            "action": "Confirm Pixel/account settings and supported consent lifecycle; runtime delivery remains unverified",
            "status": "accepted",
        }
    ]
    return approve_mutations(contract)


class ChatGPTAdsTests(unittest.TestCase):
    def test_inspected_source_cache_key_does_not_exempt_credentials(self):
        template = chatgpt_contract()["implementation"]["objects"][-1]
        source = template["intended"]["templateData"]
        self.assertFalse(
            sensitive_paths(
                template["intended"],
                public_identifier_paths=public_identifier_paths(
                    template["intended"], records=[template]
                ),
            )
        )
        for bad in (
            "const access_token = 'opaque-secret';",
            "const headers = {Authorization: 'Bearer secret-token-value'};",
            "const value = 'sk_live_1234567890abcdef';",
        ):
            changed = source.replace(
                "___SANDBOXED_JS_FOR_WEB_TEMPLATE___", "___SANDBOXED_JS_FOR_WEB_TEMPLATE___\n" + bad
            )
            template["intended"]["templateData"] = changed
            template["public_identifiers"][0]["value_sha256"] = hashlib.sha256(
                changed.encode()
            ).hexdigest()
            self.assertTrue(
                sensitive_paths(
                    template["intended"],
                    public_identifier_paths=public_identifier_paths(
                        template["intended"], records=[template]
                    ),
                )
            )

    def test_official_fixture_provenance_and_native_materialization(self):
        provenance = json.loads(
            (ROOT / "tests/fixtures/openai-template-provenance.json").read_text()
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tests/fixtures/openai-web-template.tpl").read_bytes()
            ).hexdigest(),
            provenance["sha256"].lower(),
        )
        run = create_from_contract(
            chatgpt_contract(), run_id="chatgpt", source_locator="Synthetic authorized media brief"
        )
        tag = next(o for o in run["object_changes"] if o["resource_family"] == "tag")
        saved = expected_graph(tag)
        native = saved["objects"][0]
        context = []
        for field, identifier in (("firingTriggerId", "7"), ("blockingTriggerId", "8")):
            name = native[field][0].split("::", 2)[-1]
            native[field] = [identifier]
            context.append(
                {
                    "target_id": "web-main",
                    "object_type": "trigger",
                    "name": name,
                    "triggerId": identifier,
                    "type": "customEvent",
                }
            )
        native["consentSettings"] = {"consentStatus": "notSet"}
        saved["context_objects"] = context
        self.assertTrue(build_verification_comparison(tag, saved)[0]["pass"])
        for field, wrong in (
            ("eventName", "page_viewed"),
            ("eventId", "another-occurrence"),
            ("amount", "25"),
        ):
            changed = deepcopy(saved)
            next(p for p in changed["objects"][0]["parameter"] if p["key"] == field)["value"] = (
                wrong
            )
            self.assertFalse(build_verification_comparison(tag, changed)[0]["pass"])
        changed = deepcopy(saved)
        next(p for p in changed["objects"][0]["parameter"] if p["key"] == "contents")["list"].pop()
        self.assertFalse(build_verification_comparison(tag, changed)[0]["pass"])

    def test_saved_execution_and_noop_retain_installed_source_and_items(self):
        run = create_from_contract(
            chatgpt_contract(), run_id="chatgpt-save", source_locator="Synthetic approved input"
        )
        adapter = FakeAdapter(
            existing={o["name"] for o in run["object_changes"] if o["action"] == "reuse"}
        )
        target = run["run"]["targets"][0]
        adapter.bind_target(target)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, capabilities("tag", "trigger", "template"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry)
            count = len(adapter.mutations)
            verify_idempotent_rerun(path, registry)
            result = load_document(path)
            self.assertTrue(all(o["state"] == "verified" for o in result["object_changes"]))
            self.assertEqual(len(adapter.mutations), count)
            self.assertTrue(result["idempotency"]["checked"])


if __name__ == "__main__":
    unittest.main()
