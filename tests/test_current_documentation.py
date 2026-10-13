from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORD = re.compile(r"\b[\w-]+\b")
MEDIA = {
    "affiliate",
    "criteo",
    "floodlight",
    "google-ads",
    "linkedin",
    "meta",
    "microsoft-ads",
    "pinterest",
    "reddit",
    "snapchat",
    "tiktok",
    "x",
}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class CurrentDocumentationTest(unittest.TestCase):
    def test_route_classification_keeps_server_detail_conditional(self) -> None:
        skill = read("SKILL.md")
        self.assertIn("references/media/common.md", skill)
        self.assertIn("references/media/server.md", skill)
        self.assertNotIn("references/vendors/", skill)
        for name in MEDIA:
            self.assertIn(f"../vendors/{name}/web.md", read("references/media/common.md"))
            self.assertIn(f"../vendors/{name}/server.md", read("references/media/server.md"))

    def test_all_browser_media_routes_have_concise_server_counterparts(self) -> None:
        for name in MEDIA:
            with self.subTest(platform=name):
                browser = read(f"references/vendors/{name}/web.md")
                server = read(f"references/vendors/{name}/server.md")
                self.assertIn("## Server route", browser)
                pointer = browser.rsplit("## Server route", 1)[-1]
                self.assertLessEqual(len(WORD.findall(pointer)), 90)
                self.assertIn("official", server.casefold())
                self.assertIn("fail closed", server.casefold())

    def test_server_media_files_do_not_copy_shared_boilerplate_paragraphs(self) -> None:
        owners: dict[str, list[str]] = {}
        for name in MEDIA:
            text = read(f"references/vendors/{name}/server.md")
            for paragraph in re.split(r"\n\s*\n", text):
                normalized = " ".join(paragraph.split()).casefold()
                if len(WORD.findall(normalized)) >= 35:
                    owners.setdefault(normalized, []).append(name)
        duplicates = {text: names for text, names in owners.items() if len(names) > 1}
        self.assertEqual(duplicates, {})

    def test_platform_fixture_covers_every_route_and_the_unsafe_dedup_case(self) -> None:
        fixture = json.loads(read("tests/fixtures/server_pipeline_scenarios.json"))
        records = fixture["platform_scenarios"]
        self.assertEqual({item["platform"] for item in records}, MEDIA)
        for item in records:
            self.assertTrue(item["server_route"])
            self.assertTrue(item["official_entry_point"])
            self.assertTrue(item["overlap_rule"])
        wrongness = fixture["unsafe_internal_dedup_scenario"]
        self.assertEqual(wrongness["event"], "add_to_cart")
        self.assertEqual(wrongness["delivery"], "dual")
        self.assertFalse(wrongness["stable_site_id_available"])
        self.assertIn("purchase fallback", wrongness["forbidden"])

    def test_core_is_routed_without_a_file_size_gate(self) -> None:
        from check_release import MANDATORY_CORE

        current = sum(len(WORD.findall(read(relative))) for relative in MANDATORY_CORE)
        self.assertGreater(current, 0)
        checker = read("tools/check_release.py")
        self.assertNotIn("MAX_FILE_LINES", checker)
        self.assertNotIn("MAX_REFERENCE_WORDS", checker)

    def test_controller_is_a_dispatcher_over_focused_modules(self) -> None:
        tree = ast.parse(read("scripts/configure_gtm.py"))
        functions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.assertEqual(functions, {"main"})
        for module in (
            "core/privacy",
            "domain/resources",
            "domain/server",
            "domain/pipeline",
            "domain/web",
        ):
            self.assertTrue((ROOT / "scripts/gtm_configure" / (module + ".py")).is_file())


if __name__ == "__main__":
    unittest.main()
