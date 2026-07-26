from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


class ReleaseChecksTest(unittest.TestCase):
    def test_release_check_passes_for_current_release(self) -> None:
        for cache in (ROOT / "scripts" / "__pycache__", ROOT / "tests" / "__pycache__"):
            if cache.exists():
                shutil.rmtree(cache)
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "check_release.py"),
                "--tag",
                "v5.0.0",
                "--release-notes",
                str(ROOT / "CHANGELOG.md"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        wrong_tag = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "check_release.py"),
                "--tag",
                "v2.1.0",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(wrong_tag.returncode, 0)
        self.assertIn("does not match current release", wrong_tag.stderr)

        invalid_tag = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "check_release.py"),
                "--tag",
                "v2026.7.20.1",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(invalid_tag.returncode, 0)
        self.assertIn("invalid Semantic Version release tag", invalid_tag.stderr)

        with tempfile.TemporaryDirectory() as temporary:
            notes = Path(temporary) / "CHANGELOG.md"
            notes.write_text(
                "# Changelog\n\n"
                "## 5.0.0\n\n"
                "### Why This Release Matters\n\n"
                "### What Changed\n\n"
                "### What Users Should Do\n\n"
                "### Known Limits\n\n"
                "## 2026.7.20\n\n"
                "### Validation\n",
                encoding="utf-8",
            )
            stale_heading = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "check_release.py"),
                    "--release-notes",
                    str(notes),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(stale_heading.returncode, 0)
            self.assertIn("release notes missing heading: Validation", stale_heading.stderr)

        missing_tag = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "check_release.py"),
                "--require-git-tag",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(missing_tag.returncode, 0)
        self.assertIn("--require-git-tag requires --tag", missing_tag.stderr)

    def test_runtime_package_contains_only_runtime_files(self) -> None:
        expected_sources = [
            ROOT / "SKILL.md",
            ROOT / "agents" / "openai.yaml",
            ROOT / "LICENSE",
            ROOT / "scripts" / "diff_object_graph.py",
            ROOT / "scripts" / "validate_configuration_contract.py",
            ROOT / "scripts" / "validate_contract_conformance.py",
        ]
        expected_sources.extend(sorted((ROOT / "references").rglob("*.md")))
        expected_names = {
            (Path("configure-gtm") / source.relative_to(ROOT)).as_posix()
            for source in expected_sources
        }

        with tempfile.TemporaryDirectory() as temporary:
            archives = [Path(temporary) / "first.zip", Path(temporary) / "second.zip"]
            for archive in archives:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts" / "build_skill_package.py"),
                        "--output",
                        str(archive),
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(archive.exists())

                with ZipFile(archive) as package:
                    self.assertEqual(set(package.namelist()), expected_names)
                    for info in package.infolist():
                        self.assertEqual(info.date_time, (2026, 1, 1, 0, 0, 0))
                        self.assertEqual(info.create_system, 3)
                        self.assertEqual(info.external_attr >> 16, 0o644)

            self.assertEqual(archives[0].read_bytes(), archives[1].read_bytes())


if __name__ == "__main__":
    unittest.main()
