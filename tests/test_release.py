"""Offline release regression suite. No credentials, network, or live GTM writes."""

import json
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
SKILL = ROOT.parent
FIXTURES = ROOT / "fixtures"
sys.path.insert(0, str(SKILL / "scripts"))
from gtm_configure.comparison.conformance import compare
from gtm_configure.comparison.native import differences
from gtm_configure.contract import validate_document as validate_contract
from gtm_configure.core.json_io import loads_strict
from gtm_configure.core.validation import canonical_sha256
from gtm_configure.domain.fields import _field_mappings
from gtm_configure.domain.native import supports_native_mapping
from gtm_configure.intake.ga4 import normalized_approved_semantics
from gtm_configure.intake.request import compile_request
from gtm_configure.runtime.engine import (
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from gtm_configure.runtime.state import create_from_contract, load_document
from gtm_configure.runtime.validation import validate_document as validate_run
from gtm_configure.runtime.verification import materialization_fingerprints


@pytest.fixture
def compact_request():
    value = json.loads((FIXTURES / "folder-request.json").read_text())
    for row in value["evidence"]:
        if row["grade"] == "official-current":
            row["accessed_on"] = date.today().isoformat()
    return value


@pytest.fixture
def contract(compact_request):
    return compile_request(compact_request)


def test_structural_parity(contract):
    validate_contract(contract)
    mutations = [
        lambda c: c["targets"][0].update(surprise=True),
        lambda c: c["scope"].update(surprise=True),
        lambda c: c["implementation"]["objects"][0].update(surprise=True),
        lambda c: c["implementation"]["objects"][0].pop("risk"),
    ]
    for mutate in mutations:
        value = deepcopy(contract)
        mutate(value)
        with pytest.raises(ValueError):
            validate_contract(value)


def test_materialized_run(contract):
    value = create_from_contract(contract, run_id="OFFLINE", source_locator="synthetic fixture")
    validate_run(value)
    value["object_changes"][0]["surprise"] = True
    with pytest.raises(ValueError):
        validate_run(value)


def test_scoped_intake():
    params = [
        ("event", "lead_type", "lead_type", "ga4_event_parameter"),
        ("item", "item_id", "ecommerce.items[].item_id", "ga4_item_parameter"),
        ("user", "customer_type", "customer_type", "ga4_user_property"),
        ("implementation", "event_id", "event_id", "implementation_only"),
    ]
    plan = {
        "schema_version": "6.0.0",
        "events": [
            {
                "event_name": "generate_lead",
                "classification": "official",
                "trigger": "Confirmed success",
                "journey_ids": ["lead"],
                "data_layer": {"push": {"event": "generate_lead"}},
                "parameters": [
                    {
                        "scope": s,
                        "name": n,
                        "type": "string",
                        "data_layer_path": p,
                        "requirement": "required",
                        "destination": d,
                    }
                    for s, n, p, d in params
                ],
            }
        ],
    }
    semantic = normalized_approved_semantics({"skill": {}, "plan": {}}, plan)
    requirement = semantic["requirements"][0]
    mappings = _field_mappings(requirement)
    assert {(m["field_scope"], m["destination_field"]) for m in mappings} == {
        ("event-parameter", "lead_type"),
        ("item-parameter", "item_id"),
        ("user-property", "customer_type"),
    }
    assert requirement["implementation_fields"]["event_id"]["source"] == "event_id"
    assert all(m["destination_shape"] == "scalar:string" for m in mappings)
    assert supports_native_mapping(mappings[0], {"type": "gaawe"})


@pytest.mark.parametrize("shape", ["string", "scalar", "number", "scalar:unknown", ""])
def test_shape_cannot_bypass_native_proof(shape):
    with pytest.raises(ValueError):
        supports_native_mapping(
            {"field_scope": "event-parameter", "destination_shape": shape},
            {"type": "gaawe"},
        )


@pytest.mark.parametrize("a,b", [(True, 1), (False, 0), (1, 1.0)])
def test_type_strict_conformance(a, b):
    approved = {
        "scope": {"included": ["R"], "reference_only": [], "excluded": []},
        "requirements": [{"id": "R", "business_filters": [{"value": a}]}],
    }
    candidate = deepcopy(approved)
    candidate["requirements"][0]["business_filters"][0]["value"] = b
    assert differences(approved, candidate)
    assert not compare(approved, candidate)["pass"]


def test_organization_has_bounded_scope(compact_request):
    compact_request["route"] = "organization"
    compact_request["evidence"] = [
        e for e in compact_request["evidence"] if e["grade"] != "official-current"
    ]
    compile_request(compact_request)
    compact_request["objects"][0]["resource_family"] = "tag"
    with pytest.raises(ValueError):
        compile_request(compact_request)


def server_request():
    value = json.loads((FIXTURES / "client-request.json").read_text())
    for e in value["evidence"]:
        if e["grade"] == "official-current":
            e["accessed_on"] = date.today().isoformat()
    for item in value["objects"]:
        native = item["intended"]
        native.pop("claim_criteria", None)
        item["assertions"] = {
            "client_claim": {
                "description": "Native GA4 Client claims supported GA4 collection requests",
                "evidence_locator": "SYNTHETIC reviewed template fixture",
                "native_sha256": canonical_sha256(native),
            }
        }
    return value


def test_native_client_review_and_readback():
    compact_request = server_request()
    contract = compile_request(compact_request)
    run = create_from_contract(contract, run_id="NATIVE", source_locator="synthetic fixture")
    assert run["object_changes"][0]["assertions"] == compact_request["objects"][0]["assertions"]
    assert not differences(
        compact_request["objects"][0]["intended"], run["object_changes"][0]["intended"]
    )
    run["object_changes"][0]["intended"]["priority"] = 7
    run["run"]["materialization"]["section_fingerprints"] = materialization_fingerprints(run)
    with pytest.raises(ValueError, match="stale"):
        validate_run(run)


def test_client_metadata_rejected():
    compact_request = server_request()
    compact_request["objects"][0]["intended"]["claim_criteria"] = "invented root field"
    with pytest.raises(ValueError):
        compile_request(compact_request)


def test_save_readback_convergence(contract, tmp_path):
    run = create_from_contract(contract, run_id="OFFLINE", source_locator="synthetic fixture")
    path = tmp_path / "run.json"
    path.write_text(json.dumps(run))
    adapter = folder_adapter()
    registry = TargetAdapterRegistry()
    registry.register(
        run["run"]["targets"][0],
        adapter,
        {"folder": {"list": True, "get": True, "update": True}},
    )
    execute_ready_operations(path, registry)
    verify_idempotent_rerun(path, registry)
    assert load_document(path)["run"]["status"] == "Configured"
    assert len(adapter.calls) == 10
    execute_ready_operations(path, registry)
    assert len([c for c in adapter.calls if c["call"] == "mutate"]) == 1


def runtime_fixture(contract, tmp_path, adapter):
    run = create_from_contract(contract, run_id="RECOVERY", source_locator="synthetic fixture")
    path = tmp_path / "run.json"
    path.write_text(json.dumps(run))
    registry = TargetAdapterRegistry()
    registry.register(
        run["run"]["targets"][0],
        adapter,
        {"folder": {"list": True, "get": True, "update": True}},
    )
    return path, registry


def test_prewrite_drift_prevents_mutation(contract, tmp_path):
    adapter = folder_adapter()
    adapter.folder["name"] = "Concurrent edit"
    path, registry = runtime_fixture(contract, tmp_path, adapter)
    execute_ready_operations(path, registry)
    document = load_document(path)
    assert document["object_changes"][0]["state"] == "failed"
    assert not any(c["call"] == "mutate" for c in adapter.calls)


def test_ambiguous_write_resolved_without_repeat(contract, tmp_path):
    from gtm_configure.runtime.adapter_protocol import AmbiguousWriteError

    adapter = folder_adapter()
    native_mutate = adapter.mutate

    def uncertain(operation):
        native_mutate(operation)
        raise AmbiguousWriteError("Synthetic lost response")

    adapter.mutate = uncertain
    path, registry = runtime_fixture(contract, tmp_path, adapter)
    execute_ready_operations(path, registry)
    assert load_document(path)["object_changes"][0]["state"] == "verified"
    verify_idempotent_rerun(path, registry)
    execute_ready_operations(path, registry)
    assert load_document(path)["run"]["status"] == "Configured"
    assert sum(c["call"] == "mutate" for c in adapter.calls) == 1


def test_uncertain_mismatch_never_replays(contract, tmp_path):
    from gtm_configure.runtime.adapter_protocol import AmbiguousWriteError

    adapter = folder_adapter()

    def uncertain(operation):
        adapter.calls.append({"call": "mutate"})
        adapter.folder["name"] = "Unexpected saved name"
        raise AmbiguousWriteError("Synthetic lost response")

    adapter.mutate = uncertain
    path, registry = runtime_fixture(contract, tmp_path, adapter)
    execute_ready_operations(path, registry)
    assert load_document(path)["object_changes"][0]["state"] == "uncertain"
    execute_ready_operations(path, registry)
    assert sum(c["call"] == "mutate" for c in adapter.calls) == 1
    assert load_document(path)["run"]["status"] != "Configured"


def test_native_assertions_approval_bound(contract):
    from gtm_configure.domain.actions import mutation_approval_projection

    item = contract["implementation"]["objects"][0]
    before = canonical_sha256(mutation_approval_projection(item))
    item["assertions"] = {"client_claim": {"description": "test"}}
    assert canonical_sha256(mutation_approval_projection(item)) != before


def test_render_has_no_encoding_damage(contract):
    from gtm_configure.render import render_markdown

    text = render_markdown(
        create_from_contract(contract, run_id="RENDER", source_locator="synthetic fixture")
    )
    assert "â" not in text and "\ufffd" not in text


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'])
def test_strict_json(raw):
    with pytest.raises(ValueError):
        loads_strict(raw)


class FakeFolderAdapter:
    def __init__(self):
        self.folder = {
            "folderId": "7",
            "name": "Analytics old",
            "accountId": "101",
            "containerId": "202",
            "workspaceId": "303",
        }
        self.calls = []

    def identity(self):
        self.calls.append({"call": "identity"})
        return {
            "account_id": "101",
            "container_id": "202",
            "workspace_id": "303",
            "container_type": "web",
        }

    def read(self, operation):
        self.calls.append(
            {
                "call": "read",
                "folder_id": operation.get("object_id"),
                "name": self.folder["name"],
            }
        )
        assert operation["object_id"] == "7"
        return {"objects": [{**deepcopy(self.folder), "target_id": "web", "object_type": "folder"}]}

    def mutate(self, operation):
        self.calls.append(
            {
                "call": "mutate",
                "action": operation["action"],
                "folder_id": operation["object_id"],
            }
        )
        assert operation["action"] == "rename" and operation["object_id"] == "7"
        assert self.folder["name"] == "Analytics old"
        assert operation["new_name"] == "Analytics"
        self.folder["name"] = operation["new_name"]
        return None  # Force a separate authoritative readback.

    def list_resource_page(self, resource_family, cursor):
        self.calls.append(
            {"call": "list_resource_page", "family": resource_family, "cursor": cursor}
        )
        assert resource_family == "folder" and cursor is None
        return {"items": [deepcopy(self.folder)], "next_cursor": None}

    def list_workspace_changes_page(self, cursor):
        self.calls.append({"call": "list_workspace_changes_page", "cursor": cursor})
        assert cursor is None
        return {"items": [], "next_cursor": None}


def folder_adapter():
    return FakeFolderAdapter()


@pytest.mark.parametrize("fixture", ["web-request.json", "pipeline-request.json"])
def test_independent_native_scenarios(fixture):
    value = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
    for e in value["evidence"]:
        if e["grade"] == "official-current":
            e["accessed_on"] = date.today().isoformat()
    contract = compile_request(value)
    run = create_from_contract(
        contract, run_id="INDEPENDENT", source_locator="Synthetic inspected fixture"
    )
    validate_run(run)
    assert len(run["object_changes"]) == len(value["objects"])


def test_pipeline_event_rewrite_rejected_in_both_phases():
    value = json.loads((FIXTURES / "pipeline-request.json").read_text(encoding="utf-8"))
    for e in value["evidence"]:
        if e["grade"] == "official-current":
            e["accessed_on"] = date.today().isoformat()
    contract = compile_request(value)
    run = create_from_contract(
        contract, run_id="EVENT", source_locator="Synthetic inspected fixture"
    )
    for document in (contract, run):
        document["pipelines"][0]["event_flows"][0]["transported_event"] = "purchase"
        objects = document.get(
            "object_changes", document.get("implementation", {}).get("objects", [])
        )
        trigger = next(item for item in objects if item["resource_family"] == "trigger")
        for cell in trigger["intended"]["customEventFilter"][0]["parameter"]:
            if cell["key"] == "arg1":
                cell["value"] = "purchase"
        for topology in document["consent_topologies"]:
            topology["event_coverage"] = ["purchase"]
    with pytest.raises(ValueError, match="transported_event"):
        validate_contract(contract)
    run["run"]["materialization"]["section_fingerprints"] = materialization_fingerprints(run)
    with pytest.raises(ValueError):
        validate_run(run)


def test_pipeline_native_client_binding_required():
    value = json.loads((FIXTURES / "pipeline-request.json").read_text(encoding="utf-8"))
    for e in value["evidence"]:
        if e["grade"] == "official-current":
            e["accessed_on"] = date.today().isoformat()
    value["pipelines"][0]["claiming_client"]["claim_criteria"] = (
        "Unreviewed alternate request class"
    )
    with pytest.raises(ValueError, match="Client assertion"):
        compile_request(value)


def test_field_proof_rejects_wrong_native_source():
    value = json.loads((FIXTURES / "web-request.json").read_text(encoding="utf-8"))
    for e in value["evidence"]:
        if e["grade"] == "official-current":
            e["accessed_on"] = date.today().isoformat()
    variable = next(
        item
        for item in value["objects"]
        if item["resource_family"] == "variable"
        and item["intended"]["type"] == "v"
        and any(
            row.get("key") == "name" and row.get("value") == "lead_type"
            for row in item["intended"].get("parameter", [])
        )
    )
    parameter = next(row for row in variable["intended"]["parameter"] if row["key"] == "name")
    parameter["value"] = "unapproved_source"
    with pytest.raises(ValueError):
        compile_request(value)
