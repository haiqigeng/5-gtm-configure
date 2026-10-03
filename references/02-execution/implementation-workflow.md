# Operational implementation workflow

Use one contract and the same execution engine for web, server and pipeline work. Product references
are conditional: load only the product, fields, timing and consent behavior affected by this request.
The [utility contract](../01-orientation/utility-contract.md) owns authority and scope;
[run and recovery](configuration-run-and-resume.md) owns execution state.

## 1. Resolve only blocking inputs

Read the approved plan, brief or exact direct requirement. Record included, reference-only and
excluded requirements. Discover target, adapter, template and CMP facts before asking for missing
information. Do not infer source paths, destination identities, destructive authority or consent
policy. Empty values possible at runtime do not authorize generic eligibility helpers. Resolve a
documented harmful value through the scoped rule in [data contracts](data-contract-and-transformations.md#separate-configuration-completeness-from-runtime-data-quality).

## 2. Create or reuse the workspace

Resolve stable account/container/workspace IDs and container type. Reuse the authorized dedicated
workspace and preserve its existing edits. Avoid Default Workspace unless accepted. Capture status
and conflicts before writes. A server endpoint does not grant access to its server container.

## 3. Research the product and installed template

Use current official documentation for the exact changed feature and inspect installed template
fields, defaults, automatic collection, permissions and secret fields. Preserve valid approved
semantics; report an advisory without rewriting them. Hold a technically unsupported requirement.
A missing supported template is not authorization for Custom HTML or arbitrary vendor API code.
See [official-source-policy.md](../01-orientation/official-source-policy.md).

## 4. Inspect relevant container integration

Select the supported architecture, then inspect reuse, conflicts and dependency closure. List each
required family once through the authenticated runtime, exhausting pagination. Analyze consumers
locally. An authorized refonte uses the complete inventory and ordered dispositions in
[tracking-refonte.md](tracking-refonte.md). Shared Google Configuration Settings changes always
include all tag consumers. Refresh only where drift, changed identity, pagination anomalies or an
affected shared consumer requires it. Do not treat all available families as relevant.

## 5. Build the configuration map

Use [configuration-contract.md](configuration-contract.md) and its compact-input compiler to derive
object keys, source-bound approval records and explicit reuse dependencies. Keep business and
implementation authority separate. Supply full intended and pre-change snapshots; do not manufacture
consent, page-view or first-party-data decisions. Required active-tag topologies remain explicit.
A pipeline additionally needs transport, claiming Client, Event Data fields, receiver consumers,
consent and any overlapping-delivery dedup contract.

## 6. Design and preflight the object graph

Validate the contract before materialization. Check source fidelity, current template capability,
consent route, page-view ownership, first-party data, reference closure and dependency order. A
contract hash records consistency, not authorization. The compact input uses the same semantic
validator and does not bypass any acceptance check.

Choose direct mappings before helpers; justify each object by an approved requirement. Preserve
all approved items and non-scalar shapes. Read [cmp-consent.md](cmp-consent.md) for grant timing,
revocation and pre-CMP events, [google-field-ownership.md](google-field-ownership.md) for Google
settings, and the pipeline references only for connected transport. Resolve an existing advanced
route against the approved policy before writing; do not silently inherit or replace it.

Render a preflight preview for review without adding a new approval pause to already-authorized
routine work. Give a concise update once discovery and validation are complete.

## 7. Mutate in dependency order

Bind authenticated adapters using [tool-adapters.md](tool-adapters.md). The runtime captures the
baseline, verifies pre-change state, journals the write boundary and reads back each save. Do not
hand-edit active run state. Drift stops the affected operation. An ambiguous outcome requires
readback before retry; independent safe dependencies may continue.

For pipelines, receiver dependencies must verify before the sender endpoint changes. Keep actual
API calls separate from agent tool calls when measuring cost; batching transport is not evidence
that fewer API operations occurred. Report progress during a long run without inventing an ETA.

## 8. Read back, correct, and hand off

Use the runtime's fresh read-only convergence pass. A changed intended field requires correction;
workspace status alone is insufficient. Finalization derives status only when all saved comparisons
and applicable cross-target invariants pass. Render findings and changed fields first, unchanged
counts second, with full machine evidence retained. Apply
[acceptance-and-handoff.md](../03-judgement/acceptance-and-handoff.md). Configuration does not prove
browser execution, vendor receipt or reporting, and never includes publication or version creation.
