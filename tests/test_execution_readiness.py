"""Field ownership, shared dependency demand and transitive execution blockers."""

from copy import deepcopy

import pytest
from gtm_configure.render import render_markdown
from gtm_configure.runtime.readiness import operation_readiness
from gtm_configure.runtime.state import checkpoint_operation, create_from_contract, inspect_document
from support.adapters import CurrentAdapterRuntimeTestFixture, FakeAdapter, capabilities
from support.contracts import approve_mutations, with_complete_baselines
from support.identity import user_id_contract


def blocked_contract():
    contract = user_id_contract()
    requirement = contract["requirements"][0]
    requirement["unresolved_fields"] = {
        "destination_pending": deepcopy(requirement["configuration_fields"]["user_id"])
    }
    requirement["unresolved_fields"]["destination_pending"]["destination"] = "other"
    return contract


def test_unknown_destination_blocks_actual_writes_and_manual_checkpoints():
    contract = blocked_contract()
    adapter = FakeAdapter()
    run, _ = CurrentAdapterRuntimeTestFixture()._execute(
        contract, {"web-main": (adapter, capabilities("tag", "trigger", "variable"), None)}
    )
    assert adapter.mutations == []
    inspection = inspect_document(run)
    assert inspection["ready_operations"] == []
    assert all(
        any("unresolved::destination_pending" in reason for reason in reasons)
        for reasons in inspection["blocked_operations"].values()
    )
    with pytest.raises(ValueError, match="resolved fields"):
        checkpoint_operation(
            run,
            operation_id=run["object_changes"][-1]["operation_id"],
            state="in_progress",
            note="synthetic",
        )


def test_preflight_reports_unknown_workspace_state():
    run = create_from_contract(user_id_contract(), run_id="PREVIEW", source_locator="synthetic")
    assert "not inspected" in render_markdown(run)
    assert "not inspected" not in render_markdown(with_complete_baselines(run))


def test_unresolved_requirement_does_not_block_independent_operations():
    contract = blocked_contract()
    independent = {"id": "ORG", "authority": deepcopy(contract["requirements"][0]["authority"])}
    contract["scope"]["included"].append("ORG")
    contract["requirements"].append(independent)
    next(row for row in contract["evidence"] if row["grade"] == "official-current")[
        "supports"
    ].append("ORG")
    folder = {
        "target_id": "web-main",
        "resource_family": "folder",
        "name": "Independent folder",
        "object_key": "web-main::folder::Independent folder",
        "action": "create",
        "requirement_ids": ["ORG"],
        "depends_on": [],
        "justification": "Approved independent folder",
        "evidence": ["approved-input"],
        "risk": "routine",
        "intended": {"name": "Independent folder"},
    }
    contract["implementation"]["objects"].append(folder)
    approve_mutations(contract)
    adapter = FakeAdapter()
    run, _ = CurrentAdapterRuntimeTestFixture()._execute(
        contract,
        {"web-main": (adapter, capabilities("tag", "trigger", "variable", "folder"), None)},
    )
    assert len(adapter.mutations) == 1
    assert (
        next(row for row in run["object_changes"] if row["resource_family"] == "folder")["state"]
        == "verified"
    )
    assert all(
        row["state"] == "planned"
        for row in run["object_changes"]
        if row["resource_family"] != "folder"
    )


def shared_google_graph(*, owner=None, state="planned"):
    def operation(key, family, requirements, dependencies):
        return {
            "operation_id": key,
            "object_key": key,
            "target_id": "web",
            "resource_family": family,
            "requirement_ids": requirements,
            "dependencies": dependencies,
            "state": "planned",
            "action": "create",
            "intended": {},
        }

    operations = [
        operation("CMP", "variable", ["A", "B"], []),
        operation("GOOGLE", "tag", ["A", "B"], ["CMP"]),
        operation("A", "tag", ["A"], ["GOOGLE"]),
        operation("B", "tag", ["B"], ["GOOGLE"]),
    ]
    operations[0]["state"] = state
    mapping = {
        "requirement_id": "A",
        "field_scope": "unresolved",
        "destination_field": "pending",
        "status": "blocked",
    }
    if owner:
        mapping["native_binding"] = {"object_key": owner, "field": "pending"}
    return {
        "object_changes": operations,
        "payload_mappings": [mapping],
        "pipelines": [],
        "container_baselines": [{"target_id": "web", "complete": True}],
    }


def test_shared_google_tag_is_dependency_of_both_event_consumers():
    graph = shared_google_graph()
    result = operation_readiness(graph)
    assert not result["CMP"]["blocked"] and not result["CMP"]["waiting"]
    assert result["GOOGLE"]["waiting"] == ["CMP"]
    assert result["A"]["blocked"] and not result["A"]["waiting"]
    assert result["B"]["waiting"] == ["GOOGLE"]
    graph["object_changes"].reverse()
    assert operation_readiness(graph) == result


def test_shared_field_owner_blocks_all_consumers_with_origin():
    result = operation_readiness(shared_google_graph(owner="GOOGLE"))
    assert result["GOOGLE"]["blocked"]
    assert any(
        "GOOGLE:" in reason and "unresolved::pending" in reason for reason in result["B"]["blocked"]
    )
    assert not result["B"]["waiting"]


@pytest.mark.parametrize("state", ["failed", "uncertain", "skipped"])
def test_transitive_dependency_failures_are_blocked_not_waiting(state):
    result = operation_readiness(shared_google_graph(state=state))
    assert any("CMP:" in reason and state in reason for reason in result["B"]["blocked"])
    assert not result["B"]["waiting"]


def test_pipeline_field_blockers_follow_requirement_consumers():
    graph = shared_google_graph()
    graph["payload_mappings"] = []
    graph["pipelines"] = [
        {
            "field_flows": [
                {"requirement_ids": ["A"], "destination_field": "lead_type", "status": "blocked"}
            ]
        }
    ]
    result = operation_readiness(graph)
    assert any("pipeline field lead_type" in reason for reason in result["A"]["blocked"])
    assert not result["B"]["blocked"]


@pytest.mark.parametrize("tag_type", ["googtag", "gaawc"])
def test_native_configuration_namespace_owns_unbound_fields(tag_type):
    graph = shared_google_graph()
    graph["object_changes"][1]["intended"]["type"] = tag_type
    for operation in graph["object_changes"][2:]:
        operation["intended"]["type"] = "gaawe"
    graph["payload_mappings"][0]["field_scope"] = "configuration"
    result = operation_readiness(graph)
    assert result["GOOGLE"]["blocked"]
    assert any("GOOGLE:" in reason for reason in result["B"]["blocked"])
    assert not result["B"]["waiting"]
    graph["payload_mappings"][0]["field_scope"] = "event-parameter"
    result = operation_readiness(graph)
    assert not result["GOOGLE"]["blocked"]
    assert not result["B"]["blocked"]
    assert result["A"]["blocked"]
