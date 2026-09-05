# Microsoft Advertising browser tags

## Contents

- [Treat Bing Ads as Microsoft Advertising](#treat-bing-ads-as-microsoft-advertising)
- [Complete the media brief](#complete-the-media-brief)
- [Research current UET semantics](#research-current-uet-semantics)
- [Design the UET object graph](#design-the-uet-object-graph)
- [Map fields exactly](#map-fields-exactly)
- [Apply consent](#apply-consent)
- [Verify the saved Microsoft setup](#verify-the-saved-microsoft-setup)
- [Official entry points](#official-entry-points)

## Treat Bing Ads as Microsoft Advertising

Interpret references to Bing Ads or Bing UET as Microsoft Advertising unless the analyst identifies another product. Use current Microsoft terminology in new objects while preserving recognizable existing names when reuse is safer.

## Complete the media brief

Confirm or derive:

- UET tag ID and advertising account/environment;
- requested conversion goal and exact business action;
- page-load versus custom-event measurement;
- event category, action, label, value, revenue, and currency fields required by the current goal/schema;
- dynamic remarketing/product-audience requirements and feed identifiers;
- basic versus explicitly approved advanced UET Consent Mode;
- separate UET and Clarity consent decisions when Clarity integration or another Microsoft product coupling is present.

Do not assume that sending a UET event creates the Microsoft Advertising conversion goal. Record any platform-side goal configuration as a separate requirement outside GTM unless it is explicitly authorized and tool access exists.

## Research current UET semantics

Open the current official UET custom-event, parameter-table, GTM-template, consent, and dynamic remarketing documentation. Verify:

- UET base/page-load behavior;
- custom-event syntax and supported parameters;
- conversion revenue and currency fields;
- product and feed parameter requirements;
- official GTM template fields/version;
- Consent Mode settings and default behavior;
- automatic SPA tracking or other template options.

Do not map GA4 event names or parameters directly to UET without a documented Microsoft field map.

Use Microsoft's current supported UET GTM template and its saved fields. If it is not installed,
follow the authorized supported-template install path; do not replace it with Custom HTML. Block
when template install/update authority is unavailable.

Never implement Microsoft Advertising consent defaults, updates, base code, or events with
`gtag(...)`. Google Consent Mode commands do not configure UET. Use Microsoft's current UET
template/API fields and the CMP's verified lifecycle; do not invent a
`microsoft_ads_consent_granted` dataLayer event unless the approved site contract explicitly
defines that exact event.

## Design the UET object graph

Use a verified constant such as `CST - Microsoft Ads uet_tag_id` when the UET ID is reused.

Configure:

1. one UET base tag when the current architecture requires it;
2. separate UET custom-event tags for the requested business actions;
3. vendor-neutral Custom Event triggers;
4. the shared Microsoft Advertising consent block under the default basic route;
5. documented dynamic remarketing transformations when applicable.

The UET base tag can have an inherent documented page-load event. Treat that as a vendor-specific exception to the normal no-page-view base-tag preference, document it, and do not add a duplicate manual page-load event.

Inspect automatic SPA tracking before adding history-based or manually generated page-load events.

## Map fields exactly

Build a field-level map from the media request and dataLayer to the current UET parameters. Keep
template labels, UET JavaScript parameter names, and Microsoft conversion-goal conditions distinct.
For each field record required/conditional/approved-optional status, type/cardinality, source, GTM
resolution, installed-template field, consent, and whether it belongs to the browser UET request or
only to a server/offline API. Do not place server-only fields into the browser tag.

Use the current UET parameter table to determine accepted types and conditional requirements. Do not invent an event category/action hierarchy merely to resemble Universal Analytics.

For revenue conversions, verify the exact revenue/value and currency fields expected by both the UET event and the platform-side goal. Use an actual order ID only where the current browser schema supports and requires it.

Require every design-time required source before mutation, then map runtime values directly. Do not
add an `Eligible` Custom JavaScript variable, suppress an empty runtime payload speculatively, or
invent fallback values. Runtime missing data remains a site/dataLayer and recette dependency.

## Apply consent

Default to basic UET Consent Mode/strict gating:

- block the UET base and event tags until the required vendor consent is granted;
- fire a page-load/base tag from the verified CMP readiness/grant event and a business tag from its
  approved Custom Event;
- use `Block - <CMP> - Microsoft Ads denied`;
- prove from the static trigger graph that unknown and denied states are expected to keep UET tags blocked.

For a UET tag loaded after the page's consent state has already been established, inspect and use
the current template's documented page-load consent inheritance option so its first dispatch sees
the current `ad_storage` state. Do not rely only on a future consent-update event.

Use advanced UET Consent Mode only when explicitly requested and approved. Verify the current official `ad_storage` behavior and official GTM template options, set the documented denied default before events, send updates from the CMP, and remove/avoid a blocking trigger or Additional Consent Check that would defeat approved anonymized denied-state collection.

Do not infer Google Consent Mode's full consent-type set or behavior for UET. Follow Microsoft's current documentation.

If Clarity is present, do not treat it as merely part of UET. Inspect whether it is standalone or enabled through UET and follow current Clarity Consent Mode documentation. Under an explicitly approved Clarity advanced route, its script loads under denied consent and operates with documented limited cookieless behavior. Verify the current case-sensitive Consent API V2 fields, including `analytics_Storage` and `ad_Storage`, and keep Clarity's decision separate from Microsoft Advertising's UET `ad_storage` decision.

Under strict/basic policy, apply the separately approved Clarity block. Under advanced Clarity behavior, do not attach that block merely because UET is blocked. Do not broaden a Microsoft Advertising request into new Clarity collection without explicit scope and approval.

## Verify the saved Microsoft setup

Re-read the UET base and event tags, destination constant, variables, triggers, consent blocks or
approved defaults/updates, installed-template fields, automatic SPA option, firing settings, and
references. Confirm the base's inherent page-load behavior has no manual duplicate and an identical
rerun is a no-op. Keep Microsoft Advertising goals and any separate Clarity configuration outside
the GTM completion claim.

## Official entry points

- https://learn.microsoft.com/en-us/advertising/msa-help/hlp_ba_conc_uetv2customevent
- https://learn.microsoft.com/en-us/advertising/msa-help/hlp_ba_conc_uet_parameters_table
- https://learn.microsoft.com/en-us/advertising/msa-help/hlp_ba_conc_uet_consent
- https://learn.microsoft.com/en-us/advertising/msa-help/hlp_ba_conc_uet_dynamicconsentgtm
- https://learn.microsoft.com/en-us/clarity/setup-and-installation/consent-mode
- https://learn.microsoft.com/en-us/clarity/setup-and-installation/cmp-integration-guide

## Server route

When the exact Microsoft Conversions API product is requested, load
`server/media-microsoft-ads.md`. Inspect the supported server template and ID Sync dependency; do
not copy UET fields or invent a consent-grant dataLayer event.
