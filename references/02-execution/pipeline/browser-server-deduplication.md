# Browser/server deduplication

## Contents

- [Require a contract only for overlap](#require-a-contract-only-for-overlap)
- [Choose one occurrence identity](#choose-one-occurrence-identity)
- [Map vendor fields independently](#map-vendor-fields-independently)
- [Prove runtime equality externally](#prove-runtime-equality-externally)

## Require a contract only for overlap

Create a dedup contract when the same destination event can reach the same platform through more
than one ingestion route. Choose `single-channel`, `server-replaces-browser`, `dual-shared-id`,
`platform-native`, or `not-applicable` from current product evidence. Never add `event_id` merely
because another CAPI vendor uses it. A generic `dual-shared-id` contract is invalid for Google Ads
or Floodlight: use their current product-specific replacement/duplication mechanism and fields.

## Choose one occurrence identity

For `dual-shared-id`, use one value everywhere:

1. For dual-delivery purchase, require the approved stable transaction/order/occurrence identity
   supported by the exact vendor; retain any separate cross-channel identifier it also requires.
2. For another event, use a stable approved occurrence ID such as a lead ID.
3. Otherwise use an explicitly supplied site/dataLayer event ID.
4. If no approved stable occurrence ID exists, choose one delivery channel or keep dual delivery
   blocked until the source owner provides one.

The source value may map to different browser and server field names. Do not reuse a session/user
ID across occurrences, generate a second server ID, or create independent random generators.

## Map vendor fields independently

Open current official product guidance and the installed template. The source is vendor-neutral,
but the destination fields, companion identifiers, event names, assets, and windows are not. For
example, Snap currently distinguishes browser `client_dedup_id`, CAPI `event_id`, browser
`transaction_id`, and CAPI `custom_data.order_id`; do not collapse those labels even when values
match.

## Prove runtime equality externally

Record that runtime recette must independently prove same occurrence, same resolved identifier, same asset,
compatible event name, browser/transporter timing, server consumption without regeneration, and
distinct identifiers across repeated events, reloads, and SPA transitions. Saved GTM readback
cannot certify deduplication.
