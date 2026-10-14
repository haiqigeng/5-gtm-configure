# Operational implementation workflow

Use one contract and execution engine for web, server and pipeline work. Load the feature and host
guides selected by the request. [Authority](authority.md) owns scope and approval;
[evidence](evidence.md) owns research; [authoring](authoring.md) owns declarations;
[execution](execution.md) owns state transitions; [acceptance](acceptance.md) owns the result.

## 1. Resolve the request

Read the approved plan, brief or direct requirement and classify included, reference-only and
excluded requirements. Discover available target, adapter, template and CMP facts. Resolve the
remaining [blocking inputs](authority.md#resolve-blocking-inputs) together.

## 2. Establish the workspace

Resolve stable account/container/workspace IDs and container type. Reuse the authorized dedicated
workspace, inspect its status/conflicts and retain pre-existing edits. Establish authority for each
target under [target authority](authority.md#target-authority).

## 3. Establish technical feasibility

For changed product or collection behavior, inspect current official guidance and installed
capability using [the research procedure](evidence.md#research-procedure). Classify discrepancies
before implementation. Folder-only work uses native capability and container evidence.

## 4. Inspect integration and reuse

Select the target architecture, then trace its dependencies and shared consumers. Capture each
required family with exhausted pagination through the authenticated runtime; analyze the graph
locally. Refonte uses the complete inventory and ordered dispositions in [refonte](../refonte.md).
[The adapter contract](../adapters/custom.md) owns baseline, identity and refresh mechanics.

## 5. Compile the configuration map

Use [compact input](authoring.md#compact-input) to derive mechanical identities, source-bound
approval records and reuse dependencies. Supply complete intended snapshots, delta pre-change
snapshots and the applicable field, execution, consent, page-view and first-party-data decisions.
For pipelines, bind transport, claiming Client, Event Data, receivers and overlapping-delivery
identity. The compiler preserves approved semantics and leaves judgment explicit.

## 6. Preflight

Validate the contract and applicable analytics conformance. Review the compiled delta against its
approved sources, installed capability and feature owners. Choose the least-complex supported
mapping under [data mapping](../data/mapping.md); resolve policy or field decisions before executing
the affected owners. Shared dependencies can serve ready requirements under
[dependency readiness](execution.md#contain-failures-by-dependency).

Give a concise change summary once discovery and validation are complete. Render a separate
preflight preview when it helps review; routine already-authorized work can proceed from that summary.

## 7. Execute

Bind the authenticated adapters from [adapter selection](../adapters/overview.md) and use the
[durable lifecycle](execution.md). The runtime captures baselines, compares pre-change state,
journals writes and verifies native results in dependency order. Resolve failure or uncertainty
through its recorded recovery frontier. Pipeline cutover follows verified receiver dependencies.

For long runs, report meaningful progress and use [quota sizing](../adapters/quotas.md) to distinguish
API requests, transport calls, local compute and recovery time.

## 8. Converge and hand off

Run fresh read-only convergence, correct any changed intended state and derive the result through
[acceptance](acceptance.md). Report findings and changed fields first, unchanged counts second,
with full machine evidence and external owners retained.
