#!/usr/bin/env python3
"""Bind discovered MCP profiles and run the existing execution and convergence engine."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from adapter_runtime import TargetAdapterRegistry, execute_ready_operations, verify_idempotent_rerun
from configuration_run import load_document, render_markdown
from mcp_queue_adapter import McpTargetAdapter, QueueTransport
from strict_json import load_json, write_json_atomic, write_text_atomic


def execute(run_path: Path, profiles: dict, queue: Path) -> dict:
    started = time.monotonic()
    calls = 0
    transport = QueueTransport(queue)

    def call(tool, arguments):
        nonlocal calls
        calls += 1
        return transport(tool, arguments)

    registry = TargetAdapterRegistry()
    for target in load_document(run_path)["run"]["targets"]:
        adapter = McpTargetAdapter(target, profiles[target["target_id"]], call)
        registry.register(target, adapter, adapter.capabilities())
    execute_ready_operations(run_path, registry)
    current = load_document(run_path)
    if all(item["state"] == "verified" for item in current["object_changes"]):
        verify_idempotent_rerun(run_path, registry)
    current = load_document(run_path)
    write_text_atomic(run_path.with_suffix(".md"), render_markdown(current))
    return {
        "status": current["run"]["status"],
        "mcp_calls": calls,
        "execution_seconds": round(time.monotonic() - started, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    args = parser.parse_args()
    args.queue.mkdir(parents=True, exist_ok=True)
    if any(args.queue.iterdir()):
        raise ValueError("Use a new empty queue directory for each execution")
    try:
        result = execute(args.run, load_json(args.profiles), args.queue)
    except Exception:
        write_json_atomic(
            args.queue / "complete.json",
            {
                "status": "Interrupted",
                "error": "Inspect the validated run and resolve uncertain writes before resuming",
            },
        )
        return 1
    write_json_atomic(args.queue / "complete.json", result)
    return 0 if result["status"] == "Configured" else 1


if __name__ == "__main__":
    raise SystemExit(main())
