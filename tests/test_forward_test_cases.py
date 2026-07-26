from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "forward_test_cases.json"


class ForwardTestCaseCorpusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.cases = cls.payload["cases"]

    def test_corpus_is_raw_artifact_oriented_and_complete(self) -> None:
        self.assertEqual(self.payload["version"], 2)
        expected_ids = {
            "ga4-extra-field-and-pii",
            "multi-environment-routing",
            "pinterest-multi-item",
            "floodlight-sales",
            "onetrust-compound-consent",
            "high-impact-zone",
            "matomo-generic-analytics",
            "cross-domain-ownership",
            "empty-media-payload-template-first",
            "delta-shared-tag-change",
            "basic-google-consent-four-signals",
            "affiliate-basket",
            "browser-event-id-carveout",
        }
        self.assertEqual({case["id"] for case in self.cases}, expected_ids)
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["prompt"].startswith("Configure"))
                self.assertIsInstance(case["artifact"], dict)
                self.assertGreaterEqual(len(case["expected_controls"]), 3)


if __name__ == "__main__":
    unittest.main()
