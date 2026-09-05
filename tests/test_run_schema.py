from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from configuration_run import (  # noqa: E402
    FIRST_PARTY_FEATURES,
    OPERATION_STATES,
    RUN_PHASES,
    RUN_STATUSES,
    SCHEMA_VERSION,
    RunValidationError,
    create_from_contract,
    validate_document,
)
from run_model import ACTIONS, RESOURCE_FAMILIES  # noqa: E402

from tests.current_support import valid_pipeline_contract  # noqa: E402


def schema() -> dict:
    return json.loads(
        (ROOT / "schemas" / "configuration-run.schema.json").read_text(encoding="utf-8")
    )


class ConfigurationRunSchemaTest(unittest.TestCase):
    def test_schema_is_valid_draft_2020_12_and_accepts_current_run(self) -> None:
        value = schema()
        Draft202012Validator.check_schema(value)
        current = create_from_contract(
            valid_pipeline_contract(),
            run_id="RUN-SCHEMA",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        errors = list(Draft202012Validator(value).iter_errors(current))
        self.assertEqual(errors, [], "\n".join(error.message for error in errors))

    def test_schema_and_python_authority_enums_stay_in_sync(self) -> None:
        value = schema()
        properties = value["properties"]
        operation = value["$defs"]["operation"]["properties"]
        run = value["$defs"]["run"]["properties"]
        first_party = value["properties"]["first_party_data_routes"]["items"]["properties"]
        self.assertEqual(properties["schema_version"]["const"], SCHEMA_VERSION)
        self.assertEqual(set(operation["action"]["enum"]), ACTIONS)
        self.assertEqual(set(operation["resource_family"]["enum"]), RESOURCE_FAMILIES)
        self.assertEqual(set(operation["state"]["enum"]), OPERATION_STATES)
        self.assertEqual(set(run["phase"]["enum"]), RUN_PHASES)
        self.assertEqual(set(value["$defs"]["status"]["enum"]), RUN_STATUSES)
        self.assertEqual(set(first_party["feature"]["enum"]), FIRST_PARTY_FEATURES)

    def test_schema_and_python_reject_unknown_mutation_fields(self) -> None:
        document = create_from_contract(
            valid_pipeline_contract(),
            run_id="RUN-UNKNOWN",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        document["object_changes"][0]["unreviewed_mutation_flag"] = True
        errors = list(Draft202012Validator(schema()).iter_errors(document))
        self.assertTrue(any("Additional properties" in error.message for error in errors))
        with self.assertRaisesRegex(RunValidationError, "unexpected key"):
            validate_document(document)

    def test_schema_and_python_reject_pause_for_non_tag_objects(self) -> None:
        document = create_from_contract(
            valid_pipeline_contract(),
            run_id="RUN-PAUSE",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        operation = document["object_changes"][0]
        operation.update(
            {
                "action": "pause",
                "resource_family": "variable",
                "name": "DLV - test",
                "object_key": "web-main::variable::DLV - test",
                "pre_change": {"name": "DLV - test", "type": "v"},
            }
        )
        errors = list(Draft202012Validator(schema()).iter_errors(document))
        self.assertTrue(errors)
        with self.assertRaisesRegex(RunValidationError, "only for tag objects"):
            validate_document(document)


if __name__ == "__main__":
    unittest.main()
