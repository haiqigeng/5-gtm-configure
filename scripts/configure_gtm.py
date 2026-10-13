#!/usr/bin/env python3
"""Configure GTM: one entry point, lazily loaded task-specific commands."""

import importlib
import sys

COMMANDS = {
    "import-plan": "intake.ga4",
    "prepare": "intake.request",
    "validate-contract": "contract",
    "conformance": "comparison.conformance",
    "compare": "comparison.native",
    "run": "cli.run",
    "mcp": "cli.mcp",
    "mcp-host": "cli.mcp_host",
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print(
            "Usage: configure_gtm.py COMMAND [arguments]\n\n"
            + "\n".join("  " + name for name in COMMANDS)
        )
        return 0
    command = sys.argv.pop(1)
    if command not in COMMANDS:
        print(f"Unknown command {command!r}; use --help", file=sys.stderr)
        return 2
    sys.argv[0] += " " + command
    return importlib.import_module("gtm_configure." + COMMANDS[command]).main()


if __name__ == "__main__":
    raise SystemExit(main())
