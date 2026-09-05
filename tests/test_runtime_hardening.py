from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from import_ga4_tracking_plan_handoff import (  # noqa: E402
    HandoffError,
    normalized_approved_semantics,
    verify_delivery,
)
from strict_json import StrictJsonError, load_json, loads_strict  # noqa: E402


def valid_plan() -> dict:
    return {
        "schema_version": "1.0.0",
        "future_metadata": {"producer": "accepted without reinterpretation"},
        "events": [
            {
                "event_name": "generate_lead",
                "classification": "official",
                "journey_ids": ["lead_form"],
                "measurement_opportunity_ids": ["lead_submission"],
                "trigger": "After the confirmed form success",
                "data_layer": {"clear": [], "push": {"event": "generate_lead"}},
                "parameters": [
                    {
                        "name": "method",
                        "scope": "event",
                        "type": "string",
                        "requirement": "required",
                        "data_layer_path": "event_data.method",
                        "destination": "ga4_event_parameter",
                        "future_metadata": "retained upstream",
                    }
                ],
                "future_metadata": {"reviewed": True},
            }
        ],
    }


class RuntimeHardeningTest(unittest.TestCase):
    def test_strict_json_accepts_bom_and_rejects_ambiguous_or_non_finite_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input.json"
            path.write_bytes(b'\xef\xbb\xbf{"event": "purchase"}')
            self.assertEqual(load_json(path), {"event": "purchase"})

        for raw, message in (
            ('{"event": "a", "event": "b"}', "duplicate JSON key"),
            ('{"value": NaN}', "non-finite JSON number"),
            ('{"value": Infinity}', "non-finite JSON number"),
        ):
            with self.subTest(raw=raw), self.assertRaisesRegex(StrictJsonError, message):
                loads_strict(raw)

        deeply_nested = "[" * 258 + "0" + "]" * 258
        with self.assertRaisesRegex(StrictJsonError, "nesting") as raised:
            loads_strict(deeply_nested)
        self.assertEqual(raised.exception.error_code, "json_depth")

    def test_run_cli_exposes_targeted_json_input_error_codes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = []
            missing = root / "missing.json"
            cases.append((missing, "io_error"))
            invalid_encoding = root / "encoding.json"
            invalid_encoding.write_bytes(b'{"value": \xff}')
            cases.append((invalid_encoding, "invalid_encoding"))
            deep = root / "deep.json"
            deep.write_text("[" * 258 + "0" + "]" * 258, encoding="utf-8")
            cases.append((deep, "json_depth"))

            for path, expected_code in cases:
                with self.subTest(path=path.name):
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(ROOT / "scripts" / "configuration_run.py"),
                            "validate",
                            "--run",
                            str(path),
                        ],
                        cwd=ROOT,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(json.loads(result.stdout)["error_code"], expected_code)

    def test_tracking_plan_importer_is_strict_on_records_but_forward_compatible(self) -> None:
        plan = valid_plan()
        handoff = {
            "skill": {"version": "3.0.0"},
            "plan": {"canonical_sha256": "a" * 64},
            "approval": {"state": "approved"},
        }
        normalized = normalized_approved_semantics(handoff, plan)
        requirement = normalized["requirements"][0]
        self.assertEqual(requirement["event_name"], "generate_lead")
        self.assertEqual(
            requirement["parameters"]["event::method"]["source"],
            "event_data.method",
        )

        malformed = deepcopy(plan)
        malformed["events"][0]["parameters"] = ["not-an-object"]
        with self.assertRaisesRegex(HandoffError, r"parameters\[0\] must be an object"):
            normalized_approved_semantics(handoff, malformed)

    def test_delivery_inventory_rejects_duplicate_roles_and_wrong_byte_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(valid_plan()), encoding="utf-8")
            digest = hashlib.sha256(plan_path.read_bytes()).hexdigest()
            artifact = {
                "path": "plan.json",
                "role": "canonical_tracking_plan",
                "bytes": plan_path.stat().st_size,
                "sha256": digest,
            }
            handoff = {
                "handoff_version": "1.1.0",
                "skill": {"name": "ga4-tracking-plan", "version": "3.0.0"},
                "approval": {"state": "approved"},
                "plan": {"canonical_sha256": digest},
                "artifacts": [artifact],
            }
            handoff_path = root / "handoff.json"
            handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
            _, imported = verify_delivery(root)
            self.assertEqual(imported["events"][0]["event_name"], "generate_lead")

            handoff["artifacts"] = [artifact, {**artifact, "path": "plan.json"}]
            handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
            with self.assertRaisesRegex(HandoffError, "Duplicate handoff artifact role"):
                verify_delivery(root)

            handoff["artifacts"] = [{**artifact, "bytes": artifact["bytes"] + 1}]
            handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
            with self.assertRaisesRegex(HandoffError, "byte-count mismatch"):
                verify_delivery(root)


if __name__ == "__main__":
    unittest.main()
