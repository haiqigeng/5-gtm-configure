# Configuration run, recovery, and result

## Use one durable run artifact

Use one `configuration-run@9.0` artifact for each configuration task, including isolated changes.
The [contract](authoring.md) owns approved requirements, targets, intended actions and feature
relationships. The run owns operation state, target evidence, recovery and the configuration result.
[The run schema](../../schemas/configuration-run.schema.json) validates structure; shared domain
validators check meaning and the engine enforces transitions.

Execute the current model from an approved current contract. Retain historical artifacts as evidence
and resolve their uncertain writes before preparing a new run. Resumed input follows the
[provenance boundary](authority.md#evidence-and-validation-limits).

## Materialize deterministically

`init` validates contract 11.0 and creates stable target-scoped operation IDs at a new output path.
The current run retains approved requirement and exact field fingerprints, native intentions, policy relationships,
readbacks and its authenticated baseline. Runtime APIs update execution evidence and derived results.

Revise the remaining graph through `run revise` using the current durable run, an approved contract,
inspection's `run_fingerprint`, and a rationale. The locked transition rejects stale inspection and
unreconciled dispatched writes. Verified operations keep their IDs, authority, journals, saved proof
and bound source/policy semantics. Planned work can change; an already completed intention requires
an authorized follow-on operation. The run keeps the prior/new contract fingerprints, timestamp and
changed planned object keys. A revision with no approved change preserves the existing run through
an explicit no-change rejection. New required resource families receive supplemental authenticated
capture receipts before their operations become ready; the original baseline evidence remains intact.
Semantic owners determine the protected proof: a verified shared source or settings variable keeps
its native intent and exact approved fields; executing consumers keep their event and product policies.
Planned consumers can correct their own approved event, lifecycle and receiver flows while their
verified prerequisites retain the original authority, receipts and journals.

Capture each target's relevant families and workspace changes with exhausted pagination before
mutation. An isolated run includes required dependency/consumer closure; refonte includes every
supported family, including empty ones. The authenticated runtime creates receipts, retains the
redacted baseline graph and fingerprints it. It replaces caller-authored baseline evidence while
all target operations are still planned.

## Checkpoint every write boundary

For a delta, obtain fresh target readback and compare every approved `pre_change` field, including
its name. Missing, changed or type-different state records drift and holds the operation. Create
absence is established from the complete family view and current-run writes under
[the adapter contract](../adapters/custom.md); an existing different object is a conflict.

Persist the passing pre-write comparison before `in_progress`. Record the outcome of one mutation:

| State | Meaning and next action |
| --- | --- |
| `saved` | A save exists; complete authoritative comparison. |
| `verified` | Readback matches every comparable intended field and reference. |
| `failed` | The write is proved absent or rejected; resolve its cause before reopening. |
| `uncertain` | Dispatch may have applied; establish the outcome by readback. |
| `skipped` | Work was not executed; required dependencies remain unsatisfied. An intended omission needs an approved scope decision. |

Verification binds a target-scoped comparison, intended/saved SHA-256, structured differences and
authoritative readback. Removal verifies authoritative absence, represented as JSON `null`.
Run and rendered-output writes are atomic. State transition errors retain the current durable state.

## Contain failures by dependency

Each target has its own baseline, capability matrix, journal and recovery frontier. Ready operations
are planned, have complete target baselines and verified dependencies, and have resolved owned
fields. Authentication failure holds the affected target until revalidation.

Every outgoing field binds its semantic owner directly through `owner_object_key`; pipeline fields
bind `receiver_owner`. Readiness uses those owners, including shared settings variables, and derives
dependency demand independently of operation authorization. A complete shared dependency remains
usable by a ready requirement. An unresolved field on the shared owner blocks that owner and every
dependent consumer; unresolved event overrides hold their own consumers.

Failure, uncertainty and field blockers propagate with their originating reason. `waiting` identifies
a dependency that can still complete; `blocked` identifies a prerequisite requiring resolution.
Independent authorized subtrees can continue. Pipeline sender cutover follows all required verified
receiver operations under [pipeline ordering](../pipeline/architecture-and-workflow.md#build-receiver-first).

## Resume only from proved state

After authoritative reconciliation, use the same run for a revised approved graph:

```powershell
python "<skill-dir>/scripts/configure_gtm.py" run inspect --run configuration-run.json
python "<skill-dir>/scripts/configure_gtm.py" run revise --run configuration-run.json --contract contract.json --expected-fingerprint "sha256:<inspection fingerprint>" --note "Approved remaining graph correction"
```


Validate the run before adapter calls. Resolve `in_progress` or `uncertain` through authoritative
readback, recorded with `run checkpoint --saved-readback`: verify an applied matching write,
retain uncertainty when the outcome remains unknown,
or establish non-application before any replay. A known `failed` operation can be `reopen`ed after
its cause, target identity and no-write outcome are revalidated. Reopen clears obsolete comparison
and readback evidence and returns the operation to `planned`.

A malformed, missing-ID or scope-inconsistent mutation response remains an ambiguous dispatched
write. Response parsing cannot establish non-application. Bounded retries apply to typed,
proved-non-applied quota rejection; [quotas](../adapters/quotas.md) owns classification and retry bounds.

Inspection's `valid` means validation passed, `resumable` means no unresolved write boundary, and
`pass` requires finalized `Configured`. Preserve the last verified operation, affected/dependent
operations and next readback in the recovery frontier. Baseline failures are recorded once in
`target_results[].baseline_error`; operations remain planned and resume retries the missing baseline.

## Finalize once from proved state

The locked adapter convergence call is the sole finalization transition. It requires every required
operation verified, complete target baselines, resolved mappings, applicable cross-target invariants,
and fresh read-only no-op comparisons. It atomically derives target/requirement statuses, checked
idempotency, `phase: complete` and `status: Configured`.

Call `gtm_configure.runtime.engine.verify_idempotent_rerun` with the same target registry. The runtime
rechecks target identities, captures observations newer than operation verification and recomputes
equality. A mismatch reopens the affected operation as `planned`, clears stale saved-state proof and
records a convergence-repair entry. The public CLI has no caller-supplied convergence or finalize path.
[Acceptance](acceptance.md) owns the human verdict and treatment of external dependencies.

## Handle secrets without false equality

Redact credentials and raw user values before persisting contracts, baselines, journals, diagnostics,
diffs or results. Use inspected template secret paths plus structural/text detection; actual secret
values travel through ephemeral secure input and an appropriate bound credential provider.

Readback can establish secret-field presence and non-secret equality. Record secret comparisons as
`present-not-compared` with `value_equality_claimed: false`. A delta involving a hidden value needs
a safe reference/version/rotation locator; otherwise hold that comparison. Redacted markers carry
presence evidence for hidden values. A redacted template source additionally retains full-content
UTF-8 SHA-256 and canonical-source SHA-256, plus native identity/field-type facts extracted before
redaction. The comparison reports exact-byte agreement and canonical source agreement separately;
this proves the integrity of the complete template, including code, permissions, INFO and tests,
without exposing or claiming equality of individual hidden credential values. Representation
normalization covers native line endings and JSON object serialization; source semantics stay
bound to the complete-content proof. Recovery reacquires executable source from its approved
immutable origin before a template write.

Detection covers credential-named Parameter rows, generic value cells, auth headers/literals and
flattened adjacent name/value header rows. Inspect credential-bearing custom code before persistence:
heuristics cannot parse every arbitrary secret, so redact the whole sensitive field when needed.
Governance metadata and public measurement identifiers retain their non-secret meaning.

## Credential findings and transport limits

Report credential exposure by object and field, without the literal. An unpublished saved object
establishes potential exposure; inspected published/browser content establishes live exposure and
supports rotation plus server-side custody.

The MCP worker holds responses in memory until graph-aware redaction and creates no response queue.
Host transcripts may retain raw MCP output or encoded input; inspect host access/retention policy
when credentials are involved. A credential-bearing write without a bound provider records a
specific failed operation; dependency readiness determines what can continue.

For an ambiguous public browser `apiKey`/`token`, inspect official documentation and the installed
template. Declare object-level `public_identifiers` with native `path`, exact UTF-8 literal
`value_sha256`, recorded official-current `source_url` and the inspected purpose in `reason`.
For example, `["parameter", "apiKey", "value"]` uses a unique Parameter key and survives reordering.
An update also binds `previous_value_sha256`; an embedded loader binds the complete inspected HTML.

The declaration follows the exact object/type/value through baseline, comparison, reporting and
mutation. It scopes an exemption from generic key/name heuristics; credential formats, auth headers,
URL userinfo, secret webhook paths, personal data and other credential assignments remain protected,
including decoded query values. Changed literals require reviewed declarations. Source authenticity
remains the agent's responsibility under [evidence limits](authority.md#evidence-and-validation-limits).

## Evidence reuse and recovery

Complete native create/update responses can supply saved verification; partial or ambiguous responses
require targeted authoritative reads. Complete mismatching responses remain unverified. Final
paginated inventories detect relevant names resolving to distinct IDs, including referenced names
whose IDs are already known. Conflicts or incomplete required listings prevent finalization.
Concurrent writers can therefore leave partial unpublished changes before a conflict is detected.

Complete final listing bodies also supply field comparison; trimmed bodies require targeted reads.
Stable-ID updates without a name/reference inventory requirement use targeted reads. Each observation
retains the primary object's complete fields and transitive reference closure. Full contextual
bodies participate in redaction/comparison before compacting to an ID/name index. The baseline and
`final_inventories` retain broader captures once; per-operation saved and final observations remain
distinct. These representation choices preserve fresh verification and comparison fingerprints.

## Machine-readable run record

The validated run is the machine record for mutation, recovery, saved proof and human rendering.
Use [acceptance](acceptance.md#human-and-machine-views) for its handoff and independent recette boundary.

## Commands

~~~powershell
python "<skill-dir>/scripts/configure_gtm.py" validate-contract --contract contract.json
python "<skill-dir>/scripts/configure_gtm.py" run init --contract contract.json --run-id RUN-001 --source-locator "Approved input" --output configuration-run.json
python "<skill-dir>/scripts/configure_gtm.py" run validate --run configuration-run.json
python "<skill-dir>/scripts/configure_gtm.py" run inspect --run configuration-run.json
python "<skill-dir>/scripts/configure_gtm.py" run checkpoint --run configuration-run.json --operation OP-001 --state in_progress --note "Fresh pre-change readback matched" --pre-write-readback before.json
python "<skill-dir>/scripts/configure_gtm.py" run checkpoint --run configuration-run.json --operation OP-001 --state verified --note "Saved readback matched" --result saved-result.json --saved-readback saved-object.json
python "<skill-dir>/scripts/configure_gtm.py" run reopen --run configuration-run.json --operation OP-003 --note "Blocker resolved and target revalidated."
python "<skill-dir>/scripts/configure_gtm.py" run render --run configuration-run.json --output configuration-result.md
~~~

Baseline capture is an engine action: `execute_ready_operations` obtains authenticated paginated
resources and workspace status. Manual checkpoints use the same readiness and comparison gates.
For a delta, `before.json` contains the raw authoritative target object, including its current name.
Server-generated IDs/fingerprints are tolerated; intended fields remain drift-sensitive.

A `saved-object.json` is a target-scoped graph:

~~~json
{"objects": [{"target_id": "web-main", "object_type": "tag", "name": "GA4 - purchase"}]}
~~~

Include every comparable intended field. When the primary object uses raw GTM IDs, supply referenced
objects in `context_objects`; these resolve references without adding intended mutations. A removed
object uses JSON `null`. Checkpoints load sources under the run lock and return coded errors for
invalid JSON/graph shape, duplicate keys, non-finite values, excessive nesting, unsafe transitions,
materialization drift and unsafe overwrite.
