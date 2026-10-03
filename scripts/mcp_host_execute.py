#!/usr/bin/env python3
"""Run the shared GTM engine from Claude Code or Gemini CLI using the official MCP SDK."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import re
import time
from contextlib import AsyncExitStack
from datetime import timedelta
from pathlib import Path
from typing import Any

from adapter_support import AdapterExecutionError, AmbiguousWriteError, AuthenticationError
from mcp_adapter import FAMILIES, McpTargetAdapter
from mcp_execute import execute
from redaction import contains_redacted, sensitive_paths
from strict_json import load_json, validate_output_paths, write_json_atomic


class HostSetupError(ValueError):
    """A non-secret setup diagnostic suitable for the terminal."""


def _expand(value: str, host: str) -> str:
    pattern = r"\$\{([A-Za-z_][A-Za-z_0-9]*)(?::-([^}]*))?\}"
    if host == "gemini":
        pattern += r"|\$([A-Za-z_][A-Za-z_0-9]*)"
        if os.name == "nt":
            pattern += r"|%([A-Za-z_][A-Za-z_0-9]*)%"

    def replace(match):
        variable = match.group(1) or next(group for group in match.groups()[2:] if group)
        if variable in os.environ:
            return os.environ[variable]
        if match.group(2) is not None:
            return match.group(2)
        raise HostSetupError("A referenced environment variable is unset; no connection opened")

    return re.sub(pattern, replace, value)


def load_connection(
    path: Path, host: str, server: str, project_dir: Path, approval_settings: Path | None = None
) -> dict:
    """Read one explicitly selected definition; never merge scopes or read OAuth caches."""
    document = load_json(path)
    config = document.get("mcpServers", {}).get(server)
    if not isinstance(config, dict):
        raise HostSetupError("The selected configuration has no matching mcpServers entry")
    controls = document.get("mcp", {}) if host == "gemini" else {}
    approvals = load_json(approval_settings) if approval_settings is not None else document
    if host == "claude":
        for settings in (document, approvals):
            for key in ("enabledMcpjsonServers", "disabledMcpjsonServers", "disabledMcpServers"):
                values = settings.get(key, [])
                if not isinstance(values, list) or any(
                    not isinstance(value, str) for value in values
                ):
                    raise HostSetupError("Project server approval lists must contain server names")
            if (
                "enableAllProjectMcpServers" in settings
                and type(settings["enableAllProjectMcpServers"]) is not bool
            ):
                raise HostSetupError("Project server approval switch must be a boolean")
        if server in approvals.get("disabledMcpjsonServers", []) or server in approvals.get(
            "disabledMcpServers", []
        ):
            raise HostSetupError("The selected server is disabled or rejected in approval settings")
        project_config = path.name == ".mcp.json"
        approval_control = (
            project_config
            or "enabledMcpjsonServers" in approvals
            or "enableAllProjectMcpServers" in approvals
        )
        if project_config and approval_settings is None:
            raise HostSetupError(
                "Project .mcp.json requires --approval-settings from the trusted host's effective approval settings"
            )
        if approval_control and not (
            approvals.get("enableAllProjectMcpServers") is True
            or server in approvals.get("enabledMcpjsonServers", [])
        ):
            raise HostSetupError(
                "The selected project server is not approved; approve it in the trusted host before connecting"
            )
    if (
        config.get("disabled") is True
        or config.get("enabled") is False
        or server in document.get("disabledMcpServers", [])
        or server in document.get("disabledMcpjsonServers", [])
        or server in controls.get("excluded", [])
        or (controls.get("allowed") is not None and server not in controls["allowed"])
    ):
        raise HostSetupError("The selected server is disabled or excluded")
    if any(key in config for key in ("oauth", "authProviderType", "headersHelper")):
        raise HostSetupError(
            "Host-managed OAuth or dynamic authentication is not available to this SDK connection"
        )
    if host == "claude":
        transport = config.get("type", "stdio")
        if transport == "streamable-http":
            transport = "http"
        url = config.get("url")
    elif host == "gemini":
        endpoints = [key for key in ("command", "url", "httpUrl") if key in config]
        if len(endpoints) != 1:
            raise HostSetupError("Gemini requires exactly one command, url or httpUrl")
        transport = {"command": "stdio", "url": "sse", "httpUrl": "http"}[endpoints[0]]
        url = config.get(endpoints[0]) if transport != "stdio" else None
    else:
        raise HostSetupError("Choose claude or gemini")
    if transport not in {"stdio", "http", "sse"}:
        raise HostSetupError("This runner supports MCP stdio, Streamable HTTP and SSE")
    timeout = config.get("timeout", 180_000)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise HostSetupError("The configured timeout must be a positive number of milliseconds")

    def strings(value, label):
        if not isinstance(value, dict) or any(
            not isinstance(key, str) or not isinstance(item, str) for key, item in value.items()
        ):
            raise HostSetupError(f"{label} must map names to strings")
        return {key: _expand(item, host) for key, item in value.items()}

    result = {
        "transport": transport,
        "timeout": timeout / 1000,
        "include_tools": config.get("includeTools"),
        "exclude_tools": config.get("excludeTools", []),
    }
    for key in ("include_tools", "exclude_tools"):
        values = result[key]
        if values is not None and (
            not isinstance(values, list) or any(not isinstance(item, str) for item in values)
        ):
            raise HostSetupError("Tool filters must contain tool names")
    if transport == "stdio":
        command = config.get("command")
        args = config.get("args", [])
        if (
            not isinstance(command, str)
            or not command
            or not isinstance(args, list)
            or any(not isinstance(item, str) for item in args)
        ):
            raise HostSetupError("Stdio requires a command and an array of string arguments")
        working_directory = config.get("cwd", str(project_dir))
        if not isinstance(working_directory, str):
            raise HostSetupError("Stdio cwd must be a path string")
        directory = Path(_expand(working_directory, host))
        if not directory.is_absolute():
            directory = project_dir / directory
        result.update(
            command=_expand(command, host),
            args=[_expand(a, host) for a in args],
            env=strings(config.get("env", {}), "env"),
            cwd=str(directory.resolve()),
        )
    else:
        if not isinstance(url, str) or not url:
            raise HostSetupError("A remote connection requires its configured endpoint")
        result.update(url=_expand(url, host), headers=strings(config.get("headers", {}), "headers"))
    return result


class SdkTransport:
    """Synchronous adapter calls into one SDK session; no raw response files or shell payloads."""

    def __init__(self, session, loop, tools: dict, allowed: dict, timeout: float):
        from jsonschema.validators import validator_for

        self.session, self.loop, self.allowed, self.timeout = session, loop, allowed, timeout
        self.validators = {}
        for name, tool in tools.items():
            if name not in allowed:
                continue
            validator = validator_for(tool.inputSchema)
            validator.check_schema(tool.inputSchema)
            self.validators[name] = validator(tool.inputSchema)
        if set(allowed) - set(self.validators):
            raise HostSetupError("A required GTM tool is missing or excluded from this connection")
        self.calls = 0
        self.writes_attempted = 0

    def __call__(self, tool: str, arguments: dict, *, public_identifier_paths=None) -> Any:
        if tool not in self.allowed or arguments.get("action") not in self.allowed[tool]:
            raise AdapterExecutionError("Undiscovered or forbidden MCP action")
        if not self.validators[tool].is_valid(arguments):
            raise AdapterExecutionError(
                "Arguments do not match the discovered MCP input schema", code="schema_mismatch"
            )
        mutation = arguments.get("action") in {"create", "update", "remove"}
        if mutation and (
            sensitive_paths(arguments, public_identifier_paths=public_identifier_paths)
            or contains_redacted(arguments)
        ):
            raise AdapterExecutionError(
                "Sensitive mutation fields require an explicitly bound secret provider; no write was dispatched"
            )
        self.calls += 1
        self.writes_attempted += int(mutation)
        pending = asyncio.run_coroutine_threadsafe(
            self.session.call_tool(
                tool, arguments, read_timeout_seconds=timedelta(seconds=self.timeout)
            ),
            self.loop,
        )
        try:
            response = pending.result(timeout=self.timeout + 1)
        except Exception as exc:
            pending.cancel()
            code, message = connection_diagnostic(exc)
            if code == "authentication_required":
                raise AuthenticationError(message) from None
            if code == "access_denied":
                raise AdapterExecutionError(message, code=code) from None
            if code.startswith("http_rejection_"):
                from mcp_adapter import unwrap

                unwrap(
                    {
                        "isError": True,
                        "structuredContent": {"error": {"code": int(code.rsplit("_", 1)[1])}},
                    },
                    mutation=mutation,
                )
            if mutation:
                raise AmbiguousWriteError(message + "; read back before retry") from None
            if code == "authentication_required":
                raise AuthenticationError(message) from None
            raise AdapterExecutionError(message, code=code) from None
        return response.model_dump(mode="json", exclude_none=True)


def connection_diagnostic(error: Exception) -> tuple[str, str]:
    """Classify SDK exception trees without printing URLs, headers or response text."""
    import httpx
    from jsonschema.exceptions import SchemaError

    pending, seen, errors = [error], set(), []
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        errors.append(item)
        pending.extend(getattr(item, "exceptions", ()))
        if item.__cause__ is not None:
            pending.append(item.__cause__)
    for item in errors:
        if isinstance(item, httpx.HTTPStatusError):
            status = item.response.status_code
            if status == 401:
                return (
                    "authentication_required",
                    "Authentication required (HTTP 401); use an authorized stdio connection or configured authentication headers; host OAuth is not shared",
                )
            if status == 403:
                return (
                    "access_denied",
                    "Access denied (HTTP 403); verify the authorized account and server permissions",
                )
            if status in {400, 404, 409, 422, 429}:
                return (
                    f"http_rejection_{status}",
                    f"MCP endpoint rejected the request (HTTP {status})",
                )
            return (
                "http_error",
                f"MCP endpoint returned HTTP {status}; check endpoint and service availability",
            )
    for item in errors:
        if isinstance(item, (TimeoutError, httpx.TimeoutException)):
            return "connection_timeout", "MCP connection or call timed out"
        if isinstance(item, SchemaError):
            return "schema_mismatch", "Discovered MCP tool schema is invalid"
        if isinstance(item, HostSetupError):
            return "capability_setup", str(item)
        if isinstance(item, httpx.TransportError):
            return (
                "transport_error",
                "MCP transport connection failed; check endpoint and connectivity",
            )
    return (
        "connection_failed",
        "MCP setup or execution failed; inspect configuration and saved run without printing credentials",
    )


async def run_host(
    run_path: Path, profiles: dict, connection: dict, *, discovery_output: Path | None = None
) -> dict:
    # Optional imports keep the core engine and Codex relay dependency-free.
    import httpx
    from configuration_run import load_document
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client
    from mcp_discovery import discover, discovery_targets

    allowed = {}
    targets = (
        discovery_targets(load_json(run_path))
        if discovery_output
        else load_document(run_path)["run"]["targets"]
    )
    for target in targets:
        profile = profiles.get(target["target_id"], {})
        McpTargetAdapter(target, profile, None)  # Validate every profile before connecting.
        prefix = profile["tool_prefix"]
        allowed[prefix + "gtm_workspace"] = {"get", "getStatus"}
        allowed[prefix + "gtm_container"] = {"get"}
        for family, config in profile["families"].items():
            actions = (
                set(config["actions"]) & {"get", "list"} if discovery_output else config["actions"]
            )
            allowed.setdefault(prefix + FAMILIES[family][0], set()).update(actions)
    transport = None
    started = time.monotonic()
    try:
        async with AsyncExitStack() as stack:
            if connection["transport"] == "stdio":
                errors = stack.enter_context(open(os.devnull, "w", encoding="utf-8"))
                parameters = StdioServerParameters(
                    **{key: connection[key] for key in ("command", "args", "env", "cwd")}
                )
                streams = await stack.enter_async_context(stdio_client(parameters, errlog=errors))
            elif connection["transport"] == "http":
                client = await stack.enter_async_context(
                    httpx.AsyncClient(
                        headers=connection["headers"],
                        timeout=connection["timeout"],
                        follow_redirects=False,
                    )
                )
                streams = await stack.enter_async_context(
                    streamable_http_client(connection["url"], http_client=client)
                )
            else:
                streams = await stack.enter_async_context(
                    sse_client(
                        connection["url"],
                        headers=connection["headers"],
                        timeout=connection["timeout"],
                        sse_read_timeout=connection["timeout"],
                    )
                )
            session = await stack.enter_async_context(
                ClientSession(
                    streams[0],
                    streams[1],
                    read_timeout_seconds=timedelta(seconds=connection["timeout"]),
                )
            )
            await session.initialize()
            tools, cursor, cursors = {}, None, set()
            while True:
                page = await session.list_tools(cursor=cursor)
                for tool in page.tools:
                    if tool.name in tools:
                        raise HostSetupError("MCP discovery returned duplicate tool names")
                    tools[tool.name] = tool
                cursor = page.nextCursor
                if not cursor:
                    break
                if cursor in cursors:
                    raise HostSetupError("MCP discovery repeated a pagination cursor")
                cursors.add(cursor)
            tools = {
                name: value
                for name, value in tools.items()
                if name not in connection["exclude_tools"]
                and (connection["include_tools"] is None or name in connection["include_tools"])
            }
            transport = SdkTransport(
                session, asyncio.get_running_loop(), tools, allowed, connection["timeout"]
            )
            if discovery_output:
                return await asyncio.to_thread(
                    discover, load_json(run_path), profiles, transport, discovery_output
                )
            return await asyncio.to_thread(execute, run_path, profiles, transport)
    except Exception as exc:
        writes = transport.writes_attempted if transport else 0
        code, message = connection_diagnostic(exc)
        return {
            "status": "Interrupted" if writes else "Blocked",
            "error": message,
            "error_code": code,
            "mcp_calls": transport.calls if transport else 0,
            "writes_attempted": writes,
            "execution_seconds": round(time.monotonic() - started, 3),
            "next_action": "Read back any attempted write before resuming"
            if writes
            else "Resolve connection or capability setup",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("claude", "gemini"), required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--server", required=True)
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument(
        "--approval-settings",
        type=Path,
        help="Trusted host effective project-server approval settings; required for Claude .mcp.json",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", type=Path)
    mode.add_argument("--discover", type=Path, help="Read-only approved-target input")
    parser.add_argument("--output", type=Path, help="Preparation inventory output; discovery only")
    parser.add_argument("--profiles", type=Path, required=True)
    args = parser.parse_args()
    if bool(args.discover) != bool(args.output):
        parser.error("--discover requires --output; --run does not use --output")
    input_path = args.discover or args.run
    try:
        validate_output_paths(
            inputs=[
                input_path,
                args.profiles,
                args.config,
                *([args.approval_settings] if args.approval_settings else []),
            ],
            outputs=[
                input_path.with_suffix(".execution.json"),
                args.output if args.discover else input_path.with_suffix(".md"),
            ],
        )
    except ValueError as exc:
        parser.error(str(exc))
    # SDK/server error strings can contain authentication URLs or raw responses.
    logging.disable(logging.CRITICAL)
    try:
        connection = load_connection(
            args.config, args.host, args.server, args.project_dir, args.approval_settings
        )
        result = asyncio.run(
            run_host(input_path, load_json(args.profiles), connection, discovery_output=args.output)
        )
    except HostSetupError as exc:
        result = {"status": "Blocked", "error": str(exc), "writes_attempted": 0}
    except ImportError:
        result = {
            "status": "Blocked",
            "error": "Install scripts/requirements-mcp.txt in this Python environment",
            "writes_attempted": 0,
        }
    except Exception:
        result = {
            "status": "Blocked",
            "error": "Invalid local input; validate the run, profiles and selected server definition",
            "writes_attempted": 0,
        }
    write_json_atomic(input_path.with_suffix(".execution.json"), result)
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result["status"] in {"Configured", "Discovered"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
