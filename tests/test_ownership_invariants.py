"""Observable phase parity, closed declarations and lossless input routing."""

from copy import deepcopy

import pytest
from gtm_configure.contract import validate_document as validate_contract
from gtm_configure.core.schemas import definition_validator
from gtm_configure.core.validation import canonical_sha256
from gtm_configure.domain.context import ConfigurationGraph
from gtm_configure.domain.fields import materialize_payload_mappings
from gtm_configure.intake.ga4 import HandoffError, normalized_approved_semantics
from gtm_configure.runtime.state import create_from_contract
from gtm_configure.runtime.validation import validate_document as validate_run
from support.contracts import valid_pipeline_contract, valid_web_contract


def plan_with(destination, scope):
    return {
        "schema_version": "6.0.0",
        "events": [
            {
                "event_name": "sign_up",
                "classification": "official",
                "trigger": "Success",
                "journey_ids": ["signup"],
                "data_layer": {"push": {"event": "sign_up"}},
                "parameters": [
                    {
                        "name": "identity" if destination == "ga4_user_id" else "method",
                        "scope": scope,
                        "type": "string",
                        "nullable": True,
                        "requirement": "optional",
                        "data_layer_path": "account.method",
                        "destination": destination,
                    }
                ],
            }
        ],
    }


@pytest.mark.parametrize(
    "destination,scope,collection",
    [
        ("ga4_event_parameter", "event", "parameters"),
        ("ga4_item_parameter", "item", "item_parameters"),
        ("ga4_user_property", "user", "user_properties"),
        ("implementation_only", "implementation", "implementation_fields"),
    ],
)
def test_import_routes_by_destination(destination, scope, collection):
    plan = plan_with(destination, scope)
    before = deepcopy(plan)
    requirement = normalized_approved_semantics({}, plan)["requirements"][0]
    field = requirement[collection]["method"]
    assert field["destination"] == destination
    assert field["scope"] == scope
    assert field["nullable"] is True
    assert field["source"] == "account.method"
    assert plan == before


@pytest.mark.parametrize("destination,scope", [("ga4_user_id", "user"), ("other", "event")])
def test_destination_is_preserved_without_reclassification(destination, scope):
    plan = plan_with(destination, scope)
    before = deepcopy(plan)
    result = normalized_approved_semantics({}, plan)
    collection, name = (
        ("configuration_fields", "user_id")
        if destination == "ga4_user_id"
        else ("unresolved_fields", "method")
    )
    assert result["requirements"][0][collection][name]["destination"] == destination
    assert plan == before


def test_destination_scope_conflict_is_explicit():
    with pytest.raises(HandoffError, match="requires scope 'user'"):
        normalized_approved_semantics({}, plan_with("ga4_user_property", "event"))


@pytest.mark.parametrize("field", ["evnt_name", "event_nam", "unapproved_instruction"])
def test_requirement_unknown_keys_rejected(field):
    contract = valid_web_contract()
    contract["requirements"][0][field] = "page_view"
    with pytest.raises(ValueError, match=field):
        validate_contract(contract)


@pytest.mark.parametrize(
    "definition",
    [
        "collectionField",
        "tagPolicy",
        "pageViewDecision",
        "firstPartyRoute",
        "firstPartyConsumer",
        "firstPartyField",
        "fieldBinding",
        "payloadMapping",
        "officialSource",
        "externalDependency",
    ],
)
def test_shared_records_reject_unknown_keys(definition):
    errors = list(definition_validator(definition).iter_errors({"lenght": 5}))
    assert any(error.validator == "additionalProperties" for error in errors)


def test_product_specific_consent_reaches_run_validation():
    contract = valid_web_contract()
    contract["consent_policies"][0]["consent_mode"] = "product-specific"
    topology = contract["tag_policies"][0]
    topology["blocking_event_scope"] = None
    contract["consent_policies"][0]["web_enforcement"] = {"mechanism": "product-native"}
    for operation in contract["implementation"]["objects"]:
        if operation["object_key"] == topology["tag_object_key"]:
            operation["intended"]["blockingTriggerId"] = []
    from support.contracts import approve_mutations

    approve_mutations(contract)
    validate_contract(contract)
    run = create_from_contract(contract, run_id="product-specific", source_locator="synthetic")
    validate_run(run)


def test_graph_edges_and_identity_are_equivalent_across_phases():
    contract = valid_pipeline_contract()
    run = create_from_contract(contract, run_id="graph-parity", source_locator="synthetic")
    before = ConfigurationGraph.from_contract(contract, materialize_payload_mappings(contract))
    after = ConfigurationGraph.from_run(run)

    def edges(graph):
        return {
            (item["object_key"], graph.by_id[dep]["object_key"])
            for item in graph.operations
            for dep in item["dependencies"]
        }

    assert edges(before) == edges(after)
    assert before.target_types == after.target_types
    assert set(before.by_key) == set(after.by_key)


def test_canonical_hash_is_typed_and_order_independent():
    assert canonical_sha256({"é": [1, True], "a": 2}) == canonical_sha256({"a": 2, "é": [1, True]})
    assert canonical_sha256(True) != canonical_sha256(1)
    assert canonical_sha256(1) != canonical_sha256(1.0)
    assert canonical_sha256({}).startswith("sha256:")
    with pytest.raises(ValueError, match="fingerprinted safely"):
        canonical_sha256(float("nan"))
