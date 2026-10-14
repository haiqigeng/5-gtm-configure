# Codex MCP relay

Use [the inspected profile](mcp-profile.md). Install `scripts/requirements.txt` in the selected Python environment once.

The comparison/runtime Python modules are portable; this packaged relay specifically requires
Codex on Windows, `functions.exec`, its `exec_command`/`write_stdin` session tools, Python 3.11+, and PowerShell
7+. Discover the actual Python executable, confirm `pwsh` is available, inspect callable MCP schemas,
and validate the complete target profiles before execution. Node is required for repository relay
tests, not for running the relay in Codex. Claude Code and Gemini CLI use [the SDK runner](mcp-sdk.md);
a connected MCP alone does not establish an executable path for other hosts.

Load `scripts/mcp_relay.js` into one `functions.exec` call with absolute `pythonPath`, `scriptPath`
(pointing to `scripts/configure_gtm.py`), `runPath` and `profilesPath` bindings. It starts one worker,
services ordered requests through its stdin/stdout session, and returns sanitized completion
metadata. One relay owns one run and starts its worker directly, using in-memory request/reply exchange. The relay uses PowerShell only to launch fixed local executable paths, encoded
as data; MCP responses never enter a shell command. Stop on unsupported required capabilities.

Requests use acknowledged 4096-character hex chunks so large objects do not rely on one tool-output
budget. Replies use a non-echoing stream; raw data stays in memory until complete relevant baseline
and readback graphs are classified and redacted. The bound is 64 MiB of hex per request/reply
(16 Mi UTF-16 code units), with a default 180-second call timeout and 1800-second run deadline.
For a measured large-object requirement, set positive `callTimeoutSeconds` and `runTimeoutSeconds`
before launch. A timeout/interruption requires inspecting run evidence and fresh readback before
retry under [execution recovery](../core/execution.md#resume-only-from-proved-state). The relay stops its worker on relay failure.

The worker writes a sanitized `<run>.execution.json` diagnostic. A setup/read failure before any
mutation is `Blocked`; an interrupted session after an attempted mutation says to inspect the
run and read back. Within the run, an operation uses the existing `failed` or `uncertain` state;
`Blocked` is a requirement/target/run verdict, not a new operation state.

Credential-bearing mutations remain unavailable through this relay: bind a separately verified
secure provider in an adapter that can handle the real destination/host requirements. See
[secret handling](../core/execution.md#credential-findings-and-transport-limits).
Diagnostics use the same sanitized evidence boundary. Host MCP and
session-tool transcripts can retain the original replies or recoverable encoded bytes. Hex is
transport encoding, not encryption, and this skill cannot change host logging or retention.
The local runtime is not an authentication boundary against processes able to edit its code.
