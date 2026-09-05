from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from adapter_runtime import (  # noqa: E402
    AdapterExecutionError,
    RateLimitError,
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from configuration_run import (  # noqa: E402
    atomic_write,
    create_from_contract,
    load_document,
)
from current_support import (  # noqa: E402
    approve_mutations,
    valid_pipeline_contract,
    valid_server_contract,
    valid_web_contract,
    with_complete_baselines,
)
from redaction import redacted_marker  # noqa: E402
from resource_registry import required_baseline_families  # noqa: E402
from verification import expected_graph  # noqa: E402


def capabilities(*families: str) -> dict:
    return {
        family: {
            "list": True,
            "get": True,
            "create": True,
            "update": True,
            "remove": True,
        }
        for family in families
    }


class FakeAdapter:
    def __init__(
        self,
        *,
        existing: set[str] | None = None,
        fail_names: set[str] | None = None,
        rate_limit_once: set[str] | None = None,
        read_overrides: dict[str, dict] | None = None,
    ) -> None:
        self.existing = set(existing or set())
        self.fail_names = set(fail_names or set())
        self.rate_limit_once = set(rate_limit_once or set())
        self.read_overrides = deepcopy(read_overrides or {})
        self.saved: dict[str, dict] = {}
        self.mutations: list[str] = []
        self.attempts: dict[str, int] = {}
        self.received: list[dict] = []
        self.observed_identity: dict[str, str] | None = None

    def bind_target(self, target: dict) -> None:
        self.observed_identity = {
            field: target[field]
            for field in ("account_id", "container_id", "workspace_id", "container_type")
        }

    def identity(self) -> dict[str, str]:
        if self.observed_identity is None:
            raise RuntimeError("fake adapter target is not bound")
        return deepcopy(self.observed_identity)

    def read(self, operation: dict) -> dict | None:
        name = operation["name"]
        if name in self.read_overrides:
            return deepcopy(self.read_overrides[name])
        if name in self.saved:
            return deepcopy(self.saved[name])
        if name in self.existing:
            if operation.get("pre_change") is not None:
                return {"name": operation["name"], **deepcopy(operation["pre_change"])}
            return deepcopy(expected_graph(operation))
        return None

    def mutate(self, operation: dict) -> dict | None:
        name = operation["name"]
        self.received.append(deepcopy(operation))
        self.attempts[name] = self.attempts.get(name, 0) + 1
        if name in self.rate_limit_once and self.attempts[name] == 1:
            raise RateLimitError("retry later", retry_after_seconds=0)
        if name in self.fail_names:
            raise AdapterExecutionError("documented target rejection", code="target_rejected")
        self.mutations.append(name)
        self.saved[name] = expected_graph(operation)
        return deepcopy(self.saved[name])

    def list_resource_page(self, resource_family: str, cursor: str | None) -> dict:
        if cursor is not None:
            raise AssertionError("fake adapter has only one baseline page")
        return {"items": [], "next_cursor": None}

    def list_workspace_changes_page(self, cursor: str | None) -> dict:
        if cursor is not None:
            raise AssertionError("fake adapter has only one workspace-change page")
        return {"items": [], "next_cursor": None}


class StaticSecretProvider:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def resolve(self, reference: str) -> str:
        return self.values[reference]


class CurrentAdapterRuntimeTest(unittest.TestCase):
    def test_configuration_settings_mutation_requires_tag_consumer_inventory(self) -> None:
        operation = {
            "resource_family": "variable",
            "action": "update",
            "intended": {"type": "Google Tag Configuration Settings"},
        }
        self.assertEqual(
            required_baseline_families([operation], "web"),
            {"variable", "tag"},
        )

    def test_execution_captures_and_retains_authenticated_baseline(self) -> None:
        class BaselineAdapter(FakeAdapter):
            def list_resource_page(self, resource_family, cursor):
                if resource_family == "tag":
                    return {
                        "items": [{"name": "Existing safe tag", "type": "html"}],
                        "next_cursor": None,
                    }
                return {"items": [], "next_cursor": None}

        run = create_from_contract(
            valid_web_contract(), run_id="RUN-AUTH-BASELINE", source_locator="approved"
        )
        target = run["run"]["targets"][0]
        adapter = BaselineAdapter()
        adapter.bind_target(target)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, capabilities("tag", "trigger"))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry, sleep=lambda _: None, random_value=lambda: 0)
            result = load_document(path)
        baseline = result["container_baselines"][0]
        self.assertEqual(
            baseline["capture_evidence"]["captured_by"], "authenticated-adapter-runtime"
        )
        self.assertEqual(baseline["resources"]["tag"][0]["name"], "Existing safe tag")

    def test_exhausted_rate_limit_keeps_its_specific_classification(self) -> None:
        class AlwaysLimitedAdapter(FakeAdapter):
            def mutate(self, operation):
                raise RateLimitError("documented rate limit", retry_after_seconds=0)

        run = create_from_contract(
            valid_web_contract(), run_id="RUN-RATE-CLASS", source_locator="approved"
        )
        target = run["run"]["targets"][0]
        adapter = AlwaysLimitedAdapter()
        adapter.bind_target(target)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, capabilities("tag", "trigger"))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(
                path,
                registry,
                max_rate_limit_retries=0,
                sleep=lambda _: None,
                random_value=lambda: 0,
            )
            persisted = path.read_text(encoding="utf-8")
        self.assertIn("documented rate limit", persisted)
        self.assertNotIn("unexpected_adapter_failure", persisted)

    def test_unexpected_adapter_error_is_scrubbed_and_checkpointed(self) -> None:
        class ExplodingAdapter(FakeAdapter):
            def read(self, operation):
                raise RuntimeError("X-API-Key: TOPSECRET123")

        run = with_complete_baselines(
            create_from_contract(
                valid_web_contract(), run_id="RUN-ADAPTER-ERROR", source_locator="approved"
            )
        )
        target = run["run"]["targets"][0]
        adapter = ExplodingAdapter()
        adapter.bind_target(target)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, capabilities("tag", "trigger"))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry, sleep=lambda _: None, random_value=lambda: 0)
            persisted = path.read_text(encoding="utf-8")
        self.assertNotIn("TOPSECRET123", persisted)
        self.assertIn("unexpected_adapter_failure", persisted)

    def test_adapter_identity_is_rechecked_before_execution(self) -> None:
        run = with_complete_baselines(
            create_from_contract(
                valid_web_contract(), run_id="RUN-WRONG-TARGET", source_locator="approved input"
            )
        )
        target = run["run"]["targets"][0]
        adapter = FakeAdapter()
        adapter.bind_target(target)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, capabilities("tag", "trigger"))
        adapter.observed_identity["workspace_id"] = "different-workspace"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry, sleep=lambda _: None, random_value=lambda: 0)
            result = load_document(path)
        self.assertEqual(adapter.mutations, [])
        errors = [
            entry.get("error", "") for item in result["object_changes"] for entry in item["journal"]
        ]
        self.assertTrue(any("authenticated adapter identity differs" in value for value in errors))

    def test_fresh_read_only_convergence_is_required_for_finalization(self) -> None:
        run = with_complete_baselines(
            create_from_contract(
                valid_web_contract(),
                run_id="RUN-CONVERGENCE",
                source_locator="approved input",
                timestamp="2026-08-18T00:00:00Z",
            )
        )
        target = run["run"]["targets"][0]
        adapter = FakeAdapter()
        adapter.bind_target(target)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, capabilities("tag", "trigger"))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(
                path,
                registry,
                timestamp=lambda: "2026-08-18T00:00:01Z",
                sleep=lambda _: None,
                random_value=lambda: 0,
            )
            mutation_count = len(adapter.mutations)
            proof = verify_idempotent_rerun(
                path, registry, timestamp=lambda: "2026-08-18T00:00:02Z"
            )
            self.assertTrue(proof["checked"])
            self.assertEqual(len(proof["observations"]), len(run["object_changes"]))
            self.assertEqual(len(adapter.mutations), mutation_count)
            configured = load_document(path)
            self.assertEqual(configured["run"]["status"], "Configured")

    def test_convergence_mismatch_records_required_action_and_blocks_finalization(self) -> None:
        run = with_complete_baselines(
            create_from_contract(
                valid_web_contract(), run_id="RUN-DRIFT", source_locator="approved input"
            )
        )
        target = run["run"]["targets"][0]
        adapter = FakeAdapter()
        adapter.bind_target(target)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, capabilities("tag", "trigger"))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry, sleep=lambda _: None, random_value=lambda: 0)
            drifted_operation = run["object_changes"][0]
            drifted_name = drifted_operation["name"]
            drifted = expected_graph(drifted_operation)
            drifted["objects"][0]["type"] = "drifted-type"
            adapter.read_overrides[drifted_name] = drifted
            proof = verify_idempotent_rerun(path, registry)
            self.assertFalse(proof["checked"])
            self.assertTrue(proof["remaining_actions"])
            self.assertNotEqual(load_document(path)["run"]["status"], "Configured")

    def test_convergence_timestamp_must_follow_operation_verification(self) -> None:
        run = with_complete_baselines(
            create_from_contract(
                valid_web_contract(), run_id="RUN-STALE-CONVERGENCE", source_locator="approved"
            )
        )
        target = run["run"]["targets"][0]
        adapter = FakeAdapter()
        adapter.bind_target(target)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, capabilities("tag", "trigger"))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(
                path,
                registry,
                timestamp=lambda: "2026-08-18T00:00:01Z",
                sleep=lambda _: None,
                random_value=lambda: 0,
            )
            with self.assertRaisesRegex(Exception, "newer than verification"):
                verify_idempotent_rerun(path, registry, timestamp=lambda: "2026-08-18T00:00:01Z")

    def _execute(
        self,
        contract: dict,
        bindings: dict[str, tuple[FakeAdapter, dict, StaticSecretProvider | None]],
        **kwargs: object,
    ) -> tuple[dict, dict[str, FakeAdapter]]:
        approve_mutations(contract)
        run = create_from_contract(
            contract,
            run_id="RUN-ADAPTER",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        run = with_complete_baselines(run)
        target_by_id = {item["target_id"]: item for item in run["run"]["targets"]}
        registry = TargetAdapterRegistry()
        adapters: dict[str, FakeAdapter] = {}
        for target_id, (adapter, matrix, provider) in bindings.items():
            adapter.bind_target(target_by_id[target_id])
            registry.register(
                target_by_id[target_id],
                adapter,
                matrix,
                secret_provider=provider,
            )
            adapters[target_id] = adapter
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(
                path,
                registry,
                timestamp=lambda: "2026-08-18T00:00:01Z",
                sleep=kwargs.pop("sleep", lambda _: None),
                random_value=lambda: 0,
                **kwargs,
            )
            return load_document(path), adapters

    def test_failed_client_stops_dependents_but_not_an_independent_web_object(self) -> None:
        contract = valid_pipeline_contract(cutover=True)
        web_only = valid_web_contract()
        block_key = "web-main::trigger::CMP - Analytics denied"
        block_trigger = next(
            deepcopy(item)
            for item in web_only["implementation"]["objects"]
            if item["object_key"] == block_key
        )
        contract["implementation"]["objects"].append(block_trigger)
        direct_topology = deepcopy(web_only["consent_topologies"][0])
        direct_topology["consent_topology_id"] = "CONSENT-DIAGNOSTICS"
        direct_topology["destination"] = "Diagnostics"
        contract["consent_topologies"].append(direct_topology)
        client = contract["implementation"]["objects"][1]
        client.update(
            {
                "action": "create",
                "intended": {
                    "type": "ga4-client",
                    "claim_criteria": "Default GA4 Client claims GA4 collect requests",
                    "priority": 10,
                },
                "evidence": ["approved-input", "official-current"],
                "risk": "high-impact",
            }
        )
        contract["implementation"]["objects"].append(
            {
                "target_id": "web-main",
                "resource_family": "tag",
                "name": "Independent - Diagnostics",
                "object_key": "web-main::tag::Independent - Diagnostics",
                "action": "create",
                "requirement_ids": ["REQ-PAGE"],
                "depends_on": [
                    "web-main::trigger::CMP - Analytics granted",
                    block_key,
                ],
                "justification": "Independent approved web destination",
                "evidence": ["approved-input", "official-current"],
                "risk": "routine",
                "intended": {
                    "type": "html",
                    "event_name": "diagnostic",
                    "firingTriggerId": ["web-main::trigger::CMP - Analytics granted"],
                    "blockingTriggerId": [block_key],
                    "tagFiringOption": "oncePerEvent",
                },
            }
        )
        contract["execution_topologies"].append(
            {
                "tag_object_key": "web-main::tag::Independent - Diagnostics",
                "requirement_ids": ["REQ-PAGE"],
                "lifecycle_role": "event-driven",
                "normal_triggers": [
                    {
                        "trigger_object_key": "web-main::trigger::CMP - Analytics granted",
                        "role": "source-event",
                        "type": "custom-event",
                    }
                ],
                "consent_mode": "strict-basic",
                "consent_topology_ids": ["CONSENT-DIAGNOSTICS"],
                "blocking_trigger_keys": [block_key],
                "blocking_event_scope": ".*",
                "built_in_consent_checks": ["analytics_storage"],
                "additional_consent_checks": [],
                "firing_option": "once-per-event",
                "may_precede_cmp": False,
                "pre_cmp_policy": "not-applicable",
                "page_view_capable": False,
                "page_view_destinations": [],
                "page_view_occurrences": [],
                "ecommerce_route": "not-applicable",
                "manual_ecommerce_fields": [],
                "evidence": ["official-current", "container-confirmed"],
            }
        )
        server = FakeAdapter(fail_names={"GA4 Client - Web transport"})
        web = FakeAdapter()
        run, _ = self._execute(
            contract,
            {
                "web-main": (web, capabilities("tag", "trigger"), None),
                "server-main": (server, capabilities("client", "tag", "trigger"), None),
            },
        )
        states = {item["name"]: item["state"] for item in run["object_changes"]}
        self.assertEqual(states["GA4 Client - Web transport"], "failed")
        self.assertEqual(states["GA4 - page_view"], "planned")
        self.assertEqual(states["Google tag - Web transport"], "planned")
        self.assertEqual(states["Independent - Diagnostics"], "verified")
        self.assertIn("Independent - Diagnostics", web.mutations)

    def test_one_failed_destination_does_not_block_an_independent_destination(self) -> None:
        contract = valid_pipeline_contract()
        meta_key = "server-main::tag::Meta - PageView"
        server_trigger_key = "server-main::trigger::Event Data - page_view"
        web_transport_key = "web-main::tag::Google tag - Web transport"
        contract["implementation"]["objects"].append(
            {
                "target_id": "server-main",
                "resource_family": "tag",
                "name": "Meta - PageView",
                "object_key": meta_key,
                "action": "create",
                "requirement_ids": ["REQ-PAGE"],
                "depends_on": [
                    "server-main::client::GA4 Client - Web transport",
                    server_trigger_key,
                ],
                "justification": "Approved independent server destination",
                "evidence": ["approved-input", "official-current"],
                "risk": "routine",
                "intended": {
                    "type": "meta-capi",
                    "event_name": "PageView",
                    "firingTriggerId": [server_trigger_key],
                    "blockingTriggerId": [],
                },
            }
        )
        contract["consent_topologies"].append(
            {
                "consent_topology_id": "CONSENT-META",
                "destination": "Meta",
                "requirement_ids": ["REQ-PAGE"],
                "consent_mode": "product-specific",
                "transport_behavior": "always-transported",
                "web_enforcement": {"mechanism": "transport-trigger-only"},
                "server_enforcement": {
                    "mechanism": "server-template-native-consent",
                    "template_support": "Installed Meta template consent field",
                },
                "signal_authority": "product-native",
                "signal_source": "Installed Meta server template consent input",
                "unknown_state_behavior": "explicit-policy",
                "event_coverage": ["page_view"],
                "intentional_double_gate": False,
                "server_tag_keys": [meta_key],
                "transporter_tag_keys": [web_transport_key],
                "transporter_destination_vendor_block": False,
            }
        )
        contract["pipelines"][0]["consent_topology_ids"].append("CONSENT-META")
        contract["pipelines"][0]["event_flows"][0]["server_consumer_keys"].append(meta_key)
        contract["pipelines"][0]["operation_dependencies"].append(meta_key)
        next(
            item
            for item in contract["implementation"]["objects"]
            if item["object_key"] == contract["pipelines"][0]["cutover_operation_key"]
        )["depends_on"].append(meta_key)
        server = FakeAdapter(
            existing={"GA4 Client - Web transport"}, fail_names={"Meta - PageView"}
        )
        web = FakeAdapter()
        run, _ = self._execute(
            contract,
            {
                "web-main": (web, capabilities("tag", "trigger"), None),
                "server-main": (server, capabilities("client", "tag", "trigger"), None),
            },
        )
        states = {item["name"]: item["state"] for item in run["object_changes"]}
        self.assertEqual(states["GA4 - page_view"], "verified")
        self.assertEqual(states["Meta - PageView"], "failed")
        self.assertEqual(states["Google tag - Web transport"], "planned")

    def test_cutover_executes_only_after_receiver_operations(self) -> None:
        contract = valid_pipeline_contract(cutover=True)
        server = FakeAdapter(existing={"GA4 Client - Web transport"})
        web = FakeAdapter(existing={"Google tag - Web transport"})
        run, adapters = self._execute(
            contract,
            {
                "web-main": (web, capabilities("tag", "trigger"), None),
                "server-main": (server, capabilities("client", "tag", "trigger"), None),
            },
        )
        states = {item["name"]: item["state"] for item in run["object_changes"]}
        self.assertEqual(set(states.values()), {"verified"})
        self.assertEqual(
            adapters["server-main"].mutations,
            ["Event Data - page_view", "GA4 - page_view"],
        )
        self.assertIn("Google tag - Web transport", adapters["web-main"].mutations)
        target_capabilities = {
            target["target_id"]: target["adapter_capabilities"] for target in run["run"]["targets"]
        }
        self.assertTrue(target_capabilities["server-main"]["client"]["get"])
        self.assertTrue(target_capabilities["web-main"]["tag"]["update"])

    def test_container_drift_blocks_only_the_stale_cutover_object(self) -> None:
        contract = valid_pipeline_contract(cutover=True)
        server = FakeAdapter(existing={"GA4 Client - Web transport"})
        web = FakeAdapter(
            read_overrides={
                "Google tag - Web transport": {
                    "type": "googtag",
                    "measurement_id": "G-CHANGED",
                    "send_page_view": True,
                    "tagManagerUrl": "https://tagmanager.google.com/ignored-metadata",
                }
            }
        )
        run, adapters = self._execute(
            contract,
            {
                "web-main": (web, capabilities("tag", "trigger"), None),
                "server-main": (server, capabilities("client", "tag", "trigger"), None),
            },
        )
        states = {item["name"]: item["state"] for item in run["object_changes"]}
        self.assertEqual(states["Google tag - Web transport"], "failed")
        self.assertEqual(states["GA4 - page_view"], "verified")
        self.assertNotIn("Google tag - Web transport", adapters["web-main"].mutations)
        stale = next(
            item for item in run["object_changes"] if item["name"] == "Google tag - Web transport"
        )
        self.assertEqual(stale["journal"][-1]["error"], "container_drift")

    def test_replace_requires_both_remove_and_create_capabilities(self) -> None:
        contract = valid_web_contract()
        operation = contract["implementation"]["objects"][0]
        operation.update(
            {
                "action": "replace",
                "object_id": "tag-100",
                "pre_change": deepcopy(operation["intended"]),
                "replacement_reason": "Replace the incompatible saved Google tag",
                "evidence": [
                    "approved-input",
                    "official-current",
                    "container-confirmed",
                ],
                "risk": "high-impact",
            }
        )
        matrix = capabilities("tag", "trigger")
        matrix["tag"]["create"] = False
        adapter = FakeAdapter(existing={"Google tag - Web transport"})
        run, _ = self._execute(
            contract,
            {"web-main": (adapter, matrix, None)},
        )
        saved = run["object_changes"][0]
        self.assertEqual(saved["state"], "failed")
        self.assertIn("governed replace", saved["journal"][-1]["error"])
        self.assertNotIn("Google tag - Web transport", adapter.mutations)

    def test_documented_nonapplied_rate_limit_retries_within_bound(self) -> None:
        contract = valid_web_contract()
        adapter = FakeAdapter(rate_limit_once={"Google tag - Web transport"})
        delays: list[float] = []
        run, _ = self._execute(
            contract,
            {"web-main": (adapter, capabilities("tag", "trigger"), None)},
            max_rate_limit_retries=1,
            sleep=delays.append,
        )
        self.assertEqual(run["object_changes"][0]["state"], "verified")
        self.assertEqual(adapter.attempts["Google tag - Web transport"], 2)
        self.assertEqual(delays, [0])

    def test_secret_is_resolved_only_for_mutation_and_never_persisted(self) -> None:
        contract = valid_server_contract()
        server_tag = contract["implementation"]["objects"][1]
        server_tag["intended"]["secret_fields"] = ["apiAccessToken"]
        server_tag["intended"]["apiAccessToken"] = redacted_marker(reference="vault://meta/token")
        adapter = FakeAdapter(existing={"GA4 Client - Web transport"})
        provider = StaticSecretProvider({"vault://meta/token": "runtime-secret-token"})
        run, _ = self._execute(
            contract,
            {
                "server-main": (
                    adapter,
                    capabilities("client", "tag", "trigger"),
                    provider,
                )
            },
        )
        self.assertEqual(run["object_changes"][1]["state"], "verified")
        self.assertEqual(adapter.received[-1]["intended"]["apiAccessToken"], "runtime-secret-token")
        self.assertEqual(adapter.received[-1]["intended"]["secret_fields"], ["apiAccessToken"])
        serialized = json.dumps(run)
        self.assertNotIn("runtime-secret-token", serialized)
        comparison = run["object_changes"][1]["comparison"]
        self.assertFalse(comparison["report"]["secret_comparison"]["value_equality_claimed"])

    def test_missing_secret_provider_blocks_only_the_affected_operation(self) -> None:
        contract = valid_server_contract()
        contract["implementation"]["objects"][1]["intended"]["access_token"] = redacted_marker(
            reference="vault://meta/token"
        )
        adapter = FakeAdapter(existing={"GA4 Client - Web transport"})
        run, _ = self._execute(
            contract,
            {"server-main": (adapter, capabilities("client", "tag", "trigger"), None)},
        )
        states = {item["name"]: item["state"] for item in run["object_changes"]}
        self.assertEqual(states["GA4 Client - Web transport"], "verified")
        self.assertEqual(states["GA4 - page_view"], "failed")
        self.assertEqual(adapter.mutations, ["Event Data - page_view"])


if __name__ == "__main__":
    unittest.main()
