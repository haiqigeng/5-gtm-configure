"""Current-run revisions preserve actual write lineage and exact verified intent."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from gtm_configure.core.validation import canonical_sha256
from gtm_configure.intake.request import compile_request
from gtm_configure.runtime.adapter_protocol import atomic_write
from gtm_configure.runtime.engine import (
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from gtm_configure.runtime.state import (
    checkpoint_operation,
    create_from_contract,
    load_document,
    revise_from_contract,
)
from gtm_configure.runtime.verification import build_verification_comparison, expected_graph
from support.adapters import FakeAdapter, capabilities
from support.contracts import approve_mutations, valid_pipeline_contract, with_complete_baselines
from support.enhanced_conversions import event_override_contract
from support.shared_settings import repeated_request
from support.transport_and_state import ads_transport_contract

ROOT = Path(__file__).resolve().parents[1]


def contract():
    request = json.loads((ROOT / "tests/fixtures/folder-request.json").read_text(encoding="utf-8"))
    request["objects"][0].update(action="create", name="Équipe", intended={"name": "Équipe"})
    for key in ("new_name", "pre_change", "object_id"):
        request["objects"][0].pop(key, None)
    return compile_request(request)


def revised_contract(original, *, family="folder"):
    request = deepcopy(original)
    objects = request.pop("implementation")["objects"]
    request["objects"] = objects
    request["requirements"].append(
        {
            "id": "SECOND",
            "authority": {"grade": "approved-input", "locator": "Approved second object"},
        }
    )
    request["scope"]["included"].append("SECOND")
    next(row for row in request["evidence"] if row["grade"] == "official-current")[
        "supports"
    ].append("SECOND")
    native = (
        {"name": "Deuxième"}
        if family == "folder"
        else {"type": "c", "parameter": [{"key": "value", "type": "template", "value": "approved"}]}
    )
    request["objects"].append(
        {
            "target_id": "web",
            "resource_family": family,
            "name": "Deuxième",
            "action": "create",
            "requirement_ids": ["SECOND"],
            "intended": native,
            "depends_on": [],
            "justification": "Approved independent addition",
            "evidence": ["approved-input"],
            "risk": "routine",
        }
    )
    return compile_request(request)


def execute(path, document, adapter):
    registry = TargetAdapterRegistry()
    target = document["run"]["targets"][0]
    adapter.bind_target(target)
    registry.register(target, adapter, capabilities("folder", "variable", "tag"))
    atomic_write(path, document)
    execute_ready_operations(path, registry)
    verify_idempotent_rerun(path, registry)
    return load_document(path)


def test_revision_preserves_verified_operation_and_saves_only_new_object(tmp_path):
    approved = contract()
    adapter = FakeAdapter()
    path = tmp_path / "run.json"
    completed = execute(
        path, create_from_contract(approved, run_id="LINEAGE", source_locator="approved"), adapter
    )
    verified = deepcopy(completed["object_changes"][0])
    receipt = deepcopy(completed["container_baselines"][0])
    revised = revise_from_contract(
        completed,
        revised_contract(approved),
        expected_fingerprint=canonical_sha256(completed),
        note="Approved remaining graph addition",
    )
    assert revised["run"]["id"] == "LINEAGE"
    assert revised["object_changes"][0] == verified
    assert revised["container_baselines"][0] == receipt
    assert (
        revised["run"]["revisions"][0]["previous_contract_fingerprint"]
        == completed["run"]["contract"]["fingerprint"]
    )
    final = execute(path, revised, adapter)
    assert len(adapter.mutations) == 2
    assert final["object_changes"][0] == verified
    assert final["run"]["status"] == "Configured"


def test_revision_new_family_captures_only_missing_family_and_keeps_original_receipt(tmp_path):
    approved = contract()
    adapter = FakeAdapter()
    path = tmp_path / "run.json"
    completed = execute(
        path, create_from_contract(approved, run_id="FAMILIES", source_locator="approved"), adapter
    )
    receipt = deepcopy(completed["container_baselines"][0]["capture_evidence"])
    revised = revise_from_contract(
        completed,
        revised_contract(approved, family="variable"),
        expected_fingerprint=canonical_sha256(completed),
        note="Approved new native family",
    )
    final = execute(path, revised, adapter)
    baseline = final["container_baselines"][0]
    assert baseline["capture_evidence"] == receipt
    assert baseline["supplemental_captures"]
    assert set(baseline["supplemental_captures"][0]["capture_evidence"]["resource_pagination"]) == {
        "variable"
    }
    assert len(adapter.mutations) == 2


def test_revision_rejects_stale_no_change_or_verified_source_change(tmp_path):
    approved = contract()
    completed = execute(
        tmp_path / "run.json",
        create_from_contract(approved, run_id="GUARDS", source_locator="approved"),
        FakeAdapter(),
    )
    fingerprint = canonical_sha256(completed)
    with pytest.raises(ValueError, match="changed since"):
        revise_from_contract(
            completed,
            revised_contract(approved),
            expected_fingerprint="sha256:" + "0" * 64,
            note="stale",
        )
    with pytest.raises(ValueError, match="approved change"):
        revise_from_contract(
            completed, approved, expected_fingerprint=fingerprint, note="unchanged"
        )
    changed = deepcopy(approved)
    changed["implementation"]["objects"][0]["intended"]["name"] = "Changed verified object"
    from support.contracts import approve_mutations

    with pytest.raises(ValueError, match="Verified operations"):
        revise_from_contract(
            completed,
            approve_mutations(changed),
            expected_fingerprint=fingerprint,
            note="change old intent",
        )


def test_revision_rejects_unreconciled_dispatched_write(tmp_path):
    approved = contract()
    run = create_from_contract(approved, run_id="UNSENT", source_locator="approved")
    from gtm_configure.runtime.state import checkpoint_operation
    from support.contracts import with_complete_baselines

    run = with_complete_baselines(run)
    run = checkpoint_operation(
        run,
        operation_id=run["object_changes"][0]["operation_id"],
        state="in_progress",
        note="dispatched",
    )
    with pytest.raises(ValueError, match="authoritative reconciliation"):
        revise_from_contract(
            run,
            revised_contract(approved),
            expected_fingerprint=canonical_sha256(run),
            note="unsafe",
        )


def verified_subset(approved, selected):
    run = with_complete_baselines(
        create_from_contract(approved, run_id="OWNERS", source_locator="Approved source")
    )
    operations = {row["operation_id"]: row for row in run["object_changes"]}
    selected_ids = {key for key, row in operations.items() if selected(row)}
    while True:
        expanded = selected_ids | {
            dependency for key in selected_ids for dependency in operations[key]["dependencies"]
        }
        if expanded == selected_ids:
            break
        selected_ids = expanded
    pending = set(selected_ids)
    while pending:
        key = next(
            key for key in sorted(pending) if not set(operations[key]["dependencies"]) & pending
        )
        comparison, saved = build_verification_comparison(
            operations[key], expected_graph(operations[key])
        )
        run = checkpoint_operation(
            run,
            operation_id=key,
            state="verified",
            note="Synthetic authoritative saved graph",
            comparison=comparison,
            saved=saved,
        )
        pending.remove(key)
    return run


def amend_tag_policy(approved):
    approved["tag_policies"][0]["pre_cmp_policy"] = "drop-unconsented-occurrence"


def amend_ads_route(approved):
    tag = approved["implementation"]["objects"][0]
    next(row for row in tag["intended"]["parameter"] if row["key"] == "conversionLabel")[
        "value"
    ] = "another-approved-label"
    approved["first_party_data_routes"][0]["consumer_bindings"][0]["field_review"] += (
        "; Approved remaining event override"
    )


def amend_first_party_proof(approved):
    approved["first_party_data_routes"][0]["consumer_bindings"][0]["field_review"] += (
        "; Changed verified consumer premise"
    )


def amend_receiver_flow(approved):
    approved["pipelines"][0]["field_flows"][0]["missing_behavior"] = (
        "Keep the documented standard page location when absent"
    )


@pytest.mark.parametrize(
    "base,selected,amendment",
    [
        (
            event_override_contract,
            lambda row: row["resource_family"] == "trigger" and "denied" not in row["name"],
            amend_tag_policy,
        ),
        (
            event_override_contract,
            lambda row: row.get("intended", {}).get("type") == "awec",
            amend_ads_route,
        ),
        (
            valid_pipeline_contract,
            lambda row: row["resource_family"] == "client",
            amend_receiver_flow,
        ),
    ],
    ids=[
        "verified-trigger-planned-policy",
        "verified-upd-planned-route",
        "verified-client-planned-fieldflow",
    ],
)
def test_revision_follows_semantic_owners_instead_of_verified_prerequisite_references(
    base, selected, amendment
):
    approved = base()
    current = verified_subset(approved, selected)
    original = deepcopy(current)
    changed = deepcopy(approved)
    amendment(changed)
    revised = revise_from_contract(
        current,
        approve_mutations(changed),
        expected_fingerprint=canonical_sha256(current),
        note="Approved remaining consumer correction",
    )
    assert current == original
    verified = {
        row["object_key"]: row for row in current["object_changes"] if row["state"] == "verified"
    }
    assert all(
        next(row for row in revised["object_changes"] if row["object_key"] == key) == row
        for key, row in verified.items()
    )
    assert revised["run"]["revisions"][-1]["changed_operation_keys"]
    assert not set(revised["run"]["revisions"][-1]["changed_operation_keys"]) & verified.keys()


@pytest.mark.parametrize(
    "base,selected,amendment",
    [
        (event_override_contract, lambda row: row["resource_family"] == "tag", amend_tag_policy),
        (
            event_override_contract,
            lambda row: row["resource_family"] == "tag",
            amend_first_party_proof,
        ),
        (
            valid_pipeline_contract,
            lambda row: row["resource_family"] == "tag" and row["target_id"] == "server-main",
            amend_receiver_flow,
        ),
    ],
    ids=["verified-tag-policy", "verified-first-party-route", "verified-receiver-fieldflow"],
)
def test_revision_protects_policies_and_field_proofs_owned_by_verified_consumers(
    base, selected, amendment
):
    approved = base()
    current = verified_subset(approved, selected)
    changed = deepcopy(approved)
    amendment(changed)
    with pytest.raises(ValueError, match="policies and field proofs"):
        revise_from_contract(
            current,
            approve_mutations(changed),
            expected_fingerprint=canonical_sha256(current),
            note="Rewriting verified owner proof",
        )


def test_revision_preserves_verified_prerequisite_authority():
    approved = event_override_contract()
    current = verified_subset(approved, lambda row: row.get("intended", {}).get("type") == "awec")
    changed = deepcopy(approved)
    changed["requirements"].append(
        {
            "id": "ANOTHER",
            "authority": {
                "grade": "approved-input",
                "locator": "A separately approved variable authority",
            },
        }
    )
    changed["scope"]["included"].append("ANOTHER")
    next(row for row in changed["evidence"] if row["grade"] == "official-current")[
        "supports"
    ].append("ANOTHER")
    next(
        row
        for row in changed["implementation"]["objects"]
        if row.get("intended", {}).get("type") == "awec"
    )["requirement_ids"].append("ANOTHER")
    amend_ads_route(changed)
    with pytest.raises(ValueError, match="intent and authority"):
        revise_from_contract(
            current,
            approve_mutations(changed),
            expected_fingerprint=canonical_sha256(current),
            note="Rewriting verified authority",
        )


def test_verified_shared_fields_leave_planned_event_semantics_amendable():
    approved = compile_request(repeated_request())
    current = verified_subset(approved, lambda row: row.get("intended", {}).get("type") == "gtes")
    changed = deepcopy(approved)
    requirement = next(row for row in changed["requirements"] if row["id"] == "REQ-EVENT-0")
    old_event = requirement["source_event"]
    new_event = "approved_remaining_event"
    requirement["source_event"] = requirement["event_name"] = new_event
    for row in changed["implementation"]["objects"]:
        if row["requirement_ids"] != [requirement["id"]]:
            continue
        if row["resource_family"] == "tag":
            next(item for item in row["intended"]["parameter"] if item["key"] == "eventName")[
                "value"
            ] = new_event
        if row["resource_family"] == "trigger":
            for condition in row["intended"].get("customEventFilter", []):
                next(item for item in condition["parameter"] if item["key"] == "arg1")["value"] = (
                    new_event
                )
    for policy in changed["consent_policies"]:
        policy["event_coverage"] = [
            new_event if event == old_event else event for event in policy["event_coverage"]
        ]
    revised = revise_from_contract(
        current,
        approve_mutations(changed),
        expected_fingerprint=canonical_sha256(current),
        note="Approved remaining event correction",
    )
    verified = {
        row["object_key"]: row for row in current["object_changes"] if row["state"] == "verified"
    }
    assert all(
        next(row for row in revised["object_changes"] if row["object_key"] == key) == row
        for key, row in verified.items()
    )
    assert not set(revised["run"]["revisions"][-1]["changed_operation_keys"]) & verified.keys()


def test_verified_shared_fields_protect_the_exact_approved_field_semantics():
    approved = compile_request(repeated_request())
    current = verified_subset(approved, lambda row: row.get("intended", {}).get("type") == "gtes")
    changed = deepcopy(approved)
    requirement = next(row for row in changed["requirements"] if row["id"] == "REQ-EVENT-0")
    requirement["parameters"]["context_0"]["nullable"] = False
    with pytest.raises(ValueError, match="policies and field proofs"):
        revise_from_contract(
            current,
            approve_mutations(changed),
            expected_fingerprint=canonical_sha256(current),
            note="Rewriting verified field semantics",
        )


def test_verified_server_matching_consumer_protects_its_first_party_source_semantics():
    approved = ads_transport_contract()
    current = verified_subset(approved, lambda row: row["name"] == "Ads conversion")
    changed = deepcopy(approved)
    changed["first_party_data_routes"][0]["fields"][0]["normalization"].append(
        "Approved upstream email trimming"
    )
    with pytest.raises(ValueError, match="policies and field proofs"):
        revise_from_contract(
            current,
            approve_mutations(changed),
            expected_fingerprint=canonical_sha256(current),
            note="Rewriting verified receiver source premise",
        )
