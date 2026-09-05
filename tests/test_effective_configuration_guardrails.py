from __future__ import annotations

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
)
from configuration_run import (  # noqa: E402
    atomic_write,
    create_from_contract,
    load_document,
    render_markdown,
)
from current_support import (  # noqa: E402
    approve_mutations,
    valid_web_contract,
    with_complete_baselines,
)
from test_current_adapter_runtime import FakeAdapter, capabilities  # noqa: E402
from validate_configuration_contract import ContractValidationError, validate_document  # noqa: E402


def settings_contract(*, action="update"):
    contract = valid_web_contract()
    contract["implementation"]["objects"] = [
        {
            "target_id": "web-main",
            "resource_family": "variable",
            "name": "Google Settings",
            "object_key": "web-main::variable::Google Settings",
            "action": action,
            "object_id": "v7",
            "requirement_ids": ["REQ-PAGE"],
            "depends_on": [],
            "justification": "Approved shared page-view configuration change",
            "evidence": ["approved-input", "official-current", "container-confirmed"],
            "risk": "high-impact",
            "pre_change": {"type": "gtcs", "send_page_view": True},
            "intended": {"type": "gtcs", "send_page_view": False},
        }
    ]
    contract["execution_topologies"] = []
    contract["page_view_decisions"] = []
    contract["consent_topologies"] = []
    if action == "remove":
        contract["implementation"]["objects"][0].pop("intended")
    return approve_mutations(contract)


def separate_page_view_contract(*, virtual=False):
    contract = valid_web_contract()
    google = contract["implementation"]["objects"][0]
    initial = deepcopy(google)
    initial.update(
        name="GA4 - Initial view", object_key="web-main::tag::GA4 - Initial view", risk="routine"
    )
    initial["intended"].update(type="gaawe", event_name="page_view")
    initial["intended"].pop("send_page_view")
    initial["depends_on"].append(google["object_key"])
    google["intended"]["send_page_view"] = False
    initial_topology = deepcopy(contract["execution_topologies"][0])
    initial_topology["tag_object_key"] = initial["object_key"]
    contract["execution_topologies"][0].update(
        page_view_capable=False, page_view_destinations=[], page_view_occurrences=[]
    )
    contract["implementation"]["objects"].append(initial)
    contract["execution_topologies"].append(initial_topology)
    decision = contract["page_view_decisions"][0]
    decision.update(
        owner="dedicated-ga4-event", owner_object_key=initial["object_key"], send_page_view=False
    )
    if virtual:
        history = {
            "target_id": "web-main",
            "resource_family": "trigger",
            "name": "History changed",
            "object_key": "web-main::trigger::History changed",
            "action": "create",
            "requirement_ids": ["REQ-PAGE"],
            "depends_on": [],
            "justification": "Approved virtual navigation timing",
            "evidence": ["approved-input", "official-current"],
            "risk": "routine",
            "intended": {"type": "historyChange"},
        }
        tag = deepcopy(initial)
        tag.update(name="GA4 - Virtual view", object_key="web-main::tag::GA4 - Virtual view")
        tag["intended"]["firingTriggerId"] = [history["object_key"]]
        tag["depends_on"].append(history["object_key"])
        topology = deepcopy(initial_topology)
        topology.update(
            tag_object_key=tag["object_key"],
            lifecycle_role="event-driven",
            page_view_occurrences=["virtual-navigation"],
            normal_triggers=[
                {
                    "trigger_object_key": history["object_key"],
                    "type": "history-change",
                    "role": "source-event",
                }
            ],
        )
        contract["implementation"]["objects"].extend([history, tag])
        contract["execution_topologies"].append(topology)
        contract["external_dependencies"].append(
            {
                "id": "HISTORY-OWNER",
                "requirement_ids": ["REQ-PAGE"],
                "owner": "GA4 administrator",
                "action": "Disable Enhanced Measurement history-change collection for the manual virtual-view route before rollout",
                "status": "open",
            }
        )
        contract["page_view_decisions"].append(
            {
                **deepcopy(decision),
                "occurrence": "virtual-navigation",
                "owner_object_key": tag["object_key"],
                "external_dependency_ids": ["HISTORY-OWNER"],
            }
        )
    return approve_mutations(contract)


class EffectiveConfigurationGuardrailsTest(unittest.TestCase):
    def test_separate_initial_and_disjoint_virtual_page_views_are_valid(self):
        for virtual in (False, True):
            contract = separate_page_view_contract(virtual=virtual)
            run = create_from_contract(contract, run_id="MANUAL", source_locator="approved")
            self.assertEqual(len(run["page_view_decisions"]), 2 if virtual else 1)

    def test_two_page_view_tags_cannot_claim_disjoint_occurrences_on_the_same_trigger(self):
        contract = separate_page_view_contract(virtual=True)
        initial_topology = contract["execution_topologies"][1]
        virtual_topology = contract["execution_topologies"][2]
        trigger_key = initial_topology["normal_triggers"][0]["trigger_object_key"]
        virtual_tag = contract["implementation"]["objects"][-1]
        virtual_tag["intended"]["firingTriggerId"] = [trigger_key]
        virtual_topology["normal_triggers"] = [
            {"trigger_object_key": trigger_key, "type": "custom-event", "role": "source-event"}
        ]
        approve_mutations(contract)
        with self.assertRaisesRegex(ContractValidationError, "different occurrence labels"):
            validate_document(contract)

    def test_official_guidance_decision_is_required_and_survives_handoff(self):
        contract = valid_web_contract()
        source = next(item for item in contract["evidence"] if item["grade"] == "official-current")
        source["locator"] = "https://developers.google.com/analytics/devguides/collection/ga4/views"
        source["title"] = "Measure pageviews"
        source["decision"] = (
            "Google configuration sends the initial page_view; do not add a second initial owner."
        )
        run = create_from_contract(contract, run_id="GUIDANCE", source_locator="approved")
        self.assertEqual(run["official_sources"][0]["decision"], source["decision"])
        self.assertIn(source["decision"], render_markdown(run))
        self.assertIn(source["locator"], render_markdown(run))
        source.pop("decision")
        with self.assertRaisesRegex(ContractValidationError, "decision"):
            validate_document(contract)

    def test_automatic_page_views_cannot_be_hidden_by_empty_declarations(self):
        for explicit in (True, False):
            contract = valid_web_contract()
            if not explicit:
                contract["implementation"]["objects"][0]["intended"].pop("send_page_view")
                approve_mutations(contract)
            contract["execution_topologies"][0].update(
                page_view_capable=False, page_view_destinations=[], page_view_occurrences=[]
            )
            contract["page_view_decisions"] = []
            with (
                self.subTest(explicit=explicit),
                self.assertRaisesRegex(
                    ContractValidationError, "every effective Google page-view destination"
                ),
            ):
                validate_document(contract)

    def test_page_view_declarations_cannot_omit_a_configured_destination(self):
        contract = valid_web_contract()
        contract["implementation"]["objects"][0]["intended"]["destinations"] = ["G-SECOND"]
        approve_mutations(contract)
        with self.assertRaisesRegex(
            ContractValidationError, "every effective Google page-view destination"
        ):
            validate_document(contract)

    def test_ads_only_google_tag_does_not_require_a_ga4_page_view(self):
        contract = valid_web_contract()
        contract["implementation"]["objects"][0]["intended"]["measurement_id"] = "AW-123456"
        contract["execution_topologies"][0].update(
            page_view_capable=False, page_view_destinations=[], page_view_occurrences=[]
        )
        contract["page_view_decisions"] = []
        approve_mutations(contract)
        validate_document(contract)

    def test_variable_delta_requires_type_in_both_snapshots(self):
        for field in ("pre_change", "intended"):
            contract = settings_contract()
            contract["implementation"]["objects"][0][field].pop("type")
            approve_mutations(contract)
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(ContractValidationError, field + r".type"),
            ):
                validate_document(contract)

    def test_shared_settings_cannot_claim_routine_risk(self):
        contract = settings_contract()
        contract["implementation"]["objects"][0]["risk"] = "routine"
        with self.assertRaisesRegex(ContractValidationError, "high-impact"):
            validate_document(contract)

    def test_missing_tag_inventory_prevents_variable_only_mutation(self):
        run = create_from_contract(
            settings_contract(), run_id="SETTINGS", source_locator="approved"
        )
        target = run["run"]["targets"][0]
        adapter = FakeAdapter(existing={"Google Settings"})
        adapter.bind_target(target)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, capabilities("variable"))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry)
            result = load_document(path)
        self.assertEqual(adapter.mutations, [])
        self.assertEqual(result["object_changes"][0]["state"], "failed")
        self.assertIn(
            "required resource families", result["object_changes"][0]["journal"][-1]["error"]
        )

    def test_initial_execution_replaces_fabricated_baseline_with_actual_consumers(self):
        class ConsumerAdapter(FakeAdapter):
            def list_resource_page(self, resource_family, cursor):
                items = (
                    [
                        {
                            "name": "Unreviewed tag",
                            "type": "googtag",
                            "configSettingsVariable": "{{Google Settings}}",
                        }
                    ]
                    if resource_family == "tag"
                    else []
                )
                return {"items": items, "next_cursor": None}

        contract = valid_web_contract()
        contract["implementation"]["objects"].append(
            settings_contract()["implementation"]["objects"][0]
        )
        approve_mutations(contract)
        run = with_complete_baselines(
            create_from_contract(contract, run_id="BASELINE", source_locator="approved")
        )
        target = run["run"]["targets"][0]
        adapter = ConsumerAdapter(existing={"Google Settings"})
        adapter.bind_target(target)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, capabilities("tag", "trigger", "variable"))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry)
            result = load_document(path)
        self.assertEqual(adapter.mutations, [])
        self.assertTrue(all(item["state"] == "failed" for item in result["object_changes"]))
        self.assertIn(
            "every authenticated baseline consumer", str(result["object_changes"][0]["journal"])
        )

    def test_readback_failure_after_a_successful_write_remains_uncertain(self):
        for failure in (
            RateLimitError("rate limit", retry_after_seconds=0),
            AdapterExecutionError("read failed"),
        ):

            class ReadbackFailure(FakeAdapter):
                def read(self, operation):
                    if operation["name"] in self.saved:
                        raise failure
                    return super().read(operation)

            run = create_from_contract(
                valid_web_contract(), run_id="READBACK", source_locator="approved"
            )
            target = run["run"]["targets"][0]
            adapter = ReadbackFailure()
            adapter.bind_target(target)
            registry = TargetAdapterRegistry()
            registry.register(target, adapter, capabilities("tag", "trigger"))
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "run.json"
                atomic_write(path, deepcopy(run))
                execute_ready_operations(path, registry, max_rate_limit_retries=0)
                result = load_document(path)
            wrote = [item for item in result["object_changes"] if item["name"] in adapter.mutations]
            self.assertTrue(wrote)
            self.assertTrue(all(item["state"] == "uncertain" for item in wrote))
            self.assertTrue(all(value == 1 for value in adapter.attempts.values()))

    def test_new_shared_settings_consumer_after_baseline_prevents_the_write(self):
        class NewConsumerAdapter(FakeAdapter):
            tag_lists = 0

            def list_resource_page(self, resource_family, cursor):
                if resource_family != "tag":
                    return super().list_resource_page(resource_family, cursor)
                self.tag_lists += 1
                items = (
                    []
                    if self.tag_lists == 1
                    else [
                        {
                            "name": "New unrelated tag",
                            "type": "googtag",
                            "configSettingsVariable": "{{Google Settings}}",
                        }
                    ]
                )
                return {"items": items, "next_cursor": None}

        run = create_from_contract(
            settings_contract(), run_id="NEW-CONSUMER", source_locator="approved"
        )
        target = run["run"]["targets"][0]
        adapter = NewConsumerAdapter(existing={"Google Settings"})
        adapter.bind_target(target)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, capabilities("tag", "variable"))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(path, registry)
            result = load_document(path)
        self.assertEqual(adapter.mutations, [])
        self.assertEqual(adapter.tag_lists, 2)
        self.assertEqual(result["object_changes"][0]["state"], "failed")
        self.assertIn("unreviewed current consumers", str(result["object_changes"][0]["journal"]))
