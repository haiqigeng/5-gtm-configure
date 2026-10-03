#!/usr/bin/env python3
"""Run discovered MCP capabilities through one in-memory host connection."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from adapter_runtime import TargetAdapterRegistry, execute_ready_operations, verify_idempotent_rerun
from adapter_support import AdapterExecutionError
from configuration_run import load_document, render_markdown
from mcp_adapter import McpTargetAdapter
from mcp_discovery import discover
from mcp_transport import StdioTransport, completion, configure_terminal
from redaction import scrub_sensitive_text
from strict_json import load_json, validate_output_paths, write_json_atomic, write_text_atomic


def execute(run_path: Path, profiles: dict, transport: StdioTransport) -> dict:
    validate_output_paths(inputs=[run_path], outputs=[run_path.with_suffix(".md")])
    started = time.monotonic()
    targets = load_document(run_path)["run"]["targets"]
    missing = [target["target_id"] for target in targets if target["target_id"] not in profiles]
    if missing:
        raise ValueError("Missing MCP profile for target(s): " + ", ".join(missing))
    registry = TargetAdapterRegistry()
    # Structural profile errors remain global preflight errors, before any remote call.
    adapters = [
        McpTargetAdapter(target, profiles[target["target_id"]], transport) for target in targets
    ]
    for target, adapter in zip(targets, adapters):
        try:
            registry.register(target, adapter, adapter.capabilities())
        except AdapterExecutionError as exc:
            registry.record_unavailable(target["target_id"], exc)
    execute_ready_operations(run_path, registry)
    current = load_document(run_path)
    if all(item["state"] == "verified" for item in current["object_changes"]):
        verify_idempotent_rerun(run_path, registry)
    current = load_document(run_path)
    write_text_atomic(run_path.with_suffix(".md"), render_markdown(current))
    return {
        "status": current["run"]["status"],
        "mcp_calls": transport.calls,
        "writes_attempted": transport.writes_attempted,
        "execution_seconds": round(time.monotonic() - started, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", type=Path)
    mode.add_argument("--discover", type=Path, help="Read-only approved-target input")
    parser.add_argument("--output", type=Path, help="Preparation inventory output; discovery only")
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--call-timeout", type=float, default=180)
    args = parser.parse_args()
    if bool(args.discover) != bool(args.output):
        parser.error("--discover requires --output; --run does not use --output")
    input_path = args.discover or args.run
    try:
        validate_output_paths(
            inputs=[input_path, args.profiles],
            outputs=[
                input_path.with_suffix(".execution.json"),
                args.output if args.discover else input_path.with_suffix(".md"),
            ],
        )
    except ValueError as exc:
        parser.error(str(exc))
    transport = None
    try:
        configure_terminal()
        transport = StdioTransport(timeout=args.call_timeout)
        result = (
            discover(load_json(args.discover), load_json(args.profiles), transport, args.output)
            if args.discover
            else execute(args.run, load_json(args.profiles), transport)
        )
    except Exception as exc:
        writes = transport.writes_attempted if transport else 0
        result = {
            "status": "Interrupted" if writes else "Blocked",
            "error_type": type(exc).__name__,
            "error": scrub_sensitive_text(str(exc), set()),
            "mcp_calls": transport.calls if transport else 0,
            "writes_attempted": writes,
            "next_action": (
                "Inspect the run and read back any attempted write before resuming"
                if writes
                else "Correct this setup/read failure; no mutation was dispatched"
            ),
        }
    write_json_atomic(input_path.with_suffix(".execution.json"), result)
    completion(result)
    return 0 if result["status"] in {"Configured", "Discovered"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
