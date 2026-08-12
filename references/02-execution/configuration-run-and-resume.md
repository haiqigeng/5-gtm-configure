# Configuration run, recovery, and machine handoff

## Contents

- [Use proportionate proof and one durable run artifact](#use-proportionate-proof-and-one-durable-run-artifact)
- [Preserve stable requirement identity](#preserve-stable-requirement-identity)
- [Render impact without adding a routine approval gate](#render-impact-without-adding-a-routine-approval-gate)
- [Checkpoint every write boundary](#checkpoint-every-write-boundary)
- [Resume only from proved state](#resume-only-from-proved-state)
- [Finalize once from proved state](#finalize-once-from-proved-state)
- [Use replace as one governed action](#use-replace-as-one-governed-action)
- [Summarize template permission changes](#summarize-template-permission-changes)
- [Hand off in three layers](#hand-off-in-three-layers)
- [Commands](#commands)

## Use proportionate proof and one durable run artifact

For a refonte, destructive/replace action, shared consumer, template permission change,
multi-product consent decision, multi-destination graph, or resumable multi-write operation,
maintain one `configuration-run@2.1` JSON artifact from preflight through final readback. Its
schema is [`../../schemas/configuration-run.schema.json`](../../schemas/configuration-run.schema.json).
The v5 configuration contract owns approved requirements and intended actions; the run artifact
owns execution order, evidence, recovery, idempotency, and recette handoff. Neither authorizes
publication, runtime recette, site work, or external-platform administration.

An isolated low-risk run may use the same map in memory. Classify risk across the entire run, not
one operation at a time. Promote to the durable artifact before any write when the complete graph
contains the risks above. A durable artifact uses an exclusive per-artifact writer lock; this is
not a GTM workspace lease or an extra approval gate.

`init` refuses an existing path unless `--replace-planned` is explicit and no saved history
exists. Version 2.0 artifacts remain readable. `upgrade` converts only evidence-safe unfinished
runs; it refuses finalized history, ambiguous Custom HTML first-party routes, or a delta whose
write started without v2.1 pre-write proof.

## Preserve stable requirement identity

Use an immutable source ID when supplied; otherwise derive a stable business ID such as
`GA4::generate_lead`. Keep mutable source locations separately. Multi-requirement objects list all
consumer `requirement_ids`.

## Render impact without adding a routine approval gate

Render impact from the same artifact without pausing routine authorized writes. Keep existing
authority gates for destructive, permission-expanding, Default Workspace, unresolved shared, and
high-impact actions.

For strict/basic consent, keep the CMP event as the normal trigger when it supplies page-load
timing and record the reusable blocking set independently. A verified vendor-wide Custom Event
block defaults to `blocking_event_scope: "regex:.*"`; narrower scope needs a reason.

The baseline records complete resource-family counts and semantic trigger identities/types.
Active-tag topology references must equal the target `firingTriggerId` and
`blockingTriggerId` arrays. This per-active-tag execution topology remains the declared firing
authority. For refontes, keep refonte inventory dispositions aligned with the exact tag operations
and before/after evidence. Page-view records bind real Google/GA4 tag types and effective
`send_page_view`. First-party records bind each mapped field to a positive native or installed
template identity for the exact product; a name or negative “not GA4” test is insufficient.

## Checkpoint every write boundary

Immediately before a delta mutation, re-read the exact saved object and compare every approved
`pre_change` field. Extra adapter metadata may be ignored, but a missing, changed, or type-different
field is container drift: persist the failed comparison and do not write. A create whose semantic
identity already exists with different state is a conflict, never an overwrite. Persist the passing
pre-write comparison before `in_progress`.

After one mutation, persist one accurate state:

| State | Meaning |
| --- | --- |
| `saved` | Adapter returned a saved object; authoritative comparison remains. |
| `verified` | Authoritative readback has zero differences. |
| `failed` | The write is proved absent/rejected; all remaining writes stop. |
| `uncertain` | Whether the write saved is unknown; no retry is allowed. |
| `skipped` | The approved graph intentionally omits the operation. |

`verified` requires structured comparison evidence: comparator identity, intended/saved SHA-256,
every top-level intended field, and structured differences. Supply `--saved-readback` so the
controller binds that proof to the immutable intention. JSON checkpoints and rendered handoffs are
atomic.

## Resume only from proved state

Validate before calling an adapter. Resolve `in_progress` or `uncertain` by authoritative
readback; never retry an ambiguous create/update/replace/import. Execute only `planned` operations
whose dependencies are `verified` or `skipped`. A `failed` operation is not retried automatically;
after its blocker and target identity are revalidated, `reopen` may return only
that proved no-write operation to `planned`.

Interpret inspection literally: `valid` is schema validity, `resumable` means automatic work is
safe, and `successful`/`pass` require a finalized `Configured` run. The adapter helper bounds
rate-limit retries, honors an in-bound `Retry-After`, resolves ambiguous responses by readback,
and never blindly retries. MCP/API/UI adapters must preserve the same transitions.

## Finalize once from proved state

Use the single locked `finalize` transition. It succeeds only when every operation is
`verified`/`skipped`, verified operations have readback, preflight is complete, and at least
one concrete no-op rerun/readback evidence locator is supplied. It atomically derives requirement
statuses, checked idempotency, `phase: complete`, and `status: Configured`. Do not hand-edit
those fields or use multiple section setters.

## Use replace as one governed action

Use `replace` only when a supported update cannot reach the same semantic target. Require stable
`object_id`, exact `pre_change` and `intended`, a specific reason, destructive/high-impact
authority where applicable, consumer tracing, recovery evidence, and post-create readback. Never
use replace to bypass drift, rename, or simulate a missing adapter feature.

## Summarize template permission changes

For template create/update/replace, record the inspected version and permission delta. Surface new
domain, injection, API, storage, global, or data-access permission without inventing safety claims.

## Hand off in three layers

Generate all layers from the validated `configuration-run@2.1` artifact:

1. **Executive:** status, stable target, counts, consent, blocker/recovery, no publication.
2. **Analyst/developer:** requirement/object actions, payload mappings, normal/block triggers,
   permissions, readback, and external owners.
3. **Machine/recette:** complete JSON with stable requirement IDs, expected tags/triggers,
   consent states, user-data keys/network cues, and explicit
   `runtime_validation_performed: false`.

This handoff does not prove browser, dataLayer, network, CMP-journey, or vendor behavior.

## Commands

~~~powershell
python scripts/configuration_run.py init --contract contract.json --run-id RUN-001 --source-locator "Tracking Plan / Events" --output configuration-run.json
python scripts/configuration_run.py upgrade --run configuration-run.json
python scripts/configuration_run.py validate --run configuration-run.json
python scripts/configuration_run.py inspect --run configuration-run.json
python scripts/configuration_run.py checkpoint --run configuration-run.json --operation OP-001 --state in_progress --note "Fresh pre-change readback matched" --pre-write-readback before.json --pre-write-comparison pre-write-comparison.json
python scripts/configuration_run.py checkpoint --run configuration-run.json --operation OP-001 --state verified --note "Saved readback matched" --result saved-result.json --saved-readback saved-object.json --comparison comparison.json
python scripts/configuration_run.py reopen --run configuration-run.json --operation OP-003 --note "Authentication renewed; target revalidated."
python scripts/configuration_run.py finalize --run configuration-run.json --evidence "Second adapter pass returned zero mutations."
python scripts/configuration_run.py render --run configuration-run.json --output handoff.md
~~~

Only delta actions need the pre-write files. `verified` always needs `--result`, authoritative
`--saved-readback`, and v1 comparison evidence. The controller rejects duplicate JSON keys,
non-finite values, excessive nesting, unsafe transitions, and unsafe overwrite.
