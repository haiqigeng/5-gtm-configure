# Google Ads browser tags

## Contents

- [Establish the requested Google Ads product](#establish-the-requested-google-ads-product)
- [Complete the media brief](#complete-the-media-brief)
- [Research the exact browser schema](#research-the-exact-browser-schema)
- [Design conversion tracking](#design-conversion-tracking)
- [Design remarketing](#design-remarketing)
- [Decide Conversion Linker from current architecture](#decide-conversion-linker-from-current-architecture)
- [Configure enhanced conversions only explicitly](#configure-enhanced-conversions-only-explicitly)
- [Apply consent](#apply-consent)
- [Prevent automatic-event duplication](#prevent-automatic-event-duplication)
- [Verify the saved Google Ads setup](#verify-the-saved-google-ads-setup)
- [Official entry points](#official-entry-points)

## Establish the requested Google Ads product

Determine whether the media team requests:

- a Google Ads conversion action;
- standard or dynamic remarketing;
- a Google tag destination/configuration;
- a Conversion Linker requirement;
- enhanced conversions for web;
- an imported GA4 key event rather than a direct Google Ads browser conversion.

Do not implement all products automatically. Treat direct Google Ads conversion tracking and GA4-imported conversions as different architectures and record which one governs.

## Complete the media brief

Confirm or derive the applicable values:

- Google Ads destination or conversion ID;
- conversion label for a direct conversion tag;
- exact business conversion and firing moment;
- fixed or dynamic conversion value and currency;
- transaction/order ID and duplicate-conversion behavior;
- remarketing audience use and dynamic remarketing business vertical/feed;
- required item identifiers and their match with the Merchant Center or business feed;
- enhanced-conversion request and user-data source;
- CMP and basic versus explicitly approved advanced Google Consent Mode.

Use constants such as `CST - Google Ads conversion_id` and `CST - Google Ads conversion_label` when stable identifiers are reused or a named reference is clearer than a literal.

## Research the exact browser schema

Open current official Google Ads and GTM documentation for the selected product. Record:

- tag type and destination;
- event or conversion action;
- required and optional tag fields;
- value, currency, and transaction ID semantics;
- dynamic remarketing event name and business-vertical item schema;
- Conversion Linker behavior in the current Google tag architecture;
- enhanced-conversion fields, normalization, hashing responsibility, and policies;
- built-in consent checks and selected consent-mode behavior.

Use GTM's native Google tag, Google Ads Conversion Tracking, Google Ads Remarketing, and Conversion
Linker types when applicable. Do not substitute Custom HTML or a generic template for a native
Google implementation.

Do not assume that GA4 ecommerce `items` can be passed unchanged to Google Ads dynamic remarketing. Transform only to the current Google Ads business-vertical schema.

## Design conversion tracking

Use one conversion event tag per conversion action/label unless the current template officially supports a cleaner parameterized design and all semantics match.

Map:

| Google Ads concept | Implementation rule |
| --- | --- |
| Conversion ID and label | Reference verified constants or existing equivalent variables. |
| Value | Use the documented number source; do not send a formatted currency string. |
| Currency | Use a documented ISO currency value and a reusable source/constant where appropriate. |
| Transaction ID | Use the actual stable order/transaction identifier when required; never generate a random replacement for purchase. |
| Trigger | Use the vendor-neutral Custom Event representing the completed business action. |
| Consent | Attach the shared Google Ads block for the default basic route. |

Do not create a browser/server event ID in the current client-side scope.

When current documentation makes a conversion field or value/currency pair required for the
selected use, require its source mapping before configuration and then map the runtime value
directly. Do not create a payload-eligibility CJS, rely on an unresolved variable as an implicit
gate, or invent a zero, empty currency, or random transaction ID. Runtime missing data remains a
site/dataLayer and recette dependency.

## Design remarketing

For standard remarketing, verify whether a site-wide Google tag or remarketing tag already supplies the required behavior. Avoid duplicate site-wide implementations.

For dynamic remarketing:

1. Confirm the correct business vertical.
2. Open the current event-and-parameter reference for that vertical.
3. Map every required item attribute to the actual feed identifier.
4. Preserve every approved item in the required array.
5. Validate event value and item types.
6. Prevent a GA4 destination payload from being reused without an explicit Google Ads mapping.

## Decide Conversion Linker from current architecture

Inspect existing Google tags, Google Ads/Floodlight tags, cross-domain needs, and current Google guidance before creating a Conversion Linker. Reuse a compatible linker when one exists. Do not add a duplicate simply because older implementations always used one.

Load `conversion-linker-cross-domain.md` whenever click attribution, incoming linker parameters,
form decoration, multiple domains, or shared Ads/Floodlight consumers are involved. Keep GA4 Admin
cross-domain configuration external unless an exact approved GTM override is required. Require an
approved domain list and never derive it from arbitrary outbound links.

If a linker is needed, configure only the documented options required by the site and apply the selected consent architecture.

## Configure enhanced conversions only explicitly

Require an explicit enhanced-conversions request, an approved first-party data source, appropriate policy/terms confirmation by the analyst, and the correct Google Ads/Google tag setting.

Follow the first-party-data reference. Prefer deliberate dataLayer/JavaScript variables over automatic DOM collection when the analyst wants controlled, auditable data. Verify whether the template or Google tag performs hashing; do not double-hash.

## Apply consent

Default to basic Google Consent Mode and attach `Block - <CMP> - Google Ads denied` to all in-scope Google Ads/Google tag/linker execution units that must not load before consent. Before attaching it to a Google tag or helper shared with GA4, Floodlight, or another destination, verify that every destination or consumer has a compatible basic route; otherwise follow the shared-execution-unit decision in the Google consent reference.

Establish one owner for Google consent defaults/updates and map the approved CMP policy to
`ad_storage`, `ad_user_data`, and `ad_personalization`, plus `analytics_storage` where the execution
unit also serves Analytics. Built-in checks do not replace the strict pre-grant block in the basic
route.

Use advanced Google Consent Mode only when explicitly requested. In that route, follow the Google consent reference, use documented defaults and updates, and avoid blocking triggers/additional checks that suppress the intended denied-state behavior.

## Prevent automatic-event duplication

Do not make the Google Ads config/base tag send a business page view by default. Inspect Google tag destinations, automatic event detection, remarketing behavior, GA4 imports, and hard-coded Google tags before adding a tag.

## Verify the saved Google Ads setup

Re-read the saved Google tag/conversion/remarketing/linker objects and confirm destination IDs,
labels, event fields, feed mapping, value/currency mapping, installed-template fields, normal and
consent triggers, shared consumers, firing settings, references, and an idempotent rerun. Keep the
external conversion action, imported-event choice, feed, enhanced-conversion account settings, and
publication explicitly separate.

## Official entry points

- https://support.google.com/google-ads/answer/7521212
- https://support.google.com/tagmanager/answer/6106009
- https://support.google.com/google-ads/answer/7305793
- https://support.google.com/google-ads/answer/13262500
- https://developers.google.com/tag-platform/security/concepts/consent-mode
