from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def strict_contract() -> dict:
    name = "GA4 - Event - café ☕"
    return {
        "schema_version": "4.0",
        "route": "analytics",
        "scope": {"included": ["REQ-☕"], "reference_only": [], "excluded": []},
        "requirements": [
            {
                "id": "REQ-☕",
                "authority": {"grade": "approved-input", "locator": "Plan / café ☕"},
            }
        ],
        "implementation": {
            "workspace": {
                "account_id": "1",
                "container_id": "2",
                "id": "3",
                "container_type": "web",
            },
            "objects": [
                {
                    "action": "create",
                    "object_type": "tag",
                    "name": name,
                    "justification": "Implements REQ-☕",
                    "evidence": [
                        "approved-input",
                        "official-current",
                        "container-confirmed",
                    ],
                }
            ],
        },
        "evidence": [
            {
                "grade": "official-current",
                "locator": "Official café ☕ documentation",
                "url": "https://developers.google.com/example",
                "title": "Official café ☕ documentation",
                "access_date": "2026-07-30",
            },
            {"grade": "container-confirmed", "locator": "Workspace café ☕"},
        ],
        "external_dependencies": [],
    }


class CliJsonOutputTest(unittest.TestCase):
    def run_cli(self, script: str, *arguments: str) -> tuple[int, dict]:
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "cp1252"
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / script), *arguments],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        output = result.stdout.decode("ascii")
        return result.returncode, json.loads(output)

    @staticmethod
    def write_json(path: Path, value: object) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def test_configuration_validator_preserves_schema_exit_code_under_cp1252(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            contract = strict_contract()
            contract["implementation"]["objects"].append(
                deepcopy(contract["implementation"]["objects"][0])
            )
            self.write_json(path, contract)

            returncode, report = self.run_cli(
                "validate_configuration_contract.py",
                "--contract",
                str(path),
            )

        self.assertEqual(returncode, 2)
        self.assertFalse(report["pass"])
        self.assertIn("café ☕", report["error"])

    def test_conformance_comparator_preserves_difference_exit_code_under_cp1252(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            approved_path = root / "approved.json"
            candidate_path = root / "candidate.json"
            approved = {
                "scope": {"included": ["REQ-☕"]},
                "requirements": [{"id": "REQ-☕", "event_name": "café"}],
            }
            candidate = deepcopy(approved)
            candidate["requirements"][0]["event_name"] = "thé ☕"
            self.write_json(approved_path, approved)
            self.write_json(candidate_path, candidate)

            returncode, report = self.run_cli(
                "validate_contract_conformance.py",
                "--approved",
                str(approved_path),
                "--candidate",
                str(candidate_path),
            )

        self.assertEqual(returncode, 1)
        self.assertFalse(report["pass"])
        self.assertEqual(report["requirement_mismatches"][0]["id"], "REQ-☕")

    def test_object_graph_comparator_preserves_difference_exit_code_under_cp1252(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected_path = root / "expected.json"
            saved_path = root / "saved.json"
            expected = {
                "objects": [
                    {
                        "object_type": "tag",
                        "name": "Café ☕",
                        "parameter": [{"type": "template", "key": "eventName", "value": "café"}],
                    }
                ]
            }
            saved = deepcopy(expected)
            saved["objects"][0]["parameter"][0]["value"] = "thé"
            self.write_json(expected_path, expected)
            self.write_json(saved_path, saved)

            returncode, report = self.run_cli(
                "diff_object_graph.py",
                "--expected",
                str(expected_path),
                "--saved",
                str(saved_path),
            )

        self.assertEqual(returncode, 1)
        self.assertFalse(report["pass"])
        self.assertEqual(report["object_differences"][0]["identity"], "tag::Café ☕")


if __name__ == "__main__":
    unittest.main()
