# Operational acceptance and configuration result

## Configured means saved and verified

`Configured` means the complete authorized GTM graph is saved, authoritatively read back and equal
on every comparable intended field/reference, with a fresh identical-rerun comparison proposing
zero mutations. For pipelines, all required targets and static cross-target relationships pass.
The runtime implements the gate in [finalization](execution.md#finalize-once-from-proved-state).

This verdict covers saved structure. Runtime delivery claims require independent recette evidence
under the [scope boundary](authority.md#boundaries).

## Operational statuses

Use the statuses derived from the validated run:

| Status | Meaning |
| --- | --- |
| `In progress` | Required configuration or verification work remains. |
| `Configured` | The complete saved-configuration gate above passes. |
| `Partial` | Some current-run work is verified or may have saved, while the complete graph remains unproved. Identify its recovery frontier. |
| `Blocked` | Required work cannot safely proceed because an applicable authority, input, capability, target or evidence prerequisite is unresolved. |
| `Deferred` | A declared future/external owner remains; state its scope and whether any work was attempted. |

Open external runtime or publication work is reported separately from the status of completed
in-scope configuration. Unsupported write or verification capability leaves affected configuration
blocked; a specification alone cannot establish a saved result.

## Per-target and pipeline proof

Review the evidence produced by the existing validators and execution engine:

- Each target has stable identity, a complete relevant baseline, capability evidence and attribution
  of pre-existing workspace changes.
- Each required object has intended/saved comparison with resolved references and applicable
  template, firing, consent, folder and permission fields.
- Requirements retain approved analytics semantics or the media brief's exact product mapping,
  with applicable [source evidence](evidence.md).
- The intended graph is free of unresolved identity conflicts and has a fresh zero-mutation rerun.

Pipeline evidence additionally establishes the intended claiming Client per request class,
receiver reachability, complete source/wire/Event Data/destination paths and shapes, event coverage
under each consent route, shared occurrence identity where delivery overlaps, and receiver-before-
cutover dependency closure. Required occurrences retain their approved destinations and cardinality.

Interpret redacted fields using [secret comparison](execution.md#handle-secrets-without-false-equality):
matching presence is distinct from hidden-value equality.

## Human and machine views

Derive both views from the same validated run:

1. **Summary:** overall and per-target verdict, scope and counts, major decisions, blockers/recovery
   frontier, and the saved-configuration boundary.
2. **Change log:** changed objects with target, before/after name and fields, rationale, saved
   identity/readback and external owner. Include relevant triggers, variables, Client/Event Data,
   consent and dedup changes. Summarize unchanged objects by count; keep their full machine records.
   Refonte retains client row identity/order and appends new tags. Include source title, URL,
   access date, affected requirements and applied decision.
3. **Machine record:** target identities, operation states, mappings, comparisons, readbacks,
   recovery frontier and publication assertion from the durable run.

For `Partial`, identify verified work, failed/uncertain operations, dependent blockers and the next
readback or repair. For `Blocked`, identify the smallest missing decision or capability. For
`Deferred`, identify the responsible external owner. Recette uses its own tracking plan and live
evidence; the configuration artifact provides a configuration record, not runtime certification.

## External publication sequence

Link the [external rollout sequence](../pipeline/architecture-and-workflow.md#separate-saved-configuration-from-publication)
in the handoff when deployment depends on coordinated targets. Its owners perform draft acceptance,
separately authorized publication and post-publication smoke checks after configuration handoff.
