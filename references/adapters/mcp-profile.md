# MCP capability profile

## Packaged MCP adapter

`scripts/gtm_configure/adapters/mcp.py` supplies `McpTargetAdapter` and `scripts/gtm_configure/adapters/transport.py` supplies `StdioTransport` for the callable GTM
MCP family tools. It supports discovered tag, trigger, variable, folder, Client, Transformation,
template and Zone methods using `createOrUpdateConfig`. Other families and replacement operations
need a protocol adapter that can express and recover their actual boundaries; do not claim those
capabilities in this profile. The existing runtime remains the authority for every adapter.

For semantic setup/teardown references, record `sequencing_reference` in the target's MCP profile:
`name` or `tagId`, as established by the inspected connector/native object representation. Google's
[Tag schema](https://developers.google.com/tag-platform/tag-manager/api/reference/rest/v2/accounts.containers.workspaces.tags)
describes `tagName` as a tag name; do not assume an ID-based connector representation from that
label. The adapter resolves a unique same-target tag and writes the inspected representation.
Already-native sequencing values can be retained without this setting after identity resolution;
semantic values without an inspected representation stop before dispatch. Preserve sequencing
flags. This does not change the shared-event-ID route's restriction on sequencing.

The CLIs validate all derived diagnostic/report and requested inventory paths before connection
or execution. Keep these outputs distinct from input, profile, host configuration and approval
files; collisions are refused even when the subsequent setup would fail.

Configure response paths and numbered pagination from the actual connected MCP response. Do not
copy sample paths without inspection, infer a tool action, or guess a page origin. Use the smallest
legal page size only if the MCP requires it; a full final page requires one further exhaustion read.
When the response exposes a continuation Boolean, set `has_more_path` to its inspected path;
it takes precedence over page length. Otherwise use numbered short-page exhaustion only after
confirming that protocol. The adapter rejects mismatched response structure rather than interpreting it as an empty inventory.
Tool errors during mutations are ambiguous until readback establishes the outcome.

A profile file maps each run `target_id` to this shape (illustrative response paths):

```json
{
  "web-main": {
    "tool_prefix": "mcp__gtm__",
    "workspace_path": [],
    "container_path": [],
    "status_path": [],
    "families": {
      "tag": {
        "actions": ["list", "get", "create", "update"],
        "first_page": 1,
        "page_size": 20,
        "list_path": ["tag"],
        "object_path": []
      }
    }
  }
}
```

Add each required family from its inspected schema. The adapter unwraps structured MCP results or
one JSON text block, checks identity, resolves known trigger/folder references and preserves native
GTM fields. Intentions must use the native GTM schema, not a client-specific synthetic field layout.
No hard-coded variable or destination ID belongs in transport code.
