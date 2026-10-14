# Tracking refonte workflow

## Establish migration authority

Use this route for an explicitly authorized migration to a new tracking plan with legacy-object
dispositions. The plan owns analytics semantics, the client inventory owns dispositions, current
official evidence owns technical validity and the container baseline establishes integration state.
[Authority](core/authority.md) bounds the affected analytics and dependent media surface.

## Capture the integration graph

Apply [execution baseline and delta rules](core/execution.md): complete relevant resource families,
workspace attribution, native IDs/fingerprints, references, pause/consent/template state. A whole-
container refonte includes all exposed applicable families. Build the dependency graph locally and
reuse the evidence under the adapter's freshness/conflict rules.

## Reconcile the client inventory

Preserve source-row identity/order and assign each in-scope tag one disposition:

| Disposition | Meaning |
| --- | --- |
| `keep` | Proved compatible reuse/untouched state. |
| `update` | Same owned purpose with authorized field/settings delta. |
| `remap` | Same destination purpose mapped to the new source/trigger/consent contract. |
| `pause` | Retained inactive. |
| `remove` | Exact authorized deletion. |
| `replace` | Same semantic identity requires a supported replacement. |
| `supersede` | New graph takes ownership with the old object's explicitly agreed disposition. |

Bind each row to one actual tag operation; related variable/trigger operations supplement it.
Before identity equals `pre_change`, after name equals its target, and action matches disposition.
Append genuinely new tags as `added` rows after source rows. Client intent and technical compatibility
have separate evidence; resolve conflicts with the new plan before the affected mutation.

## Rebuild and remap consumers

Build analytics from approved semantics and the applicable feature owners. Trace every kept media,
affiliate, analytics and transporter consumer recursively to its new action/source contract.
Inspect in-scope HTML/templates for actual vendor, payload, storage/network effects and consumers.
Supported updates/remaps implement only the authorized purpose.

[Target authority](core/authority.md#target-authority) governs destructive actions and recovery proof.
For a compatible kept object altered only in the current workspace, an authorized supported abandon
can restore its underlying saved version. Pause/remove preserve pre-change execution evidence under
[web execution](web/execution.md); active intended topologies belong to their actual active actions.

## Verify and hand off

Read back the affected graph, expand shared fields/consumers, prove each new requirement and each
inventory disposition, separate pre-existing/current/final workspace attribution, and converge to
no remaining action. [Acceptance](core/acceptance.md) owns the final verdict and external handoff.

Generate the inventory-aligned log directly from disposition records, preserving source order and
appending new tags. Executive action counts derive from those rows.

| Column | Content |
| --- | --- |
| Source row / vendor / client remark | Exact source identity and supplied context |
| Disposition | Added, kept, updated, remapped, paused, removed, replaced, or superseded |
| Tag name before / after | Exact saved names, with blank before for a new tag |
| Trigger before / after | Normal and blocking triggers, not a vague “consent updated” note |
| Variable changes | Added, removed, reused, or remapped variables and source paths |
| Parameter changes | Destination fields and before/after ownership or values |
| Consent changes | Built-in checks, Additional Consent Checks, normal consent event, and blocks |
| Rationale / evidence | Tracking-plan row, client instruction, documentation, and readback |

## Reconcile browser-to-server migration

Give each affected delivery route an explicit retain/add/replace/dual/update/pause/remove/untouched
disposition. Establish destination overlap and replacement/deduplication strategy before changing
existing browser ownership. Follow [receiver-first ordering](pipeline/architecture-and-workflow.md#build-receiver-first).
Inventory output records before/after endpoint, occurrence owner, triggers, Event Data/consumer,
consent, dedup identity and external rollout dependencies.
