"""Exercise exact native product ownership without treating syntax as runtime proof."""

from copy import deepcopy

import pytest
from gtm_configure.core.validation import RunValidationError
from gtm_configure.domain.first_party_data import (
    _validate_first_party_consumer_bindings,
    first_party_binding_value,
)
from gtm_configure.domain.template_bindings import validate_template_bindings


@pytest.mark.parametrize("family", ["tag", "variable", "client"])
def test_custom_consumer_families_share_the_installed_source_identity_and_field_invariant(family):
    source = '___INFO___\n{"id":"cvt_synthetic_source"}\n___TEMPLATE_PARAMETERS___\n[{"name":"path","type":"TEXT"}]\n'
    template = {
        "operation_id": "source",
        "object_key": "server::template::Synthetic",
        "resource_family": "template",
        "action": "reuse",
        "dependencies": [],
        "intended": {"templateData": source},
    }
    consumer = {
        "operation_id": "consumer",
        "object_key": "server::" + family + "::Synthetic",
        "resource_family": family,
        "action": "create",
        "dependencies": ["source"],
        "intended": {
            "type": "cvt_synthetic_source",
            "parameter": [{"key": "path", "type": "template", "value": "/approved-path"}],
        },
    }

    def reject(message):
        raise ValueError(message)

    validate_template_bindings([template, consumer], reject)
    for changed in [
        {"type": "cvt_different_source", "parameter": consumer["intended"]["parameter"]},
        {
            "type": "cvt_synthetic_source",
            "parameter": [{"key": "unreviewed", "type": "template", "value": "x"}],
        },
        {
            "type": "cvt_synthetic_source",
            "parameter": [{"key": "path", "type": "boolean", "value": "true"}],
        },
    ]:
        altered = {**consumer, "intended": changed}
        with pytest.raises(ValueError, match="matching|definition"):
            validate_template_bindings([template, altered], reject)


def table(name, field="user_data", value="{{Approved UPD}}"):
    return {
        "type": "list",
        "key": name,
        "list": [
            {
                "type": "map",
                "map": [
                    {"type": "template", "key": "parameter", "value": field},
                    {"type": "template", "key": "parameterValue", "value": value},
                ],
            }
        ],
    }


@pytest.mark.parametrize(
    "feature,tag_type,namespace",
    [
        ("google-ads-tag-wide-user-data", "googtag", "eventSettingsTable"),
        ("ga4-user-provided-data", "gaawe", "eventSettingsTable"),
        ("google-ads-server-user-data-transport", "gaawe", "eventSettingsTable"),
        ("google-ads-server-user-data-transport", "googtag", "configSettingsTable"),
        ("google-ads-server-user-provided-data-event", "gaawe", "eventSettingsTable"),
        ("google-ads-server-user-provided-data-event", "googtag", "configSettingsTable"),
    ],
)
def test_google_matching_binds_its_documented_native_namespace(feature, tag_type, namespace):
    route = {"feature": feature, "destination_field": "user_data"}
    target = {"type": tag_type, "parameter": [table(namespace)]}
    assert first_party_binding_value(route, target, "tag", "test") == (True, "{{Approved UPD}}")
    wrong = "configSettingsTable" if namespace == "eventSettingsTable" else "eventSettingsTable"
    target["parameter"] = [table(wrong)]
    assert first_party_binding_value(route, target, "tag", "test") == (False, None)
    target["parameter"] = []
    target["user_data"] = "{{Approved UPD}}"
    assert first_party_binding_value(route, target, "tag", "test") == (False, None)


def test_ga4_collection_and_ads_transport_share_shape_with_separate_feature_authority():
    collection = {"feature": "ga4-user-provided-data", "destination_field": "user_data"}
    transport = {
        "feature": "google-ads-server-user-data-transport",
        "destination_field": "user_data",
    }
    target = {"type": "gaawe", "parameter": [table("eventSettingsTable")]}
    assert first_party_binding_value(collection, target, "tag", "test") == (
        True,
        "{{Approved UPD}}",
    )
    assert first_party_binding_value(transport, target, "tag", "test") == (True, "{{Approved UPD}}")
    target["parameter"] = [
        {"type": "template", "key": "userDataVariable", "value": "{{Approved UPD}}"}
    ]
    assert first_party_binding_value(collection, target, "tag", "test") == (False, None)
    assert first_party_binding_value(transport, target, "tag", "test") == (False, None)


def test_ads_event_override_binds_saved_user_data_semantics_not_arbitrary_path():
    route = {
        "feature": "google-ads-enhanced-conversions",
        "destination_field": "user_data",
        "consumer_bindings": [
            {
                "object_key": "tag",
                "user_data_path": [
                    "parameter",
                    "eventSettingsTable",
                    "list",
                    0,
                    "map",
                    "parameterValue",
                    "value",
                ],
                "activation_paths": [],
                "field_review": "Sanitized saved awct shape; runtime unproved",
            }
        ],
    }
    target = {"type": "awct", "parameter": [table("eventSettingsTable")]}
    assert first_party_binding_value(route, target, "tag", "test") == (True, "{{Approved UPD}}")
    target["parameter"][0]["list"][0]["map"][0]["value"] = "conversionLabel"
    with pytest.raises(RunValidationError, match="must be user_data"):
        first_party_binding_value(route, target, "tag", "test")
    target["parameter"] = [
        {"type": "template", "key": "conversionLabel", "value": "{{Approved UPD}}"}
    ]
    route["consumer_bindings"][0]["user_data_path"] = ["parameter", "conversionLabel", "value"]
    with pytest.raises(RunValidationError, match="native user_data event cell"):
        first_party_binding_value(route, target, "tag", "test")


def test_sanctioned_user_data_event_parameter_is_unique():
    route = {"feature": "ga4-user-provided-data", "destination_field": "user_data"}
    selector = table("eventSettingsTable")
    target = {"type": "gaawe", "parameter": [selector, deepcopy(selector)]}
    with pytest.raises(RunValidationError, match="duplicate native field"):
        first_party_binding_value(route, target, "tag", "test")


def test_custom_matching_consumer_requires_its_exact_installed_source_dependency():
    source = '___INFO___\n{"id":"cvt_matching"}\n___TEMPLATE_PARAMETERS___\n[]\n'
    operations = {
        "tag": {
            "object_key": "tag",
            "object_type": "tag",
            "action": "create",
            "dependencies": ["template-op"],
        },
        "template": {
            "object_key": "template",
            "operation_id": "template-op",
            "object_type": "template",
            "action": "reuse",
            "intended": {"templateData": source},
        },
    }
    arguments = {
        "path": "test",
        "feature": "vendor-advanced-matching",
        "consumers": {"tag"},
        "consumer_targets": {"tag": {"type": "cvt_matching"}},
        "operations": operations,
    }
    bindings = [
        {"object_key": "tag", "product": "Synthetic matching", "evidence": ["Synthetic source"]}
    ]
    _validate_first_party_consumer_bindings(bindings, **arguments)
    operations["tag"]["dependencies"] = []
    with pytest.raises(RunValidationError, match="installed template source dependency"):
        _validate_first_party_consumer_bindings(bindings, **arguments)
    operations["tag"]["dependencies"] = ["template-op"]
    operations["template"]["intended"]["templateData"] = source.replace("cvt_matching", "cvt_other")
    with pytest.raises(RunValidationError, match="matching the consumer native type"):
        _validate_first_party_consumer_bindings(bindings, **arguments)
