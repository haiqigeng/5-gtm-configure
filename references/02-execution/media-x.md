# X Pixel

## Contents

- [Resolve the brief](#resolve-the-brief)
- [Research the current browser integration](#research-the-current-browser-integration)
- [Configure base and event tags](#configure-base-and-event-tags)
- [Ecommerce and matching](#ecommerce-and-matching)
- [Verify](#verify)

## Resolve the brief

Require the X Ads account/use, pixel identity, exact conversion event identity where applicable,
business action, optimization/audience objective, source event, and environment. Distinguish the
base pixel from each lower-funnel event.

## Research the current browser integration

Open the current official page at
https://business.x.com/en/help/campaign-measurement-and-analytics/conversion-tracking-for-websites
and inspect the installed X Pixel template/partner integration. Confirm current base/event fields,
supported event types, parameters, automatic/dataLayer behavior, and deprecations.

## Configure base and event tags

Reuse one compatible base pixel per identity/environment. Configure event tags from the exact
platform event identity and current template fields. Reconcile partner-created GTM objects,
hard-coded code, automatic site/landing-page events, and any “dataLayer Standard Events” option to
prevent duplicate lower-funnel events.

Do not reuse a GA4 event name as an X conversion identifier. Keep pixel and event identities
separate and block when the platform-side event has not been created or supplied.

## Ecommerce and matching

Use the current official value, currency, content collection, and conversion/deduplication fields.
Require the exact catalog convention, preserve all approved items, and require design-time sources
for required identifiers. Map runtime values directly and load the transformation playbook only for
a real array projection; do not add a payload-eligibility helper.

User parameters or matching require explicit approval, accepted fields, normalization/hash
ownership, consent, and destination isolation. Event or conversion IDs are not generated merely
because a future server-side implementation might use them.

Default strict/basic CMP blocking and establish current X-specific consent behavior before any
other route.

## Verify

Read back base/event tags, pixel and event identities, template/version, fields, item shape,
triggers, consent, matching, automatic behavior, folder, and references. Keep Events Manager setup,
audiences, catalog, Test Events/Pixel Helper, runtime receipt, and publication external.

## Server route

For the exact X Conversion API product, load `server/media-x.md`. Prove account access, installed
template, request schema, `conversion_id` behavior, and browser overlap rather than inferring API
support from the Pixel.
