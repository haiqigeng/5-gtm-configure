# Deterministic transformation patterns

## Contents

- [Purpose](#purpose)
- [Pattern contract](#pattern-contract)
- [Use projection before free-form code](#use-projection-before-free-form-code)
- [Ecommerce projection pattern](#ecommerce-projection-pattern)
- [Scalar validation pattern](#scalar-validation-pattern)
- [Runtime missing-output behavior](#runtime-missing-output-behavior)
- [Required static vectors](#required-static-vectors)
- [Forbidden behavior](#forbidden-behavior)

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

The transformation must be a pure, synchronous, side-effect-free function. It must not mutate the
dataLayer, read arbitrary DOM state, make network calls, set consent, generate business values, or
silently change the approved source contract.

## Use projection before free-form code

For GA4-style ecommerce to a media destination, use an explicit projection:

```javascript
function() {
  var items = {{DLV - ecommerce.items}};
  if (!Array.isArray(items) || items.length === 0) return undefined;
  var output = [];
  for (var i = 0; i < items.length; i++) {
    var item = items[i];
    if (!item || item.SOURCE_ID === undefined || item.SOURCE_ID === null || item.SOURCE_ID === '') {
      return undefined;
    }
    output.push({
      DESTINATION_ID: String(item.SOURCE_ID),
      DESTINATION_QUANTITY: item.SOURCE_QUANTITY
    });
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
official browser schema. Never treat the vendor names here as a cached field catalogue.

Create separate outputs when one destination requires both an object array and an identifier array.
Preserve original item order and every mapped item. Do not silently filter malformed items. Return
the documented transformation result and record malformed runtime source data for recette unless
the explicit brief or current browser contract defines another rule.

## Scalar validation pattern

For currency, value, quantity, date, or identifier fields:

1. preserve valid zero and `false`;
2. reject `NaN`, infinity, invalid formats, and undocumented enum values;
3. do not trim, truncate, round, lowercase, uppercase, hash, or coerce unless required by current
   official documentation and authorized by the source contract;
4. keep validation separate from an invented fallback;
5. return a clearly missing/invalid result without inventing a fallback.

## Runtime missing-output behavior

A transformation returning `undefined`, `{}`, or `[]` does not prevent a tag from firing. Do not
turn that fact into a routine Boolean eligibility helper. When the source mapping is approved,
configure the business-event trigger and treat runtime missing or malformed data as a site/dataLayer
dependency for recette.

Only when the explicit brief or current official browser contract requires a firing rule, use a
direct native condition. A narrow CJS condition is allowed only when native filters cannot express
that required rule. It must not duplicate transformation parsing or consent logic.

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

## Forbidden behavior

Do not add generic truncation, automatic type coercion, first-item selection, default currency,
fallback catalogue ID, partial-item filtering, hidden PII normalization, broad try/catch suppression,
or one cross-vendor transformation object. A deterministic pattern reduces repeated coding; it does
not authorize guessed business logic.

## Choose the server owner narrowly

In a server container prefer, in order: native destination/Event Data mapping, direct Event Data
variable, installed-template mapping table or item projection, narrow supported server variable,
then a scoped Transformation. Use a broad Transformation only when the approved rule genuinely
applies to all affected consumers and explicit high-impact authority covers its blast radius.

Do not create one shared Transformation merely to convert GA4 `items` into one media vendor's
schema. Keep platform-specific projection inside that destination tag/template when supported.
