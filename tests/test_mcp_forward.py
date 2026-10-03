"""Persist independent forward scenarios against the packaged execution path."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


class McpForwardTests(unittest.TestCase):
    def test_native_create_update_uncertain_recovery_and_drift_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(FIXTURES / "mcp_behavior_scenario.py"), directory],
                capture_output=True,
                text=True,
                timeout=45,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_actual_host_relay_unicode_errors_and_forbidden_action(self):
        available = shutil.which("node") and shutil.which("pwsh")
        if not available:
            if os.environ.get("REQUIRE_RELAY_TESTS") == "1":
                self.fail("Required relay runtimes are missing: Node and PowerShell 7")
            self.skipTest("Host relay requires Node and PowerShell 7")
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [shutil.which("node"), str(FIXTURES / "mcp_relay_scenario.cjs"), directory],
                env={
                    **os.environ,
                    "TEST_PYTHON": sys.executable,
                    "TEST_PWSH": shutil.which("pwsh"),
                },
                capture_output=True,
                text=True,
                timeout=60,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
