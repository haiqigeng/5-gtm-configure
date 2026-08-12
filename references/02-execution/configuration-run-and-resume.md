# Configuration run, recovery, and machine handoff

## Contents

- [Use proportionate proof and one durable run artifact](#use-proportionate-proof-and-one-durable-run-artifact)
- [Preserve stable requirement identity](#preserve-stable-requirement-identity)
- [Render impact without adding a routine approval gate](#render-impact-without-adding-a-routine-approval-gate)
- [Checkpoint every write boundary](#checkpoint-every-write-boundary)
- [Resume only from proved state](#resume-only-from-proved-state)
- [Use replace as one governed action](#use-replace-as-one-governed-action)
- [Summarize template permission changes](#summarize-template-permission-changes)
- [Hand off in three layers](#hand-off-in-three-layers)
- [Commands](#commands)

## Use proportionate proof and one durable run artifact

For a refonte, destructive/replace action, shared-consumer update, template permission change,
multi-product consent decision, multi-destination graph, or resumable multi-write operation,
maintain one `configuration-run@2.0` JSON artifact from preflight
through saved readback. Its schema is
[`../../schemas/configuration-run.schema.json`](../../schemas/configuration-run.schema.json).
It complements the v5 configuration contract:

- the v5 contract owns approved requirements, authority, and intended GTM actions;
- the run artifact owns execution order, checkpoints, readback, recovery, idempotency, and recette
  handoff;
- neither artifact authorizes publication, runtime recette, a site change, or external-platform
  administration.

Before the first mutation, resolve every generated payload-mapping row from approved source
authority and source shape through one named GTM method to the template and destination shape.
`direct-dlv` and `native-template` require compatible terminal shapes; `custom-javascript` requires
a documented shape conversion. A `pending` or `blocked` mapping keeps its requirement's writes out
of the ready-operation set. The controller also requires a consent route for each non-deferred
analytics/media requirement that has an executing target tag before its first write. A removal
does not need a fictional target consent route or firing topology.

When a writable file is unavailable, preserve the same structure in the response. Do not downgrade
the evidence or status rules merely because the artifact cannot be saved locally.

For an isolated low-risk change, a lightweight in-memory map may carry the same required target,
field, topology, consent, and readback proof. It must not weaken the completion rules. Promote it to
the durable artifact before the first write when preflight discovers sharing, destructive scope,
multiple products/destinations, template permissions, or recovery risk.

Treat a durable file as required for those risk triggers, not as an approval gate. When a file is
used, permit one writer for that artifact at a time. The controller uses an
exclusive per-artifact writer lock so two sessions cannot overwrite each other's checkpoints; it
does not claim a global GTM workspace lease. `init` refuses an existing path unless
`--replace-planned` is explicit and the existing artifact contains only untouched `planned` state.

## Preserve stable requirement identity

Use a source-supplied immutable requirement ID when one exists. Otherwise create a deterministic ID
from a unique stable business identity, for example `GA4::generate_lead`; do not include mutable row
order when event identity is already unique. Persist that ID for the run and record workbook/sheet/
row order, document section, or direct-message location separately.

In a multi-requirement contract, every object action declares `requirement_ids`. Shared objects list
all consumers. This makes plan-to-object and Config-to-Recette chaining exact without pretending to
parse arbitrary workbook layouts automatically.

## Render impact without adding a routine approval gate

Before mutation, the same run artifact can render a What-If view: creates, updates, replacements,
removals, reuse, affected requirements, dependencies, consent routes, shared consumers, and template
permission changes. Do not pause a routine authorized configuration merely to ask for another
approval.

Require an explicit decision only where the existing authority model already requires it: removal,
replacement, new or expanded template permissions, Default Workspace use, unresolved shared-
consumer impact, or high-impact template, Zone, environment, destination, Google tag configuration,
or container-setting change.

For strict/basic consent, record the reusable blocking trigger set even when a CMP readiness/grant
event is the normal trigger; new routes use `mechanism: "blocking-trigger"` and keep the CMP event
in `normal_trigger`. Use `blocking_event_scope: "regex:.*"` for a verified vendor-wide
Custom Event block; a narrower scope requires `scope_exception_reason`. Advanced/native routes must
not carry a block that defeats their approved denied-state behavior.

The v2 artifact also records one completed adapter baseline, per-active-tag execution topology, page-view
ownership decisions, first-party-data routes, and refonte inventory dispositions when applicable.
Preflight prevents a tag write when its topology, relevant consent route, page-view decision, or
required first-party-data route is unresolved.

The baseline records counts for every captured resource family and a semantic trigger index with
object key, real GTM type, and optional fingerprint. Every active tag topology lists one or more
typed semantic normal-trigger references and semantic block references. Those sets must equal the
tag target's `firingTriggerId` and `blockingTriggerId` arrays; a declared Custom Event cannot mask a
saved Click, Form, Visibility, Scroll, YouTube, History, Timer, or other native trigger. Removed and
paused tags carry exact `pre_change` evidence instead of target topology.

Page-view records reference the real Google tag and, when separate, the real GA4 `page_view` tag;
the controller verifies their tag types and effective `send_page_view` values. First-party-data
records bind feature, mapped destination field, correct product consumer, configured target field,
timing, consent, and external administration dependency. Refonte inventory rows bind their stated
disposition to exactly one compatible tag operation and its before/after names.

## Checkpoint every write boundary

Before each mutation, persist `in_progress` with the operation ID and read-before-write evidence.
After the adapter returns, persist one accurate state:

| State | Meaning |
| --- | --- |
| `saved` | The adapter returned a saved object, but authoritative comparison is pending. |
| `verified` | Authoritative readback and a zero-difference comparison passed. |
| `failed` | The operation is known not to have completed or was rejected; dependent writes stop. |
| `uncertain` | The response cannot prove whether the write saved; no retry is permitted yet. |
| `skipped` | The action is intentionally not executed under the approved graph. |

Record returned stable IDs and fingerprints when exposed. `verified` requires structured comparison
evidence containing the comparator identity, intended and saved SHA-256 fingerprints, every
top-level intended field, and structured differences. A bare `pass: true` or adapter success
response is insufficient. Supply the authoritative saved payload so the controller recomputes and
binds its fingerprint to the immutable intended operation. Persist the proof on both the operation
and saved-readback record. Write checkpoints atomically so an interruption cannot leave a
half-written journal.

## Resume only from proved state

On restart, load and validate the run artifact before calling the adapter:

1. if an operation is `in_progress` or `uncertain`, read the exact workspace/object identity first;
2. resolve it to `verified` only when saved state matches, or to `failed` when authoritative evidence
   proves the intended write is absent or different;
3. never retry an ambiguous create, replace, update, import, or template operation blindly;
4. execute only `planned` operations whose dependencies are `verified` or `skipped`;
5. preserve verified work and stop downstream consumers on authentication failure, fingerprint
   conflict, schema drift, or unresolved readback.

Interpret inspection fields literally: `valid` means the artifact satisfies its schema,
`resumable` means no failed/in-progress/uncertain operation permits an automatic next write, and
`successful`/`pass` become true only for a validated `Configured` run. `completed`,
`suggested_status`, and `error_code` remain separate so a valid or resumable run cannot appear
successfully configured by accident. The controller never auto-finalizes idempotency or status.

A `failed` operation is known not to have completed and is not retried automatically. After its
blocker is resolved and the target account/container/workspace is revalidated, explicitly run the
controller's `reopen` command with a durable reason. This moves only that proved no-write operation
back to `planned`; an `uncertain` operation must first be resolved by authoritative readback.

The packaged adapter state machine supplies executable regressions for cursor pagination, bounded
rate-limit retries with an in-bound documented `Retry-After` or exponential backoff and jitter,
authentication expiry, ambiguous writes, partial saves, and idempotent reruns. When `Retry-After`
exceeds the configured window, stop instead of retrying early. The helper reads the exact operation
before mutation; it does not perform a redundant whole-container inventory sweep on every write run.
For an MCP or UI that cannot call the helper directly, follow the same state transitions and keep
the run artifact as the durable checkpoint.

## Use replace as one governed action

Use `replace` only when the approved target cannot be reached by a supported update and the same
semantic object must be removed and recreated. Record it as one action, not a contradictory
`remove` plus `create` pair. Require:

- stable existing `object_id`, exact non-empty `pre_change`, and exact non-empty `intended` state;
- a specific `replacement_reason` explaining why update is insufficient;
- explicit destructive authorization and, for a high-impact object, explicit high-impact authority;
- consumer/dependency tracing and a recovery boundary based on the captured pre-change state;
- post-create readback before any dependent operation.

Do not use replace to bypass a fingerprint conflict, rename an object, clean unrelated debt, or
simulate an unavailable adapter feature.

## Summarize template permission changes

For a template create, update, or replacement, compare the installed/current and intended template
permissions. Record added and removed permissions plus the exact inspected template/version
locator. Surface any new domain, script injection, API, storage, global access, or data-access
permission in the preflight view. Do not invent a reputation score or call a publisher safe without
evidence.

## Hand off in three layers

Generate every layer from the same validated run artifact:

1. **Executive:** status, stable target, requirement/object counts, consent summary, blocker or
   recovery boundary, and explicit no-publication statement.
2. **Analyst/developer:** requirement-to-object changes, exact payload mappings, normal and blocking
   triggers, template fields/permissions, saved IDs/readback, and external owners.
3. **Machine/recette:** the complete `configuration-run@2.0` JSON with one recette record per stable
   requirement ID, exact normal/blocking triggers, expected user-data keys/network cues, and
   explicit `runtime_validation_performed: false`.

The machine layer is a handoff, not proof of runtime behavior. The recette skill remains responsible
for Preview, dataLayer, resolved-variable, browser-send, and consent-journey validation.

## Commands

~~~powershell
python scripts/configuration_run.py init --contract contract.json --run-id RUN-001 --source-locator "Tracking Plan / Events" --output configuration-run.json
python scripts/configuration_run.py validate --run configuration-run.json
python scripts/configuration_run.py inspect --run configuration-run.json
python scripts/configuration_run.py checkpoint --run configuration-run.json --operation OP-001 --state in_progress --note "Read-before-write passed"
python scripts/configuration_run.py checkpoint --run configuration-run.json --operation OP-001 --state verified --note "Saved readback matched" --result saved-result.json --saved-readback saved-object.json --comparison comparison.json
python scripts/configuration_run.py reopen --run configuration-run.json --operation OP-003 --note "Authentication renewed; target identity revalidated."
python scripts/configuration_run.py render --run configuration-run.json --output handoff.md
~~~

Use `checkpoint --state verified` only with `--result`, the authoritative `--saved-readback`, and a
structured `--comparison` file that passes the v1 verification schema and covers every top-level
intended field. The script recomputes the saved fingerprint, rejects unsafe transitions, duplicate
JSON keys, non-finite values, excessive nesting, and unsafe overwrite, and writes atomically.
