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
| `implementation.execution_mode` | `isolated-lightweight`, `isolated-durable`, or `refonte-durable` |
| `implementation.objects` | Exact target-scoped GTM actions, intended state, and dependencies |
| `implementation.field_bindings` | Explicit resolution of approved fields into mapped GTM/template fields; required for a mapped first-party route |
| `pipelines` | Sender/receiver graph, request/Client, page-view, event/field flow, and cutover |
| `consent_topologies` | Per-destination web, transport, server mechanism, signal, and event coverage |
| `execution_topologies` | One bound firing/blocking/consent/lifecycle decision per executing web tag |
| `page_view_decisions` | One effective owner per web destination and occurrence role, with an applicable `send_page_view` decision |
| `first_party_data_routes` | Approved user-data/User-ID feature, source, timing, hashing, consent, and consumers |
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

For web tags, preserve the strict/basic default: baseline/page-load tags use a verified CMP
lifecycle event plus vendor block; business and interaction tags keep the approved business trigger
plus vendor block. Default every
product to strict/basic CMP blocking unless an explicitly approved and documented advanced/native
route applies. A template's built-in consent checks are intrinsic product behavior, not configurable
Additional Consent Checks. Under strict/basic, remove duplicate consent conditions from the normal
firing trigger, keep one vendor-denied blocking trigger as the configurable gate, and leave
Additional Consent Checks empty.

For each pipeline destination, record `consent_mode`, `transport_behavior`, exact web mechanism,
exact server mechanism, signal source, denied/unknown behavior, and event coverage. Server mechanism
is exactly one of incoming Google-native consent, server-template-native consent, supported server
Additional Consent Check, server blocking trigger, or none. A destination blocked before transport
must not receive an equivalent server gate unless intentional double gating is explicitly justified.

Record dedup only when the same destination occurrence can arrive twice. A `dual-shared-id` route
binds browser and transporter to one occurrence source, transports it unchanged, and maps exact
current browser/server field names and companion fields. Purchase uses approved transaction/order
identity when the product supports it; do not synthesize an occurrence identity from GTM internals.

Every other dual event also needs an approved stable occurrence ID. If none exists, select one
delivery channel or keep the overlap blocked; do not synthesize identity from GTM internals.

## Validate and materialize

Run `scripts/validate_configuration_contract.py` before mutation. For analytics, also use
`validate_contract_conformance.py` to prove identical requirement IDs, events, timing/filters,
outgoing field set, and approved sources/literals.

The validated contract deterministically materializes active `configuration-run@4.0` sections.
Do not hand-edit requirements, pipelines, immutable operation intention/dependencies, payload maps,
consent topologies, dedup contracts, or publication dependencies; section fingerprints detect
drift. Adapters may populate baselines, journals, readbacks, comparisons, and results only.

Resolve field implementation in the contract, not by editing the materialized run. Each
`implementation.field_bindings` row has exactly `requirement_id`, `field_scope`,
`destination_field`, `status`,
`shape_compatibility`, `mapping_method`, `gtm_resolution`, `template_field`, and `missing_behavior`.
Use the existing payload-mapping enums. The approved requirement supplies source, provenance, and
source/destination shapes; a binding cannot rewrite them. For example, the Ads carrier maps
`user_data` with `native-template`, `compatible`, the actual UPD variable reference, the documented
template field, and explicit omission behavior. Unbound fields stay `pending`, not implicitly mapped.

Use only the canonical statuses in `acceptance-and-handoff.md`. External site/dataLayer, CMP,
analytics/media account, credentials, catalog/feed, cloud/DNS, publication, and recette work remains
separate. Open publication dependencies do not make a saved verified setup `Blocked`.
