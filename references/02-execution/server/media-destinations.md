# Shared server media destination framework

## Contents

- [Identify the exact route](#identify-the-exact-route)
- [Inspect the implementation surface](#inspect-the-implementation-surface)
- [Map independently](#map-independently)
- [Reconcile overlap](#reconcile-overlap)
- [Fail closed](#fail-closed)

## Identify the exact route

Start from the media brief: platform, server product, business event, destination identity, use, and
credentials owner. Classify the implementation as native GTM server tag, vendor-supported GTM
route, inspected compatible community template, or no proved GTM route. An official CAPI endpoint
does not imply an official GTM server template.

## Inspect the implementation surface

Record installed template publisher/version, fields, permissions, allowed network hosts, secret
handling, automatic Event Data mapping, hashing, batching, responses, and dedup behavior. Import,
upgrade, code edit, or permission expansion requires explicit authority.

## Map independently

Map each business event and field from the approved source through wire and Event Data into the
exact current server schema. Keep event names, time/action source, asset IDs, click/cookie IDs,
matching data, ecommerce/item projections, consent, and missing behavior product-specific. Never
translate GA4 `items` to `contents` by label alone.

## Reconcile overlap

Choose browser-only, server-only/replacement, dual delivery with one shared vendor-documented ID,
or template-native dedup. Preserve current companion fields, assets, event names, and windows. The
browser and server tags must consume one occurrence source; the server never regenerates it.

## Fail closed

Block the destination when the product, official server schema, supported GTM implementation,
template permissions/hosts, credentials owner, source shape, consent signal, or dedup path cannot be
proved. Continue independent destinations whose dependency subtrees remain safe.
