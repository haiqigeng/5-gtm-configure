"""Native source identity and parameter capability are proved before custom writes."""

from copy import deepcopy

import pytest
from gtm_configure.core.privacy import redact_for_persistence
from gtm_configure.domain.template_bindings import validate_template_bindings


def source():
    return '___INFO___\n{"id":"cvt_source_type"}\n___TEMPLATE_PARAMETERS___\n[{"name":"enabled","type":"CHECKBOX"},{"name":"value","type":"TEXT"}]\n___SANDBOXED_JS_FOR_WEB_TEMPLATE___\nreturn data.enabled;\n'


def graph(family="tag"):
    return [
        {
            "operation_id": "TEMPLATE",
            "object_key": "web::template::Installed",
            "target_id": "web",
            "resource_family": "template",
            "action": "reuse",
            "dependencies": [],
            "intended": {"templateId": "9999", "templateData": source()},
        },
        {
            "operation_id": "CONSUMER",
            "object_key": f"web::{family}::Consumer",
            "target_id": "web",
            "resource_family": family,
            "action": "create",
            "dependencies": ["TEMPLATE"],
            "intended": {
                "type": "cvt_source_type",
                "parameter": [
                    {"key": "enabled", "type": "BOOLEAN", "value": "true"},
                    {"key": "value", "type": "template", "value": "approved"},
                ],
            },
        },
    ]


def fail(message):
    raise ValueError(message)


@pytest.mark.parametrize("family", ["tag", "variable", "client"])
def test_native_source_id_and_parameters_establish_each_configurable_consumer(family):
    operations = graph(family)
    before = deepcopy(operations)
    validate_template_bindings(operations, fail)
    assert operations == before
    operations[1]["intended"]["type"] = "cvt_9999"
    with pytest.raises(ValueError, match="INFO.id"):
        validate_template_bindings(operations, fail)


@pytest.mark.parametrize("change", ["field", "shape", "source"])
def test_missing_template_capability_blocks_write_even_if_native_readback_could_echo_it(change):
    operations = graph()
    if change == "field":
        operations[1]["intended"]["parameter"][0]["key"] = "invented"
    elif change == "shape":
        operations[1]["intended"]["parameter"][0]["type"] = "template"
    else:
        operations[1]["dependencies"] = []
    with pytest.raises(ValueError, match="inspected template definition|matching installed source"):
        validate_template_bindings(operations, fail)


def test_persisted_source_inspection_retains_capability_when_sensitive_body_is_hidden():
    operations = graph()
    operations[0]["intended"]["templateData"] += (
        '\nconst token="SYNTHETIC_SECRET_VALUE_7f3a9c1e5b2d8f4a6c0e";\n'
    )
    safe = redact_for_persistence(operations)
    validate_template_bindings(safe, fail, persisted=True)
    with pytest.raises(ValueError, match="installed source"):
        validate_template_bindings(safe, fail)
