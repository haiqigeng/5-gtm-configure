# Operational configuration map

## Contents

- [Purpose and priority](#purpose-and-priority)
- [Keep business and implementation decisions separate](#keep-business-and-implementation-decisions-separate)
- [Use the versioned v5 contract](#use-the-versioned-v5-contract)
- [Use one concise record per requirement](#use-one-concise-record-per-requirement)
- [Retain critical provenance](#retain-critical-provenance)
- [Map fields and runtime data behavior](#map-fields-and-runtime-data-behavior)
- [Map GTM object actions](#map-gtm-object-actions)
- [Prove analytics conformance](#prove-analytics-conformance)
- [Record consent and external dependencies](#record-consent-and-external-dependencies)
- [Apply canonical acceptance](#apply-canonical-acceptance)

## Purpose and priority

Before the first write, create one concise requirement-to-object map. Use it for mutation, saved
comparison, idempotency, and the configuration-run handoff; it is an operational control, not a
planning deliverable.

Resolve conflicts in this order: data/consent safety, approved semantic fidelity, current technical
validity, smallest maintainable architecture, compatible reuse/organization, then saved completion.
Never weaken a higher priority for a tidier or more complete-looking graph.

## Keep business and implementation decisions separate

| Layer | Authority | Contents |
| --- | --- | --- |
| Approved collection decision | Tracking plan/direct analytics decision, or media brief plus official destination schema | Meaning, event/conversion, outgoing fields/literals, source event/paths, success timing, repeatability, and business filters |
| GTM implementation decision | Applicable playbook, current documentation, installed template, source values, consent, and relevant container evidence | Workspace, object actions, DLV/version, variables, triggers, consent, firing settings, folders, adapter fields, and readback |

Technical infrastructure must serve the approved requirement. It cannot add an analytics payload
field merely by being labeled implementation.

## Use the versioned v5 contract

New mutation maps use `"schema_version": "5.0"` with:

| Section | Contents |
| --- | --- |
| `route` | `analytics`, `media`, `consent`, or `combined` |
| `scope` | Included/reference/excluded stable requirement IDs |
| `requirements` | Approved analytics semantics or media objective plus official destination schema |
| `implementation` | Stable workspace and exact GTM object actions/fields/dependencies |
| `evidence` | Approved, official, container, and sample provenance used by decisions |
| `external_dependencies` | Work outside the saved GTM graph |

Every requirement needs approved authority and a precise locator. Every analytics parameter, user
property, and item field needs approved provenance; official documentation validates but does not
authorize an addition. Media schema fields may use current official provenance, while objective,
identity, and source authorization remain approved input.

Run `scripts/validate_configuration_contract.py` strictly for every new map. `--allow-legacy`
accepts only an explicitly versioned historical v4 contract for inspection/migration. Unversioned
comparison inputs are isolated inside `validate_contract_conformance.py`; they cannot enter the
mutation validator or authorize work.

## Use one concise record per requirement

Separate records when destination, meaning, consent route, source timing, environment, ownership,
or change path differs. Preserve a stable source ID; otherwise create one from the exact source
locator and business action, then keep it unchanged for the run.

Capture only approved semantics, source/type/shape, destination/schema, template/version, GTM field
resolution, trigger/consent/firing settings, object actions/dependencies, evidence, blockers, and
status. Add detail in proportion to real transformation, consent, shared-consumer, template, or
mutation risk.

## Retain critical provenance

| Grade | Permitted use |
| --- | --- |
| `approved-input` | Analytics semantics, media objective/identity, policy, and explicit analyst authority |
| `official-current` | Destination schema, product/GTM behavior, template expectation, and consent support |
| `container-confirmed` | Installed objects/templates, stable IDs, consumers, conflicts, fingerprints, and readback |
| `contract-sample` | Representative source timing/type/shape and transformation input; never sole mutation authority |

An assumption cannot supply a destination ID, source field, consent predicate, template capability,
or mutation target. Store exact official URL/title/access date only for material decisions.

## Map fields and runtime data behavior

For every outgoing field, keep source, GTM resolution, installed-template field, official
destination field, and browser-versus-server delivery surface distinct. Use `mapped`,
`intentionally omitted`, `external`, or `blocked`; preserve valid zero and `false`.

A missing design-time source, incompatible type/shape, or unsupported required template field
blocks. A valid source that may be missing at runtime remains directly mapped and becomes a
site/dataLayer recette dependency. Do not invent an empty string, fallback ID, payload-eligibility
CJS, validity trigger, or firing exception. Add a payload condition only when the explicit brief or
current official browser contract requires it.

For arrays, define empty/one/many/invalid-item results, preserve order and every mapped item, and
never silently substitute a catalog identifier.

## Map GTM object actions

Represent each semantic object once with canonical resource family, stable ID when existing,
intended fields/references, dependencies, requirement IDs, evidence, and expected comparison.
Express every dependency as the exact canonical object key `<resource family>::<name>`; the run
controller resolves those stable keys to operation IDs and rejects missing or cyclic edges.
Every row names the requirement or documented constraint that justifies the object.

Use `create`, `update`, `replace`, `rename`, `pause`, `unpause`, `reuse`, `untouched`, or explicitly
authorized `remove`. Every delta needs exact non-empty `pre_change`. `replace` is one governed action
for a same-identity object that cannot reach the approved target by supported update; it also needs
stable `object_id`, exact `intended`, `replacement_reason`, destructive authority, consumer tracing,
and recovery. Never express it as remove plus create.

Use canonical types: `tag`, `trigger`, `variable`, `built-in variable`, `folder`, `template`, `zone`,
`environment`, `destination`, `google tag configuration`, `container setting`, or `workspace`.
Object subtype belongs in intended fields. Mutations require approved or official evidence;
existing-object actions also require container confirmation. High-impact actions retain explicit
authority.

Reject duplicate actions, ID/name collisions, rename-target collisions, and missing dependencies.
Choose architecture before reuse: require compatible output, source, timing, consent, consumers,
template/version, environment, and change path. A repeated run against the final saved state must
resolve every completed object to `reuse` or `untouched`.

## Prove analytics conformance

Before analytics mutation and after saved readback, require identical included requirement IDs,
destination/source events, timing/filters, exact outgoing parameter/property/item-field set equality,
and exact approved source or literal. Zero unauthorized additions, removals, substitutions, or
hidden-scope inclusions are allowed.

Use `validate_configuration_contract.py` to enforce the v5 authority boundary and
`validate_contract_conformance.py` for semantic equality. Keep implementation metadata outside
requirements; never whitelist arbitrary fields out of comparison. A schema or semantic difference
blocks the affected write or `Configured` result.

## Record consent and external dependencies

For each browser product, record normal trigger plus strict/basic block or grant-event mechanism,
including unknown/denied behavior and later grant. A grant-event normal trigger must not also carry
a redundant block. Advanced/native behavior needs explicit request and exact current evidence.

Record site/dataLayer, CMP, GA4-property, media-platform, catalog/feed, publication, and server-side
work separately. A GTM save never proves an external task completed.

## Apply canonical acceptance

Use only the status definitions in `../03-judgement/acceptance-and-handoff.md`. No planning/
specification status substitutes for saved configuration. Initialize and validate the versioned
configuration-run artifact, persist checkpoints, then render:

`requirement → source event → object actions → payload map → trigger/consent → saved readback → status → external dependency → recette cues`.
