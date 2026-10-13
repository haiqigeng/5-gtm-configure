# Custom adapter protocol

## One execution engine

All adapters implement `identity`, `read`, `mutate`, `list_resource_page` and
`list_workspace_changes_page` for `gtm_configure.runtime.engine.TargetAdapterRegistry`. The runtime owns
pagination receipts, drift checks, write checkpoints, recovery, comparisons and finalization.
Adapters transport and normalize authenticated observations; they do not decide success.

Identity is read from authenticated workspace and container metadata, including container type,
and must match the authorized target at each execution boundary. Never substitute caller-assigned
identity. Discover get/list/create/update/remove per family independently; unsupported actions
block only their dependency subtree. Client and Transformation support does not follow from tag
support. Scope is governed by [utility-contract.md](../core/authority.md).

Native inventories retain each family's real identity: built-in variable `type`, destination
`destinationLinkId`, Google tag configuration `gtagConfigId`, container `containerId`, and
workspace `workspaceId`. Container settings expose only the authorized Container singleton;
workspace listings may include siblings for name conflict detection, but the selected workspace
must match the authorized target. These identities do not extend semantic-reference resolution.
Google tag configurations have no native name: keep the approved operation label local to the
comparison graph and retain the saved native ID and workspace scope for final identity lookup.
Exhausted listings still establish named-family conflicts; missing identity evidence cannot be
replaced by a targeted GET. A partial native body can use a targeted GET after identity proof.

## Baseline and references

### Protocol return shapes

The protocol is defined in `scripts/gtm_configure/runtime/engine.py` and
`runtime/adapter_protocol.py`. Return these structures; never print raw replies:

| Method | Return value |
| --- | --- |
| `identity()` | Exactly `account_id`, `container_id`, `workspace_id`, `container_type`, all strings from authenticated metadata |
| `list_resource_page(family, cursor)` | `{"items": [native_object], "next_cursor": null}`; use a continuation cursor until pagination is exhausted |
| `list_workspace_changes_page(cursor)` | The same page structure, containing native workspace-change records |
| `read(operation)` | `{"objects": [native_object_with_context, ...]}` or `null` only when confirmed absent |
| `mutate(operation)` | A complete authoritative readback graph, or `null` to request a separate read; raise `AmbiguousWriteError` when dispatch may have applied |

In a readback graph annotate each native body with `target_id` and `object_type`, preserving
its native `type`, native ID, and all material configuration fields. Include referenced trigger,
folder, and sequencing objects needed to resolve IDs. A mutation receives the operation record;
send only its native intended snapshot through the selected API, never its assertions or journal.
Register the adapter with `TargetAdapterRegistry.register(target, adapter, capabilities)` where
capabilities map each inspected family to supported actions such as `{"folder": {"list": true,
"get": true, "update": true}}`. These declarations do not replace authenticated discovery.

For isolated work, exhaust each planned family and its required dependency/consumer families once.
Google Configuration/Event Settings and UPD creation, and updates to existing variables, require
the complete tag/variable inventory to trace indirect consumers. Recheck this consumer closure
immediately before mutation. Refonte
requires all supported families, including empty ones. Record pre-existing workspace changes
separately. Capture baseline evidence through the runtime rather than authoring receipts.

Analyze reuse and closure locally. Immediately before a write re-read the target; refresh shared
consumers where applicable. After writing read back the object. A conflict, external change,
authentication change or pagination anomaly can justify refreshing a family; avoid repeated full
inventory reads during routine work. The current MCP adapter still relists the affected family
before each create to establish fresh absence; it does not infer absence from a stale baseline.
Updates/removals use the fingerprint from the latest read, not the original planning snapshot.
Identity is checked when registering a target, starting baseline capture, immediately before each
mutation and once per target during final convergence. Baseline objects
may supply IDs for reuse, followed by fresh scoped gets; they never substitute for current object
contents, fresh create-absence proof, or the final no-op convergence pass.

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
Retry-After. Authentication failure stops the affected target, not unrelated authorized targets. Repair that
connection; never fall back to another visible account or container.
Do not drop an unsupported intended field merely to make the tool accept the payload.

A malformed, missing-ID or scope-inconsistent mutation reply is also an ambiguous outcome after
dispatch. Recover using a fresh authoritative read, retaining uncertainty if that read cannot prove
the result. Response validation must not turn a potentially applied write into a non-applied failure.
Pre-write comparison canonicalizes keyed Parameter arrays/maps with the same rules as saved-state
comparison; meaningful ordered lists, unknown fields and secret-presence checks remain enforced.

Preserve pre-existing workspace changes. `workspaces.getStatus` is a view since the base version,
not attribution to this run or proof of correctness. Use baseline status plus the operation journal
for attribution, and saved-object comparisons plus fresh read-only convergence for acceptance.
The runtime rechecks every required operation and derives Configured only on a complete no-op pass.

Restore or remove only within existing explicit authority; a partial result needs a precise recovery
boundary. Publication is never a way to make workspace changes visible. The
[run reference](../core/execution.md) owns all state transitions.

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
