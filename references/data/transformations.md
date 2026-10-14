# Deterministic transformation patterns

## Contents

- [Purpose](#purpose)
- [Pattern contract](#pattern-contract)
- [Use projection before free-form code](#use-projection-before-free-form-code)
- [Ecommerce projection pattern](#ecommerce-projection-pattern)
- [Scalar validation pattern](#scalar-validation-pattern)
- [Runtime missing-output behavior](#runtime-missing-output-behavior)
- [Required static vectors](#required-static-vectors)
- [Projection contract](#projection-contract)

## Purpose

Use these patterns when a direct DLV, constant, settings variable, LUT, or RLT cannot produce the
official destination shape. They standardize repeated client-side transformations without creating
a generic transformation framework.

## Pattern contract

Before writing Custom JavaScript, record:

- exact source event and input path;
- representative non-sensitive input;
- exact current official destination schema;
- required and optional fields;
- source-to-destination key and type mapping;
- missing, null, zero, `false`, empty, one-item, multi-item, and invalid-item behavior;
- runtime missing-output and recette dependency;
- expected output vectors.

The transformation is a pure synchronous function of its declared approved source inputs, returning
only the contracted output. State, consent and business-value creation retain their upstream owners.

## Use projection before free-form code

For GA4-style ecommerce to a media destination, use an explicit projection:

```javascript
function() {
  var items = {{DLV - ecommerce.items}};
  if (!Array.isArray(items) || items.length === 0) return undefined;
  var output = [];
  for (var i = 0; i < items.length; i++) {
    var item = items[i];
    if (!item || Object.prototype.toString.call(item) !== '[object Object]') {
      return undefined;
    }
    var id = item.SOURCE_ID;
    if ((typeof id !== 'string' && typeof id !== 'number') || id === '' ||
        (typeof id === 'number' && !isFinite(id))) return undefined;
    var quantity = item.SOURCE_QUANTITY;
    if (quantity !== undefined &&
        (typeof quantity !== 'number' || !isFinite(quantity) || quantity < 0)) return undefined;
    var projected = {DESTINATION_ID: String(id)};
    if (quantity !== undefined) projected.DESTINATION_QUANTITY = quantity;
    output.push(projected);
  }
  return output;
}
```

Replace every uppercase placeholder from the approved source and current official destination
contract. Remove optional keys rather than sending `undefined`. Add numeric conversion only when the
destination requires a number and the approved source contract permits that conversion.

## Ecommerce projection pattern

Apply the same disciplined projection for Meta `contents`/`content_ids`, TikTok/Snap/Pinterest/X
item collections, and Google Ads/Floodlight dynamic remarketing only after reopening the exact
official browser schema. Current product evidence owns the exact destination schema.

Create separate outputs when one destination requires both an object array and an identifier array.
Preserve original item order and cardinality under the documented output contract. Malformed input
uses the approved missing/invalid behavior and remains a source field-test dependency.

## Scalar validation pattern

For currency, value, quantity, date, or identifier fields:

1. preserve valid zero and `false`;
2. reject `NaN`, infinity, invalid formats, and undocumented enum values;
3. apply only conversions established by current destination documentation and approved source semantics;
4. return the documented missing/invalid result when validation fails.

## Runtime missing-output behavior

Apply [mapping completeness and runtime data quality](mapping.md#separate-configuration-completeness-from-runtime-data-quality).
The projection defines output shape and missing/invalid results. The approved firing policy and
consent owners govern whether an occurrence executes.

## Required static vectors

Record and statically evaluate at least:

| Case | Expected decision |
| --- | --- |
| Missing source | Missing output; no invented fallback; record the runtime dependency. |
| Empty array | Documented empty output and recette dependency. |
| One valid item | Exact one-item destination shape. |
| Several valid items | Exact order and complete item preservation. |
| Valid zero value/quantity | Preserved when permitted. |
| Missing required identifier in any item | No silent item filtering; documented missing/invalid output. |
| Optional source absent | Destination key omitted, not guessed. |
| Unexpected source type | Invalid; no silent coercion. |

Keep vectors in the current-operation evidence. Runtime browser execution belongs to the separate
recette skill.

## Projection contract

Emit the approved destination fields with exact cardinality and explicit authorized conversions.
Missing/invalid values follow the documented output contract. Keep each destination's projection
and first-party-data normalization with its declared owner. A reusable function pattern supplies
implementation structure; approved inputs and current product documentation supply its semantics.

## Choose the server owner narrowly

In a server container prefer, in order: native destination/Event Data mapping, direct Event Data
variable, installed-template mapping table or item projection, narrow supported server variable,
then a scoped Transformation. Use a broad Transformation only when the approved rule genuinely
applies to all affected consumers and explicit high-impact authority covers its blast radius.

A destination-local tag/template owns its supported product projection. A shared Transformation
requires a distinct approved cross-consumer purpose.
