# Claude Code and Gemini CLI

## Claude Code and Gemini CLI

Use `scripts/configure_gtm.py mcp-host` from the host's ordinary shell tool. It connects through the
official MCP Python SDK and calls the same adapter and execution engine as the Codex relay.
Install the optional dependency in the selected Python environment once:

```text
python -m pip install -r "<skill-dir>/scripts/requirements-mcp.txt"
python "<skill-dir>/scripts/configure_gtm.py" mcp-host --host claude --config "<selected-config.json>" --server "<exact-server-name>" --project-dir "<project-root>" --run "<run.json>" --profiles "<profiles.json>"
```

For Gemini, change `--host claude` to `--host gemini`. All file paths should be absolute. Select
one already authorized `mcpServers` definition; the runner does not merge user/project/managed
configuration scopes. Select it within the effective host restrictions, admin policy and project trust.
For Claude project `.mcp.json`, also pass `--approval-settings "<effective-approvals.json>"`
containing the applicable settings already resolved by the trusted host. The runner requires
`enabledMcpjsonServers` to include the selected name or `enableAllProjectMcpServers: true`;
an explicit rejection always wins. A repository's own `.mcp.json` cannot approve itself.
The runner does not reconstruct Claude's workspace-trust or managed-settings precedence;
the invoking agent must inspect those restrictions before supplying the effective settings.

Supported definitions follow the current [Claude MCP configuration](https://code.claude.com/docs/en/mcp)
and [Gemini MCP configuration](https://geminicli.com/docs/tools/mcp-server/):

| Transport | Claude entry | Gemini entry |
| --- | --- | --- |
| stdio | `command`, optional `args`, `env`, `cwd` | same fields |
| Streamable HTTP | `type: "http"` or `"streamable-http"`, `url`, optional `headers` | `httpUrl`, optional `headers` |
| SSE | `type: "sse"`, `url`, optional `headers` | `url`, optional `headers` |

The runner resolves documented environment references, honors supplied disabled/excluded server
controls and `includeTools`/`excludeTools`, then discovers MCP tools and validates every call
against its input schema. Profiles use the server's actual wire tool names: normally
`tool_prefix: ""`, without the CLI's model-facing MCP namespace. Response paths, families and
pagination still require inspection as above.

This is a separate SDK connection. Host-managed OAuth sessions, `authProviderType` and dynamic
header helpers are unsupported; the runner rejects those definitions instead of reading private
CLI credential stores. Stdio servers may use their own existing authentication, and remote servers
may use configured environment-backed headers. Authentication headers are not GTM payload secret
support: credential-bearing object writes remain blocked without a verified secret provider.

A plain remote URL does not inherit the CLI's OAuth session. For an OAuth-backed server, use an
already authorized self-authenticating stdio connection, such as an installed
[mcp-remote](https://github.com/punkpeye/mcp-remote) proxy, and complete that proxy's sign-in in
the host before running this noninteractive engine. It owns its independently authorized authentication. Alternatively, when the server supports it, configure an environment-backed
`headers` map such as `{"Authorization": "Bearer ${GTM_MCP_TOKEN}"}` on the HTTP/SSE definition.
Credentials stay in the approved environment/secure provider; arguments and persisted artifacts
contain safe references. Anonymous remote servers remain
valid and are not rejected merely because their definitions omit headers.

HTTP 401 is reported as authentication required; HTTP 403 as access denied. Timeout, transport,
missing-tool and schema failures have separate sanitized diagnostics. No challenge URL, headers,
response body or raw exception is printed. These classifications do not authorize automatic retries
of an attempted write. OAuth proxy interoperability with a particular live provider still needs
verification during connection setup.

Raw replies stay in memory; SDK/server diagnostics are suppressed to avoid recording credentials.
The runner writes only sanitized execution diagnostics alongside the run. The configured `timeout`
is milliseconds (default 180000) per call. Inspect the saved run and perform authoritative readback
after any interrupted write; rerunning is not permission to replay an uncertain mutation.

The offline release checks exercise the shared engine and local protocol boundaries. They do not certify
Claude/Gemini model behavior, every authentication deployment or live GTM acceptance.

An app-managed Claude connector with no accessible local server definition cannot currently be
used by this SDK runner. Seeing its tools in chat is not proof that the Python session can reach
them. This route remains unverified until a real authenticated session completes. A host tool bridge or
explicitly configured authenticated connection feeds the same engine to provide its journal,
recovery and convergence guarantees. The selected connection owns its authorization.
