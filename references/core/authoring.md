# Operational configuration contract

## Purpose and priority

Before mutation, represent the approved change as one requirement-to-object contract. Use the
[authority contract](authority.md) for scope, priorities and approval and the
[evidence policy](evidence.md) for current technical support. This file owns declaration meaning
and preparation; schemas own structural keys and types.

## Use configuration-contract 10.0

Use `"schema_version": "10.0"` and
[the contract schema](../../schemas/configuration-contract.schema.json). Preparation and execution
consume this current model through the same domain validators.

| Section | Contents |
| --- | --- |
| `mode` | `web`, `server`, or `pipeline` |
| `route` | `analytics`, `media`, `consent`, `organization`, or `combined` |
| `scope` | Disjoint included, reference-only, and excluded requirement IDs |
| `requirements` | Approved semantics/business intent, source, destination, and field authority |
| `targets` | Explicitly authorized stable web/server workspaces with independent target IDs |
| `implementation.execution_mode` | `isolated-durable`, or `refonte-durable` |
| `implementation.objects` | Exact target-scoped GTM actions, intended state, and dependencies |
| `implementation.field_bindings` | Resolution for every outgoing field in its approved namespace; readiness blocks dependent operations while fields are pending or blocked |
| `pipelines` | Sender/receiver graph, request/Client, page-view, event/field flow, and cutover |
| `consent_topologies` | Per-destination web, transport, server mechanism, signal, and event coverage |
| `execution_topologies` | One bound firing/blocking/consent/lifecycle decision per executing web tag |
| `page_view_decisions` | One effective owner per web destination and occurrence role, with an applicable `send_page_view` decision |
| `first_party_data_routes` | Approved user-data/User-ID feature, source, timing, hashing, consent, and consumers; native Ads event overrides also bind inspected parameter/control paths as described in the [Ads procedure](../vendors/google-ads/web.md#configure-enhanced-conversions-only-explicitly) |
| `inventory_dispositions` | Ordered one-row-per-tag refonte disposition linked to exact object actions |
| `dedup_contracts` | Only overlapping delivery, with one occurrence identity and exact product fields |
| `evidence` | Approved, official-current, container-confirmed, and sample provenance |
| `external_dependencies` | Structured work outside the saved GTM graphs: `id`, affected `requirement_ids`, `owner`, `action`, and `status` (`open`, `resolved`, or `accepted`) |

## Map requirements and targets

Every requirement has a stable ID, approved source locator and field provenance. Split requirements
when destination, consent route, source timing, environment, owner or change path is independently
configurable. Record exact source paths/literals, source/destination shapes, missing behavior,
business timing and filters using [data mapping](../data/mapping.md).

Each target declares `target_id`, authoritative container type, account/container/workspace IDs and
approved-input authority. Pipeline mode requires authorized sender and receiver targets. Source
review and any additional approval follow [target authority](authority.md#target-authority).

## Collection field model

The shared schema registry owns destination namespaces. Use exact destination names as map keys:

| Requirement collection | Meaning | Binding scope |
| --- | --- | --- |
| `parameters` | Event parameters | `event-parameter` |
| `user_properties` | User properties | `user-property` |
| `item_parameters` | Item fields | `item-parameter` |
| `configuration_fields` | Product configuration settings, including GA4 `user_id` | `configuration` |
| `unresolved_fields` | Approved fields whose destination surface is unspecified | `unresolved`; blocked until approved input resolves the destination |
| `implementation_fields` | Implementation context retained with provenance | No outgoing mapping |

Source names remain in the field record even when the destination uses a different name.
Use `source_shape` and `destination_shape` from this closed vocabulary:
`scalar:string`, `scalar:number`, `scalar:integer`, `scalar:boolean`, `array`, `object`.
Nullable behavior remains explicit; it does not change the base shape.
Pipeline wire cardinality uses its separate `scalar`/`array`/`object` model.

## Organization route

`route: organization` covers folder creation, rename and inspected reuse. It carries target authority,
container evidence and complete native snapshots through the normal execution/readback engine.
Collection changes use their corresponding route and technical evidence.

## Map target-scoped object actions

Represent each semantic object once as `<target-id>::<resource-family>::<semantic-name>`. Record its
action, existing stable ID where applicable, full intended state, dependencies, requirements,
justification, evidence and risk. Resource subtypes remain in the native fields.

| Action information | Declaration |
| --- | --- |
| Delta | `object_id` and non-empty complete `pre_change`; native `type` for typed resources. |
| Executing, reuse or untouched object | Non-empty `intended` compatibility target, including applicable native `type`. |
| Rename | `new_name` in addition to delta evidence. |
| Replace | Same-identity governed replacement plus reason and authority. |
| Template mutation | Reviewed permission delta. |
| Any mutation | Approval record bound to source locator, action, object key, requirements and exact mutation payload hash. |

Use the schema's action/resource vocabulary. A complete snapshot supports comparison even when the
adapter accepts patches. Google settings-variable changes include consumers of both old and new
types. Compatible Client reuse records native type/priority and reviewed claim semantics in
`assertions.client_claim`; see [server assertions](../server/native-assertions.md).

Reconcile changes to the approved source before rebuilding approval records. The record provides
traceability and drift detection under [evidence limits](authority.md#evidence-and-validation-limits).
The graph validator checks identity uniqueness, dependency closure and target capability. Final
convergence proves completed intentions need no further mutations.

## Map pipeline flow

Declare sender target(s), receiving target, request class, transport owner, endpoint and intended
claiming Client with criteria. Bind initial-page-load transport and effective `send_page_view`;
`page_view_decisions` distinguishes occurrence roles.

Every emitting tag either owns the saved endpoint directly or inherits it through the same bound
destination identity. Link actual emitters in the consent topology. Event flows bind approved
requirement/source events to transported events and receiver tags. Field-flow identities are
`(requirement_id, field_scope, destination_field)` and cover each mapped field exactly once:

`approved source → web variable → wire field/shape → Client proof → Event Data path/shape →
server owner → template/destination field/shape → missing behavior → runtime verification note`

Use [transport declarations](../pipeline/transport-data-contract.md) for protocol and shape proof,
and [pipeline ordering](../pipeline/architecture-and-workflow.md#build-receiver-first) for receiver
and cutover dependencies. The contract records the mechanism; feature guides own its selection.

## Map consent and deduplication

Populate consent/execution topology fields from the selected [web consent](../consent/web.md),
[server consent](../consent/server.md) and applicable lifecycle/product guides. Record the exact
mechanism, signal authority, unknown/denied behavior, transport behavior, event coverage and native
owner bindings. Built-in template behavior remains distinct from custom enforcement.

An approved ungated web policy is represented by `client-policy-ungated` in consent and execution,
`signal_authority: none`, `unknown_state_behavior: explicit-policy`, `transport_behavior:
always-transported`, server mechanism `none`, and empty server/transporter bindings. Its declaration is:

```json
{"mechanism":"none","client_policy":{"grade":"approved-input","locator":"exact client instruction","scope":"approved site, audience and destination scope"}}
```

The native tag has no custom gate or pre-CMP policy under this web-only route. The policy is an
explicit client decision, with its legal interpretation outside configuration scope.

For overlapping delivery, use [deduplication](../pipeline/browser-server-deduplication.md) to declare
one occurrence source and exact browser/transporter/server bindings. Approved shared generation
uses its documented `generation` structure and installed-template evidence. Purchase and other-event
identity choices stay with that feature owner.

## Validate and materialize

Run `scripts/configure_gtm.py validate-contract` before mutation. For analytics, run
`scripts/configure_gtm.py conformance` to check requirement IDs, events, timing/filters, outgoing
fields and approved source/literal equality. Review current source evidence as well as validator output.

The contract materializes its active sections into run 8.0. Resolve implementation decisions in the
contract; [execution](execution.md#materialize-deterministically) owns durable state and fingerprints.
Each `implementation.field_bindings` row records identity, status, shape compatibility, method,
GTM resolution, template field and missing behavior. The approved requirement supplies source,
provenance and shapes; the binding records implementation of those facts.

### Native mapping proof

Deterministic proof covers explicit scalar GA4 Event (`gaawe`) event parameters and Google tag
(`googtag`, `gaawc`) configuration settings, excluding `native-template` mappings. Supply:

```json
{"object_key":"target::tag::name","field":"lead_type"}
```

as `native_binding`. The owner is an active tag for the requirement and supported namespace; `field`
matches the approved destination exactly, including case and punctuation. Provided bindings undergo
ownership validation at every status before mapped-value proof.

Configuration bindings resolve local/shared configuration tables. Event bindings resolve native
`eventSettingsTable` LIST rows with `parameter`/`parameterValue` MAP cells, including shared
`eventSettingsVariable`/`inheritedEventSettings` references and exact-name local overrides. The
effective native value equals `gtm_resolution`. A `direct-dlv` binding resolves to a represented
native `v` variable with version 2, exact approved `parameter[name]` and untransformed value.
Use an actual scalar/reference as `gtm_resolution`.

### Inspected mapping declarations

User/item scopes, other templates, automatic `native-template` fields and whole ecommerce payloads
use **agent-reviewed mapping declarations**. Inspect exact destination namespace, source routing
and native product/template structure and record the rationale. A supplied binding establishes its
owner/name, while field-equality/source proof remains limited to the supported native scope above.
The rendered handoff preserves that distinction.

Automatic values and ecommerce passthrough use their inspected native mechanism. For example,
Ads `user_data` uses `native-template`, `compatible`, the UPD variable reference, documented template
field and explicit omission behavior. External/intentional omission decisions use existing mapping
statuses with evidence. Pending/blocked fields hold their owners through
[dependency readiness](execution.md#contain-failures-by-dependency); other ready requirements can proceed.

## Compact input

Use `scripts/configure_gtm.py prepare` before `run init`. Supply `mode`, `route`, targets, approved
requirements, evidence and objects, plus the applicable pipeline, consent/execution, page-view,
first-party-data, inventory, deduplication and field-binding declarations.

Supply each object's scope justification. The compiler derives object keys, binds approval hashes to existing
requirement authority and fills target/requirement IDs only when unambiguous. It resolves native
references into dependency keys and materializes explicit `reuse_candidates`. With `--inventory`,
`reuse_keys` select exact inspected inventory definitions. Supplied intentions and semantic decisions
remain explicit; redacted values carry presence evidence rather than credentials.

```powershell
python "<skill-dir>/scripts/configure_gtm.py" prepare request.json -o contract.json
python "<skill-dir>/scripts/configure_gtm.py" run init --contract contract.json --run-id RUN-001 --source-locator "Approved input" --output configuration-run.json
```

Add `--inventory inventory.json` for inventory-assisted preparation. Review the compiled delta
against the approved scope and execute through the same runtime.

Mechanical inference covers a sole native `{{_event}} equals X` matching the approved source event,
and direct scalar bindings through one explicit untransformed V2 DLV with compatible shapes and
explicit missing behavior. Ambiguous source, consent, lifecycle, destination and cross-target
choices require declarations. A new settings variable is assessed by its action and consumer impact.
