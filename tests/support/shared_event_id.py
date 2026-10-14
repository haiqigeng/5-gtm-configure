from __future__ import annotations

import unittest
from pathlib import Path

from gtm_configure.contract import ContractValidationError, validate_document
from gtm_configure.domain.deduplication import validate_generated_event_ids  # noqa: E402

from support.contracts import (  # noqa: E402
    add_nonpurchase_dual_dedup,
    approve_mutations,
    valid_pipeline_contract,
)

ROOT = Path(__file__).resolve().parents[2]


def generated_contract():
    """Synthetic reviewed template premise, not a real GTM template export."""
    contract = add_nonpurchase_dual_dedup(valid_pipeline_contract())
    dedup = contract["dedup_contracts"][0]
    template_key = "web-main::template::Reviewed occurrence ID"
    template = {
        "target_id": "web-main",
        "resource_family": "template",
        "name": "Reviewed occurrence ID",
        "object_key": template_key,
        "object_id": "456",
        "action": "reuse",
        "requirement_ids": ["REQ-ATC"],
        "depends_on": [],
        "justification": "Reuse the inspected occurrence-scoped generator",
        "evidence": ["container-confirmed"],
        "risk": "routine",
        "intended": {
            "templateData": '___INFO___\n{"id":"cvt_123_456"}\n___TEMPLATE_PARAMETERS___\n[]\n___SANDBOXED_JS_FOR_WEB_TEMPLATE___\nreturn "synthetic occurrence id";\n'
        },
    }
    contract["implementation"]["objects"].append(template)
    variable = next(
        item
        for item in contract["implementation"]["objects"]
        if item["object_key"] == dedup["source_variable_key"]
    )
    variable["intended"] = {"type": "cvt_123_456"}
    variable["depends_on"] = [template_key]
    dedup["source_type"] = "generated-event-id"
    dedup["generation"] = {
        "template_object_key": template_key,
        "review_locator": "Synthetic source and permission review; same-event repeated reads stable",
        "consumer_bindings": [
            {"object_key": key, "field_path": ["event_id"]}
            for key in dedup["browser_consumer_keys"] + dedup["transporter_consumer_keys"]
        ],
    }
    return approve_mutations(contract)


class SharedEventIdTestFixture(unittest.TestCase):
    def assert_generation_rejected(self, contract, message, *, contract_message=None):
        with self.assertRaisesRegex(ContractValidationError, contract_message or message):
            validate_document(approve_mutations(contract))
        # Run-phase checks must reject the same native graph before any mutation.
        errors = []
        validate_generated_event_ids(
            contract["dedup_contracts"],
            contract["implementation"]["objects"],
            contract["tag_policies"],
            {item["target_id"]: item["container_type"] for item in contract["targets"]},
            errors.append,
        )
        self.assertTrue(any(message in error for error in errors), errors)
