"""Synthetic native GTM exposed through a real MCP server for host integration tests."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_behavior_scenario import FakeGtm, request  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--transport", choices=("stdio", "http", "sse"), default="stdio")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--uncertain", action="store_true")
    parser.add_argument("--marker", default="")
    args = parser.parse_args()
    backend = FakeGtm(request())
    backend.uncertain = args.uncertain
    if args.state.exists():
        saved = json.loads(args.state.read_text(encoding="utf-8"))
        backend.data = saved["data"]
        backend.calls = saved["calls"]
        backend.writes = saved["writes"]
        backend.uncertain = saved.get("uncertain", False)
        backend.hide_once = saved.get("hide_once", False)
    app = FastMCP("synthetic-gtm", host="127.0.0.1", port=args.port)
    print("Synthetic server diagnostic: " + os.environ.get("SYNTHETIC_TOKEN", ""), file=sys.stderr)

    def add(name):
        def handler(
            action: str,
            accountId: str,
            containerId: str,
            workspaceId: str | None = None,
            page: int | None = None,
            itemsPerPage: int | None = None,
            tagId: str | None = None,
            triggerId: str | None = None,
            variableId: str | None = None,
            createOrUpdateConfig: dict | None = None,
            fingerprint: str | None = None,
        ) -> dict:
            values = {
                key: value
                for key, value in locals().items()
                if value is not None and key not in {"name", "backend", "args"}
            }
            try:
                return backend.call(name, values)
            finally:
                args.state.write_text(
                    json.dumps(
                        {
                            "data": backend.data,
                            "calls": backend.calls,
                            "writes": backend.writes,
                            "marker": args.marker,
                            "uncertain": backend.uncertain,
                            "hide_once": backend.hide_once,
                        }
                    ),
                    encoding="utf-8",
                )

        app.add_tool(handler, name=name)

    for tool in ("gtm_workspace", "gtm_container", "gtm_tag", "gtm_trigger", "gtm_variable"):
        add(tool)
    app.run(transport="streamable-http" if args.transport == "http" else args.transport)


if __name__ == "__main__":
    main()
