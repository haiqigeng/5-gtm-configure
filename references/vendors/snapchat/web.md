# Snap Pixel browser tags

Apply the [media contract](../../media/common.md) and its linked implementation owners.

## Resolve Snap semantics

Establish Pixel/account/environment, business action, optimization/reporting/audience use,
standard/custom event, catalog/Dynamic Ads convention, applicable value/currency/order/item/page
fields and selected matching scope. Research current Pixel/GTM/browser references and inspect
`Snap Pixel by Snapchat` or the selected template's exact publisher/version, fields and behavior.
Browser fields require browser evidence or an explicit official shared contract with CAPI.

## Configure the browser graph

Reconcile existing GTM/site/partner initialization and page views. Use a stable
`CST - Snapchat pixel_id` where useful. A template coupling initialization and page view counts as
that occurrence's owner. Map the current Snap item/content schema, value/currency and order semantics
from approved sources through the exact installed fields. Matching and native consent choices use
[identity](../../data/identity.md) and [capability classification](../../consent/product-capabilities.md).

## Verify

Review initialization/occurrence ownership, Pixel/event identity, complete item shape, matching and
consent. Record catalog, optimization and account activation dependencies separately. The current
browser setup page supplies method-specific fields; the former `formatting-pixel` help link was
unusable at the 2026-09-29 review.

## Official entry points

- https://developers.snap.com/marketing-api/Ads-API/snap-pixel
- https://developers.snap.com/marketing-api/Conversions-API/Deduplication
- https://forbusiness.snapchat.com/advertising/snap-pixel

## Server route

For Snap CAPI, load [Server](server.md). Inspect the current version and exact identifier pairs:
`client_dedup_id`, `event_id`, `transaction_id` and `custom_data.order_id` retain their documented roles.
