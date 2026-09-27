from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_release import check_files_and_routing  # noqa: E402


class SkillRoutingTest(unittest.TestCase):
    def test_every_runtime_reference_is_reachable_and_exists(self):
        self.assertEqual(check_files_and_routing(), [])

    def test_interface_keeps_normal_discovery_and_concise_invocation(self):
        text = (ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        self.assertNotIn("allow_implicit_invocation: false", text)
        prompt = next(
            line.split(":", 1)[1].strip().strip('"')
            for line in text.splitlines()
            if "default_prompt:" in line
        )
        self.assertLess(len(prompt), 180)
        self.assertIn("$configure-gtm", prompt)


if __name__ == "__main__":
    unittest.main()
