from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from gtm_configure.contract import ContractValidationError, validate_document
from gtm_configure.render import render_markdown
from gtm_configure.runtime.adapter_protocol import atomic_write
from gtm_configure.runtime.engine import (
    AdapterExecutionError,
    RateLimitError,
    TargetAdapterRegistry,
    execute_ready_operations,
)
from gtm_configure.runtime.state import create_from_contract, load_document

from support.adapters import FakeAdapter, capabilities
from support.contracts import approve_mutations, valid_web_contract, with_complete_baselines

ROOT = Path(__file__).resolve().parents[2]


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
    contract["requirements"][0]["parameters"] = {}
    contract["implementation"]["field_bindings"] = []
    contract["tag_policies"] = []
    contract["page_view_decisions"] = []
    contract["consent_policies"] = []
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
    initial_topology = deepcopy(contract["tag_policies"][0])
    initial_topology["tag_object_key"] = initial["object_key"]
    initial_topology["page_view_occurrences"] = ["initial-page-load"]
    contract["tag_policies"][0].update(page_view_occurrences=[])
    contract["implementation"]["objects"].append(initial)
    contract["tag_policies"].append(initial_topology)
    decision = contract["page_view_decisions"][0]
    decision.update(owner="dedicated-ga4-event", owner_object_key=initial["object_key"])
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
            trigger_roles=[
                {
                    "trigger_object_key": history["object_key"],
                    "role": "source-event",
                }
            ],
        )
        contract["implementation"]["objects"].extend([history, tag])
        contract["tag_policies"].append(topology)
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


class EffectiveConfigurationGuardrailsTestFixture(unittest.TestCase):
    pass


__all__ = [
    "AdapterExecutionError",
    "ContractValidationError",
    "EffectiveConfigurationGuardrailsTestFixture",
    "FakeAdapter",
    "Path",
    "RateLimitError",
    "TargetAdapterRegistry",
    "approve_mutations",
    "atomic_write",
    "capabilities",
    "create_from_contract",
    "deepcopy",
    "execute_ready_operations",
    "load_document",
    "render_markdown",
    "separate_page_view_contract",
    "settings_contract",
    "tempfile",
    "valid_web_contract",
    "validate_document",
    "with_complete_baselines",
]
