# Operational configuration contract

## Contents

- [Purpose and priority](#purpose-and-priority)
- [Keep business and implementation authority separate](#keep-business-and-implementation-authority-separate)
- [Use configuration-contract 6.0](#use-configuration-contract-60)
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

## Use configuration-contract 6.0

Every new mutation map uses `"schema_version": "6.0"` and
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
| `pipelines` | Sender/receiver graph, request/Client, page-view, event/field flow, and cutover |
| `consent_topologies` | Per-destination web, transport, server mechanism, signal, and event coverage |
| `execution_topologies` | One bound firing/blocking/consent/lifecycle decision per executing web tag |
| `page_view_decisions` | One effective owner and `send_page_view` decision per web destination |
| `first_party_data_routes` | Approved user-data/User-ID feature, source, timing, hashing, consent, and consumers |
| `inventory_dispositions` | Ordered one-row-per-tag refonte disposition linked to exact object actions |
| `dedup_contracts` | Only overlapping delivery, with one occurrence identity and exact product fields |
| `evidence` | Approved, official-current, container-confirmed, and sample provenance |
| `external_dependencies` | Work outside the saved GTM graphs |

Versioned v5 web contracts remain on their preserved compatibility path. Explicitly versioned v4
is read-compatible only with `--allow-legacy`. Unversioned inputs never authorize mutation.

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
also requires `new_name`; `remove` and `replace` require `destructive_authorization: true`;
`replace` requires a reason; and every template mutation records its permission delta. These are
validation rules, not optional documentation conventions.

Web resource families are the complete v8 surface: tag, trigger, variable, built-in variable,
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
endpoint reference, exactly one intended claiming Client and its criteria, and one page-view owner
with explicit effective `send_page_view`.

Each event-flow row binds an approved requirement/source event to the transported event and every
receiver tag. Each field-flow row resolves:

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

For web tags, preserve the strict/basic default: baseline tags use a verified CMP lifecycle event
plus vendor block; business tags use the approved business trigger plus vendor block. Default every
product to strict/basic CMP blocking unless an explicitly approved and documented advanced/native
route applies. Do not stack an equivalent Additional Consent Check.

For each pipeline destination, record `consent_mode`, `transport_behavior`, exact web mechanism,
exact server mechanism, signal source, denied/unknown behavior, and event coverage. Server mechanism
is exactly one of incoming Google-native consent, server-template-native consent, supported server
Additional Consent Check, server blocking trigger, or none. A destination blocked before transport
must not receive an equivalent server gate unless intentional double gating is explicitly justified.

Record dedup only when the same destination occurrence can arrive twice. A `dual-shared-id` route
binds browser and transporter to one occurrence source, transports it unchanged, and maps exact
current browser/server field names and companion fields. Purchase uses approved transaction/order
identity when the product supports it; do not substitute the GTM fallback for a dual purchase.

For another dual event with no stable site ID, the guarded GTM event-scoped CJS fallback is allowed
only when both web tags resolve the same variable on the same GTM event, the server consumes the
transported value without regeneration, compatibility is recorded as an internal GTM-model
dependency, and recette must prove a defined stable value. This is not a payload eligibility gate.

## Validate and materialize

Run `scripts/validate_configuration_contract.py` before mutation. For analytics, also use
`validate_contract_conformance.py` to prove identical requirement IDs, events, timing/filters,
outgoing field set, and approved sources/literals.

The validated contract deterministically materializes active `configuration-run@3.0` sections.
Do not hand-edit requirements, pipelines, immutable operation intention/dependencies, payload maps,
consent topologies, dedup contracts, or publication dependencies; section fingerprints detect
drift. Adapters may populate baselines, journals, readbacks, comparisons, and results only.

Use only the canonical statuses in `acceptance-and-handoff.md`. External site/dataLayer, CMP,
analytics/media account, credentials, catalog/feed, cloud/DNS, publication, and recette work remains
separate. Open publication dependencies do not make a saved verified setup `Blocked`.
