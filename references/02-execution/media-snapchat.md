# Snap Pixel browser tags

## Complete the media brief

Confirm or derive:

- Snap Pixel ID, Ads account, and environment;
- requested business action and optimization/reporting/audience use;
- current standard event or justified custom event;
- catalog or Dynamic Ads requirement and product-ID convention;
- required value, currency, transaction/order ID, item, and page fields;
- matching or automatic collection request;
- CMP vendor identity and strict/basic consent policy.

## Research current Snap browser requirements

Open the current official Snap Pixel, GTM integration, event, parameter, catalog, and matching documentation. Inspect the installed `Snap Pixel by Snapchat` template or other selected template.

Record:

- exact event name/casing and standard/custom status;
- required, recommended, optional, and conditional parameters;
- accepted type, format, enum, and cardinality;
- Pixel initialization and event behavior;
- template publisher, version, permissions, and fields;
- catalog identifier rules;
- browser-side consent and matching capability.

Do not use Conversions API parameter documentation as the sole authority for a browser Pixel field. Use it only when the official browser documentation explicitly shares that contract.

Use the current supported Snap Pixel template when available and inspect its actual repository,
version, permissions, and saved fields. If current Snap browser documentation or the installed
template cannot establish a field, omit or block that field; do not borrow it from CAPI or
remembered Pixel examples. Do not substitute Custom HTML when a supported template installation
path exists but authority is missing.

## Design the Pixel object graph

Use a verified `CST - Snapchat pixel_id` when appropriate. Ensure one compatible Pixel initialization path exists, reusing a compatible GTM tag, site code, partner integration, or template behavior. Create a new GTM initialization/base tag only when initialization is in scope and no compatible path exists. Configure requested event tags separately with the vendor-neutral Custom Event trigger.

Do not make the base tag send a page-view event by default. Add a separate page-view event only when requested and after inspecting existing GTM tags, site code, plugins, and automatic/template behavior. If the selected official template couples initialization and page view, document that exception and prevent a duplicate manual event.

## Map event parameters exactly

Build the complete source-to-template-to-vendor map. Preserve product arrays and all approved items
when the current Snap schema requires them. Verify value/currency and transaction/order semantics
independently. Map runtime values directly and do not add a payload-eligibility CJS.

Do not copy Meta, TikTok, or GA4 product shapes into Snap. Transform only from the actual dataLayer to the current Snap browser schema.

## Configure matching only explicitly

Do not enable automatic or manual customer matching by default. Require explicit request/approval, verify browser-supported identifiers and hashing responsibility, confirm the data source and consent, and follow the first-party-data reference.

## Apply consent

Use strict/basic CMP gating by default for the Snap base and all event tags. Attach the complete approved Snapchat block set and prove from the static trigger graph that unknown and denied states are expected to keep Snap tags blocked.

Use a native consent capability only when explicitly requested and its complete denied-state request, storage, and data-use behavior is established by current official Snap browser documentation. A template consent field alone does not establish advanced behavior. Follow the vendor consent-mode capability reference and do not infer Google Consent Mode behavior.

## Verify the saved Snap setup

Re-read the Pixel initialization/event tags, template version and fields, destination constant,
product mapping, matching settings, normal and blocking triggers, firing options,
folders, and references. Confirm one initialization path, all required items, no known duplicate,
and an idempotent rerun. Keep catalog, optimization, matching account settings, and publication
outside the GTM completion claim.

## Official entry points

- https://developers.snap.com/marketing-api/Ads-API/snap-pixel
- https://businesshelp.snapchat.com/articles/en_US/Knowledge/formatting-pixel
- https://forbusiness.snapchat.com/advertising/snap-pixel

## Server route

For Snap CAPI, load `server/media-snapchat.md`. Use the current API version and map the exact
browser/server identifier pairs; do not collapse `client_dedup_id`, `event_id`, `transaction_id`,
and `custom_data.order_id` into one guessed field.
