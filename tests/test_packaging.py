from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]

from check_release import assigned_string_constant  # noqa: E402


class ReleaseChecksTest(unittest.TestCase):
    def test_release_check_passes_for_current_release(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "check_release.py"),
                "--tag",
                "v12.0.0",
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
                str(ROOT / "tools" / "check_release.py"),
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
                str(ROOT / "tools" / "check_release.py"),
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
                "## 12.0.0\n\n"
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
                    str(ROOT / "tools" / "check_release.py"),
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
                str(ROOT / "tools" / "check_release.py"),
                "--require-git-tag",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(missing_tag.returncode, 0)
        self.assertIn("--require-git-tag requires --tag", missing_tag.stderr)

    def test_release_version_checks_use_exact_top_level_assignments(self) -> None:
        source = 'SCHEMA_VERSION = "9.9"\nVERIFICATION_SCHEMA_VERSION = "1.1"\n'
        self.assertEqual(assigned_string_constant(source, "SCHEMA_VERSION"), "9.9")
        self.assertEqual(
            assigned_string_constant(source, "VERIFICATION_SCHEMA_VERSION"),
            "1.1",
        )
        self.assertIsNone(assigned_string_constant(source, "MISSING"))

    def test_runtime_package_contains_only_runtime_files(self) -> None:
        expected_sources = [
            ROOT / name
            for name in (
                "VERSION",
                "SKILL.md",
                "LICENSE",
                "agents/openai.yaml",
                "scripts/configure_gtm.py",
                "scripts/mcp_relay.js",
                "scripts/requirements.txt",
                "scripts/requirements-mcp.txt",
                "tests/test_release.py",
                "tests/pytest.ini",
                "tests/requirements.txt",
                "tests/fixtures/folder-request.json",
                "tests/fixtures/client-request.json",
                "tests/fixtures/web-request.json",
                "tests/fixtures/pipeline-request.json",
            )
        ]
        expected_sources.extend(sorted((ROOT / "scripts/gtm_configure").rglob("*.py")))
        expected_sources.extend(sorted((ROOT / "references").rglob("*.md")))
        expected_sources.extend(sorted((ROOT / "references").rglob("*.json")))
        expected_sources.extend(sorted((ROOT / "schemas").rglob("*.json")))
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
                        str(ROOT / "tools" / "build_skill_package.py"),
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
            extracted = Path(temporary) / "extracted"
            with ZipFile(archives[0]) as package:
                package.extractall(extracted)
            scripts_path = extracted / "configure-gtm" / "scripts"
            modules = sorted(
                source.stem
                for source in expected_sources
                if source.parent == ROOT / "scripts" and source.suffix == ".py"
            )
            smoke = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    (
                        "import importlib,sys;sys.path.insert(0,sys.argv[1]);"
                        "[importlib.import_module(name) for name in sys.argv[2:]]"
                    ),
                    str(scripts_path),
                    *modules,
                ],
                cwd=extracted,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(smoke.returncode, 0, smoke.stdout + smoke.stderr)
            regression = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "pytest",
                    str(extracted / "configure-gtm" / "tests"),
                    "-q",
                    "-p",
                    "no:cacheprovider",
                ],
                cwd=extracted,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(regression.returncode, 0, regression.stdout + regression.stderr)


if __name__ == "__main__":
    unittest.main()
