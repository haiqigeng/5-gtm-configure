from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
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
    checkpoint_operation,
    upgrade_document,
    validate_document,
)
from validate_configuration_contract import (  # noqa: E402
    ACTIONS,
    OBJECT_RESOURCE_FAMILIES,
)

from tests.test_configuration_run import ready_run_document  # noqa: E402


def schema() -> dict:
    return json.loads(
        (ROOT / "schemas" / "configuration-run.schema.json").read_text(encoding="utf-8")
    )


class ConfigurationRunSchemaTest(unittest.TestCase):
    def test_schema_is_valid_draft_2020_12_and_accepts_current_run(self) -> None:
        value = schema()
        Draft202012Validator.check_schema(value)
        errors = list(Draft202012Validator(value).iter_errors(ready_run_document()))
        self.assertEqual(errors, [], "\n".join(error.message for error in errors))

    def test_schema_and_python_authority_enums_stay_in_sync(self) -> None:
        value = schema()
        properties = value["properties"]
        operation = properties["object_changes"]["items"]["properties"]
        run = properties["run"]["properties"]
        first_party = properties["first_party_data_routes"]["items"]["properties"]
        self.assertEqual(properties["schema_version"]["const"], SCHEMA_VERSION)
        self.assertEqual(set(operation["action"]["enum"]), ACTIONS)
        self.assertEqual(set(operation["object_type"]["enum"]), OBJECT_RESOURCE_FAMILIES)
        self.assertEqual(set(operation["state"]["enum"]), OPERATION_STATES)
        self.assertEqual(set(run["phase"]["enum"]), RUN_PHASES)
        self.assertEqual(set(run["status"]["enum"]), RUN_STATUSES)
        self.assertEqual(set(first_party["feature"]["enum"]), FIRST_PARTY_FEATURES)

    def test_schema_and_python_reject_unknown_mutation_fields(self) -> None:
        document = ready_run_document()
        document["object_changes"][0]["unreviewed_mutation_flag"] = True
        errors = list(Draft202012Validator(schema()).iter_errors(document))
        self.assertTrue(any("Additional properties" in error.message for error in errors))
        with self.assertRaisesRegex(RunValidationError, "unexpected key"):
            validate_document(document)

    def test_schema_and_python_reject_pause_for_non_tag_objects(self) -> None:
        document = ready_run_document()
        operation = document["object_changes"][0]
        operation.update(
            {
                "action": "pause",
                "object_type": "variable",
                "name": "DLV - test",
                "object_key": "variable::DLV - test",
                "pre_change": {"name": "DLV - test", "type": "v"},
            }
        )
        errors = list(Draft202012Validator(schema()).iter_errors(document))
        self.assertTrue(errors)
        with self.assertRaisesRegex(RunValidationError, "only for tag objects"):
            validate_document(document)

    def test_safe_legacy_run_upgrades_before_mutation(self) -> None:
        document = ready_run_document()
        document["schema_version"] = "2.0"
        document["idempotency"].pop("evidence")
        self.assertEqual(validate_document(document)["schema_version"], "2.0")
        upgraded = upgrade_document(deepcopy(document))
        self.assertEqual(upgraded["schema_version"], "2.1")
        checkpointed = checkpoint_operation(
            deepcopy(document),
            operation_id="OP-001",
            state="in_progress",
            note="Safe legacy run upgraded before the new write.",
        )
        self.assertEqual(checkpointed["schema_version"], "2.1")

    def test_legacy_delta_history_without_pre_write_proof_is_not_upgraded(self) -> None:
        document = ready_run_document()
        operation = document["object_changes"][0]
        operation.update(
            {
                "action": "update",
                "pre_change": deepcopy(operation["intended"]),
                "state": "in_progress",
                "journal": [
                    {
                        "state": "in_progress",
                        "at": "2026-08-01T10:01:00Z",
                        "note": "Legacy mutation started without a v2.1 drift checkpoint.",
                    }
                ],
            }
        )
        document["run"]["phase"] = "mutation"
        document["schema_version"] = "2.0"
        document["idempotency"].pop("evidence")
        validate_document(document)
        with self.assertRaisesRegex(RunValidationError, "lacks pre-write drift evidence"):
            upgrade_document(document)


if __name__ == "__main__":
    unittest.main()
