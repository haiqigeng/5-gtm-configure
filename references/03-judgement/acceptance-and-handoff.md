# Operational acceptance and handoff

## Contents

- [Configured means saved and verified](#configured-means-saved-and-verified)
- [Operational statuses](#operational-statuses)
- [Configuration judgement matrix](#configuration-judgement-matrix)
- [Analytics and consent proof](#analytics-and-consent-proof)
- [Three-layer handoff](#three-layer-handoff)

## Configured means saved and verified

Assign `Configured` only when Authoritative saved-workspace readback proves the complete in-scope
graph matches the approved requirement. Require all applicable invariants:

1. stable account/container/dedicated-workspace identity, synchronization/conflicts, environment,
   and pre-existing workspace changes are recorded;
2. approved analytics authority or explicit media brief, current official technical evidence,
   installed template/version, and relevant container integration are established;
3. Select the best-practice architecture before considering container reuse; every action has
   evidence, and every delta has consumer tracing and exact pre-change state;
4. every outgoing field resolves from approved source through GTM and template to the exact
   destination field; zero/false and all mapped array items are preserved;
5. every active tag has typed semantic normal/block references bound to its saved trigger arrays,
   lifecycle role, firing option, built-in and Additional Consent Check state, and strict/basic or
   approved advanced route; removed or paused tags instead retain exact pre-change evidence, with
   pre-CMP and automatic/manual conflicts reconciled;
6. every current-run mutation and reused dependency is re-read; exact fields, references,
   template permissions/version, folder, consent, and fingerprint compare successfully;
7. analytics approved-to-saved conformance or media brief-to-official-schema mapping has zero
   unauthorized difference;
8. an identical rerun is reuse/untouched, external dependencies are separate, and no runtime
   recette, publication, Submit, or GTM version action occurred.

Static proof does not certify browser, network, dataLayer, CMP-journey, or vendor-platform behavior.

## Operational statuses

Use one status per independent requirement and one accurate overall run status:

| Status | Meaning |
| --- | --- |
| `Configured` | Complete applicable saved graph is proven by readback; no write is needed when it already matched. |
| `Partial` | Current-run work saved, but a dependent graph is unfinished or uncertain. Record exact saved state and recovery boundary. |
| `Blocked` | A critical authority, source, destination, template, consent, conflict, access, or mutation fact prevents any affected save. No planning/specification status substitutes for configuration. |
| `Deferred` | The requirement belongs to future server-side GTM, CAPI, or browser/server deduplication. Separately judge any valid client-side portion. |

Never call a returned adapter response `Configured` without readback. Never call a run `Blocked` if
it already saved current-run work; that state is `Partial`.

## Configuration judgement matrix

| Case | Result |
| --- | --- |
| Complete saved graph, readback equality, no-op rerun | `Configured` |
| Valid custom analytics event with a recommended alternative | Report advisory; preserve approved event; `Configured` if all other checks pass |
| Recommended/optional field absent from plan | Preserve exact approved set; report advisory; do not add it |
| Reserved/invalid event, missing required design-time field, unsupported template field | `Blocked` for the affected requirement pending amended authority or capability |
| Approved source mapping may resolve empty at runtime | Configure directly; record runtime missing data as a site/dataLayer and recette dependency |
| Empty transform result | Do not infer that the tag cannot fire and do not add a generic validity gate |
| Existing exact semantic object | Reuse and read back; name alone is insufficient |
| Relevant duplicate/automatic conflict with no reconciliation authority | `Blocked`; do not add a parallel duplicate |
| Authorized update/rename/pause/unpause | Capture consumers and exact pre-change state; read back the saved delta |
| Same-identity migration cannot be updated | Use one authorized `replace` action with recovery, never remove plus create rows |
| Compound CMP predicate | Use native trigger logic or OR-denial blocking triggers; prove unknown/denied block and later grant path |
| CMP readiness/grant event is the normal page-load trigger | Keep the strict/basic vendor block on the tag; the event supplies timing while the block supplies eligibility |
| Business event can occur before CMP readiness | Use a post-readiness source event, later fresh equivalent event, or explicitly approved one-time retained-payload replay; otherwise record a site dependency. Never treat a Trigger Group as replay. |
| Google tag page-view ownership is ambiguous | `Blocked` for that tag change until exactly one automatic, dedicated, external, or intentionally-none owner is established. |
| Template permission expansion | Surface the exact delta and require the applicable explicit authority |
| Adapter timeout/ambiguous write, no decisive readback | `Partial` if earlier work saved; otherwise unresolved/blocked. Never retry blindly |
| Adapter unavailable before mutation | `Blocked`; state the exact capability/access needed |
| Server/CAPI/deduplication-only request | `Deferred`; never generate a browser event ID |

## Analytics and consent proof

For analytics, compare approved and intended before mutation, then approved and saved after mutation.
Require exact included IDs, destination/source events, timing, filters, outgoing field set, and
source/literal per field. Advisories do not authorize changes; blocking technical errors stop only
their dependent graph.

For each product consent route, record:

- normal trigger and its event scope;
- strict/basic blocking mechanism plus its independent normal trigger, which may be a CMP
  readiness/grant event, or an explicit advanced/native mechanism;
- exact CMP state/identity and current official evidence;
- unknown, uninitialized, denied, granted, later-grant, and revocation expectations;
- shared execution-unit consumers and one consent owner where applicable.

This proves configured Boolean logic, not observed consent behavior.

Accept an execution topology only when its typed semantic trigger/block references equal the exact
saved tag arrays. Accept page-view ownership only when the referenced saved Google/GA4 tag types
and effective `send_page_view` values agree. Accept first-party-data routing only when the mapped
destination field exists on every correct-product consumer. For a refonte, accept each inventory
disposition only when it matches exactly one compatible tag operation and its saved before/after
identity. Removed or paused tags are proved from pre-change state, not target topology.

## Three-layer handoff

Generate all layers from the validated `configuration-run@2.0` artifact so human and machine views
cannot drift.

### 1. Executive summary

Keep it short: overall verdict, stable target/workspace, requirement count, created/updated/replaced/
reused counts, consent route summary, blocker or recovery boundary, and explicit no-publication
statement.

### 2. Analyst and developer change log

For each requirement include:

- approved source locator and business success moment;
- object actions, names, stable IDs, dependencies, and saved comparison;
- Payload map: approved source/shape → mapping method/GTM resolution → template field →
  destination shape/field/status;
- normal trigger, blocking/grant mechanism, firing option, template version/permission delta;
- external owner/action and final status.

Report pre-existing workspace changes, current-run actions, and final workspace totals separately;
never attribute the final total to the agent.

For a refonte, generate tag-level rows from the validated inventory dispositions. Preserve the
client's original row identity/order, append only new tags, keep exactly one row per tag, and show
before/after tag names, normal/blocking triggers, variables, parameters, consent, rationale, and
saved evidence. Derive executive counts from those rows.

### 3. Machine/recette handoff

Return the complete versioned run JSON with one record per stable requirement ID. Include expected
tags, normal/blocking triggers, consent states, expected first-party-data keys, network cues, and
Recette cues needed by the separate Preview skill, plus saved IDs,
fingerprints, payload mappings, official sources, external dependencies, idempotency, and recovery
boundary. Set `runtime_validation_performed` and `publication_performed` to false.

When the run is `Partial`, the recovery boundary must name the last verified operation, every
unsafe/uncertain operation, and the next authoritative readback action. When `Blocked`, state the
smallest missing fact or capability. When `Deferred`, name the future owner without implying that
client-side configuration failed.
