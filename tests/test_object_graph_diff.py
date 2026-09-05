from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from diff_object_graph import (  # noqa: E402
    BUILT_IN_TRIGGER_IDS,
    STANDALONE_PARAMETER_FIELDS,
    GraphError,
    compare_graphs,
    normalize_graph,
)

FIXTURE = ROOT / "tests" / "fixtures" / "golden_object_graphs.json"
TAG_PARAMETER_FIELDS = {"priority", "monitoringMetadata", "consentType"}
TRIGGER_PARAMETER_FIELDS = {
    "checkValidation",
    "continuousTimeMinMilliseconds",
    "eventName",
    "horizontalScrollPercentageList",
    "interval",
    "intervalSeconds",
    "limit",
    "maxTimerLengthSeconds",
    "selector",
    "totalTimeMinMilliseconds",
    "uniqueTriggerId",
    "verticalScrollPercentageList",
    "visibilitySelector",
    "visiblePercentageMax",
    "visiblePercentageMin",
    "waitForTags",
    "waitForTagsTimeout",
}
VARIABLE_FORMAT_PARAMETER_FIELDS = {
    "convertFalseToValue",
    "convertNullToValue",
    "convertTrueToValue",
    "convertUndefinedToValue",
}


class ObjectGraphDiffTest(unittest.TestCase):
    def test_raw_reference_context_resolves_ids_without_becoming_extra_objects(self) -> None:
        expected = {
            "objects": [
                {
                    "target_id": "web-main",
                    "object_type": "tag",
                    "name": "GA4 - page_view",
                    "type": "gaawe",
                    "firingTriggerId": ["web-main::trigger::CE - page_view"],
                }
            ]
        }
        saved = {
            "objects": [
                {
                    "target_id": "web-main",
                    "object_type": "tag",
                    "name": "GA4 - page_view",
                    "type": "gaawe",
                    "firingTriggerId": ["17"],
                }
            ],
            "context_objects": [
                {
                    "target_id": "web-main",
                    "object_type": "trigger",
                    "name": "CE - page_view",
                    "triggerId": "17",
                    "type": "customEvent",
                }
            ],
        }
        report = compare_graphs(expected, saved, target_types={"web-main": "web"})
        self.assertTrue(report["pass"])
        self.assertEqual(report["extra_objects"], [])

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

    def test_sequencing_tag_name_accepts_the_official_name_form(self) -> None:
        graph = {
            "objects": [
                {"object_type": "tag", "name": "Base"},
                {
                    "object_type": "tag",
                    "name": "Purchase",
                    "setupTag": [{"tagName": "Base", "stopOnSetupFailure": True}],
                },
            ]
        }
        normalized = normalize_graph(graph)["tag::Purchase"]
        self.assertEqual(normalized["setupTag"][0]["tagName"], "tag::Base")

        ambiguous = {
            "objects": [
                {"object_type": "tag", "name": "Other", "tagId": "Base"},
                {"object_type": "tag", "name": "Base", "tagId": "8"},
                {
                    "object_type": "tag",
                    "name": "Purchase",
                    "setupTag": [{"tagName": "Base", "stopOnSetupFailure": True}],
                },
            ]
        }
        with self.assertRaisesRegex(GraphError, "ambiguous tag reference"):
            normalize_graph(ambiguous)

    def test_unresolved_raw_or_semantic_reference_fails(self) -> None:
        for reference in (
            "17",
            "trigger::CE - purchase",
            "web-main::trigger::CE - purchase",
        ):
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

    def test_builtin_trigger_ids_do_not_require_synthetic_trigger_records(self) -> None:
        self.assertEqual(
            BUILT_IN_TRIGGER_IDS,
            {"2147479553", "2147479572", "2147479573"},
        )
        for trigger_id in BUILT_IN_TRIGGER_IDS:
            with self.subTest(trigger_id=trigger_id):
                graph = {
                    "objects": [
                        {
                            "object_type": "tag",
                            "name": "Built-in trigger consumer",
                            "firingTriggerId": [trigger_id],
                        }
                    ]
                }
                normalized = normalize_graph(graph)["tag::Built-in trigger consumer"]
                self.assertEqual(
                    normalized["firingTriggerId"],
                    [f"trigger::builtin::{trigger_id}"],
                )
                self.assertTrue(compare_graphs(graph, graph)["pass"])

    def test_unknown_reserved_looking_trigger_still_requires_closure(self) -> None:
        graph = {
            "objects": [
                {
                    "object_type": "tag",
                    "name": "Unknown trigger consumer",
                    "firingTriggerId": ["2147479599"],
                }
            ]
        }
        with self.assertRaisesRegex(GraphError, "unresolved trigger reference"):
            normalize_graph(graph)

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

    def test_every_official_standalone_parameter_field_normalizes_type_casing(self) -> None:
        self.assertEqual(
            STANDALONE_PARAMETER_FIELDS,
            TAG_PARAMETER_FIELDS | TRIGGER_PARAMETER_FIELDS | VARIABLE_FORMAT_PARAMETER_FIELDS,
        )

        for field in TRIGGER_PARAMETER_FIELDS:
            with self.subTest(object_type="trigger", field=field):
                expected = {
                    "objects": [
                        {
                            "object_type": "trigger",
                            "name": field,
                            field: {"type": "TEMPLATE", "value": "same"},
                        }
                    ]
                }
                saved = json.loads(json.dumps(expected))
                saved["objects"][0][field]["type"] = "template"
                self.assertTrue(compare_graphs(expected, saved)["pass"])

    def test_nested_standalone_parameters_normalize_without_changing_other_enums(self) -> None:
        expected = {
            "objects": [
                {
                    "object_type": "tag",
                    "name": "Priority",
                    "priority": {"type": "INTEGER", "value": "10"},
                },
                {
                    "object_type": "tag",
                    "name": "Consent",
                    "consentSettings": {
                        "consentStatus": "needed",
                        "consentType": {
                            "type": "LIST",
                            "list": [{"type": "STRING", "value": "ad_storage"}],
                        },
                    },
                },
                {
                    "object_type": "variable",
                    "name": "Formatted",
                    "formatValue": {
                        "caseConversionType": "lowercase",
                        "convertFalseToValue": {"type": "TEMPLATE", "value": "false"},
                        "convertNullToValue": {"type": "TEMPLATE", "value": "unknown"},
                        "convertTrueToValue": {"type": "TEMPLATE", "value": "true"},
                        "convertUndefinedToValue": {
                            "type": "TEMPLATE",
                            "value": "unknown",
                        },
                    },
                },
            ]
        }
        saved = json.loads(json.dumps(expected))
        saved["objects"][0]["priority"]["type"] = "integer"
        saved["objects"][1]["consentSettings"]["consentType"]["type"] = "list"
        saved["objects"][1]["consentSettings"]["consentType"]["list"][0]["type"] = "string"
        for field in VARIABLE_FORMAT_PARAMETER_FIELDS:
            saved["objects"][2]["formatValue"][field]["type"] = "template"
        self.assertTrue(compare_graphs(expected, saved)["pass"])

        saved["objects"][2]["formatValue"]["caseConversionType"] = "LOWERCASE"
        self.assertFalse(compare_graphs(expected, saved)["pass"])

    def test_condition_type_enum_casing_remains_material(self) -> None:
        expected = {
            "objects": [
                {
                    "object_type": "trigger",
                    "name": "Page path",
                    "filter": [
                        {
                            "type": "equals",
                            "parameter": [
                                {"type": "template", "key": "arg0", "value": "{{Page Path}}"},
                                {"type": "template", "key": "arg1", "value": "/"},
                            ],
                        }
                    ],
                }
            ]
        }
        saved = json.loads(json.dumps(expected))
        saved["objects"][0]["filter"][0]["type"] = "EQUALS"
        self.assertFalse(compare_graphs(expected, saved)["pass"])


if __name__ == "__main__":
    unittest.main()
