# Operational configuration map

## Contents

- [Purpose and priority](#purpose-and-priority)
- [Keep business and implementation decisions separate](#keep-business-and-implementation-decisions-separate)
- [Use the versioned v5 contract](#use-the-versioned-v5-contract)
- [Use one concise record per requirement](#use-one-concise-record-per-requirement)
- [Compact example](#compact-example)
- [Retain critical provenance](#retain-critical-provenance)
- [Map fields and runtime data behavior](#map-fields-and-runtime-data-behavior)
- [Map GTM object actions](#map-gtm-object-actions)
- [Prove analytics conformance](#prove-analytics-conformance)
- [Record consent and external dependencies](#record-consent-and-external-dependencies)
- [Apply canonical acceptance](#apply-canonical-acceptance)

## Purpose and priority

Build a concise internal requirement-to-object map before the first write. Use the same map for
MCP/API/UI mutation, saved-object comparison, idempotency, and the concise handoff. It is an
operational control, not a separate planning deliverable.

Resolve tradeoffs in this order:

1. data handling and consent safety;
2. exact fidelity to the approved analytics contract or explicit media business authority;
3. technical validity against current official product and installed-template documentation;
4. the smallest clean and maintainable best-practice GTM object graph;
5. compatible reuse, organization, and critical traceability;
6. completion of the saved client-side configuration.

Do not weaken a higher priority to obtain a tidier container or a more complete-looking result.
When a technically invalid analytics requirement conflicts with fidelity, stop that requirement and
request an amended approved input; never redesign it automatically.

## Keep business and implementation decisions separate

| Layer | Authority | Contents |
| --- | --- | --- |
| Approved collection decision | Analytics tracking plan or exact direct analytics requirement; for media, explicit brief plus the current official destination schema | Business action, event/conversion, outgoing fields and literals, source event/paths, success timing, repeatability, and business filters. |
| GTM implementation decision | Applicable playbook, current official documentation, installed template, source values, consent requirement, and relevant container integration | Workspace, object actions, names/folders, DLV version, mappings, triggers, consent, firing settings, sequencing, adapter fields, and readback. |

Do not use implementation infrastructure to add or change an analytics payload. Technical IDs,
folder references, consent settings, trigger references, and template mechanics are not payload
enrichment, but each must serve the current configuration or a documented product constraint.

## Use the versioned v5 contract

When the map is normalized to JSON, use `schema_version: "5.0"` and keep these top-level sections:

| Section | Contents |
| --- | --- |
| `route` | `analytics`, `media`, `consent`, or `combined`. |
| `scope` | Approved included/reference/excluded requirement IDs and source-scope facts only. |
| `requirements` | Approved analytics semantics or explicit media objective plus official destination schema. In a `combined` contract, every requirement declares `kind` as `analytics`, `media`, or `consent`. |
| `implementation` | Workspace, object actions, names, IDs, mappings, templates, triggers, consent, routing, readback, and status. |
| `evidence` | Official-source manifest and container/source evidence needed for the decisions. |
| `external_dependencies` | Work explicitly outside the saved GTM graph. |

Every requirement needs an `authority` with a permitted provenance grade and a precise non-sensitive
source locator. Every outgoing analytics parameter, user property, and item field needs its own
`provenance` locator. Analytics collection fields may use `approved-input`; `official-current` may
validate them but never authorize an addition. Media destination schema fields may use
`official-current`, while media business objective, destination identity, and source authorization
remain `approved-input`. A combined contract applies those rules per declared requirement `kind`;
it cannot use the broader media rule for an analytics field.

Keep `workspace`, `tag_type`, `template`, `gtm_variable`, object IDs, fingerprints, trigger and
folder references, consent mechanics, and adapter fields under `implementation`. Do not mark them as
approved collection semantics and do not make the conformance comparator skip arbitrary fields.

Run `scripts/validate_configuration_contract.py` for a v5 JSON map. Use `--allow-legacy` only to
read a previously produced v4 contract or an unversioned comparator input; never use compatibility
mode to authorize new mutation. Every newly created map must use v5 and pass the strict validator.

## Use one concise record per requirement

Create one record per independently configurable business action and destination. Keep separate
records when destination, business meaning, consent route, source timing, environment, ownership, or
future change path differs.

Capture only what mutation and verification need:

- stable requirement/source reference and `included`, `reference-only`, `excluded`, or `ambiguous`
  scope when the supplied artifact contains multiple relevant parts;
- analytics tracking-plan decision or media objective and exact success moment;
- source event and required fields with type/shape, timing, lifetime, and missing-data rule;
- destination product/ID, official event or conversion, configured outgoing field set, and intended
  use;
- installed tag/template identity, version, fields, defaults, and relevant permissions;
- GTM field resolution, normal trigger, consent mechanism, firing option, and folder;
- object actions and dependencies, including explicit delta actions;
- discrepancy, blocker, external dependency, and final operational status.

Do not force a large worksheet-style record for a direct one-field mapping. Add detail in proportion
to transformation, consent, shared-consumer, template, or mutation risk.

## Compact example

Use this proportional shape; extend it only for real risk:

```json
{
  "schema_version": "5.0",
  "route": "analytics",
  "scope": {"included": ["REQ-12"], "reference_only": [], "excluded": []},
  "requirements": [{
    "id": "REQ-12",
    "authority": {"grade": "approved-input", "locator": "Tracking Plan / Events / row 12"},
    "event_name": "generate_lead",
    "source_event": "form_success",
    "parameters": {
      "method": {
        "source": "event.method",
        "provenance": {"grade": "approved-input", "locator": "Tracking Plan / Events / row 12 / method"}
      }
    }
  }],
  "implementation": {
    "workspace": {
      "account_id": "account-stable-id",
      "container_id": "container-stable-id",
      "id": "workspace-stable-id",
      "container_type": "web"
    },
    "objects": [{
      "action": "create",
      "object_type": "tag",
      "name": "GA4 - Event - generate_lead",
      "justification": "Implements REQ-12 exactly",
      "evidence": ["approved-input", "official-current", "container-confirmed"]
    }]
  },
  "evidence": [
    {
      "grade": "official-current",
      "locator": "GA4 generate_lead reference",
      "url": "https://developers.google.com/analytics/devguides/collection/ga4/reference/events",
      "title": "GA4 recommended events",
      "access_date": "YYYY-MM-DD"
    },
    {"grade": "container-confirmed", "locator": "account/container/workspace stable IDs"}
  ],
  "external_dependencies": []
}
```

`lead_type` is absent because no approved locator authorizes it. A convenient implementation idea
cannot be inserted into `requirements` and cannot pass merely by being labeled infrastructure.

## Retain critical provenance

Keep source attribution for facts that determine a write:

| Provenance | Permitted decision |
| --- | --- |
| `approved-input` | Analytics semantics, media objective, destination identity, client policy, and explicit analyst decisions. Include a precise source locator. |
| `official-current` | Destination schema, GTM behavior, template expectations, and supported consent capability. |
| `container-confirmed` | Installed objects/templates, stable IDs, consumers, conflicts, fingerprints, and saved fields. It never proves best practice. |
| `contract-sample` | dataLayer/source timing, type, shape, cardinality, null behavior, and representative transformation input. |

An assumption may explain non-critical context but may not supply a destination ID, required source,
field type/shape, consent predicate, template capability, or mutation target. Ask for or discover the
critical fact instead. Preserve official URLs, titles, and access dates for schema, discrepancy,
template, and consent decisions; do not produce a citation ledger for routine self-evident object
names.

## Map fields and runtime data behavior

For every outgoing field, preserve these distinct layers:

| Layer | Required decision |
| --- | --- |
| Source | Exact dataLayer/configuration path, event timing, type/shape, and representative value when needed. |
| GTM resolution | Direct value, DLV, constant, settings variable, LUT/RLT, or narrow transformation with missing-data behavior. |
| Template | Exact installed-template field and stored type. |
| Destination | Official parameter, requirement status, type, format, enum, scope, and cardinality. |
| Delivery surface | Browser Pixel/tag field or server/CAPI-only field; never copy the latter into a browser tag without current browser support. |

Use `mapped`, `intentionally omitted`, `external`, or `blocked` for exceptional field states. Preserve
valid zero and `false`. Never turn an absent required value into an empty string, placeholder,
guessed ID, invented literal, or silent item omission.

Separate design-time completeness from runtime data quality. A required field with no approved
source, no compatible transformation, or no supported template field blocks configuration. When an
approved source mapping exists but can resolve missing or empty at runtime, configure the tag from
the approved business event and record the source obligation for recette. Do not add a Custom
JavaScript eligibility variable, a duplicate validity parser, or a firing exception merely to
suppress a potentially incomplete payload.

Add a payload-related firing condition only when the explicit brief or current official browser
contract requires one. Prefer a direct native source condition; use one narrow CJS condition only
when the rule cannot be represented natively. Consent blocks are separate policy objects and are
not payload validation.

For arrays, define the empty, one-item, multi-item, and invalid-item transformation result. Preserve
every mapped item and do not filter item zero or silently invent a catalog identifier. Runtime
missing or malformed values remain a site/dataLayer dependency unless the documented browser
contract explicitly requires a firing rule.

## Map GTM object actions

Create the complete in-scope object graph before mutation. For each object record:

- `create`, `update`, `rename`, `pause`, `unpause`, `reuse`, `untouched`, or explicitly
  authorized `remove`;
- canonical GTM resource family in `object_type`, intended name/folder, stable existing ID/path,
  and fingerprint when applicable;
- requirement or documented constraint that justifies it;
- exact intended fields, references, consent route, and dependencies;
- compatible consumers and relevant environment/hostname scope;
- exact non-empty pre-change representation for every update, rename, pause, unpause, or removal;
- expected saved-object comparison.

Represent each semantic GTM object once. Reject duplicate actions and contradictory combinations
such as creating and updating the same type/name or renaming one object onto another claimed
identity. Use stable object IDs as an additional identity when available.

Use only these canonical `object_type` values: `tag`, `trigger`, `variable`, `built-in variable`,
`folder`, `template`, `zone`, `environment`, `destination`, `google tag configuration`,
`container setting`, or `workspace`. Record product, tag, trigger, variable, or template subtype in
the intended fields rather than inventing another resource-family label.

Support every mutation with `approved-input` or `official-current` evidence, as applicable.
Existing-object actions also require `container-confirmed` evidence. A representative
`contract-sample` can support source shape but cannot authorize an object action by itself.

Use `rename`, `pause`, or `unpause` only for an approved delta and record the exact pre-change state,
related consumers, and behavioral effect. Use `remove` only after explicit destructive authorization
and confirmed ownership. A repeated run against the final saved state must resolve every completed
object to `reuse` or `untouched`.

Select the target architecture before reuse. A matching name or current value is insufficient.
Require compatible output, source, type/shape, timing, consent, consumers, template/version,
environment, and future change path. Keep harmless naming debt when reuse is otherwise correct; do
not inherit functional debt or add a parallel duplicate.

## Prove analytics conformance

Before the first analytics write, compare the approved contract with the intended event tags. After
mutation, compare it with authoritative workspace readback. Require:

- identical included requirement IDs;
- identical destination and source events;
- identical business timing and filters;
- exact outgoing parameter/property/item-field set equality;
- exact approved source or literal for every field;
- zero unauthorized additions, removals, substitutions, or hidden-scope inclusions.

Use `scripts/validate_configuration_contract.py` to enforce the v4 authority boundary and
`scripts/validate_contract_conformance.py` to compare approved, intended, or saved analytics
representations. Keep implementation metadata outside `scope` and `requirements`. Never whitelist
an arbitrary implementation field out of equality. A non-zero schema or semantic difference blocks
the affected write or `Configured` result until corrected or supported by an explicit amended
analytics decision.

## Record consent and external dependencies

For each browser product, record the normal trigger and either:

- strict/basic CMP block predicate, event scope, unknown/denied behavior, and initial/later grant
  opportunity; or
- explicitly approved advanced/native feature, defaults/updates, denied-state behavior, template
  fields, and product-specific official evidence.

Keep independent CMP grants as OR-denial across the smallest reusable block set. Reconcile consent
with every consumer of a shared execution unit.

Record but do not silently perform external work, including site/dataLayer changes, CMP setup, GA4
custom definitions or key events, Google tag/data-stream settings, advertising conversion actions,
catalog/feed work, platform account settings, publication, and server-side/deduplication work.

## Apply canonical acceptance

Use the status definitions and completion invariants only from
`../03-judgement/acceptance-and-handoff.md`. This map records the selected status and its evidence;
it does not restate or redefine `Configured`, `Partial`, `Blocked`, or `Deferred`.

Before handoff, render the compact recette-ready manifest defined there:

`requirement → source event → tag → trigger → variables → destination fields → consent route → status → external dependencies`.
