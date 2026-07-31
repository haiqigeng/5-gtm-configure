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
        self.assertEqual(self.payload["version"], 3)
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

        saved["objects"][0]["type"] = "GAAWE"
        self.assertFalse(compare_graphs(expected, saved)["pass"])

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

    def test_unresolved_raw_or_semantic_reference_fails(self) -> None:
        for reference in ("17", "trigger::CE - purchase"):
            with self.subTest(reference=reference):
                graph = {
                    "objects": [
                        {
                            "object_type": "tag",
                            "name": "Purchase",
                            "firingTriggerId": [reference],
                        }
                    ]
                }
                with self.assertRaisesRegex(GraphError, "unresolved trigger reference"):
                    normalize_graph(graph)

    def test_matching_dangling_references_cannot_prove_graph_equality(self) -> None:
        graph = {
            "objects": [
                {
                    "object_type": "tag",
                    "name": "Purchase",
                    "firingTriggerId": ["17"],
                }
            ]
        }
        with self.assertRaisesRegex(GraphError, "include the referenced object"):
            compare_graphs(graph, graph)

    def test_duplicate_keyed_gtm_parameter_fails(self) -> None:
        graph = {
            "objects": [
                {
                    "object_type": "tag",
                    "name": "Duplicate parameters",
                    "parameter": [
                        {"type": "template", "key": "eventName", "value": "purchase"},
                        {"type": "template", "key": "eventName", "value": "add_to_cart"},
                    ],
                }
            ]
        }
        with self.assertRaisesRegex(GraphError, "duplicate GTM Parameter key"):
            normalize_graph(graph)

    def test_parameter_type_casing_is_normalized_before_map_comparison(self) -> None:
        expected = {
            "objects": [
                {
                    "object_type": "tag",
                    "name": "Purchase",
                    "parameter": [
                        {
                            "type": "MAP",
                            "key": "eventSettingsTable",
                            "map": [
                                {"type": "TEMPLATE", "key": "value", "value": "{{DLV - value}}"},
                                {
                                    "type": "TEMPLATE",
                                    "key": "currency",
                                    "value": "{{DLV - currency}}",
                                },
                            ],
                        }
                    ],
                    "monitoringMetadata": {
                        "type": "MAP",
                        "map": [
                            {"type": "TEMPLATE", "key": "status", "value": "enabled"},
                            {"type": "BOOLEAN", "key": "includeTagName", "value": "true"},
                        ],
                    },
                }
            ]
        }
        saved = {
            "objects": [
                {
                    "object_type": "tag",
                    "name": "Purchase",
                    "parameter": [
                        {
                            "type": "map",
                            "key": "eventSettingsTable",
                            "map": [
                                {
                                    "type": "template",
                                    "key": "currency",
                                    "value": "{{DLV - currency}}",
                                },
                                {"type": "template", "key": "value", "value": "{{DLV - value}}"},
                            ],
                        }
                    ],
                    "monitoringMetadata": {
                        "type": "map",
                        "map": [
                            {
                                "type": "boolean",
                                "key": "includeTagName",
                                "value": "true",
                            },
                            {"type": "template", "key": "status", "value": "enabled"},
                        ],
                    },
                }
            ]
        }
        self.assertTrue(compare_graphs(expected, saved)["pass"])

    def test_uppercase_list_parameter_remains_ordered(self) -> None:
        graph = {
            "objects": [
                {
                    "object_type": "tag",
                    "name": "Ordered list",
                    "parameter": [
                        {
                            "type": "LIST",
                            "key": "items",
                            "list": [
                                {"type": "TEMPLATE", "key": "ignored", "value": "first"},
                                {"type": "TEMPLATE", "key": "ignored", "value": "second"},
                            ],
                        }
                    ],
                }
            ]
        }
        reordered = json.loads(json.dumps(graph))
        reordered["objects"][0]["parameter"][0]["list"].reverse()
        self.assertFalse(compare_graphs(graph, reordered)["pass"])


if __name__ == "__main__":
    unittest.main()
