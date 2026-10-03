"""Bounded in-memory MCP transport over one host-owned worker session."""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
from typing import Any
from uuid import uuid4

from adapter_support import AdapterExecutionError, AmbiguousWriteError
from redaction import contains_redacted, sensitive_paths
from strict_json import loads_strict

CHUNK_SIZE = 4096
MAX_HEX_SIZE = 64 * 1024 * 1024


def configure_terminal() -> None:
    """Disable Windows terminal echo and cooked-input truncation before any data."""
    if not sys.stdin.isatty():
        return
    if os.name != "nt":
        raise RuntimeError(
            "The packaged interactive relay supports Windows terminals; bind another host through the adapter protocol"
        )
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel.GetStdHandle.restype = wintypes.HANDLE
    kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    handle = kernel.GetStdHandle(-10)
    mode = wintypes.DWORD()
    if not kernel.GetConsoleMode(handle, ctypes.byref(mode)) or not kernel.SetConsoleMode(
        handle, mode.value & ~7
    ):
        raise RuntimeError("Cannot establish a non-echoing worker terminal")


class StdioTransport:
    """Requests use bounded acknowledged chunks; replies never pass through a file or shell."""

    def __init__(self, *, timeout: float = 180, input_stream=None, output_stream=None):
        if timeout <= 0:
            raise ValueError("MCP call timeout must be positive")
        self.timeout = timeout
        self.output = output_stream or sys.stdout
        self.input = input_stream or sys.stdin.buffer
        self.input_fd = sys.stdin.fileno() if input_stream is None else None
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.calls = 0
        self.writes_attempted = 0
        self.deadline = 0.0
        self.reader = threading.Thread(target=self._read_input, daemon=True)
        self.reader.start()

    def _read_input(self) -> None:
        line = bytearray()
        while True:
            byte = os.read(self.input_fd, 1) if self.input_fd is not None else self.input.read(1)
            if not byte:
                self.lines.put(None)
                return
            if byte in {b"\r", b"\n"}:
                if line:
                    self.lines.put(line.decode("ascii", errors="replace"))
                    line.clear()
            else:
                line.extend(byte)
                if len(line) > MAX_HEX_SIZE:
                    self.lines.put(None)
                    return

    def _line(self) -> str:
        try:
            value = self.lines.get(timeout=max(0, self.deadline - time.monotonic()))
        except queue.Empty as exc:
            raise AmbiguousWriteError(
                "MCP host response timed out; read back before retry"
            ) from exc
        if value is None or value == "STOP":
            raise AmbiguousWriteError("MCP host session ended; read back before retry")
        return value

    def __call__(
        self, tool: str, arguments: dict, *, public_identifier_paths: set[str] | None = None
    ) -> Any:
        try:
            return self._exchange(tool, arguments, public_identifier_paths=public_identifier_paths)
        except AmbiguousWriteError as exc:
            if arguments.get("action") not in {"create", "update", "remove"}:
                raise AdapterExecutionError(
                    "MCP read transport failed", code="read_failed"
                ) from exc
            raise

    def _exchange(
        self, tool: str, arguments: dict, *, public_identifier_paths: set[str] | None = None
    ) -> Any:
        if arguments.get("action") in {"create", "update", "remove"} and (
            sensitive_paths(arguments, public_identifier_paths=public_identifier_paths)
            or contains_redacted(arguments)
        ):
            raise AdapterExecutionError(
                "Sensitive mutation fields require an explicitly bound secret provider; no write was dispatched"
            )
        identifier = uuid4().hex
        self.deadline = time.monotonic() + self.timeout
        payload = (
            json.dumps({"id": identifier, "tool": tool, "arguments": arguments}, ensure_ascii=False)
            .encode("utf-16-be")
            .hex()
        )
        if len(payload) > MAX_HEX_SIZE:
            raise AdapterExecutionError(
                "MCP request exceeds the documented in-memory transport limit"
            )
        parts = (len(payload) + CHUNK_SIZE - 1) // CHUNK_SIZE
        for part, start in enumerate(range(0, len(payload), CHUNK_SIZE), 1):
            print(
                f"MCP1 {identifier} {part}/{parts} {payload[start : start + CHUNK_SIZE]} END",
                file=self.output,
                flush=True,
            )
            if part < parts and self._line() != "NEXT":
                raise AmbiguousWriteError("Invalid host chunk acknowledgement")
        self.calls += 1
        if arguments.get("action") in {"create", "update", "remove"}:
            self.writes_attempted += 1
        chunks = []
        length = 0
        while True:
            line = self._line()
            if line == ".":
                break
            length += len(line)
            if length > MAX_HEX_SIZE:
                raise AmbiguousWriteError(
                    "MCP response exceeds the documented in-memory transport limit"
                )
            chunks.append(line)
        try:
            reply = loads_strict(bytes.fromhex("".join(chunks)).decode("utf-16-be"))
        except (ValueError, UnicodeError) as exc:
            raise AmbiguousWriteError("Invalid host response encoding") from exc
        if not isinstance(reply, dict) or reply.get("id") != identifier:
            raise AmbiguousWriteError("MCP response identity mismatch")
        if "error" in reply:
            from mcp_adapter import unwrap

            unwrap(
                {"isError": True, "structuredContent": {"error": reply["error"]}},
                mutation=arguments.get("action") in {"create", "update", "remove"},
            )
            raise AmbiguousWriteError("MCP host call failed; read back before retry")
        if "result" not in reply:
            raise AmbiguousWriteError("MCP response has no result")
        return reply["result"]


def completion(result: dict) -> None:
    payload = json.dumps(result, ensure_ascii=True).encode("utf-16-be").hex()
    print("DONE " + payload + " END", flush=True)
