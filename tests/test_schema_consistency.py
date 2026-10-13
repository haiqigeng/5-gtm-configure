"""Guard shared declaration rules against contract/run schema drift."""

import json
import unittest
from pathlib import Path

from gtm_configure import contract
from gtm_configure.core import model
from gtm_configure.core.contract_validation import ContractValidationError
from gtm_configure.core.validation import RunValidationError
from gtm_configure.runtime.state import create_from_contract
from gtm_configure.runtime.validation import validate_document as validate_run
from support.contracts import valid_web_contract

ROOT = Path(__file__).resolve().parents[1]


class SharedSchemaTests(unittest.TestCase):
    def test_consent_enums_match_domain_rules(self):
        common = json.loads((ROOT / "schemas/common.schema.json").read_text(encoding="utf-8"))
        properties = common["$defs"]["consent"]["properties"]
        enums = {
            "consent_mode": model.CONSENT_MODES,
            "transport_behavior": model.TRANSPORT_BEHAVIORS,
            "signal_authority": model.CONSENT_SIGNAL_AUTHORITIES,
            "unknown_state_behavior": model.UNKNOWN_STATE_BEHAVIORS,
        }
        for field, expected in enums.items():
            self.assertEqual(
                set(
                    common["$defs"]["consentMode"]["enum"]
                    if field == "consent_mode"
                    else properties[field]["enum"]
                ),
                expected,
                field,
            )
        for field, expected in (
            ("web_enforcement", model.WEB_CONSENT_MECHANISMS),
            ("server_enforcement", model.SERVER_CONSENT_MECHANISMS),
        ):
            self.assertEqual(set(properties[field]["properties"]["mechanism"]["enum"]), expected)

    def test_unknown_consent_mechanism_rejected_in_both_phases(self):
        approved = valid_web_contract()
        run = create_from_contract(approved, run_id="schema-parity", source_locator="synthetic")
        for document, validate, error in (
            (approved, contract.validate_document, ContractValidationError),
            (run, validate_run, RunValidationError),
        ):
            with self.subTest(phase=document["schema_version"]):
                document["consent_topologies"][0]["web_enforcement"]["mechanism"] = (
                    "unreviewed-gate"
                )
                with self.assertRaisesRegex(error, "mechanism.*unreviewed-gate.*is not one of"):
                    validate(document)
