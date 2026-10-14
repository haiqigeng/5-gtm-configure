# Adapter selection

Prefer the connected GTM MCP, then an authorized API, complete export/import or signed-in UI for
unsupported fields. Inspect actual capabilities before selecting a route. All transports feed the
same execution engine.

| Selected transport | Required guide |
| --- | --- |
| Connected MCP in Codex | [MCP profiles](mcp-profile.md) and [Codex relay](codex.md). |
| Authorized local MCP connection in Claude/Gemini | [MCP profiles](mcp-profile.md) and [SDK host](mcp-sdk.md). |
| Custom API, import or UI | [Adapter protocol](custom.md). |

Use [discovery](discovery.md) when fresh preparation inventory is needed and [quotas](quotas.md)
for large runs or typed quota failures.
