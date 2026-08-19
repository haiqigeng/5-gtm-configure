# Configuration run, recovery, and result

## Contents

- [Use one durable run artifact](#use-one-durable-run-artifact)
- [Materialize deterministically](#materialize-deterministically)
- [Checkpoint every write boundary](#checkpoint-every-write-boundary)
- [Contain failures by dependency](#contain-failures-by-dependency)
- [Resume only from proved state](#resume-only-from-proved-state)
- [Finalize once from proved state](#finalize-once-from-proved-state)
- [Handle secrets without false equality](#handle-secrets-without-false-equality)
- [Machine-readable run record](#machine-readable-run-record)
- [Commands](#commands)

## Use one durable run artifact

For every server or pipeline run, and for a web refonte, destructive/replace action, shared
consumer, template permission change, multi-product consent decision, multi-destination graph, or
resumable multi-write operation, maintain one `configuration-run@3.0` JSON artifact from preflight
through final readback. Its schema is
[`configuration-run.schema.json`](../../schemas/configuration-run.schema.json).

The v6 configuration contract owns approved requirements, authorized targets, pipeline design, and
intended actions. The run owns execution state, per-target evidence, recovery, idempotency, and the
configuration result. Neither authorizes publication, runtime recette, site/cloud work, or
external-platform administration. An isolated low-risk web change may keep the same structure in
memory; it does not receive weaker acceptance.

Versioned 2.0/2.1 web runs remain readable. `upgrade` moves a safe web-only artifact into the v3
target-scoped envelope, preserves its object intention and legacy topology record, and never invents
a server target. Ambiguous or unsafe history is rejected rather than guessed.

## Materialize deterministically

`init` validates contract 6.0 and deterministically creates target-scoped operations and stable
operation IDs. It refuses an existing path unless `--replace-planned` is explicit and no write
history exists. The following active sections are contract-owned:

- requirements, except derived status;
- immutable target identity (container type and account/container/workspace IDs; adapter
  capabilities remain runtime-owned);
- pipelines;
- immutable object action, target, intention, dependency, and human-readable justification fields;
- payload mappings;
- consent topologies;
- web execution topologies, page-view decisions, first-party-data routes, and inventory
  dispositions;
- dedup contracts;
- official sources and external dependencies;
- publication dependencies.

Their fingerprints are revalidated on every load. Do not edit those sections by hand. Record each
target's exhausted relevant-family baseline with the `baseline` command before its first mutation.
The controller derives pre-write and saved-state comparisons from authoritative readback; adapters
populate capabilities, journal, readback, result, and recovery state.

## Checkpoint every write boundary

Immediately before a delta mutation, re-read the exact target object and compare every approved
`pre_change` field. Missing, changed, or type-different state is drift: persist the failure and do
not write. A create whose semantic identity already exists with different state is a conflict,
never an overwrite.

Persist the passing pre-write comparison before `in_progress`. After one mutation, record:

| State | Meaning |
| --- | --- |
| `saved` | A save exists but authoritative equality remains unresolved. |
| `verified` | Target readback matches all comparable intended fields and references. |
| `failed` | The operation is proved absent/rejected; transitive dependents stop. |
| `uncertain` | Whether it saved is unknown; no blind retry is allowed. |
| `skipped` | The approved graph intentionally omits it. |

`verified` requires a target-scoped comparator, intended/saved SHA-256, structured differences,
and authoritative readback. For `remove`, authoritative not-found after the write is the required
saved state and is compared as object absence; it is not a missing-readback error. JSON checkpoints
and render writes are atomic. A documented non-applied
rate-limit response may retry within a strict bound; an ambiguous mutation must read before any
further action.

## Contain failures by dependency

Each target has independent baseline, capability matrix, journal, readback, result, and recovery
frontier. Execute only planned operations whose dependencies are `verified` or `skipped`.

On failure or uncertainty, stop that operation and its transitive dependents while continuing
independent safe subtrees. A failed or unproved claiming Client blocks dependent receiver tags and
the web endpoint cutover. A failed Meta destination does not block an independent GA4 destination.
An unsupported Transformation capability blocks only consumers that depend on it.

## Resume only from proved state

Validate the artifact before calling an adapter. Resolve `in_progress` or `uncertain` by
authoritative target readback; never retry an ambiguous create/update/replace/import. A known
`failed` operation may be `reopen`ed only after its blocker and target identity are revalidated and
the no-write outcome is proved. Reopen clears stale pre-write, saved-readback, and comparison
evidence before returning the operation to `planned`; old proof never carries into a retry.

Interpret inspection literally: `valid` is schema validity, `resumable` means no unresolved write
boundary, and `pass` requires finalized `Configured`. The recovery frontier names affected target,
last verified operation, unsafe/dependent operations, and next authoritative readback.

## Finalize once from proved state

Use one locked `finalize` transition. It succeeds only when every required operation is
`verified`/`skipped`, every target baseline is complete, required cross-target invariants pass, and
concrete identical-rerun no-op evidence is supplied. It atomically derives target and requirement
statuses, checked idempotency, `phase: complete`, and `status: Configured`. Do not hand-edit
status or idempotency.

Open publication dependencies never block saved-configuration completion. A server-only run records
server publication then server recette. A pipeline continues with web cutover publication, then web
and end-to-end recette.

## Handle secrets without false equality

Redact credentials and raw user values before any baseline, contract, journal, error, diff,
rendering, or result is persisted. Use exact template secret-field paths first, heuristic detection
second, and resolve actual values only through ephemeral secure input.

Readback may prove matching secret-field presence and equality of every non-secret field, but it
must report `present-not-compared` and `value_equality_claimed: false`. Two redacted markers are
never proof of secret equality. A delta cannot claim unchanged secret value from markers alone;
use a safe reference/version/rotation locator or stop the affected comparison. Parameter-table
rows whose key names a credential are sensitive even when the literal lives in a generic `value`
field. This includes a bare `authorization` field, a `Bearer`/`Basic` literal, and GTM's flattened
`name=Authorization` plus adjacent `value=...` header rows. Governance booleans such as destructive
authorization are not credentials.

## Machine-readable run record

The validated `configuration-run@3.0` artifact is the machine-readable configuration result. It
exists for deterministic mutation, recovery, saved-state proof, and human result rendering. It is
not a recette input or acceptance authority; runtime recette independently uses the tracking plan
and live GTM/Preview evidence.

## Commands

~~~powershell
python scripts/validate_configuration_contract.py --contract contract.json
python scripts/configuration_run.py init --contract contract.json --run-id RUN-001 --source-locator "Approved input" --output configuration-run.json
python scripts/configuration_run.py upgrade --run configuration-run.json
python scripts/configuration_run.py validate --run configuration-run.json
python scripts/configuration_run.py inspect --run configuration-run.json
python scripts/configuration_run.py baseline --run configuration-run.json --target web-main --resources web-resources.json --workspace-changes web-workspace-changes.json --captured-at 2026-08-19T10:00:00Z
python scripts/configuration_run.py checkpoint --run configuration-run.json --operation OP-001 --state in_progress --note "Fresh pre-change readback matched" --pre-write-readback before.json
python scripts/configuration_run.py checkpoint --run configuration-run.json --operation OP-001 --state verified --note "Saved readback matched" --result saved-result.json --saved-readback saved-object.json
python scripts/configuration_run.py reopen --run configuration-run.json --operation OP-003 --note "Blocker resolved and target revalidated."
python scripts/configuration_run.py finalize --run configuration-run.json --evidence "Second adapter pass returned zero mutations."
python scripts/configuration_run.py render --run configuration-run.json --output configuration-result.md
~~~

`web-resources.json` maps every exhausted relevant resource family to its complete item array;
`web-workspace-changes.json` is the complete pre-existing workspace-change array. Only delta
actions need `before.json`: it is the raw authoritative target object and must include its current
`name`; server-generated IDs and fingerprints are tolerated but the name remains drift-sensitive.

A verified `saved-object.json` is a target-scoped graph:

~~~json
{
  "objects": [
    {
      "target_id": "web-main",
      "object_type": "tag",
      "name": "GA4 - purchase"
    }
  ]
}
~~~

Include every comparable intended field in that object. The controller builds and binds both
comparisons; externally supplied comparison files are optional compatibility inputs, not required
operator work. A verified remove represents readback as JSON `null`. The controller acquires the
run lock before loading a checkpoint source and returns coded JSON errors for invalid graph shape,
duplicate JSON keys, non-finite values, excessive nesting, unsafe transitions, materialization
drift, and unsafe overwrite.
