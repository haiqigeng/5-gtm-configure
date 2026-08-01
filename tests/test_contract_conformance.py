from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_contract_conformance.py"
sys.path.insert(0, str(ROOT / "scripts"))

from import_ga4_tracking_plan_handoff import (  # noqa: E402
    HandoffError,
    normalized_approved_semantics,
    verify_delivery,
)


def contract(*requirements: dict, scope: dict | None = None) -> dict:
    return {
        "scope": scope
        or {
            "included": [requirement["id"] for requirement in requirements],
            "reference_only": [],
            "excluded": {},
        },
        "requirements": list(requirements),
        "infrastructure": {"workspace": "ignored by collection comparison"},
    }


def requirement(
    requirement_id: str,
    event_name: str = "account_created",
    parameters: dict | None = None,
) -> dict:
    return {
        "id": requirement_id,
        "destination": "GA4",
        "event_name": event_name,
        "source_event": event_name,
        "business_moment": "confirmed success",
        "parameters": parameters or {"method": {"source": "event.method"}},
    }


class ContractConformanceTest(unittest.TestCase):
    def run_comparator(self, approved: dict, candidate: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            approved_path = root / "approved.json"
            candidate_path = root / "candidate.json"
            approved_path.write_text(json.dumps(approved), encoding="utf-8")
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            return subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--approved",
                    str(approved_path),
                    "--candidate",
                    str(candidate_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_exact_contract_passes_independent_of_mapping_requirement_or_scope_order(self) -> None:
        approved = contract(
            requirement(
                "REQ-1",
                parameters={
                    "method": {"source": "event.method"},
                    "plan_type": {"source": "event.plan_type"},
                },
            ),
            requirement("REQ-2", event_name="newsletter_subscription"),
        )
        candidate = contract(
            requirement("REQ-2", event_name="newsletter_subscription"),
            requirement(
                "REQ-1",
                parameters={
                    "plan_type": {"source": "event.plan_type"},
                    "method": {"source": "event.method"},
                },
            ),
            scope={
                "excluded": {},
                "reference_only": [],
                "included": ["REQ-2", "REQ-1"],
            },
        )
        candidate["infrastructure"] = {
            "workspace": "different technical workspace metadata is allowed",
            "tag_type": "adapter-specific",
        }
        result = self.run_comparator(approved, candidate)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["pass"])
        self.assertEqual(report["requirement_mismatches"], [])

    def test_nested_requirement_array_order_is_semantic(self) -> None:
        approved_requirement = requirement("REQ-1")
        approved_requirement["transformation_steps"] = ["normalize", "hash"]
        candidate_requirement = requirement("REQ-1")
        candidate_requirement["transformation_steps"] = ["hash", "normalize"]

        result = self.run_comparator(
            contract(approved_requirement),
            contract(candidate_requirement),
        )

        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        differences = report["requirement_mismatches"][0]["differences"]
        self.assertTrue(any(item["path"].endswith("transformation_steps") for item in differences))

    def test_extra_parameter_and_event_substitution_fail(self) -> None:
        approved = contract(requirement("REQ-1"))
        candidate = contract(
            requirement(
                "REQ-1",
                event_name="sign_up",
                parameters={
                    "method": {"source": "event.method"},
                    "lead_type": {"literal": "account"},
                },
            )
        )
        result = self.run_comparator(approved, candidate)
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertFalse(report["pass"])
        differences = report["requirement_mismatches"][0]["differences"]
        self.assertTrue(any(item["path"].endswith("event_name") for item in differences))
        self.assertTrue(any(item["path"].endswith("lead_type") for item in differences))

    def test_scope_missing_and_extra_requirements_fail(self) -> None:
        approved = contract(requirement("REQ-1"), requirement("REQ-2"))
        candidate = contract(requirement("REQ-1"), requirement("REQ-3"))
        result = self.run_comparator(approved, candidate)
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual(report["missing_requirements"], ["REQ-2"])
        self.assertEqual(report["extra_requirements"], ["REQ-3"])
        self.assertTrue(report["scope_mismatches"])

    def test_invalid_contract_returns_schema_error(self) -> None:
        result = self.run_comparator(
            {"scope": {}, "requirements": [{"event_name": "missing_id"}]},
            contract(requirement("REQ-1")),
        )
        self.assertEqual(result.returncode, 2)
        report = json.loads(result.stdout)
        self.assertFalse(report["pass"])
        self.assertIn("non-empty string id", report["error"])

    def test_ga4_delivery_import_preserves_approved_semantics_and_hashes(self) -> None:
        plan = {
            "events": [
                {
                    "event_name": "generate_lead",
                    "classification": "official",
                    "journey_ids": ["lead_generation"],
                    "measurement_opportunity_ids": ["lead_success"],
                    "trigger": "Confirmed form success.",
                    "data_layer": {"clear": ["event_data"]},
                    "parameters": [
                        {
                            "name": "form_name",
                            "scope": "event",
                            "type": "string",
                            "requirement": "required",
                            "data_layer_path": "event_data.form_name",
                            "destination": "ga4_event_parameter",
                        }
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as raw:
            delivery = Path(raw)
            plan_path = delivery / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            digest = hashlib.sha256(plan_path.read_bytes()).hexdigest()
            handoff = {
                "handoff_version": "1.0.0",
                "skill": {"name": "ga4-tracking-plan", "version": "2.5.0"},
                "approval": {"state": "approved", "approved_by": "Analyst"},
                "plan": {"canonical_sha256": digest},
                "artifacts": [
                    {
                        "path": "plan.json",
                        "role": "canonical_tracking_plan",
                        "sha256": digest,
                    }
                ],
            }
            (delivery / "handoff.json").write_text(json.dumps(handoff), encoding="utf-8")
            verified_handoff, verified_plan = verify_delivery(delivery)
            imported = normalized_approved_semantics(verified_handoff, verified_plan)
            self.assertEqual(imported["scope"]["included"], ["GA4::001::generate_lead"])
            requirement = imported["requirements"][0]
            self.assertEqual(requirement["measurement_opportunity_ids"], ["lead_success"])
            self.assertEqual(
                requirement["parameters"]["event::form_name"]["source"],
                "event_data.form_name",
            )
            imported_field = requirement["parameters"]["event::form_name"]
            self.assertEqual(imported_field["source_shape"], "string")
            self.assertEqual(imported_field["destination_shape"], "string")
            self.assertEqual(imported_field["source_authority"]["grade"], "approved-input")
            plan_path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(HandoffError, "hash mismatch"):
                verify_delivery(delivery)


if __name__ == "__main__":
    unittest.main()
