"""Exercise native consolidation and persistence; no browser execution is implied."""

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from gtm_configure.contract import validate_document
from gtm_configure.core.validation import canonical_sha256
from gtm_configure.domain.actions import mutation_approval_projection
from gtm_configure.domain.native import effective_collection_fields
from gtm_configure.domain.shared_settings import consolidate_event_settings
from gtm_configure.intake.request import compile_request
from gtm_configure.runtime.adapter_protocol import atomic_write
from gtm_configure.runtime.engine import TargetAdapterRegistry, execute_ready_operations
from gtm_configure.runtime.state import create_from_contract, load_document
from support.adapters import FakeAdapter, capabilities
from support.shared_settings import parameter, repeated_request


def event_tags(request):
    return [item for item in request["objects"] if item["intended"].get("type") == "gaawe"]


def effective_payloads(objects):
    variables = {
        item["name"]: item["intended"] for item in objects if item["resource_family"] == "variable"
    }
    return {
        item["object_key"]: effective_collection_fields(
            item["intended"], variables, namespace="event-parameter"
        )
        for item in objects
        if item["intended"].get("type") == "gaawe"
    }


def test_six_identical_fields_across_twenty_three_consumers_have_one_native_owner():
    request = repeated_request(23)
    before = effective_payloads(request["objects"])
    added = consolidate_event_settings(request, request["objects"])
    assert len(added) == 1
    assert len(added[0]["intended"]["parameter"][0]["list"]) == 6
    assert len(added[0]["requirement_ids"]) == 23
    assert effective_payloads(request["objects"]) == before
    assert all(
        not any(row["key"] == "eventSettingsTable" for row in tag["intended"]["parameter"])
        for tag in event_tags(request)
    )
    assert consolidate_event_settings(request, request["objects"]) == []


@pytest.mark.parametrize(
    "difference",
    [
        "source",
        "missing",
        "shape",
        "destination",
        "consent",
        "lifecycle",
        "gate",
        "firing",
        "event",
    ],
)
def test_incompatible_consumers_retain_their_own_fields(difference):
    request = repeated_request(2, 1)
    tag = event_tags(request)[1]
    field = request["requirements"][-1]["parameters"]["context_0"]
    policy = request["tag_policies"][-1]
    if difference == "source":
        field["source"] = "different.context"
    elif difference == "missing":
        field["missing_behavior"] = "block when absent"
    elif difference == "shape":
        field["source_shape"] = field["destination_shape"] = "scalar:number"
    elif difference == "destination":
        tag["intended"]["parameter"][0]["value"] = "G-OTHER"
    elif difference == "consent":
        policy["consent_policy_id"] = "OTHER"
        request["consent_policies"].append({"consent_policy_id": "OTHER"})
    elif difference == "lifecycle":
        policy["lifecycle_role"] = "cmp-lifecycle"
    elif difference == "gate":
        tag["intended"]["blockingTriggerId"] = []
    elif difference == "firing":
        tag["intended"]["tagFiringOption"] = "oncePerLoad"
    else:
        request["requirements"][-1]["source_event"] = "another_event"
    before = deepcopy(request["objects"])
    assert consolidate_event_settings(request, request["objects"]) == []
    assert request["objects"] == before


def test_shared_intersection_preserves_local_scope_and_existing_override():
    request = repeated_request(3, 2)
    tags = event_tags(request)
    tags[-1]["intended"]["parameter"][-1]["list"].pop()
    request["requirements"][-1]["parameters"].pop("context_1")
    before = effective_payloads(request["objects"])
    added = consolidate_event_settings(request, request["objects"])
    assert len(added) == 1
    assert len(added[0]["intended"]["parameter"][0]["list"]) == 1
    assert effective_payloads(request["objects"]) == before
    assert all(
        any(row["key"] == "eventSettingsTable" for row in tag["intended"]["parameter"])
        for tag in tags[:2]
    )
    # One native settings reference limits overlapping subgroup consolidation.
    assert consolidate_event_settings(request, request["objects"]) == []


def test_compiler_consolidates_before_approval_and_new_runs_reuse_saved_generated_graph():
    request = repeated_request(3)
    original = canonical_sha256(request)
    compiled = compile_request(request)
    assert canonical_sha256(request) == original
    shared = next(
        item
        for item in compiled["implementation"]["objects"]
        if item["intended"].get("type") == "gtes"
    )
    assert shared["approval"]["payload_sha256"] == canonical_sha256(
        mutation_approval_projection(shared)
    )
    assert all(
        binding["owner_object_key"] == shared["object_key"]
        for binding in compiled["implementation"]["field_bindings"]
        if binding["requirement_id"].startswith("REQ-EVENT")
    )
    adapter = FakeAdapter()
    target = compiled["targets"][0]
    adapter.bind_target(target)
    registry = TargetAdapterRegistry()
    registry.register(target, adapter, capabilities("tag", "trigger", "variable"))
    with TemporaryDirectory() as directory:
        path = Path(directory) / "run.json"
        atomic_write(
            path,
            create_from_contract(
                compiled, run_id="first", source_locator="Synthetic approved source"
            ),
        )
        execute_ready_operations(path, registry)
        assert all(item["state"] == "verified" for item in load_document(path)["object_changes"])
        count = len(adapter.mutations)
        inventory = {
            "schema_version": "gtm-preparation-inventory@1",
            "purpose": "preparation-only",
            "targets": [
                {
                    **target,
                    "objects": [
                        raw for graph in adapter.saved.values() for raw in graph["objects"]
                    ],
                    "pagination": {
                        family: {"exhausted": True, "pages_read": 1}
                        for family in ("tag", "trigger", "variable")
                    },
                }
            ],
        }
        fresh = compile_request(request, inventory=inventory)
        assert fresh == compiled
        atomic_write(
            path,
            create_from_contract(fresh, run_id="fresh", source_locator="Synthetic approved source"),
        )
        execute_ready_operations(path, registry)
        assert all(item["state"] == "verified" for item in load_document(path)["object_changes"])
        assert len(adapter.mutations) == count


def test_authored_inheritance_and_local_override_keep_their_native_owner():
    request = repeated_request(2, 1)
    tags = event_tags(request)
    tags[0]["intended"]["parameter"].append(parameter("eventSettingsVariable", "{{Authored}}"))
    before = deepcopy(request["objects"])
    assert consolidate_event_settings(request, request["objects"]) == []
    assert request["objects"] == before


def test_missing_shared_native_field_blocks_the_owned_fields_before_execution():
    from support.contracts import approve_mutations

    compiled = compile_request(repeated_request(3))
    shared = next(
        item
        for item in compiled["implementation"]["objects"]
        if item["intended"].get("type") == "gtes"
    )
    shared["intended"]["parameter"][0]["list"].pop()
    with pytest.raises(ValueError, match="native|mapping|field"):
        validate_document(approve_mutations(compiled))
