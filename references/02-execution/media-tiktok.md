# TikTok Pixel browser tags

## Complete the media brief

Confirm or derive:

- TikTok Pixel ID, Ads account, and environment;
- requested business action and optimization/reporting/audience use;
- current standard event or justified custom event;
- catalog/product-ID convention and shopping objective;
- required value, currency, content fields, order ID, and item arrays;
- Event Builder, automatic events, or existing partner integration;
- automatic/manual Advanced Matching request;
- CMP and strict/basic consent policy or explicitly requested TikTok Pixel cookie-consent behavior.

## Research current TikTok events and parameters

Open the current official TikTok standard-events page, parameter reference, custom-event rules, GTM event-tag guide, and installed template documentation. Extract:

- exact standard event code and meaning;
- recommended, required, and conditionally required parameters for the selected objective;
- accepted type, enum, currency, array, and object shape;
- reserved custom-event names and naming limits;
- Pixel base/event dependency and template fields;
- catalog/ROAS/Video Shopping requirements;
- current cookie, consent, and Advanced Matching behavior.

Use the current supported TikTok Pixel template when available. If it is absent, follow the
authorized supported-template install path; do not substitute Custom HTML or remembered pixel code.
Block when installation/update authority is unavailable.

Do not rely on a static list in this skill. TikTok revises its events and parameters.

## Design the Pixel object graph

Use a verified `CST - TikTok pixel_id` when appropriate. Ensure one compatible Pixel initialization path exists, reusing a compatible GTM base tag, site code, partner integration, or template behavior. Create a new GTM base tag only when initialization is in scope and no compatible path exists. Configure requested event tags separately and use the vendor-neutral Custom Event trigger; TikTok's current GTM guidance also recommends a GTM custom event for event tags.

Do not make the base tag send a page-view event by default. Configure a separate official page-view event only when requested and after inspecting Event Builder, automatic event detection, partner/CMS integrations, existing Pixel code, and automatic SPA behavior. If the current official base code or selected template inherently sends a page view, document that vendor exception and prevent a duplicate separate or history-based page view.

## Map commerce and content fields exactly

Treat `content_id`, `content_ids`, `contents`, `content_type`, value, currency, and order fields as separate contracts. Verify the current page because requirements can vary by objective.

When the current schema requires arrays:

- preserve every approved product ID;
- return the documented array/object structure even for one item;
- map the catalog's actual SKU or item-group convention;
- preserve exact types and allowed enums;
- test empty, one-item, and multi-item cases.

Do not assume Meta's field shapes are valid for TikTok merely because some parameter names are similar.

## Avoid automatic and manual duplicates

Inspect the current TikTok Events Manager automatic/website event features, partner installations,
and existing GTM tags using the terminology and controls visible now. Choose one browser collection
source for the action. If an automatic rule and a proposed manual event overlap, do not add the
manual event until the media owner selects the intended source and any removal or disablement of the
overlap is separately authorized. Do not preserve dated feature labels as a static capability
catalogue. Browser/server deduplication remains deferred.

## Configure Advanced Matching only explicitly

Do not enable automatic or manual Advanced Matching by default. Require explicit approval, verify accepted identifiers, source, normalization, hashing, automatic field scanning, and data-sharing terms from current official documentation. Follow the first-party-data reference.

## Apply consent

Use strict/basic CMP gating by default for the Pixel base and all event tags. Attach the complete approved TikTok block set and prove from the static trigger graph that Pixel tags are expected to remain blocked for unknown or denied consent.

TikTok documents a Pixel cookie-consent mode and cookie enable/disable controls. Classify that first as `native cookie-control`, not automatically as advanced denied-state measurement. Cookie suppression does not prove which events, fields, identifiers, or requests continue, nor that TikTok applies an advertiser-specific model.

Use a TikTok-native limited-data route only when explicitly requested and current official product/template documentation establishes the complete denied-state request, storage, data-use, and revocation behavior approved by the client. Otherwise retain the strict/basic block. Do not assume that enabling Google Consent Mode alone gates or changes a third-party TikTok template.

## Verify the saved TikTok setup

Re-read the Pixel base/event tags, template version and fields, destination constant, ecommerce
mapping, normal and blocking triggers, advanced-matching settings, current automatic-event overlap,
firing options, folders, and references. Confirm one initialization path, every
required item, and an idempotent rerun. Keep platform-side Event Builder, catalog, optimization, and
publication work separate.

## Official entry points

- https://ads.tiktok.com/help/article/standard-events-parameters
- https://ads.tiktok.com/help/article/about-parameters
- https://ads.tiktok.com/help/article/how-to-set-up-tiktok-pixel-in-google-tag-manager
- https://ads.tiktok.com/help/article/how-to-create-tiktok-event-tags-with-google-tag-manager
- https://ads.tiktok.com/help/article/custom-events
- https://ads.tiktok.com/help/article/pixel-release-notes
- https://ads.tiktok.com/help/article/how-to-use-cookies-with-tiktok-pixel
- https://ads.tiktok.com/help/article/advanced-matching-web

## Server route

For TikTok Events API, load `server/media-tiktok.md`. Prefer and inspect the vendor-generated GTM
web/server integration when applicable; otherwise prove one shared dedup owner across the exact
browser and server templates.
