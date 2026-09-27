#!/usr/bin/env python3
"""GTM MCP transport for the existing adapter runtime; queue files are always redacted."""

from __future__ import annotations

import argparse
import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from adapter_support import AdapterExecutionError, AmbiguousWriteError, collect_paginated
from diff_object_graph import BUILT_IN_TRIGGER_IDS, REFERENCE_FIELDS, ROOT_METADATA_KEYS
from redaction import contains_redacted, redact_for_persistence, sensitive_paths
from strict_json import load_json, loads_strict, write_json_atomic

FAMILIES = {
    "tag": ("gtm_tag", "tagId"),
    "trigger": ("gtm_trigger", "triggerId"),
    "variable": ("gtm_variable", "variableId"),
    "folder": ("gtm_folder", "folderId"),
    "client": ("gtm_client", "clientId"),
    "transformation": ("gtm_transformation", "transformationId"),
    "template": ("gtm_template", "templateId"),
    "zone": ("gtm_zone", "zoneId"),
}


def unwrap(response: Any) -> Any:
    if not isinstance(response, dict):
        raise AdapterExecutionError("MCP result must be an object")
    if response.get("isError"):
        # A tool error does not establish that a write was rejected before application.
        raise AmbiguousWriteError("MCP reported an error; read back before retry")
    if "structuredContent" in response:
        return response["structuredContent"]
    if "content" in response:
        texts = [item["text"] for item in response["content"] if item.get("type") == "text"]
        if len(texts) != 1:
            raise AdapterExecutionError("Expected one JSON MCP content block")
        return loads_strict(texts[0])
    return response


def select(value: Any, path: list[str]) -> Any:
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise AdapterExecutionError("MCP response differs from discovered response path")
        value = value[key]
    return value


class QueueTransport:
    """One sequential caller, unique IDs, bounded wait, no raw credential queue writes."""

    def __init__(self, directory: Path, *, timeout: float = 120):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout

    def __call__(self, tool: str, arguments: dict) -> dict:
        if sensitive_paths(arguments) or contains_redacted(arguments):
            raise AdapterExecutionError(
                "Credential-bearing mutations require a secure in-memory adapter; queue transport cannot preserve secret values"
            )
        identifier = uuid4().hex
        request = self.directory / f"{identifier}.request.json"
        response = self.directory / f"{identifier}.response.json"
        write_json_atomic(request, {"id": identifier, "tool": tool, "arguments": arguments})
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if response.is_file():
                result = load_json(response)
                if result.get("id") != identifier:
                    raise AdapterExecutionError("Queue response identity mismatch")
                response.unlink()
                request.unlink(missing_ok=True)
                if result.get("error"):
                    raise AmbiguousWriteError("Relay failed; read back before retry")
                return result["result"]
            time.sleep(0.05)
        # Remove undispatched work. A relay that already took it may have written;
        # classify the outcome as ambiguous in both cases.
        request.unlink(missing_ok=True)
        raise AmbiguousWriteError("MCP relay deadline exceeded; read back before retry")


class McpTargetAdapter:
    """Map discovered MCP schemas to the runtime protocol without client-specific code.

    Profile response paths and pagination must come from inspected tool responses.
    Intentions use native GTM fields; no invented aliases or lossy projection is applied.
    """

    def __init__(self, target: dict, profile: dict, call: Callable[[str, dict], dict]):
        self.target = target
        self.profile = profile
        self.call = call
        self.cache: dict[str, list[dict]] = {}
        self.known_ids: dict[str, str] = {}

    def _call(self, tool: str, action: str, **extra: Any) -> Any:
        if action not in {"get", "list", "create", "update", "remove", "getStatus"}:
            raise AdapterExecutionError("Unsupported MCP action")
        arguments = {
            "accountId": self.target["account_id"],
            "containerId": self.target["container_id"],
            "action": action,
        }
        if tool != "gtm_container":
            arguments["workspaceId"] = self.target["workspace_id"]
        arguments.update(extra)
        return unwrap(self.call(self.profile["tool_prefix"] + tool, arguments))

    def identity(self) -> dict[str, str]:
        workspace = select(self._call("gtm_workspace", "get"), self.profile["workspace_path"])
        container = select(self._call("gtm_container", "get"), self.profile["container_path"])
        usage = container.get("usageContext")
        if usage not in (["web"], ["server"]):
            raise AdapterExecutionError("Unsupported authenticated container usageContext")
        if any(
            str(workspace.get(key)) != str(container.get(key))
            for key in ("accountId", "containerId")
        ):
            raise AdapterExecutionError("Workspace and container identities disagree")
        return {
            "account_id": str(workspace["accountId"]),
            "container_id": str(workspace["containerId"]),
            "workspace_id": str(workspace["workspaceId"]),
            "container_type": usage[0],
        }

    def capabilities(self) -> dict:
        return {
            family: {
                action: action in config["actions"]
                for action in ("get", "list", "create", "update", "remove")
            }
            for family, config in self.profile["families"].items()
            if family in FAMILIES
        }

    def list_resource_page(self, resource_family: str, cursor: str | None) -> dict:
        tool, _ = FAMILIES[resource_family]
        config = self.profile["families"][resource_family]
        if (
            type(config["page_size"]) is not int
            or config["page_size"] < 1
            or config["first_page"] not in (0, 1)
        ):
            raise AdapterExecutionError("Invalid discovered pagination configuration")
        page = int(cursor) if cursor is not None else config["first_page"]
        result = self._call(tool, "list", page=page, itemsPerPage=config["page_size"])
        items = select(result, config["list_path"])
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise AdapterExecutionError("Discovered list path must contain objects")
        if len(items) > config["page_size"]:
            raise AdapterExecutionError("MCP ignored discovered page size; exhaustion is unproved")
        for item in items:
            self._check_scope(item)
        if cursor is None:
            self.cache[resource_family] = []
        self.cache[resource_family].extend(deepcopy(items))
        # Exhaustion requires an empty/short page; a full final page costs one extra read.
        return {
            "items": items,
            "next_cursor": str(page + 1) if len(items) == config["page_size"] else None,
        }

    def list_workspace_changes_page(self, cursor: str | None) -> dict:
        if cursor is not None:
            raise AdapterExecutionError("getStatus is not paginated")
        status = select(self._call("gtm_workspace", "getStatus"), self.profile["status_path"])
        if status.get("mergeConflict"):
            raise AdapterExecutionError("Workspace has unresolved merge conflicts")
        return {"items": status.get("workspaceChange", []), "next_cursor": None}

    def _check_scope(self, raw: dict) -> None:
        for field, target_field in (
            ("accountId", "account_id"),
            ("containerId", "container_id"),
            ("workspaceId", "workspace_id"),
        ):
            if field in raw and str(raw[field]) != str(self.target[target_field]):
                raise AdapterExecutionError("MCP object belongs to another target")

    def _find(self, operation: dict) -> dict | None:
        family = operation["resource_family"]
        tool, id_field = FAMILIES[family]
        config = self.profile["families"][family]
        identifier = operation.get("object_id") or self.known_ids.get(operation["object_key"])
        # Listing by exact identity also gives authoritative absence after removal.
        if not identifier or operation["action"] == "remove":
            items = collect_paginated(lambda cursor: self.list_resource_page(family, cursor))
            matches = [
                item
                for item in items
                if (
                    str(item.get(id_field)) == identifier
                    if identifier
                    else item.get("name") == operation["name"]
                )
            ]
            if len(matches) > 1:
                raise AdapterExecutionError("Ambiguous GTM object identity")
            if not matches:
                return None
            identifier = str(matches[0][id_field])
        raw = select(self._call(tool, "get", **{id_field: identifier}), config["object_path"])
        if not isinstance(raw, dict) or str(raw.get(id_field)) != identifier:
            raise AdapterExecutionError("Readback object ID differs from requested object")
        self._check_scope(raw)
        self.known_ids[operation["object_key"]] = identifier
        return raw

    def read(self, operation: dict) -> dict | None:
        raw = self._find(operation)
        if raw is None:
            return None
        context = []
        for family, items in self.cache.items():
            for item in items:
                if item.get("name") != raw.get("name") or family != operation["resource_family"]:
                    context.append(
                        {**item, "target_id": operation["target_id"], "object_type": family}
                    )
        return {
            "objects": [
                {
                    **raw,
                    "target_id": operation["target_id"],
                    "object_type": operation["resource_family"],
                }
            ],
            "context_objects": context,
        }

    def mutate(self, operation: dict) -> dict | None:
        family = operation["resource_family"]
        tool, id_field = FAMILIES[family]
        action = operation["action"]
        if action == "replace":
            raise AdapterExecutionError(
                "MCP replacement requires a dedicated adapter with recovery for both boundaries"
            )
        action = "update" if action in {"rename", "pause", "unpause"} else action
        if (
            action not in {"create", "update", "remove"}
            or action not in self.profile["families"][family]["actions"]
        ):
            raise AdapterExecutionError("Undiscovered mutation capability")
        arguments = {}
        if action != "create":
            arguments[id_field] = operation["object_id"]
            fingerprint = operation.get("pre_change", {}).get("fingerprint")
            if fingerprint:
                arguments["fingerprint"] = fingerprint
        if action != "remove":
            intended = {
                key: deepcopy(value)
                for key, value in operation["intended"].items()
                if key not in ROOT_METADATA_KEYS | {"target_id", "object_type"}
            }
            intended["name"] = operation.get("new_name", operation["name"])
            for field, reference_id in REFERENCE_FIELDS.items():
                if field not in intended:
                    continue

                def resolve(value):
                    if value in BUILT_IN_TRIGGER_IDS:
                        return value
                    for ref_family, items in self.cache.items():
                        for item in items:
                            if value in {
                                str(item.get(reference_id)),
                                f"{operation['target_id']}::{ref_family}::{item.get('name')}",
                            } and item.get(reference_id):
                                return str(item[reference_id])
                    if value in self.known_ids:
                        return self.known_ids[value]
                    raise AdapterExecutionError("Unresolved GTM reference")

                value = intended[field]
                intended[field] = (
                    [resolve(item) for item in value] if isinstance(value, list) else resolve(value)
                )
            arguments["createOrUpdateConfig"] = intended
        result = self._call(tool, action, **arguments)
        if action != "remove":
            raw = select(result, self.profile["families"][family]["object_path"])
            self._check_scope(raw)
            self.known_ids[operation["object_key"]] = str(raw[id_field])
            self.cache.setdefault(family, [])[:] = [
                item
                for item in self.cache.get(family, [])
                if str(item.get(id_field)) != str(raw[id_field])
            ] + [deepcopy(raw)]
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["next", "reply"])
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument(
        "--stream", action="store_true", help="Read UTF-16 hex lines ending with a dot"
    )
    args = parser.parse_args()
    if args.action == "next":
        requests = sorted(args.queue.glob("*.request.json"))
        if requests:
            request = requests[0]
            claimed = request.with_suffix(".claimed")
            request.rename(claimed)
            print(json.dumps(load_json(claimed)))
        else:
            print("null")
    else:
        import sys

        if args.stream:
            import os

            if os.name == "nt" and sys.stdin.isatty():
                import ctypes
                from ctypes import wintypes

                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.GetStdHandle.argtypes = [wintypes.DWORD]
                kernel.GetStdHandle.restype = wintypes.HANDLE
                kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
                kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
                handle = kernel.GetStdHandle(-10)
                mode = wintypes.DWORD()
                if not kernel.GetConsoleMode(
                    handle, ctypes.byref(mode)
                ) or not kernel.SetConsoleMode(handle, mode.value & ~7):
                    raise RuntimeError("Cannot disable console input echo")
            print("STREAM_READY", flush=True)
            chunks = []
            line = bytearray()
            while True:
                byte = sys.stdin.buffer.read(1)
                if not byte:
                    raise ValueError("Incomplete streamed response")
                if byte in {b"\r", b"\n"}:
                    if line == b".":
                        break
                    chunks.append(bytes(line))
                    line.clear()
                else:
                    line.extend(byte)
            payload = bytes.fromhex(b"".join(chunks).decode("ascii")).decode("utf-16-be")
        else:
            payload = sys.stdin.buffer.read().decode("utf-8")
        record = loads_strict(payload)
        identifier = record.get("id", "")
        if len(identifier) != 32 or any(char not in "0123456789abcdef" for char in identifier):
            raise ValueError("Invalid queue ID")
        claimed = args.queue / f"{identifier}.request.claimed"
        if not claimed.exists():
            raise ValueError("No claimed request for response")
        if "result" in record:
            try:
                record["result"] = redact_for_persistence(unwrap(record["result"]))
            except (AdapterExecutionError, ValueError):
                record = {
                    "id": identifier,
                    "error": "MCP response error; application status unknown",
                }
        record = redact_for_persistence(record)
        write_json_atomic(args.queue / f"{identifier}.response.json", record)
        claimed.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
