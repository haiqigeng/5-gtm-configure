"""Destination namespaces retain approval and bind to the correct native surface."""

from copy import deepcopy

import pytest
from gtm_configure.comparison.conformance import compare
from gtm_configure.contract import validate_document
from gtm_configure.core.schemas import field_collections, validator
from gtm_configure.domain.fields import materialize_payload_mappings
from gtm_configure.intake.request import compile_request
from gtm_configure.runtime.state import create_from_contract
from gtm_configure.runtime.verification import (
    build_verification_comparison,
    expected_graph,
    validate_verification_comparison,
)
from support.adapters import CurrentAdapterRuntimeTestFixture, FakeAdapter, capabilities
from support.contracts import approve_mutations
from support.identity import user_id_contract
from support.input_and_execution import compact


def test_field_namespaces_have_one_schema_owner():
    scopes = {model["payload_scope"] for model in field_collections().values()} - {None}
    assert scopes == set(validator("common").schema["$defs"]["payloadScope"]["enum"])


def test_configuration_identity_reaches_saved_native_verification():
    contract = user_id_contract()
    validate_document(contract)
    assert compare(contract, deepcopy(contract))["pass"]
    adapter = FakeAdapter()
    run, _ = CurrentAdapterRuntimeTestFixture()._execute(
        contract, {"web-main": (adapter, capabilities("tag", "trigger", "variable"), None)}
    )
    assert all(row["state"] == "verified" for row in run["object_changes"])
    assert len(adapter.mutations) == 4
    mapping = next(m for m in run["payload_mappings"] if m["destination_field"] == "user_id")
    assert mapping["field_scope"] == "configuration"
    assert mapping["source"] == "account.opaque_id"
    assert mapping["native_binding"]["field"] == "user_id"


@pytest.mark.parametrize(
    "failure",
    [
        "wrong_namespace",
        "wrong_source",
        "transformed_source",
        "missing_lifecycle",
        "wrong_lifecycle",
        "route_source",
    ],
)
def test_identity_preserves_namespace_source_and_lifecycle(failure):
    contract = user_id_contract()
    tag = contract["implementation"]["objects"][0]
    variable = contract["implementation"]["objects"][-1]
    route = contract["first_party_data_routes"][0]
    if failure == "wrong_namespace":
        tag["intended"]["parameter"][0]["key"] = "eventSettingsTable"
    elif failure == "wrong_source":
        variable["intended"]["parameter"][0]["value"] = "account.unapproved_id"
    elif failure == "transformed_source":
        variable["intended"]["formatValue"] = {"caseConversionType": "LOWERCASE"}
    elif failure == "missing_lifecycle":
        del route["identity_lifecycle"]
    elif failure == "wrong_lifecycle":
        route["identity_lifecycle"]["cleared"] = "string-null"
    else:
        route["fields"][0]["source"] = "account.unapproved_id"
    approve_mutations(contract)
    with pytest.raises(ValueError):
        validate_document(contract)


def test_unknown_destination_cannot_be_marked_mapped():
    contract = user_id_contract()
    requirement = contract["requirements"][0]
    requirement["unresolved_fields"] = {
        "vendor_id": deepcopy(requirement["configuration_fields"]["user_id"])
    }
    requirement["unresolved_fields"]["vendor_id"]["destination"] = "other"
    mapping = next(
        m for m in materialize_payload_mappings(contract) if m["field_scope"] == "unresolved"
    )
    assert mapping["status"] == "blocked"
    binding = deepcopy(contract["implementation"]["field_bindings"][-1])
    binding.update(field_scope="unresolved", destination_field="vendor_id")
    contract["implementation"]["field_bindings"].append(binding)
    with pytest.raises(ValueError, match="unresolved destinations"):
        materialize_payload_mappings(contract)


@pytest.mark.parametrize("mutation", ["unknown_key", "empty", "scope_mismatch", "unknown_route"])
def test_conformance_validates_both_semantic_projections(mutation):
    contract = user_id_contract()
    candidate = deepcopy(contract)
    if mutation == "unknown_key":
        candidate["requirements"][0]["evnt_name"] = "page_view"
    elif mutation == "empty":
        candidate["requirements"] = []
        candidate["scope"]["included"] = []
    elif mutation == "unknown_route":
        candidate["route"] = "unreviewed"
    else:
        candidate["scope"]["included"] = ["missing"]
    with pytest.raises(ValueError):
        compare(candidate, candidate)


def test_saved_evidence_rejects_boolean_number_substitution():
    run = create_from_contract(user_id_contract(), run_id="TYPES", source_locator="synthetic")
    operation = run["object_changes"][0]
    comparison, saved = build_verification_comparison(operation, expected_graph(operation))
    comparison["pass"] = 1
    with pytest.raises(ValueError, match="not bound"):
        validate_verification_comparison(operation, comparison, saved)


def test_preparation_derives_configuration_binding_from_approved_source():
    contract = user_id_contract()
    binding = contract["implementation"]["field_bindings"].pop()
    contract["requirements"][0]["configuration_fields"]["user_id"]["missing_behavior"] = binding[
        "missing_behavior"
    ]
    prepared = compile_request(compact(contract))
    actual = next(
        row
        for row in prepared["implementation"]["field_bindings"]
        if row["field_scope"] == "configuration"
    )
    assert actual == binding


@pytest.mark.parametrize("name", ["user-id", "User_ID", "user_id "])
def test_configuration_native_names_match_approved_names_exactly(name):
    contract = user_id_contract()
    contract["implementation"]["objects"][0]["intended"]["parameter"][0]["list"][0]["map"][0][
        "value"
    ] = name
    approve_mutations(contract)
    with pytest.raises(ValueError, match="configuration field 'user_id' is absent"):
        validate_document(contract)


def test_configuration_binding_resolves_shared_settings_and_exact_local_override():
    contract = user_id_contract()
    objects = contract["implementation"]["objects"]
    owner = objects[0]
    shared = deepcopy(objects[-1])
    shared.update(
        name="Shared configuration", object_key="web-main::variable::Shared configuration"
    )
    table = owner["intended"]["parameter"].pop()
    shared["intended"] = {"type": "gtcs", "parameter": [table]}
    shared["depends_on"] = [objects[-1]["object_key"]]
    objects.append(shared)
    owner["depends_on"].append(shared["object_key"])
    owner["intended"]["parameter"].append(
        {"key": "configSettingsVariable", "type": "template", "value": "{{Shared configuration}}"}
    )
    approve_mutations(contract)
    validate_document(contract)
    override = deepcopy(table)
    override["list"][0]["map"][1]["value"] = "unapproved override"
    owner["intended"]["parameter"].append(override)
    approve_mutations(contract)
    with pytest.raises(ValueError, match="differs from gtm_resolution"):
        validate_document(contract)
