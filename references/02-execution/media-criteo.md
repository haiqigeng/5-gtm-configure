# Criteo OneTag

## Contents

- [Resolve and research](#resolve-and-research)
- [Design page-type and event coverage](#design-page-type-and-event-coverage)
- [Product and transaction data](#product-and-transaction-data)
- [Consent and verification](#consent-and-verification)

## Resolve and research

Require the Criteo account/partner identity, exact OneTag product, business use, page/event coverage,
source events, catalog convention, and environment. Open current official Criteo browser OneTag,
GTM, event, product, transaction, and consent documentation from https://help.criteo.com/ and inspect
the installed template/version.

Block any critical field that cannot be established from primary documentation, the media brief,
and installed template. Do not infer Criteo's page-type or product schema from another retail-media
vendor.

## Design page-type and event coverage

Reconcile existing site, partner, plugin, and GTM OneTag paths before creating another base. Map only
the page types and business actions required by the brief. Establish current initialization order,
page-view behavior, SPA handling, template automation, and whether separate tags or one dispatcher
is the supported architecture.

Keep account/partner identity, page type, event identity, and feed/catalog identity separate. Do not
use URL rules as a substitute for an approved application event when success semantics require the
dataLayer.

## Product and transaction data

For listing, product, basket, and transaction payloads, establish exact current product-ID,
quantity, price/value, currency, transaction, and item-array rules. Preserve every approved item,
valid zero values, and official types. Require every design-time source before mutation, then map
runtime values directly without a separate eligibility helper.

Use the deterministic transformation playbook when the source array is incompatible. Never assume
GA4 `item_id` equals the Criteo feed key, silently filter an invalid product, or invent a fallback
currency or transaction ID.

## Consent and verification

Default strict/basic CMP blocking. Use another documented Criteo consent or limited-data route only
when explicitly requested and proven for the exact browser product/template. Keep user matching or
identity fields opt-in, source-approved, and isolated from analytics.

Read back OneTag initialization, account identity, page/event tags, full product/transaction shape,
template/version, triggers, consent, environment, consumers, and duplicates. Record feed/account
setup, audiences, platform-side rules, runtime validation, and publication as external work.
