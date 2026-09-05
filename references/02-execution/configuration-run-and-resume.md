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
resumable multi-write operation, maintain one `configuration-run@4.0` JSON artifact from preflight
through final readback. Its schema is
[`configuration-run.schema.json`](../../schemas/configuration-run.schema.json).
The JSON Schemas provide structural/editor validation. The packaged contract and run validators
remain authoritative for cross-object semantics, mutation eligibility, and finalization.

The configuration-contract 7.0 artifact owns approved requirements, authorized targets, pipeline design, and
intended actions. The run owns execution state, per-target evidence, recovery, idempotency, and the
configuration result. Neither authorizes publication, runtime recette, site/cloud work, or
external-platform administration. An isolated low-risk web change may keep the same structure in
memory; it does not receive weaker acceptance.

Only the current target-scoped run schema is executable. Obsolete runs must be regenerated from an
approved current contract; the controller does not guess or migrate mutation history.

## Materialize deterministically

`init` validates contract 7.0 and deterministically creates target-scoped operations and stable
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

Their fingerprints are revalidated on every load. Do not edit those sections by hand. The
authenticated adapter captures each target's exhausted relevant-family baseline before mutation.
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
| `skipped` | Work was not executed; it neither verifies a required dependency nor qualifies for Configured. Amend the approved scope when omission is intended. |

`verified` requires a target-scoped comparator, intended/saved SHA-256, structured differences,
and authoritative readback. For `remove`, authoritative not-found after the write is the required
saved state and is compared as object absence; it is not a missing-readback error. JSON checkpoints
and render writes are atomic. A documented non-applied
rate-limit response may retry within a strict bound; an ambiguous mutation must read before any
further action.

## Contain failures by dependency

Each target has independent baseline, capability matrix, journal, readback, result, and recovery
frontier. Execute only planned operations whose dependencies are `verified` and whose target has a
complete baseline covering every planned resource family. Authentication failure stops the whole
affected target until revalidated; independent authorized targets may continue.

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

The locked adapter convergence call performs the only finalization transition. It succeeds only when every required operation is
`verified`, every target baseline is complete, no required mapping is pending or blocked, required cross-target invariants pass, and
the adapter has performed a fresh read-only convergence pass with one recomputable no-op comparison
per operation. It atomically derives target and requirement statuses, checked idempotency,
`phase: complete`, and `status: Configured`. Free-text evidence cannot satisfy this gate. Do not
hand-edit status or idempotency.

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
`name=Authorization` plus adjacent `value=...` header rows. Non-sensitive governance metadata is
not a credential.

## Machine-readable run record

The validated `configuration-run@4.0` artifact is the machine-readable configuration result. It
exists for deterministic mutation, recovery, saved-state proof, and human result rendering. It is
not a recette input or acceptance authority; runtime recette independently uses the tracking plan
and live GTM/Preview evidence.

## Commands

~~~powershell
python scripts/validate_configuration_contract.py --contract contract.json
python scripts/configuration_run.py init --contract contract.json --run-id RUN-001 --source-locator "Approved input" --output configuration-run.json
python scripts/configuration_run.py validate --run configuration-run.json
python scripts/configuration_run.py inspect --run configuration-run.json
python scripts/configuration_run.py checkpoint --run configuration-run.json --operation OP-001 --state in_progress --note "Fresh pre-change readback matched" --pre-write-readback before.json
python scripts/configuration_run.py checkpoint --run configuration-run.json --operation OP-001 --state verified --note "Saved readback matched" --result saved-result.json --saved-readback saved-object.json
python scripts/configuration_run.py reopen --run configuration-run.json --operation OP-003 --note "Blocker resolved and target revalidated."
python scripts/configuration_run.py render --run configuration-run.json --output configuration-result.md
~~~

Convergence is intentionally unavailable as a caller-supplied CLI checkpoint. After every
operation is verified, call `adapter_runtime.verify_idempotent_rerun` with the same target registry.
It performs one new read through each identity-verified adapter, records the observed target
identity and a timestamp newer than operation verification, then recomputes the comparison. A match
keeps the operation verified and the same locked adapter call finalizes the run as `Configured`.
A mismatch reopens only that operation as `planned`, clears its stale saved-state proof, and records
a convergence-repair journal entry so the same current contract can be applied again safely. There
is no separate public finalize or caller-supplied convergence path.

Baseline capture is not a CLI transition. `adapter_runtime.execute_ready_operations` rechecks the
authenticated target identity, calls the adapter's paginated resource and workspace-change listing
methods, creates exhaustion receipts internally, retains the redacted canonical resource graph,
and fingerprints it before the first write. Any caller-authored baseline is replaced while all
target operations are still planned. An isolated run covers every list-capable family and every
planned family; a `refonte-durable` run must cover the complete supported target surface, including
empty arrays. Only delta actions need `before.json`: it is the raw authoritative target object and
must include its current `name`; server-generated IDs and fingerprints are tolerated but the name
remains drift-sensitive.

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
comparisons. When the primary object contains raw GTM IDs, add the referenced objects under
`context_objects`; they resolve IDs but are not treated as additional intended objects. A verified
remove represents readback as JSON `null`. The controller acquires the
run lock before loading a checkpoint source and returns coded JSON errors for invalid graph shape,
duplicate JSON keys, non-finite values, excessive nesting, unsafe transitions, materialization
drift, and unsafe overwrite.
