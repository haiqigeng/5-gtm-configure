# Tool adapters

## Contents

- One execution engine
- Packaged MCP adapter
- Baseline and references
- Writes, recovery and convergence
- Import and UI

Prefer a connected GTM MCP, then GTM API, authorized complete export/import, then signed-in UI for
unsupported fields. Inspect current tool schemas and response shapes before building the capability
profile. An available browser is not a reason to abandon a working semantic adapter.

## One execution engine

All adapters implement `identity`, `read`, `mutate`, `list_resource_page` and
`list_workspace_changes_page` for `adapter_runtime.TargetAdapterRegistry`. The runtime owns
pagination receipts, drift checks, write checkpoints, recovery, comparisons and finalization.
Adapters transport and normalize authenticated observations; they do not decide success.

Identity is read from authenticated workspace and container metadata, including container type,
and must match the authorized target at each execution boundary. Never substitute caller-assigned
identity. Discover get/list/create/update/remove per family independently; unsupported actions
block only their dependency subtree. Client and Transformation support does not follow from tag
support. Scope is governed by [utility-contract.md](../01-orientation/utility-contract.md).

## Packaged MCP adapter

`scripts/mcp_queue_adapter.py` supplies `McpTargetAdapter` and `QueueTransport` for the callable GTM
MCP family tools. It supports discovered tag, trigger, variable, folder, Client, Transformation,
template and Zone methods using `createOrUpdateConfig`. Other families and replacement operations
need a protocol adapter that can express and recover their actual boundaries; do not claim those
capabilities in this profile. The existing runtime remains the authority for every adapter.

Configure response paths and numbered pagination from the actual connected MCP response. Do not
copy sample paths without inspection, infer a tool action, or guess a page origin. Use the smallest
legal page size only if the MCP requires it; a full final page requires one further exhaustion read.
The adapter rejects mismatched response structure rather than interpreting it as an empty inventory.
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

Start the worker from the project directory using absolute paths:

```powershell
python "<skill-dir>/scripts/mcp_execute.py" --run configuration-run.json --profiles profiles.json --queue "<new-empty-queue-directory>"
```

Use the host's background execution facility; on Windows a separate `Start-Process` must be hidden.
Then load `scripts/mcp_relay.js` into a `functions.exec` call with absolute `pythonPath`, `scriptPath`
(pointing to `mcp_queue_adapter.py`) and `queuePath` bindings. It services sequential requests in one
bounded relay, emits progress at intervals, and returns completion metadata. Keep reads that can be
batched independent; writes and their dependencies remain ordered. Do not run multiple relays for
one queue. Stop the worker if the relay cannot continue. A fresh queue is required for resume so
stale requests cannot be replayed. Inspect the run and resolve uncertainty before another execution.

The queue contains redacted responses only. Credential-bearing writes cannot use the disk queue;
see [secret handling](configuration-run-and-resume.md#credential-findings-and-transport-limits).
Large replies cross a non-echoing terminal stream to avoid Windows command-line limits; the relay
waits for the receiver's readiness marker before sending any data. Raw response bytes stay in
process memory until the Python redactor writes the response. The host transcript boundary still
applies. A relay deadline or delivery failure requires stopping the worker and inspecting the run.
The transport is a bridge inside the authorized local execution environment, not an authentication
boundary against a process that can edit its files or code. The host still controls tool access.

## Baseline and references

For isolated work, exhaust each planned family and its required dependency/consumer families once.
Shared Google Configuration Settings changes require the complete tag consumer inventory. Refonte
requires all supported families, including empty ones. Record pre-existing workspace changes
separately. Capture baseline evidence through the runtime rather than authoring receipts.

Analyze reuse and closure locally. Immediately before a write re-read the target; refresh shared
consumers where applicable. After writing read back the object. A conflict, external change,
authentication change or pagination anomaly can justify refreshing a family; avoid repeated full
inventory reads during routine work.

Annotate canonical records with `object_type`; preserve raw GTM `type`. Keep GTM Parameter `map`
entries keyed and unique, and `list` entries ordered. Normalize only documented root metadata.
Retain every material field; an unrepresented field is not equality evidence. Include referenced
triggers, folders and setup/cleanup tags as comparison context. Only the three reserved web trigger
IDs may remain without listed objects: `2147479553`, `2147479572`, `2147479573`. Resolve every other
ID exactly; ambiguous or missing references block comparison.

## Writes, recovery and convergence

The runtime performs fresh pre-write comparisons, journals `in_progress`, then saves and reads back.
A create collision cannot become an overwrite. Never retry an ambiguous write until authoritative
readback resolves it. Bounded retries apply only to documented non-applied rate limits; respect
Retry-After. Authentication failure stops the affected target, not unrelated authorized targets.
Do not drop an unsupported intended field merely to make the tool accept the payload.

Preserve pre-existing workspace changes. `workspaces.getStatus` is a view since the base version,
not attribution to this run or proof of correctness. Use baseline status plus the operation journal
for attribution, and saved-object comparisons plus fresh read-only convergence for acceptance.
The runtime rechecks every required operation and derives Configured only on a complete no-op pass.

Restore or remove only within existing explicit authority; a partial result needs a precise recovery
boundary. Publication is never a way to make workspace changes visible. The
[run reference](configuration-run-and-resume.md) owns all state transitions.

## Import and UI

An import must target the dedicated workspace, preserve the complete intended schema and avoid
unapproved overwrite/deletion. In the UI verify account/container/workspace, save one logical object,
reopen it, and report any unverified fields. Neither path may Submit, Publish or Create Version.
Unavailable write or verification capability is a specific Blocked requirement, not a successful
specification.

## Official entry points

- https://developers.google.com/tag-platform/tag-manager/api/v2
- https://developers.google.com/tag-platform/tag-manager/api/reference/rest/v2/accounts.containers.workspaces/getStatus
- https://developers.google.com/tag-platform/tag-manager/api/reference/rest/v2/accounts.containers.workspaces.tags
- https://developers.google.com/tag-platform/tag-manager/api/reference/rest/v2/accounts.containers.workspaces.clients
- https://developers.google.com/tag-platform/tag-manager/api/reference/rest/v2/accounts.containers.workspaces.transformations
