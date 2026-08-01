# Tool adapters

## Contents

- [Use a capability-first execution order](#use-a-capability-first-execution-order)
- [Establish tool capabilities before mutation](#establish-tool-capabilities-before-mutation)
- [Discover exact actions and pagination](#discover-exact-actions-and-pagination)
- [Build an object-family capability profile](#build-an-object-family-capability-profile)
- [Translate the change manifest deterministically](#translate-the-change-manifest-deterministically)
- [Apply read-before-write discipline](#apply-read-before-write-discipline)
- [Maintain a current-operation journal](#maintain-a-current-operation-journal)
- [Prove idempotency](#prove-idempotency)
- [Handle authentication, quotas, and uncertain writes](#handle-authentication-quotas-and-uncertain-writes)
- [Handle partial failure](#handle-partial-failure)
- [Use export/import safely](#use-exportimport-safely)
- [Use the UI as a controlled fallback](#use-the-ui-as-a-controlled-fallback)
- [Stop when mutation is unavailable](#stop-when-mutation-is-unavailable)
- [Official entry points](#official-entry-points)

## Use a capability-first execution order

Prefer:

1. a purpose-built GTM MCP connected to the correct Google account;
2. the GTM API with appropriate container/workspace access;
3. an authorized complete export/import path when it can preserve the required workspace schema;
4. the signed-in GTM UI for unavailable operations or visual verification.

Do not open a browser merely because one exists when a connected semantic GTM tool can perform and verify the operation. Do not claim a mutation from an export-only or read-only source.

## Establish tool capabilities before mutation

Confirm whether the selected adapter can:

- list accounts, containers, workspaces, versions, and permissions;
- create/reuse a dedicated workspace;
- read, create, and modify tags, triggers, variables, folders, and templates;
- list or enable required built-in variables;
- inspect Google tag configuration/settings objects and linked destinations;
- inspect applicable Zones, environments, container settings, and their restrictions;
- expose built-in/additional consent settings and blocking triggers;
- inspect references/consumers and workspace conflicts;
- inspect or synchronize workspace state and report merge conflicts without resolving them implicitly;
- expose stable object IDs/paths, fingerprints, firing options, advanced settings, and consent fields;
- re-read saved objects;
- avoid version creation and publication.

Use the UI only for missing semantic fields, unsupported template operations, or visual confirmation. Keep the same target account/container/workspace across adapters.

## Discover exact actions and pagination

Inspect the connected adapter's current schema or capability description before the first operation.
Record exact action names, required arguments, returned object shapes, pagination mechanism and page
limits, stable IDs, fingerprints, supported template/consent fields, and any batch or quota behavior.

Do not guess a generic action alias such as `status`, assume that two object families accept the same
page size, or treat the first page as a complete inventory. Exhaust every relevant page using the
adapter's returned cursor/page token or documented offset semantics. Keep list/readback volume as low
as practical, prefer supported batch reads, and respect throttling/retry guidance without replacing a
complete inventory with a partial one.

Cache the capability profile for the current run and re-check it after an adapter error that indicates
schema drift, unsupported fields, authentication changes, or a different endpoint/version. Never
expose credentials while diagnosing compatibility.

## Build an object-family capability profile

Record `list/read/create/update/revert/readback/pagination` capability independently for workspace,
tag, trigger, user-defined variable, built-in variable, folder, template, Google tag configuration,
destination, Zone, environment, and applicable container settings. Also record whether the action is
valid for a client-side web container and whether it is routine or high-impact.

Do not infer write support from list support. Do not treat a deprecated or absent destination-link
action as authorization to use another endpoint. Do not route server-client or server
Transformation resources into a web-container configuration.

## Translate the change manifest deterministically

Use the operational configuration map as the adapter input. For each object row, resolve:

- stable parent path and intended workspace;
- action, object type, existing ID/path, and current fingerprint;
- exact adapter/template type derived from an official schema or inspected existing object;
- typed parameters, trigger IDs, blocking-trigger IDs, folder, consent settings, priority, schedule, firing option, sequencing, and notes;
- dependencies and creation order;
- complete pre-change representation for every update.

Do not mutate from an informal prose summary. If the adapter cannot represent a required field or
preserve the intended type/shape, stop that object and use another authorized adapter or mark the
affected configuration `Blocked`.

For analytics, use the strict v5 configuration-contract validation, normalized collection contract,
and zero-difference conformance result as adapter preconditions. Keep technical infrastructure fields
separate so the adapter does not mistake a required GTM reference for an approved outgoing
parameter.

## Apply read-before-write discipline

For every adapter:

1. Resolve the target by stable account/container/workspace ID, not display name alone.
2. Read current object state and conflicts.
3. Design the complete dependency graph.
4. Create dependencies before consumers.
5. Re-read every mutation and compare intended versus stored fields.
6. Record returned IDs and fingerprints/version identifiers where available.
7. Stop on a conflict or unexpected consumer rather than overwriting silently.

When complete JSON is available, use `scripts/diff_object_graph.py` as a read-only comparison aid.
Annotate every normalized record with its canonical GTM resource family in `object_type`; do not reuse the raw
GTM `type` field for that annotation because tag, trigger, and variable type codes are material
configuration and must remain comparable.
Normalize only documented server metadata such as top-level fingerprints, paths, generated IDs, and
timestamps. Never ignore nested tag fields, trigger references, consent, template fields, routing,
or configuration values.

Supply the complete in-scope reference closure: include every user-created firing or blocking
trigger, parent folder, and setup/cleanup tag referenced by a compared object. The comparator
recognizes GTM's three reserved web-container triggers (`2147479553`, `2147479572`, and
`2147479573`) directly because trigger-list responses omit them; do not synthesize fake trigger
records. Any other unresolved raw or semantic reference remains invalid comparison input rather
than proof of equality.

Preserve the GTM API `parameter` shape. Top-level keyed parameters and nested `map` entries compare
by their unique keys; nested `list` entries preserve order and ignore their own keys. Do not sort an
ordered list or treat the `monitoringMetadata` Parameter object itself as a set.

Never use a guessed template type code or API parameter. Derive it from the existing object, API schema, official template, or tool response.

## Maintain a current-operation journal

Use the versioned configuration-run artifact as the durable current-operation journal. Before
mutation, snapshot the dedicated workspace identity, synchronization/conflict state, and all pre-
existing workspace changes. For every write, record the requirement ID, action, object path/ID,
pre-change fingerprint and representation when applicable, returned fingerprint, saved result, and
verification status. Persist `in_progress` immediately before the call and atomically checkpoint its
outcome before starting a dependent operation.

Report these separately:

1. pre-existing workspace changes;
2. current-run (current-operation) created, updated, reused, untouched, failed, or explicitly authorized removed objects;
3. final workspace totals and conflicts.

Do not attribute the final workspace total to the current run. Use the journal for partial-failure
recovery and to prove that unrelated work remained untouched.

## Prove idempotency

After all successful saved-object comparisons, rerun the approved-to-saved collection-contract
comparison and recompute the change manifest against the new workspace state. Every completed row
must resolve to `reuse` or `untouched`. A second run that proposes another create or repeats the same
update fails acceptance until matching, equivalence, or stored-field normalization is corrected.

Do not use names alone as idempotency keys. Compare stable IDs where present and the semantic dimensions defined by the naming-and-reuse reference.

## Handle authentication, quotas, and uncertain writes

- On a resumed run, validate and inspect the configuration-run artifact first. Resolve any
  `in_progress` or `uncertain` operation by authoritative readback before a new write.
- Stop immediately on wrong-account, wrong-container, expired-authentication, or permission errors;
  never fall back to another visible container or account.
- Honor documented retry or quota guidance for throttling and transient server errors. Use bounded
  retries and keep the user informed during a long retry window.
- Do not retry a create, update, import, or template operation blindly after a timeout or ambiguous
  response. First list/read back the exact parent workspace and compare stable identity, semantics,
  fingerprints, and saved fields to determine whether the write succeeded.
- Stop dependent writes when readback cannot distinguish success from failure. Record the uncertain
  object and recovery action instead of risking a duplicate.
- Re-discover the adapter capability profile after an unsupported-field or schema-drift error; do
  not remove an intended field merely to make the adapter accept the request.

For a programmatic adapter, `scripts/adapter_runtime.py` provides the tested pagination, bounded
retry, read-before-write, ambiguous-response, dependency-stop, and checkpoint state machine. MCP
and UI runs must apply the same transitions even when they cannot call the helper directly.

## Handle partial failure

If a mutation fails:

- stop dependent writes;
- inventory which objects were created or changed;
- do not delete or roll back unrelated user work;
- repair only the objects created or changed by the current authorized operation when safe;
- restore a modified pre-existing object only when its exact pre-change state was captured and restoration remains within the authorized operation; otherwise preserve the partial state and report it;
- remove an object only when the current authorization explicitly includes rollback or deletion and its ownership is confirmed;
- report the partial state and exact blocker.

Do not publish to make an API/MCP change visible.

## Use export/import safely

Treat an export as complete evidence only when it includes all relevant tags, triggers, variables, templates, folders, consent settings, and references from the intended workspace/version.

For an authorized export/import operation, preserve container/object schema and clearly distinguish
create, merge, overwrite, and delete behavior. Do not import when the adapter cannot target the
dedicated workspace or cannot avoid an unapproved overwrite, delete, version, or publication.

## Use the UI as a controlled fallback

When UI work is required:

- verify the signed-in Google account and container ID before each mutation batch;
- select the dedicated workspace explicitly;
- inspect visible template and consent fields;
- save one logical object at a time and re-open it;
- never click Submit, Publish, or Create Version;
- record any UI-only field that the semantic adapter could not verify.

## Stop when mutation is unavailable

If authentication, permissions, tool availability, or workspace limits prevent mutation:

- mark the affected requirement `Blocked`;
- state the exact account, access, capability, workspace, or adapter condition required;
- preserve any safe research and concise intended-object information needed to resume;
- state explicitly that no affected GTM object changed, or report the exact partial saved state.

Do not turn the run into a successful specification or planning workflow. Configuration remains the
required outcome.

## Official entry points

- https://developers.google.com/tag-platform/tag-manager/api/v2
- https://developers.google.com/tag-platform/tag-manager/api/reference/rest/v2/accounts.containers.workspaces/sync
- https://developers.google.com/tag-platform/tag-manager/api/reference/rest/v2/accounts.containers.workspaces.tags
- https://developers.google.com/tag-platform/tag-manager/api/reference/rest
- https://support.google.com/tagmanager/answer/6106997
