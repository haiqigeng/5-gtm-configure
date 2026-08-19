# GA4 collection safety

## Contents

- [Purpose](#purpose)
- [Validate from current official documentation](#validate-from-current-official-documentation)
- [Protect approved semantics](#protect-approved-semantics)
- [Check names, fields, limits, and types](#check-names-fields-limits-and-types)
- [Prevent PII and sensitive-data leakage](#prevent-pii-and-sensitive-data-leakage)
- [Separate collection from property administration](#separate-collection-from-property-administration)
- [Record the decision](#record-the-decision)

## Purpose

Run this gate for every Google tag or GA4 analytics requirement before the first write. Its purpose
is to prevent technically invalid or unsafe collection, not to optimize the approved tracking plan.

## Validate from current official documentation

Open the current official pages for event collection limits, reserved names, recommended/ecommerce
events, configuration fields, and PII policy during the run. Record the URLs, titles, access date,
and the exact facts used. Do not freeze numeric limits or reserved-name catalogues as permanent skill
truth; Google changes them.

Use these entry points:

- https://support.google.com/analytics/answer/9267744
- https://developers.google.com/analytics/devguides/collection/ga4/reference/events
- https://developers.google.com/analytics/devguides/collection/protocol/ga4/reference
- https://support.google.com/analytics/answer/6366371

## Protect approved semantics

Classify every finding before mutation:

| Finding | Action |
| --- | --- |
| Valid but a different official recommendation exists | `advisory`; preserve the approved event and fields. |
| Invalid/reserved name, impossible type/shape, exceeded hard collection limit, or missing required field | `blocking-error`; stop the affected requirement. |
| GTM-only architecture or property-side follow-up | `implementation-note`; do not change the approved payload. |

Never rename, remove, shorten, coerce, split, or add a collection field without an explicit amended
analytics decision. In particular, do not add a seemingly useful field such as `lead_type` because
another tag, prior implementation, or generic recommendation contains it.

## Check names, fields, limits, and types

For each included requirement, prove from current documentation:

- event name validity, length, reserved status, and forbidden prefix status;
- exact parameter and user-property name validity and length;
- outgoing event-parameter count and applicable item-parameter count;
- parameter value type, format, character limit, enum, and cardinality;
- required recommended/ecommerce fields and item-level requirements;
- user-property validity, stability, scope, and current collection limit;
- compatibility of valid zero, `false`, empty, missing, and null behavior;
- absence of automatic, Enhanced Measurement, Google tag, hard-coded, or Event Builder duplication.

Count the final outgoing fields after applying Event Settings variables and inherited Google tag
settings, not only the fields visible on an individual event tag. Do not confuse property custom
definition limits with collection limits.

## Prevent PII and sensitive-data leakage

Statically inspect approved names, source paths, literals, representative samples, URL/title
overrides, campaign fields, user IDs, user properties, and search/form values for clear PII or
sensitive-data risk. At minimum consider email, telephone, full name, postal address, government or
account identifiers, fine-grained location, health/financial values, and PII embedded in URLs or
titles.

Do not treat a broad regex scan as proof that data is safe. Do not emit sensitive sample values into
the configuration map, logs, source manifest, or result. If a required source could contain PII and
the approved safe contract is not established, block the affected GA4 field. Keep advertising
matching fields isolated from GA4 even when the same source is approved for another destination.

Hashing does not make an ordinary GA4 event parameter, user property, custom definition,
`user_id`, URL, title, search value, form value, or campaign field an authorized PII destination.
The only exception is a specifically permitted and explicitly activated native user-provided-data
feature configured under `first-party-data.md`; its values never enter the ordinary analytics
payload surfaces or the run/change-log artifacts. Treat GA4 data redaction as an external safety
net, not permission to collect PII.

## Separate collection from property administration

Record but do not claim completion of:

- custom dimensions and metrics;
- key-event designation;
- data redaction and unwanted-referral settings;
- GA4 Admin cross-domain configuration;
- data retention, filters, audiences, links, or reporting setup.

The GTM configuration can be `Configured` while one of these is an explicit external dependency,
provided it is not required for the tag to send a valid approved payload.

## Record the decision

For each GA4 requirement, retain the approved source locator, final parameter set, official checks,
discrepancy class, outgoing count, PII decision, automatic-event reconciliation, and any external
GA4 administration. Re-run the exact conformance comparator before mutation and after saved-state
readback.
