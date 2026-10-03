# Operational configuration contract

## Contents

- [Purpose and priority](#purpose-and-priority)
- [Keep business and implementation authority separate](#keep-business-and-implementation-authority-separate)
- [Use configuration-contract 7.0](#use-configuration-contract-70)
- [Map requirements and targets](#map-requirements-and-targets)
- [Map target-scoped object actions](#map-target-scoped-object-actions)
- [Map pipeline flow](#map-pipeline-flow)
- [Map consent and deduplication](#map-consent-and-deduplication)
- [Validate and materialize](#validate-and-materialize)

## Purpose and priority

Before the first write, create one concise requirement-to-object contract. It controls authority,
mutation, saved comparison, idempotency, and the configuration result; it is not a planning deliverable.

Resolve conflicts in this order: data/consent safety, approved semantic fidelity, current technical
validity, smallest maintainable architecture, compatible reuse and organization, then saved
completion. Never weaken a higher priority to make a graph look complete.

## Keep business and implementation authority separate

| Layer | Authority | Contents |
| --- | --- | --- |
| Approved analytics | Tracking plan or exact direct analytics decision | Meaning, event, fields/literals, source, success timing, filters, and repeatability |
| Approved media | Explicit media brief plus current official destination schema | Product, business action, destination identity/use, source authorization, and exact vendor mapping |
| GTM implementation | Applicable playbook, current documentation, inspected templates/Clients, consent, and target evidence | Workspaces, object actions, fields, dependencies, trigger/consent/dedup topology, and readback |

Technical infrastructure must serve approved requirements. A field does not gain analytics or media
authority merely because an implementation object supports it.

## Use configuration-contract 7.0

Every new mutation map uses `"schema_version": "7.0"` and
[`configuration-contract.schema.json`](../../schemas/configuration-contract.schema.json):

| Section | Contents |
| --- | --- |
| `mode` | `web`, `server`, or `pipeline` |
| `route` | `analytics`, `media`, `consent`, or `combined` |
| `scope` | Disjoint included, reference-only, and excluded requirement IDs |
| `requirements` | Approved semantics/business intent, source, destination, and field authority |
| `targets` | Explicitly authorized stable web/server workspaces with independent target IDs |
| `implementation.execution_mode` | `isolated-durable`, or `refonte-durable` |
| `implementation.objects` | Exact target-scoped GTM actions, intended state, and dependencies |
| `implementation.field_bindings` | Explicit resolution for every approved event, item or user field, including ordinary dataLayer parameters; pending fields are rejected before execution |
| `pipelines` | Sender/receiver graph, request/Client, page-view, event/field flow, and cutover |
| `consent_topologies` | Per-destination web, transport, server mechanism, signal, and event coverage |
| `execution_topologies` | One bound firing/blocking/consent/lifecycle decision per executing web tag |
| `page_view_decisions` | One effective owner per web destination and occurrence role, with an applicable `send_page_view` decision |
| `first_party_data_routes` | Approved user-data/User-ID feature, source, timing, hashing, consent, and consumers; native Ads event overrides also bind inspected parameter/control paths as described in the [Ads procedure](media-google-ads.md#configure-enhanced-conversions-only-explicitly) |
| `inventory_dispositions` | Ordered one-row-per-tag refonte disposition linked to exact object actions |
| `dedup_contracts` | Only overlapping delivery, with one occurrence identity and exact product fields |
| `evidence` | Approved, official-current, container-confirmed, and sample provenance |
| `external_dependencies` | Structured work outside the saved GTM graphs: `id`, affected `requirement_ids`, `owner`, `action`, and `status` (`open`, `resolved`, or `accepted`) |

Only version 7.0 is accepted. Older and unversioned inputs cannot authorize mutation.

## Map requirements and targets

Every requirement has a stable ID, exact source locator, and approved authority. Every analytics
parameter, user property, and item field needs approved provenance; official documentation
validates but cannot authorize an addition. For media, official documentation can authorize the
destination schema while objective, identity, and actual source remain approved input.

Use one requirement record per independently configurable destination, consent route, source
timing, environment, owner, or change path. Record source path/literal, type and complete shape,
destination field/shape, missing behavior, business timing, and filter. Preserve valid zero and
`false`. Do not create an identically named DLV from a destination field unless approved input
proves that exact source.

Every target record names its `target_id`, authoritative container type, account/container/workspace
IDs, and approved-input authority. Web authority does not imply server authority. In pipeline mode,
at least one authorized web sender and server receiver are required.

## Map target-scoped object actions

Represent each semantic object once under:

`<target-id>::<resource-family>::<semantic-name>`

Record the action, stable ID when existing, intended fields/references, dependencies, requirement
IDs, justification, evidence, risk, and exact pre-change state for every delta. Use `create`,
`update`, `replace`, `rename`, `pause`, `unpause`, `reuse`, `untouched`, or explicitly authorized
`remove`. `replace` is one governed same-identity action, never remove plus create.

Every delta requires `object_id` and a non-empty `pre_change`. Every executing target action and
every `reuse`/`untouched` action requires a non-empty `intended` compatibility target. `rename`
also requires `new_name`. Every mutating action requires an `approval` record that binds the
approved-input locator, action, object key, requirement IDs, and exact mutation payload hash;
`replace` requires a reason; and every template mutation records its permission delta. These are
validation rules, not optional documentation conventions.

Keep the approval record consistent with the reviewed implementation. Changes to action, identity,
requirements, intended/pre-change state, rename, replacement, permission, or scope invalidate its
hash. Reconcile the change with the original approved source before rebuilding the record; request
new authority only when existing authority does not cover it. The record provides traceability and
change detection, not independent proof of user approval. Follow the
[evidence and validation limits](../01-orientation/utility-contract.md#evidence-and-validation-limits).

For typed resources (tags, triggers, variables, Clients, and Transformations), retain `type` in
every applicable intended and pre-change snapshot. Use complete snapshots, even when the adapter
accepts a patch. A shared Google Configuration Settings mutation is high impact and must account
for consumers of its old and new type, including a type change or removal.

Web resource families are the complete supported surface: tag, trigger, variable, built-in variable,
folder, template, zone, environment, destination, Google tag configuration, container setting, and
workspace. Server families are Client, tag, trigger, variable, folder, template, Transformation,
container setting, and workspace. Subtypes remain in intended fields.

High-impact authority is required for deletion/replacement, shared Client claim/priority change,
broad Transformation, template import/upgrade/permission expansion, settings, Zone/environment,
and live endpoint cutover. A compatible existing Client may be reused routinely after authoritative
claim readback; its prevalence alone is not best-practice evidence. A Client reuse row must record
the expected Client type, exact claim criteria, and priority in `intended`, so readback proves
compatibility without mutating the Client.

Every create/update has a current approved or documented constraint. Reject duplicate actions,
collisions, missing/cyclic dependencies, and cross-target families that do not exist on that target.
A rerun against final state must resolve completed objects to `reuse` or `untouched`.

## Map pipeline flow

Each pipeline records sending target IDs, receiving server target, request class, transport owner,
endpoint reference, exactly one intended claiming Client and its criteria, and the initial-page-load
transport owner with explicit effective `send_page_view`. The full web decision surface remains
occurrence-scoped in `page_view_decisions`.

The endpoint reference must resolve to the endpoint saved on the transport owner. Every linked
consent topology lists the actual web tags that can emit its event occurrences. Each listed sender
must either own that same endpoint directly or bind the same destination identity as the transport
owner and therefore inherit its endpoint. An unrelated tag that merely shares a requirement ID is
not a proved transporter.

Each event-flow row binds an approved requirement/source event to the transported event and every
receiver tag. Every mapped field has exactly one pipeline identity composed of `requirement_id`,
`field_scope`, and `destination_field`; missing or duplicate identities fail. Each field-flow row resolves:

`approved source -> web variable -> wire field/shape -> claiming Client proof -> Event Data
path/shape -> server owner -> template field -> destination field/shape -> missing behavior ->
runtime verification note`

Prove every field, including scalar fields. `items` is an array and `user_data` is an object; never
encode a universal two-array rule. If shapes change, name the template-local mapper, supported
server variable, or scoped Transformation owner. Never silently flatten, stringify, truncate, or
drop a required value or item. A missing design-time source blocks; possible runtime absence is a
site/dataLayer and recette dependency, not a payload-eligibility CJS or trigger.

The pipeline operation dependencies must include the Client and all receiver consumers. A live
sender endpoint cutover is high impact and must depend transitively on every required receiver
operation. Configure and read back the receiver before cutover.

## Map consent and deduplication

For new strict/basic gates, the preferred convention is CMP lifecycle/business triggers plus vendor
blocks, with Additional Consent Checks empty. This is a local default, not the only vendor-supported
pattern. Preserve a proved existing firing-condition or Additional Consent Checks convention using
the explicit fields in [CMP consent](cmp-consent.md#existing-consent-conventions). Do not stack
equivalent gates. Built-in template checks remain intrinsic product behavior.

An explicitly approved ungated web policy uses `client-policy-ungated` in both consent and execution
topologies, with `signal_authority: none`, `unknown_state_behavior: explicit-policy`,
`transport_behavior: always-transported`, server mechanism `none` and no server/transporter bindings.
`web_enforcement` is `{"mechanism":"none","client_policy":{"grade":"approved-input","locator":"exact client instruction","scope":"approved site, audience and destination scope"}}`.
Its tag has no blocking triggers or Additional Consent Checks and no pre-CMP behavior. Absence of a
CMP or a country label never supplies this authority. Report the client policy without asserting a
legal exemption. Pipeline/server ungated policy is not implemented by this route.

For each pipeline destination, record `consent_mode`, `transport_behavior`, exact web mechanism,
exact server mechanism, signal source, denied/unknown behavior, and event coverage. Server mechanism
is exactly one of incoming Google-native consent, server-template-native consent, supported server
Additional Consent Check, server blocking trigger, or none. A destination blocked before transport
must not receive an equivalent server gate unless intentional double gating is explicitly justified.

Record dedup only when the same destination occurrence can arrive twice. A `dual-shared-id` route
binds browser and transporter to one occurrence source, transports it unchanged, and maps exact
current browser/server field names and companion fields. Purchase uses approved transaction/order
identity when the product supports it; do not replace it with a generated per-page occurrence ID.

Other dual events may use an approved supplied identity or the reviewed `generated-event-id`
route. Generated IDs require an installed-template review, exact consumer field bindings and one
direct source event without sequencing. See
[shared generation](pipeline/browser-server-deduplication.md#configure-shared-id-generation) for
the `generation` fields and preconditions. Do not create independent browser/server generators.

## Validate and materialize

Run `scripts/validate_configuration_contract.py` before mutation. For analytics, also use
`validate_contract_conformance.py` to prove identical requirement IDs, events, timing/filters,
declared outgoing field set, and approved sources/literals. The scoped native event-parameter checks below
connect supported implementation fields to that declaration; other structures and automatic
product behavior remain inspected ownership decisions.

The validated contract deterministically materializes active `configuration-run@4.0` sections.
Do not hand-edit requirements, pipelines, immutable operation intention/dependencies, payload maps,
consent topologies, dedup contracts, or publication dependencies; section fingerprints detect
drift. Adapters may populate baselines, journals, readbacks, comparisons, and results only.

Resolve field implementation in the contract, not by editing the materialized run. Each
`implementation.field_bindings` row requires `requirement_id`, `field_scope`,
`destination_field`, `status`,
`shape_compatibility`, `mapping_method`, `gtm_resolution`, `template_field`, and `missing_behavior`.
Deterministic native mapping proof covers explicit scalar GA4 Event (`gaawe`) event parameters,
excluding `native-template` mappings. These require
`native_binding: {"object_key": "target::tag::name", "field": "lead_type"}`.
The owner must be an active tag for the requirement. `field` must equal the approved destination
exactly, including case and punctuation. Only native `eventSettingsTable` (`parameter` /
`parameterValue`) and `eventParameters` (`name` / `value`) rows establish event-parameter equality.
Shared event settings via native `eventSettingsVariable` / `inheritedEventSettings` references
are resolved with exact-name local overrides. Configuration tables, metadata, user properties,
and item fields cannot supply event-parameter proof. The effective value must equal `gtm_resolution`;
a `direct-dlv` reference must resolve to a represented native `v` variable whose `parameter[name]`
equals the approved source. Use a scalar value/reference, not prose, in `gtm_resolution`.

User-property and item-parameter scopes, other tag/template structures, automatic `native-template`
fields, and whole ecommerce payloads remain supported as **agent-reviewed mapping declarations**.
They do not require a fabricated scalar native binding. Inspect their exact destination namespace,
source routing, and actual native product/template structure before marking them mapped; record
that review in the mapping rationale. A supplied binding still requires an exact destination name
and active owning tag, but does not confer field-equality or source-routing proof outside the
supported scope. The rendered handoff labels this limitation even when a binding is present.
Do not fabricate duplicate parameter rows for automatic values or ecommerce passthrough.
Use the existing payload-mapping enums. The approved requirement supplies source, provenance, and
source/destination shapes; a binding cannot rewrite them. For example, the Ads carrier maps
`user_data` with `native-template`, `compatible`, the actual UPD variable reference, the documented
template field, and explicit omission behavior. Unbound fields are rejected before execution; they
must not remain pending until finalization. An explicit external/omission decision uses the existing
mapping status and supporting evidence, rather than an invented binding.

Use only the canonical statuses in `acceptance-and-handoff.md`. External site/dataLayer, CMP,
analytics/media account, credentials, catalog/feed, cloud/DNS, publication, and recette work remains
separate. Open publication dependencies do not make a saved verified setup `Blocked`.

## Compact input

`compile_configuration_request.py` expands mechanical fields into this same current contract.
Use it before `configuration_run.py init`; there is no alternate execution or weaker validation.

Supply `mode`, `route`, `targets`, approved `requirements`, `evidence`, and `objects`. Supply applicable
consent/execution topologies, page-view decisions, first-party-data routes, pipelines and dedup as
usual; empty unused sections are generated. `field_bindings` and `execution_mode` are top-level in
compact input. The default execution mode is `isolated-durable`.

Each object still supplies its action, native intended fields, rationale (`justification`), evidence,
and risk. Deltas supply exact `object_id` and `pre_change`. The compiler derives `object_key`, binds
mutation approval hashes to existing requirement authority, and fills target/requirement IDs only
when there is exactly one possible choice. Multi-target or multi-requirement ambiguity stays explicit.
It never infers approval, event meaning, consent or a product field.

Optional `reuse_candidates` holds inspected, redacted, compatible object records in the same shape,
with action `reuse`. Only candidates reachable through explicit dependencies, semantic references or
named variable references are included. Retained candidates use the same runtime verification as
other objects. Candidate input is discovery material, not an authenticated runtime baseline. Raw
opaque references still need exact resolution; missing semantics fail normal contract validation.

With a [preparation inventory](tool-adapters.md#read-only-preparation-discovery), pass
`--inventory inventory.json` and omit `intended` from explicitly selected `reuse_candidates`.
Keep each candidate's exact `resource_family`, `name`, target when ambiguous, justification,
evidence and risk. Include referenced candidate dependencies as usual. The compiler matches the
approved target identity, requires an exhausted family listing and a unique object, resolves
native IDs through the inventory, and retains all non-metadata native fields. It does not fill
mutation bodies, choose consent, declare evidence, or supply missing policy. A supplied `intended`
remains explicit. Redacted inventory fields remain presence-only evidence; they do not prove
secret equality or supply credentials. Runtime verification rejects stale compatibility targets.

```powershell
python "<skill-dir>/scripts/compile_configuration_request.py" request.json -o contract.json
python "<skill-dir>/scripts/configuration_run.py" init --contract contract.json --run-id RUN-001 --source-locator "Approved input" --output configuration-run.json
```

For inventory-assisted preparation, add `--inventory inventory.json` to the first command.

Review the compiled delta against the user's approved scope, then execute with the same adapter
runtime. Existing authorization covers routine mechanical materialization; a hash is not new consent.
