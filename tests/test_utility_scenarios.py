from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "utility_scenarios.json"


class UtilityScenarioFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.cases = {item["id"]: item for item in cls.payload["cases"]}

    def test_expected_utility_surface_is_covered(self) -> None:
        self.assertEqual(self.payload["version"], 1)
        self.assertIn("not model-output", self.payload["description"])
        self.assertEqual(
            set(self.cases),
            {
                "empty-media-ecommerce-supported-templates",
                "existing-ecommerce-object-reuse",
                "native-ga4-purchase-no-transform",
                "basic-google-consent-complete-signals",
                "delta-tag-update-with-consumers",
                "enhanced-measurement-collision",
                "explicit-browser-event-id-server-deferred",
                "affiliate-basket-and-network-dedup",
                "unlisted-vendor-generic-browser-route",
                "semantic-readback-returned-ids",
            },
        )

    def test_media_runtime_empty_data_never_adds_eligibility_or_custom_html(self) -> None:
        case = self.cases["empty-media-ecommerce-supported-templates"]
        forbidden = " ".join(case["forbidden_objects"]).lower()
        self.assertIn("eligible", forbidden)
        self.assertIn("custom html", forbidden)
        self.assertIn("business events own firing", case["expected_controls"])

    def test_native_ga4_and_existing_ecommerce_avoid_unnecessary_transforms(self) -> None:
        native = self.cases["native-ga4-purchase-no-transform"]
        self.assertIn("native ecommerce enabled", native["expected_controls"])
        self.assertTrue(any("CJS" in item for item in native["forbidden_objects"]))
        reuse = self.cases["existing-ecommerce-object-reuse"]
        self.assertIn("idempotent no-op rerun", reuse["expected_controls"])

    def test_consent_delta_and_event_id_boundaries_are_explicit(self) -> None:
        consent = self.cases["basic-google-consent-complete-signals"]
        self.assertEqual(
            consent["artifact"]["signals"],
            ["analytics_storage", "ad_storage", "ad_user_data", "ad_personalization"],
        )
        delta = self.cases["delta-tag-update-with-consumers"]
        self.assertEqual(delta["expected_actions"][:3], ["update", "rename", "pause"])
        event_id = self.cases["explicit-browser-event-id-server-deferred"]
        self.assertIn("event ID not generated", event_id["expected_controls"])
        self.assertIn("defer server matching", event_id["expected_actions"])

    def test_broader_routes_remain_browser_specific_and_operational(self) -> None:
        affiliate = self.cases["affiliate-basket-and-network-dedup"]
        self.assertIn("all three items preserved", affiliate["expected_controls"])
        generic = self.cases["unlisted-vendor-generic-browser-route"]
        self.assertIn("browser-only field matrix", generic["expected_controls"])
        graph = self.cases["semantic-readback-returned-ids"]
        self.assertIn("IDs translated to semantic names", graph["expected_controls"])


if __name__ == "__main__":
    unittest.main()
