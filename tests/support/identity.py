"""Synthetic approved Google configuration identity and its native DLV."""

from copy import deepcopy

from support.contracts import approve_mutations, valid_web_contract


def user_id_contract():
    contract = valid_web_contract()
    requirement = contract["requirements"][0]
    owner = contract["implementation"]["objects"][0]
    authority = deepcopy(requirement["authority"])
    requirement["configuration_fields"] = {
        "user_id": {
            "name": "account_id",
            "scope": "user",
            "destination": "ga4_user_id",
            "source": "account.opaque_id",
            "source_shape": "scalar:string",
            "destination_shape": "scalar:string",
            "nullable": True,
            "provenance": authority,
            "source_authority": authority,
        }
    }
    variable = {
        "target_id": "web-main",
        "resource_family": "variable",
        "name": "DLV - Approved ID",
        "object_key": "web-main::variable::DLV - Approved ID",
        "action": "create",
        "requirement_ids": [requirement["id"]],
        "depends_on": [],
        "justification": "Synthetic approved identity source",
        "evidence": ["approved-input"],
        "risk": "routine",
        "intended": {
            "type": "v",
            "parameter": [
                {"key": "name", "type": "template", "value": "account.opaque_id"},
                {"key": "dataLayerVersion", "type": "integer", "value": "2"},
            ],
        },
    }
    contract["implementation"]["objects"].append(variable)
    owner["depends_on"].append(variable["object_key"])
    owner["intended"]["parameter"] = [
        {
            "key": "configSettingsTable",
            "type": "list",
            "list": [
                {
                    "type": "map",
                    "map": [
                        {"key": "parameter", "type": "template", "value": "user_id"},
                        {
                            "key": "parameterValue",
                            "type": "template",
                            "value": "{{DLV - Approved ID}}",
                        },
                    ],
                }
            ],
        }
    ]
    contract["implementation"]["field_bindings"].append(
        {
            "requirement_id": requirement["id"],
            "field_scope": "configuration",
            "destination_field": "user_id",
            "shape_compatibility": "compatible",
            "mapping_method": "direct-dlv",
            "gtm_resolution": "{{DLV - Approved ID}}",
            "template_field": "user_id",
            "missing_behavior": "omit before authentication; JavaScript null at logout; replace on account switch",
            "status": "mapped",
            "owner_object_key": owner["object_key"],
        }
    )
    contract["first_party_data_routes"] = [
        {
            "requirement_id": requirement["id"],
            "feature": "ga4-user-id",
            "destination_field": "user_id",
            "consumer_object_keys": [owner["object_key"]],
            "consumer_bindings": [
                {
                    "object_key": owner["object_key"],
                    "product": "ga4",
                    "evidence": ["Synthetic native review"],
                }
            ],
            "source_priority": "data-layer",
            "timing": "tag-wide",
            "hashing_owner": "not-applicable",
            "fields": [
                {
                    "name": "user_id",
                    "normalization": [],
                    "empty_behavior": "omit",
                }
            ],
            "consent_types": ["analytics_storage"],
            "external_dependency_ids": [],
            "evidence": ["Synthetic approved identity lifecycle"],
            "identity_lifecycle": {
                "initial": "omit",
                "authenticated": "set",
                "cleared": "javascript-null",
                "changed": "replace",
                "authority": authority,
            },
        }
    ]
    approve_mutations(contract)
    return contract
