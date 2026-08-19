# Tracking refonte workflow

## Contents

- [Use this route only for an authorized refonte](#use-this-route-only-for-an-authorized-refonte)
- [Capture one authoritative baseline](#capture-one-authoritative-baseline)
- [Reconcile the client inventory](#reconcile-the-client-inventory)
- [Rebuild analytics and remap consumers](#rebuild-analytics-and-remap-consumers)
- [Control destructive changes](#control-destructive-changes)
- [Verify the final graph](#verify-the-final-graph)
- [Produce the inventory-aligned change log](#produce-the-inventory-aligned-change-log)

## Use this route only for an authorized refonte

Load this playbook when the user explicitly asks to migrate an existing web container to a new
tracking plan and supplies or authorizes decisions about legacy tags. A refonte is not general
cleanup: it replaces or remaps only the analytics and dependent media surface justified by the new
plan and the client inventory. Do not optimize unrelated tags, folders, templates, custom code,
settings, or container history.

Use a durable configuration-run artifact. Record the tracking plan as analytics authority, the
client inventory as disposition authority, current official documentation as technical authority,
and the complete container baseline as integration evidence.

## Capture one authoritative baseline

Before designing deltas, make one complete, paginated read of every relevant container resource
family and the target workspace's current changes. For a whole-container refonte, this means all
tags, triggers, variables, built-ins, folders, templates, Google tag configuration/destinations,
and every other resource family exposed by the adapter. Store stable IDs, fingerprints, references,
paused state, consent settings, template versions, and pre-existing workspace attribution locally.

Build the dependency graph locally. Do not repeatedly list the same resource family during design.
Re-read only an object about to be reused or changed, every object after saving, and the affected
family after a conflict, pagination anomaly, authentication change, or externally observed
workspace change.

## Reconcile the client inventory

Preserve the inventory's row identity and order. Assign every in-scope existing tag exactly one
disposition:

- `keep`: semantically and technically compatible; do not rewrite it merely for style;
- `update`: same owned purpose, with authorized field or setting changes;
- `remap`: same destination purpose, but trigger, variable, parameter, consent, or source mapping
  changes to the new tracking plan;
- `pause`: retained but intentionally inactive;
- `remove`: explicitly authorized deletion;
- `replace`: same semantic identity cannot reach the target through supported update;
- `supersede`: a new graph takes ownership while the old object remains only as explicitly agreed.

Treat client feedback as authority for keep/pause/remove intent, not as proof that the legacy
technical implementation is correct. Resolve conflicts with the new tracking plan explicitly.
Append one row for each genuinely new tag; never reorder, delete, merge, or silently duplicate the
client's source rows.

Bind each row to exactly one tag operation. `added` maps to create; `keep` to proved reuse or
untouched state; `update`/`remap` to the corresponding delta; `pause`, `remove`, and `replace` to
those exact governed actions. The before identity must equal the operation's `pre_change`, and the
after name must equal its target. Related trigger/variable operations may be linked too, but cannot
stand in for the one tag operation. This prevents a `keep` row from concealing an update.

## Rebuild analytics and remap consumers

Reconstruct the analytics graph from the approved tracking plan, not from legacy naming or payload
prevalence. Decide page-view ownership, Google-field ownership, event mappings, ecommerce route,
consent topology, firing option, and external administration before mutation.

For every kept media, affiliate, analytics, and browser-transporter tag, trace trigger and variable
consumers recursively. Map its business objective to the new plan's actual event and source
contract. Update the normal trigger, blocking trigger, variable shapes, template fields, and
parameters when authorized. Never assume an old conversion event still represents the new
business event merely because the tag should remain active.

Inspect every Custom HTML tag and custom template in scope as code/configuration evidence. Determine
its real vendor, payload, triggers, storage/network effects, and consumers before assigning a
disposition. Prefer a compatible native or supported template for new or replaced implementation;
do not convert unrelated retained code merely to standardize the container.

## Control destructive changes

Routine refonte authority permits documented create/update/remap/reuse. `remove` and `replace`
still require explicit destructive authority for the exact objects. Capture stable object ID,
consumers, pre-change state, reason, and recovery boundary before either action.

When an object marked `keep` appears only because of a current workspace edit, prefer abandoning
that object's workspace change when the adapter can restore the underlying saved version cleanly.
Do not delete and recreate it. Never abandon unrelated workspace changes.

Do not invent intended firing triggers or consent topology for a removed tag. Its exact
`pre_change`, consumers, destructive authority, and `remove` disposition are the proof. A paused
tag likewise keeps pre-change execution evidence without pretending that it remains an active
target topology.

## Verify the final graph

After mutation:

1. re-read every created, changed, reused, and disposition-controlled tag;
2. expand shared variables and recursively verify all affected consumers;
3. prove every new tracking-plan event has the intended tag, source, trigger, consent topology,
   fields, and page-view/ecommerce owner;
4. prove every inventory row has one disposition and the saved tag state matches it;
5. separate pre-existing workspace changes, current-run changes, and final workspace totals;
6. rerun the same target comparison and require no remaining action.

Runtime behavior remains recette work. Publication and version creation remain prohibited.

## Produce the inventory-aligned change log

Generate the human change log from the disposition records, not from an independently summarized
list. Keep one row per final tag and preserve source order. Append new tags after the original rows.
Include at least:

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

Compute executive counts from these rows. Do not claim final workspace tag totals as current-run
creations.

## Reconcile browser-to-server migration

When the refonte changes delivery architecture, add a disposition per existing browser and server
route: retain browser-only, add transporter, server replaces browser, retain dual with shared ID,
update server consumer, pause/remove with explicit authority, or leave untouched. Do not delete a
browser media tag merely because a server tag is planned; first establish the exact destination
overlap and dedup/replacement strategy.

Configure and verify the receiving Client and server destinations before a live web endpoint
cutover. Inventory output must show before/after transport endpoint, page-view owner, normal and
blocking triggers, Event Data mappings, server consumer, consent topology, dedup identity, and
external rollout order for every affected tag.
