"""Native response semantics and template proof survive the persistence boundary."""

import hashlib

import pytest
from gtm_configure.adapters.mcp import unwrap
from gtm_configure.comparison.native import GraphError, compare_graphs
from gtm_configure.core.privacy import redact_for_persistence, scrub_sensitive_text, sensitive_paths
from gtm_configure.core.public_identifiers import (
    public_identifier_paths,
    validate_public_identifiers,
)
from gtm_configure.core.template_source import inspect_template_source
from gtm_configure.runtime.adapter_protocol import AdapterExecutionError, AmbiguousWriteError
from gtm_configure.runtime.verification import (
    build_pre_write_comparison,
    build_verification_comparison,
    expected_graph,
)


def template_operation(source):
    return {
        "operation_id": "template",
        "resource_family": "template",
        "target_id": "web",
        "container_type": "web",
        "object_key": "web::template::Équipe",
        "name": "Équipe",
        "action": "reuse",
        "intended": {"templateData": source},
        "public_identifiers": [
            {
                "classification": "inspected-template-source",
                "path": ["templateData"],
                "value_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                "source_url": "https://example.test/source",
                "reason": "Inspected exact template parameter metadata and fixtures",
            }
        ],
    }


def test_evidenced_defaults_are_shared_and_other_values_stay_strict():
    client = {"object_type": "client", "name": "GA4", "type": "gaaw_client", "priority": 0}
    saved = {key: value for key, value in client.items() if key != "priority"}
    assert compare_graphs({"objects": [client]}, {"objects": [saved]})["pass"]
    assert not compare_graphs({"objects": [{**client, "priority": 1}]}, {"objects": [saved]})[
        "pass"
    ]
    assert not compare_graphs({"objects": [{**client, "priority": False}]}, {"objects": [saved]})[
        "pass"
    ]
    tag = {"object_type": "tag", "target_id": "server", "name": "GA4", "type": "sgtmgaaw"}
    native = {
        **tag,
        "parameter": [{"type": "BOOLEAN", "key": "isMeasurementIdMandatory", "value": "false"}],
    }
    assert compare_graphs(
        {"objects": [tag]}, {"objects": [native]}, target_types={"server": "server"}
    )["pass"]
    for changed in (
        {**native, "type": "cvt_unknown"},
        {**native, "extra": False},
        {
            **native,
            "parameter": [{"type": "boolean", "key": "isMeasurementIdMandatory", "value": "true"}],
        },
    ):
        assert not compare_graphs(
            {"objects": [tag]}, {"objects": [changed]}, target_types={"server": "server"}
        )["pass"]
    assert not compare_graphs(
        {"objects": [tag]}, {"objects": [native]}, target_types={"server": "web"}
    )["pass"]
    duplicate = {**native, "parameter": native["parameter"] * 2}
    with pytest.raises(GraphError, match="duplicate"):
        compare_graphs(
            {"objects": [tag]}, {"objects": [duplicate]}, target_types={"server": "server"}
        )
    operation = {
        "operation_id": "ga4",
        "target_id": "server",
        "name": "GA4",
        "resource_family": "tag",
        "container_type": "server",
        "pre_change": tag,
    }
    assert build_pre_write_comparison(operation, native)[0]["pass"]
    assert native["parameter"][0]["type"] == "BOOLEAN"


def test_diagnostic_cause_is_independent_of_write_certainty():
    prose = 'Google API Error 400 - Unknown entity type (cvt_bad).\n"api_secret":"PRIVATE_VALUE"\nInspect installed INFO.id.'
    response = {"isError": True, "content": [{"type": "text", "text": prose}]}
    with pytest.raises(AmbiguousWriteError) as caught:
        unwrap(response, mutation=True)
    assert "Unknown entity type" in str(caught.value)
    assert "Inspect installed INFO.id" in str(caught.value)
    assert "PRIVATE_VALUE" not in str(caught.value)
    assert caught.value.code == "ambiguous_write"
    response = {"isError": True, "structuredContent": {"error": {"code": 400, "message": prose}}}
    with pytest.raises(AdapterExecutionError) as caught:
        unwrap(response, mutation=True)
    assert not isinstance(caught.value, AmbiguousWriteError)
    assert caught.value.code == "http_400"
    assert "Unknown entity type" in str(caught.value)


def test_template_fixture_context_requires_exact_review_and_keeps_operational_credentials_private():
    source = """___INFO___
{"id":"cvt_TEST","type":"TAG"}
___TEMPLATE_PARAMETERS___
[{"name":"collectionKey","displayName":"Public collection identifier","type":"TEXT"}]
___SANDBOXED_JS_FOR_WEB_TEMPLATE___
data.gtmOnSuccess();
___TESTS___
const mockData = {"collectionKey":"fixture-value"};
"""
    source = source.replace("collectionKey", "publicAPIKey")
    operation = template_operation(source)
    raw = expected_graph(operation)
    assert sensitive_paths(raw)
    paths = public_identifier_paths(raw, records=[operation])
    assert not sensitive_paths(raw, public_identifier_paths=paths)
    assert redact_for_persistence(raw, public_identifier_paths=paths) == raw
    assert inspect_template_source(source)["native_type"] == "cvt_TEST"
    altered = source.replace("fixture-value", "changed")
    assert sensitive_paths(expected_graph(template_operation(altered)))
    assert not public_identifier_paths(
        expected_graph(template_operation(altered)), records=[operation]
    )
    private = source.replace("fixture-value", "ghp_" + "A" * 32)
    private_operation = template_operation(private)
    retained = redact_for_persistence(
        expected_graph(private_operation),
        public_identifier_paths=public_identifier_paths(
            expected_graph(private_operation), records=[private_operation]
        ),
    )
    assert isinstance(retained["objects"][0]["templateData"], dict)
    assert "ghp_" not in str(retained)


def test_redacted_template_proof_is_full_content_and_rebuilds_from_persistence():
    source = '___INFO___\n{"id":"cvt_TEST","type":"TAG"}\n___WEB_PERMISSIONS___\n[]\n___SANDBOXED_JS_FOR_WEB_TEMPLATE___\nconst token = "private-value";\n___TESTS___\nassertThat(1);\n'
    operation = template_operation(source)
    comparison, safe_saved = build_verification_comparison(operation, expected_graph(operation))
    assert comparison["pass"]
    assert comparison["report"]["template_source_integrity"]["exact_bytes_equal"]
    assert not comparison["report"]["template_source_integrity"]["hidden_value_equality_claimed"]
    safe_operation = redact_for_persistence(
        operation, public_identifier_paths=public_identifier_paths(operation)
    )
    validate_public_identifiers(
        {"objects": [safe_operation], "official_sources": [{"url": "https://example.test/source"}]}
    )
    rebuilt, _ = build_verification_comparison(safe_operation, safe_saved)
    assert rebuilt == comparison
    for changed in (
        source.replace("assertThat(1)", "assertThat(2)"),
        source.replace("[]", '[{"read":true}]'),
        source.replace("cvt_TEST", "cvt_OTHER"),
    ):
        saved = expected_graph(operation)
        saved["objects"][0]["templateData"] = changed
        assert not build_verification_comparison(operation, saved)[0]["pass"]
    saved = expected_graph(operation)
    saved["objects"][0]["templateData"] = source.replace("\n", "\r\n").replace(
        '{"id":"cvt_TEST","type":"TAG"}', '{"type":"TAG", "id":"cvt_TEST"}'
    )
    canonical, _ = build_verification_comparison(operation, saved)
    assert canonical["pass"]
    assert not canonical["report"]["template_source_integrity"]["exact_bytes_equal"]
    assert canonical["report"]["template_source_integrity"]["canonical_source_equal"]
    for changed in (
        source + "___INFO___\n{}",
        source.replace('"id":"cvt_TEST"', '"id":"cvt_TEST","id":"cvt_BAD"'),
    ):
        with pytest.raises(ValueError):
            inspect_template_source(changed)


def test_known_sensitive_values_are_scrubbed_without_erasing_the_cause():
    message = "Unknown field; api_secret=PRIVATE_VALUE; endpoint rejected 400"
    sanitized = scrub_sensitive_text(message, {"OTHER_VALUE"})
    assert "PRIVATE_VALUE" not in sanitized
    assert "Unknown field" in sanitized
    assert "endpoint rejected 400" in sanitized


def test_native_parameter_table_keeps_scoped_field_shapes():
    source = """___INFO___
{"id":"cvt_TABLE","type":"TAG"}
___TEMPLATE_PARAMETERS___
[{"type":"GROUP","name":"settings","subParams":[{"type":"PARAM_TABLE","name":"regions","paramTableColumns":[{"param":{"type":"TEXT","name":"region"}},{"param":{"type":"SELECT","name":"status"}}]},{"type":"RADIO","name":"mode"},{"type":"CHECKBOX","name":"enabled"}]}]
___SANDBOXED_JS_FOR_WEB_TEMPLATE___
const rows = data.regions;
data.gtmOnSuccess();
___TESTS___
runCode({regions:[{region:"FR", status:"denied"}]});
"""
    proof = inspect_template_source(source)
    assert proof["parameter_types"] == {"regions": "list", "mode": "template", "enabled": "boolean"}
    unknown = source.replace('"type":"RADIO"', '"type":"FUTURE_WIDGET"')
    proof = inspect_template_source(unknown)
    assert proof["native_type"] == "cvt_TABLE"
    assert proof["parameter_types"]["mode"] is None
