# Data contract and transformations

This file owns source-to-destination mapping decisions. Use [transformation patterns](transformations.md)
for implementation and static vectors, and [transport](../pipeline/transport-data-contract.md) when
fields cross a web/server boundary.

## Establish the source event contract

For each business action establish the exact source event, push timing/repeatability, source paths,
dataLayer version, type/shape/cardinality, null behavior and state lifetime/reset. Retain source
provenance and the owner of any required site change. Request representative payloads when they
resolve an actual shape ambiguity. A reliable business dataLayer event owns the normal Custom Event
trigger; other observed interactions establish success only when the approved source contract says so.

## Keep mapping layers distinct

| Layer | Meaning |
| --- | --- |
| Source key | Actual site-owned path or approved literal. |
| GTM variable | DLV, constant, table or transformation resolving that source. |
| Template field | Installed template's native input. |
| Destination field | Applicable product's collection contract. |

Name a DLV for its actual source and map it to the exact destination field. A destination label
establishes the terminal field, not its source path. Record approved source authority and complete
source/destination shapes before selecting the GTM method. An absent approved source leaves the
mapping blocked. [The field registry](../core/authoring.md#collection-field-model) distinguishes event,
user, item, configuration, unresolved and implementation-only fields.

## Validate before transforming

Establish that the value is available on the firing event, or document retained state and reset
behavior. Check type, object/array cardinality, empty/zero/false/null/undefined, decimal/currency
formatting, catalog/feed identity, stale ecommerce state and SPA timing where applicable.

Use a direct mapping for a compatible complete terminal shape. Otherwise declare the required
projection and its approved conversion rule. Each distinct terminal shape has its own output even
when inputs are shared. Identifier equivalence, coercion, derived totals, defaults and normalization
need approved source semantics and applicable destination support. Preserve valid zero and `false`.

Analytics mappings cover the approved field set. A documented mandatory field missing from that set
requires an approved amendment; optional improvements remain advisory under [evidence](../core/evidence.md).

## Prefer the least-complex mapping

Choose the supported target pattern before evaluating existing container reuse:

1. direct native template input or DLV for compatible approved source data;
2. named constant for a stable configuration/semantic value when it improves clarity or reuse;
3. supported settings variable for a coherent shared field set;
4. lookup/regex table for a real deterministic multi-scenario mapping;
5. one-purpose Custom JavaScript for a required conversion native mechanisms cannot express cleanly.

Reuse an existing object when its source, shapes, missing behavior, timing, consumers, consent and
environment match that pattern. Naming debt can remain if function is correct. Repeated identifiers
benefit from clear shared references; a single obvious literal can remain inline.

CMP eligibility belongs to the inspected consent contract and its native predicate under
[web consent](../consent/web.md). A source conversion serves payload mapping; it does not own consent.

## Preserve arrays and object schemas

Preserve the required output shape for zero, one and multiple items, every approved item and its
order, exact field scope/types/enums, and documented missing-item behavior. Derive totals only from
an approved rule. Malformed runtime items remain visible source-data dependencies unless an explicit
approved or mandatory product rule changes that occurrence's collection behavior.

## Write narrow Custom JavaScript

Each variable has one destination output purpose, deterministic behavior, explicit approved
conversions and documented missing/invalid output. It handles null, undefined and wrong types
without inventing values. Keep it free of network calls, DOM mutation and dataLayer pushes; make
contract failures visible. Catch only an anticipated error with a defined outcome.

Name the variable `CJS - <Vendor> - <output>` and implement it using the applicable
[projection pattern](transformations.md).

## Separate configuration completeness from runtime data quality

Configuration readiness depends on a known approved source and supported destination mapping.
A dynamic source that can be empty at runtime can still have a complete configuration contract.
Record its missing, empty, wrong-type and malformed-array cases for the site owner and recette.

Mapping output and tag firing are separate decisions: `undefined`, `{}` or `[]` can still accompany
an executing tag. Payload-related firing conditions require an explicit approved requirement or an
applicable mandatory product rule. Prefer a native condition; use narrow CJS only when native
filters cannot express that rule. Keep consent enforcement with its own owner.

## Handle harmful invalid values explicitly

Apply documented harmful-value rules through an approved invalid-value policy: correct the source,
omit the affected field where supported, or suppress/recover the affected occurrence. Resolve any
change to approved timing or coverage before saving the affected owner. Keep the rule specific to
the documented field and retain remaining source corrections and runtime acceptance cases.

For example, Google's [purchase deduplication guidance](https://support.google.com/analytics/answer/12313109)
warns that an empty GA4 `transaction_id` can collapse unrelated purchases. Reject an intentionally
empty literal and establish the policy above for a dynamic source, preserving valid zero and
repeated-order acceptance cases. Occurrence identity comes from the approved source rather than a
fabricated replacement.

## Statically verify transformations

Use non-sensitive input vectors for each transformation actually created. [Required static vectors](transformations.md#required-static-vectors)
owns the case matrix and expected checks. Record outcomes as static configuration evidence;
independent recette establishes browser/runtime behavior.

## Handle browser event IDs narrowly

An explicit media brief can authorize a supplied browser `event_id` when current documentation and
the installed template support that field. Server/pipeline requests use their own transport and
destination bindings. [Deduplication](../pipeline/browser-server-deduplication.md) owns overlapping
occurrences and [shared generation](../pipeline/browser-server-deduplication.md#configure-shared-id-generation)
owns approved non-purchase generated IDs. Apply that mechanism only within its authorized route.

## Prove transport survivability

For transported fields, bind source, web value, wire encoding, claiming Client, Event Data path/type,
server owner, destination shape and missing behavior. Prove each complete shape against its actual
protocol/Client; the standard GA `items` array and `user_data` object are specific supported shapes.
An incompatible shape needs an explicitly approved serialization and named parse owner or remains
blocked. Preserve item cardinality and product meaning under the
[transport contract](../pipeline/transport-data-contract.md).
