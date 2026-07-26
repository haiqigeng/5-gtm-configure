from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from diff_object_graph import GraphError, compare_graphs, normalize_graph  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "golden_object_graphs.json"


class ObjectGraphDiffTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_all_golden_cases_match_expected_result(self) -> None:
        self.assertEqual(self.payload["version"], 2)
        for case in self.payload["cases"]:
            with self.subTest(case=case["id"]):
                result = compare_graphs(case["expected"], case["saved"])
                self.assertEqual(result["pass"], case["expected_pass"])
                if "expected_difference_contains" in case:
                    serialized = json.dumps(result, sort_keys=True)
                    self.assertIn(case["expected_difference_contains"], serialized)

    def test_root_server_metadata_is_ignored(self) -> None:
        graph = {
            "objects": [
                {
                    "object_type": "tag",
                    "name": "A",
                    "tagId": "1",
                    "fingerprint": "x",
                    "fields": {"fingerprint": "business-field"},
                }
            ]
        }
        normalized = normalize_graph(graph)["tag::A"]
        self.assertNotIn("tagId", normalized)
        self.assertNotIn("fingerprint", normalized)
        self.assertEqual(normalized["fields"]["fingerprint"], "business-field")

    def test_duplicate_semantic_identity_fails(self) -> None:
        graph = {
            "objects": [
                {"object_type": "tag", "name": "A"},
                {"object_type": "tag", "name": "A"},
            ]
        }
        with self.assertRaisesRegex(GraphError, "duplicate semantic object"):
            normalize_graph(graph)

    def test_raw_type_is_material_and_object_family_must_be_explicit(self) -> None:
        with self.assertRaisesRegex(GraphError, "object_type annotation"):
            normalize_graph({"objects": [{"type": "gaawe", "name": "A"}]})

        expected = {"objects": [{"object_type": "tag", "type": "gaawe", "name": "A"}]}
        saved = {"objects": [{"object_type": "tag", "type": "html", "name": "A"}]}
        report = compare_graphs(expected, saved)
        self.assertFalse(report["pass"])
        self.assertIn("type", str(report["object_differences"]))

    def test_returned_ids_become_semantic_cross_object_references(self) -> None:
        graph = {
            "objects": [
                {"object_type": "folder", "name": "Commerce", "folderId": "4"},
                {"object_type": "trigger", "name": "CE - purchase", "triggerId": "7"},
                {"object_type": "tag", "name": "Base", "tagId": "8"},
                {
                    "object_type": "tag",
                    "name": "Purchase",
                    "tagId": "9",
                    "parentFolderId": "4",
                    "firingTriggerId": ["7"],
                    "setupTag": [{"tagName": "8", "stopOnSetupFailure": True}],
                },
            ]
        }
        normalized = normalize_graph(graph)["tag::Purchase"]
        self.assertEqual(normalized["parentFolderId"], "folder::Commerce")
        self.assertEqual(normalized["firingTriggerId"], ["trigger::CE - purchase"])
        self.assertEqual(normalized["setupTag"][0]["tagName"], "tag::Base")


if __name__ == "__main__":
    unittest.main()
