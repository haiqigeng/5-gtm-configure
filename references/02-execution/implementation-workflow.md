# Operational implementation workflow

## Contents

- [Run one configuration loop](#run-one-configuration-loop)
- [1. Resolve only blocking inputs](#1-resolve-only-blocking-inputs)
- [2. Create or reuse the workspace](#2-create-or-reuse-the-workspace)
- [3. Research the product and installed template](#3-research-the-product-and-installed-template)
- [4. Inspect relevant container integration](#4-inspect-relevant-container-integration)
- [5. Build the configuration map](#5-build-the-configuration-map)
- [6. Design and preflight the object graph](#6-design-and-preflight-the-object-graph)
- [7. Mutate in dependency order](#7-mutate-in-dependency-order)
- [8. Read back, correct, and hand off](#8-read-back-correct-and-hand-off)

## Run one configuration loop

Execute the eight steps in order. Use one concise configuration map for authority and intended
objects, and one durable configuration-run artifact for checkpoints, readback, recovery, and
handoff when the execution surface permits it. Detailed product playbooks resolve only the
requirements present.

## 1. Resolve only blocking inputs

Parse every supplied plan sheet, brief, direct instruction, and relevant technical attachment.
Record stable requirement IDs and an explicit included/reference/excluded source-scope manifest.
Discover safe container, adapter, template, CMP, and destination facts before asking.

Analytics requires an approved event/action, source event, success timing, exact outgoing fields
and literals, source mappings, and business filters. Media requires product, objective, use,
destination identity, and source authorization; the official browser schema supplies destination
fields. Consent requires the exact product and CMP grant path; strict/basic is the default.

Batch only unresolved facts that change or block configuration. Do not infer a destination ID,
analytics field, source path, CMP signal, template field, advanced-consent route, or destructive
authority. A mapped field that may be empty at runtime is not a design blocker and does not justify
a payload-eligibility helper.

## 2. Create or reuse the workspace

Resolve account and web container by stable ID. Reuse a dedicated workspace only when it belongs to
the same implementation and has no incompatible conflict; otherwise create one. Avoid Default
Workspace unless explicitly accepted. Record workspace ID, sync/conflict state, pre-existing
changes, adapter capabilities, and environment before writes. Never publish or create a version.

## 3. Research the product and installed template

Open current official pages for each exact browser product, event/schema, template, and consent
route. Inspect installed template identity/version, fields, permissions, defaults, and automatic
behavior. Use a compatible native or supported template; absence of install/update authority is
`Blocked`, not silent Custom HTML permission.

For analytics, compare documentation with the approved contract. Preserve a technically valid
advisory by default and report it; stop a blocking technical error. For media, map the brief to the
vendor's current browser schema without analogy. Preserve the official-source record needed for
each material write.

## 4. Inspect relevant container integration

Inspect only objects that can supply, consume, duplicate, conflict with, route, gate, or be reused
by the requested setup. Include installed templates, relevant built-ins, Google tag/destinations,
normal and blocking triggers, shared variables/settings, folders, sequencing, consent ownership,
automatic collection, and applicable Zone/environment/container restrictions.

Select the target documented architecture before evaluating local reuse. Existing prevalence is
not best-practice evidence. Trace every affected consumer for a delta, fingerprint the exact
pre-change state, and separate pre-existing workspace changes from current-run actions. Do not
reproduce a legacy pattern; do not turn the exercise into a tracking-plan or container audit.

## 5. Build the configuration map

Create one record per independently configurable requirement/destination. Keep analytics and media
authority separate. Capture only what mutation and proof need:

- stable requirement/source locator, approved action, success moment, source event/path/type/shape;
- destination identity, official event/conversion, exact outgoing field set, and intended use;
- approved actual source/authority and source shape → GTM method → template field →
  destination field/shape, including missing-data behavior;
- template/version, normal trigger, consent route, firing option, folder, and dependencies;
- one object action with canonical resource family, intended fields, evidence, and pre-change state
  for deltas;
- blocker, external owner, and expected saved comparison.

Use `requirement_ids` on every object in a multi-requirement map. Validate normalized v5 JSON before
the first write. Use `replace` only as the single governed action defined by the run/recovery
reference; never encode it as contradictory remove-plus-create rows.

## 6. Design and preflight the object graph

Build the smallest understandable graph. Justify every create or update with an approved
requirement or documented constraint. Prefer direct template fields and DLVs, then stable constants
or genuinely shared settings variables, then LUTs or RLTs for real deterministic multi-scenario
mappings. Use narrow CJS only for a required shape conversion.

Create precise normal triggers and the smallest reusable basic-consent block set. Attach the
complete block set to every in-scope vendor base/configuration and event tag. Use a verified CMP
readiness/grant event independently when it supplies an initial or later-grant firing opportunity.
For a vendor-wide Custom Event block, prefer a verified `.*` regex scope; use a narrower scope only
for a documented consumer boundary. Reconcile page views, automatic/manual business events, shared
execution units, routing, and environment isolation.

For ecommerce, preserve every mapped item and exact destination shape. Do not assume analytics and
media catalog IDs match, filter invalid items silently, invent a fallback, or turn an empty
transformation into a generic firing gate.

Preflight stable target/authority, complete pagination, source fidelity, GA4 safety, template
support/permission deltas, shared consumers, consent truth, dependency order, fingerprints, and
zero-difference intended analytics semantics. Render a What-If view for review; routine authorized
writes do not require a new pause. High-impact/destructive actions still require their explicit
authority.

## 7. Mutate in dependency order

Prefer GTM MCP, then API, then authorized export/import, then signed-in UI for unsupported semantic
fields. Discover exact actions and pagination; never guess an alias or treat the first page as the
inventory.

Write only in-scope dependencies, normally:

1. approved templates and folder;
2. built-ins, constants, DLVs, settings/LUT/RLT variables, and transformations;
3. normal and blocking triggers;
4. authorized Google tag configuration/settings and base tags;
5. event/conversion/remarketing tags;
6. sequencing, firing options, and consent settings.

Checkpoint `in_progress` immediately before one write. Re-read it immediately afterward and record
`verified`, `failed`, or `uncertain`. Retry only a documented non-applied rate-limit response within
a bound. On timeout or ambiguous response, read by stable parent and semantic identity before any
retry. Stop dependents on auth, fingerprint, consumer, schema, or readback conflict.

## 8. Read back, correct, and hand off

Re-read every created, updated, replaced, and reused object. Compare exact intended and stored
fields, resolved references, template permissions/version, triggers, consent, firing options,
folder, and fingerprint. The three documented built-in page triggers may remain reserved ID
references; every other in-scope reference needs closure.

Prove analytics requirement equality and media brief-to-official-schema mapping. Recompute the
change map so a second identical run is entirely reuse/untouched. Correct safe current-operation
differences; preserve a precise recovery boundary when not safe.

Apply canonical status rules, then render the executive summary, analyst/developer change log, and
machine recette handoff from the same validated run. State that runtime recette and publication did
not occur.
