# Data contract and transformations

## Contents

- [Establish the source event contract](#establish-the-source-event-contract)
- [Keep mapping layers distinct](#keep-mapping-layers-distinct)
- [Validate before transforming](#validate-before-transforming)
- [Prefer the least-complex mapping](#prefer-the-least-complex-mapping)
- [Preserve arrays and object schemas](#preserve-arrays-and-object-schemas)
- [Write narrow Custom JavaScript](#write-narrow-custom-javascript)
- [Separate configuration completeness from runtime data quality](#separate-configuration-completeness-from-runtime-data-quality)
- [Statically verify transformations](#statically-verify-transformations)
- [Handle browser event IDs narrowly](#handle-browser-event-ids-narrowly)

## Establish the source event contract

For every business action, record:

- exact dataLayer `event` name;
- moment the push occurs and whether it can repeat;
- source object paths and dataLayer variable version;
- expected type, format, cardinality, and null behavior;
- sample payloads for relevant edge cases;
- whether values are event-scoped or can persist from a previous push;
- evidence grade for the event, timing, shape, and representative payload;
- source owner and required site change when a field is absent.

Use the Custom Event as the normal trigger. Do not infer a success event from a click, URL, DOM message, or form submission when a reliable business dataLayer event exists.

## Keep mapping layers distinct

Create a traceable map:

| Layer | Example role |
| --- | --- |
| dataLayer key | Actual site-owned source path. |
| GTM variable | DLV, constant, table, or transformation that resolves a value. |
| Template field | Field visible in the installed tag template. |
| Destination parameter | Official network/platform contract. |

Do not rename the source key to look official. Name the DLV after the actual key and map it to the correct official destination field.

Before mutation, record the approved source authority and complete source/destination shapes beside
the selected GTM method. A vendor brief or template field such as `PRODUCT_LIST`, `content_ids`, or
`contents` identifies a terminal field, not an identically named dataLayer source. When no approved
source path or literal exists, keep the row `blocked`; do not create a speculative DLV.

## Validate before transforming

Require the approved source contract to place the value on the same GTM event that fires the tag, or to document its retained state and reset behavior. Check:

- string versus number versus Boolean;
- object versus array;
- empty string, zero, false, null, and undefined;
- decimal and currency formatting;
- item identifiers and explicit catalog/feed alignment;
- duplicate or stale ecommerce state;
- SPA navigation timing.

If a critical required value is unavailable or incompatible, block the affected tag design and specify the required dataLayer change. Do not develop the site within this skill.

Use a direct DLV/template field only when the complete terminal shape is compatible. For example,
a scalar currency string may map directly, while an analytics item-object array must be projected
before a destination can receive an identifier array or vendor-specific object array. Record each
different terminal shape separately even when the projections share one input.

Do not assume that an analytics `item_id` is the identifier used by a media catalog or feed. Do not
coerce a numeric string, derive a total, choose a default currency, or synthesize `content_type`
unless the approved source/media requirement and current destination documentation establish that
rule.

## Prefer the least-complex mapping

Select the target mapping from the approved collection contract, applicable skill playbook, and
current official/template documentation before considering local container patterns. Use this order:

1. direct template field or DLV for an already compatible approved source;
2. constant for a stable configuration value or approved fixed semantic value;
3. supported settings variable for a coherent set of genuinely shared fields;
4. lookup/regex table for a real deterministic multi-scenario mapping when it makes environment,
   destination, currency, event, or other configuration logic clearer than repeated conditions;
5. Custom JavaScript for a required destination transformation that built-in variables cannot express cleanly.

After selecting the target pattern, reuse an existing variable only when it implements that pattern
and passes current source, type/shape, null, timing, consumer, consent, environment, and static
acceptance checks. Do not preserve or reproduce a helper merely because the container already uses
that pattern. Harmless naming debt can remain; functional debt cannot become the new architecture.

Do not hard-code a measurement ID, pixel ID, conversion label, currency, or repeated semantic value when a clear named reference improves maintenance. Do not create a constant for a one-off literal when it adds no clarity or reuse.

Do not use Custom JavaScript to reinterpret routine CMP vendor consent when the documented CMP state can be tested directly in a native trigger condition. An undocumented or invalid CMP shape is a source-contract blocker, not a transformation requirement.

For analytics, do not create a mapping for a destination field absent from the approved collection
contract. A documented required field missing from the plan is a blocking discrepancy, while a
recommended or optional field remains omitted unless the analyst explicitly amends the input.

## Preserve arrays and object schemas

For ecommerce and content arrays:

- verify whether the destination expects one object, an array of IDs, or an array of objects;
- return an array for one item when the destination requires an array;
- map all in-scope items;
- retain documented event-level versus item-level fields;
- preserve exact number/string types and allowed enums;
- calculate totals only from the documented source and rule;
- define behavior for empty arrays and missing required item fields;
- test zero-item, one-item, and multi-item payloads.

Do not silently select item zero or filter an item because a field is missing. Preserve the
configured projection contract and record malformed runtime items as a site/dataLayer dependency for
recette. Add an item-level firing rule only when the explicit brief or current official browser
documentation requires it.

## Write narrow Custom JavaScript

Use one output purpose per variable. Make the function:

- deterministic and free of side effects;
- guarded for null, undefined, and wrong input type;
- explicit about string/number conversion;
- free of network calls, DOM mutation, dataLayer pushes, and invented values;
- able to return `undefined` when a critical source contract is not met;
- validated with representative inputs.

Name it `CJS - <Vendor> - <output>`, for example `CJS - Meta - contents`.

Avoid a broad `try/catch` that hides contract defects. Catch only a specifically anticipated error and preserve a visible validation failure.

## Separate configuration completeness from runtime data quality

A transformation output does not control tag firing by itself. Returning `undefined`, `{}`, or `[]`
can still let the approved event tag execute. Treat that as a mapping fact, not as a reason to create
a generic eligibility layer.

- Block configuration when a required design-time field has no approved source, no supported
  template field, or no valid transformation.
- Configure the direct mapping when the approved source exists, even if the value can be missing at
  runtime.
- Record missing, empty, wrong-type, and malformed-array cases as site/dataLayer dependencies for
  the recette workflow.
- Add a payload-related firing condition only when the explicit requirement or current official
  browser contract requires it. Prefer a native trigger condition; use one narrow CJS condition only
  when native filters cannot express the required rule.
- Never combine consent logic with payload validation.

Do not create names such as `CJS - Ecommerce - AddToCart Eligible` as routine infrastructure.

## Statically verify transformations

Use supplied non-sensitive payloads as small static vectors for each transformation actually
created. This is configuration verification, not a test mode or runtime recette. Check at least:

| Input case | Required check |
| --- | --- |
| Missing source | No invented value; affected field/tag follows the approved missing-data rule. |
| Empty array | Output matches documented empty behavior. |
| One item | Required array/object shape and types remain correct. |
| Multiple items | Every item is retained and correctly mapped. |
| Zero value/quantity | Zero is not mistaken for missing. |
| Invalid type | Transformation fails safely and visibly. |

Do not claim that these static vectors prove browser execution or add an automatic firing guard
because a vector is invalid.

## Handle browser event IDs narrowly

Never generate a browser/server event ID, transaction-based deduplication map, or
`gtm.start`/`gtm.uniqueEventId` Custom JavaScript variable in the current client-side-only scope. An
explicit media brief may authorize mapping a supplied browser `event_id` when current official
browser documentation and the installed template support that exact field. For a server or
pipeline request, resolve its owner through the pipeline and server references; do not borrow the
browser field name.
Load `transformation-patterns.md` when the same source-to-destination projection pattern recurs,
especially ecommerce item arrays, destination identifier arrays, scalar validation, or explicit
mapping vectors. The pattern reference standardizes the function contract but current official
destination documentation still establishes every output field.

## Prove transport survivability

For every transported field, record source, web resolved value, wire key/encoding, claiming Client,
generated Event Data key/type, server owner, template field/type, missing behavior, and runtime verification note.
The standard GA route documents `items` as an array and `user_data` as an object with nested paths.
Do not generalize that into “only two arrays” or assume another nested dataLayer object survives.

If a required shape is unsupported, block unless an explicitly approved serialization and named
server parse owner exist. Never silently stringify, flatten, truncate, drop invalid items, or use a
first-item shortcut. A server destination's `contents` or `content_ids` projection remains a
destination mapping, not a dataLayer eligibility test.
