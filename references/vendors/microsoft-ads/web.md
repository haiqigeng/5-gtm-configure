# Microsoft Advertising browser tags

Apply the [media contract](../../media/common.md) and its linked implementation owners.

## Resolve UET semantics

Bing Ads/Bing UET refers to Microsoft Advertising unless another product is specified. Preserve
recognizable compatible existing names; use current terminology for new objects. Establish UET ID,
account/environment, conversion goal, source action, page-load/custom-event method, required
category/action/label/value/revenue/currency and dynamic remarketing/feed fields.

Inspect current official custom-event, parameter, template and remarketing contracts. UET template
labels, JavaScript parameters and platform goal conditions have distinct meanings. The installed
Microsoft template/API owns UET initialization, events and consent. The approved deployed CMP
contract supplies actual lifecycle events. Goal creation remains platform work.

## Coordinate base, events and fields

Reuse one compatible base and a stable UET-ID constant where useful. Separate requested custom
events, actual source actions and necessary dynamic remarketing projections. The base's inherent
page-load event counts as the page-load owner. Reconcile automatic SPA collection with manual/history
views. Revenue/currency must satisfy both the browser schema and goal; order identity uses the
supported browser field when required. Browser and offline/server fields retain separate contracts.

## Resolve UET and Clarity consent separately

The [capability map](../../consent/product-capabilities.md) owns behavior classification. Checked
2026-09-29: [UET guidance](https://learn.microsoft.com/en-us/advertising/msa-help/hlp_ba_conc_uet_consent)
requires signals in EEA/UK/Switzerland with denied default where enforced. Verify the current rules,
state inherited at first load, updates after acceptance and later changes/pages. A tag loaded after
choice needs its installed template's documented page-load inheritance so first dispatch sees the
current `ad_storage`. Approved basic/advanced policy determines eligibility.

Clarity can be standalone or UET-integrated and has its own authorized scope/policy.
[Consent API V2](https://learn.microsoft.com/en-us/clarity/setup-and-installation/clarity-consent-api-v2)
uses case-sensitive `analytics_Storage` and `ad_Storage`; regional enforcement began 2025-10-31.
Its approved advanced route uses documented limited cookieless execution. Assess each execution
unit against the separate UET and Clarity decisions.

## Verify

Check UET destination, goal/event fields, inherited consent, update timing, automatic SPA and
page-load ownership. Record platform goals and separately scoped Clarity work in the handoff.

## Official entry points

- https://learn.microsoft.com/en-us/advertising/msa-help/hlp_ba_conc_uetv2customevent
- https://learn.microsoft.com/en-us/advertising/msa-help/hlp_ba_conc_uet_parameters_table
- https://learn.microsoft.com/en-us/advertising/msa-help/hlp_ba_conc_uet_consent
- https://learn.microsoft.com/en-us/advertising/msa-help/hlp_ba_conc_uet_dynamicconsentgtm
- https://learn.microsoft.com/en-us/clarity/setup-and-installation/consent-mode
- https://learn.microsoft.com/en-us/clarity/setup-and-installation/cmp-integration-guide

## Server route

For the exact Microsoft Conversions API product, load [Server](server.md). Inspect the supported
server template, ID Sync dependency and its independent field/consent contract.
