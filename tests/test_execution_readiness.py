"""Execution and checkpoints share the requirement-level readiness frontier."""

from copy import deepcopy

import pytest
from gtm_configure.render import render_markdown
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
