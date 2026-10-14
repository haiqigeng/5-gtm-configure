# GA4 collection safety

## Validate current product constraints

Run this gate before the first affected Google/GA4 write. Open current official collection limits,
reserved-name rules, event/ecommerce/configuration references and PII policy. Record actual source
facts through [evidence review](../core/evidence.md). Current sources own changing limits/catalogues.

For each approved requirement establish valid names/prefixes and lengths, exact parameter/property
names, event/item counts, value types/formats/enums/cardinality, mandatory/conditional fields,
user-property scope/stability, and meaningful zero/false/empty/missing/null behavior. Count the
complete effective outgoing payload including inherited settings. Collection limits and property
custom-definition limits have separate scopes.

[Conformance](intake-and-conformance.md) owns approved semantics and discrepancy handling;
[GA4 ownership](ga4-ownership.md) owns automatic/manual collection overlap.

## Establish permitted source data

Inspect names, paths, literals, synthetic samples, URL/title/campaign overrides, user identity,
search/form and commerce values for direct identifiers or sensitive-data risk. Sources involving
contact/account/government identifiers, fine location or health/financial values need an established
safe approved contract before their fields become ready. Broad regex detection is one inspection
input; source meaning determines the collection decision.

[Identity](../data/identity.md#apply-the-pii-firewall) owns the permitted matching/ordinary-analytics
boundary and [execution privacy](../core/execution.md#handle-secrets-without-false-equality) owns
persisted evidence. Record property-side redaction separately.

## Record the decision

Retain source locator, exact effective field set/count, official findings, discrepancy class, source
safety decision and collection ownership. Record custom definitions, key events, redaction/referral,
cross-domain, retention, filters, audiences and links as external administration. Saved GTM completion
uses the [acceptance](../core/acceptance.md) criteria independently of pending external reporting work.

## Official entry points

- https://support.google.com/analytics/answer/9267744
- https://developers.google.com/analytics/devguides/collection/ga4/reference/events
- https://developers.google.com/analytics/devguides/collection/protocol/ga4/reference
- https://support.google.com/analytics/answer/6366371
