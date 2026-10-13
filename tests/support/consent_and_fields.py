from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fixtures.mcp_behavior_scenario import (  # noqa: E402
    PROFILE,
    FakeGtm,
    condition,
    param,
    request,
)
from gtm_configure.adapters.mcp import McpTargetAdapter  # noqa: E402
from gtm_configure.contract import validate_document
from gtm_configure.core.privacy import sensitive_findings
from gtm_configure.domain.consent import validate_convention
from gtm_configure.intake.request import compile_request
from gtm_configure.render import analyst_field_changes, render_markdown
from gtm_configure.runtime.adapter_protocol import atomic_write
from gtm_configure.runtime.engine import (
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from gtm_configure.runtime.state import (
    create_from_contract,
    load_document,  # noqa: E402
)

ROOT = Path(__file__).resolve().parents[2]


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


class UtilityCorrectionsFixture(unittest.TestCase):
    pass


__all__ = [
    "UtilityCorrectionsFixture",
    "additional_request",
    "analyst_field_changes",
    "compile_request",
    "condition",
    "execute",
    "firing_request",
    "param",
    "render_markdown",
    "request",
    "sensitive_findings",
    "ungated_request",
    "validate_convention",
    "validate_document",
]
