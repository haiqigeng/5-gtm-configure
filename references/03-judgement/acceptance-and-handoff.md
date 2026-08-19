# Operational acceptance and configuration result

## Contents

- [Configured means saved and verified](#configured-means-saved-and-verified)
- [Operational statuses](#operational-statuses)
- [Per-target and pipeline proof](#per-target-and-pipeline-proof)
- [Human and machine views](#human-and-machine-views)
- [External publication sequence](#external-publication-sequence)

## Configured means saved and verified

`Configured` means the complete authorized GTM object graph is saved, authoritatively read back,
equal on every comparable intended field/reference, and an identical rerun proposes zero mutations.
For a pipeline, every required target and cross-target sender/Client/Event Data/consumer relationship
also passes static proof. A plan, prose specification, unverified save, one-sided pipeline, or
runtime expectation is not `Configured`.

Never claim browser/server delivery, consent behavior, vendor receipt, deduplication, attribution,
or reporting without the separate recette evidence. Never publish or create a GTM version.

## Operational statuses

| Status | Exact meaning |
| --- | --- |
| `Configured` | Every in-scope required operation and target is verified; static cross-target invariants and identical-rerun no-op pass. |
| `Partial` | At least one current-run save is verified or may have saved, but the complete graph is not proved. Name the exact target and recovery frontier. |
| `Blocked` | No required saved result can safely proceed because authority, source, capability, template, target, or critical technical evidence is absent. |
| `Deferred` | An explicitly out-of-scope/future owner remains, without implying that completed in-scope saved configuration failed. |

Do not invent `Specification complete`, `Ready to configure`, or another planning status. Open
runtime/publication dependencies do not downgrade a saved verified setup from `Configured`.

## Per-target and pipeline proof

For every target require:

- stable target/workspace identity, complete baseline, pre-existing change attribution, and adapter
  capability evidence;
- every create/delta/reuse read back with resolved references, template identity/permissions,
  trigger/consent, firing settings, folder, and semantic fingerprint;
- exact analytics conformance or media-brief-to-current-schema mapping;
- no unresolved duplicate/conflict within the requested graph; and
- a target-local zero-mutation rerun.

For a pipeline additionally require:

- all authorized senders and receiver saved and verified;
- exactly one intended claiming Client per request class and reachable receiver consumers;
- source-to-wire-to-Event-Data-to-destination paths and shapes, including complete item cardinality;
- one effective consent topology per destination with every triggering event covered;
- one occurrence identity across each overlapping browser/server route and no server regeneration;
- live cutover dependency closure over all required receiver objects; and
- no asymmetric route that would silently duplicate, drop, or reroute a required event.

Secret fields can be `present-not-compared` while all non-secret fields and field presence match.
This proves saved structure, never equality of hidden secret values.

## Human and machine views

Derive every view from the same validated run:

1. **Executive summary:** overall and per-target status, scope, object counts, major consent/delivery
   decisions, blocker/recovery frontier, and explicit no-publication/no-runtime statement.
2. **Analyst/developer change log:** one row per object/action with target, before/after name,
   normal/blocking triggers, variables/parameters, Client/Event Data mapping, consent, dedup,
   rationale, saved ID/readback, and external owner. For a refonte, preserve client inventory row
   identity/order and append only genuinely new tags.
3. **Machine-readable run record:** the same target identities, operation states, mappings,
   comparisons, saved readback, recovery state, and explicit no-publication assertion used to
   derive the human views.

When `Partial`, name the last verified operation, every failed/uncertain operation and transitive
dependent, and the next authoritative readback. When `Blocked`, name the smallest missing fact or
capability. When `Deferred`, name its owner without claiming it was attempted.

Runtime recette is independent. It uses the tracking plan and live GTM/Preview evidence and does
not consume or treat the configuration result as acceptance evidence.

## External publication sequence

Configuration stops at saved workspaces. Record this external order without executing it:

1. publish the verified server workspace;
2. run server recette;
3. publish the verified web cutover;
4. run web and end-to-end recette.

These dependencies protect rollout order. They do not become configuration blockers and do not
authorize Submit, version creation, or publication.
