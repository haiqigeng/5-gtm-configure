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


class V9DocumentationTest(unittest.TestCase):
    def test_route_classification_keeps_server_detail_conditional(self) -> None:
        skill = read("SKILL.md")
        pipeline_heading = skill.index("### Pipeline route")
        server_heading = skill.index("### Server route")
        judgement_heading = skill.index("## 03 - Judgement")
        self.assertLess(pipeline_heading, server_heading)
        self.assertLess(server_heading, judgement_heading)
        web_table = skill[skill.index("### Shared and web routes") : pipeline_heading]
        self.assertNotIn("references/02-execution/server/", web_table)
        server_section = skill[server_heading:judgement_heading]
        for name in MEDIA:
            self.assertIn(f"server/media-{name}.md", server_section)

    def test_all_browser_media_routes_have_concise_server_counterparts(self) -> None:
        for name in MEDIA:
            with self.subTest(platform=name):
                browser = read(f"references/02-execution/media-{name}.md")
                server = read(f"references/02-execution/server/media-{name}.md")
                self.assertIn("## Server route", browser)
                pointer = browser.rsplit("## Server route", 1)[-1]
                self.assertLessEqual(len(WORD.findall(pointer)), 90)
                self.assertIn("official", server.casefold())
                self.assertIn("fail closed", server.casefold())

    def test_server_media_files_do_not_copy_shared_boilerplate_paragraphs(self) -> None:
        owners: dict[str, list[str]] = {}
        for name in MEDIA:
            text = read(f"references/02-execution/server/media-{name}.md")
            for paragraph in re.split(r"\n\s*\n", text):
                normalized = " ".join(paragraph.split()).casefold()
                if len(WORD.findall(normalized)) >= 35:
                    owners.setdefault(normalized, []).append(name)
        duplicates = {text: names for text, names in owners.items() if len(names) > 1}
        self.assertEqual(duplicates, {})

    def test_platform_fixture_covers_every_route_and_the_v8_wrongness_case(self) -> None:
        fixture = json.loads(read("tests/fixtures/server_pipeline_scenarios.json"))
        records = fixture["platform_scenarios"]
        self.assertEqual({item["platform"] for item in records}, MEDIA)
        for item in records:
            self.assertTrue(item["server_route"])
            self.assertTrue(item["official_entry_point"])
            self.assertTrue(item["overlap_rule"])
        wrongness = fixture["v8_wrongness_scenario"]
        self.assertEqual(wrongness["event"], "add_to_cart")
        self.assertEqual(wrongness["delivery"], "dual")
        self.assertFalse(wrongness["stable_site_id_available"])
        self.assertIn("purchase fallback", wrongness["forbidden"])

    def test_core_load_delta_is_measured_without_a_file_size_gate(self) -> None:
        from check_release import MANDATORY_CORE, V8_MANDATORY_CORE_WORDS

        current = sum(len(WORD.findall(read(relative))) for relative in MANDATORY_CORE)
        self.assertEqual(V8_MANDATORY_CORE_WORDS, 7214)
        self.assertGreater(current, 0)
        checker = read("scripts/check_release.py")
        self.assertNotIn("MAX_FILE_LINES", checker)
        self.assertNotIn("MAX_REFERENCE_WORDS", checker)

    def test_controller_is_a_dispatcher_over_focused_modules(self) -> None:
        tree = ast.parse(read("scripts/configuration_run.py"))
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        imported_modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        self.assertTrue(
            {
                "run_model",
                "run_render",
                "run_state",
                "run_validation_core",
                "verification",
            }
            <= imported_modules
        )
        for module in (
            "redaction.py",
            "resource_registry.py",
            "run_validation_server.py",
            "run_validation_pipeline.py",
            "web_domain_validation.py",
        ):
            self.assertTrue((ROOT / "scripts" / module).is_file())

    def test_web_compatibility_and_v9_boundaries_are_both_explicit(self) -> None:
        combined = " ".join(
            read(relative)
            for relative in (
                "SKILL.md",
                "references/01-orientation/utility-contract.md",
                "references/02-execution/configuration-contract.md",
            )
        ).replace("\n", " ")
        for phrase in (
            "preserve the complete v8 client-side surface",
            "Default every product to strict/basic CMP blocking",
            "payload-eligibility variables",
            "Web authority does not grant server authority",
            "items` is an array and `user_data` is an object",
            "never publish",
        ):
            self.assertIn(phrase.casefold(), combined.casefold())
        self.assertNotIn(
            "server-side GTM, Conversions API, and browser/server deduplication remain future",
            combined.casefold(),
        )


if __name__ == "__main__":
    unittest.main()
